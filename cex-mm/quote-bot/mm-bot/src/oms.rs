use std::time::{Duration, Instant};
use mm_core::queue::should_place_limit;

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
    /// Contracts of the resting order already filled, from the fills feed: an edit asks for these plus the
    /// contracts wanted resting (`edit_size`).
    pub bid_filled: i64,
    pub ask_filled: i64,
    /// When the fills said the side's quote was done while the venue had not yet shown it closed. While set,
    /// the loop asks the venue again each loop (`awaiting_venue`).
    pub bid_done_at: Option<Instant>,
    pub ask_done_at: Option<Instant>,
    /// Fills of quotes already forgotten that the venue showed but the fills feed did not deliver: not yet in
    /// the position, so the loop sizes as if they were (`unseen_contracts`). Kept by `clear`, emptied by the
    /// feed, a venue reading or `expire_unseen`.
    pub unseen: Vec<UnseenFill>,
}

/// Contracts of one of our quotes that the venue shows filled while the fills feed never delivered them.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct UnseenFill {
    pub order_id: u64,
    pub side: QuoteSide,
    pub contracts: i64,
    /// When the venue showed the order gone: a venue position read sent after this includes the fill.
    pub since: Instant,
}

/// How long an unseen fill counts when neither the feed nor a venue reading has caught up. The venue reconcile
/// adopts a lasting difference within `MM_RECONCILE_MAX_WAIT_SEC` (15 s) plus one read, so this only bounds
/// an entry nothing ever confirms.
pub const UNSEEN_MAX_AGE: Duration = Duration::from_secs(60);

/// How long the loop keeps asking the venue about a quote the fills say is done before it believes a venue
/// that still shows it open. On the 19 Oct 2026 demo QA, 13 of 45 such orders still read "open" about 150 ms
/// after their last fill; each read closed when asked again 0.45-0.74 s later.
pub const SETTLE_PATIENCE: Duration = Duration::from_secs(5);

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
    /// A late fill of a quote already forgotten as filled (`LiveQuotes::forget_gone`): it reaches the position
    /// through the feed now, so it stops counting as unseen.
    CaughtUp { side: QuoteSide },
    /// Not one of the resting quotes (an order already replaced or cancelled, a reduce-only exit): ignored.
    Unknown,
}

/// What the venue's answer did to a quote the fills say is done.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Settled {
    /// Closed or cancelled: the side is clear and the loop quotes it again.
    Cleared,
    /// Still shown open, or no answer, within `SETTLE_PATIENCE`: the loop asks again next time.
    Waiting,
    /// Still open once the patience ran out: the venue's unfilled size is the remainder from now on.
    Resynced { left: i64 },
    /// No usable answer once the patience ran out: stop asking. The quote stays tracked, and the requote
    /// path asks the venue before it forgets it.
    GaveUp,
    /// The side has moved on to another order: nothing changed.
    Moved,
}

/// Contracts the venue books for `qty_base`, rounded as `mm-delta` sends it; None below one contract.
pub fn contracts_of(qty_base: f64, contract_value: f64) -> Option<i64> {
    if contract_value <= 0.0 || !qty_base.is_finite() {
        return None;
    }
    let n = (qty_base / contract_value).round();
    (n >= 1.0).then_some(n as i64)
}

/// Contracts to send in an edit so that `wanted` rest. Delta takes an edit's size as the order's total, filled
/// part included: on 28 Oct 2026 bid 1636567899 of 200 with 27 filled, edited to 200, kept 173 unfilled. Until
/// then the bot sent only the contracts it wanted resting, so a part-filled quote rested short by its filled
/// part (11-12% of the size quoted, 25-28 Oct), and an edit down to the filled part left nothing to rest: Delta
/// cancelled the order ("no_position_left_for_reduce_only", on an order that was not reduce-only) and never
/// answered, which held the loop for the 3 s timeout (all 10 unanswered edits, 26-28 Oct 2026).
pub fn edit_size(wanted: i64, filled: i64) -> i64 {
    wanted + filled.max(0)
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

/// The first venue call one side makes in a loop. The two sides' first calls go out together: Delta mainnet
/// takes about 0.55 s to answer an order write (21 Oct 2026), so one after the other a two-sided requote held
/// the loop over a second. The fallbacks of a failed call (order state, cancel-all) run only once both have
/// answered, so a cancel-all never crosses an order call on the other side.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum FirstCall {
    Nothing,
    /// Cancel the resting order: the plan switched the side off, or the new price would cross the book (the new
    /// quote is placed once the old one is gone).
    Pull(u64),
    Edit(u64),
    Place(f64),
}

