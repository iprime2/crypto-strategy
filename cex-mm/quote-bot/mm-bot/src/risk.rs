use mm_core::regime::RegimeEngine;

#[derive(Debug, Clone)]
pub struct RiskState {
    pub halt: bool,
    pub daily_loss_limit_usd: f64,
    pub daily_pnl_usd: f64,
    pub reject_count: u64,
    pub reject_kill_count: u64,
    pub last_book_ts: std::time::Instant,
}

impl Default for RiskState {
    fn default() -> Self {
        Self {
            halt: false,
            daily_loss_limit_usd: std::env::var("MM_DAILY_LOSS_LIMIT_USD")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(500.0),
            daily_pnl_usd: 0.0,
            reject_count: 0,
            reject_kill_count: std::env::var("MM_REJECT_KILL_COUNT")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(20),
            last_book_ts: std::time::Instant::now(),
        }
    }
}

/// Whether a place error should increment `reject_count` toward the kill switch.
///
/// Venue post-only crosses and qty-below-contract rejects are expected during
/// inventory shaping / reduce paths and must not permanently halt quoting.
pub fn counts_toward_reject_kill(err: &str) -> bool {
    let lower = err.to_ascii_lowercase();
    if lower.contains("immediate_execution_post_only") {
        return false;
    }
    if lower.contains("below") && lower.contains("contract") {
        return false;
    }
    true
}

impl RiskState {
    pub fn should_kill(&self, _regime_engine: &RegimeEngine) -> bool {
        self.halt
            || self.daily_pnl_usd <= -self.daily_loss_limit_usd
            || self.reject_count > self.reject_kill_count
            || mm_core::regime::RegimeEngine::calendar_pause_utc(chrono::Utc::now())
            || self.last_book_ts.elapsed().as_millis() > 500
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reject_storm_triggers_kill() {
        let mut r = RiskState::default();
        r.reject_kill_count = 20;
        r.reject_count = 21;
        assert!(r.should_kill(&RegimeEngine::default()));
    }

    #[test]
    fn post_only_cross_does_not_count() {
        assert!(!counts_toward_reject_kill(
            "order rejected: immediate_execution_post_only"
        ));
        assert!(!counts_toward_reject_kill(
            "Immediate_Execution_Post_Only on ask"
        ));
    }

    #[test]
    fn below_contract_does_not_count() {
        assert!(!counts_toward_reject_kill(
            "qty 0.0004 below 1 contract (0.001 each)"
        ));
        assert!(!counts_toward_reject_kill(
            "Order size below minimum contract size"
        ));
    }

    #[test]
    fn other_rejects_count() {
        assert!(counts_toward_reject_kill("insufficient margin"));
        assert!(counts_toward_reject_kill("rate limit exceeded"));
        assert!(counts_toward_reject_kill("below minimum price"));
    }
}
