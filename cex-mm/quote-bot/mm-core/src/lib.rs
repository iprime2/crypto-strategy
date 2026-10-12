//! CEX market-making core: GoDark-derived quote engine + research extensions (OFI, regime, economics).

mod strategy;

pub mod economics;
pub mod eval;
pub mod fair;
pub mod ofi;
pub mod queue;
pub mod regime;
pub mod venue;

pub use strategy::*;

use serde::Serialize;

/// Extra inputs from R1–R5 (fair lead, OFI, funding, regime, toxicity floor).
#[derive(Debug, Clone, Copy, Default)]
pub struct QuoteExtensions {
    pub binance_mid: Option<f64>,
    /// Recent Binance mid change in bps (see `fair::move_bps`).
    pub binance_move_bps: f64,
    pub lead_weight: f64,
    /// Clamp on `lead_weight * binance_move_bps`; `<= 0` disables the clamp.
    pub lead_max_bps: f64,
    pub ofi_drift_bps: f64,
    pub funding_carry_bps: f64,
    pub alpha_mu_bps: f64,
    pub regime_spread_mult: f64,
}

/// Full quote path: adjust fair → GoDark `compute_quote` → apply regime on spread proxy.
pub fn compute_quote_cex(
    cfg: &StrategyConfig,
    fair_native: f64,
    tick: f64,
    inventory: f64,
    max_inv: f64,
    base_qty: f64,
    vol_bps: f64,
    kappa: f64,
    markout_extra_bid_bps: f64,
    markout_extra_ask_bps: f64,
    rolling_adverse_bps: f64,
    last_fair: Option<f64>,
    book: Option<BookTop>,
    ext: QuoteExtensions,
) -> Result<QuotePlan, String> {
    // DISM quotes the shadow-tested rule. The shadow dry-run has no venue keys, so it never sees funding
    // carry; a live bot holding inventory does. Leave it out so live and shadow quote the same fair.
    let ext = if cfg.fixed_half_spread_bps > 0.0 {
        QuoteExtensions { funding_carry_bps: 0.0, ..ext }
    } else {
        ext
    };
    let fair = fair::resolve_fair_cex(fair_native, book, ext);
    let mut plan = compute_quote(
        cfg,
        fair,
        tick,
        inventory,
        max_inv,
        base_qty,
        vol_bps,
        kappa,
        markout_extra_bid_bps,
        markout_extra_ask_bps,
        rolling_adverse_bps,
        last_fair,
        book,
    )?;
    if cfg.fixed_half_spread_bps > 0.0 {
        // DISM: the shadow-tested rule replaces the AS spread, skew and regime/alpha widening.
        // Side flags (inventory cap, fair-jump defence) and size still come from `compute_quote`.
        let (bid, ask) =
            fixed_spread_quotes(plan.fair, tick, cfg.fixed_half_spread_bps, ext.regime_spread_mult, book);
        if bid <= 0.0 || ask <= bid {
            return Err(format!("invalid fixed quotes fair={} bid={bid} ask={ask}", plan.fair));
        }
        plan.bid = bid;
        plan.ask = ask;
        plan.reservation = plan.fair;
        plan.spread_bps = (ask - bid) / plan.fair * 10_000.0;
        return Ok(plan);
    }
    if ext.regime_spread_mult > 1.0 {
        let mult = ext.regime_spread_mult;
        let mid = (plan.bid + plan.ask) / 2.0;
        let half = (plan.ask - plan.bid) / 2.0 * mult;
        plan.bid = round_to_tick(mid - half, tick);
        plan.ask = round_to_tick(mid + half, tick);
        if plan.bid >= fair {
            plan.bid = round_to_tick(fair - tick, tick);
        }
        if plan.ask <= fair {
            plan.ask = round_to_tick(fair + tick, tick);
        }
        plan.spread_bps = (plan.ask - plan.bid) / mid * 10_000.0;
    }
    let fee_half = cfg.fee_floor_bps() / 2.0;
    let min_from_alpha = (ext.alpha_mu_bps + fee_half).max(cfg.min_half_spread_bps);
    if plan.spread_bps / 2.0 < min_from_alpha {
        let mid = (plan.bid + plan.ask) / 2.0;
        let half_px = mid * min_from_alpha / 10_000.0;
        plan.bid = round_to_tick(mid - half_px, tick);
        plan.ask = round_to_tick(mid + half_px, tick);
        plan.spread_bps = min_from_alpha * 2.0;
    }
    Ok(plan)
}

