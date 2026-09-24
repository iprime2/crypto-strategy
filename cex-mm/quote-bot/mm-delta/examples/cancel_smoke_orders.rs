//! Cancel resting orders tagged with client_order_id prefix `smoke-` (does not touch MM bot orders).
use anyhow::{bail, Context, Result};
use mm_delta::{DeltaCredentials, DeltaEnvironment, ProductCatalog};
use reqwest::Client;
use serde::Deserialize;
use serde_json::json;
use std::sync::Arc;

#[derive(Debug, Deserialize)]
struct OrdersEnvelope {
    success: Option<bool>,
    result: Option<Vec<OrderRow>>,
}

#[derive(Debug, Deserialize)]
struct OrderRow {
    id: u64,
    client_order_id: Option<String>,
    product_id: Option<u64>,
}

async fn signed(
    client: &Client,
    creds: &DeltaCredentials,
    base: &str,
    method: &str,
    path: &str,
    query: &str,
    body: &str,
) -> Result<String> {
    let ts = (chrono::Utc::now().timestamp()).to_string();
    let qs = if query.is_empty() {
        String::new()
    } else {
        format!("?{query}")
    };
    let sign = creds.sign_rest(method, &ts, path, &qs, body);
    let url = format!("{base}{path}{qs}");
    let http_method = match method {
        "GET" => reqwest::Method::GET,
        "DELETE" => reqwest::Method::DELETE,
        "POST" => reqwest::Method::POST,
        other => bail!("unsupported method {other}"),
    };
    let mut req = client.request(http_method, url)
        .header("api-key", &creds.api_key)
        .header("timestamp", &ts)
        .header("signature", sign)
        .header("Accept", "application/json")
        .header("User-Agent", "mm-delta-smoke/0.1");
    if !body.is_empty() {
        req = req.header("Content-Type", "application/json").body(body.to_string());
    }
    let resp = req.send().await?;
    let status = resp.status();
    let text = resp.text().await?;
    if !status.is_success() {
        bail!("HTTP {} — {text}", status.as_u16());
    }
    Ok(text)
}

#[tokio::main]
async fn main() -> Result<()> {
    dotenvy::dotenv().ok();
    let mm_symbol = std::env::var("MM_SYMBOL").unwrap_or_else(|_| "BTCUSDT".into());
    let env = DeltaEnvironment::from_env_flag(
        &std::env::var("MM_ENV").unwrap_or_else(|_| "testnet".into()),
    );
    let creds = DeltaCredentials::from_env().context("DELTA_API_KEY/SECRET")?;
    let client = Client::new();
    let products = Arc::new(ProductCatalog::load(&client, env.rest_base()).await?);
    let pid = products.get(&mm_symbol)?.product_id;
    let base = env.rest_base();

    let query = format!("product_id={pid}&state=open");
    let text = signed(&client, &creds, base, "GET", "/v2/orders", &query, "").await?;
    let parsed: OrdersEnvelope = serde_json::from_str(&text)?;
    let rows = parsed.result.unwrap_or_default();
    let smoke: Vec<_> = rows
        .into_iter()
        .filter(|o| {
            o.client_order_id
                .as_deref()
                .is_some_and(|c| c.starts_with("smoke-"))
        })
        .collect();

    if smoke.is_empty() {
        println!("No open smoke-test orders for {mm_symbol} (product_id={pid})");
        return Ok(());
    }

    for o in smoke {
        let id = o.id;
        let body = json!({ "id": id, "product_id": pid }).to_string();
        signed(&client, &creds, base, "DELETE", "/v2/orders", "", &body).await?;
        println!("Canceled smoke order id={id}");
    }
    Ok(())
}
