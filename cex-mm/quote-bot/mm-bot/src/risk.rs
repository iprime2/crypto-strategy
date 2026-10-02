use std::time::{Duration, Instant};

use mm_core::regime::RegimeEngine;

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

/// Tracks when the book feed last delivered, at loop resolution.
#[derive(Debug, Clone)]
pub struct BookWatch {
    last_update: Instant,
    stale_after: Duration,
    stale_since: Option<Instant>,
}

impl BookWatch {
    pub fn new(stale_after: Duration, now: Instant) -> Self {
        Self {
            last_update: now,
            stale_after,
            stale_since: None,
        }
    }

    /// `updated`: the feed delivered a book since the previous check.
    pub fn check(&mut self, updated: bool, now: Instant) -> BookAge {
        if updated {
            self.last_update = now;
        }
        let stale = now.saturating_duration_since(self.last_update) > self.stale_after;
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
        now.saturating_duration_since(self.last_update).as_millis() as u64
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
        let mut w = BookWatch::new(ms(2000), t0);
        assert_eq!(w.check(true, t0 + ms(400)), BookAge::Fresh);
        assert_eq!(w.check(true, t0 + ms(2800)), BookAge::Fresh);
        assert_eq!(w.age_ms(t0 + ms(3000)), 200);
    }

    #[test]
    fn silent_feed_goes_stale_once_then_stays_stale() {
        let t0 = Instant::now();
        let mut w = BookWatch::new(ms(2000), t0);
        assert_eq!(w.check(false, t0 + ms(2000)), BookAge::Fresh, "at the limit is still fresh");
        assert_eq!(w.check(false, t0 + ms(2100)), BookAge::WentStale);
        assert_eq!(w.check(false, t0 + ms(2500)), BookAge::Stale);
        assert_eq!(w.check(false, t0 + ms(9000)), BookAge::Stale);
    }

    #[test]
    fn first_update_after_an_outage_reports_how_long_it_lasted() {
        let t0 = Instant::now();
        let mut w = BookWatch::new(ms(2000), t0);
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
