//! Account-wide guards for a live Delta run. They set one shared halt flag that every symbol loop
//! obeys (cancel all, stop quoting, exit):
//! - daily loss stop on venue equity (`MM_DAILY_LOSS_LIMIT_USD`), persisted per UTC day;
//! - unexpected taker fills (quotes are post-only; only the bot's own reduce-only exit may take);
//! - Delta's dead man's switch (`MM_DMS_TTL_MS`, armed before quoting): Delta cancels our orders
//!   if the process or the network stops sending heartbeats.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicI64, Ordering};
use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use chrono::Utc;
use mm_delta::DeltaRest;

use crate::risk::{taker_fill_unexpected, DailyLossGuard, DailyLossState};

/// Taker fills within this long of our own reduce-only order are expected.
const REDUCE_ONLY_GRACE_MS: i64 = 60_000;

#[derive(Debug, Default)]
pub struct AccountFlags {
    pub halt: AtomicBool,
    pub daily_pnl_cents: AtomicI64,
    /// Unix ms of the last reduce-only order the bot sent; 0 = none.
    pub last_reduce_only_ms: AtomicI64,
}

impl AccountFlags {
    pub fn halted(&self) -> bool {
        self.halt.load(Ordering::Relaxed)
    }

    pub fn daily_pnl_usd(&self) -> f64 {
        self.daily_pnl_cents.load(Ordering::Relaxed) as f64 / 100.0
    }

    pub fn note_reduce_only(&self) {
        self.last_reduce_only_ms
            .store(Utc::now().timestamp_millis(), Ordering::Relaxed);
    }

    fn last_reduce_only(&self) -> Option<i64> {
        Some(self.last_reduce_only_ms.load(Ordering::Relaxed)).filter(|t| *t > 0)
    }

    fn trip(&self, reason: &str) {
        if !self.halt.swap(true, Ordering::Relaxed) {
            tracing::error!(reason, "account halt — cancel all and stop quoting");
        }
    }
}

#[derive(Debug, Clone)]
pub struct AccountConfig {
    pub daily_loss_limit_usd: f64,
    pub poll: Duration,
    /// 0 disables the dead man's switch.
    pub dms_ttl_ms: u64,
}

pub fn daily_loss_path(env_label: &str) -> PathBuf {
    PathBuf::from(format!("artifacts/risk/daily_loss_{env_label}.json"))
}

pub fn load_daily_loss(path: &Path) -> Option<DailyLossState> {
    serde_json::from_str(&std::fs::read_to_string(path).ok()?).ok()
}

fn save_daily_loss(path: &Path, state: &DailyLossState) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(path, serde_json::to_string_pretty(state)?)?;
    Ok(())
}

pub fn spawn_monitor(
    rest: DeltaRest,
    symbols: Vec<String>,
    cfg: AccountConfig,
    flags: Arc<AccountFlags>,
    mut guard: DailyLossGuard,
    state_path: PathBuf,
) {
    tokio::spawn(async move {
        // Fills already on the account at start are history, not something this run did.
        let mut seen: HashMap<String, u64> = HashMap::new();
        let mut interval = tokio::time::interval(cfg.poll);
        loop {
            interval.tick().await;

            match rest.get_net_equity_usd().await {
                Ok(equity) => {
                    let pnl = guard.observe(equity, Utc::now().date_naive());
                    flags
                        .daily_pnl_cents
                        .store((pnl * 100.0).round() as i64, Ordering::Relaxed);
                    if let Some(state) = guard.state() {
                        if let Err(e) = save_daily_loss(&state_path, &state) {
                            tracing::warn!(error = %e, "daily loss state not saved");
                        }
                    }
                    if guard.breached() {
                        tracing::error!(
                            pnl_usd = pnl,
                            limit_usd = cfg.daily_loss_limit_usd,
                            "daily loss limit hit"
                        );
                        flags.trip("daily loss limit");
                    }
                }
                Err(e) => tracing::warn!(error = %e, "equity read failed; daily loss stop not updated"),
            }

            for symbol in &symbols {
                let fills = match rest.recent_fill_roles(symbol, 20).await {
                    Ok(f) => f,
                    Err(e) => {
                        tracing::warn!(%symbol, error = %e, "fills read failed; taker guard not updated");
                        continue;
                    }
                };
                let newest = fills.iter().map(|f| f.id).max().unwrap_or(0);
                let Some(&last_seen) = seen.get(symbol) else {
                    seen.insert(symbol.clone(), newest);
                    continue;
                };
                for f in fills.iter().filter(|f| f.id > last_seen) {
                    if taker_fill_unexpected(f.taker, f.created_ms, flags.last_reduce_only(), REDUCE_ONLY_GRACE_MS) {
                        tracing::error!(%symbol, fill_id = f.id, "unexpected taker fill on a post-only quote");
                        flags.trip("unexpected taker fill");
                    }
                }
                seen.insert(symbol.clone(), newest.max(last_seen));
            }
        }
    });
}

/// Arms Delta's dead man's switch before any quote: one heartbeat per symbol set (a stable id, so a
/// restart re-creates the same heartbeat, which Delta accepts), first ack, then acks every TTL/3.
/// Verified on demo (`mm-delta/examples/dism_safety_smoke.rs`): a missed heartbeat cancels resting
/// orders on these products.
pub async fn arm_dead_mans_switch(rest: &DeltaRest, symbols: &[String], ttl_ms: u64) -> Result<String> {
    let delta_symbols: Vec<String> = symbols
        .iter()
        .map(|s| mm_delta::delta_product_symbol(s))
        .collect();
    let id = format!("mm-bot-{}", delta_symbols.join("-").to_ascii_lowercase());
    rest.heartbeat_create(&id, &delta_symbols).await?;
    rest.heartbeat_ack(&id, ttl_ms).await?;
    tracing::info!(heartbeat_id = %id, ttl_ms, "dead man's switch armed");
    let rest = rest.clone();
    let hb = id.clone();
    tokio::spawn(async move { keep_heartbeat(rest, hb, ttl_ms).await });
    Ok(id)
}

/// Clean exit: orders are already cancelled, so turn the heartbeat off (`ttl = 0`).
pub async fn disarm_dead_mans_switch(rest: &DeltaRest, id: &str) {
    match rest.heartbeat_ack(id, 0).await {
        Ok(()) => tracing::info!(heartbeat_id = %id, "dead man's switch disarmed"),
        Err(e) => tracing::warn!(heartbeat_id = %id, error = %e, "heartbeat disable failed; it expires on its own"),
    }
}

async fn keep_heartbeat(rest: DeltaRest, id: String, ttl_ms: u64) {
    let mut interval = tokio::time::interval(Duration::from_millis((ttl_ms / 3).max(1_000)));
    interval.tick().await; // the first ack was sent while arming
    let mut failing = false;
    loop {
        interval.tick().await;
        match rest.heartbeat_ack(&id, ttl_ms).await {
            Ok(()) if failing => {
                failing = false;
                tracing::info!(heartbeat_id = %id, "heartbeat ack ok again");
            }
            Ok(()) => {}
            Err(e) => {
                if !failing {
                    tracing::warn!(heartbeat_id = %id, error = %e, "heartbeat ack failed; Delta cancels our orders if this lasts past the TTL");
                }
                failing = true;
            }
        }
    }
}
