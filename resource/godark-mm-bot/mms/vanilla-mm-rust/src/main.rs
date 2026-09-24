//! Vanilla GoDark MM bot — devnet REST + HPKE (proven on devnet).
//!
//! Flow: REST connect → Pyth oracle / position mark → quote → place/cancel.

use std::sync::Arc;
use std::time::{Duration, Instant};

use godark::{
    GodarkError, GodarkRestClient, MarketDataClient, OrderAck, OrderType, PlaceOrderOptions,
    PositionRow, PositionsSnapshot, Side, TimeInForce, TransportConfig,
};
use serde_json::Value;
use tokio::signal;
use tokio::sync::RwLock;
use tracing::{error, info, warn};
use vanilla_mm_rust::{
    build_rest_client, effective_reduce_qty, env_f64, env_first, env_usize, fetch_binance_spot_price,
    fetch_external_book_top, fetch_tape_kappa, floor_qty_for_min_notional, FillEconomics, is_devnet,
    is_rate_limit_error, is_order_gone_error, is_token_expired_error, is_transient_error,
    load_instruments, message_looks_transient, min_notional_usdc, oracle_fair_for_symbol,
    over_cap_unwind_qty, rate_limit_backoff_ms, resolve_fair_price,
};
use vanilla_mm_rust::strategy::{
    BookTop, KappaEstimator, MarkoutGuard, StrategyConfig, VolTracker, compute_quote,
    horizon_vol_bps, quotes_within_tolerance, round_to_tick, signed_fill_markout_bps,
};

/// Global REST backoff after HTTP 429 (shared across place/cancel/positions).
struct RateLimitGate {
    paused_until: Option<Instant>,
}

impl RateLimitGate {
    fn new() -> Self {
        Self {
            paused_until: None,
        }
    }

    fn note_error(&mut self, err: &GodarkError) {
        if is_rate_limit_error(err) {
            let ms = rate_limit_backoff_ms(err);
            self.paused_until = Some(Instant::now() + Duration::from_millis(ms));
            warn!("rate limit 429; pausing REST for {ms}ms");
        }
    }

    fn note_ack_reject(&mut self, ack: &OrderAck) {
        if ack.success {
            return;
        }
        if ack
            .error
            .as_deref()
            .map(message_looks_transient)
            .unwrap_or(false)
        {
            let ms = rate_limit_backoff_ms(&GodarkError::Authentication(
                ack.error.clone().unwrap_or_default(),
            ));
            self.paused_until = Some(Instant::now() + Duration::from_millis(ms));
            warn!("rate limit on order ack; pausing REST for {ms}ms");
        }
    }

    async fn wait_if_needed(&self) {
        if let Some(until) = self.paused_until {
            if Instant::now() < until {
                let d = until - Instant::now();
                info!("rate limit sleep {:.1}s", d.as_secs_f64());
                tokio::time::sleep(d).await;
            }
        }
    }
}

/// Devnet tokens typically expire in ~15m (`expires_in=900`). Refresh before expiry.
async fn refresh_auth_if_due(
    client: &mut GodarkRestClient,
    last_refresh: &mut Instant,
    interval: Duration,
) {
    if last_refresh.elapsed() < interval {
        return;
    }
    match client.connect().await {
        Ok(()) => {
            info!(
                "auth token refreshed (scheduled, interval={}s)",
                interval.as_secs()
            );
            *last_refresh = Instant::now();
        }
        Err(e) => warn!("scheduled auth refresh failed: {e}"),
    }
}

/// On 1401 / expired token, re-run `auth/token` via `connect()` and retry once.
async fn refresh_auth_after_expiry(
    client: &mut GodarkRestClient,
    last_refresh: &mut Instant,
    err: GodarkError,
) -> Result<(), GodarkError> {
    if !is_token_expired_error(&err) {
        return Err(err);
    }
    warn!("auth token expired mid-loop; refreshing and retrying");
    client.connect().await?;
    *last_refresh = Instant::now();
    info!("auth token refreshed (reactive)");
    Ok(())
}

fn is_transient_cancel_error(err: &GodarkError) -> bool {
    is_transient_error(err)
}

fn is_transient_cancel_ack(ack: &OrderAck) -> bool {
    if ack.success {
        return false;
    }
    ack.error
        .as_deref()
        .map(|msg| vanilla_mm_rust::message_looks_transient(msg))
        .unwrap_or(false)
}
/// `sequencer unavailable: read frame: early eof` while the FE WS path stays healthy.
async fn cancel_with_retry(
    client: &mut GodarkRestClient,
    last_refresh: &mut Instant,
    coid: &str,
    symbol: &str,
) -> Result<(), GodarkError> {
    match cancel_with_retry_inner(client, coid, symbol).await {
        Ok(()) => Ok(()),
        Err(e) => {
            refresh_auth_after_expiry(client, last_refresh, e).await?;
            cancel_with_retry_inner(client, coid, symbol).await
        }
    }
}

