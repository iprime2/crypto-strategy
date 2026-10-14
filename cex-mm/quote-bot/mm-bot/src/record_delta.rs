//! Raw Delta public websocket recorder with local receive timestamps.
//!
//! One JSONL file per UTC day: `{"recv_us": <local unix µs>, "msg": <raw message>}`. Trades and everything
//! else go to `delta_<env>_public_<day>.jsonl` (what the shadow fill simulation replays). Book frames
//! (`ob_l2`, `mark_price`) go to `delta_<env>_book_<day>.jsonl`, for the live-basis replay
//! (`plans/live-basis.plan.md`). `ob_l2` re-sends an unchanged book every 500 ms; such a repeat is skipped
//! unless the last frame written for that symbol is `BOOK_KEEP_EVERY_US` old, which cuts the 4-symbol
//! shadow's book volume from about 464 to 179 MB a day while a replay can still tell a quiet book from a
//! dead feed.

use anyhow::{Context, Result};
use chrono::Utc;
use clap::Args;
use futures_util::{SinkExt, StreamExt};
use std::collections::HashMap;
use std::fs::{create_dir_all, File, OpenOptions};
use std::io::Write;
use std::path::PathBuf;
use std::time::Duration;
use tokio_tungstenite::{connect_async, tungstenite::Message};

use crate::symbols::resolve_symbol_list;

#[derive(Args)]
pub struct RecordDeltaArgs {
    /// MM symbols, e.g. `ADAUSDT,NEARUSDT` (mapped to Delta `ADAUSD`, `NEARUSD`).
    #[arg(long, value_delimiter = ',', required = true)]
    pub symbols: Vec<String>,
    #[arg(long, default_value = "mainnet")]
    pub env: String,
    #[arg(long, default_value = "artifacts/shadow")]
    pub out_dir: PathBuf,
    /// Public channels to record. Delta India's names are `trades`, `ob_l1`, `ob_l2` and `mark_price`; the
    /// documented `all_trades` and `l1_orderbook` are refused.
    #[arg(long, value_delimiter = ',', default_value = "trades")]
    pub channels: Vec<String>,
    /// Stop after this many seconds (0 = run until killed).
    #[arg(long, default_value = "0")]
    pub duration_sec: u64,
}

/// Reconnect when the socket has been silent this long (heartbeats arrive every ~30 s).
const SILENCE_RECONNECT: Duration = Duration::from_secs(45);

/// An unchanged `ob_l2` book is still written when the last frame kept for its symbol is this old.
const BOOK_KEEP_EVERY_US: i64 = 10_000_000;

/// Delta symbols for one channel: `mark_price` takes `MARK:<symbol>`, the others the product symbol.
pub fn channel_symbols(channel: &str, delta_symbols: &[String]) -> Vec<String> {
    if channel == "mark_price" {
        delta_symbols.iter().map(|s| format!("MARK:{s}")).collect()
    } else {
        delta_symbols.to_vec()
    }
}

pub fn subscribe_message(channels: &[String], delta_symbols: &[String]) -> serde_json::Value {
    let channels: Vec<serde_json::Value> = channels
        .iter()
        .map(|name| serde_json::json!({ "name": name, "symbols": channel_symbols(name, delta_symbols) }))
        .collect();
    serde_json::json!({ "type": "subscribe", "payload": { "channels": channels } })
}

/// Parses one raw text frame. Non-JSON frames are kept as strings.
pub fn parse_frame(text: &str) -> serde_json::Value {
    serde_json::from_str::<serde_json::Value>(text).unwrap_or_else(|_| serde_json::Value::String(text.to_string()))
}

/// Wraps one frame as a JSONL record.
pub fn record_line(recv_us: i64, msg: &serde_json::Value) -> String {
    serde_json::json!({ "recv_us": recv_us, "msg": msg }).to_string()
}

/// Where a frame is written.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Sink {
    Public,
    Book,
    /// A repeat of the last `ob_l2` book written for its symbol.
    Skip,
}

