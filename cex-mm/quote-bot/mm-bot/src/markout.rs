use mm_core::ofi::AlphaMuEstimator;
use mm_core::{signed_fill_markout_bps, MarkoutGuard};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio::sync::watch;

pub struct MarkoutRuntime {
    pub guard: Arc<Mutex<MarkoutGuard>>,
    pub alpha: Arc<Mutex<AlphaMuEstimator>>,
    pub fair_tx: watch::Sender<f64>,
    pub fair_rx: watch::Receiver<f64>,
}

impl Clone for MarkoutRuntime {
    fn clone(&self) -> Self {
        Self {
            guard: self.guard.clone(),
            alpha: self.alpha.clone(),
            fair_tx: self.fair_tx.clone(),
            fair_rx: self.fair_rx.clone(),
        }
    }
}

impl MarkoutRuntime {
    pub fn new(guard: MarkoutGuard, alpha: AlphaMuEstimator) -> Self {
        let (fair_tx, fair_rx) = watch::channel(0.0_f64);
        Self {
            guard: Arc::new(Mutex::new(guard)),
            alpha: Arc::new(Mutex::new(alpha)),
            fair_tx,
            fair_rx,
        }
    }

    pub fn update_fair(&self, fair: f64) {
        let _ = self.fair_tx.send(fair);
    }

    pub fn on_fill(&self, bought: bool, fair_at_fill: f64) {
        let guard = self.guard.clone();
        let alpha = self.alpha.clone();
        let mut fair_rx = self.fair_rx.clone();
        let threshold = std::env::var("MM_MARKOUT_THRESHOLD_BPS")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(3.0);
        let widen = std::env::var("MM_MARKOUT_WIDEN_BPS")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(4.0);
        let side_aware = std::env::var("MM_MARKOUT_SIDE_AWARE")
            .ok()
            .map(|s| s != "0")
            .unwrap_or(true);

        tokio::spawn(async move {
            let mut worst_mo = 0.0_f64;
            for horizon_secs in [1_u64, 5, 30] {
                tokio::time::sleep(Duration::from_secs(horizon_secs)).await;
                let fair_now = *fair_rx.borrow_and_update();
                if fair_now <= 0.0 {
                    continue;
                }
                let mo = signed_fill_markout_bps(fair_at_fill, fair_now, bought);
                worst_mo = worst_mo.min(mo);
                if let Ok(mut g) = guard.lock() {
                    g.observe_fill_markout(
                        mo,
                        threshold,
                        widen,
                        Some(horizon_secs as u32),
                        bought,
                        side_aware,
                    );
                }
                if let Ok(mut a) = alpha.lock() {
                    a.observe_adverse_mag(mo);
                }
            }
            if let Ok(mut g) = guard.lock() {
                g.observe_fill_markout(
                    worst_mo,
                    threshold,
                    widen,
                    None,
                    bought,
                    side_aware,
                );
            }
        });
    }
}
