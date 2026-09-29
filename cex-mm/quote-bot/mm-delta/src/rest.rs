use anyhow::{Context, Result};
use reqwest::Client;
use serde::Deserialize;
use serde_json::json;
use std::sync::Arc;

use crate::auth::DeltaCredentials;
use crate::products::ProductCatalog;
use crate::DeltaEnvironment;

#[derive(Clone)]
pub struct DeltaRest {
    client: Client,
    pub env: DeltaEnvironment,
    pub creds: DeltaCredentials,
    pub products: Arc<ProductCatalog>,
}

#[derive(Debug, Deserialize)]
struct ApiEnvelope<T> {
    success: Option<bool>,
    error: Option<ApiError>,
    result: Option<T>,
}

#[derive(Debug, Deserialize)]
struct ApiError {
    code: Option<String>,
    message: Option<String>,
}

#[derive(Debug, Deserialize)]
struct PositionRow {
    size: i64,
    product_symbol: Option<String>,
}

#[derive(Debug, Deserialize)]
struct TickerRow {
    symbol: Option<String>,
    funding_rate: Option<String>,
}

impl DeltaRest {
    pub fn new(env: DeltaEnvironment, creds: DeltaCredentials, products: Arc<ProductCatalog>) -> Self {
        Self {
            client: Client::new(),
            env,
            creds,
            products,
        }
    }

    fn ts() -> String {
        (chrono::Utc::now().timestamp()).to_string()
    }

    async fn signed_request(
        &self,
        method: reqwest::Method,
        path: &str,
        query: &str,
        body: &str,
    ) -> Result<reqwest::Response> {
        let timestamp = Self::ts();
        let query_string = if query.is_empty() {
            String::new()
        } else {
            format!("?{query}")
        };
        let sign = self.creds.sign_rest(
            method.as_str(),
            &timestamp,
            path,
            &query_string,
            body,
        );
        let url = format!("{}{path}{query_string}", self.env.rest_base());
        let mut req = self
            .client
            .request(method, url)
            .header("api-key", &self.creds.api_key)
            .header("timestamp", &timestamp)
            .header("signature", sign)
            .header("User-Agent", "mm-delta/0.1")
            .header("Accept", "application/json");
        if !body.is_empty() {
            req = req
                .header("Content-Type", "application/json")
                .body(body.to_string());
        }
        req.send().await.context("delta signed request")
    }

    pub async fn get_instrument(&self, mm_symbol: &str) -> Result<(f64, f64, f64)> {
        let meta = self.products.get(mm_symbol)?;
        Ok((meta.tick_size, meta.contract_value, meta.contract_value))
    }

    pub async fn get_position(&self, mm_symbol: &str) -> Result<f64> {
        let meta = self.products.get(mm_symbol)?;
        let query = format!("product_ids={}", meta.product_id);
        let resp = self
            .signed_request(reqwest::Method::GET, "/v2/positions/margined", &query, "")
            .await?;
        let text = resp.text().await?;
        let parsed: ApiEnvelope<Vec<PositionRow>> =
            serde_json::from_str(&text).context("positions json")?;
        if parsed.success == Some(false) {
            let msg = parsed
                .error
                .and_then(|e| e.message)
                .unwrap_or_else(|| "positions error".into());
            anyhow::bail!("{msg}");
        }
        let rows = parsed.result.unwrap_or_default();
        let contracts = rows
            .into_iter()
            .find(|r| {
                r.product_symbol
                    .as_deref()
                    .map(|s| s.eq_ignore_ascii_case(&meta.symbol))
                    .unwrap_or(true)
            })
            .map(|r| r.size)
            .unwrap_or(0);
        Ok(self.products.base_qty_from_contracts(mm_symbol, contracts))
    }

    pub async fn cancel_all(&self, mm_symbol: &str) -> Result<()> {
        let meta = self.products.get(mm_symbol)?;
        let body = json!({
            "product_id": meta.product_id,
            "cancel_limit_orders": true,
            "cancel_stop_orders": true
        })
        .to_string();
        let resp = self
            .signed_request(reqwest::Method::DELETE, "/v2/orders/all", "", &body)
            .await?;
        let text = resp.text().await?;
        let parsed: ApiEnvelope<serde_json::Value> =
            serde_json::from_str(&text).unwrap_or(ApiEnvelope {
                success: Some(true),
                error: None,
                result: None,
            });
        if parsed.success == Some(false) {
            let msg = parsed
                .error
                .and_then(|e| e.message)
                .unwrap_or_else(|| text);
            anyhow::bail!("cancel-all: {msg}");
        }
        Ok(())
    }

