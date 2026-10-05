//! SQLx runtime helpers (no compile-time query! macros).

use chrono::{DateTime, Timelike, Utc};
use serde_json::Value;
use sqlx::postgres::PgPoolOptions;
use sqlx::{PgPool, Row};
use std::collections::BTreeMap;

use crate::analytics::{avg_nullable_bps, AnalyticsBucket};
use crate::tca::{compute_tca, markout_bps};

#[derive(Clone)]
pub struct Db {
    pub pool: PgPool,
}

impl Db {
    pub async fn connect(database_url: &str) -> anyhow::Result<Self> {
        let pool = PgPoolOptions::new()
            .max_connections(5)
            .acquire_timeout(std::time::Duration::from_secs(3))
            .connect(database_url)
            .await?;
        Ok(Self { pool })
    }

    pub async fn migrate(&self) -> anyhow::Result<()> {
        let migrator = sqlx::migrate::Migrator::new(std::path::Path::new(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/migrations"
        )))
        .await?;
        migrator.run(&self.pool).await?;
        Ok(())
    }
}

pub async fn list_strategies(pool: &PgPool) -> sqlx::Result<Vec<Value>> {
    let rows = sqlx::query(
        "SELECT id, name, desired_state, last_pid, env, profile FROM strategies ORDER BY id",
    )
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "id": r.get::<String, _>("id"),
                "name": r.get::<String, _>("name"),
                "desired_state": r.get::<String, _>("desired_state"),
                "last_pid": r.get::<Option<i64>, _>("last_pid"),
                "env": r.get::<String, _>("env"),
                "profile": r.get::<Option<String>, _>("profile"),
            })
        })
        .collect())
}

pub async fn get_strategy(pool: &PgPool, id: &str) -> sqlx::Result<Option<Value>> {
    let row = sqlx::query(
        "SELECT id, name, desired_state, last_pid, env, profile FROM strategies WHERE id = $1",
    )
    .bind(id)
    .fetch_optional(pool)
    .await?;
    Ok(row.map(|r| {
        serde_json::json!({
            "id": r.get::<String, _>("id"),
            "name": r.get::<String, _>("name"),
            "desired_state": r.get::<String, _>("desired_state"),
            "last_pid": r.get::<Option<i64>, _>("last_pid"),
            "env": r.get::<String, _>("env"),
            "profile": r.get::<Option<String>, _>("profile"),
        })
    }))
}

