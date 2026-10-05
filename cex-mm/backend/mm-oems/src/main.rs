use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;

use mm_oems::api::{router, AppState};
use mm_oems::db::{self as oems_db, Db};
use mm_oems::delta::DeltaClient;
use mm_oems::runtime::{build_runtimes, specs_from_rows};
use mm_oems::snapshot::{new_bot_qty_map, new_snapshot_event_tx, run_snapshot_loop};
use mm_oems::supervisor::{load_env_file, Supervisor};
use mm_oems::sync::run_sync_loop;
use mm_oems::telemetry::run_tail_loop;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("mm_oems=info,tower_http=info")),
        )
        .init();

    let cex_mm_root = std::env::var("CEX_MM_ROOT")
        .map(PathBuf::from)
        .unwrap_or_else(|_| {
            // backend/mm-oems → cex-mm
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .and_then(|p| p.parent())
                .map(|p| p.to_path_buf())
                .unwrap_or_else(|| PathBuf::from("."))
        });
    let quote_bot_env = cex_mm_root.join("quote-bot/.env");
    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://oems:oems_local@127.0.0.1:5462/cex_mm_oems".to_string());

    let (db, db_ok) = match Db::connect(&database_url).await {
        Ok(db) => match db.migrate().await {
            Ok(()) => {
                tracing::info!("database connected and migrations applied");
                (Some(db), true)
            }
            Err(e) => {
                tracing::error!(error = %e, "database migrate failed; serving /health only for data routes");
                (None, false)
            }
        },
        Err(e) => {
            tracing::error!(
                error = %e,
                url = %database_url,
                "database unavailable; serving /health; data routes return 503"
            );
            (None, false)
        }
    };

    let bot_qty = new_bot_qty_map();
    let snapshot_tx = new_snapshot_event_tx();
    let supervisor = Arc::new(Supervisor::new());
    let allow_mainnet = std::env::var("OEMS_ALLOW_MAINNET").is_ok_and(|v| v == "1");

    // One runtime per strategy row: its Delta environment, profile, market, venue state, telemetry.
    let rows = match &db {
        Some(db) => oems_db::list_strategies(&db.pool).await.unwrap_or_default(),
        None => Vec::new(),
    };
    let runtimes = build_runtimes(&specs_from_rows(&rows), &cex_mm_root);
    let env_pairs = load_env_file(&quote_bot_env);
    for rt in runtimes.values() {
        tracing::info!(
            strategy = %rt.id,
            env = rt.env.label(),
            profile = ?rt.profile,
            keys = DeltaClient::from_env_pairs_for(&env_pairs, rt.env).is_some(),
            "strategy runtime"
        );
    }
    tracing::info!(allow_mainnet, "real-money starts {}", if allow_mainnet { "enabled" } else { "disabled (OEMS_ALLOW_MAINNET != 1)" });

    // Re-attach to a bot left running by a previous OEMS process.
    if let Some(db) = &db {
        if let Ok(rows) = oems_db::list_strategies(&db.pool).await {
            for row in rows {
                let id = row.get("id").and_then(|v| v.as_str()).unwrap_or_default();
                if let Some(pid) = row.get("last_pid").and_then(|v| v.as_i64()) {
                    if pid > 0 && supervisor.adopt(id, pid as u32) {
                        tracing::info!(strategy = id, pid, "adopted running bot");
                    }
                }
            }
        }
    }

    // OEMS_TELEMETRY_LOG pins the demo `mm` tailer to a file (dev / shadow runs).
    let pinned_log = std::env::var("OEMS_TELEMETRY_LOG").ok().filter(|s| !s.is_empty());
    for rt in runtimes.values() {
        tokio::spawn(run_snapshot_loop(db.clone(), quote_bot_env.clone(), rt.clone(), snapshot_tx.clone()));
        tokio::spawn(run_sync_loop(db.clone(), quote_bot_env.clone(), rt.clone()));
        match (&pinned_log, rt.id.as_str()) {
            (Some(path), "mm") => {
                tokio::spawn(mm_oems::telemetry::run_fixed_tail_loop(rt.telemetry.clone(), PathBuf::from(path)));
            }
            _ => {
                tokio::spawn(run_tail_loop(rt.telemetry.clone(), supervisor.clone(), rt.id.clone()));
            }
        }
    }

    let state = AppState {
        db,
        supervisor,
        cex_mm_root,
        quote_bot_env,
        bot_qty,
        db_ok,
        snapshot_tx,
        runtimes,
        allow_mainnet,
    };

    let app = router(state);
    let port: u16 = std::env::var("OEMS_PORT").ok().and_then(|p| p.parse().ok()).unwrap_or(8791);
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    tracing::info!(%addr, "mm-oems listening");
    let listener = match tokio::net::TcpListener::bind(addr).await {
        Ok(l) => l,
        Err(e) => {
            tracing::error!(error = %e, %addr, "bind failed");
            std::process::exit(1);
        }
    };
    if let Err(e) = axum::serve(listener, app).await {
        tracing::error!(error = %e, "server exited");
        std::process::exit(1);
    }
}
