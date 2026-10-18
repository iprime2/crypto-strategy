//! Tails the supervised bot's log: latest `MM_METRICS` per symbol plus an event feed
//! (orders, edits, rejects, regime pauses, kills, warnings, errors).

use std::collections::{HashMap, VecDeque};
use std::io::{Read, Seek, SeekFrom};
use std::path::PathBuf;
use std::sync::Arc;
use std::time::Duration;

use chrono::{DateTime, Utc};
use serde::Serialize;
use serde_json::Value;
use tokio::sync::RwLock;

use crate::supervisor::Supervisor;

const MAX_EVENTS: usize = 400;
const READ_CAP: u64 = 8 * 1024 * 1024;

#[derive(Debug, Clone, Serialize)]
pub struct BotEvent {
    pub ts: String,
    pub level: &'static str,
    pub kind: &'static str,
    pub symbol: Option<String>,
    pub message: String,
    /// Consecutive identical events are folded into one row with a count.
    pub count: u32,
}

#[derive(Default, Serialize, Clone)]
pub struct Counters {
    pub orders_placed: u64,
    pub orders_edited: u64,
    pub rejects: u64,
    pub regime_pauses: u64,
    pub risk_kills: u64,
    /// Stale-book cancels (the feed went quiet past `MM_BOOK_STALE_MS`).
    pub stale_books: u64,
    /// Account guard halts: daily loss limit, unexpected taker fill.
    pub halts: u64,
    pub warnings: u64,
    pub errors: u64,
}

#[derive(Default)]
pub struct TelemetryState {
    pub log_path: Option<PathBuf>,
    offset: u64,
    partial: String,
    pub metrics: HashMap<String, (DateTime<Utc>, Value)>,
    pub events: VecDeque<BotEvent>,
    pub counters: Counters,
    pub last_line_at: Option<DateTime<Utc>>,
}

pub type Telemetry = Arc<RwLock<TelemetryState>>;

pub fn new_telemetry() -> Telemetry {
    Arc::new(RwLock::new(TelemetryState::default()))
}

/// Strip ANSI color codes (bots started outside the supervisor may still emit them).
pub fn strip_ansi(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        if c == '\u{1b}' {
            if chars.peek() == Some(&'[') {
                chars.next();
                for n in chars.by_ref() {
                    if n.is_ascii_alphabetic() {
                        break;
                    }
                }
            }
            continue;
        }
        out.push(c);
    }
    out
}

fn field(line: &str, key: &str) -> Option<String> {
    let start = line.find(&format!("{key}="))? + key.len() + 1;
    let rest = &line[start..];
    let value = if let Some(stripped) = rest.strip_prefix('"') {
        stripped.split('"').next().unwrap_or("")
    } else {
        rest.split_whitespace().next().unwrap_or("")
    };
    Some(value.to_string())
}

/// Parsed log line.
#[derive(Debug, PartialEq)]
pub enum Parsed {
    Metrics(String, Value),
    Event { level: &'static str, kind: &'static str, symbol: Option<String>, message: String },
    Ignore,
}

pub fn parse_line(raw: &str) -> Parsed {
    let line = strip_ansi(raw);
    let line = line.trim();
    if line.is_empty() {
        return Parsed::Ignore;
    }
    if let Some(pos) = line.find("MM_METRICS:") {
        let json = &line[pos + "MM_METRICS:".len()..];
        if let Ok(v) = serde_json::from_str::<Value>(json.trim()) {
            if let Some(sym) = v.get("symbol").and_then(|s| s.as_str()) {
                return Parsed::Metrics(sym.to_string(), v);
            }
        }
        return Parsed::Ignore;
    }
    let level = if line.contains(" ERROR ") {
        "error"
    } else if line.contains(" WARN ") {
        "warn"
    } else {
        "info"
    };
    let symbol = field(line, "symbol");
    let body = line
        .splitn(2, ": ")
        .nth(1)
        .unwrap_or(line)
        .to_string();
    let (kind, message) = if line.contains("MM_ORDER:") {
        if line.contains("edited post-only") {
            ("order_edit", body)
        } else {
            ("order", body)
        }
    } else if line.contains("MM_REJECT:") {
        ("reject", body)
    } else if line.contains("regime L3 pause") {
        ("regime_pause", "Regime L3 pause: quotes cancelled".to_string())
    } else if line.contains("risk kill") {
        ("risk_kill", body)
    } else if line.contains("inventory hard cap") {
        ("hard_cap", body)
    } else if line.contains("stale book") {
        ("stale_book", body)
    } else if line.contains("book fresh again") {
        ("book_fresh", body)
    } else if line.contains("dead man's switch") || line.contains("heartbeat") {
        ("dead_mans_switch", body)
    } else if line.contains("account halt") || line.contains("daily loss limit") || line.contains("unexpected taker fill") {
        ("account_halt", body)
    } else if level != "info" {
        ("log", body)
    } else if line.contains("startup")
        || line.contains("mm universe")
        || line.contains("instrument")
        || line.contains("account guards on")
        || line.contains("fills feed")
    {
        ("lifecycle", body)
    } else {
        return Parsed::Ignore;
    };
    Parsed::Event { level, kind, symbol, message }
}

