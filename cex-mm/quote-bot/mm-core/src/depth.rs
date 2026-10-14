//! Depth price: the price at which cumulative size on one side of the book first reaches a threshold.
//!
//! The Binance-anchored fair needs a Delta price that our own resting quotes cannot move. In a live run our
//! quotes are the Delta touch most of the time, so the touch mid is mostly our own fair fed back
//! (`artifacts/research/2026-10-13-shadow-anchor-interim.md`). A threshold much larger than our quote skips
//! our order and the 1-4 contract dust, and lands on the real liquidity (`plans/live-basis.plan.md`).
//!
//! Exceptions, by construction (`Q` = all of our resting size on that side, which can exceed one order while a
//! cancel is unconfirmed):
//! - Pivot: when other orders priced better than the depth price already sum to between `X - Q` and `X`,
//!   adding our `Q` moves the depth price inward: at least to the level just inside it (`inner_px`), exactly to
//!   the clean book's depth price at `X - Q`, or to our own price if that is further out. On a clean (shadow)
//!   book `inner_size` tests the band directly. On a live book `inner_size` includes our own resting size, so
//!   count pivots on shadow rows or on the replay's synthetic book, and measure the move there with
//!   `side_depth_price(levels, X - Q)`.
//! - Level cap: `ob_l2` carries 15 levels a side. Our quote inside the touch adds a level and pushes the 15th
//!   out of view, so a side that reaches `X` only at the last level can turn `Thin`. The logged
//!   `depth_{bid,ask}_nlvl` (levels in the snapshot) and `depth_{bid,ask}_lvl` let a replay find those rows.

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
    /// Price of the level just inside `price`: the nearest a pivot can move it to; `None` at the touch.
    pub inner_px: Option<f64>,
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
        if cum + size >= qty {
            return Ok(SidePrice { price, level: i, inner_size: cum, inner_px: prev });
        }
        prev = Some(price);
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

/// Both sides read independently, so a thin or empty side does not hide the other one.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct DepthSides {
    pub bid: Result<SidePrice, DepthNone>,
    pub ask: Result<SidePrice, DepthNone>,
}

impl DepthSides {
    /// The depth mid when both sides are priced.
    pub fn mid(&self) -> Option<DepthMid> {
        let (bid, ask) = (self.bid.ok()?, self.ask.ok()?);
        Some(DepthMid { mid: (bid.price + ask.price) / 2.0, bid, ask })
    }
}

/// Bid and ask depth prices for thresholds `bid_qty` and `ask_qty` (contracts). `Err(Crossed)` when the best
/// bid is at or above the best ask; otherwise each side carries its own price or reason.
pub fn depth_sides(bids: &Levels, asks: &Levels, bid_qty: f64, ask_qty: f64) -> Result<DepthSides, DepthNone> {
    if let (Some(b), Some(a)) = (bids.first(), asks.first()) {
        if b.0 >= a.0 {
            return Err(DepthNone::Crossed);
        }
    }
    Ok(DepthSides {
        bid: side_depth_price(bids, bid_qty, true),
        ask: side_depth_price(asks, ask_qty, false),
    })
}

/// Why a read has no depth mid, per side: `None` when both sides are priced, else e.g. `"ask_thin"` or
/// `"bid_empty_side,ask_thin"`.
pub fn side_reasons(sides: &DepthSides) -> Option<String> {
    let parts: Vec<String> = [("bid", sides.bid), ("ask", sides.ask)]
        .iter()
        .filter_map(|(name, r)| r.err().map(|e| format!("{name}_{}", e.as_str())))
        .collect();
    (!parts.is_empty()).then(|| parts.join(","))
}

/// Mid of the bid and ask depth prices; the first failing side's reason otherwise.
pub fn depth_mid(bids: &Levels, asks: &Levels, bid_qty: f64, ask_qty: f64) -> Result<DepthMid, DepthNone> {
    let sides = depth_sides(bids, asks, bid_qty, ask_qty)?;
    sides.bid?;
    sides.ask?;
    Ok(sides.mid().expect("both sides priced"))
}

