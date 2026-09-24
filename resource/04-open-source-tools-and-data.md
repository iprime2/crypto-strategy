# 04 — Open-source MM tools, backtesters and data sources (survey)

Date of survey: **2026-09-20**. Target venues: OKX / Binance / Bybit (spot + USDT perps).
Star counts, licenses and last-push dates were pulled from the GitHub REST API on the survey date
(`https://api.github.com/repos/<org>/<repo>`); package versions from PyPI. Items marked **[unverified]**
could not be confirmed from a primary source.

Legend for each tool: URL · language · license · stars / activity · what it does · MM-relevant features ·
strengths · weaknesses · what we can learn / reuse.

---

## A. Market-making bots / frameworks

### A.1 Hummingbot

- URL: https://github.com/hummingbot/hummingbot · docs: https://hummingbot.org
- Language: Python (hot paths in Cython `.pyx`) · License: Apache-2.0
- Stars/activity: **20,095 ★**, 4,949 forks, pushed 2026-09-20; PyPI `hummingbot 20260901` (monthly release cadence).
- What it does: full CEX/DEX bot client with ~50 connectors (spot: `binance`, `okx`, `bybit`, …; perps: `binance_perpetual`,
  `okx_perpetual`, `bybit_perpetual`, …), a CLI, V1 strategies and a V2 "controllers + executors" framework.
  (connector list from `hummingbot/connector/exchange/` and `hummingbot/connector/derivative/` in the repo.)

**V1 `pure_market_making` (PMM)** — `hummingbot/strategy/pure_market_making/pure_market_making.pyx`
- Quote construction (`c_create_base_proposal`): for level `i`, `bid = ref × (1 − bid_spread − i·order_level_spread)`,
  `ask = ref × (1 + ask_spread + i·order_level_spread)`, size `order_amount + i·order_level_amount`; reference price is
  mid/last/custom via `AssetPriceDelegate`. Spreads are **static percentages**, not derived from volatility or intensity.
- Modifier pipeline (in order): price band / moving price band / ping-pong → `c_apply_order_price_modifiers`
  (order optimization = "join the best bid/ask minus one tick", add transaction costs) → `c_apply_order_size_modifiers`
  (**inventory skew**) → budget constraint → filter takers → cancel/refresh.
- Inventory skew (`inventory_skew_calculator.pyx::c_calculate_bid_ask_ratios_from_base_asset_ratio`): a piecewise-linear
  ramp on the **base-asset value ratio** around `target_base_asset_ratio ± base_asset_range`; returns
  `bid_adjustment ∈ [0,2]`, `ask_adjustment = 2 − bid_adjustment`. It skews **sizes**, not prices.
- Order refresh: fixed `order_refresh_time` with `order_refresh_tolerance_pct` (don't cancel if the new price is within
  tolerance) and optional "hanging orders" (`hanging_orders_tracker.py`) that keep the unfilled side alive after one side fills.

**V1 `avellaneda_market_making`** — `hummingbot/strategy/avellaneda_market_making/avellaneda_market_making.pyx`
- `c_calculate_reservation_price_and_optimal_spread` (≈ L713–777):
  `q = (base_balance − q_target) / inventory`; `r = mid − q·γ·σ²·τ`;
  `spread = γ·σ²·τ + 2/γ · ln(1 + γ/κ)`; `bid = r − spread/2`, `ask = r + spread/2` (clamped inside best bid/ask).
  `τ` is `time_left/closing_time` for a finite horizon or `1` for the "infinite" mode.
- `eta` transformation (`c_apply_order_amount_eta_transformation`): sizes scaled by `exp(∓η·q)`.
- **A/κ estimation** — `hummingbot/strategy/__utils__/trailing_indicators/trading_intensity.pyx`: buckets each public
  trade by `|trade_px − mid_at_that_time|` (price distance), sums **volume** per distance bucket over `sampling_length`
  ticks, then fits `λ(δ) = a·exp(−b·δ)` with `scipy.optimize.curve_fit(method='dogbox')`. Zero-volume buckets are
  replaced by `1e-10` before the fit. Volatility is an `InstantVolatilityIndicator` on mid price.
- Note the differences vs. hftbacktest's GLFT calibration below: Hummingbot fits **volume** by distance and does not
  count "all depths shallower than the trade also would have filled".

**V2 framework** — `hummingbot/strategy_v2/` + `controllers/`
- `MarketMakingControllerBase.determine_executor_actions()` = `create_actions_proposal()` + `stop_actions_proposal()`.
  Each quote level is a `PositionExecutor` (entry limit order + triple-barrier TP/SL/time-limit). Levels are refreshed by
  `executors_to_refresh()` after `executor_refresh_time`, and `update_processed_data()` publishes `reference_price` and
  `spread_multiplier` (`hummingbot/strategy_v2/controllers/market_making_controller_base.py` L223–300).
- `controllers/market_making/pmm_simple.py`: spreads × constant multiplier around mid.
- `controllers/market_making/pmm_dynamic.py`: `spread_multiplier = NATR(candles)`; `reference_price = close × (1 +
  (0.5·zscore(MACD) + 0.5·sign(MACDh)) · NATR/2)` — i.e., a candle-driven trend shift of the reference price.
- `controllers/market_making/dman_maker_v2.py`: each level is a `DCAExecutor` (ladder of DCA orders) — closer to
  Passivbot-style grid/DCA than to a quoting engine.
- Executors available: `position_executor`, `dca_executor`, `grid_executor`, `order_executor`, `twap_executor`,
  `xemm_executor`, `arbitrage_executor`, `lp_executor` (`hummingbot/strategy_v2/executors/`).
- Connector architecture (`hummingbot/connector/exchange_py_base.py::ExchangePyBase`): every CEX connector implements
  `_create_web_assistants_factory`, `_create_order_book_data_source`, `_create_user_stream_data_source`, `_place_order`,
  `_place_cancel`; the base runs `_status_polling_loop` (REST reconciliation) and `_user_stream_event_listener` (private
  WS). OKX connector = `okx_exchange.py`, `okx_api_order_book_data_source.py`, `okx_api_user_stream_data_source.py`,
  `okx_auth.py`. Trading rules (tick/lot/min notional) are quantized centrally via `c_quantize_order_price/amount`.
