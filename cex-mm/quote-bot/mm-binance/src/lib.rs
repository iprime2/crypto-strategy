//! Binance public market data (reference fair for CEX MM).

use anyhow::{Context, Result};
use futures_util::StreamExt;
use serde::Deserialize;
use tokio::sync::watch;
use tokio_tungstenite::connect_async;
use tracing::{info, warn};

const FSTREAM_BOOK_TICKER: &str = "wss://fstream.binance.com/ws";

#[derive(Debug, Clone, Copy, Default)]
pub struct BinanceBbo {
    pub bid: f64,
    pub ask: f64,
    pub mid: f64,
}

#[derive(Debug, Deserialize)]
struct BookTickerMsg {
    #[serde(rename = "b")]
    bid: String,
    #[serde(rename = "a")]
    ask: String,
}

pub fn symbol_stream(symbol: &str) -> String {
    let s = symbol.replace('-', "").to_lowercase();
    format!("{FSTREAM_BOOK_TICKER}/{s}@bookTicker")
}

pub async fn run_book_ticker(symbol: &str, tx: watch::Sender<BinanceBbo>) -> Result<()> {
    let url = symbol_stream(symbol);
    loop {
        match connect_async(&url).await {
            Ok((ws, _)) => {
                info!(%url, "binance bookTicker connected");
                let (_, mut read) = ws.split();
                while let Some(msg) = read.next().await {
                    let msg = msg.context("binance ws read")?;
                    if !msg.is_text() {
                        continue;
                    }
                    let parsed: BookTickerMsg = match serde_json::from_str(msg.to_text()?) {
                        Ok(p) => p,
                        Err(e) => {
                            warn!(?e, "binance parse");
                            continue;
                        }
                    };
                    let bid: f64 = parsed.bid.parse().unwrap_or(0.0);
                    let ask: f64 = parsed.ask.parse().unwrap_or(0.0);
                    if bid > 0.0 && ask > bid {
                        let mid = (bid + ask) / 2.0;
                        let _ = tx.send(BinanceBbo { bid, ask, mid });
                    }
                }
            }
            Err(e) => {
                warn!(?e, "binance reconnect in 3s");
                tokio::time::sleep(std::time::Duration::from_secs(3)).await;
            }
        }
    }
}