/// Contracts for a threshold of `base_qty` base units (the units `MM_ORDER_QTY` uses), for a contract of
/// `contract_value` base units. A fixed size, so nothing our quotes move can shift it. `None` on bad input.
pub fn contracts_for_qty(base_qty: f64, contract_value: f64) -> Option<f64> {
    (base_qty.is_finite() && base_qty > 0.0 && contract_value.is_finite() && contract_value > 0.0)
        .then(|| base_qty / contract_value)
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
        assert_eq!(d.bid, SidePrice { price: 0.23200, level: 3, inner_size: 5.0, inner_px: Some(0.23201) });
        assert_eq!(d.ask, SidePrice { price: 0.23230, level: 0, inner_size: 0.0, inner_px: None });
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
        // price moves in to the others' 1,850 level (the clean book's inner_px). On the clean book the
        // others' inner_size (1,850) is in [X - Q, X): that is how a replay counts the case. On the live
        // book inner_size is our 200.
        let others = vec![(0.23210, 1_850.0), (0.23200, 47_081.0)];
        let mut with_us = vec![(0.23215, 200.0)];
        with_us.extend(others.clone());
        let clean = side_depth_price(&others, 2_000.0, true).unwrap();
        assert_eq!((clean.price, clean.inner_size, clean.inner_px), (0.23200, 1_850.0, Some(0.23210)));
        let moved = side_depth_price(&with_us, 2_000.0, true).unwrap();
        assert_eq!((moved.price, moved.level, moved.inner_size), (0.23210, 1, 200.0));
        assert_eq!(moved.price, clean.inner_px.unwrap());
    }

    #[test]
    fn a_pivot_past_dust_moves_further_than_the_inner_level() {
        // X = 10,000, Q = 200. Others hold 9,810 then 2 contracts of dust inside the ladder: the clean inner
        // size (9,812) is in the band, and our 200 moves the price past the dust level (inner_px) to the
        // clean book's depth price at X - Q.
        let others = vec![(0.23212, 9_810.0), (0.23210, 2.0), (0.23200, 47_081.0)];
        let clean = side_depth_price(&others, 10_000.0, true).unwrap();
        assert_eq!((clean.price, clean.inner_size, clean.inner_px), (0.23200, 9_812.0, Some(0.23210)));
        let mut live = vec![(0.23220, 200.0)];
        live.extend(others.clone());
        let moved = side_depth_price(&live, 10_000.0, true).unwrap();
        assert_eq!(moved.price, 0.23212);
        assert_eq!(moved.price, side_depth_price(&others, 10_000.0 - 200.0, true).unwrap().price);
    }

    #[test]
    fn the_level_cap_exception_our_level_pushes_the_last_one_out() {
        // Others reach X only at level 15 of 15; our quote inside the touch adds a level and the venue's
        // 15-level snapshot drops the last one, so the side turns Thin.
        let others: Vec<(f64, f64)> = (0..15).map(|i| (1.0 - 0.0001 * i as f64, if i == 14 { 1_000.0 } else { 100.0 })).collect();
        assert_eq!(side_depth_price(&others, 2_000.0, true).unwrap().level, 14);
        let mut with_us = vec![(1.0005, 200.0)];
        with_us.extend(others);
        with_us.truncate(15);
        assert_eq!(side_depth_price(&with_us, 2_000.0, true), Err(DepthNone::Thin));
    }

    #[test]
    fn each_side_is_read_on_its_own() {
        let sides = depth_sides(&ada_bids(), &ada_asks(), 8_600.0, 1e9).unwrap();
        assert_eq!(sides.bid.unwrap().price, 0.23200);
        assert_eq!(sides.ask, Err(DepthNone::Thin));
        assert_eq!(sides.mid(), None);
        assert_eq!(depth_sides(&[(0.24, 5.0)], &[(0.23, 5.0)], 1.0, 1.0), Err(DepthNone::Crossed));
        let both = depth_sides(&ada_bids(), &ada_asks(), 8_600.0, 8_600.0).unwrap();
        assert_eq!(both.mid().unwrap(), depth_mid(&ada_bids(), &ada_asks(), 8_600.0, 8_600.0).unwrap());
        assert_eq!(side_reasons(&both), None);
        assert_eq!(side_reasons(&sides).as_deref(), Some("ask_thin"));
        let neither = depth_sides(&[], &ada_asks(), 8_600.0, 1e9).unwrap();
        assert_eq!(side_reasons(&neither).as_deref(), Some("bid_empty_side,ask_thin"));
    }

    #[test]
    fn reaching_the_threshold_exactly_stops_at_that_level() {
        let levels = [(10.0, 1.0), (9.0, 1.0), (8.0, 5.0)];
        assert_eq!(
            side_depth_price(&levels, 2.0, true).unwrap(),
            SidePrice { price: 9.0, level: 1, inner_size: 1.0, inner_px: Some(10.0) }
        );
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
    fn base_units_to_contracts() {
        assert_eq!(contracts_for_qty(10_000.0, 1.0), Some(10_000.0)); // ADA, 1 ADA a contract
        assert_eq!(contracts_for_qty(100_000.0, 100.0), Some(1_000.0)); // KITE, 100 KITE a contract
        assert_eq!(contracts_for_qty(0.0, 1.0), None);
        assert_eq!(contracts_for_qty(-1.0, 1.0), None);
        assert_eq!(contracts_for_qty(f64::NAN, 1.0), None);
        assert_eq!(contracts_for_qty(10_000.0, 0.0), None);
    }
}