async fn cancel_with_retry_inner(
    client: &mut GodarkRestClient,
    coid: &str,
    symbol: &str,
) -> Result<(), GodarkError> {
    let max_attempts = env_usize("MM_CANCEL_MAX_ATTEMPTS", 4).max(1);
    let initial_backoff_ms = env_f64("MM_CANCEL_INITIAL_BACKOFF_MS", 300.0).max(50.0);
    let max_backoff_ms = env_f64("MM_CANCEL_MAX_BACKOFF_MS", 2_000.0).max(initial_backoff_ms);
    let mut backoff_ms = initial_backoff_ms;
    let mut last_err: Option<GodarkError> = None;

    for attempt in 1..=max_attempts {
        if attempt > 1 {
            tokio::time::sleep(Duration::from_millis(backoff_ms as u64)).await;
            backoff_ms = (backoff_ms * 2.0).min(max_backoff_ms);
        }

        match client.cancel_order_by_client_id(coid, symbol).await {
            Ok(ack) if ack.success => {
                info!("cancel ok coid={coid} attempt={attempt}");
                return Ok(());
            }
            Ok(ack) => {
                let err = GodarkError::Order {
                    message: ack
                        .error
                        .clone()
                        .unwrap_or_else(|| "cancel rejected".into()),
                    error_code: ack.error_code.clone(),
                    user_message: None,
                };
                if is_transient_cancel_ack(&ack) && attempt < max_attempts {
                    warn!(
                        "cancel retry coid={coid} attempt={attempt}/{max_attempts}: {}",
                        ack.error.as_deref().unwrap_or("unknown")
                    );
                    last_err = Some(err);
                    continue;
                }
                return Err(err);
            }
            Err(e) if is_transient_cancel_error(&e) && attempt < max_attempts => {
                warn!("cancel retry coid={coid} attempt={attempt}/{max_attempts}: {e}");
                last_err = Some(e);
            }
            Err(e) => return Err(e),
        }
    }

    Err(last_err.unwrap_or_else(|| {
        GodarkError::Connection(format!(
            "cancel {coid} exhausted {max_attempts} attempts"
        ))
    }))
}

fn edge_ws_url(devnet: bool) -> String {
    env_first(&["GODARK_EDGE_URL", "GDX_EDGE_URL"]).unwrap_or_else(|| {
        if devnet {
            "wss://api.devnet.godark-dex.com".into()
        } else {
            "wss://api.godark-dex.com".into()
        }
    })
}

fn parse_level_price(level: &Value) -> Option<f64> {
    if let Some(arr) = level.as_array() {
        let first = arr.first()?;
        return first
            .as_str()
            .and_then(|s| s.parse().ok())
            .or_else(|| first.as_f64());
    }
    level
        .get("price")
        .and_then(|p| p.as_str().and_then(|s| s.parse().ok()).or_else(|| p.as_f64()))
}

fn parse_level_qty(level: &Value) -> f64 {
    if let Some(arr) = level.as_array() {
        if let Some(q) = arr.get(1) {
            return q
                .as_str()
                .and_then(|s| s.parse().ok())
                .or_else(|| q.as_f64())
                .unwrap_or(0.0);
        }
    }
    level
        .get("size")
        .or_else(|| level.get("qty"))
        .and_then(|q| q.as_str().and_then(|s| s.parse().ok()).or_else(|| q.as_f64()))
        .unwrap_or(0.0)
}

fn top_from_orderbook(val: &Value) -> Option<BookTop> {
    let typ = val.get("type").and_then(|v| v.as_str()).unwrap_or("");
    if matches!(typ, "status" | "subscribed" | "unsubscribed" | "pong" | "error") {
        return None;
    }
    let bids = val.get("bids")?.as_array()?;
    let asks = val.get("asks")?.as_array()?;
    let best_bid = bids.first().and_then(parse_level_price)?;
    let best_ask = asks.first().and_then(parse_level_price)?;
    if best_bid > 0.0 && best_ask > 0.0 && best_ask >= best_bid {
        Some(BookTop {
            best_bid,
            best_ask,
            bid_qty: bids.first().map(parse_level_qty).unwrap_or(0.0),
            ask_qty: asks.first().map(parse_level_qty).unwrap_or(0.0),
        })
    } else {
        None
    }
}

fn signed_position_size(row: &PositionRow) -> f64 {
    let size = row.size.parse::<f64>().unwrap_or(0.0);
    match row.side {
        Side::Buy => size,
        Side::Sell => -size,
    }
}

fn inventory_for_symbol(snapshot: &PositionsSnapshot, symbol_id: u64) -> f64 {
    snapshot
        .rows
        .iter()
        .filter(|r| r.symbol_id == symbol_id)
        .map(signed_position_size)
        .sum()
}

fn mark_price_for_symbol(snapshot: &PositionsSnapshot, symbol_id: u64) -> Option<f64> {
    snapshot
        .rows
        .iter()
        .find(|r| r.symbol_id == symbol_id)
        .and_then(|r| r.mark_price.as_deref())
        .and_then(|s| s.parse().ok())
}

async fn positions_with_retry(
    client: &mut GodarkRestClient,
    last_refresh: &mut Instant,
    rate_gate: &mut RateLimitGate,
) -> Result<PositionsSnapshot, GodarkError> {
    match positions_with_retry_inner(rate_gate, client).await {
        Ok(s) => Ok(s),
        Err(e) => {
            rate_gate.note_error(&e);
            refresh_auth_after_expiry(client, last_refresh, e).await?;
            positions_with_retry_inner(rate_gate, client).await
        }
    }
}

async fn positions_with_retry_inner(
    rate_gate: &mut RateLimitGate,
    client: &mut GodarkRestClient,
) -> Result<PositionsSnapshot, GodarkError> {
    let max_attempts = env_usize("MM_POSITIONS_MAX_ATTEMPTS", 3).max(1);
    let mut backoff_ms = env_f64("MM_POSITIONS_INITIAL_BACKOFF_MS", 300.0).max(50.0);
    let mut last_err: Option<GodarkError> = None;

    for attempt in 1..=max_attempts {
        if attempt > 1 {
            tokio::time::sleep(Duration::from_millis(backoff_ms as u64)).await;
            backoff_ms = (backoff_ms * 2.0).min(2_000.0);
        }
        match client.get_positions().await {
            Ok(snap) => return Ok(snap),
            Err(e) if is_transient_cancel_error(&e) && attempt < max_attempts => {
                rate_gate.note_error(&e);
                warn!("positions retry attempt={attempt}/{max_attempts}: {e}");
                last_err = Some(e);
            }
            Err(e) => {
                rate_gate.note_error(&e);
                return Err(e);
            }
        }
    }
    Err(last_err.unwrap_or_else(|| GodarkError::Connection("positions read failed".into())))
}

