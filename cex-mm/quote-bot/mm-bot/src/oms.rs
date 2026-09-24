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
}
