use std::time::{Duration, Instant};

use chrono::{DateTime, NaiveDate, Utc};
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

/// What the loop should do about a Delta book that keeps arriving but has stopped changing.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum BookFreeze {
    Live,
    /// Frozen past the limit, first time: cancel quotes once. Carries how long the top has been unchanged and
    /// the largest Binance move since it last changed.
    WentFrozen { unchanged: Duration, binance_move_bps: f64 },
    /// Still frozen: keep quotes off.
    Frozen,
    /// The top changed again after `WentFrozen`; carries how long it was frozen.
    Thawed(Duration),
}

/// Catches a frozen venue book that `BookWatch` cannot see. On 17 Oct 2026, 19:30-20:14Z, Delta kept sending
/// `ob_l1` frames with an unchanged book on every symbol (no trades, mark price frozen too) while Binance moved
/// (ADA +13.5 bps, DUSK +356 bps), so the book never went stale by arrival time; the anchored fair's basis
/// learned the frozen book and sat 12-18 bps off Delta's mid for ten minutes after it came back.
///
/// The top of book (both prices and sizes) is frozen when it has not changed for `after` and Binance has moved
/// at least `move_bps` since it last changed, or when it has not changed for `max_after` whatever Binance did
/// (also covers a stale Binance feed). Over the 15-18 Oct shadow (64 h, four symbols) neither fired outside
/// the freeze at 30 s / 5 bps / 120 s; the longest unchanged top was 63 s (ADA, Binance one tick away). A zero
/// duration switches its rule off.
#[derive(Debug, Clone)]
pub struct FrozenBookWatch {
    after: Duration,
    move_bps: f64,
    max_after: Duration,
    top: Option<[f64; 4]>,
    changed_at: Option<Instant>,
    binance_ref: Option<f64>,
    max_move_bps: f64,
    frozen_since: Option<Instant>,
}

impl FrozenBookWatch {
    pub fn new(after: Duration, move_bps: f64, max_after: Duration) -> Self {
        Self {
            after,
            move_bps,
            max_after,
            top: None,
            changed_at: None,
            binance_ref: None,
            max_move_bps: 0.0,
            frozen_since: None,
        }
    }

    /// `top`: bid, ask, bid size, ask size this loop. `binance_mid`: the Binance mid when it is fresh, else None.
    pub fn check(&mut self, top: [f64; 4], binance_mid: Option<f64>, now: Instant) -> BookFreeze {
        let binance_mid = binance_mid.filter(|b| *b > 0.0);
        if self.top != Some(top) {
            self.top = Some(top);
            self.changed_at = Some(now);
            self.binance_ref = binance_mid;
            self.max_move_bps = 0.0;
            return match self.frozen_since.take() {
                Some(since) => BookFreeze::Thawed(now.saturating_duration_since(since)),
                None => BookFreeze::Live,
            };
        }
        match (self.binance_ref, binance_mid) {
            (Some(r), Some(b)) => self.max_move_bps = self.max_move_bps.max((b / r - 1.0).abs() * 10_000.0),
            (None, Some(b)) => self.binance_ref = Some(b),
            _ => {}
        }
        if self.frozen_since.is_some() {
            return BookFreeze::Frozen;
        }
        let unchanged = self.changed_at.map_or(Duration::ZERO, |t| now.saturating_duration_since(t));
        let moved = !self.after.is_zero() && unchanged >= self.after && self.max_move_bps >= self.move_bps;
        let long = !self.max_after.is_zero() && unchanged >= self.max_after;
        if !(moved || long) {
            return BookFreeze::Live;
        }
        self.frozen_since = Some(now);
        BookFreeze::WentFrozen { unchanged, binance_move_bps: self.max_move_bps }
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

    /// A watch that starts in the pulled state, for a guard that must hold until its input has been good
    /// at least once (a live start with the anchor on): the first `check(true)` reports `Recovered`.
    pub fn starting_down(pull_after: Duration, now: Instant) -> Self {
        Self {
            pull_after,
            down_since: Some(now),
            pulled: true,
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
        if self.pulled {
            FeedHealth::Down
        } else if down_for <= self.pull_after {
            FeedHealth::Up
        } else {
            self.pulled = true;
            FeedHealth::WentDown(down_for)
        }
    }
}

/// What to do with a venue position read that differs from the bot's own count.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VenueReading {
    /// Within tolerance of the bot's count.
    Agrees,
    /// Take the venue's figure.
    Adopt,
    /// Read within the grace period of our last fill: the bot keeps its count, and the difference is adopted
    /// later if it lasts.
    Deferred,
}

/// When a venue position replaces the bot's own count. Delta's REST position trails its fills feed: on
/// 20 Oct 2026 a read 5 ms after a 27-contract fill still showed the old size, the bot adopted it and lost the
/// fill, sized a full quote into room it did not have, and the 300-contract cap reached -360. A read taken
/// within `grace` of the last fill is not adopted, unless the difference has already lasted `max_wait` (a fill
/// the feed never delivered still gets corrected).
#[derive(Debug, Clone)]
pub struct VenueReconcile {
    grace: Duration,
    max_wait: Duration,
    differs_since: Option<Instant>,
}

impl VenueReconcile {
    pub fn new(grace: Duration, max_wait: Duration) -> Self {
        Self { grace, max_wait, differs_since: None }
    }

