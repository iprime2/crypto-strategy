use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;

use mm_oems::api::{router, AppState};
use mm_oems::db::Db;
use mm_oems::snapshot::{new_bot_qty_map, run_snapshot_loop};
use mm_oems::supervisor::Supervisor;
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
    if let Some(db_clone) = db.clone() {
        let env_path = quote_bot_env.clone();
        let map = bot_qty.clone();
        tokio::spawn(async move {
            run_snapshot_loop(Some(db_clone), env_path, map, "mm".into()).await;
        });
    }

    let state = AppState {
        db,
        supervisor: Arc::new(Supervisor::new()),
        cex_mm_root,
        quote_bot_env,
        bot_qty,
        db_ok,
    };

    let app = router(state);
    let addr = SocketAddr::from(([127, 0, 0, 1], 8791));
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