/// Routes frames and drops `ob_l2` repeats (same `b` and `a` as the last book written for the symbol, and
/// that one younger than `BOOK_KEEP_EVERY_US`).
#[derive(Default)]
pub struct BookFilter {
    last: HashMap<String, (String, i64)>,
}

impl BookFilter {
    pub fn route(&mut self, recv_us: i64, msg: &serde_json::Value) -> Sink {
        match msg.get("type").and_then(|t| t.as_str()) {
            Some("mark_price") => Sink::Book,
            Some("ob_l2") => {
                let Some(sym) = msg.get("sy").and_then(|s| s.as_str()) else {
                    return Sink::Book;
                };
                let book = serde_json::json!([msg.get("b"), msg.get("a")]).to_string();
                if let Some((prev, at)) = self.last.get(sym) {
                    if *prev == book && recv_us - at < BOOK_KEEP_EVERY_US {
                        return Sink::Skip;
                    }
                }
                self.last.insert(sym.to_string(), (book, recv_us));
                Sink::Book
            }
            _ => Sink::Public,
        }
    }
}

struct DailyFile {
    dir: PathBuf,
    prefix: String,
    day: String,
    file: Option<File>,
}

impl DailyFile {
    fn write_line(&mut self, line: &str) -> Result<()> {
        let day = Utc::now().format("%Y%m%d").to_string();
        if self.file.is_none() || day != self.day {
            let path = self.dir.join(format!("{}_{day}.jsonl", self.prefix));
            self.file = Some(
                OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(&path)
                    .with_context(|| format!("open {}", path.display()))?,
            );
            self.day = day;
        }
        let file = self.file.as_mut().expect("file opened above");
        writeln!(file, "{line}")?;
        Ok(())
    }
}

