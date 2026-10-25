use anyhow::{Context, Result};
use chrono::Utc;
use clap::Args;
use mm_bybit::{
    BybitBook, BybitCredentials, BybitEnvironment, BybitPrivateWs, BybitRest,
    OrderbookMaintainer as BybitOrderbookMaintainer,
};
use mm_core::{
    BookTop,
    compute_quote_cex, economics::FillEconomics, hard_cap_reduce,
    should_taker_flatten, horizon_vol_bps, side_order_qty, requote_qty, adds_to_position,
    ofi::{AlphaMuEstimator, OfiTracker, SnipeTracker},
    regime::{RegimeEngine, RegimeLevel, RegimeThresholds},
    KappaEstimator, MarkoutGuard, QuoteExtensions, StrategyConfig, VolTracker, MmMetrics,
};
use crate::exchange::QuotingRest;
use crate::markout::MarkoutRuntime;
use crate::oms::{
    contracts_of, first_call, gone_after_cancel, left_after_edit, place_price, FillApplied, FillEvent, FirstCall, LiveQuotes,
    OmsState, QuoteSide, Settled, SETTLE_PATIENCE,
};
use crate::account::{AccountConfig, AccountFlags};
use crate::risk::{
    counts_toward_reject_kill, BookAge, BookFreeze, BookWatch, DailyLossGuard, FeedHealth, FeedWatch, FrozenBookWatch,
    VenueReading, VenueReconcile,
};
use crate::symbols::{env_f64_for_symbol, env_for_symbol, normalize_symbol, resolve_symbols_from_env};
use mm_core::fair::BasisSource;
use crate::universe::{UniverseOptions, resolve_universe};
use std::collections::{HashMap, VecDeque};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::sync::{mpsc, watch};
use tokio::task::JoinSet;

#[derive(Args, Clone)]
pub struct RunArgs {
    /// Single symbol (used when `--symbols` / `MM_SYMBOLS` is empty).
    #[arg(long, env = "MM_SYMBOL", default_value = "BTCUSDT")]
    pub symbol: String,
    /// Comma-separated list, e.g. `BTCUSDT,ETHUSDT,SOLUSDT` or `MM_SYMBOLS` in `.env`.
    #[arg(long, env = "MM_SYMBOLS", value_delimiter = ',')]
    pub symbols: Vec<String>,
    /// Load top N USDT linear perps by 24h turnover from Bybit at startup (0 = off).
    #[arg(long, env = "MM_TOP_N", default_value = "0")]
    pub top_n: usize,
    /// Exclude symbols when building top-N universe (comma-separated).
    #[arg(long, env = "MM_TOP_N_EXCLUDE", value_delimiter = ',')]
    pub exclude_symbols: Vec<String>,
    #[arg(long, default_value = "testnet")]
    pub env: String,
    /// `bybit` (default) or `delta` (India demo / mainnet).
    #[arg(long, env = "MM_VENUE", default_value = "bybit")]
    pub venue: String,
    #[arg(long, default_value = "250")]
    pub loop_ms: u64,
}

impl RunArgs {
    pub fn universe_options(&self) -> UniverseOptions {
        UniverseOptions {
            single: self.symbol.clone(),
            multi: self.symbols.clone(),
            top_n: self.top_n,
            exclude: self.exclude_symbols.clone(),
        }
    }
}

struct SymbolExecCtx {
    economics: Arc<Mutex<FillEconomics>>,
    markout: MarkoutRuntime,
    snipe: Arc<Mutex<SnipeTracker>>,
    last_jump: Arc<Mutex<Option<Instant>>>,
    /// When the fills feed last booked one of our fills: a venue position read right after it is still stale.
    last_fill_at: Arc<Mutex<Option<Instant>>>,
    economics_path: PathBuf,
    /// Our fills, by order id, to the symbol's loop so it can tell which resting quote they hit (Delta only).
    fills_tx: Option<mpsc::Sender<FillEvent>>,
}

#[derive(Clone, Copy)]
enum BookFeedKind {
    Bybit(BybitEnvironment),
    Delta(mm_delta::DeltaEnvironment),
}

fn spawn_book_feed(symbol: String, kind: BookFeedKind, book_tx: watch::Sender<BookTop>) {
    match kind {
        BookFeedKind::Bybit(env) => {
            let maint = BybitOrderbookMaintainer { env, symbol };
            let (inner_tx, mut inner_rx) = watch::channel(BybitBook::default());
            tokio::spawn(async move {
                let _ = maint.run(inner_tx).await;
            });
            tokio::spawn(async move {
                loop {
                    let top = inner_rx.borrow().top.clone();
                    if top.best_bid > 0.0 && top.best_ask > top.best_bid {
                        let _ = book_tx.send(top);
                    }
                    if inner_rx.changed().await.is_err() {
                        break;
                    }
                }
            });
        }
        BookFeedKind::Delta(env) => {
            let raw = std::env::var("MM_DELTA_BOOK_FEED").unwrap_or_default();
            let feed = mm_delta::BookFeed::from_flag(&raw).unwrap_or_else(|| {
                tracing::warn!(value = %raw, "unknown MM_DELTA_BOOK_FEED; using rest");
                mm_delta::BookFeed::Rest
            });
            tracing::info!(%symbol, ?feed, "delta book feed");
            let maint = mm_delta::OrderbookMaintainer { env, symbol, feed };
            tokio::spawn(async move {
                let _ = maint.run(book_tx).await;
            });
        }
    }
}

pub async fn run_delta(args: RunArgs, dry_run: bool) -> Result<()> {
    let delta_env = mm_delta::DeltaEnvironment::from_env_flag(&args.env);
    let symbols = resolve_universe_delta(args.universe_options())?;
    tracing::info!(count = symbols.len(), ?symbols, venue = "delta", "mm universe");

    let client = reqwest::Client::new();
    let products = std::sync::Arc::new(
        mm_delta::ProductCatalog::load(&client, delta_env.rest_base())
            .await
            .context("load Delta products")?,
    );

    check_anchor_settings(&symbols, dry_run)?;
    if !dry_run {
        // Every symbol needs an inventory cap of at least one contract before any symbol starts quoting.
        for s in &symbols {
            let lot = products.get(s).map(|m| m.contract_value).unwrap_or(1.0);
            size_clip_cap(s, env_f64_for_symbol(s, "MM_MAX_INVENTORY", 0.01), lot, false)?;
        }
    }
    let creds = if dry_run {
        None
    } else {
        Some(delta_credentials(delta_env)?)
    };
    let rest_timeout = Duration::from_millis(
        env_f64_global("MM_REST_TIMEOUT_MS", mm_delta::DEFAULT_REQUEST_TIMEOUT.as_millis() as f64).max(500.0) as u64,
    );
    let delta_rest = creds
        .as_ref()
        .map(|c| mm_delta::DeltaRest::new(delta_env, c.clone(), products.clone()).with_request_timeout(rest_timeout));
    let rest = delta_rest.clone().map(QuotingRest::Delta);
    let (account, heartbeat) = match &delta_rest {
        Some(r) => {
            let (flags, hb) = start_account_guards(r.clone(), &symbols, delta_env).await?;
            (Some(flags), hb)
        }
        None => (None, None),
    };

    let exec_map: Arc<Mutex<HashMap<String, SymbolExecCtx>>> = Arc::new(Mutex::new(HashMap::new()));
    let products_fill = products.clone();
    let mut fill_rxs: HashMap<String, mpsc::Receiver<FillEvent>> = HashMap::new();

    for symbol in &symbols {
        let path = economics_path_for(symbol);
        let mut economics = FillEconomics::default();
        if path.exists() {
            if let Ok(bytes) = std::fs::read_to_string(&path) {
                if let Ok(parsed) = serde_json::from_str(&bytes) {
                    economics = parsed;
                }
            }
        }
        if let Some(r) = &rest {
            let venue = r.get_position(symbol).await.unwrap_or(economics.position);
            if economics.reconcile_position(venue, 1e-6) {
                persist_economics(&path, &economics)?;
            }
        }
        let cfg = StrategyConfig::from_env_for_symbol(symbol, env_f64_global);
        let markout_rt = MarkoutRuntime::new(
            MarkoutGuard::with_rolling_capacity(cfg.markout_rolling_window),
            AlphaMuEstimator::new(64),
        );
        let (fills_tx, fills_rx) = mpsc::channel(256);
        fill_rxs.insert(symbol.clone(), fills_rx);
        exec_map.lock().unwrap().insert(
            symbol.clone(),
            SymbolExecCtx {
                economics: Arc::new(Mutex::new(economics)),
                markout: markout_rt,
                snipe: Arc::new(Mutex::new(SnipeTracker::default())),
                last_jump: Arc::new(Mutex::new(None)),
                last_fill_at: Arc::new(Mutex::new(None)),
                economics_path: path,
                fills_tx: Some(fills_tx),
            },
        );
    }

    let mut fill_feed: Option<watch::Receiver<mm_delta::PrivateFeedState>> = None;
    if let Some(c) = creds.clone() {
        let map = exec_map.clone();
        let syms = symbols.clone();
        let prod = products_fill;
        let (feed_tx, feed_rx) = watch::channel(mm_delta::PrivateFeedState::default());
        tokio::spawn(async move {
            let ws = mm_delta::DeltaPrivateWs {
                env: delta_env,
                creds: c,
            };
            ws.run_user_trades(&syms, feed_tx, move |delta_sym, row| {
                let mm_sym = normalize_symbol(&mm_delta::mm_symbol_from_delta(delta_sym));
                let Ok(guard) = map.lock() else { return };
                let Some(ctx) = guard.get(&mm_sym) else { return };
                let fill = handle_delta_fill_row(row, &prod, &mm_sym, &ctx.economics, &ctx.markout, &ctx.economics_path, &ctx.snipe, &ctx.last_jump);
                if fill.is_some() {
                    if let Ok(mut t) = ctx.last_fill_at.lock() {
                        *t = Some(Instant::now());
                    }
                }
                if let (Some(order_id), Some(contracts), Some(tx)) =
                    (fill.as_ref().and_then(|f| f.order_id), fill.as_ref().map(|f| f.contracts), &ctx.fills_tx)
                {
                    if tx.try_send(FillEvent { order_id, contracts }).is_err() {
                        tracing::warn!(symbol = %mm_sym, order_id, "fill not passed to the quote loop (queue full or loop gone); the requote path will find the order");
                    }
                }
            })
            .await;
        });
        let checked = require_fill_feed(
            feed_rx.clone(),
            secs_knob(env_f64_global("MM_FILL_FEED_WAIT_SEC", 20.0), 20.0, 1.0, 600.0),
            fill_feed_required(),
        )
        .await;
        if let Err(e) = checked {
            // No symbol loop has started, so the startup cancel-all has not run: clear what a previous
            // instance left resting (the OEMS supervisor does not cancel after a failed start).
            if let Some(r) = &delta_rest {
                for s in &symbols {
                    if let Err(ce) = r.cancel_all(s).await {
                        tracing::warn!(symbol = %s, error = %ce, "cancel-all after the refused start failed");
                    }
                }
                if let Some(id) = &heartbeat {
                    crate::account::disarm_dead_mans_switch(r, id).await;
                }
            }
            return Err(e);
        }
        fill_feed = Some(feed_rx);
    }

    // One public ob_l2 connection for every symbol (dry-runs too), unless MM_DEPTH_FEED=0.
    let mut depth_rxs = if std::env::var("MM_DEPTH_FEED").map(|v| v.trim() == "0").unwrap_or(false) {
        tracing::info!("depth feed off (MM_DEPTH_FEED=0)");
        HashMap::new()
    } else {
        mm_delta::spawn_depth_feed(delta_env, &symbols)
    };

    let mut tasks = JoinSet::new();
    for symbol in symbols {
        let args = args.clone();
        let rest = rest.clone();
        let exec_map = exec_map.clone();
        let account = account.clone();
        let fill_feed = fill_feed.clone();
        // Public catalog: dry-run has no REST client but still needs the real tick.
        let instrument = products
            .get(&symbol)
            .ok()
            .map(|m| (m.tick_size, m.contract_value, m.contract_value));
        let depth_rx = depth_rxs.remove(&symbol);
        let fills_rx = fill_rxs.remove(&symbol);
        tasks.spawn(async move {
            run_symbol_loop(
                symbol,
                args,
                dry_run,
                rest,
                exec_map,
                BookFeedKind::Delta(delta_env),
                instrument,
                account,
                fill_feed,
                depth_rx,
                fills_rx,
            )
            .await
        });
    }

    while let Some(res) = tasks.join_next().await {
        res.context("symbol task join")??;
    }
    if let (Some(r), Some(id)) = (&delta_rest, &heartbeat) {
        crate::account::disarm_dead_mans_switch(r, id).await;
    }
    if account.is_some_and(|a| a.halted()) {
        anyhow::bail!("stopped by an account guard (see the error above); orders were cancelled");
    }
    Ok(())
}

