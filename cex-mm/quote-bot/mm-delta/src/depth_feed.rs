//! Public `ob_l2` depth feed: a 15-level snapshot per symbol every 500 ms. Probed 2026-10-14 on Delta India
//! mainnet and demo: unchanged books are re-sent every 500 ms too, so the age of the last frame is the feed's
//! freshness. One connection carries every symbol and stays separate from `ob_l1`, so a depth failure cannot
//! touch the book watch that cancels quotes (it does share the IP's connection budget, hence the backoff). The
//! anchored fair is to read its live basis from this book (`plans/live-basis.plan.md`).

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use futures_util::{SinkExt, StreamExt};
use serde_json::Value;
use tokio::sync::watch;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::{info, warn};

use crate::products::delta_product_symbol;
use crate::ws::present;
use crate::DeltaEnvironment;

pub const DEPTH_CHANNEL: &str = "ob_l2";

#[derive(Debug, Clone, PartialEq)]
pub struct DepthSnapshot {
    /// Best first, `(price, size in contracts)`.
    pub bids: Vec<(f64, f64)>,
    pub asks: Vec<(f64, f64)>,
    /// Venue publish time (µs). The local clock is not Delta's, so ages use `received_at`.
    pub venue_ts_us: Option<i64>,
    pub received_at: Instant,
}

pub type DepthRx = watch::Receiver<Option<Arc<DepthSnapshot>>>;
type DepthTx = watch::Sender<Option<Arc<DepthSnapshot>>>;

fn num(v: &Value) -> Option<f64> {
    let x = match v {
        Value::String(s) => s.trim().parse::<f64>().ok()?,
        Value::Number(n) => n.as_f64()?,
        _ => return None,
    };
    x.is_finite().then_some(x)
}

/// One side's levels. A missing or null side is an empty side (`depth_mid` reports it); anything else that is
/// not a list of `[price, size]` pairs fails.
fn levels(v: Option<&Value>) -> Option<Vec<(f64, f64)>> {
    let Some(v) = v.filter(|v| !v.is_null()) else {
        return Some(Vec::new());
    };
    v.as_array()?
        .iter()
        .map(|l| {
            let l = l.as_array()?;
            Some((num(l.first()?)?, num(l.get(1)?)?))
        })
        .collect()
}

/// One `ob_l2` frame as `(delta_symbol, snapshot)`. A frame with any malformed level is dropped whole, so a
/// snapshot is never a partial book.
pub fn parse_ob_l2(text: &str, received_at: Instant) -> Option<(String, DepthSnapshot)> {
    let v: Value = serde_json::from_str(text).ok()?;
    if v.get("type")?.as_str()? != DEPTH_CHANNEL {
        return None;
    }
    let sy = v.get("sy")?.as_str()?.to_string();
    let snap = DepthSnapshot {
        bids: levels(v.get("b"))?,
        asks: levels(v.get("a"))?,
        venue_ts_us: v.get("ts").and_then(|t| t.as_i64()),
        received_at,
    };
    Some((sy, snap))
}

/// The venue's reason when it refuses our `ob_l2` subscription. A null or blank `error` is not a refusal.
fn refusal(v: &Value) -> Option<String> {
    if v.get("type")?.as_str()? != "subscriptions" {
        return None;
    }
    v.get("channels")?
        .as_array()?
        .iter()
        .find(|c| c.get("name").and_then(|n| n.as_str()) == Some(DEPTH_CHANNEL))
        .and_then(|c| present(c.get("error")))
        .map(|e| e.as_str().map(str::to_string).unwrap_or_else(|| e.to_string()))
}

/// A frame that is not an `ob_l2` book we could parse.
#[derive(Debug, PartialEq)]
enum OtherFrame {
    /// The venue refused the subscription, with its reason.
    Refused(String),
    /// The subscription ack (it names the channel, so it is not a broken book).
    Ack,
    /// Mentions `ob_l2` but did not parse as a book.
    Unparsed,
    /// Heartbeats and anything else.
    Ignore,
}