#[derive(Debug, Clone, Serialize)]
pub struct MmMetrics {
    pub symbol: String,
    pub fair: f64,
    pub reservation: f64,
    pub bid: f64,
    pub ask: f64,
    pub spread_bps: f64,
    pub vol_bps: f64,
    pub inventory: f64,
    pub effective_kappa: f64,
    pub markout_extra_bid_bps: f64,
    pub markout_extra_ask_bps: f64,
    pub regime_level: u8,
    pub ofi: f64,
    pub ofi_beta: f64,
    pub alpha_mu_bps: f64,
    pub snipe_rate: f64,
    pub place_bid: bool,
    pub place_ask: bool,
    /// Binance `bookTicker` mid (reference benchmark), when connected.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub binance_mid: Option<f64>,
    /// Venue top-of-book mid `(bid+ask)/2`.
    pub venue_mid: f64,
    /// `(fair - binance_mid) / binance_mid * 1e4` when benchmark present.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lead_skew_bps: Option<f64>,
    pub rolling_adverse_bps: f64,
    /// Wall-clock time of this sample (Unix ms), for joining with recorded trades.
    pub ts_ms: i64,
    /// Venue top of book the quote was computed from (`venue_mid` is the quote mid).
    pub book_bid: f64,
    pub book_ask: f64,
    pub book_bid_qty: f64,
    pub book_ask_qty: f64,
    /// Time since the venue book feed last delivered (ms, loop resolution).
    pub book_age_ms: u64,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixed_cfg() -> StrategyConfig {
        let mut cfg = StrategyConfig::from_env(|_, default| default);
        cfg.fixed_half_spread_bps = 5.0;
        cfg.inv_one_sided_ratio = 0.0;
        cfg
    }

    fn ada_book() -> Option<BookTop> {
        Some(BookTop { best_bid: 0.2497, best_ask: 0.2503, bid_qty: 1000.0, ask_qty: 1000.0 })
    }

    #[test]
    fn fixed_mode_quotes_fair_plus_minus_half_and_ignores_inventory_skew() {
        // Long 400 of 600: the AS path would skew and widen; fixed mode quotes around fair.
        let plan = compute_quote_cex(
            &fixed_cfg(), 0.25, 1e-5, 400.0, 600.0, 200.0, 30.0, 1.5, 3.0, 3.0, 4.0, None,
            ada_book(), QuoteExtensions { regime_spread_mult: 1.0, ..Default::default() },
        )
        .unwrap();
        let (bid, ask) = fixed_spread_quotes(plan.fair, 1e-5, 5.0, 1.0, ada_book());
        assert_eq!((plan.bid, plan.ask), (bid, ask));
        assert_eq!(plan.reservation, plan.fair);
        assert!((plan.spread_bps - (ask - bid) / plan.fair * 1e4).abs() < 1e-9);
        assert!(plan.place_bid && plan.place_ask);
    }

    #[test]
    fn fixed_mode_ignores_funding_carry_like_the_shadow() {
        // The shadow dry-run has no keys, so its funding carry is always 0. A live DISM bot holding
        // inventory gets one from the venue (12 Oct: +150 bps with 2 ADA, from a units bug); it must
        // move neither the fair nor the quotes, nor trip the fair-jump defence and drop a side.
        let run = |carry: f64| {
            compute_quote_cex(
                &fixed_cfg(), 0.25, 1e-5, 2.0, 600.0, 200.0, 30.0, 1.5, 0.0, 0.0, 0.0, Some(0.25),
                ada_book(),
                QuoteExtensions { regime_spread_mult: 1.0, funding_carry_bps: carry, ..Default::default() },
            )
            .unwrap()
        };
        let (flat, carried) = (run(0.0), run(150.0));
        assert_eq!(carried.fair, flat.fair);
        assert_eq!((carried.bid, carried.ask), (flat.bid, flat.ask));
        assert!(carried.place_bid && carried.place_ask);
    }

    #[test]
    fn as_path_still_applies_funding_carry() {
        let mut cfg = fixed_cfg();
        cfg.fixed_half_spread_bps = 0.0;
        let fair = |carry: f64| {
            compute_quote_cex(
                &cfg, 0.25, 1e-5, 0.0, 600.0, 200.0, 30.0, 1.5, 0.0, 0.0, 0.0, None, ada_book(),
                QuoteExtensions { regime_spread_mult: 1.0, funding_carry_bps: carry, ..Default::default() },
            )
            .unwrap()
            .fair
        };
        assert!((fair(1.0) / fair(0.0) - 1.0 - 1e-4).abs() < 1e-12);
    }

    #[test]
    fn fixed_mode_stops_adding_at_the_inventory_cap() {
        let ext = QuoteExtensions { regime_spread_mult: 1.0, ..Default::default() };
        let long = compute_quote_cex(&fixed_cfg(), 0.25, 1e-5, 600.0, 600.0, 200.0, 5.0, 1.5, 0.0, 0.0, 0.0, None, ada_book(), ext).unwrap();
        assert!(!long.place_bid && long.place_ask);
        let short = compute_quote_cex(&fixed_cfg(), 0.25, 1e-5, -600.0, 600.0, 200.0, 5.0, 1.5, 0.0, 0.0, 0.0, None, ada_book(), ext).unwrap();
        assert!(short.place_bid && !short.place_ask);
    }

    #[test]
    fn fixed_mode_applies_the_regime_multiplier() {
        let ext = QuoteExtensions { regime_spread_mult: 1.5, ..Default::default() };
        let plan = compute_quote_cex(&fixed_cfg(), 0.25, 1e-5, 0.0, 600.0, 200.0, 5.0, 1.5, 0.0, 0.0, 0.0, None, ada_book(), ext).unwrap();
        assert_eq!((plan.bid, plan.ask), fixed_spread_quotes(plan.fair, 1e-5, 5.0, 1.5, ada_book()));
    }
}
