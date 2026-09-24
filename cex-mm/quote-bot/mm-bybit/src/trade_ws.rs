use anyhow::{Context, Result};
use futures_util::{SinkExt, StreamExt};
use hmac::{Hmac, Mac};
use sha2::Sha256;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::info;

use crate::auth::BybitCredentials;
use crate::BybitEnvironment;

pub struct BybitTradeWs {
    pub env: BybitEnvironment,
    pub creds: BybitCredentials,
}

impl BybitTradeWs {
    pub async fn place_post_only(
        &self,
        symbol: &str,
        side: &str,
        qty: f64,
        price: f64,
        order_link_id: &str,
    ) -> Result<()> {
        let url = self.env.ws_trade();
        let (ws, _) = connect_async(url).await.context("trade ws")?;
        let (mut write, mut read) = ws.split();
        let expires = chrono::Utc::now().timestamp_millis() + 10_000;
        let sign_payload = format!("GET/realtime{expires}");
        let mut mac = Hmac::<Sha256>::new_from_slice(self.creds.api_secret.as_bytes())?;
        mac.update(sign_payload.as_bytes());
        let sign = hex::encode(mac.finalize().into_bytes());
        let auth = serde_json::json!({
            "op": "auth",
            "args": [self.creds.api_key, expires, sign]
        });
        write.send(Message::Text(auth.to_string())).await?;
        let req = serde_json::json!({
            "reqId": order_link_id,
            "header": {
                "X-BAPI-TIMESTAMP": chrono::Utc::now().timestamp_millis().to_string(),
                "X-BAPI-RECV-WINDOW": "5000",
            },
            "op": "order.create",
            "args": [{
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": "Limit",
                "qty": format!("{qty:.8}"),
                "price": format!("{price:.8}"),
                "timeInForce": "PostOnly",
                "orderLinkId": order_link_id,
            }]
        });
        write.send(Message::Text(req.to_string())).await?;
        if let Some(Ok(Message::Text(txt))) = read.next().await {
            let v: serde_json::Value = serde_json::from_str(&txt)?;
            if v.get("retCode").and_then(|c| c.as_i64()).unwrap_or(-1) != 0 {
                anyhow::bail!("trade ws order: {txt}");
            }
        }
        info!(%symbol, %side, "trade ws order ack");
        Ok(())
    }
}
