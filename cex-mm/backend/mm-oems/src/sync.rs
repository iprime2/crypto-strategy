//! Venue sync: the exchange is the source of truth for orders and fills.
//!
//! - Open orders every 3 s (kept in memory for the blotter and the book overlay).
//! - Fills every 5 s from `/v2/fills`, backfilling the full history on first run,
//!   stored with role, fee and a TCA row priced against the mid at fill time.
//! - Ticker per active symbol every 2 s into `ticks`, which markouts are measured on.

use std::collections::{BTreeSet, HashMap};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::{Duration, Instant};

use chrono::{DateTime, Utc};
use serde::Serialize;
use tokio::sync::RwLock;

use crate::db::{self, Db};
use crate::delta::{parse_fill, parse_open_orders, DeltaClient, VenueOrder};
use crate::market::Market;
use crate::supervisor::{effective_env, load_env_file};

#[derive(Default, Serialize, Clone)]
pub struct StreamHealth {
    pub last_ok: Option<DateTime<Utc>>,
    pub last_error: Option<String>,
    pub last_error_at: Option<DateTime<Utc>>,
    pub rtt_ms: Option<u64>,
}

#[derive(Default)]
pub struct VenueState {
    pub open_orders: Vec<VenueOrder>,
    pub orders_at: Option<DateTime<Utc>>,
    pub health: HashMap<&'static str, StreamHealth>,
    pub fills_backfilled: bool,
    pub fills_ingested: u64,
    pub active_symbols: Vec<String>,
}

pub type SharedVenue = Arc<RwLock<VenueState>>;

pub fn new_venue_state() -> SharedVenue {
    Arc::new(RwLock::new(VenueState::default()))
}

impl VenueState {
    fn ok(&mut self, stream: &'static str, started: Instant) {
        let h = self.health.entry(stream).or_default();
        h.last_ok = Some(Utc::now());
        h.rtt_ms = Some(started.elapsed().as_millis() as u64);
    }

    fn err(&mut self, stream: &'static str, e: impl std::fmt::Display) {
        let h = self.health.entry(stream).or_default();
        h.last_error = Some(describe_error(&e.to_string()));
        h.last_error_at = Some(Utc::now());
    }
}

/// Short operator-facing message. Never includes request details (signatures, keys).
fn describe_error(raw: &str) -> String {
    let lower = raw.to_lowercase();
    if lower.contains("timed out") || lower.contains("timeout") || lower.contains("error sending request") {
        "venue did not answer within 9 s (slow network or venue)".into()
    } else if lower.contains("expired_signature") {
        "venue rejected the request as expired (request took too long or clock skew)".into()
    } else {
        raw.chars().take(160).collect()
    }
}

/// Symbols worth tracking: configured ones plus anything with an open order.
async fn active_symbols(db: &Db, env_path: &PathBuf, strategy_id: &str, venue: &SharedVenue) -> Vec<String> {
    let body = db::latest_config(&db.pool, strategy_id)
        .await
        .ok()
        .flatten()
        .and_then(|c| c.get("body").cloned());
    let eff = effective_env(&load_env_file(env_path), body.as_ref());
    let mut set: BTreeSet<String> = eff
        .get("MM_SYMBOLS")
        .map(|(v, _)| v.split(',').map(|s| s.trim().to_uppercase()).filter(|s| !s.is_empty()).collect())
        .unwrap_or_default();
    for o in &venue.read().await.open_orders {
        set.insert(o.symbol.clone());
    }
    if let Ok(open) = db::open_position_symbols(&db.pool, strategy_id).await {
        set.extend(open);
    }
    set.into_iter().collect()
}

fn client(env_path: &PathBuf) -> Option<DeltaClient> {
    DeltaClient::from_env_pairs(&load_env_file(env_path))
}

fn api_error(v: &serde_json::Value) -> Option<String> {
    if v.get("success").and_then(|s| s.as_bool()) == Some(false) || v.get("error").is_some() {
        let code = v
            .get("error")
            .and_then(|e| e.get("code").or(Some(e)))
            .map(|c| c.to_string())
            .unwrap_or_else(|| "unknown".into());
        return Some(format!("venue error {code}"));
    }
    None
}

async fn sync_orders(env_path: &PathBuf, venue: &SharedVenue) {
    let Some(c) = client(env_path) else { return };
    let started = Instant::now();
    match c.open_orders().await {
        Ok(v) => {
            if let Some(e) = api_error(&v) {
                venue.write().await.err("orders", e);
                return;
            }
            let orders = parse_open_orders(&v);
            let mut g = venue.write().await;
            g.open_orders = orders;
            g.orders_at = Some(Utc::now());
            g.ok("orders", started);
        }
        Err(e) => venue.write().await.err("orders", e),
    }
}

