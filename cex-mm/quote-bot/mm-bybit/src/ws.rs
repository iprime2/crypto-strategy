use anyhow::{Context, Result};
use futures_util::{SinkExt, StreamExt};
use hmac::{Hmac, Mac};
use sha2::Sha256;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::info;

use crate::auth::BybitCredentials;
use crate::BybitEnvironment;

pub struct BybitPrivateWs {
    pub env: BybitEnvironment,
    pub creds: BybitCredentials,
}

impl BybitPrivateWs {
    pub async fn run_execution<F>(&self, mut on_exec: F) -> Result<()>
    where
        F: FnMut(serde_json::Value) + Send,
    {
        let url = self.env.ws_private();
        let (ws, _) = connect_async(url).await.context("private ws")?;
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
        write
            .send(Message::Text(auth.to_string()))
            .await
            .context("auth")?;
        let sub = serde_json::json!({
            "op": "subscribe",
            "args": ["execution", "order", "position"]
        });
        write.send(Message::Text(sub.to_string())).await?;
        info!("bybit private ws subscribed");
        while let Some(msg) = read.next().await {
            let msg = msg.context("read")?;
            if !msg.is_text() {
                continue;
            }
            let v: serde_json::Value = serde_json::from_str(msg.to_text()?)?;
            if v.get("topic").and_then(|t| t.as_str()) == Some("execution") {
                if let Some(data) = v.get("data") {
                    on_exec(data.clone());
                }
            }
        }
        Ok(())
    }
}
