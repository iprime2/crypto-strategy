# GoDark vanilla MM — code-grounded analysis for CEX port

**Sources (full export 2026-09-21):** `resource/godark-mm-bot/` — Rust `mms/vanilla-mm-rust/src/{strategy,main,lib}.rs`, ops Python/shell under `mms/`, tuning envs, `docs/godark-mm-strategy-cex-porting-guide.md`.

**Cross-read:** `STRATEGY.md`, research `01`–`05`.

**Date:** 2026-09-21 (re-analysis after complete export).

---

## 1. Executive summary

The GoDark **vanilla-mm-rust** bot is a **15 s (configurable) clock-driven post-only market maker** on USDC-margined perps (BTC/ETH/SOL). Strategy logic lives almost entirely in **`strategy.rs`** (~920 lines): Avellaneda–Stoikov half-spread with fee floor, **reservation price** with inventory skew + vol penalty + GLFT cubic boundary + book-imbalance shift, asymmetric half-spreads, inventory-based spread widen and one-sided quoting, fair-jump defense, and inputs from **rolling vol**, **blended κ**, and **markout guard** extras.

**`main.rs`** wires GoDark REST/WS, fair resolution (`lib.rs::resolve_fair_price`), fill detection via inventory delta, **async multi-horizon markout** (default 1/5/30 s), κ from fill distance + optional external trade tape, economics persistence, over-cap unwind, and structured **`MM_METRICS`** logging.

**Ops layer:** `mm-eval.py` auto-writes `artifacts/*/mm-tuning.env` with **hard guards** against tightening spread or scaling size up when 30 s markouts are toxic; runtime **overlays** (`mm-tuning-testnet.env`, `mm-tuning-devnet.env`) are not overwritten by eval.

**CEX fit:** Port **`compute_quote` + markout state machine + fair jump + inventory flags** first. Replace GoDark transport (HPKE REST), Pyth oracle blend, and external Hyperliquid/Binance fair tape with **native L2 + Binance lead** per `STRATEGY.md` §4. Replace fixed 15 s loop with **event-driven re-quote + max quote age** (§8). Keep eval **markout-gated tuning philosophy**; do not copy dead env knobs (see §9).

**Recommendation:** Treat this export as **Phase-1 implementation spec** for quote math and adverse-selection defense; keep `STRATEGY.md` for venue choice, queue/amend policy, hedging, and kill switches.

---

## 2. Architecture (from Rust, not the porting guide alone)

### 2.1 Process model

| Layer | Location | Role |
|--------|----------|------|
| **Quote engine** | `strategy.rs` | Pure functions: fair → reservation → bid/ask, side flags, sizes |
| **Venue loop** | `main.rs` | Auth, positions, fair, vol/κ, markout decay, place/cancel, fill economics |
| **Fair & reference data** | `lib.rs` | Pyth Hermes, Binance/Hyperliquid BBO & trades, oracle blend, min notional |
| **Legacy Python quotes** | `mms/bot/pricing.py` | Simplified reservation + symmetric half-spread — **not used by Rust binary** |
| **Tuning / observability** | `mm-eval.py`, `mm-dashboard.py`, `mm-metrics-ingest.py`, shell daemons | Logs → tuning env; optional Timescale |

One symbol per process; env from `mm-env.sh` + stack-specific tuning + overlays.

### 2.2 Main loop (`main.rs`)

Each `MM_LOOP_INTERVAL_SEC` tick (floor 5 s in code):

