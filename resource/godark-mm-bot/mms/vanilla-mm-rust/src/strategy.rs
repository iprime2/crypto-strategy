//! Market-making quote logic inspired by Avellaneda–Stoikov inventory skew,
//! Guéant–Lehalle–Tapia boundary effects, vol-adjusted spreads, and
//! adverse-selection guards (HFT Book / Hummingbot / GLFT literature).

use std::collections::VecDeque;

/// Top-of-book snapshot for microprice / imbalance skew.
#[derive(Debug, Clone, Copy, Default)]
pub struct BookTop {
    pub best_bid: f64,
    pub best_ask: f64,
    pub bid_qty: f64,
    pub ask_qty: f64,
}

impl BookTop {
    pub fn mid(&self) -> Option<f64> {
        if self.best_bid > 0.0 && self.best_ask > 0.0 && self.best_ask >= self.best_bid {
            Some((self.best_bid + self.best_ask) / 2.0)
        } else {
            None
        }
    }

    /// Stoikov-style microprice (size-weighted fair at the touch).
    pub fn microprice(&self) -> Option<f64> {
        let mid = self.mid()?;
        let bq = self.bid_qty.max(0.0);
        let aq = self.ask_qty.max(0.0);
        let denom = bq + aq;
        if denom <= 0.0 {
            return Some(mid);
        }
        Some((self.best_bid * aq + self.best_ask * bq) / denom)
    }

    /// Microprice skew vs mid in bps (positive → upward pressure).
    pub fn imbalance_skew_bps(&self) -> f64 {
        let mid = match self.mid() {
            Some(m) if m > 0.0 => m,
            _ => return 0.0,
        };
        let bq = self.bid_qty.max(0.0);
        let aq = self.ask_qty.max(0.0);
        let denom = bq + aq;
        if denom <= 0.0 {
            return 0.0;
        }
        let micro = (self.best_bid * aq + self.best_ask * bq) / denom;
        ((micro / mid) - 1.0) * 10_000.0
    }
}

/// Rolling fair-price window for realized volatility (bps per sample).
#[derive(Debug, Clone)]
pub struct VolTracker {
    window: VecDeque<f64>,
    capacity: usize,
}

impl VolTracker {
    pub fn new(capacity: usize) -> Self {
        Self {
            window: VecDeque::with_capacity(capacity.max(2)),
            capacity: capacity.max(2),
        }
    }

    pub fn push(&mut self, fair: f64) {
        if !fair.is_finite() || fair <= 0.0 {
            return;
        }
        if self.window.len() >= self.capacity {
            self.window.pop_front();
        }
        self.window.push_back(fair);
    }

    /// Realized vol of log returns, expressed in bps per loop sample (not annualized).
    pub fn vol_bps(&self) -> f64 {
        if self.window.len() < 3 {
            return 0.0;
        }
        let prices: Vec<f64> = self.window.iter().copied().collect();
        let mut returns = Vec::with_capacity(prices.len() - 1);
        for w in prices.windows(2) {
            if w[0] > 0.0 && w[1] > 0.0 {
                returns.push((w[1] / w[0]).ln());
            }
        }
        if returns.len() < 2 {
            return 0.0;
        }
        let mean = returns.iter().sum::<f64>() / returns.len() as f64;
        let var = returns
            .iter()
            .map(|r| (r - mean).powi(2))
            .sum::<f64>()
            / (returns.len() - 1) as f64;
        var.sqrt().abs() * 10_000.0
    }
}

/// Scale per-sample vol to a holding-horizon σ (Avellaneda–Stoikov holding period).
pub fn horizon_vol_bps(
    sample_vol_bps: f64,
    lookback_samples: usize,
    loop_interval_sec: f64,
    horizon_sec: f64,
) -> f64 {
    if sample_vol_bps <= 0.0 || lookback_samples == 0 || loop_interval_sec <= 0.0 {
        return sample_vol_bps.max(0.0);
    }
    let window_sec = lookback_samples as f64 * loop_interval_sec;
    if window_sec <= 0.0 {
        return sample_vol_bps;
    }
    let scale = (horizon_sec / window_sec).sqrt();
    sample_vol_bps * scale
}

/// Estimate order-arrival intensity κ from observed fill distances (Hummingbot-style).
#[derive(Debug, Clone)]
pub struct KappaEstimator {
    distances_bps: VecDeque<f64>,
    capacity: usize,
}

impl KappaEstimator {
    pub fn new(capacity: usize) -> Self {
        Self {
            distances_bps: VecDeque::with_capacity(capacity.max(4)),
            capacity: capacity.max(4),
        }
    }

