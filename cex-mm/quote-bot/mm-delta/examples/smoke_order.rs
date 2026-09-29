//! One post-only limit well off the touch, then cancel. Validates API key + IP whitelist.
use anyhow::{bail, Context, Result};
use mm_delta::{delta_product_symbol, DeltaCredentials, DeltaEnvironment, DeltaRest, ProductCatalog};
use reqwest::Client;
use serde::Deserialize;
use std::sync::Arc;

#[derive(Debug, Deserialize)]
struct ErrBody {
    success: Option<bool>,
    error: Option<ErrDetail>,
}

#[derive(Debug, Deserialize)]
struct ErrDetail {
    code: Option<String>,
    message: Option<String>,
}

async fn signed_get_text(
    client: &Client,
    creds: &DeltaCredentials,
    base: &str,
    path: &str,
    query: &str,
) -> Result<String> {
    let ts = (chrono::Utc::now().timestamp()).to_string();
    let qs = if query.is_empty() {
        String::new()
    } else {
        format!("?{query}")
    };
    let sign = creds.sign_rest("GET", &ts, path, &qs, "");
    let url = format!("{base}{path}{qs}");
    let resp = client
        .get(&url)
        .header("api-key", &creds.api_key)
        .header("timestamp", &ts)
        .header("signature", sign)
        .header("Accept", "application/json")
        .header("User-Agent", "mm-delta-smoke/0.1")
        .send()
        .await?;
    let status = resp.status();
    let text = resp.text().await?;
    if !status.is_success() {
        if let Ok(parsed) = serde_json::from_str::<ErrBody>(&text) {
            if let Some(e) = parsed.error {
                bail!(
                    "HTTP {} — {}",
                    status.as_u16(),
                    e.code.or(e.message).unwrap_or_else(|| text)
                );
            }
        }
        bail!("HTTP {} — {text}", status.as_u16());
    }
    Ok(text)
}

#[derive(Debug, Deserialize)]
struct L2Response {
    result: Option<L2Book>,
}

#[derive(Debug, Deserialize)]
struct L2Book {
    buy: Option<Vec<L2Level>>,
}

#[derive(Debug, Deserialize)]
struct L2Level {
    price: String,
}

fn round_to_tick(price: f64, tick: f64) -> f64 {
    if tick <= 0.0 {
        return price;
    }
    (price / tick).floor() * tick
}

#[tokio::main]
async fn main() -> Result<()> {
    dotenvy::dotenv().ok();
    let mm_symbol = std::env::var("MM_SYMBOL").unwrap_or_else(|_| "BTCUSDT".into());
    let env_flag = std::env::var("MM_ENV").unwrap_or_else(|_| "testnet".into());
    let env = DeltaEnvironment::from_env_flag(&env_flag);

    let creds = DeltaCredentials::from_env().context("set DELTA_API_KEY and DELTA_API_SECRET")?;
    let client = Client::new();
    let products = Arc::new(ProductCatalog::load(&client, env.rest_base()).await?);
    let rest = DeltaRest::new(env, creds, products.clone());

    println!("venue=delta env={env_flag} base={}", env.rest_base());
    println!("symbol={mm_symbol} product_id={}", products.get(&mm_symbol)?.product_id);

    let base = env.rest_base();
    let pid = products.get(&mm_symbol)?.product_id;
    let query = format!("product_ids={pid}");
    match signed_get_text(&client, &rest.creds, base, "/v2/positions/margined", &query).await {
        Ok(text) => println!("auth OK — positions: {}", &text[..text.len().min(200)]),
        Err(e) => {
            eprintln!("auth check failed: {e:#}");
            eprintln!(
                "If code is Signature Mismatch, re-copy DELTA_API_SECRET from testnet.delta.exchange (India demo key)."
            );
            eprintln!("If code mentions IP, confirm this machine's public IP is whitelisted on the key.");
            bail!("cannot place orders until authenticated GET succeeds");
        }
    }

    let delta_sym = delta_product_symbol(&mm_symbol);
    let url = format!("{base}/v2/l2orderbook/{delta_sym}");
    let l2: L2Response = client
        .get(&url)
        .header("User-Agent", "mm-delta-smoke/0.1")
        .send()
        .await?
        .json()
        .await?;
    let best_bid: f64 = l2
        .result
        .and_then(|b| b.buy)
        .and_then(|v| v.into_iter().next())
        .and_then(|l| l.price.parse().ok())
        .context("no best bid on book")?;
    let meta = products.get(&mm_symbol)?;
    let price = round_to_tick(best_bid * 0.90, meta.tick_size);
    let qty_base = meta.contract_value;
    let link = format!("smoke-{}", chrono::Utc::now().timestamp());

    println!(
        "placing post-only BUY 1 contract (~{qty_base} base) @ {price} (best_bid={best_bid})"
    );
    let _ = rest
        .place_limit_post_only(&mm_symbol, "buy", qty_base, price, &link)
        .await
        .context("place order")?;
    println!("PLACE OK (order should rest on book briefly)");

    rest.cancel_before_requote(&mm_symbol)
        .await
        .context("cancel all for product")?;
    println!("CANCEL OK — smoke test passed");
    Ok(())
}