1. **Rate-limit gate** — sleep if 429 backoff active.
2. **Scheduled auth refresh** (`MM_TOKEN_REFRESH_SEC`, default 480 s).
3. **Positions** (retry) → signed inventory, mark, uPnL; optional **one-shot venue reconcile** of `FillEconomics.position` vs venue (`MM_VENUE_RECONCILE_POSITION`).
4. **Over-cap soft cancel** if `|inv| > 1.05 × max_inv`.
5. **Fair** — `resolve_fair_price(override, book, mark, oracle, fallback, oracle_blend, microprice_weight)`; optional WS orderbook or external `MM_BOOK_SOURCE`.
6. **Hard over-cap** — cancel all; **reduce-only IOC unwind** (`try_over_cap_unwind`) if `|inv| > max_inv`.
7. **Fill detection** — inventory delta → spawn markout task; update `FillEconomics`, κ estimator from fill distance.
8. **Vol** — push fair into `VolTracker`; `horizon_vol_bps(sample, lookback, loop_sec, horizon_sec)`.
9. **κ** — fill-distance median estimator + optional tape blend (`MM_KAPPA_TAPE`, `fetch_tape_kappa` → `estimate_kappa_from_trade_prices`).
10. **Markout guard** — per-loop decay; read side extras + `rolling_adverse_bps`.
11. **`compute_quote`** → bid/ask/qty/side flags.
12. **Requote policy** — skip cancel/replace if `quotes_within_tolerance` unless fair jumped.
13. **Cancel then place** post-only GTC limits (reduce-only near cap).

Metrics: JSON line prefixed `MM_METRICS`.

### 2.3 Fair price (`lib.rs::resolve_fair_price`)

Priority:

1. `MM_FAIR_OVERRIDE` if set.
2. Book anchor: `fair = (1−w)·mid + w·microprice` (`MM_MICROPRICE_WEIGHT`, default 0.3).
3. If book + **Pyth oracle** (`oracle_fair_for_symbol`): `fair = w_oracle·oracle + (1−w_oracle)·book` (`MM_ORACLE_BLEND_WEIGHT`, default 0.35).
4. Else book only, else **position mark**, else oracle alone, else `MM_FAIR_FALLBACK_*`.

External BBO used when `MM_MARKET_DATA` is false and `MM_BOOK_SOURCE` lists `hyperliquid,binance` (not for resting orders on GoDark).

---

## 3. `strategy.rs` — types, formulas, and function catalog

### 3.1 `BookTop`

| Method | Formula / behavior |
|--------|-------------------|
| `mid()` | `(best_bid + best_ask) / 2` if valid touch |
| `microprice()` | `(best_bid × ask_qty + best_ask × bid_qty) / (bid_qty + ask_qty)`; falls back to mid if no size |
| `imbalance_skew_bps()` | `((micro / mid) − 1) × 10_000` |

Used in `compute_quote`:  
`book_skew_bps = clamp(imbalance_skew_bps × book_imbalance_skew_bps / 6, ±book_imbalance_skew_bps)`.

### 3.2 `VolTracker`

| Method | Formula |
|--------|---------|
| `push(fair)` | Rolling window of fair prices (capacity `MM_VOL_LOOKBACK`, default 96) |
| `vol_bps()` | Std dev of **log returns** × 10_000 (bps per loop sample; needs ≥3 prices) |

### 3.3 `horizon_vol_bps(sample_vol_bps, lookback_samples, loop_interval_sec, horizon_sec)`

Scales sample vol to AS holding horizon:

\[
\sigma_{\text{horizon}} = \sigma_{\text{sample}} \times \sqrt{\frac{\text{horizon\_sec}}{\text{lookback\_samples} \times \text{loop\_interval\_sec}}}
\]

(`main.rs` passes `MM_VOL_HORIZON_SEC`, default 900.)

### 3.4 `KappaEstimator`

| Method | Formula |
|--------|---------|
| `observe(distance_bps)` | Rolling deque of half-spread distances fair→fill (bps) |
| `kappa_raw(min_samples)` | `κ = ln(2) / median(distance_bps)` (median floored at 0.5 bps) |
| `kappa(fallback, min_samples, floor, cap)` | `clamp(raw or fallback, MM_KAPPA_FLOOR, MM_KAPPA_CAP)` |

### 3.5 `estimate_kappa_from_trade_prices(trade_prices, mid)`

Buckets trades by distance from mid (2/5/10/20/40+ bps bands), log-linear fit `ln(count) ~ −κ·δ`, returns `clamp(−slope × 10_000, 0.05, 50)`.

