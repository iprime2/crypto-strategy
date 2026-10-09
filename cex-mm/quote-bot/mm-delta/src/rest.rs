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

/// One account fill, reduced to what the taker-fill guard needs.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct FillRole {
    pub id: u64,
    pub taker: bool,
    /// Exchange time, Unix ms.
    pub created_ms: i64,
}

/// `GET /v2/wallet/balances` -> `meta.net_equity` (USD, unrealized PnL included). A missing value
/// is an error, never $0, which would read as a huge loss.
fn parse_net_equity(text: &str) -> Result<f64> {
    let v: serde_json::Value = serde_json::from_str(text).context("wallet json")?;
    if v.get("success").and_then(|s| s.as_bool()) == Some(false) {
        anyhow::bail!("wallet: {}", v.get("error").map(|e| e.to_string()).unwrap_or_default());
    }
    match v.get("meta").and_then(|m| m.get("net_equity")) {
        Some(serde_json::Value::String(s)) => s.parse().context("wallet: net_equity"),
        Some(serde_json::Value::Number(n)) => n.as_f64().context("wallet: net_equity"),
        _ => anyhow::bail!("wallet: no meta.net_equity"),
    }
}

/// `GET /v2/fills` rows -> id, maker/taker, time. Rows without an id or a parsable time are skipped.
fn parse_fill_roles(text: &str) -> Result<Vec<FillRole>> {
    let v: serde_json::Value = serde_json::from_str(text).context("fills json")?;
    if v.get("success").and_then(|s| s.as_bool()) == Some(false) {
        anyhow::bail!("fills: {}", v.get("error").map(|e| e.to_string()).unwrap_or_default());
    }
    let rows = v.get("result").and_then(|r| r.as_array()).cloned().unwrap_or_default();
    Ok(rows
        .iter()
        .filter_map(|row| {
            let id = row.get("id")?.as_u64()?;
            let created = chrono::DateTime::parse_from_rfc3339(row.get("created_at")?.as_str()?).ok()?;
            Some(FillRole {
                id,
                taker: row.get("role").and_then(|r| r.as_str()) == Some("taker"),
                created_ms: created.timestamp_millis(),
            })
        })
        .collect())
}

/// `GET /v2/orders/{id}` -> (`state`, `unfilled_size` in contracts).
fn parse_order_state(text: &str) -> Result<(String, i64)> {
    let v: serde_json::Value = serde_json::from_str(text).context("order json")?;
    if v.get("success").and_then(|s| s.as_bool()) == Some(false) {
        anyhow::bail!("order: {}", v.get("error").map(|e| e.to_string()).unwrap_or_default());
    }
    let r = v.get("result").context("order: no result")?;
    let state = r.get("state").and_then(|s| s.as_str()).context("order: no state")?;
    let unfilled = r.get("unfilled_size").and_then(|u| u.as_i64()).unwrap_or(0);
    Ok((state.to_string(), unfilled))
}

/// `GET /v2/products/{product_id}/orders/leverage` -> `result.leverage` (a string, e.g. `"10"`, in
/// the response ccxt's Delta adapter captured; a number is accepted too). Fails closed: a failed
/// call, a missing or unparsable value, or a non-finite or non-positive one is an error.
fn parse_order_leverage(text: &str) -> Result<f64> {
    let v: serde_json::Value = serde_json::from_str(text).context("leverage json")?;
    if v.get("success").and_then(|s| s.as_bool()) == Some(false) {
        anyhow::bail!("leverage: {}", v.get("error").map(|e| e.to_string()).unwrap_or_default());
    }
    let leverage = match v.get("result").and_then(|r| r.get("leverage")) {
        Some(serde_json::Value::String(s)) => s.trim().parse::<f64>().context("leverage: unparsable")?,
        Some(serde_json::Value::Number(n)) => n.as_f64().context("leverage: not a number")?,
        _ => anyhow::bail!("leverage: no result.leverage"),
    };
    if !leverage.is_finite() || leverage <= 0.0 {
        anyhow::bail!("leverage: invalid value {leverage}");
    }
    Ok(leverage)
}

/// Dead man's switch: cancel all orders on these products when a heartbeat is missed. Schema from
/// Delta's "Deadman Switch" guide (https://docs.delta.exchange/#deadman-switch), not the swagger.
fn heartbeat_create_body(heartbeat_id: &str, delta_symbols: &[String]) -> serde_json::Value {
    json!({
        "heartbeat_id": heartbeat_id,
        "impact": "products",
        "product_symbols": delta_symbols,
        "config": [{ "action": "cancel_orders", "unhealthy_count": 1 }],
    })
}

