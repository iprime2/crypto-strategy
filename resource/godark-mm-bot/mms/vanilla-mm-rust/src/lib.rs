//! Shared helpers for vanilla-mm-rust bot and mm-admin CLI.

pub mod strategy;

use std::collections::HashMap;
use std::env;
use std::time::Duration;

use godark::{Environment, GodarkError, GodarkRestClient};
use serde::Deserialize;
use tracing::warn;

pub fn env_first(names: &[&str]) -> Option<String> {
    names
        .iter()
        .filter_map(|n| env::var(n).ok())
        .map(|s| s.trim().to_string())
        .find(|s| !s.is_empty())
}

pub fn env_f64(name: &str, default: f64) -> f64 {
    env_first(&[name])
        .and_then(|s| s.parse().ok())
        .unwrap_or(default)
}

pub fn env_usize(name: &str, default: usize) -> usize {
    env_first(&[name])
        .and_then(|s| s.parse().ok())
        .unwrap_or(default)
}

pub fn is_devnet() -> bool {
    env_first(&["GODARK_ENV"])
        .map(|v| v.eq_ignore_ascii_case("devnet"))
        .unwrap_or(false)
}

pub fn rest_url() -> String {
    if is_devnet() {
        env_first(&["GODARK_DEVNET_REST_URL", "GDX_REST_URL"])
            .unwrap_or_else(|| "https://api.devnet.godark-dex.com".into())
    } else {
        env_first(&["GODARK_REST_URL", "GDX_REST_URL"])
            .unwrap_or_else(|| "https://api.godark-dex.com".into())
    }
}

fn hpke_pin() -> Option<String> {
    if is_devnet() {
        return env_first(&[
            "GODARK_DEVNET_HPKE_STATIC_PUBLIC_KEY",
            "GDX_HPKE_STATIC_PUBLIC_KEY",
            "GODARK_HPKE_STATIC_PUBLIC_KEY",
            "VITE_GDX_HPKE_STATIC_PUBKEY",
        ]);
    }
    env_first(&[
        "GODARK_HPKE_STATIC_PUBLIC_KEY",
        "GDX_HPKE_STATIC_PUBLIC_KEY",
        "VITE_GDX_HPKE_STATIC_PUBKEY",
    ])
}

pub fn build_rest_client() -> Result<GodarkRestClient, GodarkError> {
    let devnet = is_devnet();

    // mm-env + mm-creds export per-symbol creds as GDX_* — prefer those over shared GODARK_*.
    let (key_id, secret, passphrase) = if devnet {
        (
            env_first(&["GDX_API_KEY_ID", "GODARK_API_KEY_ID", "GODARK_DEVNET_API_KEY_ID"]),
            env_first(&["GDX_API_SECRET", "GODARK_API_SECRET", "GODARK_DEVNET_API_SECRET"]),
            env_first(&["GDX_PASSPHRASE", "GODARK_PASSPHRASE", "GODARK_DEVNET_PASSPHRASE"]),
        )
    } else {
        (
            env_first(&["GDX_API_KEY_ID", "GODARK_API_KEY_ID"]),
            env_first(&["GDX_API_SECRET", "GODARK_API_SECRET"]),
            env_first(&["GDX_PASSPHRASE", "GODARK_PASSPHRASE"]),
        )
    };

    let (key_id, secret, passphrase) = match (key_id, secret, passphrase) {
        (Some(k), Some(s), Some(p)) => (k, s, p),
        _ => {
            return Err(GodarkError::Config(
                "missing API credentials (GODARK_DEVNET_* or GODARK_*)".into(),
            ))
        }
    };

    let mut builder = GodarkRestClient::builder()
        .rest_base_url(rest_url())
        .api_key_id(key_id)
        .api_secret(secret)
        .passphrase(passphrase);

    if devnet {
        builder = builder.environment(Environment::Devnet);
    } else {
        builder = builder.environment(Environment::Testnet);
    }

    if let Some(pin) = hpke_pin() {
        builder = builder.hpke_static_public_key_hex(pin);
    }

    if let Some(uid) = env_first(&[
        "GODARK_DEVNET_USER_UUID",
        "GODARK_USER_UUID",
        "GDX_USER_UUID",
    ]) {
        builder = builder.user_uuid(uid);
    }

    builder.build()
}

