use std::time::{Duration, Instant};

/// Rate budget for Bybit order ops (~70% of 10/s).
pub struct OrderRateBudget {
    window: Vec<Instant>,
    max_per_sec: usize,
}

impl Default for OrderRateBudget {
    fn default() -> Self {
        Self {
            window: Vec::new(),
            max_per_sec: 7,
        }
    }
}

impl OrderRateBudget {
    pub fn allow(&mut self) -> bool {
        let now = Instant::now();
        self.window.retain(|t| now.duration_since(*t) < Duration::from_secs(1));
        if self.window.len() >= self.max_per_sec {
            return false;
        }
        self.window.push(now);
        true
    }
}

#[derive(Debug, Clone, Default)]
pub struct LiveQuotes {
    pub bid: Option<f64>,
    pub ask: Option<f64>,
    pub bid_link: Option<String>,
    pub ask_link: Option<String>,
    pub bid_id: Option<u64>,
    pub ask_id: Option<u64>,
    /// Contracts of the resting order not yet filled, as far as the fills feed has told us. Set at the place or
    /// edit, decremented by fills; None when not known, and then fills never settle the side.
    pub bid_left: Option<i64>,
    pub ask_left: Option<i64>,
}

/// One of our fills from the private feed, sent to the loop of the symbol that placed the order.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FillEvent {
    pub order_id: u64,
    pub contracts: i64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum QuoteSide {
    Bid,
    Ask,
}

/// What a fill did to the tracked quotes.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FillApplied {
    /// Part of a resting quote filled; `left` contracts still rest (None: its size is not tracked).
    Partial { side: QuoteSide, left: Option<i64> },
    /// The fills reached the tracked size, so the quote has most likely filled completely. It stays tracked
    /// until the venue says the order is closed (`LiveQuotes::settle`).
    Filled { side: QuoteSide },
    /// Not one of the resting quotes (an order already replaced or cancelled, a reduce-only exit): ignored.
    Unknown,
}

/// Contracts the venue books for `qty_base`, rounded as `mm-delta` sends it; None below one contract.
pub fn contracts_of(qty_base: f64, contract_value: f64) -> Option<i64> {
    if contract_value <= 0.0 || !qty_base.is_finite() {
        return None;
    }
    let n = (qty_base / contract_value).round();
    (n >= 1.0).then_some(n as i64)
}

/// Tracked remainder after an edit to `new` contracts. Whether Delta's edit size is the order's total or its
/// unfilled size is not verified, so a quote that already part-filled keeps the smaller figure: a low guess
/// only costs a venue check once the fills reach it, a high one would leave a filled side unquoted.
pub fn left_after_edit(before: Option<i64>, new: Option<i64>) -> Option<i64> {
    match (before, new) {
        (Some(b), Some(n)) if b > 0 => Some(b.min(n)),
        _ => new,
    }
}

/// Whether the venue's order state means the order no longer rests.
pub fn venue_says_gone(state: &str) -> bool {
    matches!(state.to_ascii_lowercase().as_str(), "closed" | "cancelled" | "canceled")
}

/// Whether a resting quote is gone after a cancel attempt: the cancel succeeded, or it failed and the venue
/// reports the order closed or cancelled (it filled meanwhile, or was already cancelled). An open or pending
/// order, or a state that could not be read, stays tracked: forgetting it would leave an order resting that
/// the loop no longer knows about, and it would place a second one beside it.
pub fn gone_after_cancel(cancel_ok: bool, venue_state: Option<&str>) -> bool {
    cancel_ok || venue_state.is_some_and(venue_says_gone)
}

impl LiveQuotes {
    pub fn clear(&mut self) {
        *self = Self::default();
    }

    pub fn clear_bid(&mut self) {
        self.bid = None;
        self.bid_id = None;
        self.bid_left = None;
    }

    pub fn clear_ask(&mut self) {
        self.ask = None;
        self.ask_id = None;
        self.ask_left = None;
    }

    pub fn clear_side(&mut self, side: QuoteSide) {
        match side {
            QuoteSide::Bid => self.clear_bid(),
            QuoteSide::Ask => self.clear_ask(),
        }
    }

    /// Books one fill against the resting quote it belongs to. Fills of any other order change nothing.
    pub fn apply_fill(&mut self, ev: FillEvent) -> FillApplied {
        if ev.contracts <= 0 {
            return FillApplied::Unknown;
        }
        let side = if self.bid_id == Some(ev.order_id) {
            QuoteSide::Bid
        } else if self.ask_id == Some(ev.order_id) {
            QuoteSide::Ask
        } else {
            return FillApplied::Unknown;
        };
        let left = match side {
            QuoteSide::Bid => &mut self.bid_left,
            QuoteSide::Ask => &mut self.ask_left,
        };
        let Some(n) = left.as_mut() else {
            return FillApplied::Partial { side, left: None };
        };
        *n -= ev.contracts;
        if *n > 0 {
            FillApplied::Partial { side, left: Some(*n) }
        } else {
            FillApplied::Filled { side }
        }
    }

