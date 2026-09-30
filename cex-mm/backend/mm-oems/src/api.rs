//! Axum HTTP API for mm-oems.

use std::convert::Infallible;
use std::path::PathBuf;
use std::sync::Arc;

use axum::extract::{Path, Query, State};
use axum::http::{HeaderMap, HeaderValue, Method, StatusCode};
use axum::response::sse::{Event, KeepAlive, Sse};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use futures_util::stream::Stream;
use serde::Deserialize;
use serde_json::{json, Value};
use tokio::sync::broadcast;
use tower_http::cors::CorsLayer;
use tower_http::trace::TraceLayer;

use crate::analytics::{choose_bucket, validate_analytics_range};
use crate::config_guard::find_forbidden_secret_key;
use crate::db::{self, Db};
use crate::delta::DeltaClient;
use crate::market::Market;
use crate::snapshot::{apply_fill_to_bot_qty, BotQtyMap, SnapshotEventTx};
use crate::supervisor::{effective_env, load_env_file, StartRequest, Supervisor, SupervisorError};
use crate::sync::SharedVenue;
use crate::telemetry::Telemetry;

#[derive(Clone)]
pub struct AppState {
    pub db: Option<Db>,
    pub supervisor: Arc<Supervisor>,
    pub cex_mm_root: PathBuf,
    pub quote_bot_env: PathBuf,
    pub bot_qty: BotQtyMap,
    pub db_ok: bool,
    pub snapshot_tx: SnapshotEventTx,
    pub market: Market,
    pub venue: SharedVenue,
    pub telemetry: Telemetry,
    /// `demo` or `mainnet` — which Delta environment the OEMS and bot talk to.
    pub venue_env: &'static str,
}

/// Header the web client sends on every control request. A cross-site page cannot
/// add a custom header without a CORS preflight, which only our origin passes.
pub const CLIENT_HEADER: &str = "x-oems-client";

fn require_client(headers: &HeaderMap) -> Result<(), Response> {
    if headers.contains_key(CLIENT_HEADER) {
        Ok(())
    } else {
        Err(err_json(
            StatusCode::FORBIDDEN,
            "missing_client_header",
            format!("control requests must send the {CLIENT_HEADER} header"),
        ))
    }
}

fn cors_origins() -> Vec<HeaderValue> {
    std::env::var("OEMS_CORS_ORIGINS")
        .unwrap_or_else(|_| "http://127.0.0.1:5179,http://localhost:5179".into())
        .split(',')
        .filter_map(|o| o.trim().parse::<HeaderValue>().ok())
        .collect()
}

#[derive(Deserialize)]
pub struct StrategyQuery {
    pub strategy_id: Option<String>,
    pub limit: Option<i64>,
    pub from: Option<String>,
    pub to: Option<String>,
}

fn sid(q: &StrategyQuery) -> String {
    q.strategy_id.clone().unwrap_or_else(|| "mm".into())
}

pub fn router(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/api/strategies", get(list_strategies))
        .route("/api/strategies/{id}", get(get_strategy))
        .route("/api/strategies/{id}/config", get(get_config).post(post_config))
        .route("/api/strategies/{id}/start", post(start_strategy))
        .route("/api/strategies/{id}/stop", post(stop_strategy))
        .route("/api/events/orders", post(event_order))
        .route("/api/events/fills", post(event_fill))
        .route("/api/snapshots/latest", get(snapshots_latest))
        .route("/api/stream/snapshots", get(stream_snapshots))
        .route("/api/pnl", get(get_pnl))
        .route("/api/positions", get(get_positions))
        .route("/api/orders", get(get_orders))
        .route("/api/fills", get(get_fills))
        .route("/api/reconcile", get(get_reconcile))
        .route("/api/tca", get(get_tca))
        .route("/api/analytics", get(get_analytics))
        .route("/api/overview", get(get_overview))
        .route("/api/performance", get(get_performance))
        .route("/api/strategies/{id}/effective-config", get(get_effective_config))
        .route("/api/strategies/{id}/cancel-all", post(post_cancel_all))
        .route("/api/positions/{symbol}/close", post(post_close_position))
        .route("/api/venue/orders", get(get_venue_orders))
        .route("/api/venue/status", get(get_venue_status))
        .route("/api/bot/telemetry", get(get_bot_telemetry))
        .route("/api/ticks", get(get_ticks))
        .route("/api/market/{symbol}/ticker", get(market_ticker))
        .route("/api/market/{symbol}/book", get(market_book))
        .route("/api/market/{symbol}/trades", get(market_trades))
        .route("/api/market/{symbol}/candles", get(market_candles))
        .layer(
            CorsLayer::new()
                .allow_origin(cors_origins())
                .allow_methods([Method::GET, Method::POST, Method::OPTIONS])
                .allow_headers([
                    axum::http::header::CONTENT_TYPE,
                    axum::http::HeaderName::from_static(CLIENT_HEADER),
                ]),
        )
        .layer(TraceLayer::new_for_http())
        .with_state(state)
}

