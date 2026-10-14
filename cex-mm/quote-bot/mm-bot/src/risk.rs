use std::time::{Duration, Instant};

use chrono::NaiveDate;
use mm_core::regime::RegimeEngine;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone)]
pub struct RiskState {
    pub halt: bool,
    pub daily_loss_limit_usd: f64,
    pub daily_pnl_usd: f64,
    pub reject_count: u64,
    pub reject_kill_count: u64,
}

/// What the loop should do about the age of the venue book on this iteration.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BookAge {
    Fresh,
    /// First fresh book after an outage; carries how long the book was stale.
    Recovered(Duration),
    /// The feed just went silent past the limit: cancel quotes once.
    WentStale,
    /// Still stale: keep quotes off.
    Stale,
}

/// Tracks when the book feed last delivered, at loop resolution. Arms on the first book: before
/// that the loop has nothing to quote, and a slow websocket connect is not an outage.
#[derive(Debug, Clone)]
pub struct BookWatch {
    last_update: Option<Instant>,
    stale_after: Duration,
    stale_since: Option<Instant>,
}

impl BookWatch {
    pub fn new(stale_after: Duration) -> Self {
        Self {
            last_update: None,
            stale_after,
            stale_since: None,
        }
    }

    /// `updated`: the feed delivered a book since the previous check.
    pub fn check(&mut self, updated: bool, now: Instant) -> BookAge {
        if updated {
            self.last_update = Some(now);
        }
        let Some(last) = self.last_update else {
            return BookAge::Fresh;
        };
        let stale = now.saturating_duration_since(last) > self.stale_after;
        match (stale, self.stale_since) {
            (true, None) => {
                self.stale_since = Some(now);
                BookAge::WentStale
            }
            (true, Some(_)) => BookAge::Stale,
            (false, Some(since)) => {
                self.stale_since = None;
                BookAge::Recovered(now.saturating_duration_since(since))
            }
            (false, None) => BookAge::Fresh,
        }
    }

    pub fn age_ms(&self, now: Instant) -> u64 {
        self.last_update
            .map(|t| now.saturating_duration_since(t).as_millis() as u64)
            .unwrap_or(0)
    }
}

/// What the loop should do about the private fills feed on this iteration.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FeedHealth {
    /// Subscribed, or down for no longer than the grace period (a normal reconnect).
    Up,
    /// Down past the grace period, first time: switch the adding side off. Carries how long it has been down.
    WentDown(Duration),
    /// Still down: keep the adding side off.
    Down,
    /// Subscribed again after `WentDown`; carries how long the feed was down.
    Recovered(Duration),
}

/// Watches the private fills feed in a run with keys. While it is down, fills reach the bot only through
/// the venue reconcile every few seconds (the 13 Oct 2026 failure: the cap overshot to -811 against 600),
/// so after `pull_after` the side that adds to the position is switched off and the reducing side keeps
/// quoting.
#[derive(Debug, Clone)]
pub struct FeedWatch {
    pull_after: Duration,
    down_since: Option<Instant>,
    pulled: bool,
}

impl FeedWatch {
    pub fn new(pull_after: Duration) -> Self {
        Self {
            pull_after,
            down_since: None,
            pulled: false,
        }
    }

    /// `subscribed`: the venue confirms the fills subscription on the current connection.
    pub fn check(&mut self, subscribed: bool, now: Instant) -> FeedHealth {
        if subscribed {
            let since = self.down_since.take();
            if std::mem::take(&mut self.pulled) {
                return FeedHealth::Recovered(since.map_or(Duration::ZERO, |t| now.saturating_duration_since(t)));
            }
            return FeedHealth::Up;
        }
        let down_for = now.saturating_duration_since(*self.down_since.get_or_insert(now));
        if down_for <= self.pull_after {
            FeedHealth::Up
        } else if self.pulled {
            FeedHealth::Down
        } else {
            self.pulled = true;
            FeedHealth::WentDown(down_for)
        }
    }
}

impl Default for RiskState {
    fn default() -> Self {
        Self {
            halt: false,
            daily_loss_limit_usd: std::env::var("MM_DAILY_LOSS_LIMIT_USD")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(500.0),
            daily_pnl_usd: 0.0,
            reject_count: 0,
            reject_kill_count: std::env::var("MM_REJECT_KILL_COUNT")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(20),
        }
    }
}

/// One UTC day of the daily loss stop, persisted so a restart keeps the baseline and the halt.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct DailyLossState {
    pub day: NaiveDate,
    pub baseline_equity: f64,
    pub halted: bool,
}

/// Account-wide daily loss stop on venue equity (realized + unrealized, after fees). PnL is equity
/// minus the first equity read of the UTC day. Once breached it stays halted until the next day.
/// Deposits and withdrawals move equity too: a withdrawal can halt early, a deposit hides losses.
#[derive(Debug, Clone)]
pub struct DailyLossGuard {
    limit_usd: f64,
    state: Option<DailyLossState>,
}

