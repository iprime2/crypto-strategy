//! Delta private websocket: our fills on `v2/user_trades`.
//!
//! On 13 Oct 2026 this feed delivered no fills for a whole live run. Every inventory change reached the bot
//! through the 5 s venue reconcile. The channel name is valid on Delta India: a subscription without a login
//! is refused as "Unauthorized user". The old loop sent the subscription right after the login without
//! waiting for the login reply, and dropped every frame that was not a fill, so a refusal was never seen.
//! Now the loop waits for the login reply before subscribing, logs every refusal with the venue's reason,
//! never exits on an error, and publishes its state so a live start can refuse to quote without fills.
//!
//! Delta's login reply format has not been seen yet (no signed probe), so a reply counts as a refusal only
//! on an explicit failure marker, the first reply is logged (credentials stripped), and the subscription
//! acknowledgement is what proves the feed works.

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
    /// Connections the venue refused (login or subscription) or closed before answering the login.
    pub refusals: u64,
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

const MAX_REASON: usize = 300;

fn secret_field(k: &str) -> bool {
    let k = k.to_ascii_lowercase();
    k == "payload" || ["key", "sig", "secret", "token", "pass"].iter().any(|w| k.contains(w))
}

/// Drops credential-named fields at every depth.
fn strip(v: &Value) -> Value {
    match v {
        Value::Object(o) => Value::Object(o.iter().filter(|(k, _)| !secret_field(k)).map(|(k, v)| (k.clone(), strip(v))).collect()),
        Value::Array(a) => Value::Array(a.iter().map(strip).collect()),
        other => other.clone(),
    }
}

/// A venue reply as a single log-safe line: credential fields stripped, JSON-escaped (no newlines), cut at
/// 300 characters. Values are redacted separately (`redact`), since only the session knows them.
fn brief(v: &Value) -> String {
    let s = strip(v).to_string();
    match s.char_indices().nth(MAX_REASON) {
        Some((i, _)) => format!("{}...", &s[..i]),
        None => s,
    }
}

/// Replaces every occurrence of `secrets` (the API key, the login signature) in `s`.
fn redact(s: &str, secrets: &[&str]) -> String {
    secrets
        .iter()
        .filter(|x| x.len() >= 4)
        .fold(s.to_string(), |acc, x| acc.replace(x, "<redacted>"))
}

/// A venue field that carries something: not missing, null or a blank string.
pub(crate) fn present(v: Option<&Value>) -> Option<&Value> {
    v.filter(|e| match e {
        Value::Null => false,
        Value::String(s) => !s.trim().is_empty(),
        _ => true,
    })
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
            Some(c) => match present(c.get("error")) {
                Some(e) => PrivateFrame::Subscription(Err(brief(e))),
                None => PrivateFrame::Subscription(Ok(())),
            },
            None => PrivateFrame::Other,
        };
    }
    if ty == "heartbeat" {
        return PrivateFrame::Heartbeat;
    }
    let message = v.get("message").and_then(|m| m.as_str()).unwrap_or("");
    let auth_like = ty.to_ascii_lowercase().contains("auth")
        || (ty == "success" && message.to_ascii_lowercase().contains("authenticat"));
    if auth_like {
        // Refused only on an explicit failure marker; any other login reply is taken as accepted, and the
        // subscription acknowledgement confirms it.
        let failed = v.get("success").and_then(|s| s.as_bool()) == Some(false)
            || present(v.get("error")).is_some()
            || v
                .get("status")
                .and_then(|s| s.as_str())
                .is_some_and(|s| !s.eq_ignore_ascii_case("authenticated") && !s.eq_ignore_ascii_case("ok"));
        return if failed { PrivateFrame::Auth(Err(brief(v))) } else { PrivateFrame::Auth(Ok(())) };
    }
    if ty == "error" || present(v.get("error")).is_some() {
        return PrivateFrame::Error(brief(v));
    }
    PrivateFrame::Other
}

/// One of our fills from a `v2/user_trades` frame.
#[derive(Debug, Clone, PartialEq)]
pub struct UserTrade {
    pub bought: bool,
    /// Size in contracts (Delta sends it as a string).
    pub contracts: i64,
    pub price: f64,
    /// Delta's fill id (`f`); failing that, order id and venue time, so two fills of one order stay apart.
    pub fill_id: String,
    pub order_id: Option<u64>,
    pub client_order_id: Option<String>,
    pub maker: bool,
    pub venue_ts_us: Option<i64>,
}

