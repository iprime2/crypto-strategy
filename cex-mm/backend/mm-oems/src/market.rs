//! Public Delta market data (ticker, book, trades, candles) for the trader UI.
//!
//! The browser cannot call Delta directly (no CORS headers), so the OEMS proxies
//! and normalizes it. Sizes are converted from contracts to base units. Responses
//! are cached briefly so several open tabs do not multiply venue load.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};

use serde_json::{json, Value};
use tokio::sync::RwLock;

use crate::delta::{delta_symbol_for, f64_of, fetch_catalog, http_client, ProductInfo};

#[derive(Clone)]
pub struct Market {
    http: reqwest::Client,
    base: String,
    cache: Arc<RwLock<HashMap<String, (Instant, Value)>>>,
    catalog: Arc<RwLock<Option<(Instant, HashMap<String, ProductInfo>)>>>,
}

const CATALOG_TTL: Duration = Duration::from_secs(3600);

impl Market {
    pub fn new(base: &str) -> Self {
        Self {
            http: http_client(),
            base: base.trim_end_matches('/').to_string(),
            cache: Arc::new(RwLock::new(HashMap::new())),
            catalog: Arc::new(RwLock::new(None)),
        }
    }

    pub async fn product(&self, mm_symbol: &str) -> anyhow::Result<ProductInfo> {
        let delta_sym = delta_symbol_for(mm_symbol);
        {
            let g = self.catalog.read().await;
            if let Some((at, cat)) = g.as_ref() {
                if at.elapsed() < CATALOG_TTL {
                    if let Some(p) = cat.get(&delta_sym) {
                        return Ok(p.clone());
                    }
                }
            }
        }
        let cat = fetch_catalog(&self.http, &self.base).await?;
        let found = cat.get(&delta_sym).cloned();
        *self.catalog.write().await = Some((Instant::now(), cat));
        found.ok_or_else(|| anyhow::anyhow!("unknown Delta product {delta_sym}"))
    }

    async fn cached<F, Fut>(&self, key: String, ttl: Duration, fetch: F) -> anyhow::Result<Value>
    where
        F: FnOnce() -> Fut,
        Fut: std::future::Future<Output = anyhow::Result<Value>>,
    {
        if let Some((at, v)) = self.cache.read().await.get(&key) {
            if at.elapsed() < ttl {
                return Ok(v.clone());
            }
        }
        let v = fetch().await?;
        let mut g = self.cache.write().await;
        if g.len() > 512 {
            g.retain(|_, (at, _)| at.elapsed() < Duration::from_secs(60));
        }
        g.insert(key, (Instant::now(), v.clone()));
        Ok(v)
    }

    async fn get_json(&self, path_and_query: &str) -> anyhow::Result<Value> {
        let v: Value = self
            .http
            .get(format!("{}{}", self.base, path_and_query))
            .send()
            .await?
            .json()
            .await?;
        if v.get("success").and_then(|s| s.as_bool()) == Some(false) {
            anyhow::bail!("delta error: {}", v.get("error").cloned().unwrap_or(Value::Null));
        }
        Ok(v)
    }

    pub async fn ticker(&self, mm_symbol: &str) -> anyhow::Result<Value> {
        let sym = delta_symbol_for(mm_symbol);
        let key = format!("ticker:{sym}");
        let this = self.clone();
        let mm = mm_symbol.to_uppercase();
        self.cached(key, Duration::from_millis(900), move || async move {
            let raw = this.get_json(&format!("/v2/tickers/{sym}")).await?;
            Ok(normalize_ticker(&mm, raw.get("result").unwrap_or(&Value::Null)))
        })
        .await
    }

    pub async fn book(&self, mm_symbol: &str, depth: u32) -> anyhow::Result<Value> {
        let product = self.product(mm_symbol).await?;
        let sym = product.symbol.clone();
        let depth = depth.clamp(1, 50);
        let key = format!("book:{sym}:{depth}");
        let this = self.clone();
        self.cached(key, Duration::from_millis(900), move || async move {
            let raw = this.get_json(&format!("/v2/l2orderbook/{sym}?depth={depth}")).await?;
            Ok(normalize_book(raw.get("result").unwrap_or(&Value::Null), product.contract_value))
        })
        .await
    }

    pub async fn trades(&self, mm_symbol: &str) -> anyhow::Result<Value> {
        let product = self.product(mm_symbol).await?;
        let sym = product.symbol.clone();
        let key = format!("trades:{sym}");
        let this = self.clone();
        self.cached(key, Duration::from_millis(1500), move || async move {
            let raw = this.get_json(&format!("/v2/trades/{sym}")).await?;
            Ok(normalize_trades(raw.get("result").unwrap_or(&Value::Null), product.contract_value))
        })
        .await
    }

    pub async fn candles(&self, mm_symbol: &str, resolution: &str, start: i64, end: i64) -> anyhow::Result<Value> {
        const RESOLUTIONS: [&str; 7] = ["1m", "3m", "5m", "15m", "1h", "4h", "1d"];
        if !RESOLUTIONS.contains(&resolution) {
            anyhow::bail!("resolution must be one of {RESOLUTIONS:?}");
        }
        let sym = delta_symbol_for(mm_symbol);
        // Round the window so the cache key is stable across polls.
        let end_r = end - end.rem_euclid(5);
        let key = format!("candles:{sym}:{resolution}:{start}:{end_r}");
        let this = self.clone();
        let res = resolution.to_string();
        self.cached(key, Duration::from_secs(4), move || async move {
            let raw = this
                .get_json(&format!(
                    "/v2/history/candles?resolution={res}&symbol={sym}&start={start}&end={end}"
                ))
                .await?;
            Ok(normalize_candles(raw.get("result").unwrap_or(&Value::Null)))
        })
        .await
    }
}