impl TelemetryState {
    fn reset(&mut self, path: Option<PathBuf>) {
        *self = TelemetryState { log_path: path, ..Default::default() };
    }

    fn push_event(&mut self, ev: BotEvent) {
        if let Some(last) = self.events.back_mut() {
            if last.kind == ev.kind && last.symbol == ev.symbol && last.message == ev.message {
                last.count += 1;
                last.ts = ev.ts;
                return;
            }
        }
        if self.events.len() >= MAX_EVENTS {
            self.events.pop_front();
        }
        self.events.push_back(ev);
    }

    pub fn ingest(&mut self, line: &str, now: DateTime<Utc>) {
        self.last_line_at = Some(now);
        match parse_line(line) {
            Parsed::Metrics(sym, v) => {
                self.metrics.insert(sym, (now, v));
            }
            Parsed::Event { level, kind, symbol, message } => {
                match kind {
                    "order" => self.counters.orders_placed += 1,
                    "order_edit" => self.counters.orders_edited += 1,
                    "reject" => self.counters.rejects += 1,
                    "regime_pause" => self.counters.regime_pauses += 1,
                    "risk_kill" => self.counters.risk_kills += 1,
                    "stale_book" => self.counters.stale_books += 1,
                    "account_halt" => self.counters.halts += 1,
                    _ => {}
                }
                match level {
                    "warn" => self.counters.warnings += 1,
                    "error" => self.counters.errors += 1,
                    _ => {}
                }
                self.push_event(BotEvent { ts: now.to_rfc3339(), level, kind, symbol, message, count: 1 });
            }
            Parsed::Ignore => {}
        }
    }
}

/// Every second: follow the current bot's log file and parse new lines.
pub async fn run_tail_loop(telemetry: Telemetry, supervisor: Arc<Supervisor>, strategy_id: String) {
    let mut tick = tokio::time::interval(Duration::from_secs(1));
    loop {
        tick.tick().await;
        let path = supervisor.info(&strategy_id).and_then(|i| i.log_path);
        tail_once(&telemetry, path).await;
    }
}

/// Same as `run_tail_loop` but for a fixed file (dev instance or a shadow run log).
pub async fn run_fixed_tail_loop(telemetry: Telemetry, path: PathBuf) {
    let mut tick = tokio::time::interval(Duration::from_secs(1));
    loop {
        tick.tick().await;
        tail_once(&telemetry, Some(path.clone())).await;
    }
}

