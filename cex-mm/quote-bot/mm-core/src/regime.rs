use chrono::{DateTime, Datelike, NaiveDate, NaiveDateTime, TimeDelta, Timelike, Utc, Weekday};

/// Volatility regime L0–L3 (R5 / STRATEGY §6.3).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RegimeLevel {
    L0Calm = 0,
    L1Elevated = 1,
    L2Stressed = 2,
    L3Crash = 3,
}

impl RegimeLevel {
    pub fn spread_multiplier(self) -> f64 {
        match self {
            RegimeLevel::L0Calm => 1.0,
            RegimeLevel::L1Elevated => 1.5,
            RegimeLevel::L2Stressed => 2.25,
            RegimeLevel::L3Crash => 0.0,
        }
    }

    pub fn as_u8(self) -> u8 {
        self as u8
    }
}

#[derive(Debug, Clone)]
pub struct RegimeState {
    pub level: RegimeLevel,
    pub vol_ratio: f64,
    pub flow_z: f64,
}

#[derive(Debug, Clone, Copy)]
pub struct RegimeThresholds {
    /// L3 when `min(bid_qty,ask_qty)/max(...) < this`.
    pub l3_depth_ratio: f64,
    pub l3_jump_bps: f64,
    pub l3_flow_z: f64,
}

impl Default for RegimeThresholds {
    fn default() -> Self {
        Self {
            l3_depth_ratio: 0.2,
            l3_jump_bps: 50.0,
            l3_flow_z: 4.0,
        }
    }
}

pub struct RegimeEngine {
    vol_short: f64,
    vol_long: f64,
    flow_window: std::collections::VecDeque<f64>,
    flow_cap: usize,
    last_level: RegimeLevel,
}

impl Default for RegimeEngine {
    fn default() -> Self {
        Self {
            vol_short: 0.0,
            vol_long: 1.0,
            flow_window: std::collections::VecDeque::new(),
            flow_cap: 64,
            last_level: RegimeLevel::L0Calm,
        }
    }
}

impl RegimeEngine {
    pub fn update_vol(&mut self, sample_vol_bps: f64) {
        self.vol_short = 0.9 * self.vol_short + 0.1 * sample_vol_bps;
        self.vol_long = 0.99 * self.vol_long + 0.01 * sample_vol_bps.max(1.0);
    }

    pub fn on_signed_trade(&mut self, signed_qty: f64) {
        if self.flow_window.len() >= self.flow_cap {
            self.flow_window.pop_front();
        }
        self.flow_window.push_back(signed_qty);
    }

    fn flow_zscore(&self) -> f64 {
        if self.flow_window.len() < 8 {
            return 0.0;
        }
        let mean = self.flow_window.iter().sum::<f64>() / self.flow_window.len() as f64;
        let var = self.flow_window
            .iter()
            .map(|x| (x - mean).powi(2))
            .sum::<f64>()
            / (self.flow_window.len() - 1) as f64;
        let std = var.sqrt().max(1e-9);
        let last = *self.flow_window.back().unwrap_or(&0.0);
        (last - mean) / std
    }

    pub fn evaluate(&mut self, depth_ratio: f64, jump_bps: f64) -> RegimeState {
        self.evaluate_with(&RegimeThresholds::default(), depth_ratio, jump_bps)
    }

    pub fn evaluate_with(
        &mut self,
        th: &RegimeThresholds,
        depth_ratio: f64,
        jump_bps: f64,
    ) -> RegimeState {
        let ratio = if self.vol_long > 0.0 {
            self.vol_short / self.vol_long
        } else {
            1.0
        };
        let flow_z = self.flow_zscore();
        let mut level = RegimeLevel::L0Calm;
        let depth_l3 = th.l3_depth_ratio > 0.0 && depth_ratio < th.l3_depth_ratio;
        let trip_l3 = depth_l3 || jump_bps > th.l3_jump_bps || flow_z.abs() > th.l3_flow_z;
        if trip_l3 {
            // L3 is one-shot for this sample only — do not latch into last_level.
            return RegimeState {
                level: RegimeLevel::L3Crash,
                vol_ratio: ratio,
                flow_z,
            };
        } else if ratio > 2.5 || jump_bps > 15.0 || flow_z.abs() > 2.5 {
            level = RegimeLevel::L2Stressed;
        } else if ratio > 1.5 {
            level = RegimeLevel::L1Elevated;
        }
        // Hysteresis caps at L2; L3 never stored in last_level.
        if level as u8 > self.last_level as u8 {
            self.last_level = level;
        } else if (level as u8) < (self.last_level as u8) && ratio < 1.2 {
            self.last_level = level;
        } else {
            level = self.last_level;
        }
        RegimeState {
            level,
            vol_ratio: ratio,
            flow_z,
        }
    }