pub fn normalize_ticker(mm_symbol: &str, r: &Value) -> Value {
    let q = r.get("quotes").cloned().unwrap_or(Value::Null);
    let bid = f64_of(q.get("best_bid"));
    let ask = f64_of(q.get("best_ask"));
    let mid = if bid > 0.0 && ask > 0.0 { (bid + ask) / 2.0 } else { 0.0 };
    json!({
        "symbol": mm_symbol,
        "venue_symbol": r.get("symbol"),
        "mark": f64_of(r.get("mark_price")),
        "spot": f64_of(r.get("spot_price")),
        "last": f64_of(r.get("close")),
        "open_24h": f64_of(r.get("open")),
        "high_24h": f64_of(r.get("high")),
        "low_24h": f64_of(r.get("low")),
        "change_24h_pct": f64_of(r.get("mark_change_24h")),
        "turnover_24h_usd": f64_of(r.get("turnover_usd")),
        "oi_usd": f64_of(r.get("oi_value_usd")),
        "funding_rate_pct": f64_of(r.get("funding_rate")),
        "best_bid": bid,
        "best_ask": ask,
        "spread_bps": if mid > 0.0 { (ask - bid) / mid * 1e4 } else { 0.0 },
        "tick_size": f64_of(r.get("tick_size")),
        "ts": r.get("timestamp"),
    })
}

pub fn normalize_book(r: &Value, contract_value: f64) -> Value {
    let cv = if contract_value > 0.0 { contract_value } else { 1.0 };
    let side = |key: &str| -> Vec<Value> {
        r.get(key)
            .and_then(|v| v.as_array())
            .map(|rows| {
                rows.iter()
                    .map(|l| json!([f64_of(l.get("price")), f64_of(l.get("size")) * cv]))
                    .collect()
            })
            .unwrap_or_default()
    };
    json!({ "bids": side("buy"), "asks": side("sell"), "ts": chrono::Utc::now().timestamp_millis() })
}

pub fn normalize_trades(r: &Value, contract_value: f64) -> Value {
    let cv = if contract_value > 0.0 { contract_value } else { 1.0 };
    let rows = r.as_array().cloned().unwrap_or_default();
    Value::Array(
        rows.iter()
            .map(|t| {
                let buyer_taker = t.get("buyer_role").and_then(|s| s.as_str()) == Some("taker");
                json!({
                    "ts": t.get("timestamp").and_then(|v| v.as_i64()).map(|us| us / 1000),
                    "price": f64_of(t.get("price")),
                    "size": f64_of(t.get("size")) * cv,
                    "side": if buyer_taker { "buy" } else { "sell" },
                })
            })
            .collect(),
    )
}

pub fn normalize_candles(r: &Value) -> Value {
    let mut rows: Vec<Value> = r
        .as_array()
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .map(|c| {
            json!({
                "time": c.get("time").and_then(|t| t.as_i64()).unwrap_or(0),
                "open": f64_of(c.get("open")),
                "high": f64_of(c.get("high")),
                "low": f64_of(c.get("low")),
                "close": f64_of(c.get("close")),
                "volume": f64_of(c.get("volume")),
            })
        })
        .collect();
    rows.sort_by_key(|c| c.get("time").and_then(|t| t.as_i64()).unwrap_or(0));
    rows.dedup_by_key(|c| c.get("time").and_then(|t| t.as_i64()).unwrap_or(0));
    Value::Array(rows)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn book_sizes_are_base_units() {
        let r = json!({"buy": [{"price": "2734.65", "size": 2313}], "sell": [{"price": "2734.70", "size": 380}]});
        let b = normalize_book(&r, 0.01);
        assert_eq!(b["bids"][0][0], 2734.65);
        assert!((b["bids"][0][1].as_f64().unwrap() - 23.13).abs() < 1e-9);
        assert!((b["asks"][0][1].as_f64().unwrap() - 3.8).abs() < 1e-9);
    }

    #[test]
    fn trades_mark_aggressor_side() {
        let r = json!([
            {"size": 32, "timestamp": 1790686485000000i64, "price": "2733.75", "buyer_role": "taker"},
            {"size": 10, "timestamp": 1790686480000000i64, "price": "2734.05", "buyer_role": "maker"}
        ]);
        let t = normalize_trades(&r, 0.01);
        assert_eq!(t[0]["side"], "buy");
        assert_eq!(t[1]["side"], "sell");
        assert_eq!(t[0]["ts"], 1790686485000i64);
        assert!((t[0]["size"].as_f64().unwrap() - 0.32).abs() < 1e-12);
    }

    #[test]
    fn candles_sorted_ascending_without_duplicates() {
        let r = json!([
            {"time": 120, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 3},
            {"time": 60, "open": 1, "high": 2, "low": 0.5, "close": 1.2, "volume": 3},
            {"time": 120, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 3}
        ]);
        let c = normalize_candles(&r);
        assert_eq!(c.as_array().unwrap().len(), 2);
        assert_eq!(c[0]["time"], 60);
    }

    #[test]
    fn ticker_spread_in_bps() {
        let r = json!({"mark_price": "2734.97", "quotes": {"best_bid": "2734.7", "best_ask": "2734.75"}, "funding_rate": "0.01"});
        let t = normalize_ticker("ETHUSDT", &r);
        let spread = t["spread_bps"].as_f64().unwrap();
        assert!((spread - 0.1828).abs() < 1e-3, "{spread}");
        assert_eq!(t["funding_rate_pct"], 0.01);
    }
}