### 3.6 `signed_fill_markout_bps(fair_at_fill, fair_now, bought)`

\[
\text{raw\_bps} = \left(\frac{\text{fair\_now}}{\text{fair\_at\_fill}} - 1\right) \times 10\_000
\]
\[
\text{signed} = \begin{cases}
-\text{raw\_bps} & \text{if bought} \\
+\text{raw\_bps} & \text{if sold}
\end{cases}
\]

Negative signed = toxic (adverse selection).

### 3.7 `MarkoutGuard`

| Field / method | Behavior |
|----------------|----------|
| `adverse_bps_bid`, `adverse_bps_ask` | Per-side extra half-spread (bps), cap 100 each |
| `rolling_adverse` | Deque of adverse magnitudes (cap `MM_MARKOUT_ROLLING_WINDOW`, default 24) |
| `last_horizon_markouts` | Last signed markout per horizon sec (for metrics) |
| `on_loop_decay(decay)` | Multiply side extras by `MM_MARKOUT_DECAY` (0.85); zero if < 0.01 |
| `observe_fill_markout(...)` | If `horizon_sec` set: record horizon sample only. If `horizon_sec` is **None** and `signed < −threshold`: push rolling adverse; add `widen_bps` to bid (buy fill) or ask (sell fill) when `side_aware`, else both |
| `rolling_adverse_bps()` | Mean of rolling adverse magnitudes |

**Important:** Immediate widen uses **worst signed markout across all horizons** after waits complete (`main.rs` spawn), not a single horizon.

### 3.8 `StrategyConfig` (env-driven)

Key fields loaded via `from_env` / `from_env_for_symbol` (per-symbol overrides for `MM_INV_ONE_SIDED_RATIO_{SLUG}`, `MM_INVENTORY_SKEW_BPS_{SLUG}`):

| Method | Formula |
|--------|---------|
| `fee_floor_bps()` | `2 × maker_fee_bps + adverse_buffer_bps` |
| `as_half_spread_bps(vol_bps, kappa)` | `σ = vol_bps/10_000`; `vol_term = 0.5 × γ × σ² × 10_000`; `arrival = (2/γ) × ln(1 + γ/κ) × as_arrival_scale`; return `vol_term + arrival` |

Note: `MM_HALF_SPREAD_BPS` is **not** the primary half-spread in `compute_quote`; it is a **per-side stress floor** when markout extras are active on that side.

### 3.9 Private helpers

| Function | Role |
|----------|------|
| `inventory_spread_mult(inv, max_inv, soft_ratio, widen)` | If `|inv| > max×soft_ratio`, linear ramp to `1 + widen` at hard cap |
| `reservation_price(fair, inv_ratio, skew_bps, vol_bps, risk_aversion, boundary_skew_bps, book_skew_bps)` | `fair × (1 − skew_component − vol_penalty − boundary + book)` where `skew_component = inv_ratio × skew_bps/10_000`, `vol_penalty = inv_ratio × risk_aversion × (vol_bps/10_000)²`, `boundary = inv_ratio³ × boundary_skew_bps/10_000` |
| `effective_order_qty(base, inv_ratio, shape)` | `base × max(0.15, 1 − shape × |inv_ratio|)` |

### 3.10 `compute_quote(...)` — end-to-end quote math

**Inputs:** config, fair, tick, inventory, max_inv, base_qty, vol_bps, kappa, markout extras per side, rolling_adverse, last_fair, optional `BookTop`.

**Steps:**

1. `inv_ratio = clamp(inventory/max_inv, −1, 1)`.
2. **Fair jump:** `|fair/last_fair − 1| × 10_000 ≥ MM_FAIR_JUMP_BPS` → `fair_jumped`; add `MM_FAIR_JUMP_WIDEN_BPS` to half-spread.
3. **Base half-spread:**  
   `as_half = cfg.as_half_spread_bps(vol_bps, kappa)`  
   `fee_half = fee_floor_bps / 2`  
   `min_half = MM_MIN_HALF_SPREAD_BPS`; if `MM_MARKOUT_DYNAMIC_MIN` and rolling adverse > 0:  
   `min_half = max(min_half, fee_half + rolling_adverse/2 + markout_min_buffer/2)`  
   `half_spread = max(as_half, fee_half, min_half)` + jump widen.