- Backtesting: V2 backtests replay controllers against **OHLCV candles** (`BacktestingEngineBase`,
  `hummingbot/strategy_v2/backtesting/backtesting_engine_base.py`); Hummingbot's own docs say 1-minute candles allow at
  most one fill per minute, recommend 1-second candles (Binance spot only), and list queue position / book depth /
  latency as things the engine cannot model (https://condor.hummingbot.org/bots/backtesting).
- Strengths: battle-tested connectors incl. all three target venues (spot + perp), clean order-tracking / in-flight-order
  state machine, rate-limit handling, config UX. Weaknesses for us: Python event loop with 1s `tick()` granularity, no
  L2 replay backtester, MM logic is either static spreads (PMM) or a textbook A-S with a fragile intensity fit;
  controllers are built around per-level executors rather than a single quote-state reconciler.
- Reuse: connector auth/signing and WS user-stream handling for OKX/Bybit/Binance; `InFlightOrder` state machine;
  `hanging_orders_tracker.py` idea; `inventory_skew_calculator.pyx` as a simple size-skew baseline; trading-rule
  quantization.

### A.2 nautilus_trader

- URL: https://github.com/nautechsystems/nautilus_trader · docs: https://nautilustrader.io/docs/latest/
- Language: Rust core, Python API (PyO3) · License: LGPL-3.0 (contributions require CLA)
- Stars/activity: **29,195 ★**, 3,855 forks, pushed 2026-09-20; PyPI `nautilus_trader 1.231.0` (Python ≥3.12, <3.15);
  v2 release-candidate line in progress (README "Versioning and releases").
- What it does: event-driven, deterministic trading platform; the same strategy code runs in `BacktestEngine` and live
  `TradingNode`. Adapters marked *stable* for **Binance, Bybit, OKX** (plus BitMEX, Deribit, Hyperliquid, dYdX, Kraken,
  Coinbase, Databento, **Tardis** data provider, …) — README "Integrations" table.
- Backtesting with L2: `book_type=BookType.L2_MBP` (or `L3_MBO`) venues; order-book deltas can be loaded from Binance
  depth snapshot+diff CSVs (`examples/backtest/crypto_orderbook_imbalance.py`) or Bybit `ob500` archives
  (`BybitOrderBookDeltaDataLoader`, https://nautilustrader.io/docs/latest/tutorials/backtest_orderbook_bybit/).
- Fill simulation (https://nautilustrader.io/docs/latest/concepts/backtesting/fill-models/ and
  `/trade-execution/`): the matching engine treats the recorded book as immutable; with L2/L3 the book supplies price
  levels, `FillModel.prob_fill_on_limit` (default 1.0) decides whether a *touched-but-not-crossed* limit fills; with
  `trade_execution=True, queue_position=True` the engine snapshots same-side displayed size at acceptance and lets
  correct-side trades at that price reduce the queue ahead ("displayed-queue tracking"); `liquidity_consumption=True`
  tracks consumed size per level. No latency model comparable to hftbacktest's per-order latency replay is documented
  **[unverified: could not find an order-latency model in the backtest docs]**.
- MM examples: `examples/backtest/fx_market_maker_gbpusd_bars.py` (bar-based), `crypto_orderbook_imbalance.py` and
  `architect_ax_book_imbalance.py` (book-imbalance taker); no A-S/GLFT reference strategy in-tree.
- Strengths: production-grade live adapters for all three target venues, nanosecond event ordering, Redis-backed
  cache/persistence, Rust hot path, big community. Weaknesses: heavy (large build, LGPL), fill modelling is coarser than
  hftbacktest (probabilistic touch or displayed-queue only, no latency replay); learning curve; MM strategy layer is DIY.
- Reuse: adapter code for OKX/Bybit/Binance (Rust crates `crates/adapters/*`) as a reference for WS book maintenance
  (checksum/sequence handling) and order lifecycle; `OrderBook` API (`get_avg_px_for_quantity`, `simulate_fills`); the
  queue-tracking rules as a second opinion when validating our own fill model.

### A.3 hftbacktest (go-deep section)

- URL: https://github.com/nkaz001/hftbacktest · docs: https://hftbacktest.readthedocs.io/en/latest/
- Language: Rust (`hftbacktest/`, `connector/`, `collector/`), Python bindings via Numba-JIT (`py-hftbacktest/`)
- License: MIT · Stars/activity: **4,737 ★**, 911 forks, last push 2025-12-23 (activity slowed in 2026); PyPI
  `hftbacktest 2.4.4` (Python ≥3.11).
- What it does: tick-level market-replay backtester with **feed latency + order latency**, **queue-position models**,
  L2 (MBP) and L3 (MBO) book reconstruction, multi-asset, partial/no-partial fill exchanges, and a Rust live-trading
  layer (Binance Futures tested on testnet, Bybit "under development"; OKX and Hyperliquid on the roadmap —
  `connector/README.md`, `ROADMAP.md`).

**Architecture (from source)**
- `hftbacktest/src/backtest/proc/`: `local.rs` (your process), `nopartialfillexchange.rs`, `partialfillexchange.rs`,
  `l3_local.rs`, `l3_nopartialfillexchange.rs`. Local and exchange processors exchange messages with latency applied.
- `hftbacktest/src/backtest/models/latency.rs`: `ConstantLatency`, `IntpOrderLatency` (interpolates recorded
  `OrderLatencyRow {req_ts, exch_ts, resp_ts}` from a file → `intp_order_latency([...])`).
- `hftbacktest/src/backtest/models/queue.rs`: `RiskAdverseQueueModel` (queue advances only on trades at your price),
  `ProbQueueModel<P>` with `Probability` functions `PowerProbQueueFunc(n)` (`f(x)=x^n`, `p = f(back)/(f(back)+f(front))`),
  `LogProbQueueFunc` (`f(x)=log(1+x)`), variants `*Func2`/`*Func3`; `L3FIFOQueueModel` for MBO data. The doc-comments cite
  https://rigtorp.se/2013/06/08/estimating-order-queue-position.html and quant.SE #3782.
- `hftbacktest/src/backtest/models/fee.rs`: `TradingValueFeeModel`, `TradingQtyFeeModel`, `FlatPerTradeFeeModel` with
  `CommonFees`/`DirectionalFees` (negative maker fee = rebate).
- Typical asset config from the tutorials:
  `BacktestAsset().data([...npz]).initial_snapshot(...).linear_asset(1.0).intp_order_latency([...])
   .power_prob_queue_model(2.0).no_partial_fill_exchange().trading_value_fee_model(-0.00005, 0.0007)
   .tick_size(0.01).lot_size(0.001).roi_lb(0).roi_ub(3000)` (ROI-vector depth = fast array book in a price range).
- Strategy API (Numba `@njit`): `hbt.elapse(ns)`, `hbt.wait_next_feed()`, `hbt.depth(i)`, `hbt.last_trades(i)`,
  `hbt.orders(i)`, `hbt.submit_buy_order(asset, id, px, qty, GTX, LIMIT, wait)`, `hbt.cancel(...)`,
  `hbt.wait_order_response(...)`, `hbt.clear_inactive_orders(...)`, `Recorder` + `LinearAssetRecord.stats()`.
- Data: normalized `event_dtype` npz with **both exchange and local timestamps**. Converters in
  `py-hftbacktest/hftbacktest/data/utils/`: `binancefutures.py` (own collector), `tardis.py` (`convert`, `convert_fuse`
  for trades+depth+bookTicker), `bybit.py`, `binancehistmktdata.py` / `bybithistmktdata.py` (official paid/official
  history dumps — docstring warns they lack local timestamps → no feed-latency info), `databento.py`, `hyperliquid.py`,
  `mexc.py`, `feed_order_latency.py`. The `collector/` Rust binary records raw WS for Binance spot/UM/CM, Bybit, Hyperliquid.

**Tutorials (all in `examples/*.ipynb`; rendered at readthedocs)**: Data Preparation, Getting Started, Working with
Market Depth and Trades, Making Multiple Markets (Intro + full), High-Frequency Grid Trading (+ "Comparison Across Other
Exchanges", + "Simplified from GLFT"), Impact of Order Latency, Order Latency Data, **GLFT Market Making Model and Grid
Trading**, Risk Mitigation through Price Protection, Level-3 Backtesting, Market Making with Alpha — Order Book Imbalance /
Basis / APT, **Queue-Based Market Making in Large Tick Size Assets**, Probability Queue Models, Fusing Depth Data,
Accelerated Backtesting, Pricing Framework.

**GLFT implementation (from `examples/GLFT Market Making Model and Grid Trading.ipynb`)**
- Model: Guéant–Lehalle–Fernandez-Tapia closed-form asymptotics (eqs. 4.6/4.7 of https://arxiv.org/abs/1605.01862),
  infinite horizon → suitable for perps. With `Δ=1`, `ξ=γ`:

  ```
  c1 = (1/(ξΔ)) · ln(1 + ξΔ/k)
  c2 = sqrt( γ / (2·A·Δ·k) · (1 + ξΔ/k)^(k/(ξΔ) + 1) )
  half_spread = c1 + (Δ/2)·σ·c2          # in ticks
  skew        = σ·c2                     # ticks per unit inventory
  bid = fair − (half_spread + skew·q),  ask = fair + (half_spread − skew·q)
  ```
  Implemented as `compute_coeff(xi, gamma, delta, A, k)`; tutorial uses `γ = 0.05`, then adds multipliers
  `adj1` (half-spread) and `adj2` (skew, set = 0.05) because the raw skew is "too strong". Fair price = mid (no alpha).
- **Estimating A and k** (`measure_trading_intensity_and_volatility`, `measure_trading_intensity`,
  `linear_regression`):
  1. Loop every **100 ms**. For each public trade since the last step, compute its depth from the *previous* mid in
     ticks: `buy → trade_px_tick − mid_tick`, `sell → mid_tick − trade_px_tick`; keep the **max depth per step**
     (`arrival_depth[t]`).
  2. Over a rolling window of 6,000 steps (=10 min), for each depth `d`, increment `out[:tick(d)]` — i.e. every quote
     depth **shallower** than the trade counts as executed (a quote at depth δ fills if a market order reaches ≥δ).
     Divide by 600 to get λ(δ) per second. (Note in the notebook: the tick index is in half-tick units; kept for
     reproducibility.)
  3. Fit `ln λ = ln A − k·δ` by ordinary least squares on the **shallow range only** (first 70 ticks) — the full-range
     exponential fit overestimates near the mid and underestimates far away.
  4. Refit A, k **every 5 s** (`t % 50 == 0`) once ≥10 min of history exists.
- **Estimating σ**: `volatility = nanstd(mid_price_chg over the 10-min window) · sqrt(10)` → ticks per √second
  (100 ms sampling ⇒ ×√10). Also refreshed every 5 s.
- Quoting loop: `reservation = mid_tick − skew·position`; `bid_tick = min(round(reservation − half_spread), best_bid)`,
  `ask_tick = max(round(reservation + half_spread), best_ask)` (never cross the touch); cancel resting orders whose
  price ≠ new price; submit `GTX` (post-only) with **order_id = price in ticks** so at most one order per level;
  `max_position = 20`, `order_qty = 1`.
- Grid variant (`gridtrading_glft_mm`): `grid_interval = max(round(half_spread)·tick, tick)`; floor/ceil the GLFT
  bid/ask onto the grid and place `grid_num = 20` levels per side; reconcile by cancelling anything not in the new grid
  dict and adding missing levels. The tutorial reports the grid variant works better (queue position accumulates on
  resting levels).
- Findings the author reports: single-level GLFT ≈ breakeven only with rebates; half-spread and skew co-move because
  both are driven by `c2·σ`; 5-day ETHUSDT/LTCUSDT runs profit mainly from maker rebates (−0.005% Binance LP tier).
- "Simplified from GLFT" tutorial: when λ(δ) is not exponential (common in **large-tick** pairs), drop A/k and drive
  half-spread and skew from σ alone (or use non-parametric mean/median/percentile of arrival depth); add BBO micro-price
  for large-tick assets.
- "Queue-Based MM in Large Tick Size Assets": book-pressure/micro-price + trade impulse; a pure queue rule — keep the
  quote while `qty_ahead`/level size stays above a threshold (`qty_threshold·(1 ± skew)`), react per feed event via
  `wait_next_feed` to dodge adverse selection. Cites https://arxiv.org/pdf/1207.6325 and
  https://blog.headlandstech.com/2017/08/.
- "Market Making with Alpha — OBI": static/standardised imbalance, VAMP (`(Pb·Qa + Pa·Qb)/(Qb+Qa)`), weighted-depth
  price; adds `a·forecast` to fair value. 2025 update: OBI still works but return/trade fell 0.0139% → 0.0086%
  including 0.005% rebate; `power_prob_queue_model` changed 2→3 to reflect harder fills.
- "Order Latency Data": if you don't have your own latency logs, generate order latency = `mult·feed_latency + offset`
  (entry and response separately); "Impact of Order Latency" shows PnL degradation at 4×/3× amplified latency. Best
  practice: record your own latencies by periodically posting/cancelling unfillable orders.
- Strengths: the only OSS backtester here that models latency + queue + partial fills on full-depth data, with concrete
  MM tutorials and a live path sharing the same code (Rust). Weaknesses: Python API requires Numba style; live
  connectors limited (Binance Futures/Bybit, no OKX, REST order entry only per roadmap), maintenance slowed since
  late 2025; data prep burden is high (you must collect or buy tick data with local timestamps).
- Reuse: GLFT calibration routines (`measure_trading_intensity`, `linear_regression`, `compute_coeff`), queue-model
  taxonomy in `models/queue.rs`, latency model + `feed_order_latency.py`, `collector/` for our own recording, Tardis
  converter, `LinearAssetRecord.stats` metrics, and the "order_id = price tick" reconciliation idiom.

### A.4 Passivbot

- URL: https://github.com/enarjord/passivbot · docs in-repo (`docs/`)
- Language: Python + Rust (`passivbot-rust` orchestrator via maturin) · License: **Unlicense** (public domain)
- Stars/activity: **2,106 ★**, 677 forks, pushed 2026-09-20; latest tag v8.1.0; Python 3.12/3.14.
- What it does: perpetual-futures "contrarian market maker" (README's words) — really a grid/DCA/martingale engine
  (`trailing_martingale`, `ema_anchor` strategies), a "Forager" that picks symbols by volume/volatility, an "unstucking"
  mechanism that realises small losses on stuck positions, plus a Rust backtester and evolutionary optimizer.
  Exchanges: Bybit, OKX, Bitget, Bitunix, GateIO, Binance, Kucoin, Hyperliquid, WEEX.
- MM-relevant: inventory handling (exposure limits, re-entry ladders, trailing closes), and a mature multi-exchange
  connector layer built on **CCXT**: `src/exchanges/ccxt_bot.py` base + per-venue subclasses (`okx.py`, `bybit.py`,
  `binance.py`, …). `okx.py` is a good checklist of OKX gotchas: detect `posMode` (`long_short_mode` vs `net_mode`) and
  `acctLv == "pm"` via `private_get_account_config`, cursor pagination of open orders with `after=<orderId>`, treat
  `sCode 51400` as "already cancelled/filled", error codes `59107/51039/51000/59000` on margin/position-mode changes,
  100 open-order cap (drops the farthest orders), `clOrdId` ≤ 32 chars with broker tag, `postOnly` param.
- Strengths: permissive license, actively maintained, real multi-venue perps experience. Weaknesses: candle-based
  (1m OHLCV) backtests, not a quoting engine (no spread/queue logic), directional exposure by design.
- Reuse: OKX/Bybit/Binance connector quirks and error-code handling; "unstuck" risk logic as a template for
  inventory-hard-stop rules; balance normalisation (`totalEq − upl` for OKX).

### A.5 Other credible MM repos (GitHub search, sorted by stars, 2026-09-20)

| Repo | Lang / License | ★ | Last push | What it is |
|---|---|---|---|---|
| https://github.com/ctubio/Krypto-trading-bot | C++ / ISC+MIT (paid "unlock" for the free-version handicap) | 3,715 | 2024-12 | "K": low-latency spot MM with web UI, quoting modes (PingPong, Boomerang, AK-47, HamelinRat), EWMA/STDEV quote protection, SQLite persistence; Coinbase, Binance, Kraken, KuCoin, BitMEX, … (no OKX/Bybit) |
| https://github.com/BitMEX/sample-market-maker | Python / Apache-2.0 | 1,716 | 2023-05 | Official BitMEX sample: `OrderManager.place_orders()` → `converge_orders()` (amend / create / cancel diff against desired quotes), position limits stop one side, WS-first data. Archetypal "desired-vs-live order reconciliation" |
| https://github.com/dennisyang1986/opensqt_market_maker | Go / none | 859 | 2026-04 | OpenSQT: WS-driven perps long-grid "market maker" for Binance/Bitget/Gate (Chinese docs) — grid, not two-sided quoting |
| https://github.com/fedecaccia/avellaneda-stoikov | Python / none | 728 | 2023-07 | Pure A-S simulation on synthetic Brownian mid (γ, σ, T, k, M), PnL histograms — pedagogy only |
| https://github.com/purefinance/mmb | Rust / GPL-3.0 | 619 | 2022-11 | "mmb" Rust MM bot framework (archived-ish; last push 2022) |
| https://github.com/beatzxbt/smm | Python / MIT | 612 | 2026-08 | "simple market maker" for **Bybit** (optional Binance feed): features compare several mid-prices, skew from features corrected by inventory, spread = base_spread × volatility multiple (Bollinger band width), `inventory_extreme` → reduce-only; OMS diff designed to be rate-limit-efficient; author's v2 branch is exchange-agnostic |
| https://github.com/javifalces/HFTFramework | Java+Python / Apache-2.0 | 307 | 2026-09 | Research framework behind "A RL approach to improve the performance of the Avellaneda-Stoikov MM algorithm" |
| https://github.com/joaquinbejar/market-maker-rs | Rust / MIT | 101 | 2026-09 | Library crate: A-S, GLFT, grid, adaptive spread by imbalance, VPIN, intensity estimation, event-driven backtester with immediate/queue/probabilistic fill models, exchange-connector trait, Prometheus export |
| https://github.com/mdibo/Avellaneda-Stoikov | Python / none | 155 | 2020-05 | Paper replication notebook |
| https://github.com/Drakkar-Software/OctoBot-Market-Making | Python / GPL-3.0 | 41 | 2026-03 | OctoBot-based MM for 15+ exchanges via CCXT (retail-oriented) |
| https://github.com/verata-veritatis/bybit-market-maker | Python / MIT | 52 | 2021-03 | Minimal Bybit sample MM |
| OKX official sample (`okxapi/okx-sample-market-maker`) | Python | — | — | **[unverified]** the canonical repo returns 404 today; only forks remain (e.g. https://github.com/Jack495495/okx-sample-market-maker "A sample market maker to demonstrate the usage of python-okx SDK"). Treat as removed. |

Searched-for but not found as credible repos: `jaikumarm`, `quantresearch/market-maker`, `pyquant` MM bots (GitHub API
returned no such repos). `fmzquant/strategies` (5,801 ★, JS/Python/C++ strategy dump for the FMZ platform, last push
2025-04) contains many MM snippets but is platform-locked to FMZ's runtime — reference only.

Takeaways from the long tail: (1) the durable pattern everyone converges on is *compute desired quote set → diff against
live orders → amend/cancel/create* (BitMEX `converge_orders`, hftbacktest grid dict, smm OMS); (2) most Python bots quote
on a fixed timer (100 ms–1 s) rather than per book event; (3) almost none have a credible backtester — only hftbacktest,
nautilus and (to a lesser degree) market-maker-rs.

### A.6 Data ingestion / connectivity libraries

**cryptofeed** — https://github.com/bmoscon/cryptofeed · Python 3.12+ · license badge says AGPL (GitHub API: NOASSERTION)
· 2,906 ★, pushed 2026-09-14 · PyPI 2.5.0. Normalised WS feeds (L1/L2/L3 book, trades, ticker, funding, OI,
liquidations, candles) for Binance/Binance Futures/Bybit/OKX/… with **backends** (Redis, ZeroMQ, Kafka, InfluxDB v2,
QuestDB, PostgreSQL, MongoDB, sockets) and **pcap record/replay** (`FeedHandler(record=...)`, zstd-compressed, opens in
Wireshark). README perf table: 1.39M msg/s JSON decode with Decimal (msgspec), 134k Bybit frames/s handler throughput.
Great for **self-recording L2 + trades** with local receive timestamps; AGPL matters if we ship a product.

**CCXT / CCXT Pro** — https://github.com/ccxt/ccxt · MIT · 44,072 ★ · PyPI 4.5.81. WebSocket "Pro" was merged into the
free package in Oct 2022 (https://github.com/ccxt/ccxt/pull/15085); `ccxt.pro.okx/bybit/binance` expose
`watchOrderBook`, `watchTrades`, `watchBidsAsks`, `watchOrders`, `watchPositions`, `watchMyTrades` and WS order entry
`createOrderWs/editOrderWs/cancelOrderWs` (https://docs.ccxt.com/docs/pro-manual). Pros: one API for all three venues,
huge coverage. Cons: heavy per-message overhead (unified dict objects), abstracts away sequence numbers / checksums, not
suited to a latency-sensitive hot path — fine for account/positions and tooling.

**Barter-rs** — https://github.com/barter-rs/barter-rs · Rust · MIT · 2,305 ★, pushed 2026-08-24. Crates `barter`
(engine + state), `barter-data` (public WS `MarketStream`: PublicTrades, OrderBooksL1/L2), `barter-execution`
(`ExecutionClient`, mock execution for paper/backtest), `barter-instrument`, `barter-integration`. Event-driven, indexed
O(1) state, audit stream for out-of-hot-path monitoring. README disclaimer says "educational purpose … not verified for
production"; venue coverage per crate must be checked **[unverified for OKX/Bybit execution]**. Good skeleton if we go
Rust-from-scratch; no MM strategy or fill model included.

**tectonicdb** — https://github.com/0b01/tectonicdb · Rust · 753 ★, last push 2024-01 (dormant). Standalone order-book
tick store with Dense Tick Format: 12 bytes/event `(ts, seq, is_trade, is_bid, price, size)`, 600k inserts/s/thread,
`dtfcat` tool, TCP protocol, Python/TS bindings. Useful as a compact **file format idea**; Parquet/Arrow + zstd has largely
superseded it.

**tardis-machine / tardis-python / tardis-node** — https://github.com/tardis-dev/tardis-machine (TS, MPL-2.0, 311 ★,
pushed 2026-08), `tardis-node` (368 ★), `tardis-python` (148 ★). Locally-runnable server that replays Tardis historical
data *and* proxies real-time exchange WS into normalised messages over HTTP/WS with caching — the easiest path to
"same code for replay and live" data ingestion if we buy Tardis.

---

## B. Backtesting approaches for MM

### B.1 Why bar-based backtesters don't work for market making

- A maker's PnL is decided by **which** resting orders fill, **when**, and against **whom**. Bars (even 1 s) collapse the
  path inside the bar: you cannot know whether price *touched* your level (→ maybe filled, depends on queue) or *traded
  through* it (→ surely filled, but likely adverse). Hummingbot's own docs admit 1-minute candles imply ≤1 fill/min while
  live PMM sees 30+ fills/min, and that queue position, book depth and latency are not modelled
  (https://condor.hummingbot.org/bots/backtesting, https://hummingbot.substack.com/p/the-bot-pod-episode-4-backtesting).
- backtrader / vectorbt / freqtrade assume "limit fills when price crosses the limit" (or at bar OHLC) with no queue,
  latency or partial-fill notion, so a maker strategy is graded optimistically: every touch is a fill, fills are at your
  price with zero adverse selection, and cancels are instantaneous. Moallemi & Yuan (2016, cited by
  https://marketmaker.cc/en/blog/post/fill-simulation-partial-fills-backtest/) find queue-position value ≈ half-spread
  for large-tick names, i.e. the same magnitude as the entire MM edge — a model that ignores it "estimates a different
  strategy's PnL".
- hftbacktest's README framing: backtests must be **accurate, not merely conservative**; validate by reproducing a live
  month's PnL before optimising (https://hftbacktest.readthedocs.io/en/latest/ "Why Accurate Backtesting Matters").

### B.2 Requirements checklist for an MM backtester

1. **L2 (MBP) replay with snapshot + deltas**, exchange *and* local timestamps; L3 (MBO) where the venue offers it
   (none of Binance/OKX/Bybit publish public MBO; Bybit/OKX give ≤1000/400 levels, Binance diff-depth 100 ms/250 ms).
2. **Trade tape aligned with book** (trades before the depth update they caused — hftbacktest Data Preparation note).
3. **Latency model**: feed latency (local − exchange ts) and order round-trip (entry, response), ideally replayed from
   your own recorded latencies (`IntpOrderLatency`), else `mult·feed_latency + offset`.
4. **Queue-position model** for L2: conservative (advance only on trades at your price) vs probabilistic
   (`p = f(back)/(f(back)+f(front))`, Rigtorp 2013) with `f = x^n` or `log(1+x)`; calibrate `n` against live fills
   (hftbacktest changed 2 → 3 in 2025 for Binance perps).
5. **Fill semantics**: fill when trades *through* your price; when price *touches*, fill only if queue ahead is exhausted;
   handle post-only rejects (GTX) when your price would cross.
6. **Fee model** with maker rebates and taker fees per venue/tier (`trading_value_fee_model(-0.00005, 0.0007)` style).
7. **Partial fills** and order-state machine (new → ack → partial → filled/cancelled, cancel-in-flight races).
8. Multi-asset / multi-venue clocks for hedging and cross-venue signals.
9. Speed: JIT/compiled inner loop (Numba or Rust) — a day of BTCUSDT perps L2 is tens of millions of events.

### B.3 hftbacktest's approach (summary)

Two processors (local, exchange) exchanging timestamped messages with latency; exchange processor reconstructs the full
book from MBP/MBO feed, matches your orders against replayed trades/depth changes under a pluggable `QueueModel`
(`RiskAdverseQueueModel`, `ProbQueueModel<PowerProbQueueFunc|LogProbQueueFunc…>`, `L3FIFOQueueModel`), a pluggable
`LatencyModel` (`ConstantLatency`, `IntpOrderLatency`) and `FeeModel`; `NoPartialFillExchange` vs `PartialFillExchange`.
Strategy code sees `depth`, `last_trades`, `orders`, `position` and drives time via `elapse`/`wait_next_feed`. Docs:
https://hftbacktest.readthedocs.io/en/latest/order_fill.html , https://hftbacktest.readthedocs.io/en/latest/latency_models.html .

### B.4 nautilus_trader's approach (summary)

Immutable recorded book; `FillModel.prob_fill_on_limit` for touch fills; `queue_position=True` with `trade_execution=True`
snapshots displayed same-side size at acceptance and drains it with same-price trades; `liquidity_consumption=True`
prevents double-filling the same displayed size; custom `FillModel.get_orderbook_for_fill_simulation()` can inject a
synthetic book. No per-order latency replay documented. Docs: https://nautilustrader.io/docs/latest/concepts/backtesting/ .

### B.5 References on simulating limit-order fills / queue position

- E. Rigtorp, "Estimating Order Queue Position" (2013) — https://rigtorp.se/2013/06/08/estimating-order-queue-position.html
- quant.SE #3782 "How do we estimate position of our order in order book" — https://quant.stackexchange.com/questions/3782
- quant.SE #36073 on calibrating λ(δ) in A-S — https://quant.stackexchange.com/questions/36073 (used by the GLFT tutorial)
- Huang, Lehalle, Rosenbaum, "Simulating and analyzing order book data: the queue-reactive model" (JASA 2015) —
  https://arxiv.org/abs/1312.0563 (state-dependent intensities; basis for reactive simulators)
- Moallemi & Yuan (2016), "A Model for Queue Position Valuation in a Limit Order Book" (cited in marketmaker.cc post)
- Dayri & Rosenbaum, "Large tick assets: implicit spread and optimal tick size" — https://arxiv.org/pdf/1207.6325
- Guéant, Lehalle, Fernandez-Tapia, "Dealing with the inventory risk" — https://arxiv.org/abs/1105.3115 ; Guéant,
  "Optimal market making" — https://arxiv.org/abs/1605.01862
- BitMEX blog "How to market make Bitcoin derivatives" lessons 1–2 — https://blog.bitmex.com/how-to-market-make-bitcoin-derivatives-lesson-2/
- Headlands Tech, "Market microstructure signals" — https://blog.headlandstech.com/2017/08/
- marketmaker.cc, "Fill simulation: the ladder from close-price fantasy to queue-aware reality" —
  https://marketmaker.cc/en/blog/post/fill-simulation-partial-fills-backtest/ (rungs 0–5 taxonomy)

---

## C. Data sources for L2/L3 and trades

### C.1 Tardis.dev (paid, best-in-class for our venues)

- https://tardis.dev · docs https://docs.tardis.dev · clients MPL-2.0 (above).
- Coverage: 64 exchange feeds incl. `binance`, `binance-futures`, `binance-delivery`, `okex`/`okex-swap`/`okex-futures`,
  `bybit`, `bybit-spot`, … ; history from 2019-03-30 for the earliest venues; Bybit spot since 2021-12-04 with v5
  channels `orderbook.50` (since 2023-04-05) and `orderbook.200` (since 2025-02-24)
  (https://docs.tardis.dev/historical-data-details/bybit-spot).
- Formats: (a) raw exchange-native WS messages with `localTimestamp` via replay API / `tardis-machine`; (b) normalised
  CSV datasets `incremental_book_L2`, `book_snapshot_25`, `book_snapshot_5`, `trades`, `quotes`, `book_ticker`,
  `derivative_ticker`, `liquidations`, `options_chain` at
  `https://datasets.tardis.dev/v1/:exchange/:dataType/:year/:month/:day/:symbol.csv.gz` with `timestamp` (exchange, µs)
  and `local_timestamp` (µs) columns (https://docs.tardis.dev/downloadable-csv-files/data-types).
- Pricing (site, Sep 2026): plans from **$350/mo** (quarterly/yearly billing) to $3,000–$6,000/mo depending on data plan
  and tier; historical access "4 years with yearly billing"; 20 TB/mo transfer on lower tiers
  (https://tardis.dev/ pricing section; corroborated by https://docs.ccxt.com/docs/comparisons/ccxt-vs-tardis).
- **Free tier**: the **first day of every month** for all exchanges/datasets needs no API key (HTTP API reference:
  "Without API key historical data feeds for the first day of each month are available") — enough to develop and test
  converters/backtester plumbing.
- Caveat (hftbacktest Data Preparation): Tardis' Binance Futures uses event-send time `E` rather than matching time `T`,
  so feed latency is slightly underestimated; SOD snapshots are inserted at the start of each daily file.
- hftbacktest ships `tardis.convert` / `convert_fuse`; nautilus has a stable `TARDIS` adapter.

### C.2 Exchange-provided historical data (free / official)

**Binance — data.binance.vision** (https://github.com/binance/binance-public-data, MIT; 2,497 ★)
- Spot daily/monthly: `aggTrades`, `trades`, `klines` (1s…1mo). Spot timestamps in **microseconds** from 2025-01-01.
- USDⓈ-M futures daily: `aggTrades`, `trades`, `klines`, `bookTicker`, `bookDepth`, `metrics`, `indexPriceKlines`,
  `markPriceKlines`, `premiumIndexKlines` (S3 listing `data/futures/um/daily/`).
- **`bookDepth` is NOT L2**: verified from `BTCUSDT-bookDepth-2025-09-01.zip` — columns
  `timestamp,percentage,depth,notional` at ±1…5 % bands, ~one row-set every 30–60 s (28k rows/day). Useless for fill sim.
- **`bookTicker` (BBO) is only available 2023-05-16 → 2024-03-30** for BTCUSDT (S3 listing; not truncated). Nothing after.
- `metrics`: 5-min OI, long/short ratios, taker buy/sell ratio.
- So the free Binance dump gives **trades/aggTrades only** for microstructure work; L2 must be self-recorded or bought.
  Binance sells tick-level order-book history via its "Historical Market Data" landing (https://www.binance.com/en/landing/data,
  authenticated "Get Future TickLevel Orderbook Historical Data Download Link" endpoint); hftbacktest has a converter
  (`binancehistmktdata.py`) and warns those files have **no local timestamps**. Pricing **[unverified]**.

**Bybit — public.bybit.com and quote-saver.bycsi.com** (official, free, no key)
- Trades: `https://public.bybit.com/trading/{SYMBOL}/{SYMBOL}{YYYY-MM-DD}.csv.gz` (linear/inverse) and
  `https://public.bybit.com/spot/{SYMBOL}/{SYMBOL}_{YYYY-MM-DD}.csv.gz`; columns
  `timestamp,symbol,side,size,price,tickDirection,trdMatchID,grossValue,homeNotional,foreignNotional` (post-2022 layout)
  (https://flox-foundation.github.io/flox/how-to/import-multi-exchange-archives/, https://github.com/Anton495/bybit-data-downloader).
- **L2 order book archives** (linked from https://www.bybit.com/derivatives/en/history-data): daily
  `https://quote-saver.bycsi.com/orderbook/linear/{SYMBOL}/{YYYY-MM-DD}_{SYMBOL}_ob500.data.zip` (also `inverse/`,
  `spot/` with `ob200`), JSONL of `snapshot` + `delta` records at 200/500 levels; derivatives history back to 2023, spot
  book from May 2025; ~450 MB/day zipped for BTCUSDT-class symbols (Anton495 downloader; katanaquant post;
  nautilus `BybitOrderBookDeltaDataLoader` tutorial https://nautilustrader.io/docs/latest/tutorials/backtest_orderbook_bybit/).
  Web UI limits to 7-day ranges → script the URLs. **No local timestamps** (exchange `ts` only) → latency must be modelled.
  (Direct `curl` of public.bybit.com returned an empty listing from this network; URLs above are from third-party docs.)

**OKX — Historical market data** (https://www.okx.com/en-us/historical-data)
- Offers downloadable **trade history from Sep 2021**, **"High-resolution L2" order book from Mar 2023**, candles from
  Jul 2023, funding from Mar 2022, borrow rates. Programmatic listing via
  `GET /api/v5/public/market-data-history?module=1&instType=SPOT&instIdList[0]=BTC-USDT&dateAggrType=daily&begin=..&end=..`
  returning CDN zip URLs like `https://static.okx.com/cdn/okex/traderecords/trades/daily/20251001/BTC-USDT-trades-2025-10-01.zip`
  (observed in https://github.com/ccxt/ccxt/pull/26814). L2 file schema/frequency **[unverified — not inspected]**.
- REST `GET /api/v5/market/history-trades` covers only ~3 months (https://klinepic.com/guides/okx-tick-data-download/).

### C.3 Other vendors

| Vendor | What | Cost (published) | Notes |
|---|---|---|---|
| **Crypto Lake** https://crypto-lake.com | L2 snapshots 20 levels/side at **100 ms**, tick trades, 1m candles; Python `lakeapi` (Apache-2.0, 76 ★) | **$64/mo** individual promo ($80), 300 GB/mo; $500/mo teams | Free anonymous **sample** (`lakeapi.use_sample_data(anonymous_access=True)` → Binance BTC-USDT book). Snapshot-based, not incremental → no exact queue reconstruction. |
| **CoinAPI** https://www.coinapi.io/s3-api | Flat Files (S3): trades, quotes, `T-LIMITBOOK_FULL` (full-depth L2/L3 updates), OHLCV; REST L2 capped 20×20 | Subscription tiers + usage credits; flat-file price by dataset/volume (no public per-GB list) | Hourly partitions since 2026-06-09; T+1. |
| **Kaiko** https://www.kaiko.com/products/l1-l2-data | L1/L2 tick + snapshots; cloud CSV daily; full book "since Aug 2023" | L2 aggregations from **$2,000/mo**, L2 tick from **$2,500/mo** | Replay window 72 h for tick L2 stream; institutional. |
| **Amberdata** https://www.amberdata.io/binance-market-data | Tick-level book events + 1-min full snapshots; Binance spot since 2017-08, futures since 2019-09 | Quote-based | REST history generally ≤18 months. |
| **CryptoStruct** https://cryptostruct.com/historical-data/order-book | Full L2 snapshot+updates with venue ts **and** co-located receive ts (ns), 32 venues, Feb 2021–Sep 2026 | **€1 per instrument-day**, guest checkout | Cheap way to get *local-timestamped* L2 for a few weeks of BTC/ETH on our venues; free Python reader. |
| Databento | Not crypto (US equities/futures) | — | hftbacktest has a converter; irrelevant for our venues. |

### C.4 Self-recording (recommended in parallel with any purchase)

- Record raw WS (not normalised) with a **local receive timestamp** so feed latency is measurable: hftbacktest `collector/`
  (Rust; Binance spot/UM/CM, Bybit, Hyperliquid; no OKX yet), cryptofeed pcap recorder (all three venues), or
  `tardis-machine` real-time normalised stream.
- Streams to record per symbol: Binance `depth@100ms` (perps) / `depth@100ms`+REST snapshot (spot), `aggTrade`/`trade`,
  `bookTicker`; Bybit v5 `orderbook.50`/`orderbook.200` (20 ms/100 ms push), `publicTrade`; OKX `books` (400 levels,
  100 ms) or `books-l2-tbt` (VIP-gated 10 ms) and `trades`/`trades-all`. Bybit depth push frequencies from
  https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook .
- Also log **your own order latencies** (send ts, exchange ack ts, local ack ts) — needed for `IntpOrderLatency`.
- Storage: ~1–3 GB/day/symbol raw JSON for BTCUSDT-class books; Parquet+zstd shrinks ~5–7× (Anton495 numbers: 450 MB zip
  → 65–100 MB parquet/day).

---

## D. Analytics / monitoring tooling

- **Grafana** (AGPL) as the dashboard layer for everything below; official datasource plugins exist for QuestDB
  (https://grafana.com/grafana/plugins/questdb-questdb-datasource/), ClickHouse, InfluxDB, Prometheus.
- **Prometheus** + `prometheus_client`/`metrics` crate for bot health: quote-loop latency, WS gap counts, order
  round-trip histograms, reject codes, inventory, PnL gauges. market-maker-rs ships a Prometheus exporter + Grafana
  dashboard as a template.
- **QuestDB** (Apache-2.0): time-series SQL with `ASOF JOIN`, `SAMPLE BY`, `LATEST ON`, `WINDOW JOIN`, `HORIZON JOIN`
  (markout analysis at multiple offsets), `twap()`, float64 **arrays** for L2 levels (blog:
  https://questdb.com/blog/level-2-order-book-data-into-questdb-arrays/), PostgreSQL wire + ILP ingest; cryptofeed has a
  native QuestDB backend. QuestDB's own benchmark claims 7–8.6 M rows/s ingest vs ~1.7 M for ClickHouse and faster
  latest-point queries, while ClickHouse wins broad scans/top-N (https://questdb.com/blog/clickhouse-vs-questdb-comparison/
  — vendor benchmark, treat with care). Best fit for *live* tick ingest + dashboards.
- **ClickHouse** (Apache-2.0): batch-oriented columnar OLAP; excellent for large offline research scans over Parquet
  (`s3()`/`file()` table functions), less happy with constant small inserts.
- **InfluxDB**: fine for metrics; weak for tick-level joins (QuestDB benchmark claims up to 36× ingest gap). Prefer
  Prometheus for metrics, QuestDB/ClickHouse for ticks.
- **kdb+/q**: still the HFT gold standard but proprietary and benchmark-gagged (DeWitt clause); alternatives with
  similar ergonomics: **DolphinDB** (proprietary), **QuestDB**, and **polars** in-process.
- **polars / pandas / DuckDB**: research layer. hftbacktest's tutorials already use polars (`group_by_dynamic`) on the
  recorder output; DuckDB reads Parquet lakes directly and does ASOF joins. Keep normalised tick data as
  Parquet (zstd) partitioned by `venue/symbol/date`.
- Passivbot's `monitor_*` modules (TUI + static web dashboard) and Hummingbot's Condor/dashboard are examples of
  bot-native monitoring if we want a small self-hosted UI later.

---

## Recommended stack for our bot

**Decision summary**: Python research + hftbacktest for simulation; Rust for the live quoting core, with our own thin
OKX/Bybit/Binance connectors modelled on nautilus/hftbacktest; Tardis (or CryptoStruct for a cheap start) + our own
recorder for data; Parquet lake + QuestDB + Grafana/Prometheus for analytics and monitoring.

1. **Language** — Rust for the live hot path (WS parse → book → quote → order diff → send), Python for research,
   calibration and reporting. Reasons: every serious OSS reference here (hftbacktest, nautilus, barter, market-maker-rs,
   passivbot's orchestrator) has moved the hot path to Rust; Python-only bots (Hummingbot PMM, smm) quote on ≥100 ms
   timers and cannot react per book event. Trade-off: slower iteration; mitigated by keeping strategy math in a small
   pure function that is unit-tested against the Python/Numba reference.
2. **Framework vs from-scratch** — *from scratch* for the quoting engine (it is ~2–4k lines: book, quote model, order
   reconciler, risk), but **borrow** components: hftbacktest's Rust `connector` design (shared-memory IPC, multiple bots
   per connector) and its Bybit/Binance Futures connectors as reference, nautilus adapters for OKX WS details, Passivbot
   `okx.py` for account-mode/error-code gotchas, BitMEX `converge_orders` semantics for the reconciler. Not Hummingbot:
   its executor-per-level model, 1 s tick and Cython build fight an MM engine. Not nautilus as a framework: LGPL + heavy
   build + coarser fill model; keep it as an *optional* second backtester for cross-checks.
3. **Backtester** — **hftbacktest** (MIT). It is the only option with latency replay + queue models + partial fills on
   full L2, has ready GLFT/grid/OBI tutorials, and its Rust crate lets the *same* strategy struct run in backtest and live.
   Risk: maintenance slowed in 2026 and OKX live support is absent → we own the OKX connector regardless. Mitigation:
   pin `hftbacktest==2.4.4` / the Rust crate, vendor the queue/latency models if needed.
4. **Data** — (a) start *today* recording raw WS + local ts for BTC/ETH/SOL on all three venues (cryptofeed pcap or
   hftbacktest `collector` + an OKX collector we write); (b) buy **Tardis** (from $350/mo, first-of-month free for
   plumbing) when we need months of history across venues; (c) use **CryptoStruct** (€1/instrument-day, local ts) or
   **Bybit ob500 / OKX L2 dumps** (free, exchange ts only) for cheap early experiments; (d) Binance free dumps only for
   trades/aggTrades — its `bookDepth` is aggregated bands and `bookTicker` ended 2024-03. Model latency artificially
   when local ts is missing (hftbacktest "Order Latency Data" recipe).
5. **Monitoring** — Prometheus + Grafana for bot health (loop latency, WS gaps, order RTT p50/p99, rejects, inventory,
   realised/unrealised PnL, fee/rebate accrual); QuestDB for tick + quote + fill capture with `ASOF`/`HORIZON JOIN`
   markout dashboards; Parquet lake (zstd) + polars/DuckDB for research. Skip InfluxDB/kdb.

Trade-offs acknowledged: Rust + own connectors is the largest up-front cost; alternative "Python everywhere with
hftbacktest (Numba) for research and a Python asyncio quoter" is viable for a 100 ms–1 s timer strategy on large-tick
pairs, and is how smm/Hummingbot operate — acceptable as a *phase 1* while the Rust engine is built.

## Reusable code / ideas to borrow

- GLFT calibration + quoting loop (A, k by OLS on log-intensity over the shallow range; σ in ticks/√s; `compute_coeff`;
  adj1/adj2; order_id = price tick): https://github.com/nkaz001/hftbacktest/blob/master/examples/GLFT%20Market%20Making%20Model%20and%20Grid%20Trading.ipynb
- Simplified σ-only spread/skew for non-exponential λ(δ) and large-tick assets:
  https://github.com/nkaz001/hftbacktest/blob/master/examples/High-Frequency%20Grid%20Trading%20-%20Simplified%20from%20GLFT.ipynb
- Queue-based quoting and BBO micro-price/trade-impulse signals:
  https://github.com/nkaz001/hftbacktest/blob/master/examples/Queue-Based%20Market%20Making%20in%20Large%20Tick%20Size%20Assets.ipynb
- OBI / VAMP / weighted-depth alpha into fair value:
  https://github.com/nkaz001/hftbacktest/blob/master/examples/Market%20Making%20with%20Alpha%20-%20Order%20Book%20Imbalance.ipynb
- Queue-position models (RiskAdverse, Prob power/log, L3 FIFO):
  https://github.com/nkaz001/hftbacktest/blob/master/hftbacktest/src/backtest/models/queue.rs
- Latency models and artificial order-latency generation:
  https://github.com/nkaz001/hftbacktest/blob/master/hftbacktest/src/backtest/models/latency.rs ,
  https://github.com/nkaz001/hftbacktest/blob/master/py-hftbacktest/hftbacktest/data/utils/feed_order_latency.py ,
  https://github.com/nkaz001/hftbacktest/blob/master/examples/Order%20Latency%20Data.ipynb
- Fee models incl. rebates: https://github.com/nkaz001/hftbacktest/blob/master/hftbacktest/src/backtest/models/fee.rs
- Tardis → hftbacktest converter (`convert`, `convert_fuse`):
  https://github.com/nkaz001/hftbacktest/blob/master/py-hftbacktest/hftbacktest/data/utils/tardis.py
- Raw feed collector (Binance/Bybit/Hyperliquid) to clone for OKX:
  https://github.com/nkaz001/hftbacktest/tree/master/collector/src
- Live connector architecture (IPC, multiple bots) + Bybit/Binance Futures connectors:
  https://github.com/nkaz001/hftbacktest/tree/master/connector/src , README https://github.com/nkaz001/hftbacktest/blob/master/connector/README.md
- Hummingbot A-S reservation price / spread and `eta` size transform (reference formulas):
  https://github.com/hummingbot/hummingbot/blob/master/hummingbot/strategy/avellaneda_market_making/avellaneda_market_making.pyx
- Hummingbot trading-intensity estimator (volume-by-distance exponential fit — compare with GLFT approach):
  https://github.com/hummingbot/hummingbot/blob/master/hummingbot/strategy/__utils__/trailing_indicators/trading_intensity.pyx
- Hummingbot inventory size-skew ramp and hanging orders:
  https://github.com/hummingbot/hummingbot/blob/master/hummingbot/strategy/pure_market_making/inventory_skew_calculator.pyx ,
  https://github.com/hummingbot/hummingbot/blob/master/hummingbot/strategy/hanging_orders_tracker.py
- Hummingbot OKX connector (auth, WS book source, user stream) as a spec for our own:
  https://github.com/hummingbot/hummingbot/tree/master/hummingbot/connector/exchange/okx ,
  https://github.com/hummingbot/hummingbot/tree/master/hummingbot/connector/derivative/okx_perpetual
- Passivbot OKX quirks (posMode/PM detection, pagination, error codes, 100-order cap):
  https://github.com/enarjord/passivbot/blob/master/src/exchanges/okx.py (and `bybit.py`, `binance.py`, `ccxt_bot.py`)
- BitMEX `converge_orders` desired-vs-live reconciliation:
  https://github.com/BitMEX/sample-market-maker/blob/master/market_maker/market_maker.py
- smm feature → skew → quote generation and rate-limit-aware OMS diff: https://github.com/beatzxbt/smm
- market-maker-rs crate (A-S/GLFT/VPIN/intensity estimation in Rust, Prometheus export) for API shape ideas:
  https://github.com/joaquinbejar/market-maker-rs
- nautilus Bybit `ob500` loader + OrderBookImbalance strategy (second-opinion backtester):
  https://nautilustrader.io/docs/latest/tutorials/backtest_orderbook_bybit/ ,
  https://github.com/nautechsystems/nautilus_trader/blob/develop/examples/backtest/crypto_orderbook_imbalance.py
- nautilus fill/queue semantics to cross-validate our simulator:
  https://nautilustrader.io/docs/latest/concepts/backtesting/trade-execution/
- cryptofeed pcap recorder + QuestDB backend for self-recording:
  https://github.com/bmoscon/cryptofeed/blob/master/examples/record.py , https://questdb.com/blog/level-2-order-book-data-into-questdb-arrays/
- Bybit L2/trades downloaders (URL patterns, JSONL → Parquet): https://github.com/Anton495/bybit-data-downloader ,
  https://github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines
- Binance public data helper scripts: https://github.com/binance/binance-public-data/tree/master/python
- Tardis CSV schemas: https://docs.tardis.dev/downloadable-csv-files/data-types
