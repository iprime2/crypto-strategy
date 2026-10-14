//! Delta private websocket: our fills on `v2/user_trades`.
//!
//! On 13 Oct 2026 this feed delivered no fills for a whole live run. Every inventory change reached the bot
//! through the 5 s venue reconcile. The channel name is valid on Delta India: a subscription without a login
//! is refused as "Unauthorized user". The old loop sent the subscription right after the login without
//! waiting for the login reply, and dropped every frame that was not a fill, so a refusal was never seen.
//! Now the loop waits for the login reply before subscribing, logs every refusal with the venue's reason,
//! never exits on an error, and publishes its state so a live start can refuse to quote without fills.

use std::time::Duration;

use futures_util::{SinkExt, StreamExt};
use serde_json::Value;
use tokio::sync::watch;
use tokio_tungstenite::{connect_async, tungstenite::Message};
use tracing::{error, info, warn};

use crate::auth::DeltaCredentials;
use crate::products::delta_product_symbol;
use crate::DeltaEnvironment;

pub const FILLS_CHANNEL: &str = "v2/user_trades";

/// What the feed has achieved, for logs and the live start check.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct PrivateFeedState {
    /// The venue confirmed the fills subscription on the current connection.
    pub subscribed: bool,
    pub connects: u64,
    pub fills: u64,
    /// The last failure (connect, login, subscription, read, silence), with the venue's reason when given.
    pub last_error: Option<String>,
}

/// One private frame, as far as the feed cares.
#[derive(Debug, PartialEq)]
pub enum PrivateFrame {
    Fill,
    /// Reply to the login: Ok, or the venue's reason.
    Auth(Result<(), String>),
    /// Reply to the fills subscription: Ok, or the venue's reason.
    Subscription(Result<(), String>),
    Error(String),
    Heartbeat,
    Other,
}

/// The frame without anything that could carry credentials, cut to a log-friendly length.
fn brief(v: &Value) -> String {
    let mut v = v.clone();
    if let Some(o) = v.as_object_mut() {
        o.retain(|k, _| {
            let k = k.to_ascii_lowercase();
            !(k.contains("key") || k.contains("signature") || k == "payload")
        });
    }
    let s = v.to_string();
    if s.len() > 300 {
        format!("{}...", &s[..s.char_indices().nth(300).map(|(i, _)| i).unwrap_or(s.len())])
    } else {
        s
    }
}

fn reason(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        other => brief(other),
    }
}

pub fn classify_private_frame(v: &Value) -> PrivateFrame {
    let ty = v.get("type").and_then(|t| t.as_str()).unwrap_or("");
    if ty == FILLS_CHANNEL {
        return PrivateFrame::Fill;
    }
    if ty == "subscriptions" {
        let ours = v
            .get("channels")
            .and_then(|c| c.as_array())
            .and_then(|cs| cs.iter().find(|c| c.get("name").and_then(|n| n.as_str()) == Some(FILLS_CHANNEL)));
        return match ours {
            Some(c) => match c.get("error") {
                Some(e) => PrivateFrame::Subscription(Err(reason(e))),
                None => PrivateFrame::Subscription(Ok(())),
            },
            None => PrivateFrame::Other,
        };
    }
    if ty == "heartbeat" {
        return PrivateFrame::Heartbeat;
    }
    if ty.contains("auth") {
        let ok = v.get("success").and_then(|s| s.as_bool()).unwrap_or(false)
            || v
                .get("status")
                .and_then(|s| s.as_str())
                .is_some_and(|s| s.eq_ignore_ascii_case("authenticated"));
        return if ok { PrivateFrame::Auth(Ok(())) } else { PrivateFrame::Auth(Err(brief(v))) };
    }
    if ty == "error" || v.get("error").is_some() {
        return PrivateFrame::Error(brief(v));
    }
    PrivateFrame::Other
}

/// Timings for the private feed. `Default` is what the bot runs with.
#[derive(Debug, Clone, Copy)]
pub struct PrivateWsTimings {
    pub connect_timeout: Duration,
    /// How long to wait for the login reply before subscribing anyway.
    pub auth_wait: Duration,
    /// Reconnect when nothing arrives for this long (heartbeats come every ~30 s once enabled).
    pub silence: Duration,
    /// Pause after a dropped connection.
    pub reconnect_delay: Duration,
    /// Backoff after a refused login or subscription: doubles from `refused_min` up to `refused_max`.
    pub refused_min: Duration,
    pub refused_max: Duration,
}

