use serde::{Deserialize, Serialize};

/// Bot-side fill economics (exchange remains source of truth).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FillEconomics {
    pub position: f64,
    pub avg_entry: f64,
    pub realized_pnl: f64,
    pub fees_paid: f64,
    pub fill_count: u64,
}

impl Default for FillEconomics {
    fn default() -> Self {
        Self {
            position: 0.0,
            avg_entry: 0.0,
            realized_pnl: 0.0,
            fees_paid: 0.0,
            fill_count: 0,
        }
    }
}

impl FillEconomics {
    pub fn on_fill(
        &mut self,
        side_buy: bool,
        qty: f64,
        price: f64,
        fee: f64,
    ) {
        self.fees_paid += fee;
        self.fill_count += 1;
        let signed = if side_buy { qty } else { -qty };
        let new_pos = self.position + signed;
        if self.position.signum() != 0.0 && new_pos.signum() != self.position.signum() {
            let closed = self.position.abs().min(qty);
            let pnl = if self.position > 0.0 {
                (price - self.avg_entry) * closed
            } else {
                (self.avg_entry - price) * closed
            };
            self.realized_pnl += pnl;
        }
        if new_pos.abs() < 1e-12 {
            self.position = 0.0;
            self.avg_entry = 0.0;
        } else if self.position.signum() == new_pos.signum() && signed.signum() == new_pos.signum()
        {
            self.avg_entry =
                (self.avg_entry * self.position.abs() + price * qty) / new_pos.abs();
            self.position = new_pos;
        } else {
            self.position = new_pos;
            self.avg_entry = price;
        }
    }

    pub fn reconcile_position(&mut self, venue_position: f64, tolerance: f64) -> bool {
        if (self.position - venue_position).abs() > tolerance {
            self.position = venue_position;
            return true;
        }
        false
    }
}
