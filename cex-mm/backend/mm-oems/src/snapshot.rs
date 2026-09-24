//! Periodic Delta venue snapshot + markout backfill.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use chrono::{DateTime, Utc};
use serde_json::{json, Value};
use tokio::sync::{broadcast, RwLock};

use crate::delta::{parse_positions, parse_usd_balance, DeltaClient};
use crate::db::{
    backfill_markouts, insert_balance, insert_pnl_if_minute_elapsed, insert_position, Db,
};
use crate::supervisor::load_env_file;

pub type BotQtyMap = Arc<RwLock<HashMap<(String, String), f64>>>;
pub type SnapshotEventTx = broadcast::Sender<Value>;

pub fn new_bot_qty_map() -> BotQtyMap {
    Arc::new(RwLock::new(HashMap::new()))
}

pub fn new_snapshot_event_tx() -> SnapshotEventTx {
    let (tx, _) = broadcast::channel(64);
    tx
}

/// Build the JSON body pushed on `/api/stream/snapshots` after a successful snapshot.
///
/// `pnl` is included only when a `pnl_snapshots` row was inserted for this tick.
pub fn build_snapshot_stream_event(
    strategy_id: &str,
    ts: DateTime<Utc>,
    equity: f64,
    realized: f64,
    unrealized: f64,
    available: Option<f64>,
    pnl_inserted: bool,
) -> Value {
    let ts_str = ts.to_rfc3339();
    let mut event = json!({
        "strategy_id": strategy_id,
        "ts": ts_str,
        "equity": equity,
        "realized": realized,
        "unrealized": unrealized,
    });
    if let Some(avail) = available {
        event["available"] = json!(avail);
    }
    if pnl_inserted {
        event["pnl"] = json!({
            "ts": ts_str,
            "equity": equity,
            "realized": realized,
            "unrealized": unrealized,
        });
    }
    event
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
    snapshot_tx: SnapshotEventTx,
) {
    let Some(db) = db else {
        tracing::warn!("snapshot loop idle: no database");
        return;
    };
    let mut ticker = tokio::time::interval(Duration::from_secs(10));
    loop {
        ticker.tick().await;
        if let Err(e) =
            snapshot_once(&db, &quote_bot_env, &bot_qty, &strategy_id, &snapshot_tx).await
        {
            tracing::warn!(error = %e, "delta snapshot failed");
        }
    }
}

async fn snapshot_once(
    db: &Db,
    quote_bot_env: &PathBuf,
    bot_qty: &BotQtyMap,
    strategy_id: &str,
    snapshot_tx: &SnapshotEventTx,
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

    let pnl_inserted = insert_pnl_if_minute_elapsed(
        &db.pool,
        strategy_id,
        ts,
        total_realized,
        total_unrealized,
        bal.equity,
    )
    .await?;

    let event = build_snapshot_stream_event(
        strategy_id,
        ts,
        bal.equity,
        total_realized,
        total_unrealized,
        Some(bal.available),
        pnl_inserted,
    );
    let _ = snapshot_tx.send(event);
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    #[test]
    fn stream_event_includes_pnl_only_when_inserted() {
        let ts = Utc.with_ymd_and_hms(2026, 9, 24, 12, 0, 0).unwrap();
        let with_pnl = build_snapshot_stream_event("mm", ts, 128.76, 1.5, 0.85, Some(100.0), true);
        assert_eq!(with_pnl["strategy_id"], "mm");
        assert_eq!(with_pnl["equity"], 128.76);
        assert_eq!(with_pnl["realized"], 1.5);
        assert_eq!(with_pnl["unrealized"], 0.85);
        assert_eq!(with_pnl["available"], 100.0);
        assert!(with_pnl.get("pnl").is_some());
        assert_eq!(with_pnl["pnl"]["equity"], 128.76);
        assert_eq!(with_pnl["pnl"]["ts"], with_pnl["ts"]);

        let without = build_snapshot_stream_event("mm", ts, 128.76, 1.5, 0.85, Some(100.0), false);
        assert!(without.get("pnl").is_none());
        assert_eq!(without["available"], 100.0);
    }

    #[test]
    fn stream_event_omits_available_when_unknown() {
        let ts = Utc.with_ymd_and_hms(2026, 9, 24, 12, 0, 0).unwrap();
        let event = build_snapshot_stream_event("mm", ts, 10.0, 0.0, 0.0, None, false);
        assert!(event.get("available").is_none());
        assert!(event.get("pnl").is_none());
    }
}