impl Default for PrivateWsTimings {
    fn default() -> Self {
        Self {
            connect_timeout: Duration::from_secs(10),
            auth_wait: Duration::from_secs(10),
            silence: Duration::from_secs(45),
            reconnect_delay: Duration::from_secs(3),
            refused_min: Duration::from_secs(5),
            refused_max: Duration::from_secs(60),
        }
    }
}

pub struct DeltaPrivateWs {
    pub env: DeltaEnvironment,
    pub creds: DeltaCredentials,
}

enum Ended {
    /// The connection dropped or went silent: reconnect after `reconnect_delay`.
    Dropped,
    /// The venue refused the login or the subscription: back off.
    Refused,
}

impl DeltaPrivateWs {
    /// Streams our fills to `on_fill(delta_symbol, frame)` forever, reconnecting on every failure.
    pub async fn run_user_trades<F>(&self, mm_symbols: &[String], state: watch::Sender<PrivateFeedState>, on_fill: F)
    where
        F: FnMut(&str, &Value) + Send + 'static,
    {
        self.run_user_trades_at(self.env.ws_private(), mm_symbols, PrivateWsTimings::default(), state, on_fill)
            .await
    }

    pub async fn run_user_trades_at<F>(
        &self,
        url: &str,
        mm_symbols: &[String],
        t: PrivateWsTimings,
        state: watch::Sender<PrivateFeedState>,
        mut on_fill: F,
    ) where
        F: FnMut(&str, &Value) + Send + 'static,
    {
        let delta_syms: Vec<String> = mm_symbols.iter().map(|s| delta_product_symbol(s)).collect();
        let mut refused_backoff = t.refused_min;
        loop {
            state.send_modify(|s| {
                s.connects += 1;
                s.subscribed = false;
            });
            let ended = self.session(url, &delta_syms, t, &state, &mut on_fill).await;
            if state.borrow().subscribed {
                refused_backoff = t.refused_min; // the venue accepted us last time
            }
            state.send_modify(|s| s.subscribed = false);
            let pause = match ended {
                Ended::Dropped => t.reconnect_delay,
                Ended::Refused => {
                    let p = refused_backoff;
                    refused_backoff = (refused_backoff * 2).min(t.refused_max);
                    p
                }
            };
            tokio::time::sleep(pause).await;
        }
    }