pub fn message_looks_transient(msg: &str) -> bool {
    let m = msg.to_ascii_lowercase();
    m.contains("sequencer")
        || m.contains("early eof")
        || m.contains("unavailable")
        || m.contains("connection reset")
        || m.contains("broken pipe")
        || m.contains("1429")
        || m.contains("too many requests")
        || m.contains("rate limit")
}

pub fn is_token_expired_error(err: &GodarkError) -> bool {
    match err {
        GodarkError::Authentication(msg) | GodarkError::Session(msg) => {
            let m = msg.to_ascii_lowercase();
            m.contains("1401")
                || m.contains("expired token")
                || m.contains("invalid or expired")
        }
        _ => false,
    }
}

/// Cancel target already filled or removed — safe to drop local coid tracking.
pub fn is_order_gone_error(err: &GodarkError) -> bool {
    let m = godark_error_message(err).to_ascii_lowercase();
    m.contains("order_not_found")
        || m.contains("order not found")
        || m.contains("code=2003")
        || m.contains("not found in book")
}

pub fn godark_error_message(err: &GodarkError) -> String {
    match err {
        GodarkError::Authentication(msg)
        | GodarkError::Session(msg)
        | GodarkError::Connection(msg)
        | GodarkError::Timeout(msg)
        | GodarkError::Encryption(msg)
        | GodarkError::Config(msg)
        | GodarkError::Order { message: msg, .. } => msg.clone(),
        GodarkError::InvalidInput(msg) => msg.clone(),
        GodarkError::WebSocket(e) => e.to_string(),
        GodarkError::Proto(e) => e.to_string(),
    }
}

pub fn is_rate_limit_error(err: &GodarkError) -> bool {
    let m = godark_error_message(err).to_ascii_lowercase();
    m.contains("1429")
        || m.contains("too many requests")
        || m.contains("rate limit")
}

/// Backoff after HTTP 429; parses `retry_after_ms` from the error body when present.
pub fn rate_limit_backoff_ms(err: &GodarkError) -> u64 {
    let msg = godark_error_message(err);
    for pattern in ["retry_after_ms=", "retry_after_ms:", "retry after "] {
        if let Some(rest) = msg.to_ascii_lowercase().split(pattern).nth(1) {
            let digits: String = rest.chars().take_while(|c| c.is_ascii_digit()).collect();
            if let Ok(ms) = digits.parse::<u64>() {
                if ms > 0 {
                    return ms.min(120_000);
                }
            }
        }
    }
    env_f64("MM_RATE_LIMIT_BACKOFF_MS", 30_000.0).clamp(1_000.0, 120_000.0) as u64
}

/// Venue min notional (USDC) — override per symbol via `MM_MIN_NOTIONAL_BTC`, etc.
pub fn min_notional_usdc(symbol: &str) -> f64 {
    let slug = symbol.split('-').next().unwrap_or(symbol).to_uppercase();
    env_f64(
        &format!("MM_MIN_NOTIONAL_{slug}"),
        env_f64("MM_MIN_NOTIONAL", 10.0),
    )
    .max(1.0)
}

/// Notional buffer over venue minimum (env `MM_MIN_NOTIONAL_BUFFER`, default 1.08).
pub fn min_notional_buffer() -> f64 {
    env_f64("MM_MIN_NOTIONAL_BUFFER", 1.08).clamp(1.0, 1.5)
}

/// Bump qty so `qty * price` meets min notional (with buffer).
pub fn floor_qty_for_min_notional(qty: f64, price: f64, min_notional: f64) -> f64 {
    if qty <= 0.0 || price <= 0.0 || min_notional <= 0.0 {
        return qty;
    }
    let need = min_notional * min_notional_buffer();
    if qty * price >= need {
        return qty;
    }
    (need / price).max(qty)
}