async fn run_market_data_feed(edge_url: String, symbol: String, book_top: Arc<RwLock<Option<BookTop>>>) {
    let transport = TransportConfig::default();
    let mut subscribe_failures: u32 = 0;
    loop {
        let mut md = MarketDataClient::with_transport(&edge_url, transport.clone());
        match md.connect().await {
            Ok(()) => {}
            Err(e) => {
                warn!("market data connect failed: {e}");
                tokio::time::sleep(Duration::from_secs(5)).await;
                continue;
            }
        }
        if let Err(e) = md.subscribe_orderbook(&symbol).await {
            subscribe_failures += 1;
            if subscribe_failures == 1 || subscribe_failures % 12 == 0 {
                warn!(
                    "market data subscribe failed (attempt {subscribe_failures}): {e}"
                );
            }
            md.disconnect().await;
            if subscribe_failures >= 36 {
                error!(
                    "market data subscribe gave up after {subscribe_failures} attempts; \
                     fair from oracle only (set GODARK_MARKET_DATA_USE_GOMARKET=1 or GODARK_MARKET_DATA_WS_URL)"
                );
                return;
            }
            tokio::time::sleep(Duration::from_secs(5)).await;
            continue;
        }
        subscribe_failures = 0;
        let Some(mut rx) = md.take_event_receiver() else {
            warn!("market data event receiver unavailable");
            md.disconnect().await;
            tokio::time::sleep(Duration::from_secs(5)).await;
            continue;
        };
        info!("market data streaming orderbook for {symbol}");
        while let Some((_key, val)) = rx.recv().await {
            if let Some(top) = top_from_orderbook(&val) {
                *book_top.write().await = Some(top);
            }
        }
        warn!("market data stream ended; reconnecting");
        md.disconnect().await;
        tokio::time::sleep(Duration::from_secs(2)).await;
    }
}

fn parse_markout_horizons_sec() -> Vec<u32> {
    env_first(&["MM_MARKOUT_HORIZONS_SEC"])
        .map(|s| {
            s.split(',')
                .filter_map(|p| p.trim().parse::<u32>().ok())
                .filter(|&h| h > 0 && h <= 120)
                .collect()
        })
        .filter(|v: &Vec<u32>| !v.is_empty())
        .unwrap_or_else(|| vec![1, 5, 30])
}

async fn fair_at_horizon(
    probe: &Arc<RwLock<Option<(f64, Instant)>>>,
    base: &str,
    book_source: &str,
    fallback: f64,
) -> f64 {
    if let Some((f, t)) = *probe.read().await {
        if f > 0.0 && t.elapsed() < Duration::from_secs(30) {
            return f;
        }
    }
    if let Some(top) = fetch_external_book_top(base, book_source).await {
        if let Some(m) = top.mid() {
            return m;
        }
    }
    fetch_binance_spot_price(base).await.unwrap_or(fallback)
}

async fn try_over_cap_unwind(
    client: &mut GodarkRestClient,
    last_refresh: &mut Instant,
    rate_gate: &mut RateLimitGate,
    symbol: &str,
    inventory: f64,
    max_inv: f64,
    fair: f64,
    tick: f64,
    min_notional: f64,
    cross_bps: f64,
    rest_pause_ms: usize,
) -> bool {
    if max_inv <= 0.0 || inventory.abs() <= max_inv {
        return false;
    }
    let excess = inventory.abs() - max_inv;
    let (side, abs_inv) = if inventory > 0.0 {
        (Side::Sell, inventory)
    } else {
        (Side::Buy, -inventory)
    };
    let cross = cross_bps / 10_000.0;
    let price = if side == Side::Sell {
        round_to_tick(fair * (1.0 - cross), tick)
    } else {
        round_to_tick(fair * (1.0 + cross), tick)
    };
    let Some(qty) = over_cap_unwind_qty(inventory, max_inv, price, min_notional) else {
        warn!(
            "over-cap unwind skipped: |inv|={:.4} excess={excess:.4} notional below min={min_notional}",
            abs_inv
        );
        return false;
    };
    tokio::time::sleep(Duration::from_millis(rest_pause_ms as u64)).await;
    let coid = format!("mm-unwind-{}", uuid::Uuid::new_v4());
    let options = PlaceOrderOptions {
        reduce_only: true,
        ..Default::default()
    };
    info!(
        "over-cap unwind {side:?} qty={qty:.6} @ {price:.2} (inv={inventory:.4} max={max_inv:.4})"
    );
    match place_order_with_auth_retry(
        client,
        last_refresh,
        rate_gate,
        symbol,
        side,
        OrderType::Limit,
        qty,
        Some(price),
        TimeInForce::Ioc,
        options,
        coid,
    )
    .await
    {
        Ok(ack) => {
            info!("unwind placed order_id={}", ack.order_id);
            true
        }
        Err(e) => {
            warn!("unwind failed: {e}");
            false
        }
    }
}

async fn cancel_all_symbol_orders(client: &mut GodarkRestClient, symbol: &str, symbol_id: u64) {
    let snapshot = match client.get_open_orders().await {
        Ok(s) => s,
        Err(e) => {
            warn!("open orders snapshot failed; skipping cleanup: {e}");
            return;
        }
    };
    let ours: Vec<_> = snapshot
        .rows
        .iter()
        .filter(|r| r.symbol_id == symbol_id)
        .collect();
    if ours.is_empty() {
        return;
    }
    info!("cancelling {} open orders for {symbol}", ours.len());
    let pause_ms = env_usize("MM_REST_PAUSE_MS", 120);
    for row in ours {
        tokio::time::sleep(Duration::from_millis(pause_ms as u64)).await;
        if let Err(e) = client.cancel_order(&row.order_id, symbol).await {
            warn!("cleanup cancel order_id={}: {e}", row.order_id);
        }
    }
}