    /// Record half-spread distance (fair → fill side) in bps.
    pub fn observe(&mut self, distance_bps: f64) {
        if !distance_bps.is_finite() || distance_bps <= 0.0 {
            return;
        }
        if self.distances_bps.len() >= self.capacity {
            self.distances_bps.pop_front();
        }
        self.distances_bps.push_back(distance_bps);
    }

    /// Raw κ from fill distances (before floor/cap). None if not enough samples.
    pub fn kappa_raw(&self, min_samples: usize) -> Option<f64> {
        if self.distances_bps.len() < min_samples.max(1) {
            return None;
        }
        let mut sorted: Vec<f64> = self.distances_bps.iter().copied().collect();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let median = sorted[sorted.len() / 2].max(0.5);
        Some(2.0_f64.ln() / median)
    }

    /// κ for AS spread — clamped to [floor, cap] so bad unit mismatches cannot blow spreads.
    pub fn kappa(&self, fallback: f64, min_samples: usize, floor: f64, cap: f64) -> f64 {
        let lo = floor.max(1e-6);
        let hi = cap.max(lo);
        match self.kappa_raw(min_samples) {
            Some(raw) => raw.clamp(lo, hi),
            None => fallback.clamp(lo, hi),
        }
    }

    pub fn sample_count(&self) -> usize {
        self.distances_bps.len()
    }
}

impl Default for KappaEstimator {
    fn default() -> Self {
        Self::new(32)
    }
}

/// Signed markout from MM perspective: positive = favorable, negative = adverse.
pub fn signed_fill_markout_bps(fair_at_fill: f64, fair_now: f64, bought: bool) -> f64 {
    if fair_at_fill <= 0.0 || fair_now <= 0.0 {
        return 0.0;
    }
    let markout_bps = (fair_now / fair_at_fill - 1.0) * 10_000.0;
    if bought {
        -markout_bps
    } else {
        markout_bps
    }
}

/// Tracks post-fill markout to widen spread after adverse selection.
#[derive(Debug, Clone, Default)]
pub struct MarkoutGuard {
    adverse_bps_bid: f64,
    adverse_bps_ask: f64,
    rolling_adverse: VecDeque<f64>,
    rolling_capacity: usize,
    last_horizon_markouts: Vec<(u32, f64)>,
}

impl MarkoutGuard {
    pub fn with_rolling_capacity(capacity: usize) -> Self {
        Self {
            adverse_bps_bid: 0.0,
            adverse_bps_ask: 0.0,
            rolling_adverse: VecDeque::new(),
            rolling_capacity: capacity.max(4),
            last_horizon_markouts: Vec::new(),
        }
    }

    fn decay_side(extra: &mut f64, decay: f64) {
        if *extra > 0.0 {
            *extra *= decay.clamp(0.0, 1.0);
            if *extra < 0.01 {
                *extra = 0.0;
            }
        }
    }

    pub fn on_loop_decay(&mut self, decay: f64) {
        Self::decay_side(&mut self.adverse_bps_bid, decay);
        Self::decay_side(&mut self.adverse_bps_ask, decay);
    }

    /// Apply worst signed markout across horizons (single widen step per fill).
    pub fn observe_fill_markout(
        &mut self,
        signed_markout_bps: f64,
        threshold_bps: f64,
        widen_bps: f64,
        horizon_sec: Option<u32>,
        filled_bought: bool,
        side_aware: bool,
    ) {
        if let Some(h) = horizon_sec {
            if let Some(slot) = self.last_horizon_markouts.iter_mut().find(|(hs, _)| *hs == h) {
                slot.1 = signed_markout_bps;
            } else {
                self.last_horizon_markouts.push((h, signed_markout_bps));
                self.last_horizon_markouts.sort_by_key(|(h, _)| *h);
                if self.last_horizon_markouts.len() > 8 {
                    self.last_horizon_markouts.remove(0);
                }
            }
        }
        if signed_markout_bps < -threshold_bps && widen_bps > 0.0 && horizon_sec.is_none() {
            let mag = (-signed_markout_bps).min(200.0);
            if self.rolling_adverse.len() >= self.rolling_capacity {
                self.rolling_adverse.pop_front();
            }
            self.rolling_adverse.push_back(mag);
            if side_aware {
                if filled_bought {
                    self.adverse_bps_bid = (self.adverse_bps_bid + widen_bps).min(100.0);
                } else {
                    self.adverse_bps_ask = (self.adverse_bps_ask + widen_bps).min(100.0);
                }
            } else {
                self.adverse_bps_bid = (self.adverse_bps_bid + widen_bps).min(100.0);
                self.adverse_bps_ask = (self.adverse_bps_ask + widen_bps).min(100.0);
            }
        }
    }