async fn tail_once(telemetry: &Telemetry, path: Option<PathBuf>) {
    let mut g = telemetry.write().await;
    if g.log_path != path {
        g.reset(path.clone());
        // Start near the end of an existing log instead of replaying hours of it.
        if let Some(p) = &path {
            if let Ok(meta) = std::fs::metadata(p) {
                g.offset = meta.len().saturating_sub(256 * 1024);
            }
        }
    }
    let Some(p) = path else { return };
    let Ok(mut f) = std::fs::File::open(&p) else { return };
    let len = f.metadata().map(|m| m.len()).unwrap_or(0);
    if len < g.offset {
        g.offset = 0;
    }
    if len == g.offset || f.seek(SeekFrom::Start(g.offset)).is_err() {
        return;
    }
    let mut buf = Vec::new();
    let _ = f.take(READ_CAP).read_to_end(&mut buf);
    g.offset += buf.len() as u64;
    let text = std::mem::take(&mut g.partial) + &String::from_utf8_lossy(&buf);
    let mut lines: Vec<&str> = text.split('\n').collect();
    let tail = if text.ends_with('\n') { String::new() } else { lines.pop().unwrap_or("").to_string() };
    let now = Utc::now();
    for l in lines {
        g.ingest(l, now);
    }
    g.partial = tail;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn metrics_line_parses_with_or_without_ansi() {
        let plain = r#"2026-09-29T11:54:03.291259Z  INFO MM_METRICS: {"symbol":"ETHUSDT","fair":2734.1,"bid":2731.9}"#;
        match parse_line(plain) {
            Parsed::Metrics(s, v) => {
                assert_eq!(s, "ETHUSDT");
                assert_eq!(v["bid"], 2731.9);
            }
            other => panic!("{other:?}"),
        }
        let ansi = "\u{1b}[2m2026-09-29T11:54:03Z\u{1b}[0m \u{1b}[32m INFO\u{1b}[0m \u{1b}[2mMM_METRICS\u{1b}[0m\u{1b}[2m:\u{1b}[0m {\"symbol\":\"BTCUSDT\"}";
        assert!(matches!(parse_line(ansi), Parsed::Metrics(s, _) if s == "BTCUSDT"));
    }

    #[test]
    fn reject_and_pause_become_events() {
        let rej = r#"2026-09-29T11:54:03Z  WARN MM_REJECT: post-only reject symbol=ETHUSDT side="buy" price=2731.9 qty=0.01 err=insufficient_margin"#;
        match parse_line(rej) {
            Parsed::Event { level, kind, symbol, .. } => {
                assert_eq!((level, kind), ("warn", "reject"));
                assert_eq!(symbol.as_deref(), Some("ETHUSDT"));
            }
            other => panic!("{other:?}"),
        }
        let pause = "2026-09-29T11:53:50Z  WARN mm_bot::runner: regime L3 pause — cancel all symbol=ADAUSDT regime.level=L3Crash depth_ratio=0.0005 jump_bps=0.0";
        assert!(matches!(parse_line(pause), Parsed::Event { kind: "regime_pause", .. }));
        assert_eq!(parse_line("2026-09-29T11:53:50Z  INFO mm_bot::runner: something routine"), Parsed::Ignore);
    }

    #[test]
    fn guard_lines_become_their_own_events() {
        let cases = [
            ("2026-10-05T23:48:26Z  WARN mm_bot::runner: stale book — cancel all symbol=ADAUSDT age_ms=2400 limit_ms=2000", "warn", "stale_book"),
            ("2026-10-17T19:30:49Z  WARN mm_bot::runner: stale book: frozen, unchanged while frames arrive — cancel all symbol=ADAUSDT unchanged_ms=30000 binance_move_bps=5.4", "warn", "stale_book"),
            ("2026-10-05T23:48:29Z  INFO mm_bot::runner: book fresh again symbol=ADAUSDT outage_ms=3200", "info", "book_fresh"),
            ("2026-10-17T20:13:58Z  INFO mm_bot::runner: book fresh again: changing after a freeze symbol=ADAUSDT frozen_ms=2588800", "info", "book_fresh"),
            ("2026-10-05T23:40:00Z  INFO mm_bot::account: dead man's switch armed heartbeat_id=mm-bot-adausd ttl_ms=15000", "info", "dead_mans_switch"),
            ("2026-10-05T23:41:00Z  WARN mm_bot::account: heartbeat ack failed; Delta cancels our orders if this lasts past the TTL heartbeat_id=mm-bot-adausd", "warn", "dead_mans_switch"),
            ("2026-10-05T23:42:00Z ERROR mm_bot::account: daily loss limit hit pnl_usd=-15.2 limit_usd=15", "error", "account_halt"),
            ("2026-10-05T23:42:00Z ERROR mm_bot::account: unexpected taker fill on a post-only quote symbol=ADAUSDT fill_id=9", "error", "account_halt"),
            ("2026-10-05T23:42:00Z ERROR mm_bot::runner: account halt — orders cancelled, quoting stopped symbol=ADAUSDT", "error", "account_halt"),
            ("2026-10-05T23:39:00Z  INFO mm_bot::runner: account guards on limit_usd=15 poll_sec=30 dms_ttl_ms=15000", "info", "lifecycle"),
            ("2026-10-14T09:00:00Z  INFO mm_bot::runner: delta fills feed confirmed", "info", "lifecycle"),
            ("2026-10-14T09:00:00Z ERROR mm_bot::runner: delta fills feed refused 2 times; not starting reason=login refused", "error", "log"),
            ("2026-10-14T09:00:00Z  WARN mm_bot::runner: fills feed down; adding side off until the venue confirms it again symbol=ADAUSDT down_s=30.4", "warn", "log"),
            ("2026-10-14T09:01:00Z  INFO mm_bot::runner: fills feed back; adding side on symbol=ADAUSDT down_s=65.0", "info", "lifecycle"),
        ];
        for (line, want_level, want_kind) in cases {
            match parse_line(line) {
                Parsed::Event { level, kind, .. } => assert_eq!((level, kind), (want_level, want_kind), "{line}"),
                other => panic!("{line}: {other:?}"),
            }
        }
        let mut st = TelemetryState::default();
        st.ingest(cases[0].0, Utc::now());
        st.ingest(cases[1].0, Utc::now()); // a frozen book counts as a stale-book cancel
        st.ingest(cases[6].0, Utc::now());
        assert_eq!((st.counters.stale_books, st.counters.halts), (2, 1));
    }

    #[test]
    fn repeated_events_fold_into_one_row() {
        let mut st = TelemetryState::default();
        let pause = "2026-09-29T11:53:50Z  WARN mm_bot::runner: regime L3 pause — cancel all symbol=ADAUSDT";
        for _ in 0..5 {
            st.ingest(pause, Utc::now());
        }
        assert_eq!(st.events.len(), 1);
        assert_eq!(st.events[0].count, 5);
        assert_eq!(st.counters.regime_pauses, 5);
    }
}