fn delta_credentials(env: mm_delta::DeltaEnvironment) -> Result<mm_delta::DeltaCredentials> {
    let vars: Vec<String> = mm_delta::key_vars(env).iter().map(|(k, s)| format!("{k}/{s}")).collect();
    let vars = vars.join(" or ");
    mm_delta::DeltaCredentials::from_env_for(env).with_context(|| format!("{vars} for a live run"))
}

/// Daily loss stop, taker-fill guard and dead man's switch for a live run. Refuses to start when
/// today's loss limit was already hit, when (mainnet only) Delta's order leverage on a quoted
/// product is above `MM_MAX_LEVERAGE` or cannot be read, or when the dead man's switch is
/// configured but cannot arm. Runs before any symbol loop is spawned, so before any order.
async fn start_account_guards(
    rest: mm_delta::DeltaRest,
    symbols: &[String],
    env: mm_delta::DeltaEnvironment,
) -> Result<(Arc<AccountFlags>, Option<String>)> {
    let cfg = AccountConfig {
        daily_loss_limit_usd: env_f64_global("MM_DAILY_LOSS_LIMIT_USD", 500.0),
        poll: Duration::from_secs_f64(env_f64_global("MM_ACCOUNT_POLL_SEC", 30.0).max(5.0)),
        dms_ttl_ms: env_f64_global("MM_DMS_TTL_MS", 0.0).max(0.0) as u64,
    };
    let label = if env == mm_delta::DeltaEnvironment::IndiaMainnet { "mainnet" } else { "demo" };
    let path = crate::account::daily_loss_path(label);
    let guard = DailyLossGuard::new(cfg.daily_loss_limit_usd, crate::account::load_daily_loss(&path));
    if guard.halted_on(Utc::now().date_naive()) {
        anyhow::bail!(
            "daily loss limit already hit today ({}); quoting stays off until 00:00 UTC. \
             Delete that file only after reviewing the account.",
            path.display()
        );
    }
    let max_leverage = crate::account::max_leverage_or_default(env_f64_global(
        "MM_MAX_LEVERAGE",
        crate::account::DEFAULT_MAX_LEVERAGE,
    ));
    crate::account::apply_leverage_guard(
        env,
        crate::account::verify_order_leverage(&rest, symbols, max_leverage).await,
    )?;
    let heartbeat = if cfg.dms_ttl_ms > 0 {
        Some(
            crate::account::arm_dead_mans_switch(&rest, symbols, cfg.dms_ttl_ms)
                .await
                .context("MM_DMS_TTL_MS is set but the dead man's switch could not be armed")?,
        )
    } else {
        None
    };
    tracing::info!(limit_usd = cfg.daily_loss_limit_usd, poll_sec = cfg.poll.as_secs(), dms_ttl_ms = cfg.dms_ttl_ms, max_leverage, "account guards on");
    let flags = Arc::new(AccountFlags::default());
    crate::account::spawn_monitor(rest, symbols.to_vec(), cfg, flags.clone(), guard, path);
    Ok((flags, heartbeat))
}

fn resolve_universe_delta(opts: UniverseOptions) -> Result<Vec<String>> {
    if opts.top_n > 0 {
        tracing::warn!("MM_TOP_N ignored for MM_VENUE=delta; set MM_SYMBOLS explicitly");
    }
    Ok(crate::symbols::resolve_symbol_list(&opts.multi, &opts.single))
}

pub async fn cancel_all(symbol: &str, env: &str, venue: &str) -> Result<()> {
    let sym = normalize_symbol(symbol);
    if venue.eq_ignore_ascii_case("delta") {
        let delta_env = mm_delta::DeltaEnvironment::from_env_flag(env);
        let creds = delta_credentials(delta_env)?;
        let client = reqwest::Client::new();
        let products = std::sync::Arc::new(
            mm_delta::ProductCatalog::load(&client, delta_env.rest_base())
                .await
                .context("delta products")?,
        );
        let rest = mm_delta::DeltaRest::new(delta_env, creds, products);
        rest.cancel_all(&sym).await.context("cancel-all")?;
        return Ok(());
    }
    let creds = BybitCredentials::from_env().context("BYBIT_API_KEY/SECRET")?;
    let bybit_env = if env == "mainnet" {
        BybitEnvironment::Mainnet
    } else {
        BybitEnvironment::Testnet
    };
    BybitRest::new(bybit_env, creds)
        .cancel_all(&sym)
        .await
        .context("cancel-all")?;
    Ok(())
}

pub async fn cancel_all_configured(env: &str, venue: &str) -> Result<()> {
    for sym in resolve_symbols_from_env() {
        cancel_all(&sym, env, venue).await?;
    }
    Ok(())
}

fn persist_economics(path: &PathBuf, eco: &FillEconomics) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(path, serde_json::to_string_pretty(eco)?)?;
    Ok(())
}

fn economics_path_for(symbol: &str) -> PathBuf {
    PathBuf::from(format!("artifacts/economics/{}.json", normalize_symbol(symbol)))
}

/// The cap the size clip uses. A cap below one lot leaves no room to quote at all: the 0.01 default is below
/// a Delta contract, so a symbol without MM_MAX_INVENTORY_<SYM> would quote nothing. A dry-run keeps quoting
/// without the clip (as before 2026-10-14) and says so; a live run refuses.
fn size_clip_cap(symbol: &str, max_inv: f64, min_qty: f64, dry_run: bool) -> Result<f64> {
    if max_inv.is_finite() && (max_inv <= 0.0 || max_inv >= min_qty) {
        return Ok(max_inv);
    }
    if dry_run {
        tracing::warn!(%symbol, max_inv, min_qty, "MM_MAX_INVENTORY is below one lot; this dry-run quotes without the size clip");
        return Ok(0.0);
    }
    anyhow::bail!(
        "{symbol}: MM_MAX_INVENTORY={max_inv} is below one order lot ({min_qty}); set MM_MAX_INVENTORY_{symbol} for a live run"
    )
}

/// Explicit venue refusals (login or subscription) after which a start stops waiting for the fills feed.
const FILL_FEED_REFUSALS_TO_FAIL: u64 = 2;

/// Start check for a run with keys. Without the private fill feed, inventory is only corrected by the venue
/// reconcile every few seconds: on 13 Oct 2026 no fill arrived over the feed for a whole live run, and the
/// cap overshot to -811 against 600. The run therefore waits for the venue to confirm the subscription, and
/// gives up early after repeated explicit refusals.
async fn require_fill_feed(
    mut feed: watch::Receiver<mm_delta::PrivateFeedState>,
    wait: Duration,
    required: bool,
) -> Result<()> {
    let waited = tokio::time::timeout(
        wait,
        feed.wait_for(|s| s.subscribed || s.refusals >= FILL_FEED_REFUSALS_TO_FAIL),
    )
    .await;
    let confirmed = matches!(&waited, Ok(Ok(s)) if s.subscribed);
    drop(waited);
    if confirmed {
        tracing::info!("delta fills feed confirmed");
        return Ok(());
    }
    let (why, refusals) = {
        let s = feed.borrow();
        (s.last_error.clone().unwrap_or_else(|| "no reply from the venue".into()), s.refusals)
    };
    if !required {
        tracing::warn!(reason = %why, "delta fills feed not confirmed; starting anyway (MM_FILL_FEED_REQUIRED=0)");
        return Ok(());
    }
    let what = if refusals >= FILL_FEED_REFUSALS_TO_FAIL {
        format!("refused {refusals} times")
    } else {
        format!("not confirmed within {:.1} s", wait.as_secs_f64())
    };
    // Logged as well as returned: the OEMS event feed and live.sh status read ERROR lines, not the exit error.
    tracing::error!(reason = %why, "delta fills feed {what}; not starting");
    anyhow::bail!(
        "delta fills feed {what} ({why}); fills would reach the bot only through the venue reconcile. Fix the \
         login, or waive the check with MM_FILL_FEED_REQUIRED=0 (live.sh: in the profile; OEMS: a config override)"
    )
}

/// The anchored fair's settings per symbol, checked before any order (`mm_core::fair::live_anchor_check`): a
/// live run may anchor only on the depth source, since our own quotes are most of the L1 book the `book`
/// source reads (plans/live-basis.plan.md). An unknown source is refused in dry-runs too.
fn check_anchor_settings(symbols: &[String], dry_run: bool) -> Result<Vec<(String, mm_core::fair::AnchorSettings)>> {
    let slugs: Vec<String> = symbols.iter().map(|s| normalize_symbol(s)).collect();
    let settings = mm_core::fair::live_anchor_check(&slugs, !dry_run, |k| std::env::var(k).ok())
        .map_err(|e| anyhow::anyhow!(e))?;
    for (sym, s) in &settings {
        tracing::info!(symbol = %sym, anchor_weight = s.weight, basis_source = s.source.as_str(), "anchor settings");
    }
    Ok(settings)
}

/// A depth book that can never yield a basis sample (feed off, an unusable threshold, or a threshold our own
/// order could reach) is refused at start when the depth source is anchored: the anchor would stay off and a
/// live run would pull every quote. Otherwise it is a warning, since the depth basis is then logged only.
fn depth_source_check(
    symbol: &str,
    source: BasisSource,
    anchor_weight: f64,
    have_feed: bool,
    depth_qty: Option<f64>,
    depth_base_qty: f64,
    base_qty: f64,
) -> Result<()> {
    let problem = if !have_feed {
        (source == BasisSource::Depth).then(|| "MM_DEPTH_FEED=0 switches the depth feed off".to_string())
    } else if depth_qty.is_none() {
        Some(format!("MM_BASIS_DEPTH_QTY={depth_base_qty} is not a positive size"))
    } else if depth_base_qty <= 2.0 * base_qty {
        Some(format!(
            "MM_BASIS_DEPTH_QTY={depth_base_qty} is not above twice the order size {base_qty}, so our own order could set the depth price"
        ))
    } else {
        None
    };
    match problem {
        None => Ok(()),
        Some(p) if source == BasisSource::Depth && anchor_weight > 0.0 => {
            anyhow::bail!("{symbol}: {p}; the anchored fair needs a usable depth book (MM_BASIS_SOURCE=depth)")
        }
        Some(p) => {
            tracing::warn!(%symbol, "{p}; the depth basis is logged only for this symbol");
            Ok(())
        }
    }
}

/// `MM_FILL_FEED_REQUIRED` (default on; "0" waives the start check and the mid-run pull).
fn fill_feed_required() -> bool {
    std::env::var("MM_FILL_FEED_REQUIRED").map(|v| v.trim() != "0").unwrap_or(true)
}