impl DailyLossGuard {
    /// `limit_usd <= 0` disables the stop.
    pub fn new(limit_usd: f64, saved: Option<DailyLossState>) -> Self {
        Self { limit_usd, state: saved }
    }

    /// Records an equity reading and returns today's PnL.
    pub fn observe(&mut self, equity: f64, today: NaiveDate) -> f64 {
        let st = match self.state {
            Some(s) if s.day == today => s,
            _ => DailyLossState { day: today, baseline_equity: equity, halted: false },
        };
        let pnl = equity - st.baseline_equity;
        let halted = st.halted || (self.limit_usd > 0.0 && pnl <= -self.limit_usd);
        self.state = Some(DailyLossState { halted, ..st });
        pnl
    }

    pub fn breached(&self) -> bool {
        self.state.is_some_and(|s| s.halted)
    }

    /// A saved halt from `today` blocks a fresh start.
    pub fn halted_on(&self, today: NaiveDate) -> bool {
        self.state.is_some_and(|s| s.halted && s.day == today)
    }

    pub fn state(&self) -> Option<DailyLossState> {
        self.state
    }
}

/// Quotes are post-only, so a taker fill means something placed an order that took liquidity.
/// The bot's own reduce-only exit (sent within `grace_ms` of the fill) is the one expected case.
pub fn taker_fill_unexpected(taker: bool, fill_ms: i64, last_reduce_only_ms: Option<i64>, grace_ms: i64) -> bool {
    taker && !last_reduce_only_ms.is_some_and(|sent| (fill_ms - sent).abs() <= grace_ms)
}

/// Whether a place error should increment `reject_count` toward the kill switch.
///
/// Venue post-only crosses and qty-below-contract rejects are expected during
/// inventory shaping / reduce paths and must not permanently halt quoting.
pub fn counts_toward_reject_kill(err: &str) -> bool {
    let lower = err.to_ascii_lowercase();
    if lower.contains("immediate_execution_post_only") {
        return false;
    }
    if lower.contains("below") && lower.contains("contract") {
        return false;
    }
    true
}