    /// Rolling average adverse markout magnitude (bps), for dynamic min spread.
    pub fn rolling_adverse_bps(&self) -> f64 {
        if self.rolling_adverse.is_empty() {
            return 0.0;
        }
        self.rolling_adverse.iter().sum::<f64>() / self.rolling_adverse.len() as f64
    }

    pub fn extra_spread_bid_bps(&self) -> f64 {
        self.adverse_bps_bid
    }

    pub fn extra_spread_ask_bps(&self) -> f64 {
        self.adverse_bps_ask
    }

    /// Max side extra (backward compatible with single `markout_extra_bps` metric).
    pub fn extra_spread_bps(&self) -> f64 {
        self.adverse_bps_bid.max(self.adverse_bps_ask)
    }

    pub fn last_horizon_markouts(&self) -> &[(u32, f64)] {
        &self.last_horizon_markouts
    }
}

/// GLFT-style κ from trade prices vs reference mid: λ(δ) ∝ e^{-κδ}.
pub fn estimate_kappa_from_trade_prices(trade_prices: &[f64], mid: f64) -> Option<f64> {
    if mid <= 0.0 || trade_prices.len() < 20 {
        return None;
    }
    let mut buckets: [u32; 6] = [0; 6];
    for px in trade_prices {
        if !px.is_finite() || *px <= 0.0 {
            continue;
        }
        let dist_bps = ((px - mid).abs() / mid) * 10_000.0;
        let idx = if dist_bps < 2.0 {
            0
        } else if dist_bps < 5.0 {
            1
        } else if dist_bps < 10.0 {
            2
        } else if dist_bps < 20.0 {
            3
        } else if dist_bps < 40.0 {
            4
        } else {
            5
        };
        buckets[idx] += 1;
    }
    let centers = [1.0_f64, 3.5, 7.5, 15.0, 30.0, 50.0];
    let mut xs = Vec::new();
    let mut ys = Vec::new();
    for (i, c) in centers.iter().enumerate() {
        let n = buckets[i];
        if n >= 2 {
            xs.push(*c / 10_000.0);
            ys.push((n as f64).ln());
        }
    }
    if xs.len() < 2 {
        return None;
    }
    let n = xs.len() as f64;
    let sum_x = xs.iter().sum::<f64>();
    let sum_y = ys.iter().sum::<f64>();
    let sum_xx = xs.iter().map(|x| x * x).sum::<f64>();
    let sum_xy = xs.iter().zip(ys.iter()).map(|(x, y)| x * y).sum::<f64>();
    let denom = n * sum_xx - sum_x * sum_x;
    if denom.abs() < 1e-12 {
        return None;
    }
    let slope = (n * sum_xy - sum_x * sum_y) / denom;
    if slope >= 0.0 {
        return None;
    }
    Some((-slope * 10_000.0).clamp(0.05, 50.0))
}

#[derive(Debug, Clone, Copy)]
pub struct StrategyConfig {
    pub half_spread_bps: f64,
    pub skew_bps: f64,
    pub maker_fee_bps: f64,
    pub adverse_buffer_bps: f64,
    pub inv_soft_ratio: f64,
    pub inv_spread_widen: f64,
    pub vol_spread_mult: f64,
    pub risk_aversion: f64,
    pub asym_spread_factor: f64,
    pub size_shape_factor: f64,
    pub min_half_spread_bps: f64,
    pub max_half_spread_bps: f64,
    pub fair_jump_bps: f64,
    /// GLFT-style cubic reservation shift near inventory bounds.
    pub boundary_skew_bps: f64,
    /// AS γ for spread term γσ²/2 (σ from realized vol bps).
    pub as_gamma: f64,
    /// AS order-arrival intensity κ (ln term) — fallback until fill estimator has samples.
    pub as_kappa: f64,
    /// Calibrates AS arrival term (bps scale) — tune with live fill rate.
    pub as_arrival_scale: f64,
    /// Clamp estimated κ — prevents fill-distance κ from collapsing to ~0.06 and widening to 150+ bps.
    pub kappa_floor: f64,
    pub kappa_cap: f64,
    /// Tighten spread when vol below threshold (dynamic spread, DWF-style).
    pub calm_vol_threshold_bps: f64,
    pub calm_spread_discount: f64,
    /// Extra half-spread on fair jump (toxic flow / stale quote defense).
    pub fair_jump_widen_bps: f64,
    /// Skip bid on up-jump / ask on down-jump when fair moves sharply.
    pub fair_jump_defensive: bool,
    /// Cap reservation shift from book imbalance (microprice).
    pub book_imbalance_skew_bps: f64,
    /// Stop adding inventory when |q|/max exceeds this (0 = hard cap only). E.g. 0.15 → lean early.
    pub inv_one_sided_ratio: f64,
    /// Blend microprice into fair: fair = (1-w)*mid + w*microprice (P2).
    pub microprice_weight: f64,
    /// Widen min half-spread using rolling adverse markout (P4).
    pub markout_dynamic_min: bool,
    pub markout_min_buffer_bps: f64,
    pub markout_rolling_window: usize,
    /// Weight on tape κ when available (P1); rest from fill-distance estimator.
    pub kappa_tape_blend: f64,
}