/// `x` to 10 significant digits, so a logged value carries no float noise (0.23215000000000002 -> 0.23215).
fn sig10(x: f64) -> f64 {
    if x == 0.0 || !x.is_finite() {
        return x;
    }
    let m = 10f64.powi(9 - x.abs().log10().floor() as i32);
    if !m.is_finite() || m == 0.0 {
        return x;
    }
    (x * m).round() / m
}

/// A duration knob given in seconds: `default` when it is not finite, then clamped to `[lo, hi]`.
/// `Duration::from_secs_f64` panics on an infinite or negative value, and "inf" parses as an f64.
fn secs_knob(value: f64, default: f64, lo: f64, hi: f64) -> Duration {
    let v = if value.is_finite() { value } else { default };
    Duration::from_secs_f64(v.clamp(lo, hi))
}

/// One read of the venue position: when its request went out, and the size (None when the read failed).
#[derive(Debug, Clone, Copy)]
struct VenuePositionRead {
    sent: Instant,
    position: Option<f64>,
}

async fn read_venue_position(rest: &QuotingRest, symbol: &str) -> VenuePositionRead {
    let sent = Instant::now();
    let position = match rest.get_position(symbol).await {
        Ok(p) => Some(p),
        Err(e) => {
            tracing::warn!(%symbol, ?e, "venue position fetch failed");
            None
        }
    };
    VenuePositionRead { sent, position }
}

/// The venue position, read every `every` off the quoting loop, which takes each new reading when it arrives.
/// Awaited inside the loop, a read that timed out held the quotes still: 3.4 s in the 22 Oct 2026 08:21Z
/// Delta outage. The task ends when the loop drops the receiver.
fn spawn_venue_position_poller(rest: QuotingRest, symbol: String, every: Duration) -> watch::Receiver<Option<VenuePositionRead>> {
    let (tx, rx) = watch::channel(None);
    tokio::spawn(async move {
        let mut tick = tokio::time::interval(every);
        tick.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
        loop {
            tick.tick().await;
            let read = read_venue_position(&rest, &symbol).await;
            if tx.send(Some(read)).is_err() {
                break;
            }
        }
    });
    rx
}

/// The reading the poller sent since the last call, if any.
fn take_venue_read(rx: &mut watch::Receiver<Option<VenuePositionRead>>) -> Option<VenuePositionRead> {
    if rx.has_changed().unwrap_or(false) {
        *rx.borrow_and_update()
    } else {
        None
    }
}

/// The venue is the source of truth for the open size, but its REST position trails the fills feed, so a
/// reading sent before or right after one of our fills is not adopted at once (`VenueReconcile`). Returns the
/// inventory to quote with and the venue's reading (None when it could not be read).
fn apply_venue_read(
    read: VenuePositionRead,
    symbol: &str,
    economics_arc: &Arc<Mutex<FillEconomics>>,
    econ_path: &PathBuf,
    tolerance: f64,
    reconcile: &mut VenueReconcile,
    last_fill: Option<Instant>,
) -> (f64, Option<f64>) {
    let Some(venue_pos) = read.position else {
        return (economics_arc.lock().map(|e| e.position).unwrap_or(0.0), None);
    };
    let Ok(mut eco) = economics_arc.lock() else { return (venue_pos, Some(venue_pos)) };
    let bot_pos = eco.position;
    match reconcile.check_read(bot_pos, venue_pos, tolerance, last_fill, read.sent, Instant::now()) {
        VenueReading::Agrees => (bot_pos, Some(venue_pos)),
        VenueReading::Deferred => {
            tracing::debug!(%symbol, bot_pos, venue_pos, "venue position trails a fresh fill; kept the bot's count");
            (bot_pos, Some(venue_pos))
        }
        VenueReading::Adopt => {
            eco.reconcile_position(venue_pos, tolerance);
            if let Err(e) = persist_economics(econ_path, &eco) {
                tracing::warn!(%symbol, ?e, "persist economics after reconcile");
            }
            tracing::info!(%symbol, bot_pos, venue_pos, "inventory reconciled from venue");
            (venue_pos, Some(venue_pos))
        }
    }
}

fn env_f64_global(key: &str, default: f64) -> f64 {
    std::env::var(key)
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(default)
}

pub async fn run(args: RunArgs, dry_run: bool) -> Result<()> {
    if args.venue.eq_ignore_ascii_case("delta") {
        return run_delta(args, dry_run).await;
    }
    let bybit_env = if args.env == "mainnet" {
        BybitEnvironment::Mainnet
    } else {
        BybitEnvironment::Testnet
    };
    let symbols = resolve_universe(args.universe_options(), bybit_env).await?;
    tracing::info!(count = symbols.len(), ?symbols, "mm universe");
    for (sym, settings) in check_anchor_settings(&symbols, dry_run)? {
        if settings.source == BasisSource::Depth {
            anyhow::bail!("{sym}: MM_BASIS_SOURCE=depth needs the Delta ob_l2 feed; Bybit has only the book source");
        }
    }

    let creds = if dry_run {
        None
    } else {
        Some(
            BybitCredentials::from_env()
                .context("BYBIT_API_KEY/SECRET for live run")?,
        )
    };
    let rest = creds
        .as_ref()
        .map(|c| QuotingRest::Bybit(BybitRest::new(bybit_env, c.clone())));

    let exec_map: Arc<Mutex<HashMap<String, SymbolExecCtx>>> = Arc::new(Mutex::new(HashMap::new()));

    for symbol in &symbols {
        let path = economics_path_for(symbol);
        let mut economics = FillEconomics::default();
        if path.exists() {
            if let Ok(bytes) = std::fs::read_to_string(&path) {
                if let Ok(parsed) = serde_json::from_str(&bytes) {
                    economics = parsed;
                }
            }
        }
        if let Some(r) = &rest {
            let venue = r.get_position(symbol).await.unwrap_or(economics.position);
            if economics.reconcile_position(venue, 1e-6) {
                persist_economics(&path, &economics)?;
            }
        }
        let cfg = StrategyConfig::from_env_for_symbol(symbol, env_f64_global);
        let markout_rt = MarkoutRuntime::new(
            MarkoutGuard::with_rolling_capacity(cfg.markout_rolling_window),
            AlphaMuEstimator::new(64),
        );
        exec_map.lock().unwrap().insert(
            symbol.clone(),
            SymbolExecCtx {
                economics: Arc::new(Mutex::new(economics)),
                markout: markout_rt,
                snipe: Arc::new(Mutex::new(SnipeTracker::default())),
                last_jump: Arc::new(Mutex::new(None)),
                last_fill_at: Arc::new(Mutex::new(None)),
                economics_path: path,
                fills_tx: None,
            },
        );
    }

    if let Some(c) = creds.clone() {
        let map = exec_map.clone();
        tokio::spawn(async move {
            let ws = BybitPrivateWs {
                env: bybit_env,
                creds: c,
            };
            let _ = ws
                .run_execution(move |data| {
                    if let Some(rows) = data.as_array() {
                        for row in rows {
                            let sym = row
                                .get("symbol")
                                .and_then(|s| s.as_str())
                                .map(normalize_symbol)
                                .unwrap_or_default();
                            let Ok(guard) = map.lock() else { continue };
                            let Some(ctx) = guard.get(&sym) else { continue };
                            if let Ok(mut t) = ctx.last_fill_at.lock() {
                                *t = Some(Instant::now());
                            }
                            handle_execution_row(
                                row,
                                &ctx.economics,
                                &ctx.markout,
                                &ctx.economics_path,
                                &ctx.snipe,
                                &ctx.last_jump,
                            );
                        }
                    }
                })
                .await;
        });
    }

    let mut tasks = JoinSet::new();
    for symbol in symbols {
        let args = args.clone();
        let rest = rest.clone();
        let exec_map = exec_map.clone();
        tasks.spawn(async move {
            run_symbol_loop(
                symbol,
                args,
                dry_run,
                rest,
                exec_map,
                BookFeedKind::Bybit(bybit_env),
                None,
                None,
                None,
                None,
                None,
            )
                .await
        });
    }

    while let Some(res) = tasks.join_next().await {
        res.context("symbol task join")??;
    }
    Ok(())
}