pub async fn set_desired_state_and_pid(
    pool: &PgPool,
    id: &str,
    desired_state: &str,
    last_pid: Option<i64>,
) -> sqlx::Result<()> {
    sqlx::query(
        "UPDATE strategies SET desired_state = $2, last_pid = $3 WHERE id = $1",
    )
    .bind(id)
    .bind(desired_state)
    .bind(last_pid)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn latest_config(pool: &PgPool, strategy_id: &str) -> sqlx::Result<Option<Value>> {
    let row = sqlx::query(
        r#"SELECT id, strategy_id, version, body, created_at
           FROM strategy_config WHERE strategy_id = $1
           ORDER BY version DESC LIMIT 1"#,
    )
    .bind(strategy_id)
    .fetch_optional(pool)
    .await?;
    Ok(row.map(|r| {
        serde_json::json!({
            "id": r.get::<i64, _>("id"),
            "strategy_id": r.get::<String, _>("strategy_id"),
            "version": r.get::<i32, _>("version"),
            "body": r.get::<Value, _>("body"),
            "created_at": r.get::<DateTime<Utc>, _>("created_at"),
        })
    }))
}

pub async fn insert_config(pool: &PgPool, strategy_id: &str, body: &Value) -> sqlx::Result<Value> {
    let next: i32 = sqlx::query_scalar(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM strategy_config WHERE strategy_id = $1",
    )
    .bind(strategy_id)
    .fetch_one(pool)
    .await?;
    let row = sqlx::query(
        r#"INSERT INTO strategy_config (strategy_id, version, body)
           VALUES ($1, $2, $3)
           RETURNING id, strategy_id, version, body, created_at"#,
    )
    .bind(strategy_id)
    .bind(next)
    .bind(body)
    .fetch_one(pool)
    .await?;
    Ok(serde_json::json!({
        "id": row.get::<i64, _>("id"),
        "strategy_id": row.get::<String, _>("strategy_id"),
        "version": row.get::<i32, _>("version"),
        "body": row.get::<Value, _>("body"),
        "created_at": row.get::<DateTime<Utc>, _>("created_at"),
    }))
}

pub async fn upsert_order(
    pool: &PgPool,
    strategy_id: &str,
    client_order_id: &str,
    symbol: &str,
    side: &str,
    price: f64,
    qty: f64,
    reduce_only: bool,
    reject_code: Option<&str>,
    status: &str,
) -> sqlx::Result<()> {
    sqlx::query(
        r#"INSERT INTO orders
            (strategy_id, client_order_id, symbol, side, price, qty, reduce_only, reject_code, status)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
           ON CONFLICT (strategy_id, client_order_id) DO UPDATE SET
             symbol = EXCLUDED.symbol,
             side = EXCLUDED.side,
             price = EXCLUDED.price,
             qty = EXCLUDED.qty,
             reduce_only = EXCLUDED.reduce_only,
             reject_code = EXCLUDED.reject_code,
             status = EXCLUDED.status"#,
    )
    .bind(strategy_id)
    .bind(client_order_id)
    .bind(symbol)
    .bind(side)
    .bind(price)
    .bind(qty)
    .bind(reduce_only)
    .bind(reject_code)
    .bind(status)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn insert_fill_and_tca(
    pool: &PgPool,
    strategy_id: &str,
    trade_id: &str,
    client_order_id: Option<&str>,
    symbol: &str,
    side: &str,
    price: f64,
    qty: f64,
    fee: f64,
    limit_price: f64,
    arrival_mid: f64,
    mid_at_fill: f64,
) -> sqlx::Result<()> {
    sqlx::query(
        r#"INSERT INTO fills
            (strategy_id, trade_id, client_order_id, symbol, side, price, qty, fee,
             limit_price, arrival_mid, mid_at_fill)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
           ON CONFLICT (strategy_id, trade_id) DO NOTHING"#,
    )
    .bind(strategy_id)
    .bind(trade_id)
    .bind(client_order_id)
    .bind(symbol)
    .bind(side)
    .bind(price)
    .bind(qty)
    .bind(fee)
    .bind(limit_price)
    .bind(arrival_mid)
    .bind(mid_at_fill)
    .execute(pool)
    .await?;

    let tca = compute_tca(
        side,
        price,
        qty,
        fee,
        limit_price,
        arrival_mid,
        mid_at_fill,
    );
    sqlx::query(
        r#"INSERT INTO tca_fills
            (strategy_id, trade_id, slippage_bps, quoted_half_spread_bps, effective_spread_bps,
             fee_quote, fee_bps, markout_1s_bps, markout_5s_bps, markout_30s_bps, net_5s_bps)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
           ON CONFLICT (strategy_id, trade_id) DO NOTHING"#,
    )
    .bind(strategy_id)
    .bind(trade_id)
    .bind(tca.slippage_bps)
    .bind(tca.quoted_half_spread_bps)
    .bind(tca.effective_spread_bps)
    .bind(tca.fee_quote)
    .bind(tca.fee_bps)
    .bind(tca.markout_1s_bps)
    .bind(tca.markout_5s_bps)
    .bind(tca.markout_30s_bps)
    .bind(tca.net_5s_bps)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn insert_balance(
    pool: &PgPool,
    strategy_id: &str,
    ts: DateTime<Utc>,
    equity: f64,
    available: f64,
    blocked_margin: f64,
) -> sqlx::Result<()> {
    sqlx::query(
        r#"INSERT INTO balances (strategy_id, ts, equity, available, blocked_margin)
           VALUES ($1,$2,$3,$4,$5)"#,
    )
    .bind(strategy_id)
    .bind(ts)
    .bind(equity)
    .bind(available)
    .bind(blocked_margin)
    .execute(pool)
    .await?;
    Ok(())
}

pub async fn insert_position(
    pool: &PgPool,
    strategy_id: &str,
    symbol: &str,
    ts: DateTime<Utc>,
    venue_qty: f64,
    bot_qty: Option<f64>,
    entry: f64,
    mark: f64,
    unrealized: f64,
    realized: f64,
    mismatch: bool,
    liq_price: Option<f64>,
    margin: Option<f64>,
) -> sqlx::Result<()> {
    sqlx::query(
        r#"INSERT INTO positions
            (strategy_id, symbol, ts, venue_qty, bot_qty, entry, mark, unrealized, realized, mismatch,
             liq_price, margin)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)"#,
    )
    .bind(strategy_id)
    .bind(symbol)
    .bind(ts)
    .bind(venue_qty)
    .bind(bot_qty)
    .bind(entry)
    .bind(mark)
    .bind(unrealized)
    .bind(realized)
    .bind(mismatch)
    .bind(liq_price)
    .bind(margin)
    .execute(pool)
    .await?;
    Ok(())
}

/// Symbols whose latest recorded venue position is non-zero.
pub async fn open_position_symbols(pool: &PgPool, strategy_id: &str) -> sqlx::Result<Vec<String>> {
    let rows = sqlx::query(
        r#"SELECT symbol FROM (
             SELECT DISTINCT ON (symbol) symbol, venue_qty FROM positions
             WHERE strategy_id = $1 ORDER BY symbol, ts DESC) latest
           WHERE venue_qty <> 0"#,
    )
    .bind(strategy_id)
    .fetch_all(pool)
    .await?;
    Ok(rows.into_iter().map(|r| r.get::<String, _>("symbol")).collect())
}

pub async fn insert_pnl_if_minute_elapsed(
    pool: &PgPool,
    strategy_id: &str,
    ts: DateTime<Utc>,
    realized: f64,
    unrealized: f64,
    equity: f64,
) -> sqlx::Result<bool> {
    let last: Option<DateTime<Utc>> = sqlx::query_scalar(
        "SELECT ts FROM pnl_snapshots WHERE strategy_id = $1 ORDER BY ts DESC LIMIT 1",
    )
    .bind(strategy_id)
    .fetch_optional(pool)
    .await?;
    if let Some(prev) = last {
        if (ts - prev).num_seconds() < 60 {
            return Ok(false);
        }
    }
    sqlx::query(
        r#"INSERT INTO pnl_snapshots (strategy_id, ts, realized, unrealized, equity)
           VALUES ($1,$2,$3,$4,$5)"#,
    )
    .bind(strategy_id)
    .bind(ts)
    .bind(realized)
    .bind(unrealized)
    .bind(equity)
    .execute(pool)
    .await?;
    Ok(true)
}

const POSITION_COLS: &str =
    "symbol, ts, venue_qty, bot_qty, entry, mark, unrealized, realized, mismatch, liq_price, margin";

fn position_json(r: &sqlx::postgres::PgRow) -> Value {
    serde_json::json!({
        "symbol": r.get::<String, _>("symbol"),
        "ts": r.get::<DateTime<Utc>, _>("ts"),
        "venue_qty": r.get::<f64, _>("venue_qty"),
        "bot_qty": r.get::<Option<f64>, _>("bot_qty"),
        "entry": r.get::<f64, _>("entry"),
        "mark": r.get::<f64, _>("mark"),
        "unrealized": r.get::<f64, _>("unrealized"),
        "realized": r.get::<f64, _>("realized"),
        "mismatch": r.get::<bool, _>("mismatch"),
        "liq_price": r.get::<Option<f64>, _>("liq_price"),
        "margin": r.get::<Option<f64>, _>("margin"),
    })
}

fn clamp_limit(limit: Option<i64>) -> i64 {
    let n = limit.unwrap_or(100);
    n.clamp(1, 500)
}

pub async fn latest_snapshots(pool: &PgPool, strategy_id: &str) -> sqlx::Result<Value> {
    let bal = sqlx::query(
        r#"SELECT ts, equity, available, blocked_margin FROM balances
           WHERE strategy_id = $1 ORDER BY ts DESC LIMIT 1"#,
    )
    .bind(strategy_id)
    .fetch_optional(pool)
    .await?;
    let pnl = sqlx::query(
        r#"SELECT ts, realized, unrealized, equity FROM pnl_snapshots
           WHERE strategy_id = $1 ORDER BY ts DESC LIMIT 1"#,
    )
    .bind(strategy_id)
    .fetch_optional(pool)
    .await?;
    // Latest row per symbol, open positions only: a closed position gets a zero row
    // from the snapshot loop, so it drops out here instead of showing stale size.
    let positions = sqlx::query(&format!(
        r#"SELECT * FROM (
             SELECT DISTINCT ON (symbol) {POSITION_COLS}
             FROM positions WHERE strategy_id = $1
             ORDER BY symbol, ts DESC) latest
           WHERE venue_qty <> 0"#
    ))
    .bind(strategy_id)
    .fetch_all(pool)
    .await?;
    Ok(serde_json::json!({
        "strategy_id": strategy_id,
        "balance": bal.map(|r| serde_json::json!({
            "ts": r.get::<DateTime<Utc>, _>("ts"),
            "equity": r.get::<f64, _>("equity"),
            "available": r.get::<f64, _>("available"),
            "blocked_margin": r.get::<f64, _>("blocked_margin"),
        })),
        "pnl": pnl.map(|r| serde_json::json!({
            "ts": r.get::<DateTime<Utc>, _>("ts"),
            "realized": r.get::<f64, _>("realized"),
            "unrealized": r.get::<f64, _>("unrealized"),
            "equity": r.get::<f64, _>("equity"),
        })),
        "positions": positions.iter().map(position_json).collect::<Vec<_>>(),
    }))
}

