use std::time::Duration;

use anyhow::Result;
use futures_util::{SinkExt, StreamExt};
use mm_core::BookTop;
use reqwest::Client;
use serde::Deserialize;
use serde_json::Value;
use tokio::sync::watch;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::{info, warn};

use crate::products::delta_product_symbol;
use crate::DeltaEnvironment;

/// `ob_l1` publishes a snapshot about every 100 ms even when the book is quiet, so a few
/// seconds of silence means the socket is dead.
const OB_L1_SILENCE: Duration = Duration::from_secs(5);

#[derive(Debug, Clone, Default)]
pub struct DeltaBook {
    pub top: BookTop,
}

/// Where the top of book comes from.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum BookFeed {
    /// Poll `GET /v2/l2orderbook` every 250 ms.
    #[default]
    Rest,
    /// Public websocket `ob_l1` snapshots, about every 100 ms.
    Ws,
}

impl BookFeed {
    /// `MM_DELTA_BOOK_FEED` value: empty or `rest`, `ws` or `websocket`. None for anything else.
    pub fn from_flag(flag: &str) -> Option<Self> {
        match flag.trim().to_ascii_lowercase().as_str() {
            "" | "rest" => Some(Self::Rest),
            "ws" | "websocket" => Some(Self::Ws),
            _ => None,
        }
    }
}

pub struct OrderbookMaintainer {
    pub env: DeltaEnvironment,
    /// MM symbol or Delta symbol (e.g. BTCUSDT or BTCUSD).
    pub symbol: String,
    pub feed: BookFeed,
}

fn ob_l1_subscribe(delta_sym: &str) -> Value {
    serde_json::json!({
        "type": "subscribe",
        "payload": { "channels": [{ "name": "ob_l1", "symbols": [delta_sym] }] }
    })
}

/// One public-socket frame -> top of book (sizes in contracts). None for other frame types,
/// other symbols, and one-sided, crossed or malformed books.
fn parse_ob_l1(text: &str, delta_sym: &str) -> Option<BookTop> {
    let v: Value = serde_json::from_str(text).ok()?;
    if v.get("type")?.as_str()? != "ob_l1" || v.get("sy")?.as_str()? != delta_sym {
        return None;
    }
    let num = |key: &str| -> Option<f64> {
        match v.get(key)? {
            Value::String(s) => s.parse().ok(),
            Value::Number(n) => n.as_f64(),
            _ => None,
        }
    };
    let top = BookTop {
        best_bid: num("bp")?,
        best_ask: num("ap")?,
        bid_qty: num("bs").unwrap_or(0.0),
        ask_qty: num("as").unwrap_or(0.0),
    };
    (top.best_bid > 0.0 && top.best_ask > top.best_bid).then_some(top)
}

#[derive(Debug, Deserialize)]
struct L2Response {
    success: Option<bool>,
    result: Option<L2Book>,
}

#[derive(Debug, Deserialize)]
struct L2Book {
    buy: Option<Vec<L2Level>>,
    sell: Option<Vec<L2Level>>,
}

#[derive(Debug, Deserialize)]
struct L2Level {
    price: String,
    size: i64,
}

impl OrderbookMaintainer {
    pub async fn run(&self, tx: watch::Sender<BookTop>) -> Result<()> {
        match self.feed {
            BookFeed::Rest => self.run_rest(tx).await,
            BookFeed::Ws => self.run_ws(tx).await,
        }
    }

    async fn run_ws(&self, tx: watch::Sender<BookTop>) -> Result<()> {
        let delta_sym = delta_product_symbol(&self.symbol);
        let sub = ob_l1_subscribe(&delta_sym).to_string();
        loop {
            match connect_async(self.env.ws_public()).await {
                Ok((ws, _)) => {
                    let (mut write, mut read) = ws.split();
                    match write.send(Message::Text(sub.clone())).await {
                        Ok(()) => info!(symbol = %delta_sym, "delta ob_l1 subscribed"),
                        Err(e) => warn!(?e, symbol = %delta_sym, "delta ob_l1 subscribe"),
                    }
                    loop {
                        let msg = match tokio::time::timeout(OB_L1_SILENCE, read.next()).await {
                            Ok(Some(Ok(m))) => m,
                            Ok(Some(Err(e))) => {
                                warn!(?e, symbol = %delta_sym, "delta ob_l1 read");
                                break;
                            }
                            Ok(None) => {
                                warn!(symbol = %delta_sym, "delta ob_l1 stream closed");
                                break;
                            }
                            Err(_) => {
                                warn!(symbol = %delta_sym, "delta ob_l1 silent; reconnecting");
                                break;
                            }
                        };
                        match msg {
                            Message::Text(text) => {
                                if let Some(top) = parse_ob_l1(&text, &delta_sym) {
                                    let _ = tx.send(top);
                                } else if text.contains("error") {
                                    warn!(symbol = %delta_sym, frame = %text, "delta ob_l1 error frame");
                                }
                            }
                            Message::Ping(p) => {
                                let _ = write.send(Message::Pong(p)).await;
                            }
                            Message::Close(_) => break,
                            _ => {}
                        }
                    }
                }
                Err(e) => warn!(?e, symbol = %delta_sym, "delta ob_l1 connect"),
            }
            tokio::time::sleep(Duration::from_secs(1)).await;
        }
    }

