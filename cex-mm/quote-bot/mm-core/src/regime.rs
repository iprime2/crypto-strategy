use chrono::Timelike;

/// Volatility regime L0–L3 (R5 / STRATEGY §6.3).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RegimeLevel {
    L0Calm = 0,
    L1Elevated = 1,
    L2Stressed = 2,
    L3Crash = 3,
}

impl RegimeLevel {
    pub fn spread_multiplier(self) -> f64 {
        match self {
            RegimeLevel::L0Calm => 1.0,
            RegimeLevel::L1Elevated => 1.5,
            RegimeLevel::L2Stressed => 2.25,
            RegimeLevel::L3Crash => 0.0,
        }
    }

    pub fn as_u8(self) -> u8 {
        self as u8
    }
}

#[derive(Debug, Clone)]
pub struct RegimeState {
    pub level: RegimeLevel,
    pub vol_ratio: f64,
    pub flow_z: f64,
}

#[derive(Debug, Clone, Copy)]
pub struct RegimeThresholds {
    /// L3 when `min(bid_qty,ask_qty)/max(...) < this`.
    pub l3_depth_ratio: f64,
    pub l3_jump_bps: f64,
    pub l3_flow_z: f64,
}

impl Default for RegimeThresholds {
    fn default() -> Self {
        Self {
            l3_depth_ratio: 0.2,
            l3_jump_bps: 50.0,
            l3_flow_z: 4.0,
        }
    }
}

pub struct RegimeEngine {
    vol_short: f64,
    vol_long: f64,
    flow_window: std::collections::VecDeque<f64>,
    flow_cap: usize,
    last_level: RegimeLevel,
}

impl Default for RegimeEngine {
    fn default() -> Self {
        Self {
            vol_short: 0.0,
            vol_long: 1.0,
            flow_window: std::collections::VecDeque::new(),
            flow_cap: 64,
            last_level: RegimeLevel::L0Calm,
        }
    }
}

impl RegimeEngine {
    pub fn update_vol(&mut self, sample_vol_bps: f64) {
        self.vol_short = 0.9 * self.vol_short + 0.1 * sample_vol_bps;
        self.vol_long = 0.99 * self.vol_long + 0.01 * sample_vol_bps.max(1.0);
    }

    pub fn on_signed_trade(&mut self, signed_qty: f64) {
        if self.flow_window.len() >= self.flow_cap {
            self.flow_window.pop_front();
        }
        self.flow_window.push_back(signed_qty);
    }

    fn flow_zscore(&self) -> f64 {
        if self.flow_window.len() < 8 {
            return 0.0;
        }
        let mean = self.flow_window.iter().sum::<f64>() / self.flow_window.len() as f64;
        let var = self.flow_window
            .iter()
            .map(|x| (x - mean).powi(2))
            .sum::<f64>()
            / (self.flow_window.len() - 1) as f64;
        let std = var.sqrt().max(1e-9);
        let last = *self.flow_window.back().unwrap_or(&0.0);
        (last - mean) / std
    }

    pub fn evaluate(&mut self, depth_ratio: f64, jump_bps: f64) -> RegimeState {
        self.evaluate_with(&RegimeThresholds::default(), depth_ratio, jump_bps)
    }

    pub fn evaluate_with(
        &mut self,
        th: &RegimeThresholds,
        depth_ratio: f64,
        jump_bps: f64,
    ) -> RegimeState {
        let ratio = if self.vol_long > 0.0 {
            self.vol_short / self.vol_long
        } else {
            1.0
        };
        let flow_z = self.flow_zscore();
        let mut level = RegimeLevel::L0Calm;
        let depth_l3 = th.l3_depth_ratio > 0.0 && depth_ratio < th.l3_depth_ratio;
        let trip_l3 = depth_l3 || jump_bps > th.l3_jump_bps || flow_z.abs() > th.l3_flow_z;
        if trip_l3 {
            // L3 is one-shot for this sample only — do not latch into last_level.
            return RegimeState {
                level: RegimeLevel::L3Crash,
                vol_ratio: ratio,
                flow_z,
            };
        } else if ratio > 2.5 || jump_bps > 15.0 || flow_z.abs() > 2.5 {
            level = RegimeLevel::L2Stressed;
        } else if ratio > 1.5 {
            level = RegimeLevel::L1Elevated;
        }
        // Hysteresis caps at L2; L3 never stored in last_level.
        if level as u8 > self.last_level as u8 {
            self.last_level = level;
        } else if (level as u8) < (self.last_level as u8) && ratio < 1.2 {
            self.last_level = level;
        } else {
            level = self.last_level;
        }
        RegimeState {
            level,
            vol_ratio: ratio,
            flow_z,
        }
    }

    pub fn calendar_pause_utc(now: chrono::DateTime<chrono::Utc>) -> bool {
        let minute = now.minute();
        let hour = now.hour();
        (hour == 13 && minute >= 28 && minute <= 35)
            || (hour == 18 && minute >= 28 && minute <= 35)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn regime_escalates_with_vol_ratio() {
        let mut e = RegimeEngine::default();
        for _ in 0..50 {
            e.update_vol(80.0);
        }
        let st = e.evaluate(1.0, 0.0);
        assert!(st.level as u8 >= RegimeLevel::L1Elevated as u8);
    }

    #[test]
    fn l3_jump_is_oneshot_not_latched() {
        let mut e = RegimeEngine::default();
        e.vol_short = 1.0;
        e.vol_long = 1.0;
        let th = RegimeThresholds {
            l3_depth_ratio: 0.2,
            l3_jump_bps: 50.0,
            l3_flow_z: 4.0,
        };
        let st1 = e.evaluate_with(&th, 1.0, 60.0);
        assert_eq!(st1.level, RegimeLevel::L3Crash);
        let st2 = e.evaluate_with(&th, 1.0, 0.0);
        assert!(
            (st2.level as u8) < (RegimeLevel::L3Crash as u8),
            "expected below L3 after calm sample, got {:?}",
            st2.level
        );
    }

    #[test]
    fn funding_skews_fair_via_extensions() {
        let ext = crate::QuoteExtensions {
            funding_carry_bps: -10.0,
            ..Default::default()
        };
        let fair = crate::fair::resolve_fair_cex(100.0, None, ext);
        assert!(fair < 100.0);
    }
}