pub async fn list_pnl_between(
    pool: &PgPool,
    strategy_id: &str,
    from: DateTime<Utc>,
    to: DateTime<Utc>,
) -> sqlx::Result<Vec<Value>> {
    let rows = sqlx::query(
        r#"SELECT ts, realized, unrealized, equity FROM pnl_snapshots
           WHERE strategy_id = $1 AND ts >= $2 AND ts <= $3
           ORDER BY ts DESC LIMIT 2000"#,
    )
    .bind(strategy_id)
    .bind(from)
    .bind(to)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "ts": r.get::<DateTime<Utc>, _>("ts"),
                "realized": r.get::<f64, _>("realized"),
                "unrealized": r.get::<f64, _>("unrealized"),
                "equity": r.get::<f64, _>("equity"),
            })
        })
        .collect())
}

pub async fn list_pnl(pool: &PgPool, strategy_id: &str, limit: Option<i64>) -> sqlx::Result<Vec<Value>> {
    let lim = clamp_limit(limit);
    let rows = sqlx::query(
        r#"SELECT ts, realized, unrealized, equity FROM pnl_snapshots
           WHERE strategy_id = $1 ORDER BY ts DESC LIMIT $2"#,
    )
    .bind(strategy_id)
    .bind(lim)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "ts": r.get::<DateTime<Utc>, _>("ts"),
                "realized": r.get::<f64, _>("realized"),
                "unrealized": r.get::<f64, _>("unrealized"),
                "equity": r.get::<f64, _>("equity"),
            })
        })
        .collect())
}

pub async fn list_positions(
    pool: &PgPool,
    strategy_id: &str,
    limit: Option<i64>,
) -> sqlx::Result<Vec<Value>> {
    let lim = clamp_limit(limit);
    let rows = sqlx::query(&format!(
        "SELECT {POSITION_COLS} FROM positions WHERE strategy_id = $1 ORDER BY ts DESC LIMIT $2"
    ))
    .bind(strategy_id)
    .bind(lim)
    .fetch_all(pool)
    .await?;
    Ok(rows.iter().map(position_json).collect())
}

pub async fn list_orders(
    pool: &PgPool,
    strategy_id: &str,
    limit: Option<i64>,
) -> sqlx::Result<Vec<Value>> {
    let lim = clamp_limit(limit);
    let rows = sqlx::query(
        r#"SELECT client_order_id, symbol, side, price, qty, reduce_only, reject_code, status, created_at
           FROM orders WHERE strategy_id = $1 ORDER BY created_at DESC LIMIT $2"#,
    )
    .bind(strategy_id)
    .bind(lim)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "client_order_id": r.get::<String, _>("client_order_id"),
                "symbol": r.get::<String, _>("symbol"),
                "side": r.get::<String, _>("side"),
                "price": r.get::<f64, _>("price"),
                "qty": r.get::<f64, _>("qty"),
                "reduce_only": r.get::<bool, _>("reduce_only"),
                "reject_code": r.get::<Option<String>, _>("reject_code"),
                "status": r.get::<String, _>("status"),
                "created_at": r.get::<DateTime<Utc>, _>("created_at"),
            })
        })
        .collect())
}

pub async fn list_fills(
    pool: &PgPool,
    strategy_id: &str,
    limit: Option<i64>,
) -> sqlx::Result<Vec<Value>> {
    let lim = clamp_limit(limit);
    let rows = sqlx::query(
        r#"SELECT trade_id, client_order_id, order_id, symbol, side, role, source, price, qty, fee,
                  limit_price, arrival_mid, mid_at_fill, created_at
           FROM fills WHERE strategy_id = $1 ORDER BY created_at DESC LIMIT $2"#,
    )
    .bind(strategy_id)
    .bind(lim)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|r| {
            let side: String = r.get("side");
            let price: f64 = r.get("price");
            let qty: f64 = r.get("qty");
            let mid: f64 = r.get("mid_at_fill");
            let fee: f64 = r.get("fee");
            serde_json::json!({
                "trade_id": r.get::<String, _>("trade_id"),
                "client_order_id": r.get::<Option<String>, _>("client_order_id"),
                "order_id": r.get::<Option<String>, _>("order_id"),
                "symbol": r.get::<String, _>("symbol"),
                "side": side,
                "role": r.get::<Option<String>, _>("role"),
                "source": r.get::<String, _>("source"),
                "price": price,
                "qty": qty,
                "notional": price * qty,
                "fee": fee,
                "fee_bps": if price * qty > 0.0 { Some(fee / (price * qty) * 1e4) } else { None },
                "limit_price": r.get::<f64, _>("limit_price"),
                "arrival_mid": r.get::<f64, _>("arrival_mid"),
                "mid_at_fill": mid,
                "capture_bps": capture_bps(&side, price, mid),
                "created_at": r.get::<DateTime<Utc>, _>("created_at"),
            })
        })
        .collect())
}