    /// Settles a quote the fills say is done, with the venue's `(state, unfilled)` for that order. Closed or
    /// cancelled clears the side, so the loop quotes it again; still resting resyncs the remainder to the venue's
    /// unfilled size; no answer leaves it tracked (the requote path asks again before it forgets it). A side
    /// that has moved on to another order is not touched. Returns whether the side was cleared.
    pub fn settle(&mut self, side: QuoteSide, order_id: u64, venue: Option<(&str, i64)>) -> bool {
        let (id, left) = match side {
            QuoteSide::Bid => (self.bid_id, &mut self.bid_left),
            QuoteSide::Ask => (self.ask_id, &mut self.ask_left),
        };
        if id != Some(order_id) {
            return false;
        }
        match venue {
            Some((state, _)) if venue_says_gone(state) => {
                self.clear_side(side);
                true
            }
            Some((_, unfilled)) if unfilled > 0 => {
                *left = Some(unfilled);
                false
            }
            _ => false,
        }
    }

    /// A side has a resting order we cannot address by id, so only cancel-all is safe.
    pub fn has_untracked(&self) -> bool {
        (self.bid.is_some() && self.bid_id.is_none()) || (self.ask.is_some() && self.ask_id.is_none())
    }
}

pub struct OmsState {
    pub live: LiveQuotes,
    pub budget: OrderRateBudget,
}

impl Default for OmsState {
    fn default() -> Self {
        Self {
            live: LiveQuotes::default(),
            budget: OrderRateBudget::default(),
        }
    }
}

impl OmsState {
    pub fn needs_update(&self, bid: f64, ask: f64, tol_bps: f64) -> (bool, bool) {
        let bid_ok = self
            .live
            .bid
            .map(|p| (p - bid).abs() / bid * 10_000.0 <= tol_bps)
            .unwrap_or(false);
        let ask_ok = self
            .live
            .ask
            .map(|p| (p - ask).abs() / ask * 10_000.0 <= tol_bps)
            .unwrap_or(false);
        (!bid_ok, !ask_ok)
    }

