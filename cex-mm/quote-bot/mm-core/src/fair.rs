use crate::{BookTop, QuoteExtensions};

/// Native microprice blend + Binance move lead + OFI/funding reservation shift (bps on price).
///
/// Without an anchor the lead uses the recent Binance move, never the Binance price level: the two
/// venues list different contracts, so the raw level gap is a biased, noisy offset. With an anchor
/// (`anchor_fair`: the Binance mid moved onto Delta's level by a measured basis, see `BasisEma`), the
/// fair is pulled toward it by `anchor_weight` and the move lead is scaled by `1 - anchor_weight`, since
/// the anchor already carries the move.
pub fn resolve_fair_cex(fair_native: f64, book: Option<BookTop>, ext: QuoteExtensions) -> f64 {
    let mut fair = fair_native;
    if let Some(b) = book {
        if let (Some(mid), Some(micro)) = (b.mid(), b.microprice()) {
            let w = 0.3_f64;
            fair = (1.0 - w) * mid + w * micro;
        }
    }
    let anchor_w = match ext.anchor_fair {
        Some(a) if a.is_finite() && a > 0.0 && ext.anchor_weight.is_finite() => ext.anchor_weight.clamp(0.0, 1.0),
        _ => 0.0,
    };
    if anchor_w > 0.0 {
        fair = (1.0 - anchor_w) * fair + anchor_w * ext.anchor_fair.unwrap_or(fair);
    }
    let mut shift_bps = (1.0 - anchor_w) * ext.lead_weight * ext.binance_move_bps;
    if ext.lead_max_bps > 0.0 {
        shift_bps = shift_bps.clamp(-ext.lead_max_bps, ext.lead_max_bps);
    }
    fair *= 1.0 + (shift_bps + ext.ofi_drift_bps + ext.funding_carry_bps) / 10_000.0;
    fair
}

/// The Binance mid moved onto Delta's price level: `binance_mid * (1 + basis_bps)`.
pub fn anchored_fair(binance_mid: f64, basis_bps: f64) -> Option<f64> {
    (binance_mid > 0.0 && binance_mid.is_finite() && basis_bps.is_finite())
        .then(|| binance_mid * (1.0 + basis_bps / 10_000.0))
}

/// Delta-over-Binance basis in bps (`delta_mid / binance_mid - 1`), as an exponential average with a
/// half-life in seconds. Times are seconds on any monotonic clock; a sample older than the last one is
/// ignored. On ADA the basis moved several bps within hours (2026-10-13 memo), so the half-life must be
/// minutes, not hours.
///
/// Warm-up is the plain mean of the samples so far (weight `max(time weight, 1/n)`), so the first,
/// possibly lagged, sample does not dominate. `with_max_step` caps the time one update may cover, so a
/// single sample after a gap cannot reset the average; `with_clamp` limits each sample to the average
/// ± that many bps, so a dislocation moves it slowly. After a gap longer than the caller tolerates, call
/// `reset` to start the warm-up again.
#[derive(Debug, Clone)]
pub struct BasisEma {
    half_life_sec: f64,
    max_step_sec: f64,
    clamp_bps: f64,
    value_bps: Option<f64>,
    samples: u64,
    first_t: f64,
    last_t: f64,
}

impl BasisEma {
    pub fn new(half_life_sec: f64) -> Self {
        Self {
            half_life_sec,
            max_step_sec: f64::INFINITY,
            clamp_bps: f64::INFINITY,
            value_bps: None,
            samples: 0,
            first_t: 0.0,
            last_t: 0.0,
        }
    }

    /// Caps the time one update may cover (e.g. two loop intervals).
    pub fn with_max_step(mut self, sec: f64) -> Self {
        if sec > 0.0 {
            self.max_step_sec = sec;
        }
        self
    }

    /// Limits each sample to the current average ± `bps`.
    pub fn with_clamp(mut self, bps: f64) -> Self {
        if bps > 0.0 {
            self.clamp_bps = bps;
        }
        self
    }

    /// Forgets every sample; the next one starts a new warm-up.
    pub fn reset(&mut self) {
        self.value_bps = None;
        self.samples = 0;
    }

