//! SQLx runtime helpers (no compile-time query! macros).

use chrono::{DateTime, Timelike, Utc};
use serde_json::Value;
use sqlx::postgres::PgPoolOptions;
use sqlx::{PgPool, Row};
use std::collections::BTreeMap;

use crate::analytics::{avg_nullable_bps, AnalyticsBucket};
use crate::tca::{compute_tca, markout_bps, net_5s_bps};

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
        "SELECT id, name, desired_state, last_pid FROM strategies ORDER BY id",
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
            })
        })
        .collect())
}

pub async fn get_strategy(pool: &PgPool, id: &str) -> sqlx::Result<Option<Value>> {
    let row = sqlx::query(
        "SELECT id, name, desired_state, last_pid FROM strategies WHERE id = $1",
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
    bot_qty: f64,
    entry: f64,
    mark: f64,
    unrealized: f64,
    realized: f64,
    mismatch: bool,
) -> sqlx::Result<()> {
    sqlx::query(
        r#"INSERT INTO positions
            (strategy_id, symbol, ts, venue_qty, bot_qty, entry, mark, unrealized, realized, mismatch)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)"#,
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
    .execute(pool)
    .await?;
    Ok(())
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

/// Backfill TCA markouts using a fresh mark as mid_after.
pub async fn backfill_markouts(
    pool: &PgPool,
    strategy_id: &str,
    mid_after: f64,
    now: DateTime<Utc>,
) -> sqlx::Result<()> {
    let rows = sqlx::query(
        r#"SELECT f.trade_id, f.side, f.arrival_mid, f.created_at,
                  t.effective_spread_bps, t.fee_bps,
                  t.markout_1s_bps, t.markout_5s_bps, t.markout_30s_bps
           FROM fills f
           JOIN tca_fills t ON t.strategy_id = f.strategy_id AND t.trade_id = f.trade_id
           WHERE f.strategy_id = $1
             AND (t.markout_1s_bps IS NULL OR t.markout_5s_bps IS NULL OR t.markout_30s_bps IS NULL)"#,
    )
    .bind(strategy_id)
    .fetch_all(pool)
    .await?;

    for r in rows {
        let trade_id: String = r.get("trade_id");
        let side: String = r.get("side");
        let arrival_mid: f64 = r.get("arrival_mid");
        let created: DateTime<Utc> = r.get("created_at");
        let age = (now - created).num_seconds();
        let mut m1: Option<f64> = r.get("markout_1s_bps");
        let mut m5: Option<f64> = r.get("markout_5s_bps");
        let mut m30: Option<f64> = r.get("markout_30s_bps");
        let eff: f64 = r.get("effective_spread_bps");
        let fee_bps: f64 = r.get("fee_bps");
        let mo = markout_bps(&side, mid_after, arrival_mid);
        if m1.is_none() && age >= 1 {
            m1 = Some(mo);
        }
        if m5.is_none() && age >= 5 {
            m5 = Some(mo);
        }
        if m30.is_none() && age >= 30 {
            m30 = Some(mo);
        }
        let net = net_5s_bps(eff, fee_bps, m5);
        sqlx::query(
            r#"UPDATE tca_fills SET
                 markout_1s_bps = $3,
                 markout_5s_bps = $4,
                 markout_30s_bps = $5,
                 net_5s_bps = $6
               WHERE strategy_id = $1 AND trade_id = $2"#,
        )
        .bind(strategy_id)
        .bind(&trade_id)
        .bind(m1)
        .bind(m5)
        .bind(m30)
        .bind(net)
        .execute(pool)
        .await?;
    }
    Ok(())
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
    let positions = sqlx::query(
        r#"SELECT DISTINCT ON (symbol)
              symbol, ts, venue_qty, bot_qty, entry, mark, unrealized, realized, mismatch
           FROM positions WHERE strategy_id = $1
           ORDER BY symbol, ts DESC"#,
    )
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
        "positions": positions.into_iter().map(|r| serde_json::json!({
            "symbol": r.get::<String, _>("symbol"),
            "ts": r.get::<DateTime<Utc>, _>("ts"),
            "venue_qty": r.get::<f64, _>("venue_qty"),
            "bot_qty": r.get::<f64, _>("bot_qty"),
            "entry": r.get::<f64, _>("entry"),
            "mark": r.get::<f64, _>("mark"),
            "unrealized": r.get::<f64, _>("unrealized"),
            "realized": r.get::<f64, _>("realized"),
            "mismatch": r.get::<bool, _>("mismatch"),
        })).collect::<Vec<_>>(),
    }))
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
    let rows = sqlx::query(
        r#"SELECT symbol, ts, venue_qty, bot_qty, entry, mark, unrealized, realized, mismatch
           FROM positions WHERE strategy_id = $1 ORDER BY ts DESC LIMIT $2"#,
    )
    .bind(strategy_id)
    .bind(lim)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "symbol": r.get::<String, _>("symbol"),
                "ts": r.get::<DateTime<Utc>, _>("ts"),
                "venue_qty": r.get::<f64, _>("venue_qty"),
                "bot_qty": r.get::<f64, _>("bot_qty"),
                "entry": r.get::<f64, _>("entry"),
                "mark": r.get::<f64, _>("mark"),
                "unrealized": r.get::<f64, _>("unrealized"),
                "realized": r.get::<f64, _>("realized"),
                "mismatch": r.get::<bool, _>("mismatch"),
            })
        })
        .collect())
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
        r#"SELECT trade_id, client_order_id, symbol, side, price, qty, fee,
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
            serde_json::json!({
                "trade_id": r.get::<String, _>("trade_id"),
                "client_order_id": r.get::<Option<String>, _>("client_order_id"),
                "symbol": r.get::<String, _>("symbol"),
                "side": r.get::<String, _>("side"),
                "price": r.get::<f64, _>("price"),
                "qty": r.get::<f64, _>("qty"),
                "fee": r.get::<f64, _>("fee"),
                "limit_price": r.get::<f64, _>("limit_price"),
                "arrival_mid": r.get::<f64, _>("arrival_mid"),
                "mid_at_fill": r.get::<f64, _>("mid_at_fill"),
                "created_at": r.get::<DateTime<Utc>, _>("created_at"),
            })
        })
        .collect())
}