4. **Calm tighten:** if no markout extra and `vol_bps ≤ calm_vol_threshold`: interpolate half_spread toward `max(fee_half, min_half_spread)` by `(1 − calm_spread_discount)`.
5. **Inventory spread widen:** `half_spread × inventory_spread_mult(...)`.
6. **Clamp:** `[MM_MIN_HALF_SPREAD_BPS, MM_MAX_HALF_SPREAD_BPS]`.
7. **Asymmetric halves:**  
   `bid_half = half_spread × (1 + max(inv_ratio,0) × asym) + markout_extra_bid`  
   `ask_half = half_spread × (1 + max(−inv_ratio,0) × asym) + markout_extra_ask`  
   If side has markout extra: `bid_half ≥ MM_HALF_SPREAD_BPS` (stress floor).
8. **Reservation** via `reservation_price`.
9. **Prices:**  
   `bid = round_to_tick(reservation × (1 − bid_half/10_000))`  
   `ask = round_to_tick(reservation × (1 + ask_half/10_000))`  
   Post-only clamp: bid < fair, ask > fair (tick-adjusted).
10. **Side flags:** `quote_side_flags` + optional fair-jump defensive (drop bid on up-jump, ask on down-jump).
11. **Qty:** `effective_order_qty`.

**Output:** `QuotePlan { fair, reservation, bid, ask, spread_bps, vol_bps, effective_kappa, as_half_bps, order_qty, place_bid, place_ask, fair_jumped }`.

### 3.11 Utilities

| Function | Role |
|----------|------|
| `quotes_within_tolerance(prev_bid_ask, bid, ask, tol_bps)` | Skip requote if both sides drift ≤ `MM_REQUOTE_TOL_BPS` vs mid |
| `round_to_tick(price, tick)` | Exchange tick rounding |
| `quote_side_flags(inventory, max_inv, one_sided_ratio)` | Hard cap: only reduce side; soft cap at `max × one_sided_ratio`: stop adding on heavy side |

---

## 4. Markout guard — implementation details (code path)

### 4.1 Configuration (typical from `mm-tuning.env`)

- `MM_MARKOUT_HORIZONS_SEC=1,5,30`
- `MM_MARKOUT_THRESHOLD_BPS=3`
- `MM_MARKOUT_WIDEN_BPS=4`
- `MM_MARKOUT_DECAY=0.85`
- `MM_MARKOUT_SIDE_AWARE=1` (default in `main.rs`)
- `MM_MARKOUT_DYNAMIC_MIN=1` — feeds `rolling_adverse_bps` into min half-spread

Devnet overlay tightens threshold/widen and disables calm discount (`mm-tuning-devnet.env`).

### 4.2 Runtime sequence (`main.rs`)

On inventory change (fill):

1. Record `fair_at_last_quote` (or current fair) as `f0`.
2. Spawn async task for each horizon `h`: sleep until `h` seconds elapsed since fill start; probe fair via `fair_at_horizon` (cached probe, external book, or Binance spot).
3. Log `MM_MARKOUT_HORIZON { horizon_sec, signed_bps, ... }`.
4. Track **worst** (most negative) signed markout across horizons.
5. For each horizon sample, call `observe_fill_markout(signed, threshold, 0, Some(h), ...)` — **metrics only**, no widen.
6. After all horizons, if `worst_signed < −threshold`, call `observe_fill_markout(worst, threshold, widen_bps, None, bought, side_aware)` — **applies widen** and rolling adverse entry.

Per main loop **before** quote:

- `markout_guard.on_loop_decay(markout_decay)`.
- Pass `extra_spread_bid_bps`, `extra_spread_ask_bps`, `rolling_adverse_bps()` into `compute_quote`.

### 4.3 Interaction with spread stack

- Side extras add directly to asymmetric half-spreads.
- When extra > 0 on a side, that side’s half-spread is floored at `MM_HALF_SPREAD_BPS` (stress floor).
- Rolling adverse raises **dynamic minimum** half-spread (symmetric base before asymmetry).

---

## 5. Eval and tuning (`mm-eval.py`)

### 5.1 Inputs

- Tail of bot log: `MM_METRICS {json}` rows (default last 500 lines).
- Markout samples via `mm_markout.parse_markout_samples` (from `MM_MARKOUT_HORIZON` lines).
- Existing tuning file (`MM_TUNING_ENV`, e.g. `artifacts/mm-tuning.env`).

### 5.2 Guards (do not undo edge)

| Condition | Action blocked |
|-----------|----------------|
| `avg_30s markout < −5 bps` | Spread **tighten** |
| `buy_avg_30s < −15 bps` | Spread tighten **and** size scale-up |
| `markout_extra > 2` | Implicit hold on aggressive tighten |

### 5.3 Tune rules (BTC-focused when `tune_spread`)

- No fills + avg spread > 45 bps → decrease `MM_HALF_SPREAD_BPS` by 3 (respect min half from fee floor).
- High avg vol (> 25 bps) → bump `MM_VOL_SPREAD_MULT` (see §9 — **Rust does not apply this knob**).
- At cap with fills → increase `MM_INVENTORY_SKEW_BPS` (+3, cap 30).
- uPnL < −50 → widen `MM_HALF_SPREAD_BPS` (+5, cap 80).
- ≥3 fills in window → widen +3.
- Over max inventory → shrink order qty 10%.

### 5.4 Size scaling (`evaluate_size_scaling`)

Requires ≥8 markout samples; uses last 50 signed markouts:

- Scale **up** 5% if avg > 1 bps, ≥55% positive, markout_extra < 2, below 2× base qty.
- Scale **down** 10% if avg < −5 bps.
- Block scale-up if buy-side avg < −15 bps.

Exit code **2** if tuning changed fields that require bot restart (spread/skew/vol mult/loop or size change).

### 5.5 Env files

| File | Purpose |
|------|---------|
| `mms/mm-tuning.env` | Seed defaults |
| `mms/artifacts/mm-tuning.env` | Testnet eval output |
| `mms/artifacts/devnet/mm-tuning.env` | Devnet eval output |
| `mms/mm-tuning-testnet.env` | Runtime overlay (SOL de-risk, etc.) |
| `mms/mm-tuning-devnet.env` | Thin-book + SOL guardrails (not eval-written) |

---

## 6. Reuse in our CEX `STRATEGY.md`

| Component | Verdict | Notes |
|-----------|---------|-------|
| `compute_quote` + `StrategyConfig` env mapping | **Must reuse** | Core AS + reservation + asym + clamps |
| `signed_fill_markout_bps` + multi-horizon worst-case widen | **Must reuse** | Extend horizons per R5 (5s/30s/5m) |
| Side-aware markout extras (`MarkoutGuard`) | **Must reuse** | Proven fix for SOL buy toxicity |
| `quote_side_flags` + boundary skew + size shaping | **Must reuse** | Inventory risk |
| Fair jump widen + defensive one-sided | **Must reuse** | Toxic flow defense |
| `fee_floor_bps` + dynamic min from rolling adverse | **Must reuse** | Break-even + markout-aware floor |
| `KappaEstimator` + tape blend + clamps | **Should reuse** | Tune `κ` on CEX fill tape |
| `VolTracker` + `horizon_vol_bps` | **Should reuse** | Align horizon with expected hold time |
| `resolve_fair_price` microprice blend | **Should reuse** | On **native** L2 only on CEX |
| `quotes_within_tolerance` | **Should reuse** | Map to amend hysteresis + max age |
| `FillEconomics` + venue reconcile | **Should reuse** | Debug PnL; exchange remains truth |
| Pyth oracle + external HL/Binance fair | **Replace** | §4 native L2 + Binance reference |
| GoDark REST/HPKE, `symbol_id` | **Replace** | CEX REST/WS adapters (R3) |
| 15 s primary loop | **Replace** | Event-driven + `MM_REQUOTE_TOL_BPS` as max drift |
| `mms/bot/pricing.py` | **Skip** | Superseded by Rust |
| `MM_VOL_SPREAD_MULT` as tuned spread lever | **Skip** (until wired) | Loaded in config, **unused** in `compute_quote` |
| Timescale ingest / GoDark-specific daemons | **Skip** initially | Replicate metrics in CEX stack later |

