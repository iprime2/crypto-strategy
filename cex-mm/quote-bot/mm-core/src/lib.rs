//! CEX market-making core: GoDark-derived quote engine + research extensions (OFI, regime, economics).

mod strategy;

pub mod depth;
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
    /// Binance mid moved onto Delta's level by the basis (`fair::anchored_fair`), when fresh.
    pub anchor_fair: Option<f64>,
    /// Weight of `anchor_fair` against the Delta book fair, 0..=1 (`MM_FAIR_ANCHOR_WEIGHT`).
    pub anchor_weight: f64,
}

/// The fair `compute_quote_cex` quotes around. Fixed mode (DISM) leaves funding carry out: its shadow
/// gate was measured without it, and live and shadow must quote the same fair.
pub fn quote_fair(cfg: &StrategyConfig, fair_native: f64, book: Option<BookTop>, ext: QuoteExtensions) -> f64 {
    let ext = if cfg.fixed_half_spread_bps > 0.0 {
        QuoteExtensions { funding_carry_bps: 0.0, ..ext }
    } else {
        ext
    };
    fair::resolve_fair_cex(fair_native, book, ext)
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
    let fair = quote_fair(cfg, fair_native, book, ext);
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
    /// The fair without the Binance anchor (Delta book + move lead), so one run can compare both.
    pub fair_delta: f64,
    /// Delta-over-Binance basis average in bps (`fair::BasisEma`), once it has a sample.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub basis_bps: Option<f64>,
    /// True when this loop's fair used the Binance anchor (`MM_FAIR_ANCHOR_WEIGHT` > 0 and all inputs fresh).
    pub anchored: bool,
    /// Time since the last Binance bookTicker message (ms), once one arrived.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub binance_age_ms: Option<u64>,
    /// Delta mark price and spot index from the ticker poller (Delta only), and that snapshot's age (ms).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mark_price: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub spot_price: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ticker_age_ms: Option<u64>,
    /// Private fills feed (runs with keys): the venue confirms the subscription on the current connection,
    /// and the fills it has delivered since start.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fills_feed_up: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub fills_feed_fills: Option<u64>,
    /// Binance best bid and ask with their sizes (bookTicker `b`, `a`, `B`, `A`), for a microprice reference.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub binance_bid: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub binance_ask: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub binance_bid_qty: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub binance_ask_qty: Option<f64>,
    /// Delta depth book (`depth::depth_sides`, from `ob_l2`): the price where cumulative size reaches `depth_qty`
    /// contracts (`MM_BASIS_DEPTH_QTY` base units) per side, and the mid of the two. Per side: the depth price,
    /// its level (0 = touch), the size priced better, the price of the level just inside (the nearest a pivot
    /// can move it to; see `depth.rs`), and how many levels the snapshot had. Each side is logged when priced,
    /// even if the other is not.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_mid: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_bid_px: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_ask_px: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_bid_lvl: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_ask_lvl: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_bid_inner: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_ask_inner: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_bid_inner_px: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_ask_inner_px: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_bid_nlvl: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_ask_nlvl: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_qty: Option<f64>,
    /// Age of the last ob_l2 snapshot on the local clock (ms), and its venue timestamp (µs): the key to join a
    /// row to the recorded book file (`delta_<env>_book_<day>.jsonl`) on one clock.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_age_ms: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_ts_us: Option<i64>,
    /// Why there is no depth mid this loop: no_feed, stale, invalid (threshold), crossed, or per side, e.g.
    /// `ask_thin` or `bid_empty_side,ask_thin`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub depth_none: Option<String>,
    /// Where the basis average reads Delta's price (`MM_BASIS_SOURCE`: book or depth), whether it took a
    /// sample this loop, and, with an anchor weight above 0, why the anchor is off this loop
    /// (binance_stale, basis_stale: the average aged past `MM_BASIS_MAX_AGE_SEC` and restarted, no_source,
    /// basis_warming). These are the loop's decisions; `depth_age_ms` and `binance_age_ms` are stamped at
    /// log time and are diagnostics only.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub basis_src: Option<&'static str>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub basis_updated: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub anchor_off_reason: Option<&'static str>,
    /// The basis average's own clock (seconds on the loop's monotonic clock) and sample count, so a replay
    /// can rebuild it exactly.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub basis_t: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub basis_n: Option<u64>,
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
        // A dry-run (the shadow) is given a funding carry of 0. A live DISM bot holding inventory gets
        // one from the venue (12 Oct: +150 bps with 2 ADA, from a units bug); it must move neither the
        // fair nor the quotes, nor trip the fair-jump defence and drop a side.
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
    fn fixed_mode_quotes_around_the_anchor_and_reports_the_unanchored_fair() {
        let ext = QuoteExtensions {
            regime_spread_mult: 1.0,
            anchor_fair: Some(0.2501),
            anchor_weight: 1.0,
            ..Default::default()
        };
        let plan = compute_quote_cex(
            &fixed_cfg(), 0.25, 1e-5, 0.0, 600.0, 200.0, 30.0, 1.5, 0.0, 0.0, 0.0, Some(0.2501), ada_book(), ext,
        )
        .unwrap();
        assert!((plan.fair - 0.2501).abs() < 1e-12);
        let unanchored = quote_fair(&fixed_cfg(), 0.25, ada_book(), QuoteExtensions { anchor_fair: None, ..ext });
        assert!((unanchored - quote_fair(&fixed_cfg(), 0.25, ada_book(), QuoteExtensions::default())).abs() < 1e-12);
        assert!(plan.place_bid && plan.place_ask);
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
