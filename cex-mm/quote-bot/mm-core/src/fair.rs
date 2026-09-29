use crate::{BookTop, QuoteExtensions};

/// Native microprice blend + Binance move lead + OFI/funding reservation shift (bps on price).
///
/// The lead uses the recent Binance move, never the Binance price level: the two
/// venues list different contracts, so the level gap is a biased, noisy offset.
pub fn resolve_fair_cex(fair_native: f64, book: Option<BookTop>, ext: QuoteExtensions) -> f64 {
    let mut fair = fair_native;
    if let Some(b) = book {
        if let (Some(mid), Some(micro)) = (b.mid(), b.microprice()) {
            let w = 0.3_f64;
            fair = (1.0 - w) * mid + w * micro;
        }
    }
    let mut shift_bps = ext.lead_weight * ext.binance_move_bps;
    if ext.lead_max_bps > 0.0 {
        shift_bps = shift_bps.clamp(-ext.lead_max_bps, ext.lead_max_bps);
    }
    fair *= 1.0 + (shift_bps + ext.ofi_drift_bps + ext.funding_carry_bps) / 10_000.0;
    fair
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