/// Reduce-side clip: floor to min notional but never above absolute inventory.
pub fn effective_reduce_qty(
    inventory: f64,
    qty: f64,
    price: f64,
    min_notional: f64,
) -> Option<f64> {
    let abs_inv = inventory.abs();
    if abs_inv <= 0.0 || price <= 0.0 {
        return None;
    }
    if abs_inv * price < min_notional {
        return None;
    }
    let mut q = floor_qty_for_min_notional(qty, price, min_notional);
    q = q.min(abs_inv);
    let need = min_notional * min_notional_buffer();
    if q * price >= need {
        Some(q)
    } else if abs_inv * price >= need {
        Some(abs_inv)
    } else {
        None
    }
}

/// Qty for over-cap reduce-only unwind when excess alone is below venue min notional.
pub fn over_cap_unwind_qty(inventory: f64, max_inv: f64, price: f64, min_notional: f64) -> Option<f64> {
    if max_inv <= 0.0 || inventory.abs() <= max_inv || price <= 0.0 {
        return None;
    }
    let abs_inv = inventory.abs();
    let need = min_notional * min_notional_buffer();
    if abs_inv * price < need {
        return None;
    }
    let excess = abs_inv - max_inv;
    let clip = excess.min(abs_inv);
    let mut qty = floor_qty_for_min_notional(clip, price, min_notional);
    qty = qty.min(abs_inv);
    if qty * price < need {
        qty = floor_qty_for_min_notional(abs_inv, price, min_notional).min(abs_inv);
    }
    if qty * price >= need {
        Some(qty)
    } else {
        None
    }
}

/// Persisted fill economics (survives bot restart; venue uPnL still authoritative for open risk).
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct FillEconomicsSnapshot {
    pub position: f64,
    pub avg_cost: f64,
    pub realized_usdc: f64,
    pub fees_usdc: f64,
    pub fee_bps: f64,
    pub fill_count: u64,
}

/// Signed-position fill economics (avg-cost realized PnL + estimated maker fees).
#[derive(Debug, Clone, Default)]
pub struct FillEconomics {
    pub position: f64,
    pub avg_cost: f64,
    pub realized_usdc: f64,
    pub fees_usdc: f64,
    pub fee_bps: f64,
    pub fill_count: u64,
}

impl FillEconomics {
    pub fn new(fee_bps: f64) -> Self {
        Self {
            fee_bps: fee_bps.max(0.0),
            ..Default::default()
        }
    }

    pub fn net_realized_usdc(&self) -> f64 {
        self.realized_usdc - self.fees_usdc
    }

    pub fn snapshot(&self) -> FillEconomicsSnapshot {
        FillEconomicsSnapshot {
            position: self.position,
            avg_cost: self.avg_cost,
            realized_usdc: self.realized_usdc,
            fees_usdc: self.fees_usdc,
            fee_bps: self.fee_bps,
            fill_count: self.fill_count,
        }
    }

    pub fn from_snapshot(s: FillEconomicsSnapshot) -> Self {
        Self {
            position: s.position,
            avg_cost: s.avg_cost,
            realized_usdc: s.realized_usdc,
            fees_usdc: s.fees_usdc,
            fee_bps: s.fee_bps,
            fill_count: s.fill_count,
        }
    }

    pub fn economics_state_path(symbol: &str) -> std::path::PathBuf {
        let slug = symbol.split('-').next().unwrap_or("sym");
        let base = std::env::var("MM_ARTIFACTS_DIR").unwrap_or_else(|_| {
            let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
            format!("{home}/scripts/mms/artifacts")
        });
        std::path::PathBuf::from(base).join(format!("mm-bot-{slug}-economics.json"))
    }