async fn cancel_stale_open_orders(
    client: &mut GodarkRestClient,
    symbol: &str,
    symbol_id: u64,
    keep_coids: &[&str],
) {
    let Ok(snapshot) = client.get_open_orders().await else {
        warn!("open orders snapshot failed; skipping stale cleanup");
        return;
    };
    let ours: Vec<_> = snapshot
        .rows
        .iter()
        .filter(|r| r.symbol_id == symbol_id)
        .collect();
    if ours.len() <= 2 {
        return;
    }
    warn!("found {} open orders for {symbol}; cleaning extras", ours.len());
    for row in ours {
        if let Err(e) = client.cancel_order(&row.order_id, symbol).await {
            warn!("cleanup cancel order_id={}: {e}", row.order_id);
        }
    }
    let _ = keep_coids;
}

async fn place_order_with_auth_retry(
    client: &mut GodarkRestClient,
    last_refresh: &mut Instant,
    rate_gate: &mut RateLimitGate,
    symbol: &str,
    side: Side,
    order_type: OrderType,
    order_qty: f64,
    price: Option<f64>,
    tif: TimeInForce,
    options: PlaceOrderOptions,
    coid: String,
) -> Result<OrderAck, GodarkError> {
    match client
        .place_order_with_options(
            symbol,
            side,
            order_type,
            order_qty,
            price,
            tif,
            false,
            None,
            None,
            Some(coid.clone()),
            options,
        )
        .await
    {
        Ok(ack) if ack.success => Ok(ack),
        Ok(ack) => {
            rate_gate.note_ack_reject(&ack);
            Err(GodarkError::Order {
                message: ack
                    .error
                    .clone()
                    .unwrap_or_else(|| "order rejected".into()),
                error_code: ack.error_code.clone(),
                user_message: None,
            })
        }
        Err(e) => {
            rate_gate.note_error(&e);
            refresh_auth_after_expiry(client, last_refresh, e).await?;
            match client
                .place_order_with_options(
                    symbol,
                    side,
                    order_type,
                    order_qty,
                    price,
                    tif,
                    false,
                    None,
                    None,
                    Some(coid),
                    options,
                )
                .await
            {
                Ok(ack) if ack.success => Ok(ack),
                Ok(ack) => {
                    rate_gate.note_ack_reject(&ack);
                    Err(GodarkError::Order {
                        message: ack
                            .error
                            .clone()
                            .unwrap_or_else(|| "order rejected".into()),
                        error_code: ack.error_code.clone(),
                        user_message: None,
                    })
                }
                Err(e2) => {
                    rate_gate.note_error(&e2);
                    Err(e2)
                }
            }
        }
    }
}

const DEFAULT_SYMBOL: &str = "BTC-USDC-PERP";