async fn run_symbol_loop(
    symbol: String,
    args: RunArgs,
    dry_run: bool,
    rest: Option<QuotingRest>,
    exec_map: Arc<Mutex<HashMap<String, SymbolExecCtx>>>,
    book_kind: BookFeedKind,
    instrument: Option<(f64, f64, f64)>,
    account: Option<Arc<AccountFlags>>,
    fill_feed: Option<watch::Receiver<mm_delta::PrivateFeedState>>,
    depth_rx: Option<mm_delta::DepthRx>,
    mut fills_rx: Option<mpsc::Receiver<FillEvent>>,
) -> Result<()> {
    let cfg = StrategyConfig::from_env_for_symbol(&symbol, env_f64_global);

    let (book_tx, mut book_rx) = watch::channel(BookTop::default());
    spawn_book_feed(symbol.clone(), book_kind, book_tx);

    let (bbo_tx, bbo_rx) = watch::channel(mm_binance::BinanceBbo::default());
    let sym = symbol.clone();
    tokio::spawn(async move {
        let _ = mm_binance::run_book_ticker(&sym, bbo_tx).await;
    });

    // Delta funding, mark and spot index come from a background poller (public, so dry-runs get it too).
    // The loop only reads the latest snapshot, so a slow venue cannot stall it.
    let ticker_rx = match book_kind {
        BookFeedKind::Delta(env) => Some(mm_delta::spawn_ticker_poller(
            env,
            mm_delta::delta_product_symbol(&symbol),
            secs_knob(env_f64_for_symbol(&symbol, "MM_TICKER_POLL_MS", 3000.0) / 1000.0, 3.0, 0.5, 3600.0),
            Duration::from_millis(2000),
        )),
        BookFeedKind::Bybit(_) => None,
    };
    let ticker_stale_after = secs_knob(env_f64_for_symbol(&symbol, "MM_TICKER_STALE_SEC", 30.0), 30.0, 1.0, 3600.0);
    // Delta depth mid: where cumulative size reaches MM_BASIS_DEPTH_QTY base units per side (ob_l2). A fixed
    // size, so nothing our quotes move can shift it. Logged only for now; it is the candidate live basis source
    // (plans/live-basis.plan.md). The default is ADA's: a size between its 3,850 order and its 28k ladder.
    let depth_base_qty = env_f64_for_symbol(&symbol, "MM_BASIS_DEPTH_QTY", 10_000.0);
    let depth_stale_after = secs_knob(env_f64_for_symbol(&symbol, "MM_DEPTH_STALE_MS", 2000.0) / 1000.0, 2.0, 0.1, 3600.0);

    let fallback_instrument = instrument.unwrap_or((0.01, 0.001, 0.001));
    let (tick, step, min_qty) = if let Some(r) = &rest {
        r.get_instrument(&symbol).await.unwrap_or(fallback_instrument)
    } else {
        fallback_instrument
    };
    tracing::info!(%symbol, tick, min_qty, "instrument");
    let contract_value = step; // Delta's instrument tuple is (tick, contract value, contract value)

    let max_inv = env_f64_for_symbol(&symbol, "MM_MAX_INVENTORY", 0.01);
    let clip_cap = size_clip_cap(&symbol, max_inv, min_qty, dry_run)?;
    let base_qty = env_f64_for_symbol(&symbol, "MM_ORDER_QTY", min_qty.max(0.001));
    let depth_qty = mm_core::depth::contracts_for_qty(depth_base_qty, contract_value);

    let mut vol_tracker = VolTracker::new(96);
    let kappa_est = KappaEstimator::default();
    let mut ofi = OfiTracker::new(128);
    let mut regime_engine = RegimeEngine::default();

    let loop_interval = Duration::from_millis(args.loop_ms.max(100));
    let mut interval = tokio::time::interval(loop_interval);
    let mut risk = crate::risk::RiskState::default();
    let book_stale_after =
        Duration::from_millis(env_f64_for_symbol(&symbol, "MM_BOOK_STALE_MS", 2000.0).max(100.0) as u64);
    let mut book_watch = BookWatch::new(book_stale_after);
    let secs = |key: &str, default: f64| Duration::from_secs_f64(env_f64_for_symbol(&symbol, key, default).max(0.0));
    let mut frozen_watch = FrozenBookWatch::new(
        secs("MM_FROZEN_BOOK_SEC", 30.0),
        env_f64_for_symbol(&symbol, "MM_FROZEN_BOOK_MOVE_BPS", 5.0).max(0.0),
        secs("MM_FROZEN_BOOK_MAX_SEC", 120.0),
    );
    let mut depth_seen = false;
    let mut stale_cancel_pending = false;
    let mut oms = OmsState::default();
    let mut last_fair: Option<f64> = None;
    let mut last_binance_mid: f64 = 0.0;
    let lead_lookback_sec = env_f64_for_symbol(&symbol, "MM_LEAD_LOOKBACK_SEC", 3.0).max(0.0);
    let lead_beta = env_f64_for_symbol(&symbol, "MM_LEAD_BETA", 0.8);
    let lead_max_bps = env_f64_for_symbol(&symbol, "MM_LEAD_MAX_BPS", 15.0);
    let lead_clock = Instant::now();
    let mut binance_hist: VecDeque<(f64, f64)> = VecDeque::new();
    // Fair anchored to the Binance level (artifacts/research/2026-10-13-live-run-pickoff.md). Off unless
    // MM_FAIR_ANCHOR_WEIGHT > 0; the basis average is kept (and logged) either way.
    let anchor_weight = env_f64_for_symbol(&symbol, "MM_FAIR_ANCHOR_WEIGHT", 0.0).clamp(0.0, 1.0);
    // Where the basis reads Delta's price (checked at start): the L1 mid, or the ob_l2 depth mid that our own
    // quotes cannot move. The depth source gets a short max age, so a dead depth feed turns the anchor off fast.
    let basis_source = env_for_symbol(&symbol, "MM_BASIS_SOURCE")
        .and_then(|v| BasisSource::parse(&v))
        .unwrap_or(BasisSource::Book);
    let basis_half_life = env_f64_for_symbol(&symbol, "MM_BASIS_HALFLIFE_SEC", 120.0).max(0.0);
    // One update covers at most two loops; each sample stays within MM_BASIS_CLAMP_BPS of the average.
    let new_basis = || {
        mm_core::fair::BasisEma::new(basis_half_life)
            .with_max_step(2.0 * args.loop_ms.max(100) as f64 / 1000.0)
            .with_clamp(env_f64_for_symbol(&symbol, "MM_BASIS_CLAMP_BPS", 5.0))
    };
    let mut basis = new_basis();
    let basis_warmup_sec = env_f64_for_symbol(&symbol, "MM_BASIS_WARMUP_SEC", 60.0).max(0.0);
    let basis_max_age_default = match basis_source {
        BasisSource::Book => 300.0,
        BasisSource::Depth => 30.0,
    };
    let basis_max_age_sec = env_f64_for_symbol(&symbol, "MM_BASIS_MAX_AGE_SEC", basis_max_age_default).max(0.0);
    // Live, with the anchor on, an anchor off for longer than this pulls both quotes rather than quoting on
    // the fallback fair, which reads our own quotes (plans/live-basis.plan.md). FeedWatch's outage logic
    // fits; it starts pulled, so the first quotes wait for the anchor instead of resting on that fair.
    let mut anchor_watch = (!dry_run && anchor_weight > 0.0).then(|| {
        let pull_after = secs_knob(env_f64_for_symbol(&symbol, "MM_FAIR_ANCHOR_OFF_PULL_SEC", 10.0), 10.0, 1.0, 3600.0);
        FeedWatch::starting_down(pull_after, Instant::now())
    });
    tracing::info!(%symbol, anchor_weight, basis_source = basis_source.as_str(), basis_max_age_sec, "basis source");
    depth_source_check(&symbol, basis_source, anchor_weight, depth_rx.is_some(), depth_qty, depth_base_qty, base_qty)?;
    let binance_stale_after =
        Duration::from_millis(env_f64_for_symbol(&symbol, "MM_BINANCE_STALE_MS", 5000.0).max(0.0) as u64);
    let mut binance_seq: u64 = 0;
    let mut binance_msg_at: Option<Instant> = None;
    let warm_samples = env_f64_for_symbol(&symbol, "MM_WARMUP_SAMPLES", 32.0) as usize;

    if !dry_run {
        if std::env::var("MM_CANCEL_ALL_ON_START")
            .map(|v| v != "0" && !v.eq_ignore_ascii_case("false"))
            .unwrap_or(true)
        {
            if let Some(r) = &rest {
                let mut cancelled = false;
                for attempt in 1..=3 {
                    match r.cancel_all(&symbol).await {
                        Ok(()) => {
                            tracing::info!(%symbol, attempt, "startup cancel-all");
                            cancelled = true;
                            break;
                        }
                        Err(e) => {
                            tracing::warn!(%symbol, attempt, error = %e, "startup cancel-all failed");
                            tokio::time::sleep(Duration::from_millis(400)).await;
                        }
                    }
                }
                if !cancelled {
                    tracing::error!(%symbol, "startup cancel-all did not succeed; quoting anyway");
                }
            }
        }
    }

    let markout_rt = exec_map
        .lock()
        .unwrap()
        .get(&symbol)
        .map(|c| c.markout.clone())
        .context("exec ctx missing")?;
    let economics_arc = exec_map
        .lock()
        .unwrap()
        .get(&symbol)
        .map(|c| c.economics.clone())
        .context("exec ctx missing")?;
    let last_jump_at = exec_map
        .lock()
        .unwrap()
        .get(&symbol)
        .map(|c| c.last_jump.clone())
        .context("exec ctx missing")?;
    let last_fill_at = exec_map
        .lock()
        .unwrap()
        .get(&symbol)
        .map(|c| c.last_fill_at.clone())
        .context("exec ctx missing")?;
    let snipe = exec_map
        .lock()
        .unwrap()
        .get(&symbol)
        .map(|c| c.snipe.clone())
        .context("exec ctx missing")?;
    let economics_path = exec_map
        .lock()
        .unwrap()
        .get(&symbol)
        .map(|c| c.economics_path.clone())
        .context("exec ctx missing")?;

    let use_venue_inventory = std::env::var("MM_USE_VENUE_INVENTORY")
        .map(|v| v != "0" && !v.eq_ignore_ascii_case("false"))
        .unwrap_or(true);
    let reconcile_tol = env_f64_for_symbol(&symbol, "MM_INVENTORY_RECONCILE_TOL", 1e-6);
    let reconcile_every = Duration::from_secs_f64(
        env_f64_for_symbol(&symbol, "MM_VENUE_RECONCILE_SEC", 5.0).max(0.5),
    );
    let mut venue_reconcile = VenueReconcile::new(
        Duration::from_millis(env_f64_for_symbol(&symbol, "MM_RECONCILE_FILL_GRACE_MS", 3000.0).clamp(0.0, 60_000.0) as u64),
        secs_knob(env_f64_for_symbol(&symbol, "MM_RECONCILE_MAX_WAIT_SEC", 15.0), 15.0, 1.0, 600.0),
    );
    // The venue's last reported position. The private fills feed and the reconcile both move the bot's
    // inventory, and either can lag the other, so the adding side is sized against both readings.
    let mut last_venue_pos: Option<f64> = None;
    let mut last_reduce_only = Instant::now() - Duration::from_secs(2);
    // Only with the check on: a waived start (MM_FILL_FEED_REQUIRED=0) chose to run on the reconcile alone.
    let mut feed_watch = (fill_feed.is_some() && fill_feed_required()).then(|| {
        FeedWatch::new(secs_knob(env_f64_for_symbol(&symbol, "MM_FILL_FEED_DOWN_PULL_SEC", 30.0), 30.0, 5.0, 3600.0))
    });
    let mut l3_pause_until: Option<Instant> = None;
    let mut reject_over_since: Option<Instant> = None;

    let mut venue_rx = None;
    if !dry_run {
        if let Some(r) = &rest {
            if use_venue_inventory {
                // Before the first quote, so the startup read is awaited; later reads come from the poller.
                let read = read_venue_position(r, &symbol).await;
                let (inv, venue) =
                    apply_venue_read(read, &symbol, &economics_arc, &economics_path, reconcile_tol, &mut venue_reconcile, None);
                last_venue_pos = Some(venue.unwrap_or(inv));
                tracing::info!(%symbol, inventory = inv, "startup venue inventory");
                venue_rx = Some(spawn_venue_position_poller(r.clone(), symbol.clone(), reconcile_every));
            }
        }
    }

    // An iteration that overran its tick (order calls) is followed by one tick at once, then the loop's rhythm
    // again; tokio's default fired every missed tick back to back.
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
    let mut iteration_started: Option<Instant> = None;
    let mut loop_work_ms: Option<u64> = None;
    loop {
        if let Some(t) = iteration_started {
            loop_work_ms = Some(t.elapsed().as_millis() as u64);
        }
        interval.tick().await;
        iteration_started = Some(Instant::now());
        if let Some(a) = &account {
            risk.daily_pnl_usd = a.daily_pnl_usd();
            if a.halted() {
                if let Some(r) = &rest {
                    for attempt in 1..=3 {
                        match r.cancel_all(&symbol).await {
                            Ok(()) => break,
                            Err(e) => tracing::warn!(%symbol, attempt, error = %e, "halt cancel-all failed"),
                        }
                    }
                }
                oms.live.clear();
                tracing::error!(%symbol, daily_pnl_usd = risk.daily_pnl_usd, "account halt — orders cancelled, quoting stopped");
                break;
            }
        }
        // Quotes the fills said were done that the venue did not yet show closed: ask again (its order state can
        // trail the fills feed by a few hundred ms).
        for side in [QuoteSide::Bid, QuoteSide::Ask] {
            if let Some(id) = oms.live.awaiting_venue(side) {
                settle_with_venue(rest.as_ref(), &symbol, &mut oms.live, side, id).await;
            }
        }
        // Fills since the last loop, against the quotes they hit. A quote the fills say is done is forgotten only
        // once the venue says it is closed; then this loop quotes that side again.
        if let Some(rx) = fills_rx.as_mut() {
            while let Ok(ev) = rx.try_recv() {
                match oms.live.apply_fill(ev, Instant::now()) {
                    FillApplied::Partial { side, left } => {
                        tracing::info!(%symbol, ?side, order_id = ev.order_id, contracts = ev.contracts, left = ?left, "fill on a resting quote");
                    }
                    FillApplied::Filled { side } => {
                        tracing::info!(%symbol, ?side, order_id = ev.order_id, contracts = ev.contracts, "fill reached the quote's size");
                        settle_with_venue(rest.as_ref(), &symbol, &mut oms.live, side, ev.order_id).await;
                    }
                    FillApplied::Unknown => {
                        tracing::debug!(%symbol, order_id = ev.order_id, contracts = ev.contracts, "fill of an order that is not a resting quote");
                    }
                }
            }
        }
        // A dropped feed task counts as no update, so the book goes stale.
        let updated = book_rx.has_changed().unwrap_or(false);
        let top = book_rx.borrow_and_update().clone();
        match book_watch.check(updated, Instant::now()) {
            BookAge::Fresh => {}
            BookAge::Recovered(outage) => {
                tracing::info!(%symbol, outage_ms = outage.as_millis() as u64, "book fresh again");
            }
            age @ (BookAge::WentStale | BookAge::Stale) => {
                if age == BookAge::WentStale {
                    tracing::warn!(
                        %symbol,
                        age_ms = book_watch.age_ms(Instant::now()),
                        limit_ms = book_stale_after.as_millis() as u64,
                        "stale book — cancel all"
                    );
                    oms.live.clear();
                    stale_cancel_pending = rest.is_some();
                }
                // A dead feed often means a dead network, so the first cancel can fail too:
                // keep trying every loop until the venue confirms.
                if stale_cancel_pending {
                    if let Some(r) = &rest {
                        match r.cancel_all(&symbol).await {
                            Ok(()) => stale_cancel_pending = false,
                            Err(e) => tracing::warn!(%symbol, error = %e, "stale-book cancel-all failed; retrying"),
                        }
                    }
                }
                continue;
            }
        }
        if top.best_bid <= 0.0 || top.best_ask <= top.best_bid {
            continue;
        }

        let bbo = *bbo_rx.borrow();
        let binance_mid = bbo.mid;
        if bbo.seq != binance_seq {
            binance_seq = bbo.seq;
            binance_msg_at = Some(Instant::now());
        }
        // A silent feed counts as stale even if the price would not have moved.
        let binance_fresh = binance_mid > 0.0 && binance_msg_at.is_some_and(|t| t.elapsed() <= binance_stale_after);

        // A book that keeps arriving but has stopped changing while Binance moves (17 Oct 2026): pull quotes and
        // skip the loop, so neither the basis nor OFI, volatility or the fair learn the frozen book.
        let top_now = [top.best_bid, top.best_ask, top.bid_qty, top.ask_qty];
        match frozen_watch.check(top_now, binance_fresh.then_some(binance_mid), Instant::now()) {
            BookFreeze::Live => {}
            BookFreeze::Thawed(frozen) => {
                tracing::info!(%symbol, frozen_ms = frozen.as_millis() as u64, "book fresh again: changing after a freeze");
            }
            freeze @ (BookFreeze::WentFrozen { .. } | BookFreeze::Frozen) => {
                if let BookFreeze::WentFrozen { unchanged, binance_move_bps } = freeze {
                    tracing::warn!(
                        %symbol,
                        unchanged_ms = unchanged.as_millis() as u64,
                        binance_move_bps,
                        "stale book: frozen, unchanged while frames arrive — cancel all"
                    );
                    oms.live.clear();
                    stale_cancel_pending = rest.is_some();
                }
                if stale_cancel_pending {
                    if let Some(r) = &rest {
                        match r.cancel_all(&symbol).await {
                            Ok(()) => stale_cancel_pending = false,
                            Err(e) => tracing::warn!(%symbol, error = %e, "frozen-book cancel-all failed; retrying"),
                        }
                    }
                }
                continue;
            }
        }

        ofi.on_book(top.best_bid, top.bid_qty, top.best_ask, top.ask_qty);

        let fair_native = top.mid().unwrap_or((top.best_bid + top.best_ask) / 2.0);
        markout_rt.update_fair(fair_native);
        vol_tracker.push(fair_native);
        let sample_vol = vol_tracker.vol_bps();
        regime_engine.update_vol(sample_vol);
        let vol_bps = horizon_vol_bps(
            sample_vol,
            96,
            args.loop_ms as f64 / 1000.0,
            env_f64_for_symbol(&symbol, "MM_VOL_HORIZON_SEC", 900.0),
        );

        let kappa = kappa_est.kappa(cfg.as_kappa, 5, cfg.kappa_floor, cfg.kappa_cap);
        if let Ok(mut g) = markout_rt.guard.lock() {
            g.on_loop_decay(env_f64_for_symbol(&symbol, "MM_MARKOUT_DECAY", 0.85));
        }

        if binance_mid > 0.0 && last_binance_mid > 0.0 {
            let jump_bps = (binance_mid - last_binance_mid) / last_binance_mid * 10_000.0;
            if jump_bps.abs() > 5.0 {
                if let Ok(mut j) = last_jump_at.lock() {
                    *j = Some(Instant::now());
                }
            }
        }
        if binance_mid > 0.0 {
            last_binance_mid = binance_mid;
        }
        let lead_now = lead_clock.elapsed().as_secs_f64();
        if binance_fresh {
            binance_hist.push_back((lead_now, binance_mid));
        } else {
            // A silent feed is a gap: after a reconnect the move lead starts from post-reconnect prices only.
            binance_hist.clear();
        }
        while binance_hist
            .front()
            .is_some_and(|(t, _)| *t < lead_now - 2.0 * lead_lookback_sec)
        {
            binance_hist.pop_front();
        }
        let binance_move_bps = if binance_mid > 0.0 {
            mm_core::fair::move_bps(binance_hist.make_contiguous(), lead_now, lead_lookback_sec)
        } else {
            0.0
        };

        let depth = depth_rx.as_ref().map(|rx| rx.borrow().clone());
        let depth_snap = depth.as_ref().and_then(|d| d.as_deref());
        if depth_snap.is_some() && !depth_seen {
            depth_seen = true;
            tracing::info!(%symbol, "depth book streaming (ob_l2)");
        }
        let depth_read: Option<Result<mm_core::depth::DepthSides, String>> = depth.as_ref().map(|d| match d {
            None => Err("no_feed".into()),
            Some(d) if d.received_at.elapsed() > depth_stale_after => Err("stale".into()),
            Some(d) => match depth_qty {
                None => Err("invalid".into()),
                Some(q) => mm_core::depth::depth_sides(&d.bids, &d.asks, q, q).map_err(|e| e.as_str().into()),
            },
        });
        let depth_ok = depth_read.as_ref().and_then(|r| r.as_ref().ok());
        let (depth_bid, depth_ask) = (depth_ok.and_then(|s| s.bid.ok()), depth_ok.and_then(|s| s.ask.ok()));

        // The basis sample for this loop. Source `book`: the Delta L1 mid, skipped while our own resting
        // quote is the touch (live only; a dry-run has no resting orders), since that mid would feed our
        // fair back into the basis. Source `depth`: the ob_l2 depth mid from a fresh snapshot.
        let own_touch = oms.live.bid.is_some_and(|p| (p - top.best_bid).abs() < tick * 0.5)
            || oms.live.ask.is_some_and(|p| (p - top.best_ask).abs() < tick * 0.5);
        let basis_sample = match basis_source {
            BasisSource::Book if own_touch => None,
            BasisSource::Book => top.mid(),
            BasisSource::Depth => depth_ok.and_then(|s| s.mid()).map(|d| d.mid),
        };
        let basis_aged_out = basis.last_update().is_some_and(|t| lead_now - t > basis_max_age_sec);
        if basis_aged_out {
            basis = new_basis(); // too old to trust: warm up again before anchoring
        }
        let mut basis_updated = false;
        if let (true, Some(px)) = (binance_fresh, basis_sample) {
            basis.update(lead_now, px, binance_mid);
            basis_updated = true;
        }
        let basis_fresh = basis.warm_sec(lead_now) >= basis_warmup_sec
            && basis.last_update().is_some_and(|t| lead_now - t <= basis_max_age_sec);
        let anchor_fair = if anchor_weight > 0.0 && binance_fresh && basis_fresh {
            basis.value_bps().and_then(|b| mm_core::fair::anchored_fair(binance_mid, b))
        } else {
            None
        };
        let anchor_off_reason: Option<&'static str> = (anchor_weight > 0.0 && anchor_fair.is_none()).then(|| {
            if !binance_fresh {
                "binance_stale"
            } else if basis_aged_out {
                "basis_stale"
            } else if basis.value_bps().is_none() {
                "no_source"
            } else {
                "basis_warming"
            }
        });

        let jump_bps = last_fair
            .map(|lf| (fair_native - lf) / lf * 10_000.0)
            .unwrap_or(0.0);
        let depth_ratio =
            (top.bid_qty.min(top.ask_qty) / top.bid_qty.max(top.ask_qty).max(1e-9)).clamp(0.0, 1.0);
        let regime_th = RegimeThresholds {
            l3_depth_ratio: env_f64_for_symbol(&symbol, "MM_REGIME_L3_DEPTH_RATIO", 0.2),
            l3_jump_bps: env_f64_for_symbol(&symbol, "MM_REGIME_L3_JUMP_BPS", 50.0),
            l3_flow_z: env_f64_for_symbol(&symbol, "MM_REGIME_L3_FLOW_Z", 4.0),
        };
        let regime = regime_engine.evaluate_with(&regime_th, depth_ratio, jump_bps.abs());
        let regime_mult = if regime.level == RegimeLevel::L3Crash {
            999.0
        } else {
            regime.level.spread_multiplier()
        };

        let inventory = if let Some(rx) = venue_rx.as_mut() {
            if let Some(read) = take_venue_read(rx) {
                let last_fill = last_fill_at.lock().ok().and_then(|t| *t);
                let (inv, venue) =
                    apply_venue_read(read, &symbol, &economics_arc, &economics_path, reconcile_tol, &mut venue_reconcile, last_fill);
                last_venue_pos = Some(venue.unwrap_or(inv));
                inv
            } else {
                economics_arc
                    .lock()
                    .map(|e| e.position)
                    .unwrap_or(0.0)
            }
        } else {
            economics_arc
                .lock()
                .map(|e| e.position)
                .unwrap_or(0.0)
        };

        let ticker = ticker_rx
            .as_ref()
            .and_then(|rx| rx.borrow().clone())
            .filter(|t| t.received_at.elapsed() <= ticker_stale_after);
        // A dry-run's inventory is whatever the economics file held at start and is never reconciled, so
        // it gets no carry: dry-runs stay comparable with each other and with the shadow.
        let funding_bps = match (&ticker_rx, &rest) {
            _ if dry_run => 0.0,
            (Some(_), _) => ticker
                .as_ref()
                .and_then(|t| t.funding_rate_pct)
                .map(|rate| mm_delta::funding_carry_bps(inventory, rate))
                .unwrap_or(0.0),
            (None, Some(r)) => r.get_funding_carry_bps(&symbol, inventory).await.unwrap_or(0.0),
            (None, None) => 0.0,
        };

        let ofi_beta = env_f64_for_symbol(&symbol, "MM_OFI_BETA", 0.01);
        let alpha_mu_bps = markout_rt
            .alpha
            .lock()
            .map(|a| a.alpha_mu_bps())
            .unwrap_or(0.0);

        let ext = QuoteExtensions {
            binance_mid: if binance_mid > 0.0 {
                Some(binance_mid)
            } else {
                None
            },
            binance_move_bps,
            lead_weight: lead_beta,
            lead_max_bps,
            ofi_drift_bps: ofi.drift_bps(ofi_beta, top.bid_qty + top.ask_qty),
            funding_carry_bps: funding_bps,
            alpha_mu_bps,
            regime_spread_mult: regime_mult,
            anchor_fair,
            anchor_weight,
        };

        // Update before kill/L3 continue so the next loop measures a fresh jump.
        last_fair = Some(fair_native);

        // Reject-kill is not permanent: after 30s over the threshold, reset count.
        if risk.reject_count > risk.reject_kill_count {
            match reject_over_since {
                None => reject_over_since = Some(Instant::now()),
                Some(since) if since.elapsed() >= Duration::from_secs(30) => {
                    tracing::warn!(
                        %symbol,
                        was = risk.reject_count,
                        "reject kill cooldown — resetting reject_count"
                    );
                    risk.reject_count = 0;
                    reject_over_since = None;
                }
                Some(_) => {}
            }
        } else {
            reject_over_since = None;
        }

        if regime.level == RegimeLevel::L3Crash {
            let in_pause = l3_pause_until
                .map(|d| Instant::now() < d)
                .unwrap_or(false);
            if !in_pause {
                l3_pause_until = Some(Instant::now() + Duration::from_secs(5));
            }
        }

        if l3_pause_until
            .map(|d| Instant::now() < d)
            .unwrap_or(false)
        {
            if let Some(r) = &rest {
                let _ = r.cancel_all(&symbol).await;
            }
            oms.live.clear();
            tracing::warn!(%symbol, ?regime.level, depth_ratio, jump_bps, "regime L3 pause — cancel all");
            continue;
        }

        if risk.should_kill(&regime_engine) {
            if let Some(r) = &rest {
                let _ = r.cancel_all(&symbol).await;
            }
            oms.live.clear();
            tracing::warn!(%symbol, reject_count = risk.reject_count, "risk kill — cancel all");
            if risk.halt {
                break;
            }
            continue;
        }

        if vol_tracker.sample_count() < warm_samples {
            continue;
        }

        let markout_extra_bid = markout_rt
            .guard
            .lock()
            .map(|g| g.extra_spread_bid_bps())
            .unwrap_or(0.0);
        let markout_extra_ask = markout_rt
            .guard
            .lock()
            .map(|g| g.extra_spread_ask_bps())
            .unwrap_or(0.0);
        let rolling_adverse = markout_rt
            .guard
            .lock()
            .map(|g| g.rolling_adverse_bps())
            .unwrap_or(0.0);

        let mut plan = compute_quote_cex(
            &cfg,
            fair_native,
            tick,
            inventory,
            max_inv,
            base_qty,
            vol_bps,
            kappa,
            markout_extra_bid,
            markout_extra_ask,
            rolling_adverse,
            last_fair,
            Some(top),
            ext,
        )
        .map_err(|e| anyhow::anyhow!(e))?;
        // The side that adds to the position only quotes the room left under the cap, by both the bot's and
        // the venue's last position (whichever leaves less). No room switches the side off, so
        // needs_update_sides pulls any order still resting there.
        let size = |side_is_sell: bool| {
            let q = side_order_qty(inventory, side_is_sell, plan.order_qty, min_qty, clip_cap, step);
            match last_venue_pos {
                Some(v) => q.min(side_order_qty(v, side_is_sell, plan.order_qty, min_qty, clip_cap, step)),
                None => q,
            }
        };
        let bid_qty = size(false);
        let ask_qty = size(true);
        if bid_qty <= 0.0 {
            plan.place_bid = false;
        }
        if ask_qty <= 0.0 {
            plan.place_ask = false;
        }
        if let Some(w) = anchor_watch.as_mut() {
            let health = w.check(anchor_fair.is_some(), Instant::now());
            match health {
                FeedHealth::WentDown(d) => tracing::warn!(
                    %symbol,
                    off_s = d.as_secs_f64(),
                    reason = anchor_off_reason.unwrap_or("none"),
                    "anchor off; quotes pulled until it is back"
                ),
                FeedHealth::Recovered(d) => tracing::info!(%symbol, off_s = d.as_secs_f64(), "anchor on; quoting"),
                FeedHealth::Up | FeedHealth::Down => {}
            }
            if matches!(health, FeedHealth::WentDown(_) | FeedHealth::Down) {
                plan.place_bid = false;
                plan.place_ask = false;
            }
        }
        let feed_state = fill_feed.as_ref().map(|f| {
            let s = f.borrow();
            (s.subscribed, s.fills, s.last_error.clone())
        });
        if let (Some(w), Some((up, _, why))) = (feed_watch.as_mut(), &feed_state) {
            let health = w.check(*up, Instant::now());
            match health {
                FeedHealth::WentDown(d) => tracing::warn!(
                    %symbol,
                    down_s = d.as_secs_f64(),
                    reason = why.as_deref().unwrap_or("none given"),
                    "fills feed down; adding side off until the venue confirms it again"
                ),
                FeedHealth::Recovered(d) => {
                    tracing::info!(%symbol, down_s = d.as_secs_f64(), "fills feed back; adding side on")
                }
                FeedHealth::Up | FeedHealth::Down => {}
            }
            if matches!(health, FeedHealth::WentDown(_) | FeedHealth::Down) {
                // A side is pulled when it adds by either reading of the position; flat pulls both.
                let venue = last_venue_pos.unwrap_or(inventory);
                if adds_to_position(inventory, false) || adds_to_position(venue, false) {
                    plan.place_bid = false;
                }
                if adds_to_position(inventory, true) || adds_to_position(venue, true) {
                    plan.place_ask = false;
                }
            }
        }

        let tol_bps = env_f64_for_symbol(&symbol, "MM_REQUOTE_TOL_BPS", 3.0);

        let venue_mid = (plan.bid + plan.ask) / 2.0;
        let lead_skew_bps = if binance_mid > 0.0 {
            Some((plan.fair - binance_mid) / binance_mid * 10_000.0)
        } else {
            None
        };
        let metrics = MmMetrics {
            symbol: symbol.clone(),
            fair: plan.fair,
            reservation: plan.reservation,
            bid: plan.bid,
            ask: plan.ask,
            spread_bps: plan.spread_bps,
            vol_bps: plan.vol_bps,
            inventory,
            effective_kappa: plan.effective_kappa,
            markout_extra_bid_bps: markout_extra_bid,
            markout_extra_ask_bps: markout_extra_ask,
            regime_level: regime.level.as_u8(),
            ofi: ofi.window_ofi(),
            ofi_beta,
            alpha_mu_bps,
            snipe_rate: snipe.lock().map(|s| s.rate()).unwrap_or(0.0),
            place_bid: plan.place_bid,
            place_ask: plan.place_ask,
            binance_mid: if binance_mid > 0.0 { Some(binance_mid) } else { None },
            venue_mid,
            lead_skew_bps,
            rolling_adverse_bps: rolling_adverse,
            ts_ms: Utc::now().timestamp_millis(),
            book_bid: top.best_bid,
            book_ask: top.best_ask,
            book_bid_qty: top.bid_qty,
            book_ask_qty: top.ask_qty,
            book_age_ms: book_watch.age_ms(Instant::now()),
            fair_delta: mm_core::quote_fair(&cfg, fair_native, Some(top), QuoteExtensions { anchor_fair: None, ..ext }),
            basis_bps: basis.value_bps(),
            anchored: anchor_fair.is_some(),
            binance_age_ms: binance_msg_at.map(|t| t.elapsed().as_millis() as u64),
            mark_price: ticker.as_ref().and_then(|t| t.mark_price),
            spot_price: ticker.as_ref().and_then(|t| t.spot_price),
            ticker_age_ms: ticker.as_ref().map(|t| t.received_at.elapsed().as_millis() as u64),
            fills_feed_up: feed_state.as_ref().map(|s| s.0),
            fills_feed_fills: feed_state.as_ref().map(|s| s.1),
            binance_bid: (bbo.bid > 0.0).then_some(bbo.bid),
            binance_ask: (bbo.ask > 0.0).then_some(bbo.ask),
            binance_bid_qty: bbo.bid_qty,
            binance_ask_qty: bbo.ask_qty,
            depth_mid: depth_ok.and_then(|s| s.mid()).map(|d| sig10(d.mid)),
            depth_bid_px: depth_bid.map(|s| s.price),
            depth_ask_px: depth_ask.map(|s| s.price),
            depth_bid_lvl: depth_bid.map(|s| s.level as u32),
            depth_ask_lvl: depth_ask.map(|s| s.level as u32),
            depth_bid_inner: depth_bid.map(|s| sig10(s.inner_size)),
            depth_ask_inner: depth_ask.map(|s| sig10(s.inner_size)),
            depth_bid_inner_px: depth_bid.and_then(|s| s.inner_px),
            depth_ask_inner_px: depth_ask.and_then(|s| s.inner_px),
            depth_bid_nlvl: depth_snap.map(|d| d.bids.len() as u32),
            depth_ask_nlvl: depth_snap.map(|d| d.asks.len() as u32),
            depth_qty: depth.as_ref().and(depth_qty).map(|q| (q * 100.0).round() / 100.0),
            depth_age_ms: depth_snap.map(|d| d.received_at.elapsed().as_millis() as u64),
            depth_ts_us: depth_snap.and_then(|d| d.venue_ts_us),
            depth_none: depth_read.as_ref().and_then(|r| match r {
                Err(e) => Some(e.clone()),
                Ok(sides) => mm_core::depth::side_reasons(sides),
            }),
            basis_src: Some(basis_source.as_str()),
            basis_updated: Some(basis_updated),
            anchor_off_reason,
            basis_t: Some(lead_now),
            basis_n: Some(basis.samples()),
            loop_work_ms,
        };
        tracing::info!(target: "MM_METRICS", "{}", serde_json::to_string(&metrics)?);

        if dry_run {
            continue;
        }

        let Some(r) = &rest else { continue };

        if should_taker_flatten(inventory, max_inv, base_qty) {
            let _ = r.cancel_all(&symbol).await;
            oms.live.clear();
            if last_reduce_only.elapsed() >= Duration::from_secs(2) {
                if let Some(clip) = hard_cap_reduce(inventory, max_inv, base_qty, min_qty) {
                    let price = if clip.side.eq_ignore_ascii_case("sell") {
                        top.best_bid
                    } else {
                        top.best_ask
                    };
                    if price > 0.0 {
                        last_reduce_only = Instant::now();
                        if let Some(a) = &account {
                            a.note_reduce_only();
                        }
                        tracing::warn!(
                            %symbol,
                            side = clip.side,
                            qty = clip.qty,
                            inventory,
                            "inventory hard cap — reduce-only"
                        );
                        let link = format!("mm-{symbol}-red-{}", Utc::now().timestamp_millis());
                        match r
                            .place_reduce_only(&symbol, clip.side, clip.qty, price, &link)
                            .await
                        {
                            Ok(()) => {
                                crate::oems::post_order(
                                    &link,
                                    &symbol,
                                    clip.side,
                                    price,
                                    clip.qty,
                                    true,
                                    None,
                                );
                                tracing::info!(
                                    target: "MM_ORDER",
                                    symbol = %symbol,
                                    side = clip.side,
                                    qty = clip.qty,
                                    price,
                                    "reduce-only"
                                );
                            }
                            Err(e) => {
                                let msg = format!("{e:#}");
                                crate::oems::post_order(
                                    &link,
                                    &symbol,
                                    clip.side,
                                    price,
                                    clip.qty,
                                    true,
                                    Some(&msg),
                                );
                                tracing::warn!(
                                    target: "MM_REJECT",
                                    symbol = %symbol,
                                    side = clip.side,
                                    qty = clip.qty,
                                    err = %msg,
                                    "reduce-only place failed"
                                );
                                if counts_toward_reject_kill(&msg) {
                                    risk.reject_count += 1;
                                }
                            }
                        }
                    }
                }
            }
            continue;
        }

        // An order the venue may hold under an id we do not know (a place with no answer) is cancelled at once,
        // not when a quote next has to move: on 22 Oct 2026 one waited 9.6 s for that, and a cancel-all takes
        // Delta about 17 ms. Forget nothing the venue may still hold: retry next loop if the cancel-all fails.
        // After the clear, both sides need an update and are quoted again below.
        let edits_by_id = r.cancel_before_requote();
        if edits_by_id && oms.live.has_untracked() {
            if let Err(e) = r.cancel_all(&symbol).await {
                tracing::warn!(%symbol, error = %e, "cancel-all for an order without an id failed; retrying next loop");
                continue;
            }
            oms.live.clear();
        }

        let (need_bid, need_ask) = oms.needs_update_sides(plan.bid, plan.ask, plan.place_bid, plan.place_ask, tol_bps);
        if !need_bid && !need_ask {
            continue;
        }
        if !oms.budget.allow() {
            continue;
        }

        let mut need_bid = need_bid;
        let mut need_ask = need_ask;

        let ts = Utc::now().timestamp_millis();
        let queue_front_frac = env_f64_for_symbol(&symbol, "MM_QUEUE_MAX_FRONT_FRAC", 0.9);
        let bid_px = place_price(QuoteSide::Bid, plan.bid, inventory < 0.0, top.best_bid, top.best_ask, top.bid_qty, bid_qty, tick, queue_front_frac);
        let ask_px = place_price(QuoteSide::Ask, plan.ask, inventory > 0.0, top.best_bid, top.best_ask, top.ask_qty, ask_qty, tick, queue_front_frac);
        let bid = SideOrder { side: QuoteSide::Bid, quoted: plan.place_bid, target: plan.bid, qty: bid_qty, link: format!("mm-{symbol}-bid-{ts}") };
        let ask = SideOrder { side: QuoteSide::Ask, quoted: plan.place_ask, target: plan.ask, qty: ask_qty, link: format!("mm-{symbol}-ask-{ts}") };

        // Both sides' first calls at once; then the fallbacks of failed ones, one after the other (`FirstCall`).
        let bid_call = first_call(need_bid, oms.live.bid_id, plan.place_bid, top.best_ask > 0.0 && plan.bid >= top.best_ask, edits_by_id, bid_px);
        let ask_call = first_call(need_ask, oms.live.ask_id, plan.place_ask, top.best_bid > 0.0 && plan.ask <= top.best_bid, edits_by_id, ask_px);
        let (bid_answer, ask_answer) =
            tokio::join!(first_venue_call(r, &symbol, bid_call, &bid), first_venue_call(r, &symbol, ask_call, &ask));
        let bid_fallback = book_answer(r, &symbol, &mut oms.live, &mut risk, &bid, bid_call, bid_answer, contract_value, &mut need_bid);
        let ask_fallback = book_answer(r, &symbol, &mut oms.live, &mut risk, &ask, ask_call, ask_answer, contract_value, &mut need_ask);
        let (bid_held, ask_held) = (oms.live.bid_id, oms.live.ask_id);
        if let Some(f) = bid_fallback {
            run_fallback(r, &symbol, &mut oms.live, &bid, f, &mut need_bid).await;
        } else if bid_held.is_some() && oms.live.bid_id.is_none() {
            // The ask's fallback cancelled all, the bid too: quote it again below.
            need_bid = plan.place_bid;
        }
        if let Some(f) = ask_fallback {
            run_fallback(r, &symbol, &mut oms.live, &ask, f, &mut need_ask).await;
        } else if ask_held.is_some() && oms.live.ask_id.is_none() {
            need_ask = plan.place_ask;
        }

        // Sides still to place: pulled because the old price crossed the book, a failed edit, or a cancel-all.
        // A fill can land while the first calls are in flight (a failed edit is often that fill), so the size is
        // clipped again by the position now: the fills feed has updated it by the time the fallbacks answer.
        let inventory_now = economics_arc.lock().map(|e| e.position).unwrap_or(inventory);
        let resize = |o: &SideOrder| {
            let side_is_sell = o.side == QuoteSide::Ask;
            let q = requote_qty(o.qty, inventory_now, side_is_sell, min_qty, clip_cap, step);
            match last_venue_pos {
                Some(v) => q.min(requote_qty(o.qty, v, side_is_sell, min_qty, clip_cap, step)),
                None => q,
            }
        };
        let bid = SideOrder { qty: resize(&bid), ..bid };
        let ask = SideOrder { qty: resize(&ask), ..ask };
        let bid_call = if need_bid && plan.place_bid && oms.live.bid.is_none() && bid.qty > 0.0 {
            bid_px.map_or(FirstCall::Nothing, FirstCall::Place)
        } else {
            FirstCall::Nothing
        };
        let ask_call = if need_ask && plan.place_ask && oms.live.ask.is_none() && ask.qty > 0.0 {
            ask_px.map_or(FirstCall::Nothing, FirstCall::Place)
        } else {
            FirstCall::Nothing
        };
        let (bid_answer, ask_answer) =
            tokio::join!(first_venue_call(r, &symbol, bid_call, &bid), first_venue_call(r, &symbol, ask_call, &ask));
        book_answer(r, &symbol, &mut oms.live, &mut risk, &bid, bid_call, bid_answer, contract_value, &mut need_bid);
        book_answer(r, &symbol, &mut oms.live, &mut risk, &ask, ask_call, ask_answer, contract_value, &mut need_ask);
    }
    Ok(())
}

