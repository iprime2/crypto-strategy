use mm_bybit::{BybitEnvironment, BybitPublic};

#[tokio::test]
#[ignore = "hits Bybit public API"]
async fn fetch_top_liquid_testnet() {
    let list = BybitPublic::new(BybitEnvironment::Testnet)
        .top_liquid_usdt_linear(5)
        .await
        .expect("top liquid");
    assert!(!list.is_empty());
    assert!(list.iter().all(|s| s.ends_with("USDT")));
}