fn json_num(v: Option<&Value>) -> Option<f64> {
    match v? {
        Value::String(s) => s.trim().parse::<f64>().ok(),
        Value::Number(n) => n.as_f64(),
        _ => None,
    }
    .filter(|x| x.is_finite())
}

fn json_text(v: Option<&Value>) -> Option<String> {
    match v? {
        Value::String(s) => Some(s.clone()),
        Value::Number(n) => Some(n.to_string()),
        _ => None,
    }
}

/// Parses a `v2/user_trades` frame as Delta India sends it (captured 15 Oct 2026):
/// `{"R":"normal","S":"buy","c":"<client id>","f":"<fill id>","i":84,"o":2175436569,"p":"81140.5","po":1,
/// "r":"maker","s":"1","se":1,"sy":"BTCUSD","t":1792064274527989,"type":"v2/user_trades","u":...}`.
/// `i` is the product id, not a trade id. `None` when the side, size or price cannot be read.
pub fn parse_user_trade(v: &Value) -> Option<UserTrade> {
    let side = v.get("S").and_then(|s| s.as_str())?;
    let bought = match side.to_ascii_lowercase().as_str() {
        "buy" => true,
        "sell" => false,
        _ => return None,
    };
    let size = json_num(v.get("s")).filter(|x| *x > 0.0)?;
    let price = json_num(v.get("p")).filter(|x| *x > 0.0)?;
    let order_id = json_num(v.get("o")).filter(|x| *x >= 0.0).map(|x| x as u64);
    let venue_ts_us = json_num(v.get("t")).map(|x| x as i64);
    let fill_id = json_text(v.get("f")).filter(|s| !s.is_empty()).or_else(|| {
        Some(format!("{}-{}", order_id?, venue_ts_us?))
    })?;
    Some(UserTrade {
        bought,
        contracts: size.round() as i64,
        price,
        fill_id,
        order_id,
        client_order_id: json_text(v.get("c")).filter(|s| !s.is_empty()),
        maker: v.get("r").and_then(|r| r.as_str()).map_or(true, |r| !r.eq_ignore_ascii_case("taker")),
        venue_ts_us,
    })
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
    /// The venue refused the login or the subscription, or closed before answering the login: back off.
    Refused,
}