    /// Adds one Delta/Binance mid pair at time `t`; returns the new average, or None for bad inputs
    /// before any good sample.
    pub fn update(&mut self, t: f64, delta_mid: f64, binance_mid: f64) -> Option<f64> {
        let valid = delta_mid > 0.0 && binance_mid > 0.0 && delta_mid.is_finite() && binance_mid.is_finite();
        if !valid || !t.is_finite() {
            return self.value_bps;
        }
        let x = (delta_mid / binance_mid - 1.0) * 10_000.0;
        match self.value_bps {
            None => {
                self.value_bps = Some(x);
                self.samples = 1;
                self.first_t = t;
                self.last_t = t;
            }
            Some(_) if t < self.last_t => {}
            Some(v) => {
                let dt = (t - self.last_t).min(self.max_step_sec);
                let time_w = if self.half_life_sec > 0.0 {
                    1.0 - (-std::f64::consts::LN_2 * dt / self.half_life_sec).exp()
                } else {
                    1.0
                };
                self.samples += 1;
                let alpha = time_w.max(1.0 / self.samples as f64);
                let x = x.clamp(v - self.clamp_bps, v + self.clamp_bps);
                self.value_bps = Some(v + alpha * (x - v));
                self.last_t = t;
            }
        }
        self.value_bps
    }

    pub fn value_bps(&self) -> Option<f64> {
        self.value_bps
    }

    /// Seconds of samples behind the average at `now` (0 before the first sample).
    pub fn warm_sec(&self, now: f64) -> f64 {
        if self.value_bps.is_some() {
            (now - self.first_t).max(0.0)
        } else {
            0.0
        }
    }

    /// Time of the latest sample, if any.
    pub fn last_update(&self) -> Option<f64> {
        self.value_bps.map(|_| self.last_t)
    }
}