fn hpke_pin_set() -> bool {
    env_first(&[
        "GODARK_DEVNET_HPKE_STATIC_PUBLIC_KEY",
        "GDX_HPKE_STATIC_PUBLIC_KEY",
        "GODARK_HPKE_STATIC_PUBLIC_KEY",
        "VITE_GDX_HPKE_STATIC_PUBKEY",
    ])
    .is_some()
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "vanilla_mm_rust=info,godark=warn".into()),
        )
        .init();

    let symbol = env_first(&["GODARK_DEVNET_SYMBOL", "GODARK_SYMBOL"])
        .unwrap_or_else(|| DEFAULT_SYMBOL.to_string());
    let loop_sec = env_f64("MM_LOOP_INTERVAL_SEC", 15.0);
    let order_qty = env_f64("MM_ORDER_QTY", 0.01);
    let max_inv = env_f64("MM_MAX_INVENTORY", 0.05);
    let strat_cfg = StrategyConfig::from_env_for_symbol(&symbol, env_f64);
    let fair_override = env_first(&["MM_FAIR_OVERRIDE"]).and_then(|s| s.parse().ok());
    let fair_fallback = env_f64("MM_FAIR_FALLBACK", 64_000.0);
    let devnet = is_devnet();
    let rest_pause_ms = env_usize("MM_REST_PAUSE_MS", 120);
    let vol_lookback = env_usize("MM_VOL_LOOKBACK", 96);
    let vol_horizon_sec = env_f64("MM_VOL_HORIZON_SEC", 900.0).max(60.0);
    let kappa_min_samples = env_usize("MM_KAPPA_MIN_SAMPLES", 3).max(2);
    let markout_decay = env_f64("MM_MARKOUT_DECAY", 0.85);
    let markout_widen_bps = env_f64("MM_MARKOUT_WIDEN_BPS", 4.0);
    let markout_threshold_bps = env_f64("MM_MARKOUT_THRESHOLD_BPS", 3.0);
    let markout_side_aware = env_f64("MM_MARKOUT_SIDE_AWARE", 1.0) >= 0.5;
    let venue_reconcile_tol = env_f64("MM_VENUE_RECONCILE_POSITION_TOL", 1e-4).max(0.0);
    let venue_reconcile_enabled = env_f64("MM_VENUE_RECONCILE_POSITION", 1.0) >= 0.5;
    let markout_horizons = parse_markout_horizons_sec();
    let kappa_tape_enabled = env_f64("MM_KAPPA_TAPE", 1.0) >= 0.5;
    let kappa_tape_refresh_sec = env_f64("MM_KAPPA_TAPE_REFRESH_SEC", 300.0).max(60.0);
    let kappa_tape_limit = env_usize("MM_KAPPA_TAPE_TRADES", 500).clamp(100, 1000);
    let oracle_blend = env_f64("MM_ORACLE_BLEND_WEIGHT", 0.35);
    let requote_tol_bps = env_f64("MM_REQUOTE_TOL_BPS", 3.0);
    let unwind_cross_bps = env_f64("MM_UNWIND_CROSS_BPS", 5.0);
    let min_notional = min_notional_usdc(&symbol);

    let instruments = load_instruments().await;
    let tick = instruments
        .get(&symbol)
        .and_then(|i| i.tick_size)
        .unwrap_or_else(|| env_f64("MM_TICK_SIZE", 0.01));

    let symbol_id = instruments
        .get(&symbol)
        .map(|i| i.symbol_id)
        .unwrap_or_else(|| {
        warn!("symbol {symbol} missing from instruments map; defaulting symbol_id=1");
        1
    });

    let market_data_enabled = env_first(&["MM_MARKET_DATA"])
        .map(|v| matches!(v.as_str(), "1" | "true" | "yes"))
        .unwrap_or(false);
    let book_source = env_first(&["MM_BOOK_SOURCE"])
        .unwrap_or_else(|| {
            if market_data_enabled {
                "ws".into()
            } else {
                "hyperliquid,binance".into()
            }
        })
        .to_lowercase();
    let external_book_enabled = book_source != "off" && book_source != "ws" && !market_data_enabled;

    let book_top = Arc::new(RwLock::new(None));
    if market_data_enabled {
        tokio::spawn(run_market_data_feed(
            edge_ws_url(devnet),
            symbol.clone(),
            book_top.clone(),
        ));
    } else if external_book_enabled {
        info!("market data WS disabled; external book source={book_source} (gdx-web reference venues)");
    } else {
        info!("market data disabled; fair from oracle / position mark / fallback");
    }

    let startup_wait = env_f64("MM_MARKET_DATA_STARTUP_SEC", 3.0);
    if market_data_enabled && fair_override.is_none() && startup_wait > 0.0 {
        info!("waiting {startup_wait:.1}s for first orderbook tick");
        tokio::time::sleep(Duration::from_secs_f64(startup_wait)).await;
    }

    let mut client = build_rest_client()?;
    for attempt in 1..=4 {
        match client.connect().await {
            Ok(()) => break,
            Err(e) if is_transient_error(&e) && attempt < 4 => {
                warn!("connect retry {attempt}/4: {e}");
                tokio::time::sleep(Duration::from_millis(300 * attempt as u64)).await;
            }
            Err(e) => return Err(e.into()),
        }
    }
    info!(
        "REST connected user_uuid={:?} hpke_pin={} symbol_id={symbol_id} tick={tick}",
        client.user_uuid(),
        if hpke_pin_set() { "set" } else { "MISSING" },
    );

    let mut bid_coid: Option<String> = None;
    let mut ask_coid: Option<String> = None;
    let mut last_posted: Option<(f64, f64)> = None;
    let mut last_fair: Option<f64> = None;
    let mut fair_at_last_quote: Option<f64> = None;
    let mut vol_tracker = VolTracker::new(vol_lookback);
    let mut kappa_est = KappaEstimator::new(32);
    let mut kappa_tape: Option<f64> = None;
    let mut last_kappa_tape_refresh = Instant::now()
        .checked_sub(Duration::from_secs(3600))
        .unwrap_or_else(Instant::now);
    let markout_guard = Arc::new(tokio::sync::Mutex::new(MarkoutGuard::with_rolling_capacity(
        strat_cfg.markout_rolling_window,
    )));
    let fair_probe: Arc<RwLock<Option<(f64, Instant)>>> = Arc::new(RwLock::new(None));
    let symbol_base = symbol.split('-').next().unwrap_or(&symbol).to_string();
    let mut prev_inventory: Option<f64> = None;
    let mut last_confirmed_inventory: Option<f64> = None;
    let mut loop_count: u64 = 0;
    let mut fill_events: u64 = 0;
    let mut fill_economics = FillEconomics::new(strat_cfg.maker_fee_bps);
    let economics_path = FillEconomics::economics_state_path(&symbol);
    if let Some(restored) = FillEconomics::load_state(&economics_path) {
        fill_events = restored.fill_count;
        info!(
            "restored fill economics from {} realized={:.4} fees={:.4} n={}",
            economics_path.display(),
            restored.realized_usdc,
            restored.fees_usdc,
            restored.fill_count,
        );
        fill_economics = restored;
    }
    let mut auth_fail_streak: u32 = 0;
    let mut error_streak: u32 = 0;
    let mut venue_reconciled = false;
    let mut oracle_mark: Option<f64> = oracle_fair_for_symbol(&instruments, &symbol).await;
    if let Some(m) = oracle_mark {
        info!("initial oracle fair={m:.2}");
    }
    let token_refresh_sec = env_f64("MM_TOKEN_REFRESH_SEC", 480.0).max(60.0);
    let token_refresh_interval = Duration::from_secs_f64(token_refresh_sec);
    let mut last_auth_refresh = Instant::now();
    let mut rate_gate = RateLimitGate::new();
    let loop_offset = env_f64("MM_LOOP_OFFSET_SEC", 0.0);
    if loop_offset > 0.0 {
        info!("loop offset {loop_offset:.0}s (stagger multi-symbol API calls)");
        tokio::time::sleep(Duration::from_secs_f64(loop_offset)).await;
    }
    let mut interval = tokio::time::interval(Duration::from_secs_f64(loop_sec.max(5.0)));

    cancel_all_symbol_orders(&mut client, &symbol, symbol_id).await;

    loop {
        tokio::select! {
            _ = signal::ctrl_c() => {
                info!("shutdown");
                break;
            }
            _ = interval.tick() => {}
        }
        loop_count += 1;
        rate_gate.wait_if_needed().await;
        refresh_auth_if_due(&mut client, &mut last_auth_refresh, token_refresh_interval).await;

        if loop_count % 3 == 1 {
            oracle_mark = oracle_fair_for_symbol(&instruments, &symbol).await;
        }

        let (inventory, positions_mark, unrealized_pnl) =
            match positions_with_retry(&mut client, &mut last_auth_refresh, &mut rate_gate).await {
                Ok(s) => {
                    auth_fail_streak = 0;
                    let inv = inventory_for_symbol(&s, symbol_id);
                    last_confirmed_inventory = Some(inv);
                    let upl = s
                        .rows
                        .iter()
                        .find(|r| r.symbol_id == symbol_id)
                        .and_then(|r| r.unrealized_pnl.as_deref())
                        .and_then(|v| v.parse::<f64>().ok());
                    if venue_reconcile_enabled && !venue_reconciled {
                        if fill_economics.reconcile_position_with_venue(
                            inv,
                            &symbol,
                            venue_reconcile_tol,
                        ) {
                            if let Err(e) = fill_economics.save_state(&economics_path) {
                                warn!(
                                    "failed to save economics after venue reconcile {}: {e}",
                                    economics_path.display()
                                );
                            }
                        }
                        venue_reconciled = true;
                    }
                    (inv, mark_price_for_symbol(&s, symbol_id), upl)
                }
                Err(e) => {
                    if is_token_expired_error(&e) {
                        auth_fail_streak += 1;
                        error!(
                            "positions read failed after auth refresh (streak={auth_fail_streak}): {e}"
                        );
                    } else {
                        warn!("positions read failed: {e}");
                    }
                    (
                        last_confirmed_inventory.unwrap_or(0.0),
                        None,
                        None,
                    )
                }
            };

        if max_inv > 0.0 && inventory.abs() > max_inv * 1.05 {
            warn!(
                "inventory {:.4} exceeds cap {:.4}; cancelling all resting orders",
                inventory, max_inv
            );
            cancel_all_symbol_orders(&mut client, &symbol, symbol_id).await;
            bid_coid = None;
            ask_coid = None;
        }

        let mut live_book = *book_top.read().await;
        if external_book_enabled {
            let base = symbol.split('-').next().unwrap_or(&symbol);
            if let Some(top) = fetch_external_book_top(base, &book_source).await {
                live_book = Some(top);
            }
        }
        let (fair, fair_source) = resolve_fair_price(
            fair_override,
            live_book,
            positions_mark,
            oracle_mark,
            fair_fallback,
            oracle_blend,
            strat_cfg.microprice_weight,
        );
        *fair_probe.write().await = Some((fair, Instant::now()));

        if max_inv > 0.0 && inventory.abs() > max_inv {
            cancel_all_symbol_orders(&mut client, &symbol, symbol_id).await;
            bid_coid = None;
            ask_coid = None;
            try_over_cap_unwind(
                &mut client,
                &mut last_auth_refresh,
                &mut rate_gate,
                &symbol,
                inventory,
                max_inv,
                fair,
                tick,
                min_notional,
                unwind_cross_bps,
                rest_pause_ms,
            )
            .await;
            continue;
        }

        if let Some(prev) = prev_inventory {
            if (inventory - prev).abs() > 1e-6 {
                fill_events += 1;
                let delta = inventory - prev;
                info!(
                    "fill detected inv {prev:.4} -> {inventory:.4} (delta {:.4})",
                    delta
                );
                let f0 = fair_at_last_quote.unwrap_or(fair);
                let bought = delta > 0.0;
                let probe = fair_probe.clone();
                let base = symbol_base.clone();
                let src = book_source.clone();
                let guard = markout_guard.clone();
                let horizons = markout_horizons.clone();
                let threshold = markout_threshold_bps;
                let widen = markout_widen_bps;
                let side_aware = markout_side_aware;
                let fallback_fair = fair;
                tokio::spawn(async move {
                    let mut worst_signed = 0.0_f64;
                    let mut elapsed = 0.0_f64;
                    for h in horizons {
                        let wait = h as f64 - elapsed;
                        if wait > 0.0 {
                            tokio::time::sleep(Duration::from_secs_f64(wait)).await;
                        }
                        elapsed = h as f64;
                        let fair_now =
                            fair_at_horizon(&probe, &base, &src, fallback_fair).await;
                        let signed = signed_fill_markout_bps(f0, fair_now, bought);
                        info!(
                            "MM_MARKOUT_HORIZON {}",
                            serde_json::json!({
                                "horizon_sec": h,
                                "signed_bps": signed,
                                "fair_at_fill": f0,
                                "fair_now": fair_now,
                                "bought": bought,
                            })
                        );
                        if signed < worst_signed {
                            worst_signed = signed;
                        }
                        let mut g = guard.lock().await;
                        g.observe_fill_markout(
                            signed,
                            threshold,
                            0.0,
                            Some(h),
                            bought,
                            side_aware,
                        );
                    }
                    if worst_signed < -threshold {
                        let mut g = guard.lock().await;
                        g.observe_fill_markout(
                            worst_signed,
                            threshold,
                            widen,
                            None,
                            bought,
                            side_aware,
                        );
                        info!(
                            "fill markout guard widen worst_signed={worst_signed:.2} bps side={} (fair_at_fill {f0:.2})",
                            if bought { "bid" } else { "ask" }
                        );
                    }
                });
                if let Some((pb, pa)) = last_posted {
                    let fill_px = if delta > 0.0 { pb } else { pa };
                    fill_economics.on_fill(delta, fill_px);
                    fill_events = fill_economics.fill_count;
                    if let Err(e) = fill_economics.save_state(&economics_path) {
                        warn!("failed to save fill economics {}: {e}", economics_path.display());
                    }
                    info!(
                        "fill economics realized={:.4} fees={:.4} net={:.4} (n={})",
                        fill_economics.realized_usdc,
                        fill_economics.fees_usdc,
                        fill_economics.net_realized_usdc(),
                        fill_economics.fill_count,
                    );
                    let f0 = fair_at_last_quote.unwrap_or(fair);
                    if f0 > 0.0 {
                        let dist_bps = if delta > 0.0 {
                            ((f0 - pb).abs() / f0) * 10_000.0
                        } else {
                            ((pa - f0).abs() / f0) * 10_000.0
                        };
                        if dist_bps > 0.1 {
                            kappa_est.observe(dist_bps);
                            let k = kappa_est.kappa(
                                strat_cfg.as_kappa,
                                kappa_min_samples,
                                strat_cfg.kappa_floor,
                                strat_cfg.kappa_cap,
                            );
                            let raw_note = kappa_est
                                .kappa_raw(kappa_min_samples)
                                .map(|r| format!(" raw={r:.3}"))
                                .unwrap_or_default();
                            info!(
                                "fill distance {:.1} bps → kappa={k:.2}{raw_note} (n={})",
                                dist_bps,
                                kappa_est.sample_count()
                            );
                        }
                    }
                }
                // Filled order is no longer resting — drop stale coid before cancel/requote.
                if delta > 0.0 {
                    if bid_coid.take().is_some() {
                        info!("fill cleared stale bid coid");
                    }
                } else if delta < 0.0 {
                    if ask_coid.take().is_some() {
                        info!("fill cleared stale ask coid");
                    }
                }
            }
        }
        prev_inventory = Some(inventory);

        vol_tracker.push(fair);
        let vol_sample_bps = vol_tracker.vol_bps();
        let vol_bps = horizon_vol_bps(
            vol_sample_bps,
            vol_lookback,
            loop_sec,
            vol_horizon_sec,
        );
        if kappa_tape_enabled
            && last_kappa_tape_refresh.elapsed() >= Duration::from_secs_f64(kappa_tape_refresh_sec)
        {
            if let Some(kt) =
                fetch_tape_kappa(&symbol_base, &book_source, fair, kappa_tape_limit).await
            {
                kappa_tape = Some(kt);
                info!("tape kappa={kt:.3} (source={book_source})");
            }
            last_kappa_tape_refresh = Instant::now();
        }

        let kappa_raw = kappa_est.kappa_raw(kappa_min_samples);
        let kappa_fill = kappa_est.kappa(
            strat_cfg.as_kappa,
            kappa_min_samples,
            strat_cfg.kappa_floor,
            strat_cfg.kappa_cap,
        );
        let effective_kappa = if let Some(kt) = kappa_tape {
            let w = strat_cfg.kappa_tape_blend;
            (w * kt + (1.0 - w) * kappa_fill).clamp(strat_cfg.kappa_floor, strat_cfg.kappa_cap)
        } else {
            kappa_fill
        };
        {
            let mut g = markout_guard.lock().await;
            g.on_loop_decay(markout_decay);
        }
        let (markout_extra, markout_extra_bid, markout_extra_ask, rolling_adverse, horizon_snap) = {
            let g = markout_guard.lock().await;
            let mut horizon_snap = serde_json::Map::new();
            for (h, b) in g.last_horizon_markouts() {
                horizon_snap.insert(h.to_string(), serde_json::json!(b));
            }
            (
                g.extra_spread_bps(),
                g.extra_spread_bid_bps(),
                g.extra_spread_ask_bps(),
                g.rolling_adverse_bps(),
                serde_json::Value::Object(horizon_snap),
            )
        };

        let plan = match compute_quote(
            &strat_cfg,
            fair,
            tick,
            inventory,
            max_inv,
            order_qty,
            vol_bps,
            effective_kappa,
            markout_extra_bid,
            markout_extra_ask,
            rolling_adverse,
            last_fair,
            live_book,
        ) {
            Ok(p) => p,
            Err(e) => {
                error!("quote math: {e}");
                continue;
            }
        };
        last_fair = Some(fair);

        let reservation = plan.reservation;
        let bid = plan.bid;
        let ask = plan.ask;
        let spread_bps = plan.spread_bps;
        let mut place_bid = plan.place_bid;
        let mut place_ask = plan.place_ask;
        let mut loop_order_qty = plan.order_qty;

        if inventory.abs() >= max_inv * 0.99 && max_inv > 0.0 {
            if inventory > 0.0 && place_ask {
                loop_order_qty = effective_reduce_qty(inventory, loop_order_qty, ask, min_notional)
                    .unwrap_or(0.0);
                if loop_order_qty <= 0.0 {
                    warn!("skip ask: reduce qty below min_notional={min_notional}");
                    place_ask = false;
                }
            } else if inventory < 0.0 && place_bid {
                loop_order_qty = effective_reduce_qty(inventory, loop_order_qty, bid, min_notional)
                    .unwrap_or(0.0);
                if loop_order_qty <= 0.0 {
                    warn!("skip bid: reduce qty below min_notional={min_notional}");
                    place_bid = false;
                }
            }
        } else {
            loop_order_qty = floor_qty_for_min_notional(loop_order_qty, fair, min_notional);
        }

        info!(
            "quote fair={fair:.2} ({fair_source}) inv={inventory:.4}/{max_inv:.4} res={reservation:.2} bid={bid:.2} ask={ask:.2} spread_bps={spread_bps:.1} vol={vol_sample_bps:.2}/{vol_bps:.2} kappa={effective_kappa:.2} qty={loop_order_qty:.4} sides=bid:{place_bid}/ask:{place_ask}"
        );

        let inv_ratio = if max_inv > 0.0 {
            (inventory / max_inv).clamp(-1.0, 1.0)
        } else {
            0.0
        };
        let reservation_skew_bps = if fair > 0.0 {
            (reservation / fair - 1.0) * 10_000.0
        } else {
            0.0
        };

        info!(
            "MM_METRICS {}",
            serde_json::json!({
                "symbol": symbol,
                "loop": loop_count,
                "fair": fair,
                "fair_source": fair_source,
                "inventory": inventory,
                "inv_ratio": inv_ratio,
                "reservation_skew_bps": reservation_skew_bps,
                "max_inventory": max_inv,
                "spread_bps": spread_bps,
                "vol_bps": vol_sample_bps,
                "vol_horizon_bps": vol_bps,
                "effective_kappa": effective_kappa,
                "kappa_raw": kappa_raw,
                "as_half_bps": plan.as_half_bps,
                "markout_extra_bps": markout_extra,
                "markout_extra_bid_bps": markout_extra_bid,
                "markout_extra_ask_bps": markout_extra_ask,
                "markout_side_aware": markout_side_aware,
                "rolling_adverse_bps": rolling_adverse,
                "markout_horizons_bps": horizon_snap,
                "kappa_tape": kappa_tape,
                "microprice_weight": strat_cfg.microprice_weight,
                "bid": bid,
                "ask": ask,
                "order_qty": loop_order_qty,
                "place_bid": place_bid,
                "place_ask": place_ask,
                "fair_jumped": plan.fair_jumped,
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl_usdc": fill_economics.realized_usdc,
                "fees_usdc": fill_economics.fees_usdc,
                "net_realized_pnl_usdc": fill_economics.net_realized_usdc(),
                "fill_events": fill_events,
                "at_cap": inventory.abs() >= max_inv,
                "auth_fail_streak": auth_fail_streak,
                "error_streak": error_streak,
            })
        );

        if error_streak >= 5 {
            let backoff = Duration::from_secs((error_streak as u64).min(60));
            warn!("error_streak={error_streak}; backing off {backoff:?}");
            tokio::time::sleep(backoff).await;
        }

        if !plan.fair_jumped
            && quotes_within_tolerance(last_posted, bid, ask, requote_tol_bps)
            && bid_coid.is_some()
            && ask_coid.is_some()
        {
            if error_streak > 0 {
                error_streak = error_streak.saturating_sub(1);
            }
            info!("quotes within {requote_tol_bps:.1} bps; keeping resting orders");
            continue;
        }

        if plan.fair_jumped {
            info!("fair jumped ≥{:.1} bps — forcing requote", strat_cfg.fair_jump_bps);
        }

        let mut loop_had_error = false;
        let mut bid_cancel_ok = bid_coid.is_none();
        let mut ask_cancel_ok = ask_coid.is_none();

        if let Some(coid) = bid_coid.take() {
            tokio::time::sleep(Duration::from_millis(rest_pause_ms as u64)).await;
            match cancel_with_retry(&mut client, &mut last_auth_refresh, &coid, &symbol).await {
                Ok(()) => bid_cancel_ok = true,
                Err(e) => {
                    if is_order_gone_error(&e) {
                        info!("cancel bid {coid}: order already gone");
                        bid_cancel_ok = true;
                    } else {
                        warn!("cancel bid {coid} failed after retries: {e}");
                        bid_coid = Some(coid);
                        loop_had_error = true;
                    }
                }
            }
        }
        if let Some(coid) = ask_coid.take() {
            tokio::time::sleep(Duration::from_millis(rest_pause_ms as u64)).await;
            match cancel_with_retry(&mut client, &mut last_auth_refresh, &coid, &symbol).await {
                Ok(()) => ask_cancel_ok = true,
                Err(e) => {
                    if is_order_gone_error(&e) {
                        info!("cancel ask {coid}: order already gone");
                        ask_cancel_ok = true;
                    } else {
                        warn!("cancel ask {coid} failed after retries: {e}");
                        ask_coid = Some(coid);
                        loop_had_error = true;
                    }
                }
            }
        }

        if place_bid && bid_cancel_ok {
            tokio::time::sleep(Duration::from_millis(rest_pause_ms as u64)).await;
            let new_bid_coid = format!("mm-bid-{}", uuid::Uuid::new_v4());
            match place_order_with_auth_retry(
                &mut client,
                &mut last_auth_refresh,
                &mut rate_gate,
                &symbol,
                Side::Buy,
                OrderType::Limit,
                loop_order_qty,
                Some(bid),
                TimeInForce::Gtc,
                PlaceOrderOptions {
                    reduce_only: inventory < 0.0 && inventory.abs() >= max_inv * 0.99,
                    ..Default::default()
                },
                new_bid_coid.clone(),
            )
            .await
            {
                Ok(ack) => {
                    info!("bid placed coid={new_bid_coid} order_id={}", ack.order_id);
                    bid_coid = Some(new_bid_coid);
                    auth_fail_streak = 0;
                }
                Err(e) => {
                    loop_had_error = true;
                    if is_token_expired_error(&e) {
                        auth_fail_streak += 1;
                    }
                    error!("bid place failed: {e}");
                }
            }
        } else if place_bid && !bid_cancel_ok {
            warn!("skip bid requote: prior cancel failed (avoid stacking resting orders)");
        } else if place_bid {
            info!("skip bid (sizing or inventory cap: inv={inventory:.4} max={max_inv:.4})");
        }

        if place_ask && ask_cancel_ok {
            tokio::time::sleep(Duration::from_millis(rest_pause_ms as u64)).await;
            let new_ask_coid = format!("mm-ask-{}", uuid::Uuid::new_v4());
            match place_order_with_auth_retry(
                &mut client,
                &mut last_auth_refresh,
                &mut rate_gate,
                &symbol,
                Side::Sell,
                OrderType::Limit,
                loop_order_qty,
                Some(ask),
                TimeInForce::Gtc,
                PlaceOrderOptions {
                    reduce_only: inventory > 0.0 && inventory >= max_inv * 0.99,
                    ..Default::default()
                },
                new_ask_coid.clone(),
            )
            .await
            {
                Ok(ack) => {
                    info!("ask placed coid={new_ask_coid} order_id={}", ack.order_id);
                    ask_coid = Some(new_ask_coid);
                    auth_fail_streak = 0;
                }
                Err(e) => {
                    loop_had_error = true;
                    if is_token_expired_error(&e) {
                        auth_fail_streak += 1;
                    }
                    error!("ask place failed: {e}");
                }
            }
        } else if place_ask && !ask_cancel_ok {
            warn!("skip ask requote: prior cancel failed (avoid stacking resting orders)");
        } else if place_ask {
            info!("skip ask (sizing or inventory cap: inv={inventory:.4} max={max_inv:.4})");
        }

        if loop_had_error {
            error_streak = error_streak.saturating_add(1);
        } else if bid_coid.is_some() || ask_coid.is_some() {
            error_streak = 0;
            last_posted = Some((bid, ask));
            fair_at_last_quote = Some(fair);
        }

        if loop_count % 12 == 0 {
            cancel_stale_open_orders(&mut client, &symbol, symbol_id, &[]).await;
        }
    }

    client.disconnect().await.ok();
    Ok(())
}