/// One side of a requote: whether the plan quotes it, at what price and size, and the client id of a new order.
struct SideOrder {
    side: QuoteSide,
    quoted: bool,
    target: f64,
    qty: f64,
    link: String,
}

impl SideOrder {
    fn venue_side(&self) -> &'static str {
        match self.side {
            QuoteSide::Bid => "Buy",
            QuoteSide::Ask => "Sell",
        }
    }

    fn log_side(&self) -> &'static str {
        match self.side {
            QuoteSide::Bid => "buy",
            QuoteSide::Ask => "sell",
        }
    }
}

/// A venue call's answer and how long it took (ms).
struct Answered {
    result: Result<Option<u64>>,
    ms: u64,
}

/// What a side still has to do after its first call, once both sides have answered.
enum Fallback {
    /// The edit failed (the order filled or is gone, or the venue refused): pull the quote.
    PullAfterEdit(u64),
    /// The cancel's answer: a failed cancel asks the venue before the quote is forgotten.
    AfterCancel(u64, Result<()>),
}

async fn first_venue_call(r: &QuotingRest, symbol: &str, call: FirstCall, order: &SideOrder) -> Option<Answered> {
    let started = Instant::now();
    let result = match call {
        FirstCall::Nothing => return None,
        FirstCall::Pull(id) => r.cancel_order(symbol, id).await.map(|()| None),
        FirstCall::Edit(id) => r.edit_post_only(symbol, id, order.qty, order.target).await.map(|()| None),
        FirstCall::Place(price) => r.place_limit_post_only(symbol, order.venue_side(), order.qty, price, &order.link).await,
    };
    Some(Answered { result, ms: started.elapsed().as_millis() as u64 })
}