    async fn session<F>(
        &self,
        url: &str,
        delta_syms: &[String],
        t: PrivateWsTimings,
        state: &watch::Sender<PrivateFeedState>,
        on_fill: &mut F,
    ) -> Ended
    where
        F: FnMut(&str, &Value),
    {
        let fail = |what: &str, why: String| {
            state.send_modify(|s| s.last_error = Some(format!("{what}: {why}")));
        };
        let ws = match tokio::time::timeout(t.connect_timeout, connect_async(url)).await {
            Ok(Ok((ws, _))) => ws,
            Ok(Err(e)) => {
                warn!(?e, "delta private connect");
                fail("connect", e.to_string());
                return Ended::Dropped;
            }
            Err(_) => {
                warn!("delta private connect timed out");
                fail("connect", "timed out".into());
                return Ended::Dropped;
            }
        };
        let (mut write, mut read) = ws.split();

        let ts = chrono::Utc::now().timestamp().to_string();
        let auth = serde_json::json!({
            "type": "key-auth",
            "payload": {
                "api-key": self.creds.api_key,
                "signature": self.creds.sign_ws_auth(&ts),
                "timestamp": ts
            }
        });
        if let Err(e) = write.send(Message::Text(auth.to_string())).await {
            warn!(?e, "delta private login send");
            fail("login send", e.to_string());
            return Ended::Dropped;
        }

        // Wait for the login reply before subscribing; the venue refuses a private subscription it has not
        // authenticated yet.
        let deadline = tokio::time::Instant::now() + t.auth_wait;
        let mut logged_in = false;
        while !logged_in {
            let next = match tokio::time::timeout_at(deadline, read.next()).await {
                Err(_) => {
                    warn!(wait = ?t.auth_wait, "delta private: no login reply; subscribing anyway");
                    break;
                }
                Ok(None) => {
                    warn!("delta private closed before the login reply");
                    fail("login", "connection closed before the reply".into());
                    return Ended::Dropped;
                }
                Ok(Some(Err(e))) => {
                    warn!(?e, "delta private read");
                    fail("read", e.to_string());
                    return Ended::Dropped;
                }
                Ok(Some(Ok(m))) => m,
            };
            let Some(v) = text_json(&next) else { continue };
            match classify_private_frame(&v) {
                PrivateFrame::Auth(Ok(())) => {
                    info!("delta private login ok");
                    logged_in = true;
                }
                PrivateFrame::Auth(Err(why)) => {
                    error!(reply = %why, "delta private login refused; fills will reach the bot only through the venue reconcile");
                    fail("login refused", why);
                    return Ended::Refused;
                }
                PrivateFrame::Error(why) => warn!(frame = %why, "delta private error frame"),
                _ => {}
            }
        }

        let sub = serde_json::json!({
            "type": "subscribe",
            "payload": { "channels": [{ "name": FILLS_CHANNEL, "symbols": delta_syms }] }
        });
        for msg in [sub, serde_json::json!({ "type": "enable_heartbeat" })] {
            if let Err(e) = write.send(Message::Text(msg.to_string())).await {
                warn!(?e, "delta private send");
                fail("subscribe send", e.to_string());
                return Ended::Dropped;
            }
        }

        loop {
            let msg = match tokio::time::timeout(t.silence, read.next()).await {
                Err(_) => {
                    warn!(silence = ?t.silence, "delta private silent; reconnecting");
                    fail("read", "silent".into());
                    return Ended::Dropped;
                }
                Ok(None) => {
                    warn!("delta private stream closed; reconnecting");
                    fail("read", "stream closed".into());
                    return Ended::Dropped;
                }
                Ok(Some(Err(e))) => {
                    warn!(?e, "delta private read; reconnecting");
                    fail("read", e.to_string());
                    return Ended::Dropped;
                }
                Ok(Some(Ok(m))) => m,
            };
            let Some(v) = text_json(&msg) else { continue };
            match classify_private_frame(&v) {
                PrivateFrame::Fill => {
                    let sym = v.get("sy").and_then(|s| s.as_str()).unwrap_or("");
                    state.send_modify(|s| s.fills += 1);
                    on_fill(sym, &v);
                }
                PrivateFrame::Subscription(Ok(())) => {
                    info!(channel = FILLS_CHANNEL, symbols = ?delta_syms, "delta fills subscribed");
                    state.send_modify(|s| {
                        s.subscribed = true;
                        s.last_error = None;
                    });
                }
                PrivateFrame::Subscription(Err(why)) => {
                    error!(reason = %why, "delta fills subscription refused; fills will reach the bot only through the venue reconcile");
                    fail("subscription refused", why);
                    return Ended::Refused;
                }
                PrivateFrame::Auth(Err(why)) => {
                    error!(reply = %why, "delta private login refused");
                    fail("login refused", why);
                    return Ended::Refused;
                }
                PrivateFrame::Error(why) => warn!(frame = %why, "delta private error frame"),
                PrivateFrame::Auth(Ok(())) | PrivateFrame::Heartbeat | PrivateFrame::Other => {}
            }
        }
    }
}