    pub async fn get_funding_carry_bps(&self, mm_symbol: &str, position: f64) -> Result<f64> {
        let meta = self.products.get(mm_symbol)?;
        let url = format!(
            "{}/v2/tickers/{}",
            self.env.rest_base(),
            meta.symbol
        );
        let resp: ApiEnvelope<TickerRow> = self
            .client
            .get(&url)
            .header("User-Agent", "mm-delta/0.1")
            .send()
            .await?
            .json()
            .await?;
        let rate: f64 = resp
            .result
            .and_then(|r| r.funding_rate)
            .and_then(|s| s.parse().ok())
            .unwrap_or(0.0);
        Ok(-position * rate * 10_000.0)
    }

    /// Returns the Delta order id when the response includes one.
    pub async fn place_limit_post_only(
        &self,
        mm_symbol: &str,
        side: &str,
        qty_base: f64,
        price: f64,
        link_id: &str,
    ) -> Result<Option<u64>> {
        self.place_limit(
            mm_symbol,
            side,
            qty_base,
            price,
            link_id,
            /* post_only */ true,
            /* reduce_only */ false,
            "gtc",
        )
        .await
    }

    /// IOC limit at the given price; `reduce_only=true`, not post-only.
    pub async fn place_reduce_only(
        &self,
        mm_symbol: &str,
        side: &str,
        qty_base: f64,
        price: f64,
        link_id: &str,
    ) -> Result<()> {
        self.place_limit(
            mm_symbol,
            side,
            qty_base,
            price,
            link_id,
            /* post_only */ false,
            /* reduce_only */ true,
            "ioc",
        )
        .await
        .map(|_| ())
    }

    /// Move a resting post-only order to a new price and size.
    pub async fn edit_post_only(
        &self,
        mm_symbol: &str,
        order_id: u64,
        qty_base: f64,
        price: f64,
    ) -> Result<()> {
        let meta = self.products.get(mm_symbol)?;
        let size = self.products.contracts_for_qty(mm_symbol, qty_base)?;
        let body = json!({
            "id": order_id,
            "product_id": meta.product_id,
            "limit_price": format!("{price}"),
            "size": size,
            "post_only": "true",
        })
        .to_string();
        let resp = self
            .signed_request(reqwest::Method::PUT, "/v2/orders", "", &body)
            .await?;
        let text = resp.text().await?;
        let parsed: ApiEnvelope<serde_json::Value> =
            serde_json::from_str(&text).context("edit order json")?;
        if parsed.success == Some(false) {
            let msg = parsed
                .error
                .and_then(|e| e.message.or(e.code))
                .unwrap_or(text);
            anyhow::bail!("edit: {msg}");
        }
        Ok(())
    }

    pub async fn cancel_order(&self, mm_symbol: &str, order_id: u64) -> Result<()> {
        let meta = self.products.get(mm_symbol)?;
        let body = json!({ "id": order_id, "product_id": meta.product_id }).to_string();
        let resp = self
            .signed_request(reqwest::Method::DELETE, "/v2/orders", "", &body)
            .await?;
        let text = resp.text().await?;
        let parsed: ApiEnvelope<serde_json::Value> =
            serde_json::from_str(&text).context("cancel order json")?;
        if parsed.success == Some(false) {
            let msg = parsed
                .error
                .and_then(|e| e.message.or(e.code))
                .unwrap_or(text);
            anyhow::bail!("cancel: {msg}");
        }
        Ok(())
    }

    async fn place_limit(
        &self,
        mm_symbol: &str,
        side: &str,
        qty_base: f64,
        price: f64,
        link_id: &str,
        post_only: bool,
        reduce_only: bool,
        time_in_force: &str,
    ) -> Result<Option<u64>> {
        let meta = self.products.get(mm_symbol)?;
        let size = self.products.contracts_for_qty(mm_symbol, qty_base)?;
        let side = if side.eq_ignore_ascii_case("buy") {
            "buy"
        } else {
            "sell"
        };
        let body = json!({
            "product_id": meta.product_id,
            "size": size,
            "side": side,
            "order_type": "limit_order",
            "limit_price": format!("{price}"),
            "time_in_force": time_in_force,
            "post_only": post_only,
            "client_order_id": link_id,
            "reduce_only": reduce_only,
        });
        let body_str = body.to_string();
        let resp = self
            .signed_request(reqwest::Method::POST, "/v2/orders", "", &body_str)
            .await?;
        let text = resp.text().await?;
        let parsed: ApiEnvelope<serde_json::Value> =
            serde_json::from_str(&text).context("place order json")?;
        if parsed.success == Some(false) {
            let msg = parsed
                .error
                .and_then(|e| e.message)
                .unwrap_or(text);
            anyhow::bail!("place: {msg}");
        }
        Ok(parsed
            .result
            .as_ref()
            .and_then(|r| r.get("id"))
            .and_then(|v| v.as_u64()))
    }

    /// Delta accumulates resting orders if we only place; cancel before replace.
    pub async fn cancel_before_requote(&self, mm_symbol: &str) -> Result<()> {
        self.cancel_all(mm_symbol).await
    }
}
