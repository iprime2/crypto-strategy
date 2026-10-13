//! Demo-only check of the DISM real-money safety assumptions. The environment is hard-coded to the
//! India demo; it places at most two 1-contract post-only orders and always cancels them.
//!   1. equity and fills reads work (daily loss stop, taker-fill guard);
//!   2. an edit that would cross the ask never trades (post-only edits never take);
//!   3. the dead man's switch cancels a resting order once heartbeats stop.
//!
//!   cd cex-mm/quote-bot && cargo run -p mm-delta --example dism_safety_smoke   # demo keys from .env
use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use mm_delta::{delta_product_symbol, DeltaCredentials, DeltaEnvironment, DeltaRest, ProductCatalog};
use reqwest::Client;

fn to_tick(price: f64, tick: f64) -> f64 {
    ((price / tick).round() * tick * 1e10).round() / 1e10
}

async fn touch(client: &Client, env: DeltaEnvironment, delta_sym: &str) -> Result<(f64, f64)> {
    let url = format!("{}/v2/l2orderbook/{delta_sym}", env.rest_base());
    let v: serde_json::Value = client
        .get(&url)
        .header("User-Agent", "mm-delta-smoke/0.1")
        .send()
        .await?
        .json()
        .await?;
    let px = |side: &str| -> Option<f64> {
        v["result"][side].as_array()?.first()?["price"].as_str()?.parse().ok()
    };
    Ok((px("buy").context("no bid")?, px("sell").context("no ask")?))
}

#[tokio::main]
async fn main() -> Result<()> {
    dotenvy::dotenv().ok();
    let mm_symbol = std::env::var("MM_SYMBOL").unwrap_or_else(|_| "ADAUSDT".into());
    let env = DeltaEnvironment::DemoIndia;
    let creds = DeltaCredentials::from_env_for(env).context("DELTA_DEMO_API_KEY/SECRET or DELTA_API_KEY/SECRET (demo)")?;
    let client = Client::new();
    let products = Arc::new(ProductCatalog::load(&client, env.rest_base()).await?);
    let rest = DeltaRest::new(env, creds, products.clone());
    let meta = products.get(&mm_symbol)?;
    let delta_sym = delta_product_symbol(&mm_symbol);
    let qty = meta.contract_value; // one contract
    println!("demo {mm_symbol} ({delta_sym}) tick={} contract={}", meta.tick_size, meta.contract_value);

    // 1. Reads the account guards depend on.
    println!("1. equity {:.2} USD", rest.get_net_equity_usd().await?);
    let fills = rest.recent_fill_roles(&mm_symbol, 20).await?;
    println!(
        "   last {} fills: {} maker, {} taker",
        fills.len(),
        fills.iter().filter(|f| !f.taker).count(),
        fills.iter().filter(|f| f.taker).count()
    );

    // 2. Edit a resting post-only bid to a price through the ask.
    rest.cancel_all(&mm_symbol).await?;
    let (bid, ask) = touch(&client, env, &delta_sym).await?;
    let far = to_tick(bid * 0.97, meta.tick_size);
    let link = format!("mm-smoke-edit-{}", chrono::Utc::now().timestamp_millis());
    let id = rest
        .place_limit_post_only(&mm_symbol, "buy", qty, far, &link)
        .await?
        .context("no order id")?;
    let cross = to_tick(ask + 5.0 * meta.tick_size, meta.tick_size);
    let edit = rest.edit_post_only(&mm_symbol, id, qty, cross).await;
    tokio::time::sleep(Duration::from_secs(2)).await;
    let (state, unfilled) = rest.order_state(id).await?;
    println!(
        "2. bid {far} edited to {cross} (book {bid}/{ask}): {} -> order {state}, unfilled {unfilled}",
        match &edit {
            Ok(()) => "edit accepted".to_string(),
            Err(e) => format!("edit rejected ({e:#})"),
        }
    );
    println!(
        "   {}",
        if unfilled >= 1 { "PASS: nothing traded" } else { "FAIL: the crossing edit traded as taker" }
    );
    rest.cancel_all(&mm_symbol).await?;

    // 3. Dead man's switch: arm, ack once with a 5 s TTL, then go silent.
    let hb = "mm-bot-dms-smoke";
    match rest.heartbeat_create(hb, &[delta_sym.clone()]).await {
        Ok(()) => println!("3. heartbeat {hb} created"),
        Err(e) => println!("3. heartbeat create: {e:#}"),
    }
    // A restart creates the same id again: show what Delta answers.
    match rest.heartbeat_create(hb, &[delta_sym.clone()]).await {
        Ok(()) => println!("   create again: ok"),
        Err(e) => println!("   create again: {e:#}"),
    }
    let link = format!("mm-smoke-dms-{}", chrono::Utc::now().timestamp_millis());
    let id2 = rest
        .place_limit_post_only(&mm_symbol, "buy", qty, far, &link)
        .await?
        .context("no order id")?;
    match rest.heartbeat_ack(hb, 5_000).await {
        Ok(()) => println!("   ack ttl 5 s ok; silent for 20 s"),
        Err(e) => println!("   ack: {e:#}"),
    }
    tokio::time::sleep(Duration::from_secs(20)).await;
    let (state2, _) = rest.order_state(id2).await?;
    println!(
        "   order after the missed heartbeat: {state2} -> {}",
        if state2 == "cancelled" { "PASS: Delta cancelled it" } else { "FAIL: still resting" }
    );
    rest.cancel_all(&mm_symbol).await?;
    match rest.heartbeat_ack(hb, 0).await {
        Ok(()) => println!("cleanup: cancel-all done, heartbeat disabled (ttl 0)"),
        Err(e) => println!("cleanup: cancel-all done, heartbeat disable failed: {e:#}"),
    }
    Ok(())
}