    /// A reading whose request went out at `sent`, applied at `now`. A fill after `sent` cannot be in it,
    /// however long the answer took, so it counts as fresh too (the read runs off the quoting loop).
    pub fn check_read(
        &mut self,
        bot: f64,
        venue: f64,
        tolerance: f64,
        last_fill: Option<Instant>,
        sent: Instant,
        now: Instant,
    ) -> VenueReading {
        if (bot - venue).abs() <= tolerance {
            self.differs_since = None;
            return VenueReading::Agrees;
        }
        let since = *self.differs_since.get_or_insert(now);
        let fresh_fill = last_fill.is_some_and(|t| t >= sent || now.saturating_duration_since(t) < self.grace);
        if fresh_fill && now.saturating_duration_since(since) < self.max_wait {
            return VenueReading::Deferred;
        }
        self.differs_since = None;
        VenueReading::Adopt
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

/// The daily loss stop's day is the UTC calendar day (00:00 UTC = 05:30 IST), the day Delta's PNL Analytics page
/// counts (the owner's choice, 30 Oct 2026; the IST day before that).
const LOSS_DAY_UTC_OFFSET_MIN: i64 = 0;

/// The calendar day of the daily loss stop at `now`.
pub fn loss_day(now: DateTime<Utc>) -> NaiveDate {
    (now + chrono::Duration::minutes(LOSS_DAY_UTC_OFFSET_MIN)).date_naive()
}

/// One day of the daily loss stop, persisted so a restart keeps the baseline and the halt.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct DailyLossState {
    pub day: NaiveDate,
    pub baseline_equity: f64,
    pub halted: bool,
}

/// Account-wide daily loss stop on venue equity (realized + unrealized, after fees). PnL is equity
/// minus the first equity read of the day (`loss_day`). Once breached it stays halted until the next day.
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
    fn a_venue_read_right_after_a_fill_does_not_overwrite_the_bot() {
        // 20 Oct 2026, 14:07:28: a 27-contract sell took the bot to -187; the venue read 5 ms later said -160.
        let t0 = Instant::now();
        let mut r = VenueReconcile::new(ms(3000), ms(15_000));
        assert_eq!(r.check_read(-187.0, -160.0, 1e-6, Some(t0), t0 + ms(5), t0 + ms(5)), VenueReading::Deferred);
        // The next read, 5 s on, has caught up.
        assert_eq!(r.check_read(-187.0, -187.0, 1e-6, Some(t0), t0 + ms(5005), t0 + ms(5005)), VenueReading::Agrees);
    }

