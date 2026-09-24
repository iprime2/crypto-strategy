//! Optional OEMS event publisher. Active only when `MM_OEMS_URL` is set.

use serde_json::json;

fn base_url() -> Option<String> {
    let u = std::env::var("MM_OEMS_URL").ok()?;
    let u = u.trim().trim_end_matches('/').to_string();
    if u.is_empty() {
        None
    } else {
        Some(u)
    }
}

fn strategy_id() -> String {
    std::env::var("MM_OEMS_STRATEGY_ID").unwrap_or_else(|_| "mm".into())
}

/// Fire-and-forget POST; never panics; never logs secrets.
pub fn post_order(
    client_order_id: &str,
    symbol: &str,
    side: &str,
    price: f64,
    qty: f64,
    reduce_only: bool,
    reject_code: Option<&str>,
) {
    let Some(base) = base_url() else {
        return;
    };
    let body = json!({
        "strategy_id": strategy_id(),
        "client_order_id": client_order_id,
        "symbol": symbol,
        "side": side,
        "price": price,
        "qty": qty,
        "reduce_only": reduce_only,
        "reject_code": reject_code,
    });
    tokio::spawn(async move {
        let client = reqwest::Client::new();
        let url = format!("{base}/api/events/orders");
        if let Err(e) = client.post(&url).json(&body).send().await {
            tracing::debug!(error = %e, "oems order event failed");
        }
    });
}

pub fn post_fill(
    trade_id: &str,
    client_order_id: Option<&str>,
    symbol: &str,
    side: &str,
    price: f64,
    qty: f64,
    fee: f64,
    limit_price: f64,
    arrival_mid: f64,
    mid_at_fill: f64,
) {
    let Some(base) = base_url() else {
        return;
    };
    let body = json!({
        "strategy_id": strategy_id(),
        "trade_id": trade_id,
        "client_order_id": client_order_id,
        "symbol": symbol,
        "side": side,
        "price": price,
        "qty": qty,
        "fee": fee,
        "limit_price": limit_price,
        "arrival_mid": arrival_mid,
        "mid_at_fill": mid_at_fill,
    });
    tokio::spawn(async move {
        let client = reqwest::Client::new();
        let url = format!("{base}/api/events/fills");
        if let Err(e) = client.post(&url).json(&body).send().await {
            tracing::debug!(error = %e, "oems fill event failed");
        }
    });
}