    pub fn save_state(&self, path: &std::path::Path) -> std::io::Result<()> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let tmp = path.with_extension("json.tmp");
        let body = serde_json::to_string_pretty(&self.snapshot())?;
        std::fs::write(&tmp, body)?;
        std::fs::rename(tmp, path)?;
        Ok(())
    }

    pub fn load_state(path: &std::path::Path) -> Option<Self> {
        let raw = std::fs::read_to_string(path).ok()?;
        let snap: FillEconomicsSnapshot = serde_json::from_str(&raw).ok()?;
        Some(Self::from_snapshot(snap))
    }

    /// Align internal position with venue inventory after restart (realized/fees unchanged).
    pub fn reconcile_position_with_venue(
        &mut self,
        venue_inventory: f64,
        symbol: &str,
        tolerance: f64,
    ) -> bool {
        if !venue_inventory.is_finite() {
            return false;
        }
        let drift = (self.position - venue_inventory).abs();
        if drift <= tolerance.max(1e-9) {
            return false;
        }
        tracing::warn!(
            "economics position {:.6} != venue {:.6} for {symbol} (drift {drift:.6}); syncing position (realized/fees unchanged)",
            self.position,
            venue_inventory,
        );
        self.position = venue_inventory;
        if venue_inventory.abs() < 1e-12 {
            self.avg_cost = 0.0;
        }
        true
    }

    /// `delta` = inventory change (+ buy, − sell). `fill_price` = resting quote that filled.
    pub fn on_fill(&mut self, delta: f64, fill_price: f64) {
        if fill_price <= 0.0 || !delta.is_finite() || delta.abs() < 1e-12 {
            return;
        }
        self.fees_usdc += fill_price * delta.abs() * self.fee_bps / 10_000.0;
        self.fill_count += 1;

        if self.position.abs() < 1e-12 {
            self.position = delta;
            self.avg_cost = fill_price;
            return;
        }

        if delta.signum() == self.position.signum() {
            let new_pos = self.position + delta;
            let w = (self.avg_cost * self.position.abs() + fill_price * delta.abs())
                / new_pos.abs().max(1e-12);
            self.avg_cost = w;
            self.position = new_pos;
            return;
        }

        let close_qty = delta.abs().min(self.position.abs());
        if close_qty > 0.0 {
            let pnl = if self.position > 0.0 {
                (fill_price - self.avg_cost) * close_qty
            } else {
                (self.avg_cost - fill_price) * close_qty
            };
            self.realized_usdc += pnl;
        }

        let new_pos = self.position + delta;
        if new_pos.abs() < 1e-12 {
            self.position = 0.0;
            self.avg_cost = 0.0;
        } else if new_pos.signum() != self.position.signum() {
            self.position = new_pos;
            self.avg_cost = fill_price;
        } else {
            self.position = new_pos;
        }
    }
}

pub fn is_transient_error(err: &GodarkError) -> bool {
    match err {
        GodarkError::Connection(msg) | GodarkError::Timeout(msg) => message_looks_transient(msg),
        GodarkError::Authentication(msg) | GodarkError::Session(msg) => {
            message_looks_transient(msg) || is_token_expired_error(err)
        }
        GodarkError::Encryption(msg) => {
            let m = msg.to_ascii_lowercase();
            m.contains("decrypt") || m.contains("aes-gcm") || m.contains("open failed")
        }
        GodarkError::Proto(_) => true,
        _ => false,
    }
}

pub async fn with_retries<T, F, Fut>(
    label: &str,
    max_attempts: usize,
    mut f: F,
) -> Result<T, GodarkError>
where
    F: FnMut() -> Fut,
    Fut: std::future::Future<Output = Result<T, GodarkError>>,
{
    let max_attempts = max_attempts.max(1);
    let mut backoff = Duration::from_millis(300);
    let mut last_err: Option<GodarkError> = None;

    for attempt in 1..=max_attempts {
        if attempt > 1 {
            tokio::time::sleep(backoff).await;
            backoff = (backoff * 2).min(Duration::from_secs(3));
        }
        match f().await {
            Ok(v) => return Ok(v),
            Err(e) if is_transient_error(&e) && attempt < max_attempts => {
                warn!("{label} retry {attempt}/{max_attempts}: {e}");
                last_err = Some(e);
            }
            Err(e) => return Err(e),
        }
    }

    Err(last_err.unwrap_or_else(|| GodarkError::Connection(format!("{label} failed"))))
}

#[derive(Debug, Deserialize)]
struct InstrumentsEnvelope {
    data: InstrumentsData,
}