/// Spread earned vs the mid at fill, in bps: positive when a buy is below mid or a sell above it.
pub fn capture_bps(side: &str, price: f64, mid: f64) -> Option<f64> {
    if mid <= 0.0 {
        return None;
    }
    Some(crate::tca::side_sign(side) * (mid - price) / mid * 10_000.0)
}

pub async fn list_tca(
    pool: &PgPool,
    strategy_id: &str,
    limit: Option<i64>,
) -> sqlx::Result<Vec<Value>> {
    let lim = clamp_limit(limit);
    let rows = sqlx::query(
        r#"SELECT t.trade_id, f.symbol, f.side, f.role, f.price, f.qty, f.mid_at_fill, f.created_at,
                  t.slippage_bps, t.quoted_half_spread_bps, t.effective_spread_bps,
                  t.fee_quote, t.fee_bps, t.markout_1s_bps, t.markout_5s_bps, t.markout_30s_bps,
                  t.markout_60s_bps, t.net_5s_bps
           FROM tca_fills t
           JOIN fills f ON f.strategy_id = t.strategy_id AND f.trade_id = t.trade_id
           WHERE t.strategy_id = $1
           ORDER BY f.created_at DESC LIMIT $2"#,
    )
    .bind(strategy_id)
    .bind(lim)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|r| {
            let side: String = r.get("side");
            let capture = capture_bps(&side, r.get("price"), r.get("mid_at_fill"));
            let fee_bps: f64 = r.get("fee_bps");
            let m60: Option<f64> = r.get("markout_60s_bps");
            serde_json::json!({
                "trade_id": r.get::<String, _>("trade_id"),
                "symbol": r.get::<String, _>("symbol"),
                "side": side,
                "role": r.get::<Option<String>, _>("role"),
                "price": r.get::<f64, _>("price"),
                "qty": r.get::<f64, _>("qty"),
                "created_at": r.get::<DateTime<Utc>, _>("created_at"),
                "capture_bps": capture,
                "slippage_bps": r.get::<f64, _>("slippage_bps"),
                "quoted_half_spread_bps": r.get::<f64, _>("quoted_half_spread_bps"),
                "effective_spread_bps": r.get::<f64, _>("effective_spread_bps"),
                "fee_quote": r.get::<f64, _>("fee_quote"),
                "fee_bps": fee_bps,
                "markout_1s_bps": r.get::<Option<f64>, _>("markout_1s_bps"),
                "markout_5s_bps": r.get::<Option<f64>, _>("markout_5s_bps"),
                "markout_30s_bps": r.get::<Option<f64>, _>("markout_30s_bps"),
                "markout_60s_bps": m60,
                "net_5s_bps": r.get::<Option<f64>, _>("net_5s_bps"),
                "net_60s_bps": match (capture, m60) {
                    (Some(c), Some(m)) => Some(c + m - fee_bps),
                    _ => None,
                },
            })
        })
        .collect())
}

pub async fn reconcile(pool: &PgPool, strategy_id: &str, limit: Option<i64>) -> sqlx::Result<Value> {
    let lim = clamp_limit(limit);
    let mismatches = sqlx::query(&format!(
        r#"SELECT {POSITION_COLS} FROM positions WHERE strategy_id = $1 AND mismatch = TRUE
           ORDER BY ts DESC LIMIT $2"#
    ))
    .bind(strategy_id)
    .bind(lim)
    .fetch_all(pool)
    .await?;
    let latest = sqlx::query(&format!(
        r#"SELECT DISTINCT ON (symbol) {POSITION_COLS} FROM positions WHERE strategy_id = $1
           ORDER BY symbol, ts DESC"#
    ))
    .bind(strategy_id)
    .fetch_all(pool)
    .await?;
    Ok(serde_json::json!({
        "mismatches": mismatches.iter().map(position_json).collect::<Vec<_>>(),
        "latest_by_symbol": latest.iter().map(position_json).collect::<Vec<_>>(),
    }))
}

#[derive(Default)]
struct FillBucketAgg {
    slippage: Vec<Option<f64>>,
    fee_quote: f64,
    volume_quote: f64,
    effective_spread: Vec<Option<f64>>,
    markout_5s: Vec<Option<f64>>,
    net_5s: Vec<Option<f64>>,
}