    #[test]
    fn a_fill_the_feed_never_sent_is_still_corrected() {
        let t0 = Instant::now();
        let mut r = VenueReconcile::new(ms(3000), ms(15_000));
        // No fill for a minute: the venue's figure is taken at once.
        assert_eq!(r.check_read(-160.0, -187.0, 1e-6, Some(t0), t0 + ms(60_000), t0 + ms(60_000)), VenueReading::Adopt);
        // Never any fill: the same.
        let mut r = VenueReconcile::new(ms(3000), ms(15_000));
        assert_eq!(r.check_read(0.0, 100.0, 1e-6, None, t0, t0), VenueReading::Adopt);
        // Fills keep landing right before every read: the difference is adopted once it has lasted 15 s.
        let mut r = VenueReconcile::new(ms(3000), ms(15_000));
        for s in [0u64, 5, 10] {
            let now = t0 + ms(s * 1000);
            assert_eq!(r.check_read(-160.0, -187.0, 1e-6, Some(now - ms(100)), now, now), VenueReading::Deferred, "{s} s");
        }
        let now = t0 + ms(15_000);
        assert_eq!(r.check_read(-160.0, -187.0, 1e-6, Some(now - ms(100)), now, now), VenueReading::Adopt);
        // Adopting starts the clock again for the next difference.
        let now = t0 + ms(20_000);
        assert_eq!(r.check_read(-187.0, -200.0, 1e-6, Some(now - ms(100)), now, now), VenueReading::Deferred);
    }

    #[test]
    fn a_read_sent_before_a_fill_is_not_adopted_however_late_it_answers() {
        // The read is sent, a fill lands 100 ms later, and the answer (without the fill) is applied 3.5 s
        // after it: past the grace, but that reading cannot contain the fill.
        let t0 = Instant::now();
        let mut r = VenueReconcile::new(ms(3000), ms(15_000));
        assert_eq!(r.check_read(-187.0, -160.0, 1e-6, Some(t0 + ms(100)), t0, t0 + ms(3600)), VenueReading::Deferred);
        // A read sent after the fill, applied past the grace, is adopted as before.
        let mut r = VenueReconcile::new(ms(3000), ms(15_000));
        assert_eq!(r.check_read(-187.0, -160.0, 1e-6, Some(t0), t0 + ms(3500), t0 + ms(3600)), VenueReading::Adopt);
        // A difference that lasts is still adopted after max_wait, even with fills landing during each read.
        let mut r = VenueReconcile::new(ms(3000), ms(15_000));
        for s in [0u64, 5, 10] {
            let sent = t0 + ms(s * 1000);
            assert_eq!(r.check_read(-160.0, -187.0, 1e-6, Some(sent + ms(50)), sent, sent + ms(400)), VenueReading::Deferred);
        }
        let sent = t0 + ms(15_000);
        assert_eq!(r.check_read(-160.0, -187.0, 1e-6, Some(sent + ms(50)), sent, sent + ms(400)), VenueReading::Adopt);
    }

    #[test]
    fn agreement_resets_the_wait() {
        let t0 = Instant::now();
        let mut r = VenueReconcile::new(ms(3000), ms(15_000));
        assert_eq!(r.check_read(-100.0, -90.0, 1e-6, Some(t0), t0, t0), VenueReading::Deferred);
        assert_eq!(r.check_read(-100.0, -100.0, 1e-6, Some(t0), t0 + ms(5000), t0 + ms(5000)), VenueReading::Agrees);
        // A new difference 12 s later waits its own 15 s, not the remainder of the old one.
        let now = t0 + ms(17_000);
        assert_eq!(r.check_read(-120.0, -100.0, 1e-6, Some(now - ms(50)), now, now), VenueReading::Deferred);
        // Within tolerance counts as agreement.
        assert_eq!(r.check_read(-100.0, -100.0000001, 1e-6, Some(now), now + ms(10), now + ms(10)), VenueReading::Agrees);
    }