fn classify_other(text: &str) -> OtherFrame {
    if let Ok(v) = serde_json::from_str::<Value>(text) {
        if let Some(why) = refusal(&v) {
            return OtherFrame::Refused(why);
        }
        if v.get("type").and_then(|t| t.as_str()) == Some("subscriptions") {
            return OtherFrame::Ack;
        }
    }
    if text.contains(DEPTH_CHANNEL) {
        OtherFrame::Unparsed
    } else {
        OtherFrame::Ignore
    }
}

#[derive(Debug, Clone, Copy)]
pub struct DepthFeedTimings {
    pub connect_timeout: Duration,
    /// Reconnect when no frame arrives for this long (snapshots come every 500 ms per symbol).
    pub silence: Duration,
    /// Pause before reconnecting (±20% jitter); doubles while connections keep failing, up to `retry_max`.
    pub retry_min: Duration,
    pub retry_max: Duration,
    /// A session that delivered books for at least this long resets the pause to `retry_min`. A venue that
    /// accepts, sends one book and closes keeps backing off instead of being redialled every second.
    pub reset_after: Duration,
}

impl Default for DepthFeedTimings {
    fn default() -> Self {
        Self {
            connect_timeout: Duration::from_secs(10),
            silence: Duration::from_secs(15),
            retry_min: Duration::from_secs(1),
            retry_max: Duration::from_secs(30),
            reset_after: Duration::from_secs(30),
        }
    }
}

/// Starts one `ob_l2` connection for `mm_symbols`; returns a receiver per MM symbol (`None` until its first
/// snapshot). The task ends when every receiver is dropped.
pub fn spawn_depth_feed(env: DeltaEnvironment, mm_symbols: &[String]) -> HashMap<String, DepthRx> {
    let mut senders = HashMap::new();
    let mut receivers = HashMap::new();
    for s in mm_symbols {
        let (tx, rx) = watch::channel(None);
        senders.insert(delta_product_symbol(s), tx);
        receivers.insert(s.clone(), rx);
    }
    let url = env.ws_public().to_string();
    tokio::spawn(async move { run_depth_feed(&url, senders, DepthFeedTimings::default()).await });
    receivers
}

enum Ended {
    /// The session delivered snapshots; how long it lasted.
    Delivered(Duration),
    Failed,
    /// Every receiver is gone.
    Unwanted,
}

/// `d` scaled by a factor in [0.8, 1.2), so several feeds dropped together do not redial in step.
fn jitter(d: Duration) -> Duration {
    let n = SystemTime::now().duration_since(UNIX_EPOCH).map(|t| t.subsec_nanos()).unwrap_or(0);
    d.mul_f64(0.8 + 0.4 * f64::from(n % 1000) / 1000.0)
}

async fn run_depth_feed(url: &str, senders: HashMap<String, DepthTx>, t: DepthFeedTimings) {
    let mut retry = t.retry_min;
    loop {
        match session(url, &senders, t).await {
            Ended::Unwanted => return,
            Ended::Delivered(lasted) if lasted >= t.reset_after => retry = t.retry_min,
            Ended::Delivered(_) | Ended::Failed => {}
        }
        tokio::time::sleep(jitter(retry)).await;
        if senders.values().all(|tx| tx.is_closed()) {
            return;
        }
        retry = (retry * 2).min(t.retry_max);
    }
}

