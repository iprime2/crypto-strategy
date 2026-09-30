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

/// `MM_BINANCE_WS_BASE` overrides the stream host, e.g. `wss://data-stream.binance.vision/ws`
/// (Binance's public spot market-data mirror) where `fstream.binance.com` does not resolve.
pub fn symbol_stream(symbol: &str) -> String {
    let base = std::env::var("MM_BINANCE_WS_BASE")
        .ok()
        .map(|b| b.trim().trim_end_matches('/').to_string())
        .filter(|b| !b.is_empty())
        .unwrap_or_else(|| FSTREAM_BOOK_TICKER.to_string());
    stream_url(&base, symbol)
}

fn stream_url(base: &str, symbol: &str) -> String {
    let s = symbol.replace('-', "").to_lowercase();
    format!("{base}/{s}@bookTicker")
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stream_url_uses_given_base() {
        assert_eq!(
            stream_url(FSTREAM_BOOK_TICKER, "ADA-USDT"),
            "wss://fstream.binance.com/ws/adausdt@bookTicker"
        );
        assert_eq!(
            stream_url("wss://data-stream.binance.vision/ws", "NEARUSDT"),
            "wss://data-stream.binance.vision/ws/nearusdt@bookTicker"
        );
    }
}
