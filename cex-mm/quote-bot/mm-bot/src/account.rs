//! Account-wide guards for a live Delta run. They set one shared halt flag that every symbol loop
//! obeys (cancel all, stop quoting, exit):
//! - daily loss stop on venue equity (`MM_DAILY_LOSS_LIMIT_USD`), persisted per IST day (from 18:30 UTC);
//! - unexpected taker fills (quotes are post-only; only the bot's own reduce-only exit may take);
//! - Delta's dead man's switch (`MM_DMS_TTL_MS`, armed before quoting): Delta cancels our orders
//!   if the process or the network stops sending heartbeats.
//!
//! Before any of that, a mainnet start is refused when Delta's order leverage on a quoted product
//! is above `MM_MAX_LEVERAGE`.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicI64, Ordering};
use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use chrono::Utc;
use mm_delta::{DeltaEnvironment, DeltaRest};

use crate::risk::{loss_day, taker_fill_unexpected, DailyLossGuard, DailyLossState};

/// Taker fills within this long of our own reduce-only order are expected.
const REDUCE_ONLY_GRACE_MS: i64 = 60_000;

/// Bound on the monitor's equity and fills reads. They are off the quote path, so a slow answer only delays
/// the next check; with the quote loop's 3 s bound a slow fills query skipped the taker guard 6 times in ten
/// minutes on 21 Oct 2026 (the same query normally answers in about 45 ms).
const MONITOR_REQUEST_TIMEOUT: Duration = Duration::from_secs(10);

/// `MM_MAX_LEVERAGE` default. Delta's own default order leverage is 100x.
pub const DEFAULT_MAX_LEVERAGE: f64 = 5.0;

/// A zero, negative or non-finite `MM_MAX_LEVERAGE` would block every start or disable the guard;
/// it falls back to the default instead.
pub fn max_leverage_or_default(v: f64) -> f64 {
    if v.is_finite() && v > 0.0 {
        v
    } else {
        DEFAULT_MAX_LEVERAGE
    }
}

/// One error naming every symbol whose order leverage is above `max` (equal passes; NaN fails),
/// with the fix, and every symbol whose read failed (fails closed).
pub fn check_leverage(readings: &[(String, Result<f64>)], max: f64) -> Result<()> {
    let (mut over, mut failed) = (Vec::new(), Vec::new());
    for (symbol, reading) in readings {
        match reading {
            Ok(leverage) if leverage.is_nan() || *leverage > max => {
                over.push(format!("{symbol} {leverage}x"))
            }
            Ok(_) => {}
            Err(e) => failed.push(format!("{symbol} ({e:#})")),
        }
    }
    let mut problems = Vec::new();
    if !over.is_empty() {
        problems.push(format!(
            "order leverage above MM_MAX_LEVERAGE={max}x: {}. Set the order leverage on Delta for \
             each of these products to {max}x or less, then restart.",
            over.join(", ")
        ));
    }
    if !failed.is_empty() {
        problems.push(format!("order leverage read failed: {}.", failed.join("; ")));
    }
    if !problems.is_empty() {
        anyhow::bail!("{}", problems.join(" "));
    }
    Ok(())
}

/// Reads Delta's order leverage for every quoted symbol (each reading logged at info; a failed read
/// does not stop the others) and checks them all against `max`.
pub async fn verify_order_leverage(rest: &DeltaRest, symbols: &[String], max: f64) -> Result<()> {
    let mut readings = Vec::with_capacity(symbols.len());
    for symbol in symbols {
        let reading = rest.get_order_leverage(symbol).await;
        if let Ok(leverage) = &reading {
            tracing::info!(%symbol, leverage = *leverage, max_leverage = max, "order leverage");
        }
        readings.push((symbol.clone(), reading));
    }
    check_leverage(&readings, max)
}

