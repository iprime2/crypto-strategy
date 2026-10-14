//! Depth price: the price at which cumulative size on one side of the book first reaches a threshold.
//!
//! The Binance-anchored fair needs a Delta price that our own resting quotes cannot move. In a live run our
//! quotes are the Delta touch most of the time, so the touch mid is mostly our own fair fed back
//! (`artifacts/research/2026-10-13-shadow-anchor-interim.md`). A threshold much larger than our quote skips
//! our order and the 1-4 contract dust, and lands on the real liquidity (`plans/live-basis.plan.md`).
//!
//! Exception, by construction: when other orders priced better than the depth price already sum to between
//! `X - Q` and `X`, adding our quote of size `Q` moves the depth price inward. `inner_size` lets a replay
//! count how often that happens.

/// One side of the book, best level first: `(price, size)`. Sizes are in contracts.
pub type Levels = [(f64, f64)];

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct SidePrice {
    /// Price of the level where cumulative size first reaches the threshold.
    pub price: f64,
    /// Index of that level (0 = the touch).
    pub level: usize,
    /// Size priced better than `price`: the sum of the levels before it.
    pub inner_size: f64,
}

/// Why a depth price could not be read.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DepthNone {
    EmptySide,
    /// Cumulative size never reached the threshold within the levels we have.
    Thin,
    /// The best bid is at or above the best ask.
    Crossed,
    /// Unsorted levels, a non-positive or non-finite price or size, or a non-positive threshold.
    Invalid,
}

impl DepthNone {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::EmptySide => "empty_side",
            Self::Thin => "thin",
            Self::Crossed => "crossed",
            Self::Invalid => "invalid",
        }
    }
}

