//! Raw Delta public websocket recorder (trades + L1) with local receive timestamps.
//!
//! One JSONL file per UTC day: `{"recv_us": <local unix µs>, "msg": <raw message>}`.
//! Used by the shadow test to replay what a quote would have traded against.

use anyhow::{Context, Result};
use chrono::Utc;
use clap::Args;
use futures_util::{SinkExt, StreamExt};
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
    /// Public channels to record.
    #[arg(long, value_delimiter = ',', default_value = "all_trades,l1_orderbook")]
    pub channels: Vec<String>,
    /// Stop after this many seconds (0 = run until killed).
    #[arg(long, default_value = "0")]
    pub duration_sec: u64,
}

/// Reconnect when the socket has been silent this long (heartbeats arrive every ~30 s).
const SILENCE_RECONNECT: Duration = Duration::from_secs(45);

pub fn subscribe_message(channels: &[String], delta_symbols: &[String]) -> serde_json::Value {
    let channels: Vec<serde_json::Value> = channels
        .iter()
        .map(|name| serde_json::json!({ "name": name, "symbols": delta_symbols }))
        .collect();
    serde_json::json!({ "type": "subscribe", "payload": { "channels": channels } })
}

/// Wraps one raw text frame as a JSONL record. Non-JSON frames are kept as strings.
pub fn record_line(recv_us: i64, text: &str) -> String {
    let msg = serde_json::from_str::<serde_json::Value>(text)
        .unwrap_or_else(|_| serde_json::Value::String(text.to_string()));
    serde_json::json!({ "recv_us": recv_us, "msg": msg }).to_string()
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
                        Message::Text(text) => out.write_line(&record_line(recv_us, &text))?,
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
            serde_json::from_str(&record_line(5, r#"{"type":"all_trades","price":"0.25"}"#)).unwrap();
        assert_eq!(json_line["recv_us"], 5);
        assert_eq!(json_line["msg"]["price"], "0.25");
        let raw: serde_json::Value = serde_json::from_str(&record_line(6, "not json")).unwrap();
        assert_eq!(raw["msg"], "not json");
    }
}