fn close_reason(frame: &Option<tokio_tungstenite::tungstenite::protocol::CloseFrame<'_>>) -> String {
    match frame {
        Some(f) => format!("closed by the venue ({}): {}", u16::from(f.code), f.reason),
        None => "closed by the venue".into(),
    }
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
        let mut logged_reply = false;
        loop {
            state.send_modify(|s| {
                s.connects += 1;
                s.subscribed = false;
            });
            let ended = self.session(url, &delta_syms, t, &state, &mut on_fill, &mut logged_reply).await;
            if state.borrow().subscribed {
                refused_backoff = t.refused_min; // the venue accepted us last time
            }
            state.send_modify(|s| s.subscribed = false);
            let pause = match ended {
                Ended::Dropped => t.reconnect_delay,
                Ended::Refused => {
                    state.send_modify(|s| s.refusals += 1);
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
        logged_reply: &mut bool,
    ) -> Ended
    where
        F: FnMut(&str, &Value),
    {
        let ts = chrono::Utc::now().timestamp().to_string();
        let sig = self.creds.sign_ws_auth(&ts);
        let secrets = [self.creds.api_key.as_str(), sig.as_str()];
        let safe = |s: &str| redact(s, &secrets);
        let fail = |what: &str, why: &str| {
            let why = redact(why, &secrets);
            state.send_modify(|s| s.last_error = Some(format!("{what}: {why}")));
        };

        let ws = match tokio::time::timeout(t.connect_timeout, connect_async(url)).await {
            Ok(Ok((ws, _))) => ws,
            Ok(Err(e)) => {
                warn!(err = %e, "delta private connect");
                fail("connect", &e.to_string());
                return Ended::Dropped;
            }
            Err(_) => {
                warn!("delta private connect timed out");
                fail("connect", "timed out");
                return Ended::Dropped;
            }
        };
        let (mut write, mut read) = ws.split();

        let auth = serde_json::json!({
            "type": "key-auth",
            "payload": { "api-key": self.creds.api_key, "signature": sig, "timestamp": ts }
        });
        if let Err(e) = write.send(Message::Text(auth.to_string())).await {
            warn!(err = %e, "delta private login send");
            fail("login send", &e.to_string());
            return Ended::Dropped;
        }

        // Wait for the login reply before subscribing: the venue refuses a private subscription it has not
        // authenticated yet. A venue error frame here is kept, so a later refusal names the first cause.
        let deadline = tokio::time::Instant::now() + t.auth_wait;
        let mut login_note: Option<String> = None;
        loop {
            let next = match tokio::time::timeout_at(deadline, read.next()).await {
                Err(_) => {
                    warn!(wait = ?t.auth_wait, "delta private: no login reply; subscribing anyway");
                    break;
                }
                Ok(None) => {
                    warn!("delta private closed before the login reply");
                    fail("login", login_note.as_deref().unwrap_or("connection closed before the reply"));
                    return Ended::Refused;
                }
                Ok(Some(Err(e))) => {
                    warn!(err = %e, "delta private read");
                    fail("read", &e.to_string());
                    return Ended::Dropped;
                }
                Ok(Some(Ok(m))) => m,
            };
            if let Message::Close(cf) = &next {
                let why = safe(&close_reason(cf));
                error!(reason = %why, "delta private login: the venue closed the connection");
                fail("login", &why);
                return Ended::Refused;
            }
            let Some(v) = text_json(&next) else { continue };
            match classify_private_frame(&v) {
                PrivateFrame::Auth(r) => {
                    if !*logged_reply {
                        info!(reply = %safe(&brief(&v)), "delta private login reply");
                        *logged_reply = true;
                    }
                    match r {
                        Ok(()) => {
                            info!("delta private login ok");
                            break;
                        }
                        Err(why) => {
                            let why = safe(&why);
                            error!(reply = %why, "delta private login refused; fills will reach the bot only through the venue reconcile");
                            fail("login refused", &why);
                            return Ended::Refused;
                        }
                    }
                }
                PrivateFrame::Error(why) => {
                    let why = safe(&why);
                    warn!(frame = %why, "delta private error frame during login");
                    login_note = Some(why);
                }
                _ => {}
            }
        }

        let sub = serde_json::json!({
            "type": "subscribe",
            "payload": { "channels": [{ "name": FILLS_CHANNEL, "symbols": delta_syms }] }
        });
        for msg in [sub, serde_json::json!({ "type": "enable_heartbeat" })] {
            if let Err(e) = write.send(Message::Text(msg.to_string())).await {
                warn!(err = %e, "delta private send");
                fail("subscribe send", &e.to_string());
                return Ended::Dropped;
            }
        }

        loop {
            let msg = match tokio::time::timeout(t.silence, read.next()).await {
                Err(_) => {
                    warn!(silence = ?t.silence, "delta private silent; reconnecting");
                    fail("read", "silent");
                    return Ended::Dropped;
                }
                Ok(None) => {
                    warn!("delta private stream closed; reconnecting");
                    fail("read", "stream closed");
                    return Ended::Dropped;
                }
                Ok(Some(Err(e))) => {
                    warn!(err = %e, "delta private read; reconnecting");
                    fail("read", &e.to_string());
                    return Ended::Dropped;
                }
                Ok(Some(Ok(m))) => m,
            };
            if let Message::Close(cf) = &msg {
                let why = safe(&close_reason(cf));
                warn!(reason = %why, "delta private closed; reconnecting");
                fail("read", &why);
                return Ended::Dropped;
            }
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
                    let why = match &login_note {
                        Some(note) => format!("{} (after a venue error during login: {note})", safe(&why)),
                        None => safe(&why),
                    };
                    error!(reason = %why, "delta fills subscription refused; fills will reach the bot only through the venue reconcile");
                    fail("subscription refused", &why);
                    return Ended::Refused;
                }
                PrivateFrame::Auth(Err(why)) => {
                    let why = safe(&why);
                    error!(reply = %why, "delta private login refused");
                    fail("login refused", &why);
                    return Ended::Refused;
                }
                PrivateFrame::Error(why) => warn!(frame = %safe(&why), "delta private error frame"),
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
    use tokio_tungstenite::tungstenite::protocol::{frame::coding::CloseCode, CloseFrame};

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
            PrivateFrame::Subscription(Err("\"subscription forbidden on this channel. Unauthorized user\"".into()))
        );
        // A null or empty error is not a refusal.
        for e in [json!(null), json!("")] {
            assert_eq!(
                classify_private_frame(&json!({"type": "subscriptions", "channels": [{"name": "v2/user_trades", "error": e}]})),
                PrivateFrame::Subscription(Ok(()))
            );
        }
        // A reply about another channel is not ours.
        assert_eq!(
            classify_private_frame(&json!({"type": "subscriptions", "channels": [{"name": "orders"}]})),
            PrivateFrame::Other
        );
        assert_eq!(classify_private_frame(&json!({"type": "heartbeat", "ts_origin": 1})), PrivateFrame::Heartbeat);
        assert!(matches!(classify_private_frame(&json!({"type": "error", "message": "bad"})), PrivateFrame::Error(_)));
        assert_eq!(classify_private_frame(&json!({"type": "v2/orders"})), PrivateFrame::Other);
    }

    #[test]
    fn a_login_reply_is_a_refusal_only_on_an_explicit_failure_marker() {
        for ok in [
            json!({"type": "key-auth", "success": true}),
            json!({"type": "auth", "status": "authenticated"}),
            json!({"type": "auth", "message": "Authenticated"}),
            json!({"type": "key-auth", "status_code": 200}),
            json!({"type": "success", "message": "Authenticated"}),
        ] {
            assert_eq!(classify_private_frame(&ok), PrivateFrame::Auth(Ok(())), "{ok}");
        }
        for bad in [
            json!({"type": "key-auth", "success": false, "error": {"code": "InvalidApiKey"}}),
            json!({"type": "auth", "error": "SignatureExpired"}),
            json!({"type": "key-auth", "status": "unauthorized"}),
        ] {
            assert!(matches!(classify_private_frame(&bad), PrivateFrame::Auth(Err(_))), "{bad}");
        }
    }

    #[test]
    fn logged_replies_never_carry_credentials() {
        // Credential-named fields at any depth, in arrays, and under other spellings.
        let v = json!({"type": "key-auth", "success": false, "api-key": "AK0", "error": {"context": {"api-key": "AK1", "signature": "SIG1"}},
                       "errors": [{"apiKey": "AK3", "sig": "SIG3"}], "secret": "S", "token": "T", "payload": {"api-key": "AK2"}});
        let PrivateFrame::Auth(Err(why)) = classify_private_frame(&v) else { panic!("auth refusal") };
        for leak in ["AK0", "AK1", "AK2", "AK3", "SIG1", "SIG3", "\"S\"", "\"T\""] {
            assert!(!why.contains(leak), "{leak} in {why}");
        }
        // Values echoed inside free text are redacted by value.
        assert_eq!(redact("invalid api key AKEY-123 for SIGVALUE", &["AKEY-123", "SIGVALUE"]), "invalid api key <redacted> for <redacted>");
        // One line, bounded.
        let long = classify_private_frame(&json!({"type": "error", "message": format!("a\nb{}", "x".repeat(5000))}));
        let PrivateFrame::Error(why) = long else { panic!("error frame") };
        assert!(!why.contains('\n') && why.chars().count() <= MAX_REASON + 3, "{}", why.len());
    }

    fn creds() -> DeltaCredentials {
        DeltaCredentials { api_key: "test-key-123".into(), api_secret: "test-secret".into() }
    }

    /// The frame captured on demo on 15 Oct 2026 (a 1-contract post-only BTCUSD bid filled as maker).
    const REAL_FILL: &str = r#"{"R":"normal","S":"buy","c":"probe-1792064272244","f":"7257cf23e12c439e96894ef3ed6bfcd3","i":84,"o":2175436569,"p":"81140.5","po":1,"r":"maker","s":"1","se":1,"sy":"BTCUSD","t":1792064274527989,"type":"v2/user_trades","u":48589616}"#;

    #[test]
    fn parses_the_real_fill_frame() {
        let v: Value = serde_json::from_str(REAL_FILL).unwrap();
        assert_eq!(classify_private_frame(&v), PrivateFrame::Fill);
        let t = parse_user_trade(&v).unwrap();
        assert_eq!(
            t,
            UserTrade {
                bought: true,
                contracts: 1,
                price: 81140.5,
                fill_id: "7257cf23e12c439e96894ef3ed6bfcd3".into(),
                order_id: Some(2175436569),
                client_order_id: Some("probe-1792064272244".into()),
                maker: true,
                venue_ts_us: Some(1792064274527989),
            }
        );
    }

    #[test]
    fn fill_fields_are_read_leniently_and_the_product_id_is_never_the_fill_id() {
        let v: Value = serde_json::from_str(REAL_FILL).unwrap();
        // Numbers instead of strings, a taker sell, no fill id: the id falls back to order id + venue time.
        let mut w = v.clone();
        w["s"] = json!(3);
        w["p"] = json!(81140.5);
        w["S"] = json!("sell");
        w["r"] = json!("taker");
        w.as_object_mut().unwrap().remove("f");
        let t = parse_user_trade(&w).unwrap();
        assert_eq!((t.bought, t.contracts, t.price, t.maker), (false, 3, 81140.5, false));
        assert_eq!(t.fill_id, "2175436569-1792064274527989");
        assert_ne!(t.fill_id, "84");
        // Unreadable size, price or side: no fill rather than a zero-size one.
        for (k, bad) in [("s", json!("x")), ("s", json!("0")), ("p", json!(null)), ("S", json!("short"))] {
            let mut b = v.clone();
            b[k] = bad;
            assert!(parse_user_trade(&b).is_none(), "{k}");
        }
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

    enum Reply {
        Text(Value),
        Close(CloseCode, &'static str),
    }

    /// A one-path websocket venue. `script(conn_no, frame)` returns the replies for each frame we send.
    async fn venue<S>(script: S) -> (String, Arc<Mutex<Vec<Vec<Value>>>>)
    where
        S: Fn(usize, &Value) -> Vec<Reply> + Send + Sync + 'static,
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
                            let msg = match reply {
                                Reply::Text(v) => Message::Text(v.to_string()),
                                Reply::Close(code, reason) => Message::Close(Some(CloseFrame { code, reason: reason.into() })),
                            };
                            if ws.send(msg).await.is_err() {
                                return;
                            }
                        }
                    }
                });
            }
        });
        (url, seen)
    }

    fn txt(v: Value) -> Vec<Reply> {
        vec![Reply::Text(v)]
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
            Some("key-auth") => txt(json!({"type": "key-auth", "success": true})),
            Some("subscribe") => vec![
                Reply::Text(json!({"type": "subscriptions", "channels": [{"name": "v2/user_trades", "symbols": ["ADAUSD"]}]})),
                Reply::Text(json!({"type": "v2/user_trades", "sy": "ADAUSD", "S": "buy", "s": 200, "p": "0.2398"})),
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
        assert_eq!((s.last_error, s.refusals), (None, 0));
        assert_eq!(*got.lock().unwrap(), vec!["ADAUSD".to_string()]);
        let frames = seen.lock().unwrap()[0].clone();
        assert_eq!(frames[0]["type"], "key-auth");
        assert_eq!(frames[1]["type"], "subscribe");
        assert_eq!(frames[1]["payload"]["channels"][0]["name"], "v2/user_trades");
    }

    #[tokio::test]
    async fn an_unfamiliar_login_reply_still_subscribes_at_once() {
        // A reply shape we have not seen: no wait for auth_wait, and the subscription ack decides.
        let (url, _) = venue(|_, v| match v["type"].as_str() {
            Some("key-auth") => txt(json!({"type": "auth", "message": "Authenticated"})),
            Some("subscribe") => txt(json!({"type": "subscriptions", "channels": [{"name": "v2/user_trades"}]})),
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        let started = std::time::Instant::now();
        tokio::spawn(async move { feed().run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, |_, _| {}).await });
        wait_until(&mut rx, |s| s.subscribed).await;
        assert!(started.elapsed() < Duration::from_millis(250), "no auth_wait spent: {:?}", started.elapsed());
    }

    #[tokio::test]
    async fn a_refused_subscription_is_reported_counted_and_retried() {
        let (url, seen) = venue(|_, v| match v["type"].as_str() {
            Some("key-auth") => txt(json!({"type": "key-auth", "success": true})),
            Some("subscribe") => txt(json!({"type": "subscriptions", "channels": [{"error": "subscription forbidden on this channel. Unauthorized user", "name": "v2/user_trades"}]})),
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        tokio::spawn(async move { feed().run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, |_, _| {}).await });
        let s = wait_until(&mut rx, |s| s.refusals >= 2).await;
        assert!(!s.subscribed);
        assert!(s.last_error.as_deref().unwrap_or("").contains("Unauthorized user"), "{:?}", s.last_error);
        assert!(seen.lock().unwrap().len() >= 2, "the feed reconnects after a refusal");
    }

    #[tokio::test]
    async fn a_refused_login_stops_before_subscribing() {
        let (url, seen) = venue(|_, v| match v["type"].as_str() {
            Some("key-auth") => txt(json!({"type": "key-auth", "success": false, "error": {"code": "InvalidApiKey"}})),
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        tokio::spawn(async move { feed().run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, |_, _| {}).await });
        let s = wait_until(&mut rx, |s| s.refusals >= 1).await;
        assert!(s.last_error.unwrap().contains("InvalidApiKey"));
        assert!(seen.lock().unwrap().iter().flatten().all(|f| f["type"] != "subscribe"));
    }

    #[tokio::test]
    async fn a_close_during_login_keeps_the_venues_reason_and_backs_off() {
        let (url, _) = venue(|_, v| match v["type"].as_str() {
            Some("key-auth") => vec![Reply::Close(CloseCode::Policy, "Unauthorized: bad signature")],
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        tokio::spawn(async move { feed().run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, |_, _| {}).await });
        let s = wait_until(&mut rx, |s| s.refusals >= 2).await;
        assert!(s.last_error.as_deref().unwrap_or("").contains("bad signature"), "{:?}", s.last_error);
    }

    #[tokio::test]
    async fn a_venue_error_during_login_is_named_when_the_subscription_is_refused() {
        let (url, _) = venue(|_, v| match v["type"].as_str() {
            Some("key-auth") => txt(json!({"type": "error", "message": "key-auth is deprecated, use auth"})),
            Some("subscribe") => txt(json!({"type": "subscriptions", "channels": [{"error": "Unauthorized user", "name": "v2/user_trades"}]})),
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        tokio::spawn(async move { feed().run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, |_, _| {}).await });
        let s = wait_until(&mut rx, |s| s.refusals >= 1).await;
        let e = s.last_error.unwrap();
        assert!(e.contains("Unauthorized user") && e.contains("deprecated"), "{e}");
    }

    #[tokio::test]
    async fn a_reply_echoing_our_credentials_is_redacted() {
        // A hostile or verbose venue echoing the key: neither the state nor the error carries it.
        let (url, _) = venue(|_, v| match v["type"].as_str() {
            Some("key-auth") => txt(json!({"type": "key-auth", "success": false, "error": format!("bad key {}", v["payload"]["api-key"].as_str().unwrap())})),
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        tokio::spawn(async move { feed().run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, |_, _| {}).await });
        let s = wait_until(&mut rx, |s| s.refusals >= 1).await;
        let e = s.last_error.unwrap();
        assert!(!e.contains("test-key-123") && e.contains("<redacted>"), "{e}");
    }

    #[tokio::test]
    async fn a_dropped_connection_reconnects_instead_of_ending_the_task() {
        // The first connection never answers the subscription, so the client gives up after `silence`;
        // the second one works.
        let (url, _) = venue(|conn, v| match (conn, v["type"].as_str()) {
            (_, Some("key-auth")) => txt(json!({"type": "key-auth", "success": true})),
            (0, Some("subscribe")) => vec![],
            (_, Some("subscribe")) => txt(json!({"type": "subscriptions", "channels": [{"name": "v2/user_trades"}]})),
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
            Some("subscribe") => txt(json!({"type": "subscriptions", "channels": [{"name": "v2/user_trades"}]})),
            _ => vec![],
        })
        .await;
        let (tx, mut rx) = watch::channel(PrivateFeedState::default());
        tokio::spawn(async move { feed().run_user_trades_at(&url, &["ADAUSDT".into()], fast(), tx, |_, _| {}).await });
        wait_until(&mut rx, |s| s.subscribed).await;
        assert_eq!(seen.lock().unwrap()[0][1]["type"], "subscribe");
    }
}