    #[test]
    fn book_updates_keep_the_book_fresh() {
        let t0 = Instant::now();
        let mut w = BookWatch::new(ms(2000));
        assert_eq!(w.check(true, t0 + ms(400)), BookAge::Fresh);
        assert_eq!(w.check(true, t0 + ms(2800)), BookAge::Fresh);
        assert_eq!(w.age_ms(t0 + ms(3000)), 200);
    }

    const TOP: [f64; 4] = [0.2202, 0.2205, 56_196.0, 44_789.0];

    fn frozen_watch() -> FrozenBookWatch {
        FrozenBookWatch::new(Duration::from_secs(30), 5.0, Duration::from_secs(120))
    }

    #[test]
    fn a_changing_book_is_never_frozen() {
        let t0 = Instant::now();
        let mut w = frozen_watch();
        for i in 0..1_000u64 {
            let top = [TOP[0], TOP[1], TOP[2] + (i % 2) as f64, TOP[3]];
            assert_eq!(w.check(top, Some(0.2205 * (1.0 + i as f64 * 1e-4)), t0 + ms(400 * i)), BookFreeze::Live);
        }
    }

    #[test]
    fn an_unchanged_book_freezes_once_binance_has_moved_past_the_limit() {
        // 17 Oct 2026 19:30Z: ob_l1 frames kept arriving with the same book while Binance moved.
        let t0 = Instant::now();
        let mut w = frozen_watch();
        assert_eq!(w.check(TOP, Some(0.22000), t0), BookFreeze::Live);
        assert_eq!(w.check(TOP, Some(0.22012), t0 + ms(10_000)), BookFreeze::Live, "5.5 bps, but only 10 s");
        assert_eq!(w.check(TOP, Some(0.22000), t0 + ms(29_600)), BookFreeze::Live, "Binance back, 29.6 s");
        match w.check(TOP, Some(0.22000), t0 + ms(30_000)) {
            BookFreeze::WentFrozen { unchanged, binance_move_bps } => {
                assert_eq!(unchanged, ms(30_000));
                assert!((binance_move_bps - 5.4545).abs() < 1e-3, "the largest move since the change counts: {binance_move_bps}");
            }
            other => panic!("expected WentFrozen, got {other:?}"),
        }
        assert_eq!(w.check(TOP, Some(0.22000), t0 + ms(30_400)), BookFreeze::Frozen);
        assert_eq!(w.check(TOP, None, t0 + ms(900_000)), BookFreeze::Frozen);
    }

    #[test]
    fn a_quiet_book_with_a_quiet_binance_freezes_only_after_the_long_limit() {
        // ADA's longest unchanged top outside the freeze over 64 h was 63 s, with Binance one tick (4.4 bps) away.
        let t0 = Instant::now();
        let mut w = frozen_watch();
        assert_eq!(w.check(TOP, Some(0.22000), t0), BookFreeze::Live);
        assert_eq!(w.check(TOP, Some(0.22009), t0 + ms(63_200)), BookFreeze::Live, "4.1 bps is under the 5 bps limit");
        assert_eq!(w.check(TOP, Some(0.22009), t0 + ms(119_600)), BookFreeze::Live);
        assert!(matches!(w.check(TOP, Some(0.22009), t0 + ms(120_000)), BookFreeze::WentFrozen { .. }));
    }

    #[test]
    fn the_long_limit_freezes_while_binance_is_stale() {
        let t0 = Instant::now();
        let mut w = frozen_watch();
        assert_eq!(w.check(TOP, None, t0), BookFreeze::Live);
        assert_eq!(w.check(TOP, None, t0 + ms(60_000)), BookFreeze::Live, "no Binance mid: no move to measure");
        assert!(matches!(w.check(TOP, None, t0 + ms(120_000)), BookFreeze::WentFrozen { .. }));
    }