/// One side's first call. `resting_id` is the side's tracked order; `edits_by_id` is false on a venue that
/// replaces quotes by placing (Bybit); `place_price` is `place_price`'s answer for an empty side.
pub fn first_call(
    need: bool,
    resting_id: Option<u64>,
    quote_side: bool,
    crosses: bool,
    edits_by_id: bool,
    place_price: Option<f64>,
) -> FirstCall {
    if !need {
        return FirstCall::Nothing;
    }
    match resting_id {
        Some(id) if edits_by_id => {
            if quote_side && !crosses {
                FirstCall::Edit(id)
            } else {
                FirstCall::Pull(id)
            }
        }
        _ if quote_side => place_price.map_or(FirstCall::Nothing, FirstCall::Place),
        _ => FirstCall::Nothing,
    }
}

/// Price of a new post-only quote, or None to leave the side empty this loop. A quote that reduces the
/// position and would cross the book goes one tick inside the opposite touch; any other quote goes in at its
/// own price unless it would join the back of a deep queue at the touch (`should_place_limit`).
#[allow(clippy::too_many_arguments)]
pub fn place_price(
    side: QuoteSide,
    target: f64,
    reduces: bool,
    best_bid: f64,
    best_ask: f64,
    touch_qty: f64,
    qty: f64,
    tick: f64,
    queue_front_frac: f64,
) -> Option<f64> {
    let is_bid = side == QuoteSide::Bid;
    if is_bid && reduces && target >= best_ask && best_ask > 0.0 && qty > 0.0 {
        return Some((best_ask - tick).max(best_bid));
    }
    if !is_bid && reduces && target <= best_bid && best_bid > 0.0 && qty > 0.0 {
        return Some((best_bid + tick).min(best_ask));
    }
    let touch = if is_bid { best_bid } else { best_ask };
    should_place_limit(target, touch, touch_qty, qty, tick, is_bid, queue_front_frac).then_some(target)
}

impl LiveQuotes {
    /// A place that got no answer (`mm_delta::outcome_unknown`): the order may rest, under an id we do not know.
    /// The side is tracked without one, so the next loop cancels all at once (`has_untracked`).
    pub fn track_without_id(&mut self, side: QuoteSide, price: f64) {
        match side {
            QuoteSide::Bid => {
                self.clear_bid();
                self.bid = Some(price);
            }
            QuoteSide::Ask => {
                self.clear_ask();
                self.ask = Some(price);
            }
        }
    }

    /// Forgets both quotes (a cancel-all), but not the unseen fills they left in the position.
    pub fn clear(&mut self) {
        let unseen = std::mem::take(&mut self.unseen);
        *self = Self { unseen, ..Self::default() };
    }

    pub fn clear_bid(&mut self) {
        self.bid = None;
        self.bid_id = None;
        self.bid_left = None;
        self.bid_filled = 0;
        self.bid_done_at = None;
    }

    pub fn clear_ask(&mut self) {
        self.ask = None;
        self.ask_id = None;
        self.ask_left = None;
        self.ask_filled = 0;
        self.ask_done_at = None;
    }

    /// The side's tracked remainder after a place or an edit the venue accepted: that order is not done.
    pub fn set_left(&mut self, side: QuoteSide, left: Option<i64>) {
        let (l, done_at) = self.track_mut(side);
        *l = left;
        *done_at = None;
    }

    /// A new order the venue accepted on the side: nothing of it has filled yet.
    pub fn track_placed(&mut self, side: QuoteSide, id: Option<u64>, price: f64, left: Option<i64>) {
        match side {
            QuoteSide::Bid => {
                self.bid = Some(price);
                self.bid_id = id;
                self.bid_filled = 0;
            }
            QuoteSide::Ask => {
                self.ask = Some(price);
                self.ask_id = id;
                self.ask_filled = 0;
            }
        }
        self.set_left(side, left);
    }