/// Depth price on one side. `is_bid` sets the sort order the levels must follow (bids descending, asks
/// ascending).
pub fn side_depth_price(levels: &Levels, qty: f64, is_bid: bool) -> Result<SidePrice, DepthNone> {
    if !(qty.is_finite() && qty > 0.0) {
        return Err(DepthNone::Invalid);
    }
    if levels.is_empty() {
        return Err(DepthNone::EmptySide);
    }
    let mut cum = 0.0;
    let mut prev: Option<f64> = None;
    for (i, &(price, size)) in levels.iter().enumerate() {
        if !(price.is_finite() && price > 0.0 && size.is_finite() && size > 0.0) {
            return Err(DepthNone::Invalid);
        }
        if let Some(p) = prev {
            let ordered = if is_bid { price < p } else { price > p };
            if !ordered {
                return Err(DepthNone::Invalid);
            }
        }
        prev = Some(price);
        if cum + size >= qty {
            return Ok(SidePrice { price, level: i, inner_size: cum });
        }
        cum += size;
    }
    Err(DepthNone::Thin)
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct DepthMid {
    pub mid: f64,
    pub bid: SidePrice,
    pub ask: SidePrice,
}

/// Mid of the bid and ask depth prices for thresholds `bid_qty` and `ask_qty` (contracts).
pub fn depth_mid(bids: &Levels, asks: &Levels, bid_qty: f64, ask_qty: f64) -> Result<DepthMid, DepthNone> {
    if let (Some(b), Some(a)) = (bids.first(), asks.first()) {
        if b.0 >= a.0 {
            return Err(DepthNone::Crossed);
        }
    }
    let bid = side_depth_price(bids, bid_qty, true)?;
    let ask = side_depth_price(asks, ask_qty, false)?;
    Ok(DepthMid { mid: (bid.price + ask.price) / 2.0, bid, ask })
}

/// Contracts worth `notional` at `price`, for a contract of `contract_value` base units. `None` on bad input.
pub fn contracts_for_notional(notional: f64, price: f64, contract_value: f64) -> Option<f64> {
    let per_contract = price * contract_value;
    (notional.is_finite() && notional > 0.0 && per_contract.is_finite() && per_contract > 0.0)
        .then(|| notional / per_contract)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// ADA, 14 Oct 2026 (ob_l2 probe): 1-2 contract dust inside a 47k-90k ladder on a 0.0002 grid.
    fn ada_bids() -> Vec<(f64, f64)> {
        vec![(0.23207, 2.0), (0.23206, 1.0), (0.23201, 2.0), (0.23200, 47_081.0), (0.23180, 63_846.0)]
    }
    fn ada_asks() -> Vec<(f64, f64)> {
        vec![(0.23230, 65_594.0), (0.23250, 52_216.0)]
    }

    #[test]
    fn skips_dust_and_lands_on_the_ladder() {
        let d = depth_mid(&ada_bids(), &ada_asks(), 8_600.0, 8_600.0).unwrap();
        assert_eq!(d.bid, SidePrice { price: 0.23200, level: 3, inner_size: 5.0 });
        assert_eq!(d.ask, SidePrice { price: 0.23230, level: 0, inner_size: 0.0 });
        assert!((d.mid - 0.23215).abs() < 1e-12);
    }

    #[test]
    fn our_quote_inside_the_spread_does_not_move_it() {
        // Our 200-contract bid one tick under the ask: the touch moves to us, the depth price does not.
        let mut bids = vec![(0.23229, 200.0)];
        bids.extend(ada_bids());
        let with_us = depth_mid(&bids, &ada_asks(), 8_600.0, 8_600.0).unwrap();
        let without = depth_mid(&ada_bids(), &ada_asks(), 8_600.0, 8_600.0).unwrap();
        assert_eq!(with_us.mid, without.mid);
        assert_eq!(with_us.bid.inner_size, 205.0);
    }

    #[test]
    fn the_known_exception_others_inside_between_x_minus_q_and_x() {
        // Others hold 1,850 inside; our 200 takes the cumulative to 2,050, past X = 2,000, so the depth
        // price becomes our price. inner_size (1,850) is what a replay uses to count this case.
        let others = vec![(0.23210, 1_850.0), (0.23200, 47_081.0)];
        let mut with_us = vec![(0.23215, 200.0)];
        with_us.extend(others.clone());
        assert_eq!(side_depth_price(&others, 2_000.0, true).unwrap().price, 0.23200);
        let moved = side_depth_price(&with_us, 2_000.0, true).unwrap();
        assert_eq!((moved.price, moved.level, moved.inner_size), (0.23210, 1, 200.0));
    }

    #[test]
    fn reaching_the_threshold_exactly_stops_at_that_level() {
        let levels = [(10.0, 1.0), (9.0, 1.0), (8.0, 5.0)];
        assert_eq!(side_depth_price(&levels, 2.0, true).unwrap(), SidePrice { price: 9.0, level: 1, inner_size: 1.0 });
    }

    #[test]
    fn says_why_when_it_cannot_price_a_side() {
        let asks = ada_asks();
        assert_eq!(depth_mid(&[], &asks, 10.0, 10.0), Err(DepthNone::EmptySide));
        assert_eq!(depth_mid(&ada_bids(), &asks, 1e9, 10.0), Err(DepthNone::Thin));
        assert_eq!(depth_mid(&[(0.24, 5.0)], &[(0.23, 5.0)], 1.0, 1.0), Err(DepthNone::Crossed));
        // Unsorted, zero size, NaN, non-positive threshold.
        assert_eq!(side_depth_price(&[(1.0, 1.0), (2.0, 1.0)], 5.0, true), Err(DepthNone::Invalid));
        assert_eq!(side_depth_price(&[(2.0, 1.0), (1.0, 1.0)], 5.0, false), Err(DepthNone::Invalid));
        assert_eq!(side_depth_price(&[(1.0, 0.0)], 5.0, true), Err(DepthNone::Invalid));
        assert_eq!(side_depth_price(&[(f64::NAN, 1.0)], 5.0, true), Err(DepthNone::Invalid));
        assert_eq!(side_depth_price(&[(1.0, 1.0)], 0.0, true), Err(DepthNone::Invalid));
        assert_eq!(DepthNone::Thin.as_str(), "thin");
    }

    #[test]
    fn notional_to_contracts() {
        // ADA: $2,000 at 0.2329, 1 ADA per contract.
        assert!((contracts_for_notional(2_000.0, 0.2329, 1.0).unwrap() - 8_587.37).abs() < 0.01);
        // KITE-like: 100 per contract at $0.08 is $8 a contract.
        assert!((contracts_for_notional(2_000.0, 0.08, 100.0).unwrap() - 250.0).abs() < 1e-9);
        assert_eq!(contracts_for_notional(2_000.0, 0.0, 1.0), None);
        assert_eq!(contracts_for_notional(-1.0, 0.23, 1.0), None);
        assert_eq!(contracts_for_notional(f64::NAN, 0.23, 1.0), None);
    }
}