pub async fn run(args: RecordDeltaArgs) -> Result<()> {
    create_dir_all(&args.out_dir)?;
    let env = mm_delta::DeltaEnvironment::from_env_flag(&args.env);
    let symbols = resolve_symbol_list(&args.symbols, "");
    let delta_symbols: Vec<String> = symbols
        .iter()
        .map(|s| mm_delta::delta_product_symbol(s))
        .collect();
    let env_label = if env == mm_delta::DeltaEnvironment::IndiaMainnet {
        "mainnet"
    } else {
        "demo"
    };
    let mut out = DailyFile {
        dir: args.out_dir.clone(),
        prefix: format!("delta_{env_label}_public"),
        day: String::new(),
        file: None,
    };
    let mut book_out = DailyFile {
        dir: args.out_dir.clone(),
        prefix: format!("delta_{env_label}_book"),
        day: String::new(),
        file: None,
    };
    let mut books = BookFilter::default();
    let deadline = (args.duration_sec > 0)
        .then(|| tokio::time::Instant::now() + Duration::from_secs(args.duration_sec));
    let sub = subscribe_message(&args.channels, &delta_symbols);
    tracing::info!(url = env.ws_public(), ?delta_symbols, channels = ?args.channels, "delta recorder start");

    loop {
        if deadline.is_some_and(|d| tokio::time::Instant::now() >= d) {
            break;
        }
        match connect_async(env.ws_public()).await {
            Ok((ws, _)) => {
                let (mut write, mut read) = ws.split();
                write
                    .send(Message::Text(serde_json::json!({ "type": "enable_heartbeat" }).to_string()))
                    .await
                    .context("delta ws heartbeat")?;
                write
                    .send(Message::Text(sub.to_string()))
                    .await
                    .context("delta ws subscribe")?;
                loop {
                    if deadline.is_some_and(|d| tokio::time::Instant::now() >= d) {
                        break;
                    }
                    let next = tokio::time::timeout(SILENCE_RECONNECT, read.next()).await;
                    let msg = match next {
                        Ok(Some(Ok(m))) => m,
                        Ok(Some(Err(e))) => {
                            tracing::warn!(?e, "delta recorder read");
                            break;
                        }
                        Ok(None) => {
                            tracing::warn!("delta recorder stream closed");
                            break;
                        }
                        Err(_) => {
                            tracing::warn!("delta recorder silent; reconnecting");
                            break;
                        }
                    };
                    let recv_us = Utc::now().timestamp_micros();
                    match msg {
                        Message::Text(text) => {
                            let frame = parse_frame(&text);
                            match books.route(recv_us, &frame) {
                                Sink::Public => out.write_line(&record_line(recv_us, &frame))?,
                                Sink::Book => book_out.write_line(&record_line(recv_us, &frame))?,
                                Sink::Skip => {}
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
            Err(e) => tracing::warn!(?e, "delta recorder connect"),
        }
        tokio::time::sleep(Duration::from_secs(3)).await;
    }
    tracing::info!("delta recorder finished");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn subscribe_lists_each_channel_with_symbols() {
        let v = subscribe_message(
            &["all_trades".into(), "l1_orderbook".into()],
            &["ADAUSD".into(), "NEARUSD".into()],
        );
        assert_eq!(v["type"], "subscribe");
        let ch = v["payload"]["channels"].as_array().unwrap();
        assert_eq!(ch.len(), 2);
        assert_eq!(ch[0]["name"], "all_trades");
        assert_eq!(ch[1]["symbols"][1], "NEARUSD");
    }

    #[test]
    fn record_line_keeps_json_and_raw_text() {
        let json_line: serde_json::Value =
            serde_json::from_str(&record_line(5, &parse_frame(r#"{"type":"all_trades","price":"0.25"}"#))).unwrap();
        assert_eq!(json_line["recv_us"], 5);
        assert_eq!(json_line["msg"]["price"], "0.25");
        let raw: serde_json::Value = serde_json::from_str(&record_line(6, &parse_frame("not json"))).unwrap();
        assert_eq!(raw["msg"], "not json");
    }

    #[test]
    fn mark_price_subscribes_with_the_mark_prefix() {
        let v = subscribe_message(&["trades".into(), "mark_price".into()], &["ADAUSD".into()]);
        let ch = v["payload"]["channels"].as_array().unwrap();
        assert_eq!(ch[0]["symbols"][0], "ADAUSD");
        assert_eq!(ch[1]["symbols"][0], "MARK:ADAUSD");
    }

    #[test]
    fn book_frames_go_apart_and_unchanged_books_are_thinned() {
        let l2 = |b: &str, ts: u64| {
            parse_frame(&format!(
                r#"{{"type":"ob_l2","sy":"ADAUSD","ts":{ts},"b":[["{b}","47081"]],"a":[["0.23230","65594"]]}}"#
            ))
        };
        let mut f = BookFilter::default();
        assert_eq!(f.route(0, &parse_frame(r#"{"type":"trades","sy":"ADAUSD"}"#)), Sink::Public);
        assert_eq!(f.route(0, &parse_frame(r#"{"type":"mark_price","s":"MARK:ADAUSD"}"#)), Sink::Book);
        assert_eq!(f.route(0, &parse_frame("not json")), Sink::Public);
        assert_eq!(f.route(1_000_000, &l2("0.23200", 1)), Sink::Book);
        // Same book, new venue timestamp: a repeat.
        assert_eq!(f.route(1_500_000, &l2("0.23200", 2)), Sink::Skip);
        assert_eq!(f.route(10_999_999, &l2("0.23200", 3)), Sink::Skip);
        // Kept once the last written frame is 10 s old, so a quiet book still shows up.
        assert_eq!(f.route(11_000_000, &l2("0.23200", 4)), Sink::Book);
        assert_eq!(f.route(11_500_000, &l2("0.23200", 5)), Sink::Skip);
        assert_eq!(f.route(12_000_000, &l2("0.23180", 6)), Sink::Book);
        // Another symbol has its own history.
        let other = parse_frame(r#"{"type":"ob_l2","sy":"KITEUSD","b":[["0.1","1"]],"a":[["0.2","1"]]}"#);
        assert_eq!(f.route(12_100_000, &other), Sink::Book);
    }
}