/// Books one side's answer in `live` and returns what the side still has to do. A place's answer is final: an
/// accepted order is tracked, a refusal counts toward the reject kill, and a place with no answer is tracked
/// without an id so the next loop cancels all (`LiveQuotes::track_without_id`).
#[allow(clippy::too_many_arguments)]
fn book_answer(
    r: &QuotingRest,
    symbol: &str,
    live: &mut LiveQuotes,
    risk: &mut crate::risk::RiskState,
    order: &SideOrder,
    call: FirstCall,
    answer: Option<Answered>,
    contract_value: f64,
    need: &mut bool,
) -> Option<Fallback> {
    let answer = answer?;
    let side = order.log_side();
    let ms = answer.ms;
    match call {
        FirstCall::Nothing => None,
        FirstCall::Pull(id) => Some(Fallback::AfterCancel(id, answer.result.map(|_| ()))),
        FirstCall::Edit(id) => {
            if answer.result.is_err() {
                return Some(Fallback::PullAfterEdit(id));
            }
            let left = match order.side {
                QuoteSide::Bid => {
                    live.bid = Some(order.target);
                    live.bid_left
                }
                QuoteSide::Ask => {
                    live.ask = Some(order.target);
                    live.ask_left
                }
            };
            live.set_left(order.side, left_after_edit(left, contracts_of(order.qty, contract_value)));
            *need = false;
            tracing::info!(target: "MM_ORDER", %symbol, side, price = order.target, qty = order.qty, ms, "edited post-only");
            None
        }
        FirstCall::Place(price) => {
            *need = false;
            match answer.result {
                Ok(id) => {
                    risk.reject_count = risk.reject_count.saturating_sub(2);
                    match order.side {
                        QuoteSide::Bid => {
                            live.bid = Some(price);
                            live.bid_id = id;
                        }
                        QuoteSide::Ask => {
                            live.ask = Some(price);
                            live.ask_id = id;
                        }
                    }
                    live.set_left(order.side, contracts_of(order.qty, contract_value));
                    crate::oems::post_order(&order.link, symbol, side, price, order.qty, false, None);
                    tracing::info!(target: "MM_ORDER", %symbol, side, price, qty = order.qty, ms, "placed post-only");
                }
                Err(e) if r.outcome_unknown(&e) => {
                    let msg = format!("{e:#}");
                    live.track_without_id(order.side, price);
                    crate::oems::post_order(&order.link, symbol, side, price, order.qty, false, Some(&format!("no answer: {msg}")));
                    tracing::warn!(%symbol, side, price, qty = order.qty, ms, error = %msg, "no answer to the place: the order may rest, so the next loop cancels all before quoting again");
                }
                Err(e) => {
                    let msg = format!("{e:#}");
                    crate::oems::post_order(&order.link, symbol, side, price, order.qty, false, Some(&msg));
                    tracing::warn!(target: "MM_REJECT", symbol = %symbol, side, price, qty = order.qty, err = %msg, ms, "post-only reject");
                    if counts_toward_reject_kill(&msg) {
                        risk.reject_count += 1;
                    }
                }
            }
            None
        }
    }
}

