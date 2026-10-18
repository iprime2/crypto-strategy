/// Bybit linear symbol, e.g. `BTCUSDT` (also accepts `BTC/USDT`).
pub fn normalize_symbol(raw: &str) -> String {
    raw.trim()
        .replace('/', "")
        .replace('-', "")
        .to_uppercase()
}

pub fn resolve_symbol_list(multi: &[String], single: &str) -> Vec<String> {
    let mut out: Vec<String> = multi
        .iter()
        .map(|s| normalize_symbol(s))
        .filter(|s| !s.is_empty())
        .collect();
    if out.is_empty() {
        out.push(normalize_symbol(single));
    }
    out.sort();
    out.dedup();
    out
}

pub fn resolve_symbols_from_env() -> Vec<String> {
    if let Ok(list) = std::env::var("MM_SYMBOLS") {
        let v: Vec<String> = list
            .split(',')
            .map(normalize_symbol)
            .filter(|s| !s.is_empty())
            .collect();
        if !v.is_empty() {
            return v;
        }
    }
    vec![normalize_symbol(
        &std::env::var("MM_SYMBOL").unwrap_or_else(|_| "BTCUSDT".into()),
    )]
}

/// `KEY_{SYMBOL}` then `KEY`, as a string.
pub fn env_for_symbol(symbol: &str, key: &str) -> Option<String> {
    let slug = normalize_symbol(symbol);
    std::env::var(format!("{key}_{slug}")).ok().or_else(|| std::env::var(key).ok())
}

/// Global env, then `KEY_{SYMBOL}` override (e.g. `MM_ORDER_QTY_ETHUSDT`).
pub fn env_f64_for_symbol(symbol: &str, key: &str, default: f64) -> f64 {
    let slug = normalize_symbol(symbol);
    let per = format!("{key}_{slug}");
    std::env::var(&per)
        .ok()
        .and_then(|s| s.parse().ok())
        .or_else(|| std::env::var(key).ok().and_then(|s| s.parse().ok()))
        .unwrap_or(default)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_slash_pairs() {
        assert_eq!(normalize_symbol("btc/usdt"), "BTCUSDT");
        assert_eq!(normalize_symbol(" ETH-USDT "), "ETHUSDT");
    }
}
