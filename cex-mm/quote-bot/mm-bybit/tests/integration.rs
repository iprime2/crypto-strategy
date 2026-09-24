use mm_bybit::{BybitCredentials, BybitEnvironment, BybitRest};

#[tokio::test]
#[ignore = "requires BYBIT_API_KEY/SECRET on testnet"]
async fn post_only_amend_cancel_flow() {
    dotenvy::dotenv().ok();
    let creds = BybitCredentials::from_env().expect("keys");
    let rest = BybitRest::new(BybitEnvironment::Testnet, creds);
    let symbol = std::env::var("MM_SYMBOL").unwrap_or_else(|_| "BTCUSDT".into());
    let (_tick, _step, min_qty) = rest.get_instrument(&symbol).await.expect("instrument");
    let link = format!("mm-it-{}", chrono::Utc::now().timestamp_millis());
    let bid = rest
        .get_funding_carry_bps(&symbol, 0.0)
        .await
        .expect("tickers");
    assert!(bid.is_finite());
    let price = 10_000.0_f64;
    rest.place_limit_post_only(&symbol, "Buy", min_qty, price, &link)
        .await
        .expect("place");
    rest.amend_batch(&symbol, &[(link.clone(), min_qty, price - 1.0)])
        .await
        .expect("amend");
    rest.cancel_all(&symbol).await.expect("cancel");
}