    async fn run_rest(&self, tx: watch::Sender<BookTop>) -> Result<()> {
        let delta_sym = delta_product_symbol(&self.symbol);
        let client = Client::new();
        let url = format!(
            "{}/v2/l2orderbook/{delta_sym}",
            self.env.rest_base()
        );
        loop {
            match client
                .get(&url)
                .header("User-Agent", "mm-delta/0.1")
                .send()
                .await
            {
                Ok(resp) => match resp.json::<L2Response>().await {
                    Ok(parsed) => {
                        if let Some(book) = parsed.result {
                            let mut top = BookTop::default();
                            if let Some(bids) = book.buy {
                                if let Some(lvl) = bids.first() {
                                    top.best_bid = lvl.price.parse().unwrap_or(0.0);
                                    top.bid_qty = lvl.size as f64;
                                }
                            }
                            if let Some(asks) = book.sell {
                                if let Some(lvl) = asks.first() {
                                    top.best_ask = lvl.price.parse().unwrap_or(0.0);
                                    top.ask_qty = lvl.size as f64;
                                }
                            }
                            if top.best_bid > 0.0 && top.best_ask > top.best_bid {
                                let _ = tx.send(top);
                            }
                        }
                    }
                    Err(e) => warn!(?e, "delta l2 json"),
                },
                Err(e) => warn!(?e, "delta l2 poll"),
            }
            tokio::time::sleep(std::time::Duration::from_millis(250)).await;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const ADA: &str = r#"{"ap":"0.24629","as":"5","bp":"0.24620","bs":"50309","lts":1790899147476387,"sy":"ADAUSD","ts":1790899148781737,"type":"ob_l1"}"#;

    #[test]
    fn ob_l1_frame_gives_top_of_book_in_contracts() {
        let top = parse_ob_l1(ADA, "ADAUSD").expect("valid frame");
        assert_eq!(top.best_bid, 0.2462);
        assert_eq!(top.best_ask, 0.24629);
        assert_eq!(top.bid_qty, 50309.0);
        assert_eq!(top.ask_qty, 5.0);
    }

    #[test]
    fn ob_l1_ignores_other_symbols_and_other_frames() {
        assert!(parse_ob_l1(ADA, "KITEUSD").is_none());
        assert!(parse_ob_l1(r#"{"type":"heartbeat","ts_origin":1}"#, "ADAUSD").is_none());
        assert!(parse_ob_l1(
            r#"{"channels":[{"name":"ob_l1","symbols":["ADAUSD"]}],"type":"subscriptions"}"#,
            "ADAUSD"
        )
        .is_none());
        assert!(parse_ob_l1("not json", "ADAUSD").is_none());
    }

    #[test]
    fn ob_l1_rejects_one_sided_crossed_or_malformed_books() {
        let one_sided = r#"{"type":"ob_l1","sy":"ADAUSD","bp":"0.2462","bs":"10","ap":null,"as":null}"#;
        let crossed = r#"{"type":"ob_l1","sy":"ADAUSD","bp":"0.2470","bs":"10","ap":"0.2462","as":"3"}"#;
        let garbage = r#"{"type":"ob_l1","sy":"ADAUSD","bp":"abc","bs":"10","ap":"0.2462","as":"3"}"#;
        assert!(parse_ob_l1(one_sided, "ADAUSD").is_none());
        assert!(parse_ob_l1(crossed, "ADAUSD").is_none());
        assert!(parse_ob_l1(garbage, "ADAUSD").is_none());
    }

    #[test]
    fn ob_l1_missing_sizes_default_to_zero() {
        let top = parse_ob_l1(r#"{"type":"ob_l1","sy":"ADAUSD","bp":"1.0","ap":"1.1"}"#, "ADAUSD").unwrap();
        assert_eq!((top.bid_qty, top.ask_qty), (0.0, 0.0));
    }

    #[test]
    fn book_feed_flag_defaults_to_rest_and_rejects_typos() {
        assert_eq!(BookFeed::from_flag(""), Some(BookFeed::Rest));
        assert_eq!(BookFeed::from_flag("rest"), Some(BookFeed::Rest));
        assert_eq!(BookFeed::from_flag(" WS "), Some(BookFeed::Ws));
        assert_eq!(BookFeed::from_flag("websocket"), Some(BookFeed::Ws));
        assert_eq!(BookFeed::from_flag("wss"), None);
    }

    #[test]
    fn ob_l1_subscribe_names_one_symbol() {
        let v = ob_l1_subscribe("ADAUSD");
        assert_eq!(v["type"], "subscribe");
        assert_eq!(v["payload"]["channels"][0]["name"], "ob_l1");
        assert_eq!(v["payload"]["channels"][0]["symbols"][0], "ADAUSD");
    }
}
