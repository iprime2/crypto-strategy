//! Public ticker poller: `GET /v2/tickers/{symbol}` (funding rate, mark price, spot index) on its own task,
//! with a request timeout. Until 2026-10-14 the quote loop awaited this call on every iteration with no
//! timeout, so one hung request froze the loop, including its stale-book cancel, while the dead man's
//! switch was still acknowledged from another task. No keys are needed, so a dry-run sees the same data.

use std::time::{Duration, Instant};

use reqwest::Client;
use serde_json::Value;
use tokio::sync::watch;
use tracing::{info, warn};

use crate::DeltaEnvironment;

#[derive(Debug, Clone, PartialEq)]
pub struct TickerSnapshot {
    /// Funding rate in percent per 8 h, as Delta publishes it (`funding_rate`).
    pub funding_rate_pct: Option<f64>,
    pub mark_price: Option<f64>,
    /// Delta's spot index (`spot_price`).
    pub spot_price: Option<f64>,
    /// Venue time of the snapshot (`timestamp`, µs). The local clock is not Delta's, so ages use
    /// `received_at`.
    pub venue_ts_us: Option<i64>,
    pub received_at: Instant,
}

fn num(v: Option<&Value>) -> Option<f64> {
    let x = match v? {
        Value::String(s) => s.trim().parse::<f64>().ok()?,
        Value::Number(n) => n.as_f64()?,
        _ => return None,
    };
    x.is_finite().then_some(x)
}

/// One `/v2/tickers/{symbol}` response. Missing or malformed fields are `None`, never 0; a body without a
/// `result` object is `None`.
pub fn parse_ticker(body: &str, received_at: Instant) -> Option<TickerSnapshot> {
    let v: Value = serde_json::from_str(body).ok()?;
    let r = v.get("result").filter(|r| r.is_object())?;
    Some(TickerSnapshot {
        funding_rate_pct: num(r.get("funding_rate")),
        mark_price: num(r.get("mark_price")).filter(|p| *p > 0.0),
        spot_price: num(r.get("spot_price")).filter(|p| *p > 0.0),
        venue_ts_us: r
            .get("timestamp")
            .and_then(|t| t.as_i64().or_else(|| t.as_str()?.trim().parse().ok())),
        received_at,
    })
}

pub struct TickerPoller {
    pub env: DeltaEnvironment,
    /// Delta product symbol, e.g. `ADAUSD`.
    pub delta_symbol: String,
    pub every: Duration,
    pub timeout: Duration,
}

impl TickerPoller {
    /// Polls until every receiver is dropped. A failed or slow request keeps the last snapshot; its age
    /// tells the reader how old it is.
    pub async fn run(self, tx: watch::Sender<Option<TickerSnapshot>>) {
        let url = format!("{}/v2/tickers/{}", self.env.rest_base(), self.delta_symbol);
        self.run_at(&url, tx).await;
    }

    async fn run_at(&self, url: &str, tx: watch::Sender<Option<TickerSnapshot>>) {
        let client = match Client::builder()
            .timeout(self.timeout)
            .connect_timeout(self.timeout)
            .user_agent("mm-delta/0.1")
            .build()
        {
            Ok(c) => c,
            Err(e) => {
                warn!(symbol = %self.delta_symbol, ?e, "ticker client; funding carry stays 0");
                return;
            }
        };
        let mut failing = false;
        let mut tick = tokio::time::interval(self.every);
        tick.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
        loop {
            tick.tick().await;
            if tx.is_closed() {
                return;
            }
            let got = match client.get(url).send().await {
                Ok(resp) => match resp.text().await {
                    Ok(body) => parse_ticker(&body, Instant::now()).ok_or_else(|| "unparsed body".to_string()),
                    Err(e) => Err(e.to_string()),
                },
                Err(e) => Err(e.to_string()),
            };
            match got {
                Ok(snap) => {
                    if failing {
                        info!(symbol = %self.delta_symbol, "ticker recovered");
                        failing = false;
                    }
                    if tx.send(Some(snap)).is_err() {
                        return;
                    }
                }
                Err(e) => {
                    if !failing {
                        warn!(symbol = %self.delta_symbol, err = %e, "ticker poll failed; keeping the last snapshot");
                        failing = true;
                    }
                }
            }
        }
    }
}