impl StrategyConfig {
    pub fn from_env(env_f64: fn(&str, f64) -> f64) -> Self {
        Self {
            half_spread_bps: env_f64("MM_HALF_SPREAD_BPS", 20.0),
            skew_bps: env_f64("MM_INVENTORY_SKEW_BPS", 30.0),
            maker_fee_bps: env_f64("MM_MAKER_FEE_BPS", 2.0),
            adverse_buffer_bps: env_f64("MM_ADVERSE_BUFFER_BPS", 8.0),
            inv_soft_ratio: env_f64("MM_INV_SOFT_RATIO", 0.8),
            inv_spread_widen: env_f64("MM_INV_SPREAD_WIDEN", 0.5),
            vol_spread_mult: env_f64("MM_VOL_SPREAD_MULT", 1.5),
            risk_aversion: env_f64("MM_RISK_AVERSION", 0.35),
            asym_spread_factor: env_f64("MM_ASYM_SPREAD_FACTOR", 0.35),
            size_shape_factor: env_f64("MM_SIZE_SHAPE_FACTOR", 0.6),
            min_half_spread_bps: env_f64("MM_MIN_HALF_SPREAD_BPS", 12.0),
            max_half_spread_bps: env_f64("MM_MAX_HALF_SPREAD_BPS", 80.0),
            fair_jump_bps: env_f64("MM_FAIR_JUMP_BPS", 12.0),
            boundary_skew_bps: env_f64("MM_BOUNDARY_SKEW_BPS", 15.0),
            as_gamma: env_f64("MM_AS_GAMMA", 0.35),
            as_kappa: env_f64("MM_AS_KAPPA", 1.5),
            as_arrival_scale: env_f64("MM_AS_ARRIVAL_SCALE", 1.0),
            kappa_floor: env_f64("MM_KAPPA_FLOOR", 0.5),
            kappa_cap: env_f64("MM_KAPPA_CAP", 5.0),
            calm_vol_threshold_bps: env_f64("MM_CALM_VOL_THRESHOLD_BPS", 8.0),
            calm_spread_discount: env_f64("MM_CALM_SPREAD_DISCOUNT", 0.15),
            fair_jump_widen_bps: env_f64("MM_FAIR_JUMP_WIDEN_BPS", 8.0),
            fair_jump_defensive: env_f64("MM_FAIR_JUMP_DEFENSIVE", 1.0) >= 0.5,
            book_imbalance_skew_bps: env_f64("MM_BOOK_IMBALANCE_SKEW_BPS", 6.0),
            inv_one_sided_ratio: env_f64("MM_INV_ONE_SIDED_RATIO", 0.35).clamp(0.0, 0.95),
            microprice_weight: env_f64("MM_MICROPRICE_WEIGHT", 0.3).clamp(0.0, 1.0),
            markout_dynamic_min: env_f64("MM_MARKOUT_DYNAMIC_MIN", 1.0) >= 0.5,
            markout_min_buffer_bps: env_f64("MM_MARKOUT_MIN_BUFFER_BPS", 2.0).max(0.0),
            markout_rolling_window: env_f64("MM_MARKOUT_ROLLING_WINDOW", 24.0).max(4.0) as usize,
            kappa_tape_blend: env_f64("MM_KAPPA_TAPE_BLEND", 0.65).clamp(0.0, 1.0),
        }
    }

    pub fn from_env_for_symbol(symbol: &str, env_f64: fn(&str, f64) -> f64) -> Self {
        let slug = symbol.split('-').next().unwrap_or(symbol).to_uppercase();
        let mut cfg = Self::from_env(env_f64);
        let one_sided_key = format!("MM_INV_ONE_SIDED_RATIO_{slug}");
        if let Some(v) = std::env::var(&one_sided_key)
            .ok()
            .and_then(|s| s.parse::<f64>().ok())
        {
            cfg.inv_one_sided_ratio = v.clamp(0.0, 0.95);
        }
        let skew_key = format!("MM_INVENTORY_SKEW_BPS_{slug}");
        if let Some(v) = std::env::var(&skew_key)
            .ok()
            .and_then(|s| s.parse::<f64>().ok())
        {
            cfg.skew_bps = v.max(0.0);
        }
        cfg
    }