/// Analytics series + heatmap for a strategy over `[from, to]` (UTC).
pub async fn analytics(
    pool: &PgPool,
    strategy_id: &str,
    from: DateTime<Utc>,
    to: DateTime<Utc>,
    bucket: AnalyticsBucket,
) -> sqlx::Result<Value> {
    let trunc = bucket.date_trunc_unit();

    // Fills joined to TCA — raw rows; bucket in Rust so unit-tested avg applies.
    let fill_sql = format!(
        r#"SELECT date_trunc('{trunc}', f.created_at) AS bucket_ts,
                  f.created_at,
                  f.price * f.qty AS volume_quote,
                  t.slippage_bps,
                  t.fee_quote,
                  t.effective_spread_bps,
                  t.markout_5s_bps,
                  t.net_5s_bps
           FROM fills f
           JOIN tca_fills t
             ON t.strategy_id = f.strategy_id AND t.trade_id = f.trade_id
           WHERE f.strategy_id = $1
             AND f.created_at >= $2
             AND f.created_at <= $3
           ORDER BY f.created_at ASC"#
    );
    let fill_rows = sqlx::query(&fill_sql)
        .bind(strategy_id)
        .bind(from)
        .bind(to)
        .fetch_all(pool)
        .await?;

    let mut fill_by_bucket: BTreeMap<DateTime<Utc>, FillBucketAgg> = BTreeMap::new();
    let mut heat_slip: BTreeMap<(String, i32), Vec<Option<f64>>> = BTreeMap::new();
    let mut heat_fee: BTreeMap<(String, i32), f64> = BTreeMap::new();
    let mut heat_vol: BTreeMap<(String, i32), f64> = BTreeMap::new();

    for r in fill_rows {
        let bucket_ts: DateTime<Utc> = r.get("bucket_ts");
        let created: DateTime<Utc> = r.get("created_at");
        let volume_quote: f64 = r.get("volume_quote");
        let slippage: f64 = r.get("slippage_bps");
        let fee_quote: f64 = r.get("fee_quote");
        let eff: f64 = r.get("effective_spread_bps");
        let markout_5s: Option<f64> = r.get("markout_5s_bps");
        let net_5s: Option<f64> = r.get("net_5s_bps");

        let agg = fill_by_bucket.entry(bucket_ts).or_default();
        agg.slippage.push(Some(slippage));
        agg.fee_quote += fee_quote;
        agg.volume_quote += volume_quote;
        agg.effective_spread.push(Some(eff));
        agg.markout_5s.push(markout_5s);
        agg.net_5s.push(net_5s);

        let day = created.format("%Y-%m-%d").to_string();
        let hour = created.hour() as i32;
        let key = (day, hour);
        heat_slip.entry(key.clone()).or_default().push(Some(slippage));
        *heat_fee.entry(key.clone()).or_default() += fee_quote;
        *heat_vol.entry(key).or_default() += volume_quote;
    }

    // PnL: last snapshot in each series bucket; equity heatmap by UTC day+hour.
    let pnl_sql = format!(
        r#"SELECT date_trunc('{trunc}', ts) AS bucket_ts,
                  ts, equity, realized, unrealized
           FROM pnl_snapshots
           WHERE strategy_id = $1
             AND ts >= $2
             AND ts <= $3
           ORDER BY ts ASC"#
    );
    let pnl_rows = sqlx::query(&pnl_sql)
        .bind(strategy_id)
        .bind(from)
        .bind(to)
        .fetch_all(pool)
        .await?;

    let mut pnl_by_bucket: BTreeMap<DateTime<Utc>, (f64, f64, f64)> = BTreeMap::new();
    let mut heat_equity: BTreeMap<(String, i32), f64> = BTreeMap::new();
    for r in pnl_rows {
        let bucket_ts: DateTime<Utc> = r.get("bucket_ts");
        let ts: DateTime<Utc> = r.get("ts");
        let equity: f64 = r.get("equity");
        let realized: f64 = r.get("realized");
        let unrealized: f64 = r.get("unrealized");
        // ASC order → last write wins = last snapshot in bucket.
        pnl_by_bucket.insert(bucket_ts, (equity, realized, unrealized));
        let day = ts.format("%Y-%m-%d").to_string();
        let hour = ts.hour() as i32;
        heat_equity.insert((day, hour), equity);
    }

    let mut series_keys: BTreeMap<DateTime<Utc>, ()> = BTreeMap::new();
    for k in fill_by_bucket.keys() {
        series_keys.insert(*k, ());
    }
    for k in pnl_by_bucket.keys() {
        series_keys.insert(*k, ());
    }

    let series: Vec<Value> = series_keys
        .into_keys()
        .map(|ts| {
            let fill = fill_by_bucket.get(&ts);
            let pnl = pnl_by_bucket.get(&ts);
            serde_json::json!({
                "ts": ts,
                "slippage_bps": fill.and_then(|f| avg_nullable_bps(&f.slippage)),
                "fee_quote": fill.map(|f| f.fee_quote).unwrap_or(0.0),
                "volume_quote": fill.map(|f| f.volume_quote).unwrap_or(0.0),
                "equity": pnl.map(|(e, _, _)| *e),
                "realized": pnl.map(|(_, r, _)| *r),
                "unrealized": pnl.map(|(_, _, u)| *u),
                "effective_spread_bps": fill.and_then(|f| avg_nullable_bps(&f.effective_spread)),
                "markout_5s_bps": fill.and_then(|f| avg_nullable_bps(&f.markout_5s)),
                "net_5s_bps": fill.and_then(|f| avg_nullable_bps(&f.net_5s)),
            })
        })
        .collect();

    let heat_cells = |map: &BTreeMap<(String, i32), f64>| -> Vec<Value> {
        map.iter()
            .map(|((day, hour), value)| {
                serde_json::json!({ "day": day, "hour": hour, "value": value })
            })
            .collect()
    };
    let heat_avg_cells = |map: &BTreeMap<(String, i32), Vec<Option<f64>>>| -> Vec<Value> {
        map.iter()
            .filter_map(|((day, hour), vals)| {
                avg_nullable_bps(vals).map(|value| {
                    serde_json::json!({ "day": day, "hour": hour, "value": value })
                })
            })
            .collect()
    };

    Ok(serde_json::json!({
        "from": from,
        "to": to,
        "bucket": bucket.as_str(),
        "series": series,
        "heatmap": {
            "slippage_bps": heat_avg_cells(&heat_slip),
            "fee_quote": heat_cells(&heat_fee),
            "volume_quote": heat_cells(&heat_vol),
            "equity": heat_cells(&heat_equity),
        },
    }))
}

// ---------------------------------------------------------------- venue truth

/// Insert a venue fill and its TCA row. Returns false when the fill was already stored.
pub async fn insert_venue_fill(
    pool: &PgPool,
    strategy_id: &str,
    f: &crate::delta::VenueFill,
    mid: f64,
) -> sqlx::Result<bool> {
    let res = sqlx::query(
        r#"INSERT INTO fills
            (strategy_id, trade_id, client_order_id, order_id, symbol, side, role, source, price, qty,
             fee, limit_price, arrival_mid, mid_at_fill, created_at)
           VALUES ($1,$2,NULL,$3,$4,$5,$6,'venue',$7,$8,$9,$10,$11,$11,$12)
           ON CONFLICT (strategy_id, trade_id) DO NOTHING"#,
    )
    .bind(strategy_id)
    .bind(&f.id)
    .bind(&f.order_id)
    .bind(&f.symbol)
    .bind(&f.side)
    .bind(&f.role)
    .bind(f.price)
    .bind(f.qty)
    .bind(f.fee)
    .bind(f.order_price)
    .bind(mid)
    .bind(f.created_at)
    .execute(pool)
    .await?;
    if res.rows_affected() == 0 {
        return Ok(false);
    }
    let tca = compute_tca(&f.side, f.price, f.qty, f.fee, f.order_price, mid, mid);
    sqlx::query(
        r#"INSERT INTO tca_fills
            (strategy_id, trade_id, slippage_bps, quoted_half_spread_bps, effective_spread_bps,
             fee_quote, fee_bps, markout_1s_bps, markout_5s_bps, markout_30s_bps, net_5s_bps)
           VALUES ($1,$2,$3,$4,$5,$6,$7,NULL,NULL,NULL,NULL)
           ON CONFLICT (strategy_id, trade_id) DO NOTHING"#,
    )
    .bind(strategy_id)
    .bind(&f.id)
    .bind(tca.slippage_bps)
    .bind(tca.quoted_half_spread_bps)
    .bind(tca.effective_spread_bps)
    .bind(tca.fee_quote)
    .bind(tca.fee_bps)
    .execute(pool)
    .await?;
    Ok(true)
}