/// Mid to price a fill against: nearest tick at or before the fill, else the mark
/// Delta stamped on the fill, else the fill price.
async fn mid_for_fill(db: &Db, symbol: &str, at: DateTime<Utc>, mark: f64, price: f64) -> f64 {
    if let Ok(Some(mid)) = db::tick_mid_before(&db.pool, symbol, at, 10).await {
        return mid;
    }
    if mark > 0.0 {
        mark
    } else {
        price
    }
}

async fn sync_fills(db: &Db, env_path: &PathBuf, strategy_id: &str, venue: &SharedVenue) {
    let Some(c) = client(env_path) else { return };
    let backfill = !venue.read().await.fills_backfilled;
    let max_pages = if backfill { 200 } else { 5 };
    let mut after: Option<String> = None;
    let mut inserted_total = 0u64;
    let started = Instant::now();
    for _ in 0..max_pages {
        let page = match c.fills_page(100, after.as_deref()).await {
            Ok(v) => v,
            Err(e) => {
                venue.write().await.err("fills", e);
                return;
            }
        };
        if let Some(e) = api_error(&page) {
            venue.write().await.err("fills", e);
            return;
        }
        let rows = page.get("result").and_then(|r| r.as_array()).cloned().unwrap_or_default();
        let mut inserted_page = 0;
        for row in &rows {
            let Some(f) = parse_fill(row) else { continue };
            let mid = mid_for_fill(db, &f.symbol, f.created_at, f.mark, f.price).await;
            match db::insert_venue_fill(&db.pool, strategy_id, &f, mid).await {
                Ok(true) => inserted_page += 1,
                Ok(false) => {}
                Err(e) => {
                    venue.write().await.err("fills", e);
                    return;
                }
            }
        }
        inserted_total += inserted_page;
        after = page
            .get("meta")
            .and_then(|m| m.get("after"))
            .and_then(|a| a.as_str())
            .map(|s| s.to_string());
        // Incremental mode stops at the first page with nothing new.
        if after.is_none() || rows.is_empty() || (!backfill && inserted_page == 0) {
            break;
        }
    }
    let mut g = venue.write().await;
    g.fills_ingested += inserted_total;
    g.fills_backfilled = true;
    g.ok("fills", started);
}

async fn sync_ticks(db: &Db, market: &Market, symbols: &[String], venue: &SharedVenue) {
    let started = Instant::now();
    let mut any_ok = false;
    for sym in symbols {
        match market.ticker(sym).await {
            Ok(t) => {
                let mark = t.get("mark").and_then(|v| v.as_f64()).unwrap_or(0.0);
                if mark <= 0.0 {
                    continue;
                }
                let f = |k: &str| t.get(k).and_then(|v| v.as_f64()).filter(|x| *x > 0.0);
                if let Err(e) = db::insert_tick(
                    &db.pool,
                    sym,
                    Utc::now(),
                    mark,
                    f("best_bid"),
                    f("best_ask"),
                    f("last"),
                    f("spot"),
                )
                .await
                {
                    venue.write().await.err("ticker", e);
                    return;
                }
                any_ok = true;
            }
            Err(e) => venue.write().await.err("ticker", e),
        }
    }
    if any_ok {
        venue.write().await.ok("ticker", started);
    }
}

pub async fn run_sync_loop(
    db: Option<Db>,
    env_path: PathBuf,
    strategy_id: String,
    market: Market,
    venue: SharedVenue,
) {
    let Some(db) = db else {
        tracing::warn!("venue sync idle: no database");
        return;
    };
    let mut tick = tokio::time::interval(Duration::from_secs(1));
    tick.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);
    let mut n: u64 = 0;
    loop {
        tick.tick().await;
        if n % 10 == 0 {
            let syms = active_symbols(&db, &env_path, &strategy_id, &venue).await;
            venue.write().await.active_symbols = syms;
        }
        if n % 2 == 0 {
            let syms = venue.read().await.active_symbols.clone();
            sync_ticks(&db, &market, &syms, &venue).await;
        }
        if n % 3 == 0 {
            sync_orders(&env_path, &venue).await;
        }
        if n % 5 == 0 {
            sync_fills(&db, &env_path, &strategy_id, &venue).await;
            if let Err(e) = db::backfill_markouts_from_ticks(&db.pool, &strategy_id, Utc::now()).await {
                tracing::warn!(error = %e, "markout backfill failed");
            }
        }
        n = n.wrapping_add(1);
    }
}