#[derive(Debug, Deserialize)]
struct InstrumentsData {
    instruments: Vec<InstrumentRow>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct InstrumentRow {
    pub symbol: String,
    pub symbol_id: u64,
    pub pyth_feed_id: Option<String>,
    pub tick_size: Option<f64>,
}

pub async fn load_instruments() -> HashMap<String, InstrumentRow> {
    let url = format!("{}/api/v1/instruments", rest_url().trim_end_matches('/'));
    let client = reqwest::Client::new();
    match client.get(&url).send().await {
        Ok(resp) if resp.status().is_success() => match resp.json::<InstrumentsEnvelope>().await {
            Ok(env) => env
                .data
                .instruments
                .into_iter()
                .map(|row| (row.symbol.clone(), row))
                .collect(),
            Err(e) => {
                warn!("instruments parse failed: {e}");
                HashMap::new()
            }
        },
        Ok(resp) => {
            warn!("instruments HTTP {}", resp.status());
            HashMap::new()
        }
        Err(e) => {
            warn!("instruments fetch failed: {e}");
            HashMap::new()
        }
    }
}

#[derive(Debug, Deserialize)]
struct PythLatest {
    parsed: Vec<PythParsed>,
}

#[derive(Debug, Deserialize)]
struct PythParsed {
    price: PythPrice,
}

#[derive(Debug, Deserialize)]
struct PythPrice {
    price: String,
    expo: i32,
}

/// Live oracle mark via Pyth Hermes (same source as gdx-web).
pub async fn fetch_pyth_oracle_price(feed_id: &str) -> Option<f64> {
    let feed = feed_id.trim();
    if feed.is_empty() {
        return None;
    }
    let url = format!(
        "https://hermes.pyth.network/v2/updates/price/latest?ids[]={feed}"
    );
    let client = reqwest::Client::builder()
        .user_agent("vanilla-mm-rust/0.1")
        .build()
        .ok()?;
    let resp = client.get(&url).send().await.ok()?;
    if !resp.status().is_success() {
        warn!("pyth hermes HTTP {}", resp.status());
        return None;
    }
    let body: PythLatest = resp.json().await.ok()?;
    let parsed = body.parsed.first()?;
    let mantissa: f64 = parsed.price.price.parse().ok()?;
    Some(mantissa * 10f64.powi(parsed.price.expo))
}

fn binance_http_client() -> Option<reqwest::Client> {
    reqwest::Client::builder()
        .user_agent("vanilla-mm-rust/0.1")
        .build()
        .ok()
}

fn parse_binance_level(level: &[String]) -> Option<(f64, f64)> {
    if level.len() < 2 {
        return None;
    }
    let price = level[0].parse().ok()?;
    let qty = level[1].parse().ok()?;
    Some((price, qty))
}

/// Hyperliquid perp BBO — same reference venue as gdx-web default orderbook.
pub async fn fetch_hyperliquid_book_top(base: &str) -> Option<strategy::BookTop> {
    let coin = base.trim().to_uppercase();
    if coin.is_empty() {
        return None;
    }
    let client = binance_http_client()?;
    let resp = client
        .post("https://api.hyperliquid.xyz/info")
        .json(&serde_json::json!({ "type": "l2Book", "coin": coin }))
        .send()
        .await
        .ok()?;
    if !resp.status().is_success() {
        warn!("hyperliquid l2Book HTTP {} for {coin}", resp.status());
        return None;
    }
    #[derive(Deserialize)]
    struct HlLevel {
        px: String,
        sz: String,
    }
    #[derive(Deserialize)]
    struct HlBook {
        levels: Vec<Vec<HlLevel>>,
    }
    let body: HlBook = resp.json().await.ok()?;
    if body.levels.len() < 2 {
        return None;
    }
    let bid = body.levels[0].first()?;
    let ask = body.levels[1].first()?;
    let best_bid: f64 = bid.px.parse().ok()?;
    let bid_qty: f64 = bid.sz.parse().ok()?;
    let best_ask: f64 = ask.px.parse().ok()?;
    let ask_qty: f64 = ask.sz.parse().ok()?;
    if best_bid > 0.0 && best_ask > 0.0 && best_ask >= best_bid {
        Some(strategy::BookTop {
            best_bid,
            best_ask,
            bid_qty,
            ask_qty,
        })
    } else {
        None
    }
}

/// Binance spot BBO — external L1 proxy when GoDark orderbook WS is unavailable.
pub async fn fetch_binance_book_top(base: &str) -> Option<strategy::BookTop> {
    let base = base.trim().to_uppercase();
    if base.is_empty() {
        return None;
    }
    let url = format!(
        "https://api.binance.com/api/v3/depth?symbol={base}USDT&limit=5"
    );
    let client = binance_http_client()?;
    let resp = client.get(&url).send().await.ok()?;
    if !resp.status().is_success() {
        warn!("binance depth HTTP {} for {base}", resp.status());
        return None;
    }
    #[derive(Deserialize)]
    struct Depth {
        bids: Vec<Vec<String>>,
        asks: Vec<Vec<String>>,
    }
    let body: Depth = resp.json().await.ok()?;
    let (best_bid, bid_qty) = body.bids.first().and_then(|l| parse_binance_level(l))?;
    let (best_ask, ask_qty) = body.asks.first().and_then(|l| parse_binance_level(l))?;
    if best_bid > 0.0 && best_ask > 0.0 && best_ask >= best_bid {
        Some(strategy::BookTop {
            best_bid,
            best_ask,
            bid_qty,
            ask_qty,
        })
    } else {
        None
    }
}

/// Fair from book mid / microprice blend, optional oracle, position mark, fallback.
pub fn resolve_fair_price(
    fair_override: Option<f64>,
    book: Option<strategy::BookTop>,
    positions_mark: Option<f64>,
    oracle_mark: Option<f64>,
    fallback: f64,
    oracle_blend: f64,
    microprice_weight: f64,
) -> (f64, &'static str) {
    if let Some(f) = fair_override {
        return (f, "override");
    }
    let book_anchor = book.and_then(|b| {
        let mid = b.mid()?;
        let w = microprice_weight.clamp(0.0, 1.0);
        if w <= 0.0 {
            return Some((mid, "orderbook_mid"));
        }
        let micro = b.microprice().unwrap_or(mid);
        let fair = (1.0 - w) * mid + w * micro;
        Some((fair, "microprice_blend"))
    });
    if let (Some((bf, _src)), Some(om)) = (book_anchor, oracle_mark) {
        let w = oracle_blend.clamp(0.0, 1.0);
        return (w * om + (1.0 - w) * bf, "blended");
    }
    if let Some((bf, src)) = book_anchor {
        return (bf, src);
    }
    if let Some(m) = positions_mark {
        return (m, "position_mark");
    }
    if let Some(m) = oracle_mark {
        return (m, "oracle");
    }
    (fallback, "fallback")
}

pub async fn fetch_hyperliquid_trade_prices(base: &str, limit: usize) -> Vec<f64> {
    let coin = base.trim().to_uppercase();
    if coin.is_empty() {
        return Vec::new();
    }
    let Some(client) = binance_http_client() else {
        return Vec::new();
    };
    let resp = match client
        .post("https://api.hyperliquid.xyz/info")
        .json(&serde_json::json!({ "type": "recentTrades", "coin": coin }))
        .send()
        .await
    {
        Ok(r) => r,
        Err(_) => return Vec::new(),
    };
    if !resp.status().is_success() {
        warn!("hyperliquid trades HTTP {} for {coin}", resp.status());
        return Vec::new();
    }
    #[derive(Deserialize)]
    struct HlTrade {
        px: String,
    }
    let body: Vec<HlTrade> = match resp.json().await {
        Ok(b) => b,
        Err(_) => return Vec::new(),
    };
    body.into_iter()
        .take(limit.max(50))
        .filter_map(|t| t.px.parse().ok())
        .collect()
}

pub async fn fetch_binance_trade_prices(base: &str, limit: usize) -> Vec<f64> {
    let base = base.trim().to_uppercase();
    if base.is_empty() {
        return Vec::new();
    }
    let Some(client) = binance_http_client() else {
        return Vec::new();
    };
    let cap = limit.clamp(50, 1000);
    let url = format!(
        "https://api.binance.com/api/v3/trades?symbol={base}USDT&limit={cap}"
    );
    let resp = match client.get(&url).send().await {
        Ok(r) => r,
        Err(_) => return Vec::new(),
    };
    if !resp.status().is_success() {
        warn!("binance trades HTTP {} for {base}", resp.status());
        return Vec::new();
    }
    #[derive(Deserialize)]
    struct BinTrade {
        price: String,
    }
    let body: Vec<BinTrade> = match resp.json().await {
        Ok(b) => b,
        Err(_) => return Vec::new(),
    };
    body.into_iter()
        .filter_map(|t| t.price.parse().ok())
        .collect()
}

/// Recent trade prints for GLFT-style κ (public venues only).
pub async fn fetch_external_trade_prices(base: &str, source: &str, limit: usize) -> Vec<f64> {
    let src = source.trim().to_lowercase();
    if src.is_empty() || src == "off" {
        return Vec::new();
    }
    for venue in src.split(',') {
        let venue = venue.trim();
        let prices = match venue {
            "hyperliquid" | "hl" => fetch_hyperliquid_trade_prices(base, limit).await,
            "binance" | "binanceusdm" => fetch_binance_trade_prices(base, limit).await,
            _ => Vec::new(),
        };
        if prices.len() >= 20 {
            return prices;
        }
    }
    Vec::new()
}

pub async fn fetch_tape_kappa(base: &str, source: &str, mid: f64, limit: usize) -> Option<f64> {
    if mid <= 0.0 {
        return None;
    }
    let prices = fetch_external_trade_prices(base, source, limit).await;
    strategy::estimate_kappa_from_trade_prices(&prices, mid)
}

/// Resolve external reference book (Hyperliquid / Binance — mirrors gdx-web venues).
pub async fn fetch_external_book_top(base: &str, source: &str) -> Option<strategy::BookTop> {
    let src = source.trim().to_lowercase();
    if src.is_empty() || src == "off" {
        return None;
    }
    for venue in src.split(',') {
        let venue = venue.trim();
        let top = match venue {
            "hyperliquid" | "hl" => fetch_hyperliquid_book_top(base).await,
            "binance" | "binanceusdm" => fetch_binance_book_top(base).await,
            _ => None,
        };
        if top.is_some() {
            return top;
        }
    }
    None
}

/// Public spot fallback when Hermes is unavailable (401, outage, etc.).
pub async fn fetch_binance_spot_price(base: &str) -> Option<f64> {
    let base = base.trim().to_uppercase();
    if base.is_empty() {
        return None;
    }
    let url = format!(
        "https://api.binance.com/api/v3/ticker/price?symbol={base}USDT"
    );
    let client = binance_http_client()?;
    let resp = client.get(&url).send().await.ok()?;
    if !resp.status().is_success() {
        warn!("binance spot HTTP {} for {base}", resp.status());
        return None;
    }
    #[derive(Deserialize)]
    struct Ticker {
        price: String,
    }
    let body: Ticker = resp.json().await.ok()?;
    body.price.parse().ok()
}

pub async fn oracle_fair_for_symbol(
    instruments: &HashMap<String, InstrumentRow>,
    symbol: &str,
) -> Option<f64> {
    let row = instruments.get(symbol)?;
    if let Some(feed) = row.pyth_feed_id.as_deref() {
        if let Some(p) = fetch_pyth_oracle_price(feed).await {
            return Some(p);
        }
    }
    let base = symbol.split('-').next().unwrap_or(symbol);
    fetch_binance_spot_price(base).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn over_cap_unwind_bumps_small_excess_to_min_notional() {
        // ETH-like: 0.0043 excess @ ~2500 with $28 min tier
        let qty = over_cap_unwind_qty(-0.5043, 0.5, 2513.0, 28.0).expect("qty");
        assert!(qty * 2513.0 >= 28.0 * min_notional_buffer());
        assert!(qty <= 0.5043);
        assert!(qty > 0.0045);
    }

    #[test]
    fn fill_economics_round_trip_long() {
        let mut ec = FillEconomics::new(0.0);
        ec.on_fill(1.0, 100.0);
        ec.on_fill(-1.0, 101.0);
        assert!((ec.realized_usdc - 1.0).abs() < 1e-6);
    }
}