    /// Daily news pause (K11, STRATEGY.md: CPI/FOMC T-2m to T+5m), anchored to
    /// America/New_York wall-clock time so it follows US daylight saving:
    ///
    /// - 08:28-08:35 ET: the 08:30 ET US releases (CPI, NFP, PPI, jobless
    ///   claims, retail sales). 12:28-12:35 UTC under EDT, 13:28-13:35 UTC under EST.
    /// - 14:28-14:35 ET: the 14:30 ET FOMC press conference (the 14:00 ET
    ///   statement is not covered). 18:28-18:35 UTC under EDT, 19:28-19:35 UTC under EST.
    ///
    /// Minutes are inclusive (through hh:35:59). It runs every day, not from an
    /// event calendar, so it also pauses on days with no release.
    pub fn calendar_pause_utc(now: DateTime<Utc>) -> bool {
        let local = new_york_local_time(now);
        (local.hour() == 8 || local.hour() == 14) && (28..=35).contains(&local.minute())
    }
}

/// America/New_York UTC offset in hours at `now`: -4 under US daylight time
/// (EDT), -5 otherwise (EST). DST runs from the second Sunday of March at
/// 02:00 EST (07:00 UTC) to the first Sunday of November at 02:00 EDT (06:00 UTC).
// shortcut: hard-codes the 2007 US DST rule, switch to chrono-tz if US DST law changes
fn new_york_utc_offset_hours(now: DateTime<Utc>) -> i64 {
    let year = now.year();
    let start = sunday_utc(year, 3, 2, 7);
    let end = sunday_utc(year, 11, 1, 6);
    match (start, end) {
        (Some(start), Some(end)) if now >= start && now < end => -4,
        _ => -5,
    }
}

/// The `nth` Sunday of `month` in `year` at `hour_utc`:00 UTC. `None` only
/// outside chrono's date range.
fn sunday_utc(year: i32, month: u32, nth: u8, hour_utc: u32) -> Option<DateTime<Utc>> {
    NaiveDate::from_weekday_of_month_opt(year, month, Weekday::Sun, nth)
        .and_then(|d| d.and_hms_opt(hour_utc, 0, 0))
        .map(|dt| dt.and_utc())
}