/// Starts a poller task and returns its receiver (`None` until the first good response).
pub fn spawn_ticker_poller(
    env: DeltaEnvironment,
    delta_symbol: String,
    every: Duration,
    timeout: Duration,
) -> watch::Receiver<Option<TickerSnapshot>> {
    let (tx, rx) = watch::channel(None);
    let poller = TickerPoller { env, delta_symbol, every, timeout };
    tokio::spawn(async move { poller.run(tx).await });
    rx
}

#[cfg(test)]
mod tests {
    use super::*;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpListener;

    const ADA: &str = r#"{"success":true,"result":{"symbol":"ADAUSD","funding_rate":"-0.021308670218638942","mark_price":"0.23303072","spot_price":"0.233","mark_basis":"0.00013183","timestamp":1791889303335321,"turnover":12.5}}"#;

    #[test]
    fn parses_the_fields_the_bot_uses() {
        let now = Instant::now();
        let t = parse_ticker(ADA, now).expect("valid ticker");
        assert!((t.funding_rate_pct.unwrap() + 0.021308670218638942).abs() < 1e-15);
        assert_eq!(t.mark_price, Some(0.23303072));
        assert_eq!(t.spot_price, Some(0.233));
        assert_eq!(t.venue_ts_us, Some(1791889303335321));
        assert_eq!(t.received_at, now);
    }

    #[test]
    fn missing_or_malformed_fields_are_none_never_zero() {
        let now = Instant::now();
        let t = parse_ticker(r#"{"result":{"funding_rate":"n/a","mark_price":"0","spot_price":null,"timestamp":"17"}}"#, now)
            .expect("object result");
        assert_eq!(t.funding_rate_pct, None);
        assert_eq!(t.mark_price, None);
        assert_eq!(t.spot_price, None);
        assert_eq!(t.venue_ts_us, Some(17));
        assert!(parse_ticker(r#"{"success":false,"error":{"code":"x"}}"#, now).is_none());
        assert!(parse_ticker("not json", now).is_none());
        assert!(parse_ticker(r#"{"result":[]}"#, now).is_none());
    }

    /// One-route HTTP server: replies with `body` after `delay` on every request.
    async fn serve(body: &'static str, delay: Duration) -> String {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            loop {
                let Ok((mut sock, _)) = listener.accept().await else { return };
                tokio::spawn(async move {
                    let mut buf = [0u8; 2048];
                    let _ = sock.read(&mut buf).await;
                    tokio::time::sleep(delay).await;
                    let resp = format!(
                        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                        body.len(),
                        body
                    );
                    let _ = sock.write_all(resp.as_bytes()).await;
                });
            }
        });
        format!("http://{addr}/v2/tickers/ADAUSD")
    }

    fn poller(every_ms: u64, timeout_ms: u64) -> TickerPoller {
        TickerPoller {
            env: DeltaEnvironment::IndiaMainnet,
            delta_symbol: "ADAUSD".into(),
            every: Duration::from_millis(every_ms),
            timeout: Duration::from_millis(timeout_ms),
        }
    }

    #[tokio::test]
    async fn publishes_snapshots_from_the_venue() {
        let url = serve(ADA, Duration::ZERO).await;
        let (tx, mut rx) = watch::channel(None);
        tokio::spawn(async move { poller(20, 500).run_at(&url, tx).await });
        tokio::time::timeout(Duration::from_secs(5), rx.changed()).await.expect("snapshot").unwrap();
        assert_eq!(rx.borrow().as_ref().and_then(|t| t.mark_price), Some(0.23303072));
    }

    #[tokio::test]
    async fn a_hung_venue_times_out_and_never_blocks_the_reader() {
        // The server answers after 5 s; the poller gives up after 100 ms and keeps trying. The reader sees
        // no snapshot rather than waiting on the request.
        let url = serve(ADA, Duration::from_secs(5)).await;
        let (tx, rx) = watch::channel(None);
        let task = tokio::spawn(async move { poller(50, 100).run_at(&url, tx).await });
        tokio::time::sleep(Duration::from_millis(600)).await;
        assert!(rx.borrow().is_none());
        assert!(!task.is_finished(), "the poller keeps running after timeouts");
        task.abort();
    }

    #[tokio::test]
    async fn stops_when_every_receiver_is_gone() {
        let url = serve(ADA, Duration::ZERO).await;
        let (tx, rx) = watch::channel(None);
        drop(rx);
        let done = tokio::time::timeout(Duration::from_secs(2), poller(20, 500).run_at(&url, tx)).await;
        assert!(done.is_ok(), "run_at returns once nobody listens");
    }
}
