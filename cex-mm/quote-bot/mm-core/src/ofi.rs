use std::collections::VecDeque;

/// Order-flow imbalance accumulator (Cont–Kukanov–Stoikov style on L1 changes).
#[derive(Debug, Clone)]
pub struct OfiTracker {
    window: VecDeque<f64>,
    capacity: usize,
    last_bid: (f64, f64),
    last_ask: (f64, f64),
    sum_ofi: f64,
}

impl OfiTracker {
    pub fn new(capacity: usize) -> Self {
        Self {
            window: VecDeque::with_capacity(capacity.max(4)),
            capacity: capacity.max(4),
            last_bid: (0.0, 0.0),
            last_ask: (0.0, 0.0),
            sum_ofi: 0.0,
        }
    }

    pub fn on_book(&mut self, bid: f64, bid_qty: f64, ask: f64, ask_qty: f64) {
        if self.last_bid.0 > 0.0 {
            let e = Self::event_contribution(
                self.last_bid,
                (bid, bid_qty),
                self.last_ask,
                (ask, ask_qty),
            );
            self.push(e);
        }
        self.last_bid = (bid, bid_qty);
        self.last_ask = (ask, ask_qty);
    }

    fn event_contribution(
        prev_b: (f64, f64),
        b: (f64, f64),
        prev_a: (f64, f64),
        a: (f64, f64),
    ) -> f64 {
        let mut e = 0.0;
        if b.0 >= prev_b.0 {
            e += b.1;
        }
        if b.0 <= prev_b.0 {
            e -= prev_b.1;
        }
        if a.0 <= prev_a.0 {
            e -= a.1;
        }
        if a.0 >= prev_a.0 {
            e += prev_a.1;
        }
        e
    }

    fn push(&mut self, ofi: f64) {
        if self.window.len() >= self.capacity {
            if let Some(old) = self.window.pop_front() {
                self.sum_ofi -= old;
            }
        }
        self.window.push_back(ofi);
        self.sum_ofi += ofi;
    }

    pub fn window_ofi(&self) -> f64 {
        self.sum_ofi
    }

    /// Map OFI to reservation drift in bps (scaled by caller `beta`).
    pub fn drift_bps(&self, beta: f64, depth: f64) -> f64 {
        if depth <= 0.0 {
            return 0.0;
        }
        (beta * self.sum_ofi / depth).clamp(-50.0, 50.0)
    }
}

/// Rolling signed markout mean for α·μ toxicity floor (R5).
#[derive(Debug, Default)]
pub struct AlphaMuEstimator {
    samples: VecDeque<f64>,
    cap: usize,
}

impl AlphaMuEstimator {
    pub fn new(cap: usize) -> Self {
        Self {
            samples: VecDeque::new(),
            cap: cap.max(8),
        }
    }

    pub fn observe_adverse_mag(&mut self, signed_markout_bps: f64) {
        if signed_markout_bps >= 0.0 {
            return;
        }
        if self.samples.len() >= self.cap {
            self.samples.pop_front();
        }
        self.samples.push_back(-signed_markout_bps);
    }

    pub fn alpha_mu_bps(&self) -> f64 {
        if self.samples.is_empty() {
            return 0.0;
        }
        self.samples.iter().sum::<f64>() / self.samples.len() as f64
    }
}

/// Snipe detector: fills shortly after reference fair jump.
#[derive(Debug, Default)]
pub struct SnipeTracker {
    fills: u64,
    sniped: u64,
}

impl SnipeTracker {
    pub fn record_fill(&mut self, ms_since_ref_jump: u64) {
        self.fills += 1;
        if ms_since_ref_jump <= 500 {
            self.sniped += 1;
        }
    }

    pub fn rate(&self) -> f64 {
        if self.fills == 0 {
            return 0.0;
        }
        self.sniped as f64 / self.fills as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ofi_accumulates_bid_pressure() {
        let mut t = OfiTracker::new(16);
        t.on_book(100.0, 1.0, 101.0, 1.0);
        t.on_book(100.0, 3.0, 101.0, 1.0);
        assert!(t.window_ofi() > 0.0);
        assert!(t.drift_bps(0.01, 4.0) > 0.0);
    }

    #[test]
    fn alpha_mu_rises_with_adverse_series() {
        let mut a = AlphaMuEstimator::new(8);
        for _ in 0..5 {
            a.observe_adverse_mag(-4.0);
        }
        assert!(a.alpha_mu_bps() >= 3.5);
    }
}
