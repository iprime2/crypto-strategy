use anyhow::{Context, Result};
use futures_util::{SinkExt, StreamExt};
use serde_json::Value;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::warn;

use crate::auth::DeltaCredentials;
use crate::products::delta_product_symbol;
use crate::DeltaEnvironment;

pub struct DeltaPrivateWs {
    pub env: DeltaEnvironment,
    pub creds: DeltaCredentials,
}

impl DeltaPrivateWs {
    pub async fn run_user_trades<F>(&self, mm_symbols: &[String], mut on_fill: F) -> Result<()>
    where
        F: FnMut(&str, &Value) + Send + 'static,
    {
        let delta_syms: Vec<String> = mm_symbols
            .iter()
            .map(|s| delta_product_symbol(s))
            .collect();
        let url = self.env.ws_private();
        loop {
            match connect_async(url).await {
                Ok((ws, _)) => {
                    let (mut write, mut read) = ws.split();
                    let ts = (chrono::Utc::now().timestamp()).to_string();
                    let sig = self.creds.sign_ws_auth(&ts);
                    let auth = serde_json::json!({
                        "type": "key-auth",
                        "payload": {
                            "api-key": self.creds.api_key,
                            "signature": sig,
                            "timestamp": ts
                        }
                    });
                    write
                        .send(Message::Text(auth.to_string()))
                        .await
                        .context("delta ws auth")?;
                    let sub = serde_json::json!({
                        "type": "subscribe",
                        "payload": {
                            "channels": [{
                                "name": "v2/user_trades",
                                "symbols": delta_syms
                            }]
                        }
                    });
                    write
                        .send(Message::Text(sub.to_string()))
                        .await
                        .context("delta ws subscribe fills")?;
                    while let Some(msg) = read.next().await {
                        let msg = match msg {
                            Ok(m) => m,
                            Err(e) => {
                                warn!(?e, "delta private read");
                                break;
                            }
                        };
                        if !msg.is_text() {
                            continue;
                        }
                        let v: Value = match serde_json::from_str(msg.to_text()?) {
                            Ok(x) => x,
                            Err(_) => continue,
                        };
                        if v.get("type").and_then(|t| t.as_str()) != Some("v2/user_trades") {
                            continue;
                        }
                        let sym = v
                            .get("sy")
                            .and_then(|s| s.as_str())
                            .unwrap_or("");
                        on_fill(sym, &v);
                    }
                }
                Err(e) => warn!(?e, "delta private connect"),
            }
            tokio::time::sleep(std::time::Duration::from_secs(3)).await;
        }
    }
}
