//! Axum HTTP API for mm-oems.

use std::path::PathBuf;
use std::sync::Arc;

use axum::extract::{Path, Query, State};
use axum::http::{HeaderValue, Method, StatusCode};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use serde::Deserialize;
use serde_json::{json, Value};
use tower_http::cors::CorsLayer;
use tower_http::trace::TraceLayer;

use crate::config_guard::find_forbidden_secret_key;
use crate::db::{self, Db};
use crate::delta::DeltaClient;
use crate::snapshot::{apply_fill_to_bot_qty, BotQtyMap};
use crate::supervisor::{load_env_file, Supervisor, SupervisorError, StartRequest};

#[derive(Clone)]
pub struct AppState {
    pub db: Option<Db>,
    pub supervisor: Arc<Supervisor>,
    pub cex_mm_root: PathBuf,
    pub quote_bot_env: PathBuf,
    pub bot_qty: BotQtyMap,
    pub db_ok: bool,
}

#[derive(Deserialize)]
pub struct StrategyQuery {
    pub strategy_id: Option<String>,
    pub limit: Option<i64>,
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
        .route("/api/pnl", get(get_pnl))
        .route("/api/positions", get(get_positions))
        .route("/api/orders", get(get_orders))
        .route("/api/fills", get(get_fills))
        .route("/api/reconcile", get(get_reconcile))
        .route("/api/tca", get(get_tca))
        .layer(
            CorsLayer::new()
                .allow_origin(
                    "http://127.0.0.1:5179"
                        .parse::<HeaderValue>()
                        .expect("vite origin"),
                )
                .allow_methods([Method::GET, Method::POST, Method::OPTIONS])
                .allow_headers([axum::http::header::CONTENT_TYPE]),
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

async fn list_strategies(State(st): State<AppState>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::list_strategies(&db.pool).await {
        Ok(rows) => Json(rows).into_response(),
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn get_strategy(State(st): State<AppState>, Path(id): Path<String>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
    match db::get_strategy(&db.pool, &id).await {
        Ok(Some(row)) => Json(row).into_response(),
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
    Path(id): Path<String>,
    Json(body): Json<Value>,
) -> Response {
    if let Some(key) = find_forbidden_secret_key(&body) {
        return err_json(
            StatusCode::BAD_REQUEST,
            "secret_rejected",
            format!("config must not contain secret field '{key}'"),
        );
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
            // Running: insert version, stop, then start (no hot reload).
            let running = db::get_strategy(&db.pool, &id)
                .await
                .ok()
                .flatten()
                .and_then(|s| s.get("desired_state").and_then(|v| v.as_str()).map(|s| s == "running"))
                .unwrap_or(false);
            if running {
                let _ = st.supervisor.stop_owned(&id);
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
                    }
                    Err(e) => {
                        tracing::warn!(error = %e, "config apply restart failed");
                    }
                }
            }
            (StatusCode::CREATED, Json(row)).into_response()
        }
        Err(e) => err_json(StatusCode::INTERNAL_SERVER_ERROR, "db_error", e.to_string()),
    }
}

async fn start_strategy(State(st): State<AppState>, Path(id): Path<String>) -> Response {
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

async fn stop_strategy(State(st): State<AppState>, Path(id): Path<String>) -> Response {
    let signaled = match st.supervisor.stop_owned(&id) {
        Ok(v) => v,
        Err(e) => {
            return err_json(StatusCode::INTERNAL_SERVER_ERROR, "stop_failed", e.to_string())
        }
    };
    if let Some(db) = &st.db {
        let _ = db::set_desired_state_and_pid(&db.pool, &id, "stopped", None).await;
    }

    // Best-effort cancel Delta orders for strategy symbols; leave positions.
    let cancel_result = cancel_delta_orders(&st, &id).await;

    Json(json!({
        "ok": true,
        "signaled": signaled,
        "strategy_id": id,
        "cancel": cancel_result,
    }))
    .into_response()
}

async fn cancel_delta_orders(st: &AppState, strategy_id: &str) -> Value {
    if !st.quote_bot_env.is_file() {
        return json!({"skipped": "no quote-bot/.env"});
    }
    let pairs = load_env_file(&st.quote_bot_env);
    let Some(client) = DeltaClient::from_env_pairs(&pairs) else {
        return json!({"skipped": "no DELTA_API_KEY"});
    };
    let mut symbols = vec![
        "BTCUSDT".to_string(),
        "ETHUSDT".to_string(),
        "SOLUSDT".to_string(),
    ];
    if let Some(db) = &st.db {
        if let Ok(Some(cfg)) = db::latest_config(&db.pool, strategy_id).await {
            if let Some(arr) = cfg
                .get("body")
                .and_then(|b| b.get("symbols"))
                .and_then(|s| s.as_array())
            {
                let from_cfg: Vec<String> = arr
                    .iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect();
                if !from_cfg.is_empty() {
                    symbols = from_cfg;
                }
            }
        }
    }
    let mut results = Vec::new();
    for sym in symbols {
        match client.product_id_for_mm_symbol(&sym).await {
            Ok(Some(pid)) => match client.cancel_all_product(pid).await {
                Ok(()) => results.push(json!({"symbol": sym, "ok": true})),
                Err(e) => results.push(json!({"symbol": sym, "ok": false, "error": e.to_string()})),
            },
            Ok(None) => results.push(json!({"symbol": sym, "ok": false, "error": "product not found"})),
            Err(e) => results.push(json!({"symbol": sym, "ok": false, "error": e.to_string()})),
        }
    }
    json!(results)
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

async fn get_pnl(State(st): State<AppState>, Query(q): Query<StrategyQuery>) -> Response {
    let db = match db_required(&st) {
        Ok(d) => d,
        Err(r) => return r,
    };
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
