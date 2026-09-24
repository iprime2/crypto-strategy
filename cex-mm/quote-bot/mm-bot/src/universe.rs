use anyhow::{Context, Result};
use mm_bybit::{BybitEnvironment, BybitPublic};

use crate::symbols::{normalize_symbol, resolve_symbol_list};

#[derive(Debug, Clone)]
pub struct UniverseOptions {
    pub single: String,
    pub multi: Vec<String>,
    pub top_n: usize,
    pub exclude: Vec<String>,
}

/// Pinned symbols from `MM_SYMBOLS`. When `top_n > 0` and list is empty, no default BTC pin.
fn pinned_symbols(opts: &UniverseOptions) -> Vec<String> {
    let from_list: Vec<String> = opts
        .multi
        .iter()
        .map(|s| normalize_symbol(s))
        .filter(|s| !s.is_empty())
        .collect();
    if !from_list.is_empty() {
        return from_list;
    }
    if opts.top_n > 0 {
        return Vec::new();
    }
    vec![normalize_symbol(&opts.single)]
}

/// Resolve symbol universe: optional Bybit top-N liquidity + pinned symbols.
pub async fn resolve_universe(
    opts: UniverseOptions,
    bybit_env: BybitEnvironment,
) -> Result<Vec<String>> {
    if opts.top_n == 0 {
        return Ok(resolve_symbol_list(&opts.multi, &opts.single));
    }

    let pins = pinned_symbols(&opts);
    let ranked = BybitPublic::new(bybit_env)
        .top_liquid_usdt_linear(500)
        .await
        .context("load top liquid USDT perps from Bybit")?;

    let exclude: std::collections::HashSet<String> = opts
        .exclude
        .iter()
        .map(|s| normalize_symbol(s))
        .collect();

    let out = merge_pins_and_ranked(pins, ranked, opts.top_n, &exclude);

    if out.is_empty() {
        anyhow::bail!(
            "MM_TOP_N={} but no symbols resolved (check exchange / excludes)",
            opts.top_n
        );
    }

    Ok(out)
}

/// Merge pinned symbols then fill from ranked list up to `top_n` total.
pub fn merge_pins_and_ranked(
    pins: Vec<String>,
    ranked: Vec<String>,
    top_n: usize,
    exclude: &std::collections::HashSet<String>,
) -> Vec<String> {
    let mut out: Vec<String> = pins.into_iter().filter(|s| !exclude.contains(s)).collect();
    for sym in ranked {
        if exclude.contains(&sym) || out.iter().any(|s| s == &sym) {
            continue;
        }
        out.push(sym);
        if out.len() >= top_n {
            break;
        }
    }
    out
}

pub async fn print_universe(opts: UniverseOptions, bybit_env: BybitEnvironment) -> Result<()> {
    let syms = resolve_universe(opts, bybit_env).await?;
    for (i, s) in syms.iter().enumerate() {
        println!("{:>2}. {s}", i + 1);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn merge_respects_pins_and_cap() {
        let ex = std::collections::HashSet::new();
        let out = merge_pins_and_ranked(
            vec!["ETHUSDT".into()],
            vec![
                "BTCUSDT".into(),
                "SOLUSDT".into(),
                "XRPUSDT".into(),
            ],
            3,
            &ex,
        );
        assert_eq!(out.len(), 3);
        assert_eq!(out[0], "ETHUSDT");
        assert!(out.contains(&"BTCUSDT".into()));
    }

    #[test]
    fn merge_honors_exclude() {
        let ex = std::collections::HashSet::from(["BTCUSDT".into()]);
        let out = merge_pins_and_ranked(vec![], vec!["BTCUSDT".into(), "ETHUSDT".into()], 2, &ex);
        assert_eq!(out, vec!["ETHUSDT"]);
    }
}
