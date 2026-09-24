use crate::{BookTop, QuoteExtensions};

/// Native microprice blend + Binance lead + OFI/funding reservation shift (bps additive on price).
pub fn resolve_fair_cex(fair_native: f64, book: Option<BookTop>, ext: QuoteExtensions) -> f64 {
    let mut fair = fair_native;
    if let Some(b) = book {
        if let (Some(mid), Some(micro)) = (b.mid(), b.microprice()) {
            let w = 0.3_f64;
            fair = (1.0 - w) * mid + w * micro;
        }
    }
    if let Some(bm) = ext.binance_mid {
        if bm > 0.0 && ext.lead_weight > 0.0 {
            fair += ext.lead_weight * (bm - fair_native);
        }
    }
    fair *= 1.0 + (ext.ofi_drift_bps + ext.funding_carry_bps) / 10_000.0;
    fair
}
