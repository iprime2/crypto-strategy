//! Binance public market data (reference fair for CEX MM).

use anyhow::Result;
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
    /// Messages received so far. A count that stops changing means the feed went silent, even when the
    /// price would not have moved (ADA's mid can sit unchanged for minutes).
    pub seq: u64,
}

/// A reconnect when no message arrives for this long: a half-open connection otherwise blocks forever.
const READ_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(30);
/// A connect (DNS, TCP, TLS, websocket handshake) that takes longer is abandoned and retried.
const CONNECT_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(10);

/// One bookTicker message as a quote, or None if it does not parse or the book is not sane.
fn parse_book_ticker(text: &str, seq: u64) -> Option<BinanceBbo> {
    let parsed: BookTickerMsg = serde_json::from_str(text).ok()?;
    let bid: f64 = parsed.bid.parse().ok()?;
    let ask: f64 = parsed.ask.parse().ok()?;
    (bid > 0.0 && ask > bid).then(|| BinanceBbo { bid, ask, mid: (bid + ask) / 2.0, seq })
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

/// Streams the symbol's bookTicker into `tx` until every receiver is gone. A read error, a closed stream,
/// `READ_TIMEOUT` without a message or a connect slower than `CONNECT_TIMEOUT` reconnects; before 2026-10-13 a read error ended the task and the
/// last price stayed in `tx` for good (the 8-12 Oct 2026 freeze is consistent with that [UNVERIFIED]).
pub async fn run_book_ticker(symbol: &str, tx: watch::Sender<BinanceBbo>) -> Result<()> {
    let url = symbol_stream(symbol);
    let mut seq: u64 = 0;
    loop {
        if tx.is_closed() {
            return Ok(()); // nobody reads the quotes any more
        }
        match tokio::time::timeout(CONNECT_TIMEOUT, connect_async(&url)).await {
            Ok(Ok((ws, _))) => {
                info!(%url, "binance bookTicker connected");
                let (_, mut read) = ws.split();
                loop {
                    let msg = match tokio::time::timeout(READ_TIMEOUT, read.next()).await {
                        Err(_) => {
                            warn!(%url, "binance bookTicker silent for 30 s, reconnecting");
                            break;
                        }
                        Ok(None) => {
                            warn!(%url, "binance bookTicker stream ended, reconnecting");
                            break;
                        }
                        Ok(Some(Err(e))) => {
                            warn!(?e, "binance ws read error, reconnecting");
                            break;
                        }
                        Ok(Some(Ok(m))) => m,
                    };
                    if !msg.is_text() {
                        continue;
                    }
                    let Ok(text) = msg.to_text() else { continue };
                    match parse_book_ticker(text, seq + 1) {
                        Some(bbo) => {
                            seq += 1;
                            if tx.send(bbo).is_err() {
                                return Ok(()); // nobody reads the quotes any more
                            }
                        }
                        None => warn!(len = text.len(), "binance bookTicker message skipped"),
                    }
                }
                tokio::time::sleep(std::time::Duration::from_secs(1)).await;
            }
            Ok(Err(e)) => {
                warn!(?e, "binance reconnect in 3s");
                tokio::time::sleep(std::time::Duration::from_secs(3)).await;
            }
            Err(_) => {
                warn!(%url, "binance connect timed out, retrying in 3s");
                tokio::time::sleep(std::time::Duration::from_secs(3)).await;
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn book_ticker_parses_and_numbers_messages() {
        let m = r#"{"u":1,"s":"ADAUSDT","b":"0.2400","B":"10","a":"0.2401","A":"5"}"#;
        let bbo = parse_book_ticker(m, 7).unwrap();
        assert_eq!((bbo.bid, bbo.ask, bbo.seq), (0.24, 0.2401, 7));
        assert!((bbo.mid - 0.24005).abs() < 1e-12);
        assert!(parse_book_ticker(r#"{"b":"0.25","a":"0.24"}"#, 1).is_none(), "crossed");
        assert!(parse_book_ticker(r#"{"b":"x","a":"0.24"}"#, 1).is_none());
        assert!(parse_book_ticker("not json", 1).is_none());
    }

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