---

## 7. Concrete merge list into `STRATEGY.md`

| STRATEGY section | Merge from GoDark export |
|------------------|-------------------------|
| **§4 Fair value** | Microprice blend formula; fair-jump threshold behavior; drop oracle/external book for CEX-native stack |
| **§5 Parameter estimation** | `VolTracker.vol_bps`, `horizon_vol_bps`, `KappaEstimator`, `estimate_kappa_from_trade_prices`, effective κ blend weights |
| **§6 Quote model** | Full `compute_quote` pipeline: AS half, fee/dynamic min, calm discount, inventory spread mult, reservation terms, asym halves, post-only clamp, tick round |
| **§7 Inventory** | `quote_side_flags`, `effective_order_qty`, over-cap unwind pattern (reduce-only IOC cross) |
| **§8 Order management** | `quotes_within_tolerance`; cancel-before-place; do not stack if cancel fails; stagger via `MM_LOOP_OFFSET_SEC` |
| **§9 Risk** | Over-cap cancel at 1.05×; rate-limit gate; min notional floor helpers from `lib.rs` |
| **§10 P&L / feedback** | `FillEconomics.on_fill`; `MM_METRICS` schema; markout logging; eval guards from `mm-eval.py` |
| **§12 Parameters** | Seed table from `mm-tuning.env` (fee, AS γ/κ, markout, skew, one-sided ratios) adjusted for CEX fee tier |

---

## 8. Porting guide vs Rust code — discrepancies

| Topic | Porting guide | Actual code |
|-------|---------------|-------------|
| Primary half-spread | Reads like `MM_HALF_SPREAD_BPS` drives width | **AS term is primary**; `MM_HALF_SPREAD_BPS` is stress floor when markout active on a side |
| `MM_VOL_SPREAD_MULT` | Implied vol-driven widening via eval | Field exists in `StrategyConfig` but **never multiplied** in `compute_quote`; eval changes may be no-ops |
| Markout widen timing | Single multi-horizon worst | Matches code: per-horizon logging first, one widen from **worst** signed after all horizons |
| `pricing.py` | Not emphasized | **Legacy** simpler quotes; production path is Rust only |
| Inventory vol penalty | Described as γσ²q | Code uses `inv_ratio × risk_aversion × (vol_bps/10_000)²` added in **reservation** (not identical to textbook AS reservation term) |
| Book skew scaling | `f(imbalance) × cap` | Explicit: `imbalance_skew_bps × MM_BOOK_IMBALANCE_SKEW_BPS / 6`, clamped |

---

## 9. Top implementation notes for CEX engineers

1. Copy **`compute_quote`** semantics exactly before optimizing; unit tests in `strategy.rs` are the spec.
2. Implement **markout async task** equivalent on fill events from user stream (not only clock loop).
3. Wire **`MM_VOL_SPREAD_MULT`** in CEX code or drop from eval — do not tune a dead knob.
4. Map **post-only** + tick rounding to venue-specific flags (R3).
5. Keep **separate tuning files** per environment/symbol class as in GoDark ops.

---

## 10. Related paths in repo

- Export tree: `resource/godark-mm-bot/`
- Target design: `STRATEGY.md`
- Research: `resource/01`–`05`
