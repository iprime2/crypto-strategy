use anyhow::{Context, Result};
use reqwest::Client;
use serde::Deserialize;
use serde_json::json;

use crate::auth::BybitCredentials;
use crate::BybitEnvironment;

#[derive(Clone)]
pub struct BybitRest {
    client: Client,
    pub env: BybitEnvironment,
    pub creds: BybitCredentials,
}

#[derive(Debug, Deserialize)]
pub struct ApiResponse<T> {
    #[serde(rename = "retCode")]
    pub ret_code: i32,
    #[serde(rename = "retMsg")]
    pub ret_msg: String,
    pub result: Option<T>,
}

#[derive(Debug, Deserialize)]
pub struct InstrumentInfo {
    #[serde(rename = "priceFilter")]
    pub price_filter: PriceFilter,
    #[serde(rename = "lotSizeFilter")]
    pub lot_size_filter: LotSizeFilter,
}

#[derive(Debug, Deserialize)]
pub struct PriceFilter {
    #[serde(rename = "tickSize")]
    pub tick_size: String,
}

#[derive(Debug, Deserialize)]
pub struct LotSizeFilter {
    #[serde(rename = "qtyStep")]
    pub qty_step: String,
    #[serde(rename = "minOrderQty")]
    pub min_order_qty: String,
}

#[derive(Debug, Deserialize)]
pub struct InstrumentsResult {
    pub list: Vec<InstrumentRow>,
}

#[derive(Debug, Deserialize)]
pub struct InstrumentRow {
    pub symbol: String,
    #[serde(rename = "priceFilter")]
    pub price_filter: PriceFilter,
    #[serde(rename = "lotSizeFilter")]
    pub lot_size_filter: LotSizeFilter,
}

#[derive(Debug, Deserialize)]
pub struct PositionList {
    pub list: Vec<PositionRow>,
}

#[derive(Debug, Deserialize)]
pub struct PositionRow {
    pub symbol: String,
    pub size: String,
    pub side: String,
}

impl BybitRest {
    pub fn new(env: BybitEnvironment, creds: BybitCredentials) -> Self {
        Self {
            client: Client::new(),
            env,
            creds,
        }
    }

    fn ts() -> String {
        chrono::Utc::now().timestamp_millis().to_string()
    }

    pub async fn get_instrument(&self, symbol: &str) -> Result<(f64, f64, f64)> {
        let url = format!(
            "{}/v5/market/instruments-info?category=linear&symbol={symbol}",
            self.env.rest_base()
        );
        let resp: ApiResponse<InstrumentsResult> = self
            .client
            .get(&url)
            .send()
            .await
            .context("instruments request")?
            .json()
            .await
            .context("instruments json")?;
        if resp.ret_code != 0 {
            anyhow::bail!("instruments {}: {}", resp.ret_code, resp.ret_msg);
        }
        let row = resp
            .result
            .and_then(|r| r.list.into_iter().next())
            .context("no instrument")?;
        let tick: f64 = row.price_filter.tick_size.parse().unwrap_or(0.01);
        let step: f64 = row.lot_size_filter.qty_step.parse().unwrap_or(0.001);
        let min_qty: f64 = row.lot_size_filter.min_order_qty.parse().unwrap_or(step);
        Ok((tick, step, min_qty))
    }

    pub async fn get_position(&self, symbol: &str) -> Result<f64> {
        let query = format!("category=linear&symbol={symbol}");
        let ts = Self::ts();
        let recv = "5000";
        let sign = self.creds.sign_get(&query, &ts, recv);
        let url = format!("{}/v5/position/list?{query}", self.env.rest_base());
        let resp: ApiResponse<PositionList> = self
            .client
            .get(&url)
            .header("X-BAPI-API-KEY", &self.creds.api_key)
            .header("X-BAPI-SIGN", sign)
            .header("X-BAPI-TIMESTAMP", ts)
            .header("X-BAPI-RECV-WINDOW", recv)
            .send()
            .await?
            .json()
            .await?;
        if resp.ret_code != 0 {
            anyhow::bail!("position {}: {}", resp.ret_code, resp.ret_msg);
        }
        let list = resp.result.map(|r| r.list).unwrap_or_default();
        let mut net = 0.0_f64;
        for p in list {
            let sz: f64 = p.size.parse().unwrap_or(0.0);
            if p.side.eq_ignore_ascii_case("Buy") {
                net += sz;
            } else {
                net -= sz;
            }
        }
        Ok(net)
    }