fn text_json(msg: &Message) -> Option<Value> {
    match msg {
        Message::Text(t) => serde_json::from_str(t).ok(),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::sync::{Arc, Mutex};
    use tokio::net::TcpListener;
    use tokio_tungstenite::accept_async;

    #[test]
    fn classifies_the_frames_the_feed_acts_on() {
        assert_eq!(classify_private_frame(&json!({"type": "v2/user_trades", "sy": "ADAUSD"})), PrivateFrame::Fill);
        assert_eq!(
            classify_private_frame(&json!({"type": "subscriptions", "channels": [{"name": "v2/user_trades", "symbols": ["ADAUSD"]}]})),
            PrivateFrame::Subscription(Ok(()))
        );
        // The reply Delta India sent to a subscription without a login (probed 2026-10-14).
        assert_eq!(
            classify_private_frame(&json!({"type": "subscriptions", "channels": [{"error": "subscription forbidden on this channel. Unauthorized user", "name": "v2/user_trades"}]})),
            PrivateFrame::Subscription(Err("subscription forbidden on this channel. Unauthorized user".into()))
        );
        // A reply about another channel is not ours.
        assert_eq!(
            classify_private_frame(&json!({"type": "subscriptions", "channels": [{"name": "orders"}]})),
            PrivateFrame::Other
        );
        assert_eq!(classify_private_frame(&json!({"type": "key-auth", "success": true})), PrivateFrame::Auth(Ok(())));
        assert_eq!(
            classify_private_frame(&json!({"type": "auth", "status": "authenticated"})),
            PrivateFrame::Auth(Ok(()))
        );
        assert!(matches!(
            classify_private_frame(&json!({"type": "key-auth", "success": false, "error": {"code": "InvalidApiKey"}})),
            PrivateFrame::Auth(Err(why)) if why.contains("InvalidApiKey")
        ));
        assert_eq!(classify_private_frame(&json!({"type": "heartbeat", "ts_origin": 1})), PrivateFrame::Heartbeat);
        assert!(matches!(classify_private_frame(&json!({"type": "error", "message": "bad"})), PrivateFrame::Error(_)));
        assert_eq!(classify_private_frame(&json!({"type": "v2/orders"})), PrivateFrame::Other);
    }

    #[test]
    fn logged_replies_never_carry_credential_fields() {
        let v = json!({"type": "key-auth", "success": false, "api-key": "AK", "signature": "SIG", "payload": {"api-key": "AK"}, "error": "x"});
        let PrivateFrame::Auth(Err(why)) = classify_private_frame(&v) else { panic!("auth refusal") };
        assert!(!why.contains("AK") && !why.contains("SIG"), "{why}");
        assert!(why.contains("\"error\""));
    }

    fn creds() -> DeltaCredentials {
        DeltaCredentials { api_key: "test-key".into(), api_secret: "test-secret".into() }
    }

    fn fast() -> PrivateWsTimings {
        PrivateWsTimings {
            connect_timeout: Duration::from_secs(2),
            auth_wait: Duration::from_millis(300),
            silence: Duration::from_secs(2),
            reconnect_delay: Duration::from_millis(20),
            refused_min: Duration::from_millis(20),
            refused_max: Duration::from_millis(40),
        }
    }

    /// A one-path websocket venue. `script(conn_no, frame)` returns the replies for each frame we send.
    async fn venue<S>(script: S) -> (String, Arc<Mutex<Vec<Vec<Value>>>>)
    where
        S: Fn(usize, &Value) -> Vec<Value> + Send + Sync + 'static,
    {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let url = format!("ws://{}", listener.local_addr().unwrap());
        let seen: Arc<Mutex<Vec<Vec<Value>>>> = Arc::default();
        let script = Arc::new(script);
        let seen2 = seen.clone();
        tokio::spawn(async move {
            let mut conn = 0;
            while let Ok((sock, _)) = listener.accept().await {
                let n = conn;
                conn += 1;
                seen2.lock().unwrap().push(Vec::new());
                let (seen3, script) = (seen2.clone(), script.clone());
                tokio::spawn(async move {
                    let Ok(mut ws) = accept_async(sock).await else { return };
                    while let Some(Ok(Message::Text(t))) = ws.next().await {
                        let v: Value = serde_json::from_str(&t).unwrap();
                        seen3.lock().unwrap()[n].push(v.clone());
                        for reply in script(n, &v) {
                            if ws.send(Message::Text(reply.to_string())).await.is_err() {
                                return;
                            }
                        }
                    }
                });
            }
        });
        (url, seen)
    }

    fn feed() -> DeltaPrivateWs {
        DeltaPrivateWs { env: DeltaEnvironment::DemoIndia, creds: creds() }
    }

    async fn wait_until(rx: &mut watch::Receiver<PrivateFeedState>, f: impl Fn(&PrivateFeedState) -> bool) -> PrivateFeedState {
        tokio::time::timeout(Duration::from_secs(5), rx.wait_for(|s| f(s))).await.expect("state reached").unwrap().clone()
    }

    #[tokio::test]
    async fn logs_in_before_subscribing_and_delivers_fills() {
        let (url, seen) = venue(|_, v| match v["type"].as_str() {
            Some("key-auth") => vec![json!({"type": "key-auth", "success": true})],
            Some("subscribe") => vec![
                json!({"type": "subscriptions", "channels": [{"name": "v2/user_trades", "symbols": ["ADAUSD"]}]}),
                json!({"type": "v2/user_trades", "sy": "ADAUSD", "S": "buy", "s": 200, "p": "0.2398"}),
            ],
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        let got: Arc<Mutex<Vec<String>>> = Arc::default();
        let got2 = got.clone();
        tokio::spawn(async move {
            feed()
                .run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, move |sym, _| got2.lock().unwrap().push(sym.into()))
                .await
        });
        let s = wait_until(&mut rx, |s| s.subscribed && s.fills == 1).await;
        assert_eq!(s.last_error, None);
        assert_eq!(*got.lock().unwrap(), vec!["ADAUSD".to_string()]);
        let frames = seen.lock().unwrap()[0].clone();
        assert_eq!(frames[0]["type"], "key-auth");
        assert_eq!(frames[1]["type"], "subscribe");
        assert_eq!(frames[1]["payload"]["channels"][0]["name"], "v2/user_trades");
    }

    #[tokio::test]
    async fn a_refused_subscription_is_reported_and_retried() {
        let (url, seen) = venue(|_, v| match v["type"].as_str() {
            Some("key-auth") => vec![json!({"type": "key-auth", "success": true})],
            Some("subscribe") => vec![json!({"type": "subscriptions", "channels": [{"error": "subscription forbidden on this channel. Unauthorized user", "name": "v2/user_trades"}]})],
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        tokio::spawn(async move { feed().run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, |_, _| {}).await });
        let s = wait_until(&mut rx, |s| s.connects >= 3).await;
        assert!(!s.subscribed);
        assert!(s.last_error.as_deref().unwrap_or("").contains("Unauthorized user"), "{:?}", s.last_error);
        assert!(seen.lock().unwrap().len() >= 2, "the feed reconnects after a refusal");
    }

    #[tokio::test]
    async fn a_refused_login_stops_before_subscribing() {
        let (url, seen) = venue(|_, v| match v["type"].as_str() {
            Some("key-auth") => vec![json!({"type": "key-auth", "success": false, "error": {"code": "InvalidApiKey"}})],
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        tokio::spawn(async move { feed().run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, |_, _| {}).await });
        let s = wait_until(&mut rx, |s| s.connects >= 2 && s.last_error.is_some()).await;
        assert!(s.last_error.unwrap().contains("InvalidApiKey"));
        assert!(seen.lock().unwrap().iter().flatten().all(|f| f["type"] != "subscribe"));
    }

    #[tokio::test]
    async fn a_dropped_connection_reconnects_instead_of_ending_the_task() {
        // The first connection never answers the subscription, so the client gives up after `silence`;
        // the second one works.
        let (url, _) = venue(|conn, v| match (conn, v["type"].as_str()) {
            (_, Some("key-auth")) => vec![json!({"type": "key-auth", "success": true})],
            (0, Some("subscribe")) => vec![],
            (_, Some("subscribe")) => vec![json!({"type": "subscriptions", "channels": [{"name": "v2/user_trades"}]})],
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        let task = tokio::spawn(async move { feed().run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, |_, _| {}).await });
        let s = wait_until(&mut rx, |s| s.subscribed).await;
        assert!(s.connects >= 2);
        assert!(!task.is_finished());
        task.abort();
    }

    #[tokio::test]
    async fn no_login_reply_still_subscribes_after_the_wait() {
        let (url, seen) = venue(|_, v| match v["type"].as_str() {
            Some("subscribe") => vec![json!({"type": "subscriptions", "channels": [{"name": "v2/user_trades"}]})],
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        tokio::spawn(async move { feed().run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, |_, _| {}).await });
        wait_until(&mut rx, |s| s.subscribed).await;
        assert_eq!(seen.lock().unwrap()[0][1]["type"], "subscribe");
    }
}
