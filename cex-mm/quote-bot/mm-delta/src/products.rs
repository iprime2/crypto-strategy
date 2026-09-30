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
    meta: Option<PageMeta>,
}

#[derive(Debug, Deserialize)]
struct PageMeta {
    after: Option<String>,
}

/// Mainnet lists 220+ perpetuals; one page of 200 misses alts such as ADAUSD.
const MAX_PRODUCT_PAGES: usize = 20;

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
        let mut rows = Vec::new();
        let mut after: Option<String> = None;
        for _ in 0..MAX_PRODUCT_PAGES {
            let mut query = vec![
                ("contract_types", "perpetual_futures".to_string()),
                ("page_size", "200".to_string()),
            ];
            if let Some(cursor) = &after {
                query.push(("after", cursor.clone()));
            }
            let resp: ProductsResponse = client
                .get(format!("{base_url}/v2/products"))
                .query(&query)
                .header("User-Agent", "mm-delta/0.1")
                .send()
                .await
                .context("products request")?
                .json()
                .await
                .context("products json")?;
            let page = resp.result.unwrap_or_default();
            let page_len = page.len();
            rows.extend(page);
            after = resp.meta.and_then(|m| m.after);
            if after.is_none() || page_len == 0 {
                break;
            }
        }
        Ok(Self::from_rows(rows))
    }

    fn from_rows(rows: Vec<ProductRow>) -> Self {
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
        Self {
            by_mm_symbol,
            by_delta_symbol,
        }
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

#[cfg(test)]
mod tests {
    use super::*;

    fn row(id: u64, symbol: &str, tick: &str, cv: &str, state: &str) -> ProductRow {
        ProductRow {
            id,
            symbol: symbol.into(),
            tick_size: tick.into(),
            contract_value: cv.into(),
            contract_type: Some("perpetual_futures".into()),
            state: Some(state.into()),
        }
    }

    #[test]
    fn alt_perp_resolves_from_mm_symbol() {
        let cat = ProductCatalog::from_rows(vec![
            row(1, "ETHUSD", "0.05", "0.01", "live"),
            row(2, "ADAUSD", "0.00001", "10", "live"),
        ]);
        let ada = cat.get("ADAUSDT").expect("ADAUSDT resolves");
        assert_eq!(ada.symbol, "ADAUSD");
        assert_eq!(ada.tick_size, 0.00001);
        assert_eq!(ada.contract_value, 10.0);
        assert_eq!(cat.get("ETHUSDT").unwrap().product_id, 1);
    }

    #[test]
    fn non_live_products_are_skipped() {
        let cat = ProductCatalog::from_rows(vec![row(3, "NEARUSD", "0.001", "1", "expired")]);
        assert!(cat.get("NEARUSDT").is_err());
    }

    #[test]
    fn page_cursor_is_read_from_meta() {
        let body = r#"{"success":true,"result":[],"meta":{"after":"abc+/=","limit":200}}"#;
        let resp: ProductsResponse = serde_json::from_str(body).unwrap();
        assert_eq!(resp.meta.and_then(|m| m.after).as_deref(), Some("abc+/="));
        let last = r#"{"success":true,"result":[],"meta":{"after":null}}"#;
        let resp: ProductsResponse = serde_json::from_str(last).unwrap();
        assert!(resp.meta.and_then(|m| m.after).is_none());
    }
}
