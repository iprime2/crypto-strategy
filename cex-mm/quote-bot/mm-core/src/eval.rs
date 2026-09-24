/// Port of GoDark mm-eval.py guards (block tighten when markouts toxic).
pub struct EvalGuards;

impl EvalGuards {
    pub fn block_spread_tighten(avg_markout_30s_bps: Option<f64>, buy_avg_30s_bps: Option<f64>) -> bool {
        if let Some(avg) = avg_markout_30s_bps {
            if avg < -5.0 {
                return true;
            }
        }
        if let Some(buy) = buy_avg_30s_bps {
            if buy < -15.0 {
                return true;
            }
        }
        false
    }

    pub fn block_size_up(buy_avg_30s_bps: Option<f64>) -> bool {
        buy_avg_30s_bps.is_some_and(|b| b < -15.0)
    }
}