async fn session(url: &str, senders: &HashMap<String, DepthTx>, t: DepthFeedTimings) -> Ended {
    let ws = match tokio::time::timeout(t.connect_timeout, connect_async(url)).await {
        Ok(Ok((ws, _))) => ws,
        Ok(Err(e)) => {
            warn!(?e, "delta ob_l2 connect");
            return Ended::Failed;
        }
        Err(_) => {
            warn!("delta ob_l2 connect timed out");
            return Ended::Failed;
        }
    };
    let (mut write, mut read) = ws.split();
    let mut symbols: Vec<&String> = senders.keys().collect();
    symbols.sort();
    let sub = serde_json::json!({
        "type": "subscribe",
        "payload": { "channels": [{ "name": DEPTH_CHANNEL, "symbols": symbols }] }
    });
    for msg in [sub, serde_json::json!({ "type": "enable_heartbeat" })] {
        if let Err(e) = write.send(Message::Text(msg.to_string())).await {
            warn!(?e, "delta ob_l2 subscribe");
            return Ended::Failed;
        }
    }
    let started = Instant::now();
    let mut delivered = false;
    let mut skipped = 0u64;
    let mut unknown: HashSet<String> = HashSet::new();
    loop {
        let msg = match tokio::time::timeout(t.silence, read.next()).await {
            Err(_) => {
                warn!(silence = ?t.silence, "delta ob_l2 silent; reconnecting");
                break;
            }
            Ok(None) => {
                warn!("delta ob_l2 stream closed; reconnecting");
                break;
            }
            Ok(Some(Err(e))) => {
                warn!(?e, "delta ob_l2 read; reconnecting");
                break;
            }
            Ok(Some(Ok(m))) => m,
        };
        let Message::Text(text) = msg else { continue };
        if let Some((sy, snap)) = parse_ob_l2(&text, Instant::now()) {
            if let Some(tx) = senders.get(&sy) {
                if !delivered {
                    info!(symbols = ?symbols, "delta ob_l2 streaming");
                }
                delivered = true;
                let _ = tx.send(Some(Arc::new(snap)));
            } else if unknown.insert(sy.clone()) {
                warn!(symbol = %sy, "delta ob_l2 book for a symbol we did not subscribe; ignored");
            }
            if senders.values().all(|tx| tx.is_closed()) {
                return Ended::Unwanted;
            }
            continue;
        }
        match classify_other(&text) {
            OtherFrame::Refused(why) => {
                warn!(reason = %why, "delta ob_l2 subscription refused");
                break;
            }
            OtherFrame::Unparsed => {
                skipped += 1;
                if skipped == 1 || skipped % 1000 == 0 {
                    warn!(skipped, "delta ob_l2 frame did not parse; skipped");
                }
            }
            OtherFrame::Ack | OtherFrame::Ignore => {}
        }
    }
    if delivered {
        Ended::Delivered(started.elapsed())
    } else {
        Ended::Failed
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::sync::Mutex;
    use tokio::net::TcpListener;
    use tokio_tungstenite::accept_async;

    /// An ADA frame from the 2026-10-14 probe, trimmed to three levels a side.
    const ADA: &str = r#"{"a":[["0.23260","49847"],["0.23280","56421"],["0.23300","75318"]],"b":[["0.23230","46133"],["0.23210","52216"],["0.23181","1"]],"lts":1791889924106368,"sy":"ADAUSD","ts":1791889924869646,"type":"ob_l2"}"#;

    #[test]
    fn parses_a_snapshot() {
        let now = Instant::now();
        let (sy, s) = parse_ob_l2(ADA, now).unwrap();
        assert_eq!(sy, "ADAUSD");
        assert_eq!(s.bids, vec![(0.23230, 46133.0), (0.23210, 52216.0), (0.23181, 1.0)]);
        assert_eq!(s.asks[0], (0.23260, 49847.0));
        assert_eq!(s.venue_ts_us, Some(1791889924869646));
        assert_eq!(s.received_at, now);
    }

    #[test]
    fn a_malformed_level_drops_the_whole_frame() {
        let now = Instant::now();
        assert!(parse_ob_l2(&ADA.replace(r#""52216""#, r#""x""#), now).is_none());
        assert!(parse_ob_l2(&ADA.replace(r#"["0.23181","1"]"#, r#"["0.23181"]"#), now).is_none());
        assert!(parse_ob_l2(r#"{"type":"ob_l1","sy":"ADAUSD"}"#, now).is_none());
        assert!(parse_ob_l2("not json", now).is_none());
        // An empty, missing or null side is a valid book with an empty side; depth_mid reports it.
        for frame in [
            r#"{"type":"ob_l2","sy":"ADAUSD","a":[],"b":[["1","2"]]}"#,
            r#"{"type":"ob_l2","sy":"ADAUSD","b":[["1","2"]]}"#,
            r#"{"type":"ob_l2","sy":"ADAUSD","a":null,"b":[["1","2"]]}"#,
        ] {
            let (_, s) = parse_ob_l2(frame, now).unwrap();
            assert!(s.asks.is_empty(), "{frame}");
            assert_eq!(s.bids, vec![(1.0, 2.0)]);
        }
        assert!(parse_ob_l2(r#"{"type":"ob_l2","sy":"ADAUSD","a":"x","b":[]}"#, now).is_none());
    }

    #[test]
    fn the_subscription_ack_is_not_counted_as_a_broken_book() {
        let ack = json!({"type": "subscriptions", "channels": [{"name": "ob_l2", "symbols": ["ADAUSD"]}]});
        assert_eq!(classify_other(&ack.to_string()), OtherFrame::Ack);
        let refused = json!({"type": "subscriptions", "channels": [{"name": "ob_l2", "error": "forbidden"}]});
        assert_eq!(classify_other(&refused.to_string()), OtherFrame::Refused("forbidden".into()));
        assert_eq!(classify_other(r#"{"type":"ob_l2","sy":"ADAUSD","b":"oops"}"#), OtherFrame::Unparsed);
        assert_eq!(classify_other(r#"{"type":"heartbeat"}"#), OtherFrame::Ignore);
    }

    #[test]
    fn reads_the_venues_refusal() {
        let v = json!({"type": "subscriptions", "channels": [{"name": "ob_l2", "error": "subscription forbidden on this invalid channel"}]});
        assert_eq!(refusal(&v).as_deref(), Some("subscription forbidden on this invalid channel"));
        assert_eq!(refusal(&json!({"type": "subscriptions", "channels": [{"name": "ob_l2", "symbols": ["ADAUSD"]}]})), None);
        // A success ack that echoes an empty error field is not a refusal.
        for e in [json!(null), json!(""), json!("  ")] {
            let ack = json!({"type": "subscriptions", "channels": [{"name": "ob_l2", "symbols": ["ADAUSD"], "error": e}]});
            assert_eq!(refusal(&ack), None);
            assert_eq!(classify_other(&ack.to_string()), OtherFrame::Ack);
        }
    }

    fn fast() -> DepthFeedTimings {
        DepthFeedTimings {
            connect_timeout: Duration::from_secs(2),
            silence: Duration::from_millis(300),
            retry_min: Duration::from_millis(10),
            retry_max: Duration::from_millis(40),
            reset_after: Duration::from_millis(100),
        }
    }

    /// A venue that answers each subscription by sending `frames(conn_no)`, then holds the connection open.
    async fn venue<F>(frames: F) -> (String, Arc<Mutex<Vec<Value>>>)
    where
        F: Fn(usize) -> Vec<String> + Send + Sync + 'static,
    {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let url = format!("ws://{}", listener.local_addr().unwrap());
        let subs: Arc<Mutex<Vec<Value>>> = Arc::default();
        let (subs2, frames) = (subs.clone(), Arc::new(frames));
        tokio::spawn(async move {
            let mut conn = 0;
            while let Ok((sock, _)) = listener.accept().await {
                let (n, subs3, frames) = (conn, subs2.clone(), frames.clone());
                conn += 1;
                tokio::spawn(async move {
                    let Ok(mut ws) = accept_async(sock).await else { return };
                    while let Some(Ok(Message::Text(t))) = ws.next().await {
                        let v: Value = serde_json::from_str(&t).unwrap();
                        if v["type"] == "subscribe" {
                            subs3.lock().unwrap().push(v);
                            for f in frames(n) {
                                if ws.send(Message::Text(f)).await.is_err() {
                                    return;
                                }
                            }
                        }
                    }
                });
            }
        });
        (url, subs)
    }

    fn senders(syms: &[&str]) -> (HashMap<String, DepthTx>, HashMap<String, DepthRx>) {
        let (mut tx, mut rx) = (HashMap::new(), HashMap::new());
        for s in syms {
            let (t, r) = watch::channel(None);
            tx.insert(s.to_string(), t);
            rx.insert(s.to_string(), r);
        }
        (tx, rx)
    }

    #[tokio::test]
    async fn one_connection_routes_each_symbols_book() {
        let (url, subs) = venue(|_| vec![ADA.to_string(), ADA.replace("ADAUSD", "KITEUSD").replace("0.2326", "0.0826")]).await;
        let (tx, mut rx) = senders(&["ADAUSD", "KITEUSD"]);
        tokio::spawn(async move { run_depth_feed(&url, tx, fast()).await });
        let ada = rx.get_mut("ADAUSD").unwrap();
        tokio::time::timeout(Duration::from_secs(5), ada.wait_for(|s| s.is_some())).await.unwrap().unwrap();
        let kite = rx.get_mut("KITEUSD").unwrap();
        let k = tokio::time::timeout(Duration::from_secs(5), kite.wait_for(|s| s.is_some())).await.unwrap().unwrap().clone();
        assert_eq!(k.unwrap().asks[0].0, 0.0826);
        let sub = subs.lock().unwrap()[0].clone();
        assert_eq!(sub["payload"]["channels"][0]["name"], "ob_l2");
        assert_eq!(sub["payload"]["channels"][0]["symbols"], json!(["ADAUSD", "KITEUSD"]));
    }

    #[tokio::test]
    async fn a_silent_connection_reconnects() {
        // The first connection sends nothing after the subscription; the second sends a book.
        let (url, subs) = venue(|n| if n == 0 { vec![] } else { vec![ADA.to_string()] }).await;
        let (tx, mut rx) = senders(&["ADAUSD"]);
        tokio::spawn(async move { run_depth_feed(&url, tx, fast()).await });
        let ada = rx.get_mut("ADAUSD").unwrap();
        tokio::time::timeout(Duration::from_secs(5), ada.wait_for(|s| s.is_some())).await.unwrap().unwrap();
        assert!(subs.lock().unwrap().len() >= 2);
    }

    #[tokio::test]
    async fn a_refused_subscription_is_retried() {
        let refused = json!({"type": "subscriptions", "channels": [{"name": "ob_l2", "error": "subscription forbidden on this invalid channel"}]}).to_string();
        let (url, subs) = venue(move |n| if n < 2 { vec![refused.clone()] } else { vec![ADA.to_string()] }).await;
        let (tx, mut rx) = senders(&["ADAUSD"]);
        tokio::spawn(async move { run_depth_feed(&url, tx, fast()).await });
        let ada = rx.get_mut("ADAUSD").unwrap();
        tokio::time::timeout(Duration::from_secs(5), ada.wait_for(|s| s.is_some())).await.unwrap().unwrap();
        assert!(subs.lock().unwrap().len() >= 3);
    }

    #[tokio::test]
    async fn a_book_for_an_unknown_symbol_does_not_stop_the_others() {
        let (url, _) = venue(|_| vec![ADA.replace("ADAUSD", "XRPUSD"), ADA.to_string()]).await;
        let (tx, mut rx) = senders(&["ADAUSD"]);
        tokio::spawn(async move { run_depth_feed(&url, tx, fast()).await });
        let ada = rx.get_mut("ADAUSD").unwrap();
        tokio::time::timeout(Duration::from_secs(5), ada.wait_for(|s| s.is_some())).await.unwrap().unwrap();
    }

    #[test]
    fn jitter_stays_within_twenty_percent() {
        for _ in 0..100 {
            let j = jitter(Duration::from_secs(10));
            assert!(j >= Duration::from_secs(8) && j < Duration::from_secs(12), "{j:?}");
        }
    }

    #[tokio::test]
    async fn stops_once_nobody_listens() {
        let (url, _) = venue(|_| vec![ADA.to_string()]).await;
        let (tx, rx) = senders(&["ADAUSD"]);
        drop(rx);
        let done = tokio::time::timeout(Duration::from_secs(3), run_depth_feed(&url, tx, fast())).await;
        assert!(done.is_ok(), "the feed ends when every receiver is gone");
    }
}