    /// Fee-aware floor: round-trip maker fees + adverse buffer (HFT Book break-even).
    pub fn fee_floor_bps(&self) -> f64 {
        2.0 * self.maker_fee_bps + self.adverse_buffer_bps
    }

    /// Avellaneda–Stoikov half-spread: γσ²/2 + (2/γ)ln(1+γ/κ) in bps (Hummingbot form).
    pub fn as_half_spread_bps(&self, vol_bps: f64, kappa: f64) -> f64 {
        let gamma = self.as_gamma.max(1e-6);
        let kappa = kappa.max(1e-6);
        let sigma = vol_bps / 10_000.0;
        let vol_term = 0.5 * gamma * sigma * sigma * 10_000.0;
        let arrival = (2.0 / gamma) * (1.0 + gamma / kappa).ln() * self.as_arrival_scale;
        vol_term + arrival
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct QuotePlan {
    pub fair: f64,
    pub reservation: f64,
    pub bid: f64,
    pub ask: f64,
    pub spread_bps: f64,
    pub vol_bps: f64,
    pub vol_horizon_bps: f64,
    pub effective_kappa: f64,
    pub as_half_bps: f64,
    pub order_qty: f64,
    pub place_bid: bool,
    pub place_ask: bool,
    pub fair_jumped: bool,
}

/// Skip cancel/replace when new quotes drift less than `tol_bps` from resting ones.
pub fn quotes_within_tolerance(
    prev: Option<(f64, f64)>,
    bid: f64,
    ask: f64,
    tol_bps: f64,
) -> bool {
    let Some((pb, pa)) = prev else {
        return false;
    };
    let mid = (bid + ask) / 2.0;
    if mid <= 0.0 || tol_bps <= 0.0 {
        return false;
    }
    let bid_drift = (bid - pb).abs() / mid * 10_000.0;
    let ask_drift = (ask - pa).abs() / mid * 10_000.0;
    bid_drift <= tol_bps && ask_drift <= tol_bps
}

pub fn round_to_tick(price: f64, tick: f64) -> f64 {
    if tick <= 0.0 {
        return price;
    }
    let steps = (price / tick).round();
    (steps * tick * 1e10).round() / 1e10
}

pub fn quote_side_flags(inventory: f64, max_inv: f64, one_sided_ratio: f64) -> (bool, bool) {
    if max_inv <= 0.0 {
        return (true, true);
    }
    if inventory >= max_inv {
        return (false, true);
    }
    if inventory <= -max_inv {
        return (true, false);
    }
    let soft = max_inv * one_sided_ratio.clamp(0.0, 0.95);
    if soft > 0.0 {
        if inventory >= soft {
            return (false, true);
        }
        if inventory <= -soft {
            return (true, false);
        }
    }
    (true, true)
}

fn inventory_spread_mult(inventory: f64, max_inv: f64, soft_ratio: f64, widen: f64) -> f64 {
    if max_inv <= 0.0 {
        return 1.0;
    }
    let abs = inventory.abs();
    let soft = max_inv * soft_ratio.clamp(0.0, 1.0);
    if abs <= soft {
        return 1.0;
    }
    let t = ((abs - soft) / (max_inv - soft).max(1e-9)).clamp(0.0, 1.0);
    1.0 + t * widen.max(0.0)
}

/// AS-style reservation: shift fair against normalized inventory, vol-weighted.
fn reservation_price(
    fair: f64,
    inv_ratio: f64,
    skew_bps: f64,
    vol_bps: f64,
    risk_aversion: f64,
    boundary_skew_bps: f64,
    book_skew_bps: f64,
) -> f64 {
    let skew_component = inv_ratio * skew_bps / 10_000.0;
    // Extra vol inventory penalty (simplified γσ²q term, σ from realized vol bps)
    let vol_penalty = inv_ratio * risk_aversion * (vol_bps / 10_000.0).powi(2);
    // GLFT: boundary effects propagate inward — cubic near limits.
    let boundary = inv_ratio.powi(3) * boundary_skew_bps / 10_000.0;
    let book = book_skew_bps / 10_000.0;
    fair * (1.0 - skew_component - vol_penalty - boundary + book)
}

fn effective_order_qty(base_qty: f64, inv_ratio: f64, shape: f64) -> f64 {
    if base_qty <= 0.0 {
        return base_qty;
    }
    let shrink = 1.0 - shape.clamp(0.0, 1.0) * inv_ratio.abs();
    (base_qty * shrink.max(0.15)).max(base_qty * 0.15)
}

pub fn compute_quote(
    cfg: &StrategyConfig,
    fair: f64,
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
) -> Result<QuotePlan, String> {
    let markout_extra_bps = markout_extra_bid_bps.max(markout_extra_ask_bps);
    if fair <= 0.0 || !fair.is_finite() {
        return Err(format!("invalid fair={fair}"));
    }

    let inv_ratio = if max_inv <= 0.0 {
        0.0
    } else {
        (inventory / max_inv).clamp(-1.0, 1.0)
    };

    let fair_jump_signed_bps = last_fair
        .filter(|p| *p > 0.0)
        .map(|p| (fair / p - 1.0) * 10_000.0)
        .unwrap_or(0.0);
    let fair_jump_bps = fair_jump_signed_bps.abs();
    let fair_jumped = fair_jump_bps >= cfg.fair_jump_bps;

    let book_skew_bps = book
        .map(|b| {
            (b.imbalance_skew_bps() * cfg.book_imbalance_skew_bps / 6.0)
                .clamp(-cfg.book_imbalance_skew_bps, cfg.book_imbalance_skew_bps)
        })
        .unwrap_or(0.0);

    let as_half = cfg.as_half_spread_bps(vol_bps, kappa);
    // AS-primary spread: fee floor + min bound; MM_HALF_SPREAD_BPS is stress floor only.
    let fee_half = cfg.fee_floor_bps() / 2.0;
    let mut min_half = cfg.min_half_spread_bps;
    if cfg.markout_dynamic_min && rolling_adverse_bps > 0.0 {
        let adverse_half = rolling_adverse_bps / 2.0 + cfg.markout_min_buffer_bps / 2.0;
        min_half = min_half.max(fee_half + adverse_half);
    }
    let mut half_spread = as_half.max(fee_half).max(min_half);
    if fair_jumped {
        half_spread += cfg.fair_jump_widen_bps;
    }
    // Calm markets: tighten toward fee floor when markout is clean.
    if markout_extra_bps <= 0.0
        && vol_bps <= cfg.calm_vol_threshold_bps
        && cfg.calm_spread_discount > 0.0
    {
        let floor = (cfg.fee_floor_bps() / 2.0).max(cfg.min_half_spread_bps);
        half_spread = floor + (half_spread - floor) * (1.0 - cfg.calm_spread_discount.clamp(0.0, 0.5));
    }
    half_spread *= inventory_spread_mult(inventory, max_inv, cfg.inv_soft_ratio, cfg.inv_spread_widen);
    half_spread = half_spread.clamp(cfg.min_half_spread_bps, cfg.max_half_spread_bps);

    // Asymmetric halves: tighten side that reduces inventory (Hummingbot / AS intuition).
    let asym = cfg.asym_spread_factor.clamp(0.0, 0.9);
    let mut bid_half_bps = half_spread * (1.0 + inv_ratio.max(0.0) * asym);
    let mut ask_half_bps = half_spread * (1.0 + (-inv_ratio).max(0.0) * asym);
    bid_half_bps += markout_extra_bid_bps;
    ask_half_bps += markout_extra_ask_bps;
    if markout_extra_bid_bps > 0.0 {
        bid_half_bps = bid_half_bps.max(cfg.half_spread_bps);
    }
    if markout_extra_ask_bps > 0.0 {
        ask_half_bps = ask_half_bps.max(cfg.half_spread_bps);
    }

    let spread_bps = bid_half_bps + ask_half_bps;
    let reservation = reservation_price(
        fair,
        inv_ratio,
        cfg.skew_bps,
        vol_bps,
        cfg.risk_aversion,
        cfg.boundary_skew_bps,
        book_skew_bps,
    );

    let mut bid = round_to_tick(reservation * (1.0 - bid_half_bps / 10_000.0), tick);
    let mut ask = round_to_tick(reservation * (1.0 + ask_half_bps / 10_000.0), tick);

    if bid >= fair {
        bid = round_to_tick(fair - tick, tick);
    }
    if ask <= fair {
        ask = round_to_tick(fair + tick, tick);
    }
    if bid <= 0.0 || ask <= bid {
        return Err(format!("invalid quotes fair={fair} bid={bid} ask={ask}"));
    }

    let (mut place_bid, mut place_ask) =
        quote_side_flags(inventory, max_inv, cfg.inv_one_sided_ratio);
    if cfg.fair_jump_defensive && fair_jumped {
        if fair_jump_signed_bps > 0.0 {
            place_bid = false;
        } else if fair_jump_signed_bps < 0.0 {
            place_ask = false;
        }
    }
    let order_qty = effective_order_qty(base_qty, inv_ratio, cfg.size_shape_factor);

    Ok(QuotePlan {
        fair,
        reservation,
        bid,
        ask,
        spread_bps,
        vol_bps,
        vol_horizon_bps: vol_bps,
        effective_kappa: kappa,
        as_half_bps: as_half,
        order_qty,
        place_bid,
        place_ask,
        fair_jumped,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg() -> StrategyConfig {
        StrategyConfig {
            half_spread_bps: 20.0,
            skew_bps: 30.0,
            maker_fee_bps: 2.0,
            adverse_buffer_bps: 8.0,
            inv_soft_ratio: 0.8,
            inv_spread_widen: 0.5,
            vol_spread_mult: 1.5,
            risk_aversion: 0.35,
            asym_spread_factor: 0.35,
            size_shape_factor: 0.6,
            min_half_spread_bps: 12.0,
            max_half_spread_bps: 80.0,
            fair_jump_bps: 12.0,
            boundary_skew_bps: 15.0,
            as_gamma: 0.35,
            as_kappa: 1.5,
            as_arrival_scale: 1.0,
            kappa_floor: 0.5,
            kappa_cap: 5.0,
            calm_vol_threshold_bps: 8.0,
            calm_spread_discount: 0.15,
            fair_jump_widen_bps: 8.0,
            fair_jump_defensive: true,
            book_imbalance_skew_bps: 6.0,
            inv_one_sided_ratio: 0.35,
            microprice_weight: 0.0,
            markout_dynamic_min: false,
            markout_min_buffer_bps: 2.0,
            markout_rolling_window: 24,
            kappa_tape_blend: 0.0,
        }
    }

    #[test]
    fn vol_tracker_increases_with_moves() {
        let mut v = VolTracker::new(10);
        for p in [100.0, 100.5, 99.5, 100.2, 99.8, 100.1] {
            v.push(p);
        }
        assert!(v.vol_bps() > 0.0);
    }

    #[test]
    fn one_sided_stops_bid_when_long_soft_cap() {
        let (bid, ask) = quote_side_flags(0.8, 5.0, 0.15);
        assert!(!bid);
        assert!(ask);
        let (bid2, ask2) = quote_side_flags(-0.8, 5.0, 0.15);
        assert!(bid2);
        assert!(!ask2);
    }

    #[test]
    fn long_inventory_lowers_reservation() {
        let q0 = compute_quote(&cfg(), 1000.0, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 0.0, 0.0, 0.0, None, None).unwrap();
        let q1 = compute_quote(&cfg(), 1000.0, 0.01, 0.5, 1.0, 0.1, 0.0, 1.5, 0.0, 0.0, 0.0, None, None).unwrap();
        assert!(q1.reservation < q0.reservation);
        assert!(q1.order_qty < q0.order_qty);
    }

    #[test]
    fn high_vol_widens_spread() {
        let mut c = cfg();
        c.min_half_spread_bps = 1.0;
        c.maker_fee_bps = 0.0;
        c.adverse_buffer_bps = 0.0;
        let q0 = compute_quote(&c, 1000.0, 0.01, 0.0, 1.0, 0.1, 5.0, 1.5, 0.0, 0.0, 0.0, None, None).unwrap();
        let q1 = compute_quote(&c, 1000.0, 0.01, 0.0, 1.0, 0.1, 500.0, 1.5, 0.0, 0.0, 0.0, None, None).unwrap();
        assert!(q1.spread_bps > q0.spread_bps);
    }

    #[test]
    fn fair_jump_detected() {
        let q = compute_quote(&cfg(), 1015.0, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 0.0, 0.0, 0.0, Some(1000.0), None).unwrap();
        assert!(q.fair_jumped);
        assert!(!q.place_bid);
    }

    #[test]
    fn calm_vol_tightens_spread() {
        let mut c = cfg();
        c.min_half_spread_bps = 1.0;
        c.maker_fee_bps = 0.0;
        c.adverse_buffer_bps = 0.0;
        c.calm_spread_discount = 0.0;
        let q_wide = compute_quote(&c, 1000.0, 0.01, 0.0, 1.0, 0.1, 2.0, 1.5, 0.0, 0.0, 0.0, None, None).unwrap();
        c.calm_spread_discount = 0.25;
        let q_calm = compute_quote(&c, 1000.0, 0.01, 0.0, 1.0, 0.1, 2.0, 1.5, 0.0, 0.0, 0.0, None, None).unwrap();
        assert!(q_calm.spread_bps < q_wide.spread_bps);
    }

    #[test]
    fn book_imbalance_shifts_reservation() {
        let book = BookTop {
            best_bid: 100.0,
            best_ask: 100.2,
            bid_qty: 1.0,
            ask_qty: 10.0,
        };
        let q0 = compute_quote(&cfg(), 100.1, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 0.0, 0.0, 0.0, None, None).unwrap();
        let q1 = compute_quote(&cfg(), 100.1, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 0.0, 0.0, 0.0, None, Some(book)).unwrap();
        assert!(q1.reservation < q0.reservation);
    }

    #[test]
    fn horizon_vol_scales_with_sqrt_time() {
        let raw = 2.0;
        let h_up = horizon_vol_bps(raw, 24, 15.0, 900.0);
        let scale_up = (900.0_f64 / (24.0 * 15.0)).sqrt();
        assert!((h_up / raw - scale_up).abs() < 0.01);
        let h_down = horizon_vol_bps(raw, 96, 15.0, 900.0);
        let scale_down = (900.0_f64 / (96.0 * 15.0)).sqrt();
        assert!(h_down < raw);
        assert!((h_down / raw - scale_down).abs() < 0.01);
    }

    #[test]
    fn as_spread_can_tighten_below_stress_floor_when_calm() {
        let mut c = cfg();
        c.half_spread_bps = 20.0;
        c.min_half_spread_bps = 6.0;
        c.maker_fee_bps = 2.0;
        c.adverse_buffer_bps = 8.0;
        c.as_arrival_scale = 1.0;
        let q = compute_quote(&c, 1000.0, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 0.0, 0.0, 0.0, None, None).unwrap();
        assert!(q.spread_bps < c.half_spread_bps * 2.0);
    }

    #[test]
    fn markout_enforces_stress_spread_floor() {
        let mut c = cfg();
        c.half_spread_bps = 20.0;
        c.min_half_spread_bps = 6.0;
        c.as_arrival_scale = 1.0;
        let calm =
            compute_quote(&c, 1000.0, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 0.0, 0.0, 0.0, None, None).unwrap();
        let stressed = compute_quote(
            &c, 1000.0, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 4.0, 0.0, 0.0, None, None,
        )
        .unwrap();
        assert!(stressed.spread_bps > calm.spread_bps);
        assert!(stressed.bid < calm.bid);
    }

    #[test]
    fn kappa_estimator_tightens_with_closer_fills() {
        let mut est = KappaEstimator::new(16);
        for _ in 0..6 {
            est.observe(20.0);
        }
        let k_wide = est.kappa(1.5, 5, 0.05, 200.0);
        for _ in 0..8 {
            est.observe(5.0);
        }
        let k_tight = est.kappa(1.5, 5, 0.05, 200.0);
        assert!(k_tight > k_wide);
    }

    #[test]
    fn kappa_floor_prevents_tiny_estimates() {
        let mut est = KappaEstimator::new(16);
        for _ in 0..4 {
            est.observe(12.0);
        }
        let raw = est.kappa_raw(3).unwrap();
        assert!(raw < 0.1);
        let clamped = est.kappa(1.5, 3, 0.5, 5.0);
        assert!((clamped - 0.5).abs() < 1e-6);
    }

    #[test]
    fn dynamic_min_widens_with_rolling_adverse() {
        let mut c = cfg();
        c.min_half_spread_bps = 6.0;
        c.markout_dynamic_min = true;
        c.markout_min_buffer_bps = 0.0;
        c.maker_fee_bps = 0.0;
        c.adverse_buffer_bps = 0.0;
        let calm = compute_quote(&c, 1000.0, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 0.0, 0.0, 0.0, None, None).unwrap();
        let wide = compute_quote(&c, 1000.0, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 0.0, 24.0, 0.0, None, None).unwrap();
        assert!(wide.spread_bps > calm.spread_bps);
    }

    #[test]
    fn side_aware_markout_widens_bid_only() {
        let c = cfg();
        let base = compute_quote(&c, 1000.0, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 0.0, 0.0, 0.0, None, None).unwrap();
        let bid_toxic = compute_quote(&c, 1000.0, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 8.0, 0.0, 0.0, None, None).unwrap();
        let ask_toxic = compute_quote(&c, 1000.0, 0.01, 0.0, 1.0, 0.1, 0.0, 1.5, 0.0, 8.0, 0.0, None, None).unwrap();
        assert!(bid_toxic.bid < base.bid);
        assert!((bid_toxic.ask - base.ask).abs() < 1e-6);
        assert!(ask_toxic.ask > base.ask);
        assert!((ask_toxic.bid - base.bid).abs() < 1e-6);
    }

    #[test]
    fn tape_kappa_positive_from_synthetic_trades() {
        let mid = 1000.0;
        let mut prices = Vec::new();
        for _ in 0..200 {
            prices.push(mid * (1.0 - 0.0001));
        }
        for _ in 0..80 {
            prices.push(mid * (1.0 - 0.001));
        }
        for _ in 0..20 {
            prices.push(mid * (1.0 - 0.003));
        }
        let k = estimate_kappa_from_trade_prices(&prices, mid).expect("kappa");
        assert!(k > 0.1);
    }
}