/// A leverage-guard error refuses a mainnet start; on demo it is only a warning (the demo bot
/// restarts via the OEMS and demo leverage defaults to 100x).
pub fn apply_leverage_guard(env: DeltaEnvironment, res: Result<()>) -> Result<()> {
    match (env, res) {
        (_, Ok(())) => Ok(()),
        (DeltaEnvironment::IndiaMainnet, Err(e)) => {
            Err(e.context("leverage guard: mainnet start refused"))
        }
        (DeltaEnvironment::DemoIndia, Err(e)) => {
            tracing::warn!("leverage guard (demo, not blocking; demo defaults to 100x): {e:#}");
            Ok(())
        }
    }
}

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
    let rest = rest.with_request_timeout(MONITOR_REQUEST_TIMEOUT);
    tokio::spawn(async move {
        // Fills already on the account at start are history, not something this run did.
        let mut seen: HashMap<String, u64> = HashMap::new();
        let mut interval = tokio::time::interval(cfg.poll);
        loop {
            interval.tick().await;

            match rest.get_net_equity_usd().await {
                Ok(equity) => {
                    let pnl = guard.observe(equity, loss_day(Utc::now()));
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
                Err(e) => tracing::warn!(error = %format!("{e:#}"), "equity read failed; daily loss stop not updated"),
            }

            for symbol in &symbols {
                let fills = match rest.recent_fill_roles(symbol, 20).await {
                    Ok(f) => f,
                    Err(e) => {
                        tracing::warn!(%symbol, error = %format!("{e:#}"), "fills read failed; taker guard not updated");
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
    rest.heartbeat_create(&id, &delta_symbols, ttl_ms).await?;
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

#[cfg(test)]
mod tests {
    use super::*;

    fn readings(rows: &[(&str, f64)]) -> Vec<(String, Result<f64>)> {
        rows.iter().map(|(s, l)| (s.to_string(), Ok(*l))).collect()
    }

    #[test]
    fn leverage_at_or_below_the_cap_passes() {
        assert!(check_leverage(&readings(&[("ADAUSDT", 5.0), ("ETHUSDT", 2.0)]), 5.0).is_ok());
        assert!(check_leverage(&[], 5.0).is_ok());
    }

    #[test]
    fn failed_reads_and_over_cap_symbols_are_reported_together() {
        let mut rows = readings(&[("ETHUSDT", 2.0), ("SOLUSDT", 100.0)]);
        rows.insert(0, ("ADAUSDT".to_string(), Err(anyhow::anyhow!("HTTP 502"))));
        rows.push(("XRPUSDT".to_string(), Err(anyhow::anyhow!("bad envelope"))));
        let err = check_leverage(&rows, 5.0).unwrap_err().to_string();
        assert!(err.contains("SOLUSDT 100x"), "{err}");
        assert!(err.contains("ADAUSDT (HTTP 502)"), "{err}");
        assert!(err.contains("XRPUSDT (bad envelope)"), "{err}");
        assert!(err.contains("read failed"), "{err}");
        assert!(!err.contains("ETHUSDT"), "{err}");
        // A failed read alone still fails closed.
        let only_failed = vec![("ADAUSDT".to_string(), Err(anyhow::anyhow!("timeout")))];
        assert!(check_leverage(&only_failed, 5.0).is_err());
    }

    #[test]
    fn leverage_guard_error_blocks_mainnet_and_only_warns_on_demo() {
        use mm_delta::DeltaEnvironment::{DemoIndia, IndiaMainnet};
        let err = apply_leverage_guard(IndiaMainnet, Err(anyhow::anyhow!("ADAUSDT 100x")))
            .unwrap_err();
        assert!(format!("{err:#}").contains("mainnet start refused"), "{err:#}");
        assert!(format!("{err:#}").contains("ADAUSDT 100x"), "{err:#}");
        assert!(apply_leverage_guard(DemoIndia, Err(anyhow::anyhow!("ADAUSDT 100x"))).is_ok());
        assert!(apply_leverage_guard(IndiaMainnet, Ok(())).is_ok());
        assert!(apply_leverage_guard(DemoIndia, Ok(())).is_ok());
    }

    #[test]
    fn leverage_over_the_cap_names_every_symbol_and_the_fix() {
        let err = check_leverage(
            &readings(&[("ADAUSDT", 100.0), ("ETHUSDT", 5.0), ("SOLUSDT", 10.0)]),
            5.0,
        )
        .unwrap_err()
        .to_string();
        assert!(err.contains("ADAUSDT 100x"), "{err}");
        assert!(err.contains("SOLUSDT 10x"), "{err}");
        assert!(!err.contains("ETHUSDT"), "{err}");
        assert!(err.contains("MM_MAX_LEVERAGE=5x"), "{err}");
        assert!(err.contains("Set the order leverage on Delta") && err.contains("restart"), "{err}");
    }

    #[test]
    fn unreadable_leverage_fails_closed() {
        assert!(check_leverage(&readings(&[("ADAUSDT", f64::NAN)]), 5.0).is_err());
    }

    #[test]
    fn max_leverage_knob_falls_back_to_the_default_when_not_positive() {
        assert_eq!(max_leverage_or_default(3.0), 3.0);
        assert_eq!(max_leverage_or_default(0.0), DEFAULT_MAX_LEVERAGE);
        assert_eq!(max_leverage_or_default(-2.0), DEFAULT_MAX_LEVERAGE);
        assert_eq!(max_leverage_or_default(f64::NAN), DEFAULT_MAX_LEVERAGE);
        assert_eq!(max_leverage_or_default(f64::INFINITY), DEFAULT_MAX_LEVERAGE);
        assert_eq!(DEFAULT_MAX_LEVERAGE, 5.0);
    }
}
