//! Transaction cost analysis metrics for fills.
//!
//! Sign convention (oems-tca): negative slippage means the fill was worse than
//! arrival mid. That is `side * (arrival_mid - fill_price) / arrival_mid * 1e4`
//! with side = +1 buy / −1 sell (buy paid up or sell sold down ⇒ negative).

/// Side sign: +1 buy, -1 sell.
pub fn side_sign(side: &str) -> f64 {
    if side.eq_ignore_ascii_case("buy") || side.eq_ignore_ascii_case("b") {
        1.0
    } else {
        -1.0
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct TcaMetrics {
    pub slippage_bps: f64,
    pub quoted_half_spread_bps: f64,
    pub effective_spread_bps: f64,
    pub fee_quote: f64,
    pub fee_bps: f64,
    pub markout_1s_bps: Option<f64>,
    pub markout_5s_bps: Option<f64>,
    pub markout_30s_bps: Option<f64>,
    pub net_5s_bps: Option<f64>,
}

/// Compute TCA at fill time (markouts filled in later by snapshot backfill).
pub fn compute_tca(
    side: &str,
    fill_price: f64,
    qty: f64,
    fee: f64,
    limit_price: f64,
    arrival_mid: f64,
    mid_at_fill: f64,
) -> TcaMetrics {
    let s = side_sign(side);
    // Worse-than-mid ⇒ negative (buy fill > mid, sell fill < mid).
    let slippage_bps = if arrival_mid.abs() > f64::EPSILON {
        s * (arrival_mid - fill_price) / arrival_mid * 10_000.0
    } else {
        0.0
    };
    let quoted_half_spread_bps = if arrival_mid.abs() > f64::EPSILON {
        (limit_price - arrival_mid).abs() / arrival_mid * 10_000.0
    } else {
        0.0
    };
    // Effective spread must use mid_at_fill (not arrival_mid).
    let effective_spread_bps = if mid_at_fill.abs() > f64::EPSILON {
        2.0 * s * (fill_price - mid_at_fill) / mid_at_fill * 10_000.0
    } else {
        0.0
    };
    let notional = fill_price * qty;
    let fee_bps = if notional > 0.0 {
        fee / notional * 10_000.0
    } else {
        0.0
    };
    TcaMetrics {
        slippage_bps,
        quoted_half_spread_bps,
        effective_spread_bps,
        fee_quote: fee,
        fee_bps,
        markout_1s_bps: None,
        markout_5s_bps: None,
        markout_30s_bps: None,
        net_5s_bps: None,
    }
}

/// markout_bps(h) = side * (mid_after - arrival_mid) / arrival_mid * 10000
pub fn markout_bps(side: &str, mid_after: f64, arrival_mid: f64) -> f64 {
    if arrival_mid.abs() <= f64::EPSILON {
        return 0.0;
    }
    side_sign(side) * (mid_after - arrival_mid) / arrival_mid * 10_000.0
}

/// net_5s = effective_spread_bps - fee_bps - max(0, -markout_5s) when markout_5s is Some
pub fn net_5s_bps(
    effective_spread_bps: f64,
    fee_bps: f64,
    markout_5s: Option<f64>,
) -> Option<f64> {
    let m = markout_5s?;
    let adverse = (-m).max(0.0);
    Some(effective_spread_bps - fee_bps - adverse)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn buy_filled_worse_than_arrival_mid_negative_slippage() {
        // Buy paid above arrival mid → worse → negative slippage.
        let m = compute_tca("buy", 101.0, 1.0, 0.0, 101.0, 100.0, 100.5);
        assert!(m.slippage_bps < 0.0);
        assert!((m.slippage_bps - (-100.0)).abs() < 1e-9);
    }

    #[test]
    fn sell_filled_worse_than_arrival_mid_negative_slippage() {
        // Sell below arrival mid → worse → negative slippage.
        let m = compute_tca("sell", 99.0, 1.0, 0.0, 99.0, 100.0, 100.0);
        assert!(m.slippage_bps < 0.0);
        assert!((m.slippage_bps - (-100.0)).abs() < 1e-9);
    }

    #[test]
    fn effective_spread_uses_mid_at_fill_not_arrival() {
        let m = compute_tca("buy", 100.0, 1.0, 0.0, 99.0, 100.0, 102.0);
        let expected = 2.0 * 1.0 * (100.0 - 102.0) / 102.0 * 10_000.0;
        assert!((m.effective_spread_bps - expected).abs() < 1e-6);
        assert!(m.effective_spread_bps.abs() > 1.0);
    }

    #[test]
    fn quoted_half_spread() {
        let m = compute_tca("sell", 100.0, 1.0, 0.0, 101.0, 100.0, 100.0);
        assert!((m.quoted_half_spread_bps - 100.0).abs() < 1e-9);
    }

    #[test]
    fn fee_bps_from_notional() {
        let m = compute_tca("buy", 100.0, 2.0, 0.4, 100.0, 100.0, 100.0);
        assert!((m.fee_bps - 20.0).abs() < 1e-9);
        assert!((m.fee_quote - 0.4).abs() < 1e-9);
    }

    #[test]
    fn markout_and_net_5s() {
        let mo = markout_bps("buy", 101.0, 100.0);
        assert!((mo - 100.0).abs() < 1e-9);
        assert!((net_5s_bps(50.0, 10.0, Some(-20.0)).unwrap() - 20.0).abs() < 1e-9);
        assert!(net_5s_bps(50.0, 10.0, None).is_none());
        assert!((net_5s_bps(50.0, 10.0, Some(15.0)).unwrap() - 40.0).abs() < 1e-9);
    }
}