/// A side switched off is done once its pull has run, whatever came of it; a side the plan quotes is placed
/// again only once its old order is gone.
async fn run_fallback(r: &QuotingRest, symbol: &str, live: &mut LiveQuotes, order: &SideOrder, fallback: Fallback, need: &mut bool) {
    let cleared = match fallback {
        Fallback::PullAfterEdit(id) => pull_quote(r, symbol, live, order.side, id).await,
        Fallback::AfterCancel(id, cancel) => after_cancel(r, symbol, live, order.side, id, cancel).await,
    };
    if !order.quoted || !cleared {
        *need = false;
    }
}

fn handle_delta_fill_row(
    row: &serde_json::Value,
    products: &mm_delta::ProductCatalog,
    mm_symbol: &str,
    eco: &Arc<Mutex<FillEconomics>>,
    markout: &MarkoutRuntime,
    econ_path: &PathBuf,
    snipe: &Arc<Mutex<SnipeTracker>>,
    last_jump: &Arc<Mutex<Option<Instant>>>,
) -> Option<mm_delta::UserTrade> {
    // Delta sends the size as a string and `i` is the product id: before 15 Oct 2026 this read a size of 0
    // and used one id per product, so the OEMS (unique on trade id) kept only the first fill.
    let Some(fill) = mm_delta::parse_user_trade(row) else {
        tracing::warn!(symbol = %mm_symbol, frame = %row.to_string().chars().take(300).collect::<String>(), "fill frame not understood; skipped (the reconcile will catch the position)");
        return None;
    };
    let qty = products.base_qty_from_contracts(mm_symbol, fill.contracts);
    let price = fill.price;
    let bought = fill.bought;
    tracing::info!(
        symbol = %mm_symbol,
        side = if bought { "buy" } else { "sell" },
        contracts = fill.contracts,
        price,
        maker = fill.maker,
        fill_id = %fill.fill_id,
        order_id = ?fill.order_id,
        "fill from the private feed"
    );
    if let Ok(mut e) = eco.lock() {
        e.on_fill(bought, qty, price, 0.0);
        let _ = persist_economics(econ_path, &e);
    }
    let fair_at_fill = *markout.fair_rx.borrow();
    markout.on_fill(bought, fair_at_fill);
    let fill_side = if bought { "buy" } else { "sell" };
    let mid = if fair_at_fill > 0.0 { fair_at_fill } else { price };
    crate::oems::post_fill(
        &fill.fill_id,
        fill.client_order_id.as_deref(),
        mm_symbol,
        fill_side,
        price,
        qty,
        0.0,
        price,
        mid,
        mid,
    );
    let ms = last_jump
        .lock()
        .ok()
        .and_then(|j| j.map(|t| t.elapsed().as_millis() as u64))
        .unwrap_or(u64::MAX);
    if let Ok(mut s) = snipe.lock() {
        s.record_fill(ms);
    }
    Some(fill)
}