    /// An edit the venue accepted: the order now rests at `price` with `left` contracts unfilled, since the edit
    /// asked for its filled part plus these (`edit_qty`). Fills that land later run it down as usual.
    pub fn track_edited(&mut self, side: QuoteSide, price: f64, left: Option<i64>) {
        match side {
            QuoteSide::Bid => self.bid = Some(price),
            QuoteSide::Ask => self.ask = Some(price),
        }
        self.set_left(side, left);
    }

    /// Contracts of the side's resting order already filled, as far as the fills feed has told us.
    pub fn filled(&self, side: QuoteSide) -> i64 {
        match side {
            QuoteSide::Bid => self.bid_filled,
            QuoteSide::Ask => self.ask_filled,
        }
    }

    /// Size, in base units for `mm-delta`, to send in an edit of the side's order so that `qty` rests
    /// (`edit_size`). A size below one contract is sent as it is: the venue refuses it either way.
    pub fn edit_qty(&self, side: QuoteSide, qty: f64, contract_value: f64) -> f64 {
        match contracts_of(qty, contract_value) {
            Some(n) => edit_size(n, self.filled(side)) as f64 * contract_value,
            None => qty,
        }
    }

    /// The order to ask the venue about again: the side's quote the fills say is done, not yet shown closed.
    pub fn awaiting_venue(&self, side: QuoteSide) -> Option<u64> {
        match side {
            QuoteSide::Bid => self.bid_done_at.and(self.bid_id),
            QuoteSide::Ask => self.ask_done_at.and(self.ask_id),
        }
    }

    /// When the fills said the side's quote was done, while the venue has not confirmed it.
    pub fn done_at(&self, side: QuoteSide) -> Option<Instant> {
        match side {
            QuoteSide::Bid => self.bid_done_at,
            QuoteSide::Ask => self.ask_done_at,
        }
    }

    fn track_mut(&mut self, side: QuoteSide) -> (&mut Option<i64>, &mut Option<Instant>) {
        match side {
            QuoteSide::Bid => (&mut self.bid_left, &mut self.bid_done_at),
            QuoteSide::Ask => (&mut self.ask_left, &mut self.ask_done_at),
        }
    }

    pub fn clear_side(&mut self, side: QuoteSide) {
        match side {
            QuoteSide::Bid => self.clear_bid(),
            QuoteSide::Ask => self.clear_ask(),
        }
    }

    /// Forgets a quote the venue shows gone (closed or cancelled) with `venue_unfilled` contracts unfilled.
    /// Contracts the fills feed still expected to rest beyond that filled without the feed saying so: on
    /// 29 Oct 2026 the feed was reconnecting when bid 1640249200 filled, the bot forgot the closed order at
    /// 400 long, bid again and reached 800 against a cap of 600. Those contracts count toward the position
    /// until the feed or a venue reading catches up (`unseen_contracts`). Returns them.
    pub fn forget_gone(&mut self, side: QuoteSide, venue_unfilled: i64, now: Instant) -> i64 {
        let (id, left) = match side {
            QuoteSide::Bid => (self.bid_id, self.bid_left),
            QuoteSide::Ask => (self.ask_id, self.ask_left),
        };
        let unseen = left.map_or(0, |l| l - venue_unfilled.max(0)).max(0);
        if let (Some(order_id), true) = (id, unseen > 0) {
            self.unseen.push(UnseenFill { order_id, side, contracts: unseen, since: now });
        }
        self.clear_side(side);
        unseen
    }

    /// Contracts the venue showed filled that are not yet in the position: bought positive, sold negative.
    pub fn unseen_contracts(&self) -> i64 {
        self.unseen
            .iter()
            .map(|u| match u.side {
                QuoteSide::Bid => u.contracts,
                QuoteSide::Ask => -u.contracts,
            })
            .sum()
    }

    /// The position now matches a venue reading sent at `sent`: it includes every fill the venue showed
    /// before then.
    pub fn unseen_settled_by_venue(&mut self, sent: Instant) {
        self.unseen.retain(|u| u.since > sent);
    }

