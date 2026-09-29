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
}