/// Asks the venue about a quote the fills say is done and settles it (`LiveQuotes::settle`).
async fn settle_with_venue(rest: Option<&QuotingRest>, symbol: &str, live: &mut LiveQuotes, side: QuoteSide, order_id: u64) {
    let since = live.done_at(side);
    let venue = match rest {
        Some(r) => r.order_state(order_id).await,
        None => Err(anyhow::anyhow!("no REST client")),
    };
    let answer = venue.as_ref().ok().map(|(state, unfilled)| (state.as_str(), *unfilled));
    let now = Instant::now();
    let waited_ms = since.map_or(0, |t| now.saturating_duration_since(t).as_millis() as u64);
    match live.settle(side, order_id, answer, now, SETTLE_PATIENCE) {
        Settled::Cleared => {
            tracing::info!(%symbol, ?side, order_id, waited_ms, "venue shows the filled quote closed; quoting the side again");
        }
        Settled::Waiting => {
            tracing::debug!(%symbol, ?side, order_id, waited_ms, venue = ?answer, "venue does not show the filled quote closed yet; asking again next loop");
        }
        Settled::Resynced { left } => {
            tracing::warn!(%symbol, ?side, order_id, waited_ms, left, "venue still shows the quote open; its unfilled size is the remainder now");
        }
        Settled::GaveUp => {
            let error = venue.as_ref().err().map(|e| format!("{e:#}"));
            tracing::warn!(%symbol, ?side, order_id, waited_ms, venue = ?answer, ?error, "no usable answer on the filled quote; it stays tracked until the requote path checks it");
        }
        Settled::Moved => {}
    }
}

/// Cancels one resting quote and forgets it once it is gone. A failed cancel asks the venue: closed or
/// cancelled (it filled meanwhile) counts as gone. Otherwise a cancel-all clears the symbol and both sides are
/// forgotten. If that fails too, the quote stays tracked and the next loop tries again: forgetting an order
/// that may still rest would put a second quote beside it. Returns whether `side` is now clear.
async fn pull_quote(r: &QuotingRest, symbol: &str, live: &mut LiveQuotes, side: QuoteSide, id: u64) -> bool {
    let cancel = r.cancel_order(symbol, id).await;
    after_cancel(r, symbol, live, side, id, cancel).await
}

/// `pull_quote` from the cancel's answer on: a cancel the requote sent beside the other side's call.
async fn after_cancel(r: &QuotingRest, symbol: &str, live: &mut LiveQuotes, side: QuoteSide, id: u64, cancel: Result<()>) -> bool {
    let Err(cancel_err) = cancel else {
        live.clear_side(side);
        return true;
    };
    let state = r.order_state(id).await;
    let answer = state.as_ref().ok().map(|(s, _)| s.as_str());
    if gone_after_cancel(false, answer) {
        live.clear_side(side);
        return true;
    }
    tracing::warn!(%symbol, ?side, order_id = id, error = %cancel_err, venue_state = ?answer, "cancel failed and the venue does not say the quote is gone; cancelling all");
    match r.cancel_all(symbol).await {
        Ok(()) => {
            live.clear();
            true
        }
        Err(e) => {
            tracing::warn!(%symbol, error = %e, "cancel-all failed too; the quote stays tracked and the next loop retries");
            false
        }
    }
}

fn handle_execution_row(
    row: &serde_json::Value,
    eco: &Arc<Mutex<FillEconomics>>,
    markout: &MarkoutRuntime,
    econ_path: &PathBuf,
    snipe: &Arc<Mutex<SnipeTracker>>,
    last_jump: &Arc<Mutex<Option<Instant>>>,
) {
    let side = row.get("side").and_then(|s| s.as_str()).unwrap_or("");
    let qty: f64 = row
        .get("execQty")
        .and_then(|s| s.as_str())
        .unwrap_or("0")
        .parse()
        .unwrap_or(0.0);
    let price: f64 = row
        .get("execPrice")
        .and_then(|s| s.as_str())
        .unwrap_or("0")
        .parse()
        .unwrap_or(0.0);
    let fee: f64 = row
        .get("execFee")
        .and_then(|s| s.as_str())
        .unwrap_or("0")
        .parse()
        .unwrap_or(0.0);
    let bought = side.eq_ignore_ascii_case("Buy");
    if let Ok(mut e) = eco.lock() {
        e.on_fill(bought, qty, price, fee);
        let _ = persist_economics(econ_path, &e);
    }
    let fair_at_fill = *markout.fair_rx.borrow();
    markout.on_fill(bought, fair_at_fill);
    let trade_id = row
        .get("execId")
        .or_else(|| row.get("orderId"))
        .map(|v| match v {
            serde_json::Value::String(s) => s.clone(),
            serde_json::Value::Number(n) => n.to_string(),
            _ => format!("bybit-{}", Utc::now().timestamp_millis()),
        })
        .unwrap_or_else(|| format!("bybit-{}", Utc::now().timestamp_millis()));
    let fill_side = if bought { "buy" } else { "sell" };
    let mid = if fair_at_fill > 0.0 { fair_at_fill } else { price };
    let link = row
        .get("orderLinkId")
        .and_then(|s| s.as_str());
    crate::oems::post_fill(
        &trade_id,
        link,
        row.get("symbol").and_then(|s| s.as_str()).unwrap_or(""),
        fill_side,
        price,
        qty,
        fee,
        price,
        mid,
        mid,
    );
    let ms = last_jump
        .lock()
        .ok()
        .and_then(|j| j.map(|t| t.elapsed().as_millis() as u64))
        .unwrap_or(u64::MAX);
    if let Ok(mut s) = snipe.lock() {
        s.record_fill(ms);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn a_live_start_waits_for_the_fills_feed() {
        let (tx, rx) = watch::channel(mm_delta::PrivateFeedState::default());
        tokio::spawn(async move {
            tokio::time::sleep(Duration::from_millis(50)).await;
            tx.send_modify(|s| s.subscribed = true);
            tokio::time::sleep(Duration::from_secs(5)).await; // keep the sender alive
        });
        require_fill_feed(rx, Duration::from_secs(2), true).await.expect("confirmed in time");
    }

    #[tokio::test]
    async fn a_live_start_refuses_without_the_fills_feed_and_says_why() {
        let (tx, rx) = watch::channel(mm_delta::PrivateFeedState::default());
        tx.send_modify(|s| {
            s.last_error = Some("subscription refused: subscription forbidden on this channel. Unauthorized user".into())
        });
        let err = require_fill_feed(rx, Duration::from_millis(100), true).await.unwrap_err().to_string();
        assert!(err.contains("Unauthorized user"), "{err}");
        assert!(err.contains("MM_FILL_FEED_REQUIRED=0"), "{err}");
        drop(tx);
    }

    #[test]
    fn a_cap_below_one_lot_disables_the_clip_in_a_dry_run_and_refuses_a_live_run() {
        assert_eq!(size_clip_cap("ADAUSDT", 600.0, 1.0, false).unwrap(), 600.0);
        assert_eq!(size_clip_cap("ADAUSDT", 0.0, 1.0, false).unwrap(), 0.0); // no cap configured
        // KITE in the shadow: the 0.01 default against a 1-contract lot (100 KITE).
        assert_eq!(size_clip_cap("KITEUSDT", 0.01, 100.0, true).unwrap(), 0.0);
        let err = size_clip_cap("KITEUSDT", 0.01, 100.0, false).unwrap_err().to_string();
        assert!(err.contains("MM_MAX_INVENTORY_KITEUSDT"), "{err}");
        assert!(size_clip_cap("ADAUSDT", f64::NAN, 1.0, false).is_err());
    }

    #[tokio::test]
    async fn repeated_refusals_end_the_wait_early() {
        let (tx, rx) = watch::channel(mm_delta::PrivateFeedState::default());
        tokio::spawn(async move {
            for _ in 0..2 {
                tokio::time::sleep(Duration::from_millis(20)).await;
                tx.send_modify(|s| {
                    s.refusals += 1;
                    s.last_error = Some("login refused: {\"success\":false}".into());
                });
            }
            tokio::time::sleep(Duration::from_secs(30)).await; // keep the sender alive
        });
        let started = Instant::now();
        let err = require_fill_feed(rx, Duration::from_secs(20), true).await.unwrap_err().to_string();
        assert!(started.elapsed() < Duration::from_secs(2), "waited {:?}", started.elapsed());
        assert!(err.contains("refused 2 times"), "{err}");
        assert!(err.contains("login refused"), "{err}");
    }

    #[tokio::test]
    async fn a_timeout_reports_the_wait_to_a_tenth_of_a_second() {
        let (_tx, rx) = watch::channel(mm_delta::PrivateFeedState::default());
        let err = require_fill_feed(rx, Duration::from_millis(150), true).await.unwrap_err().to_string();
        assert!(err.contains("not confirmed within 0.1 s (no reply from the venue)"), "{err}");
    }

    #[test]
    fn an_anchored_depth_source_needs_a_usable_depth_book() {
        use BasisSource::{Book, Depth};
        let ok = |s, w, feed, q, x, b| depth_source_check("ADAUSDT", s, w, feed, q, x, b).is_ok();
        assert!(ok(Depth, 1.0, true, Some(10_000.0), 10_000.0, 200.0));
        // Feed off, an unusable threshold, or X <= 2Q: refused only when the depth source is anchored.
        assert!(!ok(Depth, 1.0, false, None, 10_000.0, 200.0));
        assert!(!ok(Depth, 1.0, true, None, 0.0, 200.0));
        assert!(!ok(Depth, 1.0, true, Some(400.0), 400.0, 200.0));
        assert!(ok(Depth, 0.0, true, Some(400.0), 400.0, 200.0)); // logged only
        assert!(ok(Book, 1.0, true, Some(400.0), 400.0, 200.0)); // logged only
        assert!(ok(Book, 1.0, false, None, 10_000.0, 200.0)); // no depth at all is fine for the book source
        let err = depth_source_check("ADAUSDT", Depth, 1.0, true, Some(400.0), 400.0, 200.0).unwrap_err().to_string();
        assert!(err.starts_with("ADAUSDT: MM_BASIS_DEPTH_QTY=400 is not above twice the order size 200"), "{err}");
    }

    #[test]
    fn logged_values_lose_their_float_noise() {
        assert_eq!(sig10((0.23200 + 0.23230) / 2.0).to_string(), "0.23215");
        assert_eq!(sig10(8614.933988068316), 8614.933988);
        assert_eq!(sig10(47_081.0), 47_081.0);
        assert_eq!(sig10(0.0), 0.0);
        assert!(sig10(f64::NAN).is_nan());
        assert_eq!(sig10(1e-300), 1e-300); // the scale overflows; the value is kept as is
    }

    #[test]
    fn duration_knobs_never_panic() {
        assert_eq!(secs_knob(20.0, 20.0, 1.0, 600.0), Duration::from_secs(20));
        assert_eq!(secs_knob(f64::INFINITY, 20.0, 1.0, 600.0), Duration::from_secs(20));
        assert_eq!(secs_knob(f64::NAN, 20.0, 1.0, 600.0), Duration::from_secs(20));
        assert_eq!(secs_knob(-5.0, 20.0, 1.0, 600.0), Duration::from_secs(1));
        assert_eq!(secs_knob(1e12, 20.0, 1.0, 600.0), Duration::from_secs(600));
        assert_eq!(secs_knob(0.25, 3.0, 0.5, 3600.0), Duration::from_millis(500));
    }

    #[tokio::test]
    async fn the_check_can_be_waived() {
        let (_tx, rx) = watch::channel(mm_delta::PrivateFeedState::default());
        require_fill_feed(rx, Duration::from_millis(50), false).await.expect("waived");
    }
}