    /// Drops unseen fills older than `max_age` that nothing confirmed, and returns them.
    pub fn expire_unseen(&mut self, now: Instant, max_age: Duration) -> Vec<UnseenFill> {
        let (expired, kept) = self.unseen.drain(..).partition(|u| now.saturating_duration_since(u.since) >= max_age);
        self.unseen = kept;
        expired
    }

    /// A late feed fill of an unseen order: it is in the position now. Returns the side it caught up.
    fn catch_up_unseen(&mut self, ev: FillEvent) -> Option<QuoteSide> {
        let i = self.unseen.iter().position(|u| u.order_id == ev.order_id)?;
        let side = self.unseen[i].side;
        self.unseen[i].contracts -= ev.contracts;
        if self.unseen[i].contracts <= 0 {
            self.unseen.remove(i);
        }
        Some(side)
    }

    /// Books one fill against the resting quote it belongs to. Fills of any other order change nothing.
    pub fn apply_fill(&mut self, ev: FillEvent, now: Instant) -> FillApplied {
        if ev.contracts <= 0 {
            return FillApplied::Unknown;
        }
        let side = if self.bid_id == Some(ev.order_id) {
            QuoteSide::Bid
        } else if self.ask_id == Some(ev.order_id) {
            QuoteSide::Ask
        } else if let Some(side) = self.catch_up_unseen(ev) {
            return FillApplied::CaughtUp { side };
        } else {
            return FillApplied::Unknown;
        };
        match side {
            QuoteSide::Bid => self.bid_filled += ev.contracts,
            QuoteSide::Ask => self.ask_filled += ev.contracts,
        }
        let (left, done_at) = self.track_mut(side);
        let Some(n) = left.as_mut() else {
            return FillApplied::Partial { side, left: None };
        };
        *n -= ev.contracts;
        if *n > 0 {
            FillApplied::Partial { side, left: Some(*n) }
        } else {
            done_at.get_or_insert(now);
            FillApplied::Filled { side }
        }
    }