pub async fn list_tca(
    pool: &PgPool,
    strategy_id: &str,
    limit: Option<i64>,
) -> sqlx::Result<Vec<Value>> {
    let lim = clamp_limit(limit);
    let rows = sqlx::query(
        r#"SELECT trade_id, slippage_bps, quoted_half_spread_bps, effective_spread_bps,
                  fee_quote, fee_bps, markout_1s_bps, markout_5s_bps, markout_30s_bps, net_5s_bps
           FROM tca_fills WHERE strategy_id = $1
           ORDER BY trade_id DESC LIMIT $2"#,
    )
    .bind(strategy_id)
    .bind(lim)
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|r| {
            serde_json::json!({
                "trade_id": r.get::<String, _>("trade_id"),
                "slippage_bps": r.get::<f64, _>("slippage_bps"),
                "quoted_half_spread_bps": r.get::<f64, _>("quoted_half_spread_bps"),
                "effective_spread_bps": r.get::<f64, _>("effective_spread_bps"),
                "fee_quote": r.get::<f64, _>("fee_quote"),
                "fee_bps": r.get::<f64, _>("fee_bps"),
                "markout_1s_bps": r.get::<Option<f64>, _>("markout_1s_bps"),
                "markout_5s_bps": r.get::<Option<f64>, _>("markout_5s_bps"),
                "markout_30s_bps": r.get::<Option<f64>, _>("markout_30s_bps"),
                "net_5s_bps": r.get::<Option<f64>, _>("net_5s_bps"),
            })
        })
        .collect())
}

pub async fn reconcile(pool: &PgPool, strategy_id: &str, limit: Option<i64>) -> sqlx::Result<Value> {
    let lim = clamp_limit(limit);
    let mismatches = sqlx::query(
        r#"SELECT symbol, ts, venue_qty, bot_qty, entry, mark, unrealized, realized, mismatch
           FROM positions WHERE strategy_id = $1 AND mismatch = TRUE
           ORDER BY ts DESC LIMIT $2"#,
    )
    .bind(strategy_id)
    .bind(lim)
    .fetch_all(pool)
    .await?;
    let latest = sqlx::query(
        r#"SELECT DISTINCT ON (symbol)
              symbol, ts, venue_qty, bot_qty, entry, mark, unrealized, realized, mismatch
           FROM positions WHERE strategy_id = $1
           ORDER BY symbol, ts DESC"#,
    )
    .bind(strategy_id)
    .fetch_all(pool)
    .await?;
    let map_row = |r: sqlx::postgres::PgRow| {
        serde_json::json!({
            "symbol": r.get::<String, _>("symbol"),
            "ts": r.get::<DateTime<Utc>, _>("ts"),
            "venue_qty": r.get::<f64, _>("venue_qty"),
            "bot_qty": r.get::<f64, _>("bot_qty"),
            "entry": r.get::<f64, _>("entry"),
            "mark": r.get::<f64, _>("mark"),
            "unrealized": r.get::<f64, _>("unrealized"),
            "realized": r.get::<f64, _>("realized"),
            "mismatch": r.get::<bool, _>("mismatch"),
        })
    };
    Ok(serde_json::json!({
        "mismatches": mismatches.into_iter().map(map_row).collect::<Vec<_>>(),
        "latest_by_symbol": latest.into_iter().map(map_row).collect::<Vec<_>>(),
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