    pub async fn cancel_all(&self, symbol: &str) -> Result<()> {
        let body = json!({
            "category": "linear",
            "symbol": symbol,
        });
        let body_str = body.to_string();
        let ts = Self::ts();
        let recv = "5000";
        let sign = self.creds.sign_post(&body_str, &ts, recv);
        let url = format!("{}/v5/order/cancel-all", self.env.rest_base());
        let resp: ApiResponse<serde_json::Value> = self
            .client
            .post(url)
            .header("X-BAPI-API-KEY", &self.creds.api_key)
            .header("X-BAPI-SIGN", sign)
            .header("X-BAPI-TIMESTAMP", ts)
            .header("X-BAPI-RECV-WINDOW", recv)
            .header("Content-Type", "application/json")
            .body(body_str)
            .send()
            .await?
            .json()
            .await?;
        if resp.ret_code != 0 {
            anyhow::bail!("cancel-all {}: {}", resp.ret_code, resp.ret_msg);
        }
        Ok(())
    }

    pub async fn get_funding_carry_bps(&self, symbol: &str, position: f64) -> Result<f64> {
        let url = format!(
            "{}/v5/market/tickers?category=linear&symbol={symbol}",
            self.env.rest_base()
        );
        let resp: ApiResponse<serde_json::Value> = self.client.get(&url).send().await?.json().await?;
        if resp.ret_code != 0 {
            anyhow::bail!("tickers {}: {}", resp.ret_code, resp.ret_msg);
        }
        let rate_str = resp
            .result
            .and_then(|r| r.get("list")?.as_array()?.first()?.get("fundingRate")?.as_str().map(String::from))
            .unwrap_or_else(|| "0".to_string());
        let rate: f64 = rate_str.parse().unwrap_or(0.0);
        Ok(-position * rate * 10_000.0)
    }

    pub async fn amend_batch(
        &self,
        symbol: &str,
        orders: &[(String, f64, f64)],
    ) -> Result<()> {
        let mut batch = Vec::new();
        for (link_id, qty, price) in orders {
            batch.push(json!({
                "symbol": symbol,
                "orderLinkId": link_id,
                "qty": format!("{qty:.8}"),
                "price": format!("{price:.8}"),
            }));
        }
        let body = json!({
            "category": "linear",
            "request": batch,
        });
        let body_str = body.to_string();
        let ts = Self::ts();
        let recv = "5000";
        let sign = self.creds.sign_post(&body_str, &ts, recv);
        let url = format!("{}/v5/order/amend-batch", self.env.rest_base());
        let resp: ApiResponse<serde_json::Value> = self
            .client
            .post(url)
            .header("X-BAPI-API-KEY", &self.creds.api_key)
            .header("X-BAPI-SIGN", sign)
            .header("X-BAPI-TIMESTAMP", ts)
            .header("X-BAPI-RECV-WINDOW", recv)
            .header("Content-Type", "application/json")
            .body(body_str)
            .send()
            .await?
            .json()
            .await?;
        if resp.ret_code != 0 {
            anyhow::bail!("amend-batch {}: {}", resp.ret_code, resp.ret_msg);
        }
        Ok(())
    }

    pub async fn place_limit_post_only(
        &self,
        symbol: &str,
        side: &str,
        qty: f64,
        price: f64,
        order_link_id: &str,
    ) -> Result<()> {
        self.place_limit(
            symbol,
            side,
            qty,
            price,
            order_link_id,
            "PostOnly",
            /* reduce_only */ false,
        )
        .await
    }

    /// IOC limit at the given price with `reduceOnly=true` (not post-only).
    pub async fn place_reduce_only(
        &self,
        symbol: &str,
        side: &str,
        qty: f64,
        price: f64,
        order_link_id: &str,
    ) -> Result<()> {
        self.place_limit(
            symbol,
            side,
            qty,
            price,
            order_link_id,
            "IOC",
            /* reduce_only */ true,
        )
        .await
    }

    async fn place_limit(
        &self,
        symbol: &str,
        side: &str,
        qty: f64,
        price: f64,
        order_link_id: &str,
        time_in_force: &str,
        reduce_only: bool,
    ) -> Result<()> {
        let mut body = json!({
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "qty": format!("{qty:.8}"),
            "price": format!("{price:.8}"),
            "timeInForce": time_in_force,
            "orderLinkId": order_link_id,
        });
        if reduce_only {
            body["reduceOnly"] = json!(true);
        }
        let body_str = body.to_string();
        let ts = Self::ts();
        let recv = "5000";
        let sign = self.creds.sign_post(&body_str, &ts, recv);
        let url = format!("{}/v5/order/create", self.env.rest_base());
        let resp: ApiResponse<serde_json::Value> = self
            .client
            .post(url)
            .header("X-BAPI-API-KEY", &self.creds.api_key)
            .header("X-BAPI-SIGN", sign)
            .header("X-BAPI-TIMESTAMP", ts)
            .header("X-BAPI-RECV-WINDOW", recv)
            .header("Content-Type", "application/json")
            .body(body_str)
            .send()
            .await?
            .json()
            .await?;
        if resp.ret_code != 0 {
            anyhow::bail!("place {}: {}", resp.ret_code, resp.ret_msg);
        }
        Ok(())
    }
}