fn heartbeat_ack_body(heartbeat_id: &str, ttl_ms: u64) -> serde_json::Value {
    json!({ "heartbeat_id": heartbeat_id, "ttl": ttl_ms })
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

    pub async fn get_net_equity_usd(&self) -> Result<f64> {
        let resp = self
            .signed_request(reqwest::Method::GET, "/v2/wallet/balances", "", "")
            .await?;
        parse_net_equity(&resp.text().await?)
    }

    /// Most recent fills on one product, newest first.
    pub async fn recent_fill_roles(&self, mm_symbol: &str, page_size: u32) -> Result<Vec<FillRole>> {
        let meta = self.products.get(mm_symbol)?;
        let query = format!("product_ids={}&page_size={page_size}", meta.product_id);
        let resp = self
            .signed_request(reqwest::Method::GET, "/v2/fills", &query, "")
            .await?;
        parse_fill_roles(&resp.text().await?)
    }

    /// Order state (`open`, `pending`, `closed`, `cancelled`) and unfilled contracts.
    pub async fn order_state(&self, order_id: u64) -> Result<(String, i64)> {
        let path = format!("/v2/orders/{order_id}");
        let resp = self.signed_request(reqwest::Method::GET, &path, "", "").await?;
        parse_order_state(&resp.text().await?)
    }

    /// Order leverage Delta applies to new orders on this product (Delta's default is 100x; the bot
    /// never sets it). Signed `GET /v2/products/{product_id}/orders/leverage`, no query or body, per
    /// Delta's official client `get_order_leverage`
    /// (https://github.com/delta-exchange/python-rest-client/blob/master/delta_rest_client/delta_rest_client.py)
    /// and https://docs.delta.exchange/#get-order-leverage. Response shape from ccxt's `fetchLeverage`
    /// (https://github.com/ccxt/ccxt/blob/master/ts/src/delta.ts).
    pub async fn get_order_leverage(&self, mm_symbol: &str) -> Result<f64> {
        let meta = self.products.get(mm_symbol)?;
        let path = format!("/v2/products/{}/orders/leverage", meta.product_id);
        let resp = self.signed_request(reqwest::Method::GET, &path, "", "").await?;
        parse_order_leverage(&resp.text().await?)
            .with_context(|| format!("{} (product {})", meta.symbol, meta.product_id))
    }

    pub async fn heartbeat_create(&self, heartbeat_id: &str, delta_symbols: &[String]) -> Result<()> {
        let body = heartbeat_create_body(heartbeat_id, delta_symbols).to_string();
        let resp = self
            .signed_request(reqwest::Method::POST, "/v2/heartbeat/create", "", &body)
            .await?;
        Self::expect_success("heartbeat create", resp).await
    }

    /// Re-arms the dead man's switch: Delta cancels the orders if no ack arrives within `ttl_ms`.
    /// `ttl_ms = 0` disables the heartbeat.
    pub async fn heartbeat_ack(&self, heartbeat_id: &str, ttl_ms: u64) -> Result<()> {
        let body = heartbeat_ack_body(heartbeat_id, ttl_ms).to_string();
        let resp = self
            .signed_request(reqwest::Method::POST, "/v2/heartbeat", "", &body)
            .await?;
        Self::expect_success("heartbeat ack", resp).await
    }

    async fn expect_success(what: &str, resp: reqwest::Response) -> Result<()> {
        let text = resp.text().await?;
        let parsed: ApiEnvelope<serde_json::Value> =
            serde_json::from_str(&text).with_context(|| format!("{what} json"))?;
        if parsed.success == Some(false) {
            let msg = parsed.error.and_then(|e| e.message.or(e.code)).unwrap_or(text);
            anyhow::bail!("{what}: {msg}");
        }
        Ok(())
    }

    /// Delta accumulates resting orders if we only place; cancel before replace.
    pub async fn cancel_before_requote(&self, mm_symbol: &str) -> Result<()> {
        self.cancel_all(mm_symbol).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn net_equity_comes_from_meta_and_is_never_guessed() {
        let ok = r#"{"success":true,"meta":{"net_equity":"135.0512"},"result":[]}"#;
        assert_eq!(parse_net_equity(ok).unwrap(), 135.0512);
        let num = r#"{"success":true,"meta":{"net_equity":98.5},"result":[]}"#;
        assert_eq!(parse_net_equity(num).unwrap(), 98.5);
        // Missing or failed reads must error, not read as $0 (which would look like a huge loss).
        assert!(parse_net_equity(r#"{"success":true,"meta":{},"result":[]}"#).is_err());
        assert!(parse_net_equity(r#"{"success":false,"error":{"code":"expired_signature"}}"#).is_err());
        assert!(parse_net_equity("<html>502</html>").is_err());
    }

    #[test]
    fn fill_roles_keep_role_and_time() {
        let text = r#"{"success":true,"result":[
            {"id":1,"role":"maker","created_at":"2026-10-05T10:00:00.250Z","product_symbol":"ADAUSD"},
            {"id":2,"role":"taker","created_at":"2026-10-05T10:00:01Z","product_symbol":"ADAUSD"},
            {"id":3,"created_at":"garbage"}
        ]}"#;
        let rows = parse_fill_roles(text).unwrap();
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[0], FillRole { id: 1, taker: false, created_ms: 1_791_194_400_250 });
        assert_eq!(rows[1], FillRole { id: 2, taker: true, created_ms: 1_791_194_401_000 });
    }

    #[test]
    fn order_state_reads_state_and_unfilled_size() {
        let text = r#"{"success":true,"result":{"id":7,"state":"cancelled","unfilled_size":1,"size":1}}"#;
        assert_eq!(parse_order_state(text).unwrap(), ("cancelled".to_string(), 1));
        assert!(parse_order_state(r#"{"success":false,"error":{"code":"not_found"}}"#).is_err());
    }

    #[test]
    fn order_leverage_reads_string_or_number_and_fails_closed() {
        // Verbatim from ccxt's Delta adapter (fetchLeverage): leverage is a string.
        let ccxt = r#"{"result":{"index_symbol":null,"leverage":"10","margin_mode":"isolated","order_margin":"0","product_id":84,"user_id":30084879},"success":true}"#;
        assert_eq!(parse_order_leverage(ccxt).unwrap(), 10.0);
        let num = r#"{"result":{"leverage":5,"product_id":84},"success":true}"#;
        assert_eq!(parse_order_leverage(num).unwrap(), 5.0);
        // Delta's default order leverage.
        let default = r#"{"result":{"leverage":"100","product_id":84},"success":true}"#;
        assert_eq!(parse_order_leverage(default).unwrap(), 100.0);

        let failed = r#"{"success":false,"error":{"code":"unauthorized","message":"invalid api key"}}"#;
        let err = parse_order_leverage(failed).unwrap_err().to_string();
        assert!(err.contains("unauthorized") && err.contains("invalid api key"), "{err}");
        assert!(parse_order_leverage(r#"{"success":true}"#).is_err());
        assert!(parse_order_leverage(r#"{"success":true,"result":{"product_id":84}}"#).is_err());
        assert!(parse_order_leverage(r#"{"success":true,"result":{"leverage":"ten"}}"#).is_err());
        assert!(parse_order_leverage(r#"{"success":true,"result":{"leverage":null}}"#).is_err());
        assert!(parse_order_leverage(r#"{"success":true,"result":{"leverage":"0"}}"#).is_err());
        assert!(parse_order_leverage(r#"{"success":true,"result":{"leverage":-3}}"#).is_err());
        assert!(parse_order_leverage(r#"{"success":true,"result":{"leverage":"NaN"}}"#).is_err());
        assert!(parse_order_leverage(r#"{"success":true,"result":{"leverage":"inf"}}"#).is_err());
        assert!(parse_order_leverage("<html>502 Bad Gateway</html>").is_err());
    }

    #[test]
    fn heartbeat_bodies_match_the_dead_mans_switch_api() {
        let create = heartbeat_create_body("dism-1", &["ADAUSD".to_string()]);
        assert_eq!(create["heartbeat_id"], "dism-1");
        // Delta's guide: impact is "products" (with product_symbols) or "contracts"; the swagger's
        // low/medium/high is rejected as bad_schema.
        assert_eq!(create["impact"], "products");
        assert_eq!(create["product_symbols"][0], "ADAUSD");
        assert_eq!(create["config"][0]["action"], "cancel_orders");
        assert_eq!(create["config"][0]["unhealthy_count"], 1);
        let ack = heartbeat_ack_body("dism-1", 15_000);
        assert_eq!(ack["heartbeat_id"], "dism-1");
        assert_eq!(ack["ttl"], 15_000);
    }
}