/// Wall-clock time in America/New_York at `now`.
fn new_york_local_time(now: DateTime<Utc>) -> NaiveDateTime {
    now.naive_utc() + TimeDelta::hours(new_york_utc_offset_hours(now))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn regime_escalates_with_vol_ratio() {
        let mut e = RegimeEngine::default();
        for _ in 0..50 {
            e.update_vol(80.0);
        }
        let st = e.evaluate(1.0, 0.0);
        assert!(st.level as u8 >= RegimeLevel::L1Elevated as u8);
    }

    #[test]
    fn l3_jump_is_oneshot_not_latched() {
        let mut e = RegimeEngine::default();
        e.vol_short = 1.0;
        e.vol_long = 1.0;
        let th = RegimeThresholds {
            l3_depth_ratio: 0.2,
            l3_jump_bps: 50.0,
            l3_flow_z: 4.0,
        };
        let st1 = e.evaluate_with(&th, 1.0, 60.0);
        assert_eq!(st1.level, RegimeLevel::L3Crash);
        let st2 = e.evaluate_with(&th, 1.0, 0.0);
        assert!(
            (st2.level as u8) < (RegimeLevel::L3Crash as u8),
            "expected below L3 after calm sample, got {:?}",
            st2.level
        );
    }

    #[test]
    fn funding_skews_fair_via_extensions() {
        let ext = crate::QuoteExtensions {
            funding_carry_bps: -10.0,
            ..Default::default()
        };
        let fair = crate::fair::resolve_fair_cex(100.0, None, ext);
        assert!(fair < 100.0);
    }

    fn utc(rfc3339: &str) -> DateTime<Utc> {
        rfc3339.parse().expect("test timestamp is RFC 3339")
    }

    fn ny_local(rfc3339: &str) -> String {
        new_york_local_time(utc(rfc3339))
            .format("%Y-%m-%d %H:%M:%S")
            .to_string()
    }

    #[test]
    fn new_york_offset_flips_exactly_at_the_dst_boundaries() {
        // (one second before, boundary, offset before, offset at boundary)
        let cases = [
            ("2025-03-09T06:59:59Z", "2025-03-09T07:00:00Z", -5, -4),
            ("2025-11-02T05:59:59Z", "2025-11-02T06:00:00Z", -4, -5),
            ("2026-03-08T06:59:59Z", "2026-03-08T07:00:00Z", -5, -4),
            ("2026-11-01T05:59:59Z", "2026-11-01T06:00:00Z", -4, -5),
            ("2027-03-14T06:59:59Z", "2027-03-14T07:00:00Z", -5, -4),
            ("2027-11-07T05:59:59Z", "2027-11-07T06:00:00Z", -4, -5),
        ];
        for (before, at, off_before, off_at) in cases {
            assert_eq!(
                new_york_utc_offset_hours(utc(before)),
                off_before,
                "{before}"
            );
            assert_eq!(new_york_utc_offset_hours(utc(at)), off_at, "{at}");
        }
    }

    #[test]
    fn new_york_local_time_jumps_at_the_2026_boundaries() {
        // Spring forward: 01:59:59 EST -> 03:00:00 EDT.
        assert_eq!(ny_local("2026-03-08T06:59:59Z"), "2026-03-08 01:59:59");
        assert_eq!(ny_local("2026-03-08T07:00:00Z"), "2026-03-08 03:00:00");
        // Fall back: 01:59:59 EDT -> 01:00:00 EST.
        assert_eq!(ny_local("2026-11-01T05:59:59Z"), "2026-11-01 01:59:59");
        assert_eq!(ny_local("2026-11-01T06:00:00Z"), "2026-11-01 01:00:00");
        // Across UTC midnight the local date is the previous day.
        assert_eq!(ny_local("2026-12-10T03:00:00Z"), "2026-12-09 22:00:00");
    }

    fn paused(rfc3339: &str) -> bool {
        RegimeEngine::calendar_pause_utc(utc(rfc3339))
    }

    #[test]
    fn news_pause_follows_new_york_daylight_time() {
        // Fri 2026-10-09 is EDT (UTC-4): 08:30 ET = 12:30 UTC, 14:30 ET = 18:30 UTC.
        for t in [
            "2026-10-09T12:30:00Z",
            "2026-10-09T12:28:00Z",
            "2026-10-09T12:35:00Z",
            "2026-10-09T12:35:59Z",
            "2026-10-09T18:28:00Z",
            "2026-10-09T18:30:00Z",
            "2026-10-09T18:35:59Z",
        ] {
            assert!(paused(t), "{t} is inside an EDT news window");
        }
        for t in [
            "2026-10-09T12:27:59Z",
            "2026-10-09T12:36:00Z",
            // 09:30 EDT: the old fixed 13:28-13:35 UTC window paused here.
            "2026-10-09T13:30:00Z",
            "2026-10-09T18:27:59Z",
            "2026-10-09T18:36:00Z",
        ] {
            assert!(!paused(t), "{t} is outside the EDT news windows");
        }
    }

    #[test]
    fn news_pause_follows_new_york_standard_time() {
        // Thu 2026-12-10 is EST (UTC-5): 08:30 ET = 13:30 UTC, 14:30 ET = 19:30 UTC.
        assert!(paused("2026-12-10T13:30:00Z"));
        assert!(!paused("2026-12-10T12:30:00Z"), "07:30 EST");
        assert!(paused("2026-12-10T19:30:00Z"));
        assert!(!paused("2026-12-10T18:30:00Z"), "13:30 EST");
    }

    #[test]
    fn news_pause_moves_with_the_dst_end_weekend() {
        // DST ends Sun 2026-11-01 at 06:00 UTC (02:00 EDT -> 01:00 EST).
        assert!(paused("2026-10-30T12:30:00Z"), "Fri 08:30 EDT");
        assert!(!paused("2026-11-01T12:30:00Z"), "Sun 07:30 EST");
        assert!(paused("2026-11-01T13:30:00Z"), "Sun 08:30 EST");
        assert!(paused("2026-11-02T13:30:00Z"), "Mon 08:30 EST");
        assert!(!paused("2026-11-02T12:30:00Z"), "Mon 07:30 EST");
    }

    #[test]
    fn news_pause_moves_with_the_dst_start_weekend() {
        // DST starts Sun 2026-03-08 at 07:00 UTC (02:00 EST -> 03:00 EDT).
        assert!(paused("2026-03-06T13:30:00Z"), "Fri 08:30 EST");
        assert!(paused("2026-03-09T12:30:00Z"), "Mon 08:30 EDT");
        assert!(!paused("2026-03-09T13:30:00Z"), "Mon 09:30 EDT");
    }
}
