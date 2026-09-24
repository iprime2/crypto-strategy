use anyhow::{Context, Result};
use serde::Deserialize;
use std::collections::HashMap;

/// Map MM env symbols (Bybit-style) to Delta perpetual symbols.
pub fn mm_symbol_from_delta(delta_symbol: &str) -> String {
    match delta_symbol.to_uppercase().as_str() {
        "BTCUSD" => "BTCUSDT".into(),
        "ETHUSD" => "ETHUSDT".into(),
        "SOLUSD" => "SOLUSDT".into(),
        other if other.ends_with("USD") && !other.ends_with("USDT") => {
            format!("{}T", other)
        }
        other => other.to_string(),
    }
}

pub fn delta_product_symbol(mm_symbol: &str) -> String {
    let s = mm_symbol.trim().to_uppercase().replace(['/', '-'], "");
    match s.as_str() {
        "BTCUSDT" | "BTCUSD" => "BTCUSD".into(),
        "ETHUSDT" | "ETHUSD" => "ETHUSD".into(),
        "SOLUSDT" | "SOLUSD" => "SOLUSD".into(),
        other if other.ends_with("USDT") => {
            let base = other.trim_end_matches("USDT");
            format!("{base}USD")
        }
        other => other.to_string(),
    }
}

#[derive(Debug, Clone)]
pub struct ProductMeta {
    pub product_id: u64,
    pub symbol: String,
    pub tick_size: f64,
    /// BTC (or base) per one contract.
    pub contract_value: f64,
}

#[derive(Debug, Deserialize)]
struct ProductsResponse {
    success: Option<bool>,
    result: Option<Vec<ProductRow>>,
}

#[derive(Debug, Deserialize)]
struct ProductRow {
    id: u64,
    symbol: String,
    tick_size: String,
    contract_value: String,
    contract_type: Option<String>,
    state: Option<String>,
}

#[derive(Clone)]
pub struct ProductCatalog {
    by_mm_symbol: HashMap<String, ProductMeta>,
    by_delta_symbol: HashMap<String, ProductMeta>,
}

impl ProductCatalog {
    pub async fn load(client: &reqwest::Client, base_url: &str) -> Result<Self> {
        let url = format!(
            "{base_url}/v2/products?contract_types=perpetual_futures&page_size=200"
        );
        let resp: ProductsResponse = client
            .get(&url)
            .header("User-Agent", "mm-delta/0.1")
            .send()
            .await
            .context("products request")?
            .json()
            .await
            .context("products json")?;
        let rows = resp.result.unwrap_or_default();
        let mut by_mm_symbol = HashMap::new();
        let mut by_delta_symbol = HashMap::new();
        for row in rows {
            if row.state.as_deref() != Some("live") {
                continue;
            }
            if row.contract_type.as_deref() != Some("perpetual_futures") {
                continue;
            }
            let tick_size: f64 = row.tick_size.parse().unwrap_or(0.5);
            let contract_value: f64 = row.contract_value.parse().unwrap_or(0.001);
            let meta = ProductMeta {
                product_id: row.id,
                symbol: row.symbol.clone(),
                tick_size,
                contract_value,
            };
            by_delta_symbol.insert(row.symbol.clone(), meta.clone());
            // Index common MM aliases.
            for alias in mm_aliases_for_delta(&row.symbol) {
                by_mm_symbol.insert(alias, meta.clone());
            }
        }
        Ok(Self {
            by_mm_symbol,
            by_delta_symbol,
        })
    }

    pub fn get(&self, mm_or_delta_symbol: &str) -> Result<&ProductMeta> {
        let key = mm_or_delta_symbol.trim().to_uppercase();
        self.by_mm_symbol
            .get(&key)
            .or_else(|| {
                let d = delta_product_symbol(&key);
                self.by_delta_symbol.get(&d)
            })
            .context(format!("unknown Delta product for {mm_or_delta_symbol}"))
    }

    pub fn contracts_for_qty(&self, mm_symbol: &str, qty_base: f64) -> Result<i64> {
        let meta = self.get(mm_symbol)?;
        if meta.contract_value <= 0.0 {
            anyhow::bail!("invalid contract_value");
        }
        let n = (qty_base / meta.contract_value).round();
        if n < 1.0 {
            anyhow::bail!(
                "qty {qty_base} below 1 contract ({} each)",
                meta.contract_value
            );
        }
        Ok(n as i64)
    }

    pub fn base_qty_from_contracts(&self, mm_symbol: &str, contracts: i64) -> f64 {
        self.get(mm_symbol)
            .map(|m| contracts as f64 * m.contract_value)
            .unwrap_or(0.0)
    }
}

fn mm_aliases_for_delta(delta_symbol: &str) -> Vec<String> {
    match delta_symbol {
        "BTCUSD" => vec!["BTCUSD".into(), "BTCUSDT".into()],
        "ETHUSD" => vec!["ETHUSD".into(), "ETHUSDT".into()],
        "SOLUSD" => vec!["SOLUSD".into(), "SOLUSDT".into()],
        other => vec![other.to_string()],
    }
}