async fn health(State(st): State<AppState>) -> impl IntoResponse {
    Json(json!({
        "ok": true,
        "db": st.db_ok,
    }))
}

fn err_json(code: StatusCode, err_code: &str, message: impl Into<String>) -> Response {
    (
        code,
        Json(json!({
            "code": err_code,
            "message": message.into(),
        })),
    )
        .into_response()
}

fn db_required(st: &AppState) -> Result<&Db, Response> {
    st.db
        .as_ref()
        .ok_or_else(|| err_json(StatusCode::SERVICE_UNAVAILABLE, "db_unavailable", "database unavailable"))
}

/// If the saved process is gone, persist stopped so the badge matches the OS.
async fn reconcile_liveness(pool: &sqlx::PgPool, row: &mut Value) {
    let desired = row
        .get("desired_state")
        .and_then(|v| v.as_str())
        .unwrap_or("stopped");
    let pid = row.get("last_pid").and_then(|v| v.as_i64());
    let alive = match pid {
        Some(pid) if (1..=u32::MAX as i64).contains(&pid) => {
            crate::supervisor::pid_alive(pid as u32)
        }
        _ => false,
    };
    let shown = crate::supervisor::status_for_display(desired, alive);
    if shown == desired {
        return;
    }
    let Some(id) = row.get("id").and_then(|v| v.as_str()).map(|s| s.to_string()) else {
        return;
    };
    let _ = db::set_desired_state_and_pid(pool, &id, shown, None).await;
    if let Some(obj) = row.as_object_mut() {
        obj.insert("desired_state".into(), json!(shown));
        obj.insert("last_pid".into(), Value::Null);
    }
}