#[allow(clippy::too_many_arguments)]
pub async fn insert_tick(
    pool: &PgPool,
    env: &str,
    symbol: &str,
    ts: DateTime<Utc>,
    mark: f64,
    bid: Option<f64>,
    ask: Option<f64>,
    last: Option<f64>,
    spot: Option<f64>,
) -> sqlx::Result<()> {
    sqlx::query(
        r#"INSERT INTO ticks (env, symbol, ts, mark, bid, ask, last, spot)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (env, symbol, ts) DO NOTHING"#,
    )
    .bind(env)
    .bind(symbol)
    .bind(ts)
    .bind(mark)
    .bind(bid)
    .bind(ask)
    .bind(last)
    .bind(spot)
    .execute(pool)
    .await?;
    Ok(())
}

fn tick_mid(r: &sqlx::postgres::PgRow) -> f64 {
    match (r.get::<Option<f64>, _>("bid"), r.get::<Option<f64>, _>("ask")) {
        (Some(b), Some(a)) if b > 0.0 && a > 0.0 => (b + a) / 2.0,
        _ => r.get::<f64, _>("mark"),
    }
}

/// Book mid from the latest tick at or before `at`, no older than `max_age_secs`.
pub async fn tick_mid_before(pool: &PgPool, env: &str, symbol: &str, at: DateTime<Utc>, max_age_secs: i64) -> sqlx::Result<Option<f64>> {
    let row = sqlx::query(
        r#"SELECT mark, bid, ask FROM ticks
           WHERE env = $4 AND symbol = $1 AND ts <= $2 AND ts >= $2 - make_interval(secs => $3)
           ORDER BY ts DESC LIMIT 1"#,
    )
    .bind(symbol)
    .bind(at)
    .bind(max_age_secs as f64)
    .bind(env)
    .fetch_optional(pool)
    .await?;
    Ok(row.as_ref().map(tick_mid))
}

/// Book mid from the first tick at or after `at`, within `max_after_secs`.
pub async fn tick_mid_after(pool: &PgPool, env: &str, symbol: &str, at: DateTime<Utc>, max_after_secs: i64) -> sqlx::Result<Option<f64>> {
    let row = sqlx::query(
        r#"SELECT mark, bid, ask FROM ticks
           WHERE env = $4 AND symbol = $1 AND ts >= $2 AND ts <= $2 + make_interval(secs => $3)
           ORDER BY ts ASC LIMIT 1"#,
    )
    .bind(symbol)
    .bind(at)
    .bind(max_after_secs as f64)
    .bind(env)
    .fetch_optional(pool)
    .await?;
    Ok(row.as_ref().map(tick_mid))
}

/// Fill markouts at 1 s / 5 s / 30 s / 60 s from each fill's own symbol's ticks in the
/// strategy's environment. Only fills from the last 30 minutes are attempted; older ones without
/// ticks stay null.
pub async fn backfill_markouts_from_ticks(pool: &PgPool, env: &str, strategy_id: &str, now: DateTime<Utc>) -> sqlx::Result<()> {
    let rows = sqlx::query(
        r#"SELECT f.trade_id, f.symbol, f.side, f.mid_at_fill, f.created_at,
                  t.markout_1s_bps, t.markout_5s_bps, t.markout_30s_bps, t.markout_60s_bps
           FROM fills f
           JOIN tca_fills t ON t.strategy_id = f.strategy_id AND t.trade_id = f.trade_id
           WHERE f.strategy_id = $1
             AND f.created_at >= $2 - interval '30 minutes' AND f.created_at <= $2 - interval '1 second'
             AND (t.markout_1s_bps IS NULL OR t.markout_5s_bps IS NULL
                  OR t.markout_30s_bps IS NULL OR t.markout_60s_bps IS NULL)
           ORDER BY f.created_at DESC LIMIT 300"#,
    )
    .bind(strategy_id)
    .bind(now)
    .fetch_all(pool)
    .await?;
    for r in rows {
        let trade_id: String = r.get("trade_id");
        let symbol: String = r.get("symbol");
        let side: String = r.get("side");
        let mid0: f64 = r.get("mid_at_fill");
        let created: DateTime<Utc> = r.get("created_at");
        let mut vals: [Option<f64>; 4] = [
            r.get("markout_1s_bps"),
            r.get("markout_5s_bps"),
            r.get("markout_30s_bps"),
            r.get("markout_60s_bps"),
        ];
        let mut changed = false;
        for (i, h) in [1i64, 5, 30, 60].into_iter().enumerate() {
            if vals[i].is_some() || now < created + chrono::Duration::seconds(h) {
                continue;
            }
            if let Some(mid) = tick_mid_after(pool, env, &symbol, created + chrono::Duration::seconds(h), 15).await? {
                vals[i] = Some(markout_bps(&side, mid, mid0));
                changed = true;
            }
        }
        if changed {
            sqlx::query(
                r#"UPDATE tca_fills SET markout_1s_bps = $3, markout_5s_bps = $4,
                          markout_30s_bps = $5, markout_60s_bps = $6
                   WHERE strategy_id = $1 AND trade_id = $2"#,
            )
            .bind(strategy_id)
            .bind(&trade_id)
            .bind(vals[0])
            .bind(vals[1])
            .bind(vals[2])
            .bind(vals[3])
            .execute(pool)
            .await?;
        }
    }
    Ok(())
}