/// Mid change in bps from the latest sample at or before `now - lookback` to the newest sample.
///
/// `history` is `(time_sec, mid)` in ascending time. Returns 0.0 when no sample is old
/// enough or either mid is non-positive.
pub fn move_bps(history: &[(f64, f64)], now: f64, lookback: f64) -> f64 {
    let Some(&(_, mid_now)) = history.last() else {
        return 0.0;
    };
    let cutoff = now - lookback;
    let Some(&(_, mid_ref)) = history.iter().rev().find(|(t, _)| *t <= cutoff) else {
        return 0.0;
    };
    if mid_now <= 0.0 || mid_ref <= 0.0 {
        return 0.0;
    }
    (mid_now - mid_ref) / mid_ref * 10_000.0
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lead_ext(move_bps: f64) -> QuoteExtensions {
        QuoteExtensions {
            binance_mid: Some(2700.0),
            binance_move_bps: move_bps,
            lead_weight: 0.8,
            lead_max_bps: 15.0,
            ..Default::default()
        }
    }

    #[test]
    fn binance_level_gap_does_not_offset_fair() {
        let fair_native = 2700.0;
        let away = fair_native * (1.0 + 20.0 / 10_000.0);
        let ext = QuoteExtensions {
            binance_mid: Some(away),
            ..lead_ext(0.0)
        };
        let base = resolve_fair_cex(fair_native, None, QuoteExtensions::default());
        let fair = resolve_fair_cex(fair_native, None, ext);
        assert_eq!(fair, base);
    }

    #[test]
    fn binance_move_leads_fair_by_beta() {
        let base = resolve_fair_cex(2700.0, None, QuoteExtensions::default());
        let fair = resolve_fair_cex(2700.0, None, lead_ext(5.0));
        let expected = base * (1.0 + 4.0 / 10_000.0);
        assert!(((fair - expected) / expected).abs() < 1e-9, "fair={fair} expected={expected}");
    }

    #[test]
    fn binance_move_lead_is_clamped() {
        let base = resolve_fair_cex(2700.0, None, QuoteExtensions::default());
        let up = resolve_fair_cex(2700.0, None, lead_ext(50.0));
        let expected_up = base * (1.0 + 15.0 / 10_000.0);
        assert!(((up - expected_up) / expected_up).abs() < 1e-9, "up={up}");
        let down = resolve_fair_cex(2700.0, None, lead_ext(-50.0));
        let expected_down = base * (1.0 - 15.0 / 10_000.0);
        assert!(((down - expected_down) / expected_down).abs() < 1e-9, "down={down}");
    }

    #[test]
    fn binance_move_lead_unclamped_when_max_non_positive() {
        let base = resolve_fair_cex(2700.0, None, QuoteExtensions::default());
        let ext = QuoteExtensions {
            lead_max_bps: 0.0,
            ..lead_ext(50.0)
        };
        let fair = resolve_fair_cex(2700.0, None, ext);
        let expected = base * (1.0 + 40.0 / 10_000.0);
        assert!(((fair - expected) / expected).abs() < 1e-9, "fair={fair}");
    }

    #[test]
    fn no_anchor_or_zero_weight_leaves_the_fair_unchanged() {
        let base = resolve_fair_cex(2700.0, None, lead_ext(5.0));
        let off = QuoteExtensions { anchor_fair: Some(2710.0), anchor_weight: 0.0, ..lead_ext(5.0) };
        assert_eq!(resolve_fair_cex(2700.0, None, off), base);
        let none = QuoteExtensions { anchor_fair: None, anchor_weight: 1.0, ..lead_ext(5.0) };
        assert_eq!(resolve_fair_cex(2700.0, None, none), base);
    }

    #[test]
    fn full_anchor_replaces_the_book_fair_and_drops_the_move_lead() {
        // The anchor already carries the Binance move; adding the 3 s lead again would count it twice.
        let ext = QuoteExtensions { anchor_fair: Some(2710.0), anchor_weight: 1.0, ..lead_ext(5.0) };
        assert!((resolve_fair_cex(2700.0, None, ext) - 2710.0).abs() < 1e-9);
    }

    #[test]
    fn partial_anchor_blends_levels_and_scales_the_lead() {
        let ext = QuoteExtensions { anchor_fair: Some(2710.0), anchor_weight: 0.5, ..lead_ext(5.0) };
        let expected = 2705.0 * (1.0 + 0.5 * 4.0 / 10_000.0);
        assert!((resolve_fair_cex(2700.0, None, ext) - expected).abs() < 1e-9);
    }

    #[test]
    fn invalid_anchor_or_weight_is_ignored_or_clamped() {
        let base = resolve_fair_cex(2700.0, None, QuoteExtensions::default());
        for a in [0.0, -1.0, f64::NAN, f64::INFINITY] {
            let ext = QuoteExtensions { anchor_fair: Some(a), anchor_weight: 1.0, ..Default::default() };
            assert_eq!(resolve_fair_cex(2700.0, None, ext), base, "anchor {a}");
        }
        let nan_w = QuoteExtensions { anchor_fair: Some(2710.0), anchor_weight: f64::NAN, ..Default::default() };
        assert_eq!(resolve_fair_cex(2700.0, None, nan_w), base);
        let big_w = QuoteExtensions { anchor_fair: Some(2710.0), anchor_weight: 3.0, ..Default::default() };
        assert!((resolve_fair_cex(2700.0, None, big_w) - 2710.0).abs() < 1e-9);
    }

    #[test]
    fn anchored_fair_moves_binance_onto_the_delta_level() {
        assert!((anchored_fair(0.24, -5.0).unwrap() - 0.24 * (1.0 - 5.0 / 10_000.0)).abs() < 1e-15);
        assert_eq!(anchored_fair(0.0, -5.0), None);
        assert_eq!(anchored_fair(0.24, f64::NAN), None);
    }

    #[test]
    fn basis_ema_starts_at_the_first_sample_and_moves_halfway_per_half_life() {
        let mut b = BasisEma::new(120.0);
        assert_eq!(b.value_bps(), None);
        assert_eq!(b.warm_sec(5.0), 0.0);
        // Delta 10 bps below Binance.
        let v = b.update(100.0, 0.999, 1.0).unwrap();
        assert!((v + 10.0).abs() < 1e-9);
        // The basis jumps to -4 bps: one half-life later the average is halfway.
        let v = b.update(220.0, 0.9996, 1.0).unwrap();
        assert!((v + 7.0).abs() < 1e-9, "v={v}");
        assert!((b.warm_sec(230.0) - 130.0).abs() < 1e-9);
        assert_eq!(b.last_update(), Some(220.0));
    }

    /// `delta_mid / 1.0 - 1` in bps, for a Binance mid of 1.0.
    fn mid(bps: f64) -> f64 {
        1.0 + bps / 10_000.0
    }

    #[test]
    fn basis_ema_warm_up_is_the_mean_not_the_first_sample() {
        // Started while Delta trailed Binance by 7.5 bps: the first sample is -17.5, the basis -10.
        let mut b = BasisEma::new(120.0);
        b.update(0.0, mid(-17.5), 1.0);
        for i in 1..=150 {
            b.update(i as f64 * 0.4, mid(-10.0), 1.0);
        }
        // An exponential average seeded with the first sample would still read -15.3 at 60 s.
        assert!((b.value_bps().unwrap() + 10.0).abs() < 0.1, "basis {:?}", b.value_bps());
    }

    #[test]
    fn basis_ema_step_cap_and_clamp_stop_one_sample_resetting_it() {
        let mut b = BasisEma::new(120.0).with_max_step(0.8).with_clamp(5.0);
        for i in 0..1000 {
            b.update(i as f64 * 0.4, mid(-10.0), 1.0);
        }
        // One sample 6 min later, during a 7.5 bps Delta lag, and one in a +50 bps dislocation.
        b.update(400.0 + 360.0, mid(-17.5), 1.0);
        assert!((b.value_bps().unwrap() + 10.0).abs() < 0.05, "after a gap: {:?}", b.value_bps());
        b.update(760.4, mid(40.0), 1.0);
        assert!((b.value_bps().unwrap() + 10.0).abs() < 0.05, "after a spike: {:?}", b.value_bps());
    }

    #[test]
    fn basis_ema_reset_starts_the_warm_up_again() {
        let mut b = BasisEma::new(120.0);
        b.update(0.0, mid(-10.0), 1.0);
        b.update(100.0, mid(-10.0), 1.0);
        b.reset();
        assert_eq!((b.value_bps(), b.last_update(), b.warm_sec(200.0)), (None, None, 0.0));
        b.update(200.0, mid(-4.0), 1.0);
        assert!((b.value_bps().unwrap() + 4.0).abs() < 1e-9);
        assert_eq!(b.warm_sec(230.0), 30.0);
    }

    #[test]
    fn basis_ema_ignores_bad_inputs_and_clock_steps_back() {
        let mut b = BasisEma::new(120.0);
        assert_eq!(b.update(1.0, 0.0, 1.0), None);
        assert_eq!(b.update(1.0, 1.0, f64::NAN), None);
        b.update(10.0, 0.999, 1.0);
        let v = b.update(5.0, 0.9996, 1.0).unwrap(); // time went backwards: no decay, value unchanged
        assert!((v + 10.0).abs() < 1e-9);
        let mut instant = BasisEma::new(0.0); // half-life 0: follows the last sample
        instant.update(1.0, 0.999, 1.0);
        assert!((instant.update(2.0, 0.9996, 1.0).unwrap() + 4.0).abs() < 1e-9);
    }

    #[test]
    fn move_bps_zero_without_old_enough_sample() {
        let hist = [(9.0, 2700.0), (10.0, 2701.0)];
        assert_eq!(move_bps(&hist, 10.0, 3.0), 0.0);
        assert_eq!(move_bps(&[], 10.0, 3.0), 0.0);
    }

    #[test]
    fn move_bps_from_latest_sample_at_or_before_lookback() {
        let hist = [(5.0, 2690.0), (7.0, 2700.0), (8.5, 2705.0), (10.0, 2701.35)];
        let m = move_bps(&hist, 10.0, 3.0);
        assert!((m - 5.0).abs() < 1e-9, "m={m}");
    }

    #[test]
    fn move_bps_zero_on_non_positive_mid() {
        assert_eq!(move_bps(&[(7.0, 0.0), (10.0, 2701.35)], 10.0, 3.0), 0.0);
        assert_eq!(move_bps(&[(7.0, 2700.0), (10.0, -1.0)], 10.0, 3.0), 0.0);
    }
}