async fn list_strategies(State(st): State<AppState>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::list_strategies(&db.pool).await {
        Ok(mut rows) => {
            for row in rows.iter_mut() {
                reconcile_liveness(&db.pool, row).await;
            }
            Json(rows).into_response()
        }
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn get_strategy(State(st): State<AppState>, Path(id): Path<String>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::get_strategy(&db.pool, &id).await {
        Ok(Some(mut row)) => {
            reconcile_liveness(&db.pool, &mut row).await;
            Json(row).into_response()
        }
        Ok(None) => err_json(StatusCode::NOT_FOUND, "not_found", format!("strategy {id}")),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn get_config(State(st): State<AppState>, Path(id): Path<String>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::latest_config(&db.pool, &id).await {
        Ok(Some(row)) => Json(row).into_response(),
        Ok(None) => Json(json!({"strategy_id": id, "body": null, "version": null})).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn post_config(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
    Json(body): Json<Value>,
) -> Response {
    if let Err(r) = require_client(&headers) {
        return r;
    }
    if let Some(key) = find_forbidden_secret_key(&body) {
        return err_json(
            StatusCode::BAD_REQUEST,
            "secret_rejected",
            format!("config must not contain secret field '{key}'"),
        );
    }
    if !body.is_object() {
        return err_json(StatusCode::BAD_REQUEST, "invalid_config", "config body must be a JSON object");
    }
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    if db::get_strategy(&db.pool, &id).await.ok().flatten().is_none() {
        return err_json(StatusCode::NOT_FOUND, "not_found", format!("strategy {id}"));
    }
    match db::insert_config(&db.pool, &id, &body).await {
        Ok(row) => {
            // Running: insert version, stop (wait for exit), cancel, then start. No hot reload.
            let running = db::get_strategy(&db.pool, &id)
                .await
                .ok()
                .flatten()
                .and_then(|s| s.get("desired_state").and_then(|v| v.as_str()).map(|s| s == "running"))
                .unwrap_or(false);
            let mut restarted = None;
            if running {
                stop_blocking(&st, &id).await;
                let _ = db::set_desired_state_and_pid(&db.pool, &id, "stopped", None).await;
                let _ = cancel_delta_orders(&st, &id).await;
                match st.supervisor.start(StartRequest {
                    strategy_id: id.clone(),
                    cex_mm_root: st.cex_mm_root.clone(),
                    quote_bot_env: st.quote_bot_env.clone(),
                    config_body: Some(body),
                }) {
                    Ok(pid) => {
                        let _ =
                            db::set_desired_state_and_pid(&db.pool, &id, "running", Some(pid as i64))
                                .await;
                        restarted = Some(json!({"ok": true, "pid": pid}));
                    }
                    Err(e) => {
                        tracing::warn!(error = %e, "config apply restart failed");
                        restarted = Some(json!({"ok": false, "error": e.to_string()}));
                    }
                }
            }
            let mut out = row;
            out["restarted"] = restarted.unwrap_or(Value::Null);
            (StatusCode::CREATED, Json(out)).into_response()
        }
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

/// SIGTERM + wait for exit runs blocking sleeps; keep it off the async executor.
async fn stop_blocking(st: &AppState, id: &str) -> bool {
    let sup = st.supervisor.clone();
    let id = id.to_string();
    tokio::task::spawn_blocking(move || sup.stop_owned(&id).unwrap_or(false))
        .await
        .unwrap_or(false)
}

async fn start_strategy(State(st): State<AppState>, headers: HeaderMap, Path(id): Path<String>) -> Response {
    if let Err(r) = require_client(&headers) {
        return r;
    }
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    if db::get_strategy(&db.pool, &id).await.ok().flatten().is_none() {
        return err_json(StatusCode::NOT_FOUND, "not_found", format!("strategy {id}"));
    }
    // Refuse if DB last_pid is still alive (even if not spawned by this process).
    if let Ok(Some(row)) = db::get_strategy(&db.pool, &id).await {
        if let Some(pid) = row.get("last_pid").and_then(|v| v.as_i64()) {
            if pid > 0 && crate::supervisor::pid_alive(pid as u32) {
                return err_json(
                    StatusCode::CONFLICT,
                    "already_running",
                    format!("strategy {id} already has a live process (pid {pid})"),
                );
            }
        }
    }
    let config_body = db::latest_config(&db.pool, &id)
        .await
        .ok()
        .flatten()
        .and_then(|c| c.get("body").cloned());

    match st.supervisor.start(StartRequest {
        strategy_id: id.clone(),
        cex_mm_root: st.cex_mm_root.clone(),
        quote_bot_env: st.quote_bot_env.clone(),
        config_body,
    }) {
        Ok(pid) => {
            let _ = db::set_desired_state_and_pid(&db.pool, &id, "running", Some(pid as i64)).await;
            Json(json!({"ok": true, "pid": pid, "strategy_id": id})).into_response()
        }
        Err(SupervisorError::MissingEnv(path)) => err_json(
            StatusCode::CONFLICT,
            "missing_env",
            format!("quote-bot/.env is missing at {path}; refuse to start"),
        ),
        Err(SupervisorError::AlreadyAlive(sid, pid)) => err_json(
            StatusCode::CONFLICT,
            "already_running",
            format!("strategy {sid} already has a live process (pid {pid})"),
        ),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "start_failed", e.to_string()),
    }
}

async fn stop_strategy(State(st): State<AppState>, headers: HeaderMap, Path(id): Path<String>) -> Response {
    if let Err(r) = require_client(&headers) {
        return r;
    }
    let signaled = stop_blocking(&st, &id).await;
    if let Some(db) = &st.db {
        let _ = db::set_desired_state_and_pid(&db.pool, &id, "stopped", None).await;
    }

    // Cancel Delta orders for strategy symbols after the process has exited; leave positions.
    let cancel_result = cancel_delta_orders(&st, &id).await;

    Json(json!({
        "ok": true,
        "signaled": signaled,
        "strategy_id": id,
        "cancel": cancel_result,
    }))
    .into_response()
}

/// Symbols the strategy trades: effective `MM_SYMBOLS` (env file + config overrides).
async fn strategy_symbols(st: &AppState, strategy_id: &str) -> Vec<String> {
    let body = match &st.db {
        Some(db) => db::latest_config(&db.pool, strategy_id)
            .await
            .ok()
            .flatten()
            .and_then(|c| c.get("body").cloned()),
        None => None,
    };
    let eff = effective_env(&load_env_file(&st.quote_bot_env), body.as_ref());
    let syms: Vec<String> = eff
        .get("MM_SYMBOLS")
        .map(|(v, _)| v.split(',').map(|s| s.trim().to_uppercase()).filter(|s| !s.is_empty()).collect())
        .unwrap_or_default();
    if syms.is_empty() {
        vec!["BTCUSDT".into(), "ETHUSDT".into(), "SOLUSDT".into()]
    } else {
        syms
    }
}

async fn cancel_delta_orders(st: &AppState, strategy_id: &str) -> Value {
    if !st.quote_bot_env.is_file() {
        return json!({"skipped": "no quote-bot/.env"});
    }
    let pairs = load_env_file(&st.quote_bot_env);
    let Some(client) = DeltaClient::from_env_pairs(&pairs) else {
        return json!({"skipped": "no DELTA_API_KEY"});
    };
    let mut results = Vec::new();
    for sym in strategy_symbols(st, strategy_id).await {
        match st.market.product(&sym).await {
            Ok(p) => match client.cancel_all_product(p.product_id).await {
                Ok(()) => results.push(json!({"symbol": sym, "ok": true})),
                Err(e) => results.push(json!({"symbol": sym, "ok": false, "error": e.to_string()})),
            },
            Err(e) => results.push(json!({"symbol": sym, "ok": false, "error": e.to_string()})),
        }
    }
    json!(results)
}

async fn post_cancel_all(State(st): State<AppState>, headers: HeaderMap, Path(id): Path<String>) -> Response {
    if let Err(r) = require_client(&headers) {
        return r;
    }
    let result = cancel_delta_orders(&st, &id).await;
    Json(json!({"ok": true, "strategy_id": id, "cancel": result})).into_response()
}

#[derive(Deserialize)]
struct CloseBody {
    confirm: String,
    strategy_id: Option<String>,
}

/// Close a venue position with a reduce-only market order. Refused while the bot is
/// running (it would immediately re-quote against the close) and unless the body
/// repeats the symbol as confirmation.
async fn post_close_position(
    State(st): State<AppState>,
    headers: HeaderMap,
    Path(symbol): Path<String>,
    Json(body): Json<CloseBody>,
) -> Response {
    if let Err(r) = require_client(&headers) {
        return r;
    }
    let symbol = symbol.to_uppercase();
    if body.confirm.trim().to_uppercase() != symbol {
        return err_json(StatusCode::BAD_REQUEST, "confirm_mismatch", format!("type {symbol} to confirm"));
    }
    let sid = body.strategy_id.unwrap_or_else(|| "mm".into());
    if let Some(pid) = st.supervisor.recorded_pid(&sid) {
        if crate::supervisor::pid_alive(pid) {
            return err_json(StatusCode::CONFLICT, "bot_running", "stop the strategy before closing a position");
        }
    }
    let pairs = load_env_file(&st.quote_bot_env);
    let Some(client) = DeltaClient::from_env_pairs(&pairs) else {
        return err_json(StatusCode::CONFLICT, "no_keys", "no Delta API key configured");
    };
    let product = match st.market.product(&symbol).await {
        Ok(p) => p,
        Err(e) => return err_json(StatusCode::BAD_REQUEST, "unknown_symbol", e.to_string()),
    };
    let positions = match client.positions_margined().await {
        Ok(v) => crate::delta::parse_positions(&v),
        Err(e) => return err_json(StatusCode::BAD_GATEWAY, "venue_error", e.to_string()),
    };
    let Some(pos) = positions.iter().find(|p| p.symbol == symbol && p.venue_qty != 0.0) else {
        return err_json(StatusCode::CONFLICT, "flat", format!("no open {symbol} position"));
    };
    let contracts = (pos.venue_qty.abs() / product.contract_value.max(1e-12)).round() as i64;
    let side = if pos.venue_qty > 0.0 { "sell" } else { "buy" };
    match client.place_reduce_only_market(product.product_id, side, contracts).await {
        Ok(v) if v.get("success").and_then(|s| s.as_bool()) == Some(true) => Json(json!({
            "ok": true, "symbol": symbol, "side": side, "contracts": contracts,
            "order_id": v.get("result").and_then(|r| r.get("id")).cloned(),
        }))
        .into_response(),
        Ok(v) => err_json(
            StatusCode::BAD_GATEWAY,
            "venue_rejected",
            v.get("error").map(|e| e.to_string()).unwrap_or_else(|| "rejected".into()),
        ),
        Err(e) => err_json(StatusCode::BAD_GATEWAY, "venue_error", e.to_string()),
    }
}

#[derive(Deserialize)]
struct OrderEvent {
    strategy_id: String,
    client_order_id: String,
    symbol: String,
    side: String,
    price: f64,
    qty: f64,
    reduce_only: Option<bool>,
    reject_code: Option<String>,
}

async fn event_order(State(st): State<AppState>, Json(ev): Json<OrderEvent>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    let status = if ev.reject_code.is_some() {
        "rejected"
    } else {
        "open"
    };
    match db::upsert_order(
        &db.pool,
        &ev.strategy_id,
        &ev.client_order_id,
        &ev.symbol,
        &ev.side,
        ev.price,
        ev.qty,
        ev.reduce_only.unwrap_or(false),
        ev.reject_code.as_deref(),
        status,
    )
    .await
    {
        Ok(()) => Json(json!({"ok": true})).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

#[derive(Deserialize)]
struct FillEvent {
    strategy_id: String,
    trade_id: String,
    client_order_id: Option<String>,
    symbol: String,
    side: String,
    price: f64,
    qty: f64,
    fee: f64,
    limit_price: f64,
    arrival_mid: f64,
    mid_at_fill: f64,
}

async fn event_fill(State(st): State<AppState>, Json(ev): Json<FillEvent>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::insert_fill_and_tca(
        &db.pool,
        &ev.strategy_id,
        &ev.trade_id,
        ev.client_order_id.as_deref(),
        &ev.symbol,
        &ev.side,
        ev.price,
        ev.qty,
        ev.fee,
        ev.limit_price,
        ev.arrival_mid,
        ev.mid_at_fill,
    )
    .await
    {
        Ok(()) => {
            apply_fill_to_bot_qty(&st.bot_qty, &ev.strategy_id, &ev.symbol, &ev.side, ev.qty).await;
            Json(json!({"ok": true})).into_response()
        }
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn snapshots_latest(State(st): State<AppState>, Query(q): Query<StrategyQuery>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::latest_snapshots(&db.pool, &sid(&q)).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn stream_snapshots(
    State(st): State<AppState>,
    Query(q): Query<StrategyQuery>,
) -> Sse<impl Stream<Item = Result<Event, Infallible>>> {
    let strategy_id = sid(&q);
    let rx = st.snapshot_tx.subscribe();
    let stream = futures_util::stream::unfold(rx, move |mut rx| {
        let strategy_id = strategy_id.clone();
        async move {
            loop {
                match rx.recv().await {
                    Ok(value) => {
                        let event_sid = value
                            .get("strategy_id")
                            .and_then(|v| v.as_str())
                            .unwrap_or("");
                        if event_sid != strategy_id {
                            continue;
                        }
                        let data = match serde_json::to_string(&value) {
                            Ok(s) => s,
                            Err(_) => continue,
                        };
                        return Some((Ok(Event::default().data(data)), rx));
                    }
                    Err(broadcast::error::RecvError::Lagged(_)) => continue,
                    Err(broadcast::error::RecvError::Closed) => return None,
                }
            }
        }
    });
    Sse::new(stream).keep_alive(KeepAlive::default())
}

async fn get_pnl(State(st): State<AppState>, Query(q): Query<StrategyQuery>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    if q.from.is_some() || q.to.is_some() {
        let (Some(from_s), Some(to_s)) = (q.from.as_deref(), q.to.as_deref()) else {
            return err_json(
                StatusCode::BAD_REQUEST,
                "invalid_range",
                "from and to must both be set",
            );
        };
        let from = match chrono::DateTime::parse_from_rfc3339(from_s) {
            Ok(dt) => dt.with_timezone(&chrono::Utc),
            Err(_) => {
                return err_json(StatusCode::BAD_REQUEST, "invalid_from", "from must be RFC3339");
            }
        };
        let to = match chrono::DateTime::parse_from_rfc3339(to_s) {
            Ok(dt) => dt.with_timezone(&chrono::Utc),
            Err(_) => {
                return err_json(StatusCode::BAD_REQUEST, "invalid_to", "to must be RFC3339");
            }
        };
        if from > to {
            return err_json(StatusCode::BAD_REQUEST, "invalid_range", "from is after to");
        }
        return match db::list_pnl_between(&db.pool, &sid(&q), from, to).await {
            Ok(v) => Json(v).into_response(),
            Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
        };
    }
    match db::list_pnl(&db.pool, &sid(&q), q.limit).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn get_positions(State(st): State<AppState>, Query(q): Query<StrategyQuery>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::list_positions(&db.pool, &sid(&q), q.limit).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn get_orders(State(st): State<AppState>, Query(q): Query<StrategyQuery>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::list_orders(&db.pool, &sid(&q), q.limit).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn get_fills(State(st): State<AppState>, Query(q): Query<StrategyQuery>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::list_fills(&db.pool, &sid(&q), q.limit).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn get_reconcile(State(st): State<AppState>, Query(q): Query<StrategyQuery>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::reconcile(&db.pool, &sid(&q), q.limit).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn get_tca(State(st): State<AppState>, Query(q): Query<StrategyQuery>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::list_tca(&db.pool, &sid(&q), q.limit).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

#[derive(Deserialize)]
struct AnalyticsQuery {
    strategy_id: Option<String>,
    from: Option<String>,
    to: Option<String>,
}

async fn get_analytics(State(st): State<AppState>, Query(q): Query<AnalyticsQuery>) -> Response {
    let Some(strategy_id) = q.strategy_id.as_deref().filter(|s| !s.is_empty()) else {
        return err_json(
            StatusCode::BAD_REQUEST,
            "missing_strategy_id",
            "strategy_id is required",
        );
    };
    let Some(from_s) = q.from.as_deref() else {
        return err_json(StatusCode::BAD_REQUEST, "missing_from", "from is required");
    };
    let Some(to_s) = q.to.as_deref() else {
        return err_json(StatusCode::BAD_REQUEST, "missing_to", "to is required");
    };
    let from = match chrono::DateTime::parse_from_rfc3339(from_s) {
        Ok(dt) => dt.with_timezone(&chrono::Utc),
        Err(_) => {
            return err_json(
                StatusCode::BAD_REQUEST,
                "invalid_from",
                "from must be ISO-8601 / RFC3339",
            );
        }
    };
    let to = match chrono::DateTime::parse_from_rfc3339(to_s) {
        Ok(dt) => dt.with_timezone(&chrono::Utc),
        Err(_) => {
            return err_json(
                StatusCode::BAD_REQUEST,
                "invalid_to",
                "to must be ISO-8601 / RFC3339",
            );
        }
    };
    if let Err(msg) = validate_analytics_range(from, to) {
        return err_json(StatusCode::BAD_REQUEST, "invalid_range", msg);
    }
    let bucket = choose_bucket(from, to);
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::analytics(&db.pool, strategy_id, from, to, bucket).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

// ---------------------------------------------------------------- trader views

#[derive(Deserialize)]
struct OverviewQuery {
    strategy_id: Option<String>,
    /// Local midnight as RFC3339; day PnL is measured from the first snapshot after it.
    day_start: Option<String>,
}

fn parse_ts(s: Option<&str>) -> Option<chrono::DateTime<chrono::Utc>> {
    chrono::DateTime::parse_from_rfc3339(s?).ok().map(|d| d.with_timezone(&chrono::Utc))
}

async fn get_overview(State(st): State<AppState>, Query(q): Query<OverviewQuery>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    let sid = q.strategy_id.clone().unwrap_or_else(|| "mm".into());
    let mut strategy = match db::get_strategy(&db.pool, &sid).await {
        Ok(Some(row)) => row,
        Ok(None) => return err_json(StatusCode::NOT_FOUND, "not_found", format!("strategy {sid}")),
        Err(e) => return err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    };
    reconcile_liveness(&db.pool, &mut strategy).await;
    let info = st.supervisor.info(&sid);
    let now = chrono::Utc::now();
    let alive = info.as_ref().is_some_and(|i| crate::supervisor::pid_alive(i.pid));
    strategy["pid"] = json!(info.as_ref().filter(|_| alive).map(|i| i.pid));
    strategy["started_at"] = json!(info.as_ref().filter(|_| alive).and_then(|i| i.started_at));
    strategy["uptime_s"] = json!(info
        .as_ref()
        .filter(|_| alive)
        .and_then(|i| i.started_at)
        .map(|t| (now - t).num_seconds()));
    strategy["adopted"] = json!(info.as_ref().is_some_and(|i| i.adopted));
    strategy["last_exit"] = json!(st.supervisor.last_exit(&sid).map(|e| json!({
        "pid": e.pid, "code": e.code, "at": e.at,
    })));

    let snap = db::latest_snapshots(&db.pool, &sid).await.unwrap_or(Value::Null);
    let day = match parse_ts(q.day_start.as_deref()) {
        Some(ds) => db::equity_at_or_after(&db.pool, &sid, ds).await.ok().flatten(),
        None => None,
    };
    let equity = snap.get("balance").and_then(|b| b.get("equity")).and_then(|e| e.as_f64());
    let unrealized: f64 = snap
        .get("positions")
        .and_then(|p| p.as_array())
        .map(|ps| ps.iter().filter_map(|p| p.get("unrealized").and_then(|u| u.as_f64())).sum())
        .unwrap_or(0.0);
    let venue = st.venue.read().await;
    let tel = st.telemetry.read().await;
    Json(json!({
        "strategy": strategy,
        "venue_env": st.venue_env,
        "balance": snap.get("balance"),
        "positions": snap.get("positions"),
        "unrealized": unrealized,
        "day": {
            "start_ts": day.map(|(t, _)| t),
            "start_equity": day.map(|(_, e)| e),
            "pnl": match (day, equity) { (Some((_, s)), Some(e)) => Some(e - s), _ => None },
        },
        "open_orders": venue.open_orders.len(),
        "venue": {
            "health": venue.health,
            "orders_at": venue.orders_at,
            "fills_backfilled": venue.fills_backfilled,
            "fills_ingested": venue.fills_ingested,
            "active_symbols": venue.active_symbols,
        },
        "telemetry": {
            "attached": tel.log_path.is_some(),
            "last_line_at": tel.last_line_at,
            "symbols": tel.metrics.keys().collect::<Vec<_>>(),
            "counters": tel.counters,
        },
        "server_time": now,
    }))
    .into_response()
}

async fn get_effective_config(State(st): State<AppState>, Path(id): Path<String>) -> Response {
    let (body, version) = match &st.db {
        Some(db) => match db::latest_config(&db.pool, &id).await {
            Ok(Some(row)) => (row.get("body").cloned(), row.get("version").cloned()),
            Ok(None) => (None, None),
            Err(e) => return err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
        },
        None => (None, None),
    };
    let eff = effective_env(&load_env_file(&st.quote_bot_env), body.as_ref().filter(|b| !b.is_null()));
    let values: serde_json::Map<String, Value> = eff
        .into_iter()
        .map(|(k, (v, src))| (k, json!({"value": v, "source": src})))
        .collect();
    Json(json!({
        "strategy_id": id,
        "version": version,
        "overrides": body,
        "values": values,
        "env_file": st.quote_bot_env.file_name().map(|f| f.to_string_lossy().to_string()),
    }))
    .into_response()
}

async fn get_venue_orders(State(st): State<AppState>) -> Response {
    let g = st.venue.read().await;
    Json(json!({
        "fetched_at": g.orders_at,
        "orders": g.open_orders,
    }))
    .into_response()
}

async fn get_venue_status(State(st): State<AppState>) -> Response {
    let g = st.venue.read().await;
    Json(json!({
        "venue_env": st.venue_env,
        "health": g.health,
        "orders_at": g.orders_at,
        "fills_backfilled": g.fills_backfilled,
        "fills_ingested": g.fills_ingested,
        "active_symbols": g.active_symbols,
    }))
    .into_response()
}

#[derive(Deserialize)]
struct TelemetryQuery {
    events: Option<usize>,
}

async fn get_bot_telemetry(State(st): State<AppState>, Query(q): Query<TelemetryQuery>) -> Response {
    let g = st.telemetry.read().await;
    let now = chrono::Utc::now();
    let n = q.events.unwrap_or(100).min(400);
    let metrics: serde_json::Map<String, Value> = g
        .metrics
        .iter()
        .map(|(sym, (at, v))| {
            let mut v = v.clone();
            v["age_s"] = json!((now - *at).num_milliseconds() as f64 / 1000.0);
            (sym.clone(), v)
        })
        .collect();
    Json(json!({
        "log_path": g.log_path.as_ref().and_then(|p| p.file_name()).map(|f| f.to_string_lossy().to_string()),
        "attached": g.log_path.is_some(),
        "last_line_at": g.last_line_at,
        "metrics": metrics,
        "counters": g.counters,
        "events": g.events.iter().rev().take(n).cloned().collect::<Vec<_>>(),
    }))
    .into_response()
}

#[derive(Deserialize)]
struct TicksQuery {
    symbol: String,
    from: Option<String>,
    limit: Option<i64>,
}

async fn get_ticks(State(st): State<AppState>, Query(q): Query<TicksQuery>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    let from = parse_ts(q.from.as_deref()).unwrap_or_else(|| chrono::Utc::now() - chrono::Duration::hours(1));
    match db::list_ticks(&db.pool, &q.symbol.to_uppercase(), from, q.limit.unwrap_or(2000)).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

#[derive(Deserialize)]
struct PerformanceQuery {
    strategy_id: Option<String>,
    from: Option<String>,
    to: Option<String>,
    tz_offset_min: Option<i32>,
}

async fn get_performance(State(st): State<AppState>, Query(q): Query<PerformanceQuery>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    let to = parse_ts(q.to.as_deref()).unwrap_or_else(chrono::Utc::now);
    let from = parse_ts(q.from.as_deref()).unwrap_or(to - chrono::Duration::days(7));
    if let Err(msg) = validate_analytics_range(from, to) {
        return err_json(StatusCode::BAD_REQUEST, "invalid_range", msg);
    }
    let tz = q.tz_offset_min.unwrap_or(0).clamp(-14 * 60, 14 * 60);
    match db::performance(&db.pool, &sid_or_default(q.strategy_id), from, to, tz).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

fn sid_or_default(s: Option<String>) -> String {
    s.filter(|s| !s.is_empty()).unwrap_or_else(|| "mm".into())
}

fn market_err(e: anyhow::Error) -> Response {
    err_json(StatusCode::BAD_GATEWAY, "market_unavailable", e.to_string())
}

async fn market_ticker(State(st): State<AppState>, Path(symbol): Path<String>) -> Response {
    match st.market.ticker(&symbol).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => market_err(e),
    }
}

#[derive(Deserialize)]
struct BookQuery {
    depth: Option<u32>,
}

async fn market_book(State(st): State<AppState>, Path(symbol): Path<String>, Query(q): Query<BookQuery>) -> Response {
    match st.market.book(&symbol, q.depth.unwrap_or(20)).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => market_err(e),
    }
}

async fn market_trades(State(st): State<AppState>, Path(symbol): Path<String>) -> Response {
    match st.market.trades(&symbol).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => market_err(e),
    }
}

#[derive(Deserialize)]
struct CandleQuery {
    resolution: Option<String>,
    from: Option<i64>,
    to: Option<i64>,
}

async fn market_candles(State(st): State<AppState>, Path(symbol): Path<String>, Query(q): Query<CandleQuery>) -> Response {
    let res = q.resolution.unwrap_or_else(|| "1m".into());
    let to = q.to.unwrap_or_else(|| chrono::Utc::now().timestamp());
    let from = q.from.unwrap_or(to - 6 * 3600).max(to - 30 * 86_400);
    if from >= to {
        return err_json(StatusCode::BAD_REQUEST, "invalid_range", "from must be before to");
    }
    match st.market.candles(&symbol, &res, from, to).await {
        Ok(v) => Json(v).into_response(),
        Err(e) => market_err(e),
    }
}