/// Latest ticks for a symbol in one environment since `from` (for price overlays), oldest first.
pub async fn list_ticks(pool: &PgPool, env: &str, symbol: &str, from: DateTime<Utc>, limit: i64) -> sqlx::Result<Vec<Value>> {
    let rows = sqlx::query(
        r#"SELECT ts, mark, bid, ask, last, spot FROM ticks
           WHERE env = $4 AND symbol = $1 AND ts >= $2 ORDER BY ts ASC LIMIT $3"#,
    )
    .bind(symbol)
    .bind(from)
    .bind(limit.clamp(1, 5000))
    .bind(env)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "ts": r.get::<DateTime<Utc>, _>("ts"),
                "mark": r.get::<f64, _>("mark"),
                "bid": r.get::<Option<f64>, _>("bid"),
                "ask": r.get::<Option<f64>, _>("ask"),
                "last": r.get::<Option<f64>, _>("last"),
                "spot": r.get::<Option<f64>, _>("spot"),
            })
        })
        .collect())
}

/// First equity snapshot at or after `ts` (day-start equity for day PnL).
pub async fn equity_at_or_after(pool: &PgPool, strategy_id: &str, ts: DateTime<Utc>) -> sqlx::Result<Option<(DateTime<Utc>, f64)>> {
    let row = sqlx::query(
        r#"SELECT ts, equity FROM balances WHERE strategy_id = $1 AND ts >= $2 ORDER BY ts ASC LIMIT 1"#,
    )
    .bind(strategy_id)
    .bind(ts)
    .fetch_optional(pool)
    .await?;
    Ok(row.map(|r| (r.get("ts"), r.get("equity"))))
}

// ---------------------------------------------------------------- performance

/// One fill as the performance aggregator sees it.
#[derive(Debug, Clone)]
pub struct PerfFill {
    pub day: String,
    pub symbol: String,
    pub maker: bool,
    pub notional: f64,
    pub fee: f64,
    pub capture_bps: f64,
    pub markouts: [Option<f64>; 4],
}

#[derive(Default, Debug, Clone)]
struct PerfAgg {
    fills: u64,
    maker_fills: u64,
    volume: f64,
    maker_volume: f64,
    fees: f64,
    maker_fees: f64,
    taker_fees: f64,
    capture_w: f64,
    // Net = capture + markout - fee at each horizon: (notional-weighted sum, weight, count)
    net: [(f64, f64, u64); 5],
    maker_net: [(f64, f64, u64); 5],
}

pub const PERF_HORIZONS: [u32; 5] = [0, 1, 5, 30, 60];

impl PerfAgg {
    fn add(&mut self, f: &PerfFill) {
        self.fills += 1;
        self.volume += f.notional;
        self.fees += f.fee;
        let fee_bps = if f.notional > 0.0 { f.fee / f.notional * 1e4 } else { 0.0 };
        self.capture_w += f.capture_bps * f.notional;
        if f.maker {
            self.maker_fills += 1;
            self.maker_volume += f.notional;
            self.maker_fees += f.fee;
        } else {
            self.taker_fees += f.fee;
        }
        for (i, _) in PERF_HORIZONS.iter().enumerate() {
            let mo = if i == 0 { Some(0.0) } else { f.markouts[i - 1] };
            if let Some(m) = mo {
                let net = f.capture_bps + m - fee_bps;
                let slot = &mut self.net[i];
                slot.0 += net * f.notional;
                slot.1 += f.notional;
                slot.2 += 1;
                if f.maker {
                    let ms = &mut self.maker_net[i];
                    ms.0 += net * f.notional;
                    ms.1 += f.notional;
                    ms.2 += 1;
                }
            }
        }
    }

    fn json(&self) -> Value {
        let curve = |slots: &[(f64, f64, u64); 5]| -> Vec<Value> {
            PERF_HORIZONS
                .iter()
                .zip(slots.iter())
                .map(|(h, (s, w, n))| {
                    serde_json::json!({ "h": h, "net_bps": if *w > 0.0 { Some(s / w) } else { None }, "n": n })
                })
                .collect()
        };
        serde_json::json!({
            "fills": self.fills,
            "maker_fills": self.maker_fills,
            "maker_share": if self.fills > 0 { self.maker_fills as f64 / self.fills as f64 } else { 0.0 },
            "volume": self.volume,
            "maker_volume": self.maker_volume,
            "fees": self.fees,
            "maker_fees": self.maker_fees,
            "taker_fees": self.taker_fees,
            "fee_bps": if self.volume > 0.0 { Some(self.fees / self.volume * 1e4) } else { None },
            "capture_bps": if self.volume > 0.0 { Some(self.capture_w / self.volume) } else { None },
            "net_curve": curve(&self.net),
            "maker_net_curve": curve(&self.maker_net),
        })
    }
}

/// Aggregate fills into totals, per-day and per-symbol stats (pure; unit-tested).
pub fn aggregate_performance(fills: &[PerfFill]) -> (Value, Vec<(String, Value)>, Vec<(String, Value)>) {
    let mut total = PerfAgg::default();
    let mut days: BTreeMap<String, PerfAgg> = BTreeMap::new();
    let mut syms: BTreeMap<String, PerfAgg> = BTreeMap::new();
    for f in fills {
        total.add(f);
        days.entry(f.day.clone()).or_default().add(f);
        syms.entry(f.symbol.clone()).or_default().add(f);
    }
    (
        total.json(),
        days.into_iter().map(|(k, v)| (k, v.json())).collect(),
        syms.into_iter().map(|(k, v)| (k, v.json())).collect(),
    )
}