    /// `needs_update`, plus: a side the plan switches off (inventory cap, fair-jump defence) that still has
    /// a resting order always needs an update, so the loop cancels it however close its price is.
    pub fn needs_update_sides(&self, bid: f64, ask: f64, place_bid: bool, place_ask: bool, tol_bps: f64) -> (bool, bool) {
        let (need_bid, need_ask) = self.needs_update(bid, ask, tol_bps);
        (
            need_bid || (!place_bid && self.live.bid.is_some()),
            need_ask || (!place_ask && self.live.ask.is_some()),
        )
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_side_switched_off_is_pulled_however_close_its_price() {
        let mut oms = OmsState::default();
        oms.live.bid = Some(0.2400);
        oms.live.bid_id = Some(1);
        oms.live.ask = Some(0.2412);
        oms.live.ask_id = Some(2);
        // Same prices, both sides wanted: nothing to do.
        assert_eq!(oms.needs_update_sides(0.2400, 0.2412, true, true, 3.0), (false, false));
        // The inventory cap turns the ask off: it must be cancelled even though its price did not move
        // (13 Oct 2026: a resting ask kept filling past the 600-contract cap).
        assert_eq!(oms.needs_update_sides(0.2400, 0.2412, true, false, 3.0), (false, true));
        assert_eq!(oms.needs_update_sides(0.2400, 0.2412, false, true, 3.0), (true, false));
        // Nothing resting on a side that is off: nothing to pull.
        oms.live.clear_ask();
        assert_eq!(oms.needs_update_sides(0.2400, 0.2412, true, false, 3.0), (false, true));
    }

    fn resting(bid_left: i64, ask_left: i64) -> LiveQuotes {
        let mut live = LiveQuotes::default();
        live.bid = Some(0.2400);
        live.bid_id = Some(11);
        live.bid_left = Some(bid_left);
        live.ask = Some(0.2412);
        live.ask_id = Some(12);
        live.ask_left = Some(ask_left);
        live
    }

    #[test]
    fn a_partial_fill_decrements_the_side_and_a_full_one_waits_for_the_venue() {
        let mut live = resting(200, 200);
        let ev = |order_id, contracts| FillEvent { order_id, contracts };
        assert_eq!(live.apply_fill(ev(11, 50)), FillApplied::Partial { side: QuoteSide::Bid, left: Some(150) });
        assert_eq!((live.bid, live.bid_id, live.bid_left), (Some(0.2400), Some(11), Some(150)));
        // The rest fills: the quote looks done, but it stays tracked until the venue says it is closed.
        assert_eq!(live.apply_fill(ev(11, 150)), FillApplied::Filled { side: QuoteSide::Bid });
        assert_eq!((live.bid, live.bid_id), (Some(0.2400), Some(11)));
        assert!(live.settle(QuoteSide::Bid, 11, Some(("closed", 0))));
        assert_eq!((live.bid, live.bid_id, live.bid_left), (None, None, None));
        // The ask is untouched, and fills it independently.
        assert_eq!((live.ask_id, live.ask_left), (Some(12), Some(200)));
        assert_eq!(live.apply_fill(ev(12, 260)), FillApplied::Filled { side: QuoteSide::Ask });
        assert!(live.settle(QuoteSide::Ask, 12, Some(("closed", 0))));
        assert!(live.ask.is_none() && live.ask_id.is_none());
    }

    #[test]
    fn the_venue_decides_whether_a_filled_looking_quote_is_gone() {
        // Still open (a fill counted twice, or the edit kept more size than tracked): resync, keep quoting it.
        let mut live = resting(50, 200);
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 50 }), FillApplied::Filled { side: QuoteSide::Bid });
        assert!(!live.settle(QuoteSide::Bid, 11, Some(("open", 120))));
        assert_eq!((live.bid_id, live.bid_left), (Some(11), Some(120)));
        // No answer from the venue: keep it tracked rather than risk a second quote beside it.
        assert!(!live.settle(QuoteSide::Bid, 11, None));
        assert_eq!(live.bid_id, Some(11));
        // A cancelled order is gone too.
        assert!(live.settle(QuoteSide::Bid, 11, Some(("cancelled", 120))));
        assert!(live.bid_id.is_none());
        // The side moved on to another order before the answer came: nothing changes.
        live.bid = Some(0.2401);
        live.bid_id = Some(21);
        live.bid_left = Some(200);
        assert!(!live.settle(QuoteSide::Bid, 11, Some(("closed", 0))));
        assert_eq!((live.bid_id, live.bid_left), (Some(21), Some(200)));
    }

    #[test]
    fn fills_of_replaced_unknown_or_untracked_orders_change_nothing() {
        let mut live = resting(200, 200);
        let before = (live.bid, live.bid_id, live.bid_left, live.ask, live.ask_id, live.ask_left);
        // A replaced order (cancelled, then a fill that was already in flight), a reduce-only exit, anything else.
        for id in [10, 13, 99] {
            assert_eq!(live.apply_fill(FillEvent { order_id: id, contracts: 50 }), FillApplied::Unknown);
        }
        // A zero or negative size is not a fill.
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 0 }), FillApplied::Unknown);
        assert_eq!(before, (live.bid, live.bid_id, live.bid_left, live.ask, live.ask_id, live.ask_left));
        // After the bid is cleared, a late fill of its id is unknown too.
        live.clear_bid();
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 50 }), FillApplied::Unknown);
    }

    #[test]
    fn a_side_whose_size_is_not_tracked_is_never_settled_by_a_fill() {
        // Without a known size, a fill cannot say the order is done: keep it (the requote path still pulls it).
        let mut live = resting(200, 200);
        live.bid_left = None;
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 500 }), FillApplied::Partial { side: QuoteSide::Bid, left: None });
        assert_eq!((live.bid_id, live.bid_left), (Some(11), None));
    }

    #[test]
    fn contracts_follow_the_venue_rounding() {
        assert_eq!(contracts_of(200.0, 1.0), Some(200));
        assert_eq!(contracts_of(250.0, 100.0), Some(3)); // 2.5 rounds as mm-delta does
        assert_eq!(contracts_of(40.0, 100.0), None); // below one contract: the venue rejects it
        assert_eq!(contracts_of(200.0, 0.0), None);
    }

    #[test]
    fn an_edit_keeps_the_smaller_remainder() {
        // 50 of 200 filled, edited at 200: the venue may count the 50 (150 left) or not (200 left). Keep 150.
        assert_eq!(left_after_edit(Some(150), Some(200)), Some(150));
        // The clip shrank the quote below what was left.
        assert_eq!(left_after_edit(Some(200), Some(120)), Some(120));
        // Nothing tracked before, or a remainder the fills already ran down (the edit proves it still rests).
        assert_eq!(left_after_edit(None, Some(200)), Some(200));
        assert_eq!(left_after_edit(Some(0), Some(200)), Some(200));
        assert_eq!(left_after_edit(Some(150), None), None);
    }

    #[test]
    fn a_quote_is_forgotten_only_when_the_venue_says_it_is_gone() {
        assert!(gone_after_cancel(true, None));
        // The cancel failed: only a closed or cancelled order (filled meanwhile, or already cancelled) is gone.
        assert!(gone_after_cancel(false, Some("closed")));
        assert!(gone_after_cancel(false, Some("cancelled")));
        assert!(!gone_after_cancel(false, Some("open")));
        assert!(!gone_after_cancel(false, Some("pending")));
        // The state could not be read either: keep tracking it and retry next loop.
        assert!(!gone_after_cancel(false, None));
    }

    #[test]
    fn resting_order_without_id_forces_cancel_all() {
        let mut live = LiveQuotes::default();
        assert!(!live.has_untracked());

        live.bid = Some(2700.0);
        live.bid_id = Some(1);
        assert!(!live.has_untracked());

        live.ask = Some(2705.0);
        assert!(live.has_untracked());

        live.clear_ask();
        assert!(!live.has_untracked());

        live.clear();
        assert!(live.bid.is_none() && live.bid_id.is_none());
    }
}
