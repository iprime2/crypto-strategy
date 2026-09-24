//! Periodic Delta venue snapshot + markout backfill.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use chrono::Utc;
use tokio::sync::RwLock;

use crate::delta::{parse_positions, parse_usd_balance, DeltaClient};
use crate::db::{
    backfill_markouts, insert_balance, insert_pnl_if_minute_elapsed, insert_position, Db,
};
use crate::supervisor::load_env_file;

pub type BotQtyMap = Arc<RwLock<HashMap<(String, String), f64>>>;

pub fn new_bot_qty_map() -> BotQtyMap {
    Arc::new(RwLock::new(HashMap::new()))
}

pub async fn apply_fill_to_bot_qty(map: &BotQtyMap, strategy_id: &str, symbol: &str, side: &str, qty: f64) {
    let signed = if side.eq_ignore_ascii_case("buy") {
        qty
    } else {
        -qty
    };
    let mut g = map.write().await;
    *g.entry((strategy_id.to_string(), symbol.to_string()))
        .or_insert(0.0) += signed;
}

pub async fn run_snapshot_loop(
    db: Option<Db>,
    quote_bot_env: PathBuf,
    bot_qty: BotQtyMap,
    strategy_id: String,
) {
    let Some(db) = db else {
        tracing::warn!("snapshot loop idle: no database");
        return;
    };
    let mut ticker = tokio::time::interval(Duration::from_secs(10));
    loop {
        ticker.tick().await;
        if let Err(e) = snapshot_once(&db, &quote_bot_env, &bot_qty, &strategy_id).await {
            tracing::warn!(error = %e, "delta snapshot failed");
        }
    }
}

async fn snapshot_once(
    db: &Db,
    quote_bot_env: &PathBuf,
    bot_qty: &BotQtyMap,
    strategy_id: &str,
) -> anyhow::Result<()> {
    if !quote_bot_env.is_file() {
        return Ok(());
    }
    let pairs = load_env_file(quote_bot_env);
    let Some(client) = DeltaClient::from_env_pairs(&pairs) else {
        // No DELTA_API_KEY — skip quietly (do not log secrets).
        return Ok(());
    };

    let bal_json = client.wallet_balances().await?;
    let pos_json = client.positions_margined().await?;
    if bal_json.get("error").is_some() {
        anyhow::bail!("wallet balances error");
    }
    if pos_json.get("error").is_some() {
        anyhow::bail!("positions error");
    }

    let ts = Utc::now();
    let bal = parse_usd_balance(&bal_json);
    insert_balance(
        &db.pool,
        strategy_id,
        ts,
        bal.equity,
        bal.available,
        bal.blocked_margin,
    )
    .await?;

    let positions = parse_positions(&pos_json);
    let qty_guard = bot_qty.read().await;
    let mut total_realized = 0.0;
    let mut total_unrealized = 0.0;
    for p in &positions {
        total_realized += p.realized;
        total_unrealized += p.unrealized;
        let bot = qty_guard
            .get(&(strategy_id.to_string(), p.symbol.clone()))
            .copied()
            .unwrap_or(0.0);
        let mismatch = (p.venue_qty - bot).abs() > 1e-5;
        insert_position(
            &db.pool,
            strategy_id,
            &p.symbol,
            ts,
            p.venue_qty,
            bot,
            p.entry,
            p.mark,
            p.unrealized,
            p.realized,
            mismatch,
        )
        .await?;
        if p.mark > 0.0 {
            backfill_markouts(&db.pool, strategy_id, p.mark, ts).await?;
        }
    }
    drop(qty_guard);

    let _ = insert_pnl_if_minute_elapsed(
        &db.pool,
        strategy_id,
        ts,
        total_realized,
        total_unrealized,
        bal.equity,
    )
    .await?;
    Ok(())
}