impl RiskState {
    pub fn should_kill(&self, _regime_engine: &RegimeEngine) -> bool {
        self.halt
            || self.daily_pnl_usd <= -self.daily_loss_limit_usd
            || self.reject_count > self.reject_kill_count
            || mm_core::regime::RegimeEngine::calendar_pause_utc(chrono::Utc::now())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{Duration, Instant};

    fn ms(n: u64) -> Duration {
        Duration::from_millis(n)
    }

    #[test]
    fn book_updates_keep_the_book_fresh() {
        let t0 = Instant::now();
        let mut w = BookWatch::new(ms(2000));
        assert_eq!(w.check(true, t0 + ms(400)), BookAge::Fresh);
        assert_eq!(w.check(true, t0 + ms(2800)), BookAge::Fresh);
        assert_eq!(w.age_ms(t0 + ms(3000)), 200);
    }

    #[test]
    fn silent_feed_goes_stale_once_then_stays_stale() {
        let t0 = Instant::now();
        let mut w = BookWatch::new(ms(2000));
        assert_eq!(w.check(true, t0), BookAge::Fresh);
        assert_eq!(w.check(false, t0 + ms(2000)), BookAge::Fresh, "at the limit is still fresh");
        assert_eq!(w.check(false, t0 + ms(2100)), BookAge::WentStale);
        assert_eq!(w.check(false, t0 + ms(2500)), BookAge::Stale);
        assert_eq!(w.check(false, t0 + ms(9000)), BookAge::Stale);
    }

    fn day(d: u32) -> chrono::NaiveDate {
        chrono::NaiveDate::from_ymd_opt(2026, 10, d).unwrap()
    }

    #[test]
    fn daily_pnl_is_equity_minus_the_days_first_reading() {
        let mut g = DailyLossGuard::new(15.0, None);
        assert_eq!(g.observe(135.0, day(5)), 0.0);
        assert_eq!(g.observe(129.0, day(5)), -6.0);
        assert!(!g.breached());
        assert_eq!(g.observe(120.0, day(5)), -15.0);
        assert!(g.breached(), "at the limit halts");
    }

    #[test]
    fn a_halt_sticks_for_the_rest_of_the_day_then_resets() {
        let mut g = DailyLossGuard::new(15.0, None);
        g.observe(135.0, day(5));
        g.observe(119.0, day(5));
        assert!(g.breached());
        g.observe(140.0, day(5));
        assert!(g.breached(), "a bounce does not un-halt");
        assert_eq!(g.observe(140.0, day(6)), 0.0, "new UTC day, new baseline");
        assert!(!g.breached());
    }

    #[test]
    fn a_restart_keeps_the_days_baseline_and_halt() {
        let saved = DailyLossState { day: day(5), baseline_equity: 135.0, halted: false };
        let mut g = DailyLossGuard::new(15.0, Some(saved));
        assert_eq!(g.observe(125.0, day(5)), -10.0, "baseline survives the restart");
        let halted = DailyLossState { day: day(5), baseline_equity: 135.0, halted: true };
        assert!(DailyLossGuard::new(15.0, Some(halted)).halted_on(day(5)));
        assert!(!DailyLossGuard::new(15.0, Some(halted)).halted_on(day(6)));
        assert!(!DailyLossGuard::new(15.0, None).halted_on(day(5)));
    }

    #[test]
    fn zero_limit_disables_the_daily_stop() {
        let mut g = DailyLossGuard::new(0.0, None);
        g.observe(135.0, day(5));
        g.observe(1.0, day(5));
        assert!(!g.breached());
    }

    #[test]
    fn only_taker_fills_without_our_own_reduce_only_are_unexpected() {
        // Fill at t=100_000 ms. Reduce-only sent at 95_000 explains it; one sent at 10_000 does not.
        assert!(!taker_fill_unexpected(false, 100_000, None, 60_000), "maker fills are fine");
        assert!(taker_fill_unexpected(true, 100_000, None, 60_000));
        assert!(!taker_fill_unexpected(true, 100_000, Some(95_000), 60_000));
        assert!(taker_fill_unexpected(true, 100_000, Some(10_000), 60_000));
    }

    #[test]
    fn a_short_feed_drop_is_a_reconnect_not_an_outage() {
        let t0 = Instant::now();
        let mut w = FeedWatch::new(ms(30_000));
        assert_eq!(w.check(true, t0), FeedHealth::Up);
        assert_eq!(w.check(false, t0 + ms(1_000)), FeedHealth::Up);
        assert_eq!(w.check(false, t0 + ms(31_000)), FeedHealth::Up, "at the limit is still up");
        assert_eq!(w.check(true, t0 + ms(32_000)), FeedHealth::Up, "no pull, so nothing to recover");
        // The next drop starts its own clock.
        assert_eq!(w.check(false, t0 + ms(40_000)), FeedHealth::Up);
        assert_eq!(w.check(false, t0 + ms(69_000)), FeedHealth::Up);
    }

    #[test]
    fn a_long_feed_outage_pulls_once_and_reports_the_recovery() {
        let t0 = Instant::now();
        let mut w = FeedWatch::new(ms(30_000));
        assert_eq!(w.check(false, t0), FeedHealth::Up);
        assert_eq!(w.check(false, t0 + ms(30_400)), FeedHealth::WentDown(ms(30_400)));
        assert_eq!(w.check(false, t0 + ms(30_800)), FeedHealth::Down);
        assert_eq!(w.check(false, t0 + ms(90_000)), FeedHealth::Down);
        assert_eq!(w.check(true, t0 + ms(95_000)), FeedHealth::Recovered(ms(95_000)));
        assert_eq!(w.check(true, t0 + ms(95_400)), FeedHealth::Up);
    }

    #[test]
    fn a_slow_start_is_not_stale_before_the_first_book() {
        // Without a book the loop cannot quote anyway; only a feed that stops after it started
        // should cancel.
        let t0 = Instant::now();
        let mut w = BookWatch::new(ms(2000));
        assert_eq!(w.check(false, t0 + ms(4000)), BookAge::Fresh);
        assert_eq!(w.check(true, t0 + ms(4400)), BookAge::Fresh);
        assert_eq!(w.check(false, t0 + ms(6500)), BookAge::WentStale);
    }

    #[test]
    fn first_update_after_an_outage_reports_how_long_it_lasted() {
        let t0 = Instant::now();
        let mut w = BookWatch::new(ms(2000));
        assert_eq!(w.check(true, t0), BookAge::Fresh);
        assert_eq!(w.check(false, t0 + ms(2100)), BookAge::WentStale);
        assert_eq!(w.check(true, t0 + ms(5000)), BookAge::Recovered(ms(2900)));
        assert_eq!(w.check(false, t0 + ms(5400)), BookAge::Fresh);
    }

    #[test]
    fn reject_storm_triggers_kill() {
        let mut r = RiskState::default();
        r.reject_kill_count = 20;
        r.reject_count = 21;
        assert!(r.should_kill(&RegimeEngine::default()));
    }

    #[test]
    fn post_only_cross_does_not_count() {
        assert!(!counts_toward_reject_kill(
            "order rejected: immediate_execution_post_only"
        ));
        assert!(!counts_toward_reject_kill(
            "Immediate_Execution_Post_Only on ask"
        ));
    }

    #[test]
    fn below_contract_does_not_count() {
        assert!(!counts_toward_reject_kill(
            "qty 0.0004 below 1 contract (0.001 each)"
        ));
        assert!(!counts_toward_reject_kill(
            "Order size below minimum contract size"
        ));
    }

    #[test]
    fn other_rejects_count() {
        assert!(counts_toward_reject_kill("insufficient margin"));
        assert!(counts_toward_reject_kill("rate limit exceeded"));
        assert!(counts_toward_reject_kill("below minimum price"));
    }
}