    /// Settles a quote the fills say is done, with the venue's `(state, unfilled)` for that order (None: no
    /// answer). Closed or cancelled clears the side, so the loop quotes it again. The venue's order state can
    /// trail the fills feed, so an order it still shows open stays tracked and is asked about again until
    /// `patience` has passed since the fills said it was done; only then does the venue's unfilled size become
    /// the remainder. A side that has moved on to another order is not touched.
    pub fn settle(
        &mut self,
        side: QuoteSide,
        order_id: u64,
        venue: Option<(&str, i64)>,
        now: Instant,
        patience: Duration,
    ) -> Settled {
        let id = match side {
            QuoteSide::Bid => self.bid_id,
            QuoteSide::Ask => self.ask_id,
        };
        if id != Some(order_id) {
            return Settled::Moved;
        }
        if venue.is_some_and(|(state, _)| venue_says_gone(state)) {
            self.clear_side(side);
            return Settled::Cleared;
        }
        let (left, done_at) = self.track_mut(side);
        let since = *done_at.get_or_insert(now);
        if now.saturating_duration_since(since) < patience {
            return Settled::Waiting;
        }
        *done_at = None;
        match venue {
            Some((_, unfilled)) if unfilled > 0 => {
                *left = Some(unfilled);
                Settled::Resynced { left: unfilled }
            }
            _ => Settled::GaveUp,
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
    fn each_side_edits_pulls_or_places_first() {
        use FirstCall::*;
        // A resting quote moves by edit, or is pulled when the plan switches the side off or the new price
        // would cross the book (the place comes after the pull, once it is gone).
        assert_eq!(first_call(true, Some(7), true, false, true, Some(0.2)), Edit(7));
        assert_eq!(first_call(true, Some(7), false, false, true, Some(0.2)), Pull(7));
        assert_eq!(first_call(true, Some(7), true, true, true, Some(0.2)), Pull(7));
        // An empty side places, if the queue rule lets it; a side switched off stays empty.
        assert_eq!(first_call(true, None, true, false, true, Some(0.2)), Place(0.2));
        assert_eq!(first_call(true, None, true, false, true, None), Nothing);
        assert_eq!(first_call(true, None, false, false, true, Some(0.2)), Nothing);
        // Nothing to do when the side needs no update.
        assert_eq!(first_call(false, Some(7), false, true, true, Some(0.2)), Nothing);
        // A venue without edit by id (Bybit) only places, as before.
        assert_eq!(first_call(true, Some(7), true, false, false, Some(0.2)), Place(0.2));
    }

    #[test]
    fn a_reducing_quote_that_would_cross_goes_one_tick_inside_the_touch() {
        let tick = 0.00001;
        // Short, so the bid reduces: a bid at or above the best ask is placed one tick under it.
        let px = place_price(QuoteSide::Bid, 0.22100, true, 0.22080, 0.22090, 500.0, 200.0, tick, 0.9).unwrap();
        assert!((px - 0.22089).abs() < 1e-12);
        // Long, so the ask reduces: an ask at or below the best bid is placed one tick over it.
        let px = place_price(QuoteSide::Ask, 0.22070, true, 0.22080, 0.22090, 500.0, 200.0, tick, 0.9).unwrap();
        assert!((px - 0.22081).abs() < 1e-12);
        // Away from the touch a quote always goes in at its own price.
        assert_eq!(place_price(QuoteSide::Bid, 0.22050, false, 0.22080, 0.22090, 500.0, 200.0, tick, 0.9), Some(0.22050));
        assert_eq!(place_price(QuoteSide::Ask, 0.22120, false, 0.22080, 0.22090, 500.0, 200.0, tick, 0.9), Some(0.22120));
    }

    #[test]
    fn a_place_with_no_answer_is_tracked_without_an_id() {
        let mut live = LiveQuotes { ask: Some(0.221), ask_id: Some(3), ..Default::default() };
        live.track_without_id(QuoteSide::Bid, 0.2205);
        // The next loop sees an order it cannot address by id and cancels all before quoting again.
        assert!(live.has_untracked());
        assert_eq!((live.bid, live.bid_id), (Some(0.2205), None));
        assert_eq!(live.ask_id, Some(3), "the other side is untouched");
    }

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

    const P: Duration = SETTLE_PATIENCE;

    fn ms(t0: Instant, n: u64) -> Instant {
        t0 + Duration::from_millis(n)
    }

    #[test]
    fn a_partial_fill_decrements_the_side_and_a_full_one_waits_for_the_venue() {
        let t0 = Instant::now();
        let mut live = resting(200, 200);
        let ev = |order_id, contracts| FillEvent { order_id, contracts };
        assert_eq!(live.apply_fill(ev(11, 50), t0), FillApplied::Partial { side: QuoteSide::Bid, left: Some(150) });
        assert_eq!((live.bid, live.bid_id, live.bid_left), (Some(0.2400), Some(11), Some(150)));
        assert_eq!(live.awaiting_venue(QuoteSide::Bid), None);
        // The rest fills: the quote looks done, but it stays tracked until the venue says it is closed.
        assert_eq!(live.apply_fill(ev(11, 150), t0), FillApplied::Filled { side: QuoteSide::Bid });
        assert_eq!((live.bid, live.bid_id, live.awaiting_venue(QuoteSide::Bid)), (Some(0.2400), Some(11), Some(11)));
        assert_eq!(live.settle(QuoteSide::Bid, 11, Some(("closed", 0)), ms(t0, 100), P), Settled::Cleared);
        assert_eq!((live.bid, live.bid_id, live.bid_left, live.bid_done_at), (None, None, None, None));
        // The ask is untouched, and fills it independently.
        assert_eq!((live.ask_id, live.ask_left), (Some(12), Some(200)));
        assert_eq!(live.apply_fill(ev(12, 260), t0), FillApplied::Filled { side: QuoteSide::Ask });
        assert_eq!(live.settle(QuoteSide::Ask, 12, Some(("closed", 0)), ms(t0, 100), P), Settled::Cleared);
        assert!(live.ask.is_none() && live.ask_id.is_none());
    }

    #[test]
    fn a_venue_that_trails_the_fills_is_asked_again_until_it_shows_the_quote_closed() {
        // 19 Oct 2026 demo: about 150 ms after the last fill the venue still showed the order open with its
        // old size; asked again 0.5 s later it showed it closed.
        let t0 = Instant::now();
        let mut live = resting(200, 2);
        assert_eq!(live.apply_fill(FillEvent { order_id: 12, contracts: 2 }, t0), FillApplied::Filled { side: QuoteSide::Ask });
        assert_eq!(live.settle(QuoteSide::Ask, 12, Some(("open", 2)), ms(t0, 150), P), Settled::Waiting);
        // Still tracked with the fills' remainder, not the venue's stale size, and asked about again.
        assert_eq!((live.ask_id, live.ask_left, live.awaiting_venue(QuoteSide::Ask)), (Some(12), Some(0), Some(12)));
        assert_eq!(live.settle(QuoteSide::Ask, 12, None, ms(t0, 550), P), Settled::Waiting);
        assert_eq!(live.settle(QuoteSide::Ask, 12, Some(("closed", 0)), ms(t0, 950), P), Settled::Cleared);
        assert_eq!((live.ask, live.ask_id, live.awaiting_venue(QuoteSide::Ask)), (None, None, None));
        // The bid was never involved.
        assert_eq!((live.bid_id, live.bid_left, live.awaiting_venue(QuoteSide::Bid)), (Some(11), Some(200), None));
    }

    #[test]
    fn after_the_patience_the_venue_decides() {
        let t0 = Instant::now();
        // Still open after the patience (a fill counted twice, say): its unfilled size becomes the remainder.
        let mut live = resting(50, 200);
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 50 }, t0), FillApplied::Filled { side: QuoteSide::Bid });
        assert_eq!(live.settle(QuoteSide::Bid, 11, Some(("open", 120)), ms(t0, 4_900), P), Settled::Waiting);
        assert_eq!(live.settle(QuoteSide::Bid, 11, Some(("open", 120)), ms(t0, 5_000), P), Settled::Resynced { left: 120 });
        assert_eq!((live.bid_id, live.bid_left, live.awaiting_venue(QuoteSide::Bid)), (Some(11), Some(120), None));
        // No answer for the whole patience: stop asking, but keep the quote tracked rather than risk a second
        // one beside it (the requote path asks before it forgets it).
        let mut live = resting(50, 200);
        live.apply_fill(FillEvent { order_id: 11, contracts: 50 }, t0);
        assert_eq!(live.settle(QuoteSide::Bid, 11, None, ms(t0, 5_000), P), Settled::GaveUp);
        assert_eq!((live.bid_id, live.bid_left, live.awaiting_venue(QuoteSide::Bid)), (Some(11), Some(0), None));
        // A cancelled order is gone, at any time.
        assert_eq!(live.settle(QuoteSide::Bid, 11, Some(("cancelled", 0)), ms(t0, 9_000), P), Settled::Cleared);
        assert!(live.bid_id.is_none());
    }

    #[test]
    fn a_side_that_moved_on_or_was_placed_again_is_not_settled() {
        let t0 = Instant::now();
        let mut live = resting(2, 200);
        live.apply_fill(FillEvent { order_id: 11, contracts: 2 }, t0);
        // The requote path replaced the order before the answer came: nothing changes.
        live.bid = Some(0.2401);
        live.bid_id = Some(21);
        live.set_left(QuoteSide::Bid, Some(200));
        assert_eq!(live.settle(QuoteSide::Bid, 11, Some(("closed", 0)), ms(t0, 100), P), Settled::Moved);
        assert_eq!((live.bid_id, live.bid_left), (Some(21), Some(200)));
        // A place or an accepted edit means the order rests: no venue check is pending for it.
        assert_eq!(live.awaiting_venue(QuoteSide::Bid), None);
    }

    #[test]
    fn fills_of_replaced_unknown_or_untracked_orders_change_nothing() {
        let mut live = resting(200, 200);
        let before = (live.bid, live.bid_id, live.bid_left, live.ask, live.ask_id, live.ask_left);
        // A replaced order (cancelled, then a fill that was already in flight), a reduce-only exit, anything else.
        for id in [10, 13, 99] {
            assert_eq!(live.apply_fill(FillEvent { order_id: id, contracts: 50 }, Instant::now()), FillApplied::Unknown);
        }
        // A zero or negative size is not a fill.
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 0 }, Instant::now()), FillApplied::Unknown);
        assert_eq!(before, (live.bid, live.bid_id, live.bid_left, live.ask, live.ask_id, live.ask_left));
        // After the bid is cleared, a late fill of its id is unknown too.
        live.clear_bid();
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 50 }, Instant::now()), FillApplied::Unknown);
    }

    #[test]
    fn a_quote_the_venue_shows_filled_without_a_feed_fill_counts_until_the_feed_catches_up() {
        // 29 Oct 2026 20:48 UTC: the private feed reconnected and never delivered the fill of bid 1640249200
        // (200). Its edit failed, the venue showed it closed, the bot forgot it at 400 long and bid again: 800
        // against a cap of 600 until the venue reconcile caught up 13 s later.
        let t0 = Instant::now();
        let mut live = resting(200, 200);
        assert_eq!(live.forget_gone(QuoteSide::Bid, 0, t0), 200);
        assert_eq!((live.bid, live.bid_id, live.bid_left), (None, None, None));
        assert_eq!(live.unseen_contracts(), 200);
        // Long 400 by the feed, so 600 with the unseen fill: no room left for another bid.
        let position = 400.0 + live.unseen_contracts() as f64;
        assert_eq!(mm_core::side_order_qty(position, false, 200.0, 1.0, 600.0, 1.0), 0.0);
        // The feed delivers it late: it reaches the position that way, so it stops counting as unseen.
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 120 }, t0), FillApplied::CaughtUp { side: QuoteSide::Bid });
        assert_eq!(live.unseen_contracts(), 80);
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 80 }, t0), FillApplied::CaughtUp { side: QuoteSide::Bid });
        assert!(live.unseen.is_empty());
        // Nothing left to catch up: another fill of that id is unknown.
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 10 }, t0), FillApplied::Unknown);
    }

    #[test]
    fn only_contracts_the_feed_did_not_count_and_the_venue_shows_filled_are_unseen() {
        let t0 = Instant::now();
        // The feed counted every fill: nothing unseen.
        let mut live = resting(200, 200);
        live.apply_fill(FillEvent { order_id: 12, contracts: 200 }, t0);
        assert_eq!(live.forget_gone(QuoteSide::Ask, 0, t0), 0);
        // Cancelled with 150 of the 200 the feed left us expecting still unfilled: 50 bought unseen.
        assert_eq!(live.forget_gone(QuoteSide::Bid, 150, t0), 50);
        assert_eq!(live.unseen_contracts(), 50);
        // An ask sold unseen counts the other way.
        let mut live = resting(200, 200);
        assert_eq!(live.forget_gone(QuoteSide::Ask, 0, t0), 200);
        assert_eq!(live.unseen_contracts(), -200);
        // A size we never tracked tells us nothing.
        let mut live = resting(200, 200);
        live.bid_left = None;
        assert_eq!(live.forget_gone(QuoteSide::Bid, 0, t0), 0);
        assert!(live.unseen.is_empty() && live.bid_id.is_none());
    }

    #[test]
    fn unseen_fills_survive_a_cancel_all_and_clear_once_a_venue_reading_after_them_is_in_the_position() {
        let t0 = Instant::now();
        let mut live = resting(200, 200);
        live.forget_gone(QuoteSide::Bid, 0, ms(t0, 1_000));
        // A cancel-all forgets the quotes, not the position they left behind.
        live.clear();
        assert_eq!(live.unseen_contracts(), 200);
        // A reading sent before the venue showed the order closed may not include the fill.
        live.unseen_settled_by_venue(ms(t0, 999));
        assert_eq!(live.unseen_contracts(), 200);
        live.unseen_settled_by_venue(ms(t0, 1_000));
        assert!(live.unseen.is_empty());
    }

    #[test]
    fn an_unseen_fill_nothing_confirms_expires() {
        let t0 = Instant::now();
        let mut live = resting(200, 200);
        live.forget_gone(QuoteSide::Ask, 0, t0);
        assert!(live.expire_unseen(t0 + UNSEEN_MAX_AGE - Duration::from_millis(1), UNSEEN_MAX_AGE).is_empty());
        let expired = live.expire_unseen(t0 + UNSEEN_MAX_AGE, UNSEEN_MAX_AGE);
        assert_eq!(expired.iter().map(|u| (u.order_id, u.side, u.contracts)).collect::<Vec<_>>(), vec![(12, QuoteSide::Ask, 200)]);
        assert_eq!(live.unseen_contracts(), 0);
    }

    #[test]
    fn a_side_whose_size_is_not_tracked_is_never_settled_by_a_fill() {
        // Without a known size, a fill cannot say the order is done: keep it (the requote path still pulls it).
        let mut live = resting(200, 200);
        live.bid_left = None;
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 500 }, Instant::now()), FillApplied::Partial { side: QuoteSide::Bid, left: None });
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
    fn fills_count_toward_the_resting_orders_filled_part() {
        let t0 = Instant::now();
        let mut live = resting(200, 200);
        live.apply_fill(FillEvent { order_id: 11, contracts: 70 }, t0);
        live.apply_fill(FillEvent { order_id: 11, contracts: 3 }, t0);
        assert_eq!((live.filled(QuoteSide::Bid), live.filled(QuoteSide::Ask)), (73, 0));
        // Fills of other orders, and a size that is not tracked, still count only for their own order.
        live.apply_fill(FillEvent { order_id: 99, contracts: 50 }, t0);
        live.ask_left = None;
        live.apply_fill(FillEvent { order_id: 12, contracts: 5 }, t0);
        assert_eq!((live.filled(QuoteSide::Bid), live.filled(QuoteSide::Ask)), (73, 5));
        // A new order on the side, or a cleared side, starts from nothing filled.
        live.track_placed(QuoteSide::Bid, Some(21), 0.2401, Some(200));
        assert_eq!((live.bid, live.bid_id, live.bid_left, live.filled(QuoteSide::Bid)), (Some(0.2401), Some(21), Some(200), 0));
        live.clear_ask();
        assert_eq!(live.filled(QuoteSide::Ask), 0);
    }

    #[test]
    fn an_edit_asks_for_the_filled_part_plus_the_size_wanted_resting() {
        // Delta takes an edit's size as the order's total: 28 Oct 2026, bid 1636567899 of 200 with 27 filled,
        // edited to 200, kept 173 unfilled. An edit that asked only for the 73 wanted resting, on a bid that had
        // filled 73, left nothing: Delta cancelled it and never answered (11:26:44Z, as all 10 unanswered edits).
        let t0 = Instant::now();
        let mut live = resting(200, 200);
        live.apply_fill(FillEvent { order_id: 11, contracts: 70 }, t0);
        live.apply_fill(FillEvent { order_id: 11, contracts: 3 }, t0);
        assert_eq!(live.edit_qty(QuoteSide::Bid, 73.0, 1.0), 146.0);
        assert_eq!(live.edit_qty(QuoteSide::Bid, 200.0, 1.0), 273.0);
        // Nothing filled: the size wanted, as before.
        assert_eq!(live.edit_qty(QuoteSide::Ask, 200.0, 1.0), 200.0);
        // In base units for a contract of 10: 200 contracts wanted, 5 filled, 205 sent.
        live.apply_fill(FillEvent { order_id: 12, contracts: 5 }, t0);
        assert_eq!(live.edit_qty(QuoteSide::Ask, 2000.0, 10.0), 2050.0);
        assert_eq!(edit_size(73, 73), 146);
    }

    #[test]
    fn after_an_edit_the_wanted_size_rests_and_the_fills_run_it_down() {
        let t0 = Instant::now();
        let mut live = resting(200, 200);
        live.apply_fill(FillEvent { order_id: 11, contracts: 70 }, t0);
        // Edited back to 200 resting (270 sent): 200 left, the 70 already filled still count.
        live.track_edited(QuoteSide::Bid, 0.2399, Some(200));
        assert_eq!((live.bid, live.bid_id, live.bid_left, live.filled(QuoteSide::Bid)), (Some(0.2399), Some(11), Some(200), 70));
        assert_eq!(live.awaiting_venue(QuoteSide::Bid), None);
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 150 }, t0), FillApplied::Partial { side: QuoteSide::Bid, left: Some(50) });
        assert_eq!(live.filled(QuoteSide::Bid), 220);
        assert_eq!(live.apply_fill(FillEvent { order_id: 11, contracts: 50 }, t0), FillApplied::Filled { side: QuoteSide::Bid });
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
