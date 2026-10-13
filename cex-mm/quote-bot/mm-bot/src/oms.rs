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
}

impl LiveQuotes {
    pub fn clear(&mut self) {
        *self = Self::default();
    }

    pub fn clear_bid(&mut self) {
        self.bid = None;
        self.bid_id = None;
    }

    pub fn clear_ask(&mut self) {
        self.ask = None;
        self.ask_id = None;
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
