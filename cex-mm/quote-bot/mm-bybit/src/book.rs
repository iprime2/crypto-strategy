use anyhow::{Context, Result};
use futures_util::{SinkExt, StreamExt};
use mm_core::BookTop;
use serde::Deserialize;
use tokio::sync::watch;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::warn;

use crate::BybitEnvironment;

#[derive(Debug, Clone, Default)]
pub struct BybitBook {
    pub top: BookTop,
    pub last_u: u64,
}

#[derive(Debug, Deserialize)]
struct WsEnvelope {
    topic: Option<String>,
    #[serde(rename = "type")]
    msg_type: Option<String>,
    data: Option<serde_json::Value>,
}

pub struct OrderbookMaintainer {
    pub env: BybitEnvironment,
    pub symbol: String,
}

impl OrderbookMaintainer {
    pub async fn run(&self, tx: watch::Sender<BybitBook>) -> Result<()> {
        let url = self.env.ws_public();
        loop {
            match connect_async(url).await {
                Ok((ws, _)) => {
                    let (mut write, mut read) = ws.split();
                    let sub = serde_json::json!({
                        "op": "subscribe",
                        "args": [
                            format!("orderbook.50.{}", self.symbol),
                            format!("orderbook.1.{}", self.symbol),
                        ]
                    });
                    write
                        .send(Message::Text(sub.to_string()))
                        .await
                        .context("subscribe")?;
                    let mut book = BybitBook::default();
                    while let Some(msg) = read.next().await {
                        let msg = msg.context("read")?;
                        if !msg.is_text() {
                            continue;
                        }
                        let env: WsEnvelope = match serde_json::from_str(msg.to_text()?) {
                            Ok(v) => v,
                            Err(_) => continue,
                        };
                        if env.topic.as_deref().is_some_and(|t| t.contains("orderbook")) {
                            if let Some(data) = env.data {
                                if let Some(u) = data.get("u").and_then(|v| v.as_u64()) {
                                    if u == 1 {
                                        book = BybitBook::default();
                                    }
                                    book.last_u = u;
                                }
                                if let Some(b) = data.get("b").and_then(|v| v.as_array()) {
                                    if let Some(level) = b.first().and_then(|l| l.as_array()) {
                                        if level.len() >= 2 {
                                            book.top.best_bid =
                                                level[0].as_str().unwrap_or("0").parse().unwrap_or(0.0);
                                            book.top.bid_qty =
                                                level[1].as_str().unwrap_or("0").parse().unwrap_or(0.0);
                                        }
                                    }
                                }
                                if let Some(a) = data.get("a").and_then(|v| v.as_array()) {
                                    if let Some(level) = a.first().and_then(|l| l.as_array()) {
                                        if level.len() >= 2 {
                                            book.top.best_ask =
                                                level[0].as_str().unwrap_or("0").parse().unwrap_or(0.0);
                                            book.top.ask_qty =
                                                level[1].as_str().unwrap_or("0").parse().unwrap_or(0.0);
                                        }
                                    }
                                }
                                if book.top.best_bid > 0.0 && book.top.best_ask > book.top.best_bid {
                                    let _ = tx.send(book.clone());
                                }
                            }
                        }
                    }
                }
                Err(e) => {
                    warn!(?e, "bybit book reconnect");
                    tokio::time::sleep(std::time::Duration::from_secs(2)).await;
                }
            }
        }
    }
}