    #[test]
    fn the_move_counts_from_the_first_fresh_binance_mid_after_the_change() {
        let t0 = Instant::now();
        let mut w = frozen_watch();
        assert_eq!(w.check(TOP, None, t0), BookFreeze::Live);
        assert_eq!(w.check(TOP, Some(0.22000), t0 + ms(5_000)), BookFreeze::Live);
        assert_eq!(w.check(TOP, Some(0.22012), t0 + ms(29_000)), BookFreeze::Live, "5.5 bps at 29 s");
        assert!(matches!(w.check(TOP, Some(0.22012), t0 + ms(30_000)), BookFreeze::WentFrozen { .. }));
    }

    #[test]
    fn a_change_thaws_with_the_frozen_duration_and_resets_the_move() {
        let t0 = Instant::now();
        let mut w = frozen_watch();
        w.check(TOP, Some(0.22000), t0);
        w.check(TOP, Some(0.22030), t0 + ms(10_000));
        assert!(matches!(w.check(TOP, Some(0.22030), t0 + ms(30_000)), BookFreeze::WentFrozen { .. }));
        let moved = [TOP[0], TOP[1], TOP[2], TOP[3] - 200.0];
        assert_eq!(w.check(moved, Some(0.22030), t0 + ms(2_648_800)), BookFreeze::Thawed(ms(2_618_800)));
        // The move counts again from the change: Binance where it was is no move, so 30 s more is not frozen.
        assert_eq!(w.check(moved, Some(0.22030), t0 + ms(2_678_800)), BookFreeze::Live);
    }

    #[test]
    fn zero_limits_switch_the_watch_off() {
        let t0 = Instant::now();
        let mut w = FrozenBookWatch::new(Duration::ZERO, 5.0, Duration::ZERO);
        assert_eq!(w.check(TOP, Some(0.22000), t0), BookFreeze::Live);
        assert_eq!(w.check(TOP, Some(0.23000), t0 + ms(3_600_000)), BookFreeze::Live);
        let mut w = FrozenBookWatch::new(Duration::ZERO, 5.0, Duration::from_secs(120));
        w.check(TOP, Some(0.22000), t0);
        assert_eq!(w.check(TOP, Some(0.23000), t0 + ms(60_000)), BookFreeze::Live, "move rule off");
        assert!(matches!(w.check(TOP, Some(0.23000), t0 + ms(120_000)), BookFreeze::WentFrozen { .. }));
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
        assert_eq!(g.observe(140.0, day(6)), 0.0, "new day, new baseline");
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
    fn the_loss_day_is_the_utc_calendar_day() {
        // Delta's PNL Analytics page counts UTC days (00:00 UTC = 05:30 IST); the stop does too since 30 Oct 2026.
        let at = |s: &str| chrono::DateTime::parse_from_rfc3339(s).unwrap().with_timezone(&chrono::Utc);
        assert_eq!(loss_day(at("2026-10-27T18:30:00Z")), day(27), "00:00 IST no longer starts a day");
        assert_eq!(loss_day(at("2026-10-27T23:59:59Z")), day(27), "05:29:59 IST is still the 27th");
        assert_eq!(loss_day(at("2026-10-28T00:00:00Z")), day(28), "00:00 UTC (05:30 IST) starts the 28th");
        assert_eq!(loss_day(at("2026-10-28T23:59:59Z")), day(28));
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
    fn a_watch_started_down_holds_until_the_first_good_check() {
        let t0 = Instant::now();
        let mut w = FeedWatch::starting_down(ms(10_000), t0);
        assert_eq!(w.check(false, t0 + ms(400)), FeedHealth::Down, "no grace before the first good input");
        assert_eq!(w.check(false, t0 + ms(59_000)), FeedHealth::Down);
        assert_eq!(w.check(true, t0 + ms(60_000)), FeedHealth::Recovered(ms(60_000)));
        // From then on the usual grace applies.
        assert_eq!(w.check(false, t0 + ms(61_000)), FeedHealth::Up);
        assert_eq!(w.check(false, t0 + ms(71_400)), FeedHealth::WentDown(ms(10_400)));
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