pub async fn performance(
    pool: &PgPool,
    strategy_id: &str,
    from: DateTime<Utc>,
    to: DateTime<Utc>,
    tz_offset_min: i32,
) -> sqlx::Result<Value> {
    let rows = sqlx::query(
        r#"SELECT to_char(f.created_at + make_interval(mins => $4), 'YYYY-MM-DD') AS day,
                  f.symbol, f.side, f.role, f.price, f.qty, f.fee, f.mid_at_fill,
                  t.markout_1s_bps, t.markout_5s_bps, t.markout_30s_bps, t.markout_60s_bps
           FROM fills f
           LEFT JOIN tca_fills t ON t.strategy_id = f.strategy_id AND t.trade_id = f.trade_id
           WHERE f.strategy_id = $1 AND f.created_at >= $2 AND f.created_at <= $3
           ORDER BY f.created_at ASC"#,
    )
    .bind(strategy_id)
    .bind(from)
    .bind(to)
    .bind(tz_offset_min)
    .fetch_all(pool)
    .await?;
    let fills: Vec<PerfFill> = rows
        .iter()
        .map(|r| {
            let side: String = r.get("side");
            let price: f64 = r.get("price");
            let qty: f64 = r.get("qty");
            PerfFill {
                day: r.get("day"),
                symbol: r.get("symbol"),
                maker: r.get::<Option<String>, _>("role").as_deref() != Some("taker"),
                notional: price * qty,
                fee: r.get("fee"),
                capture_bps: capture_bps(&side, price, r.get("mid_at_fill")).unwrap_or(0.0),
                markouts: [
                    r.get("markout_1s_bps"),
                    r.get("markout_5s_bps"),
                    r.get("markout_30s_bps"),
                    r.get("markout_60s_bps"),
                ],
            }
        })
        .collect();
    let (totals, by_day, by_symbol) = aggregate_performance(&fills);

    let eq_rows = sqlx::query(
        r#"SELECT day,
                  (array_agg(equity ORDER BY ts ASC))[1] AS first,
                  (array_agg(equity ORDER BY ts DESC))[1] AS last
           FROM (SELECT to_char(ts + make_interval(mins => $4), 'YYYY-MM-DD') AS day, ts, equity
                 FROM balances WHERE strategy_id = $1 AND ts >= $2 AND ts <= $3) b
           GROUP BY day ORDER BY day"#,
    )
    .bind(strategy_id)
    .bind(from)
    .bind(to)
    .bind(tz_offset_min)
    .fetch_all(pool)
    .await?;
    let mut equity: BTreeMap<String, (f64, f64)> = BTreeMap::new();
    for r in eq_rows {
        equity.insert(r.get("day"), (r.get("first"), r.get("last")));
    }
    let mut day_keys: std::collections::BTreeSet<String> = equity.keys().cloned().collect();
    day_keys.extend(by_day.iter().map(|(d, _)| d.clone()));
    let by_day_map: BTreeMap<String, Value> = by_day.into_iter().collect();
    let daily: Vec<Value> = day_keys
        .into_iter()
        .map(|d| {
            let (first, last) = equity.get(&d).copied().map(|(a, b)| (Some(a), Some(b))).unwrap_or((None, None));
            let mut v = by_day_map.get(&d).cloned().unwrap_or_else(|| PerfAgg::default().json());
            v["day"] = serde_json::json!(d);
            v["equity_start"] = serde_json::json!(first);
            v["equity_end"] = serde_json::json!(last);
            v["equity_change"] = serde_json::json!(match (first, last) {
                (Some(a), Some(b)) => Some(b - a),
                _ => None,
            });
            v
        })
        .collect();
    let (eq_first, eq_last) = (
        equity.values().next().map(|(a, _)| *a),
        equity.values().last().map(|(_, b)| *b),
    );
    Ok(serde_json::json!({
        "from": from,
        "to": to,
        "tz_offset_min": tz_offset_min,
        "totals": totals,
        "equity_change": match (eq_first, eq_last) { (Some(a), Some(b)) => Some(b - a), _ => None },
        "daily": daily,
        "by_symbol": by_symbol.into_iter().map(|(s, mut v)| { v["symbol"] = serde_json::json!(s); v }).collect::<Vec<_>>(),
    }))
}

#[cfg(test)]
mod perf_tests {
    use super::*;

    fn fill(day: &str, maker: bool, notional: f64, fee: f64, capture: f64, m60: Option<f64>) -> PerfFill {
        PerfFill {
            day: day.into(),
            symbol: "ETHUSDT".into(),
            maker,
            notional,
            fee,
            capture_bps: capture,
            markouts: [None, None, None, m60],
        }
    }

    #[test]
    fn capture_sign_matches_side() {
        assert!((capture_bps("buy", 99.0, 100.0).unwrap() - 100.0).abs() < 1e-9);
        assert!((capture_bps("sell", 101.0, 100.0).unwrap() - 100.0).abs() < 1e-9);
        assert!(capture_bps("sell", 99.0, 100.0).unwrap() < 0.0);
        assert!(capture_bps("buy", 99.0, 0.0).is_none());
    }

    #[test]
    fn net_curve_is_capture_plus_markout_minus_fee() {
        // $100 notional, fee $0.0212 = 2.12 bps, capture 3 bps, 60 s markout -1 bp → net -0.12 bps.
        let fills = vec![fill("2026-09-29", true, 100.0, 0.0212, 3.0, Some(-1.0))];
        let (tot, days, syms) = aggregate_performance(&fills);
        let at_fill = tot["net_curve"][0]["net_bps"].as_f64().unwrap();
        let at_60 = tot["net_curve"][4]["net_bps"].as_f64().unwrap();
        assert!((at_fill - 0.88).abs() < 1e-9, "{at_fill}");
        assert!((at_60 + 0.12).abs() < 1e-9, "{at_60}");
        assert_eq!(tot["net_curve"][1]["n"], 0);
        assert_eq!(days.len(), 1);
        assert_eq!(syms[0].0, "ETHUSDT");
    }

    #[test]
    fn maker_share_and_fee_split() {
        let fills = vec![
            fill("2026-09-28", true, 100.0, 0.02, 1.0, None),
            fill("2026-09-29", false, 100.0, 0.05, -0.5, None),
        ];
        let (tot, days, _) = aggregate_performance(&fills);
        assert_eq!(tot["fills"], 2);
        assert!((tot["maker_share"].as_f64().unwrap() - 0.5).abs() < 1e-12);
        assert!((tot["taker_fees"].as_f64().unwrap() - 0.05).abs() < 1e-12);
        assert_eq!(days.len(), 2);
    }
}
