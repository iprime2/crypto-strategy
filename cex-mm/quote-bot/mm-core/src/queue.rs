/// Queue-ahead estimate for a resting limit (R2 Albers / Daru).
#[derive(Debug, Clone, Copy, Default)]
pub struct QueueEstimate {
    pub price: f64,
    pub side_buy: bool,
    pub qty_ahead: f64,
}

impl QueueEstimate {
    pub fn new_at_level(price: f64, side_buy: bool, depth_at_level: f64, our_qty: f64) -> Self {
        Self {
            price,
            side_buy,
            qty_ahead: (depth_at_level - our_qty).max(0.0),
        }
    }

    /// Back-of-queue if ahead qty exceeds fraction of level depth.
    pub fn is_back_of_queue(&self, level_qty: f64, max_front_fraction: f64) -> bool {
        if level_qty <= 0.0 {
            return true;
        }
        self.qty_ahead / level_qty > max_front_fraction
    }
}

/// Post-only quote at a **new** level (away from touch) should not use touch queue depth.
pub fn should_place_limit(
    quote_price: f64,
    touch_price: f64,
    touch_qty: f64,
    our_qty: f64,
    tick: f64,
    side_buy: bool,
    max_front_fraction: f64,
) -> bool {
    if quote_price <= 0.0 {
        return false;
    }
    if touch_price <= 0.0 || tick <= 0.0 {
        return true;
    }
    if (quote_price - touch_price).abs() > tick * 0.51 {
        return true;
    }
    let qe = QueueEstimate::new_at_level(quote_price, side_buy, touch_qty, our_qty);
    !qe.is_back_of_queue(touch_qty, max_front_fraction)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn off_touch_quote_always_places() {
        assert!(should_place_limit(
            85_000.0,
            86_000.0,
            10.0,
            0.001,
            0.5,
            true,
            0.9
        ));
    }

    #[test]
    fn at_touch_respects_queue() {
        assert!(!should_place_limit(
            86_000.0,
            86_000.0,
            1.0,
            0.001,
            0.5,
            true,
            0.9
        ));
    }
}
