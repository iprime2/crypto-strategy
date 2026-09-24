# MM strategy performance review (Delta demo)

**Date:** 2026-09-23  
**Scope:** `artifacts/delta-mm-run.log`, `artifacts/economics/*.json`, dashboard counters  
**Venue:** Delta India demo · **Symbols:** BTCUSDT, ETHUSDT (SOL historically)

---

## Services (after restart this session)

- **mm-bot:** running (`run --venue delta --env testnet --loop-ms 400`)
- **Dashboard:** http://127.0.0.1:8787/ (HTTP 200)

---

## Executive summary

| Finding | Severity | Plain English |
|---------|----------|----------------|
| **~44k L3 cancel-all events** in log | High | Bot spends large fractions of time **not quoting** because demo books look “imbalanced” or jumpy vs regime thresholds. |
| **Economics: 0 realized PnL**, flat inventory | — | Cannot claim profitability yet; fills exist but **markout edge not proven**. |
| **Markout / snipe / adverse always 0** in metrics | Medium | Guards are **idle** — need sustained fills + markout pipeline export to tune spread. |
| **Margin rejects** (~65 in log) | High | Demo **isolated margin** / low **available** (~$3.6 in errors) blocked BTC two-sided quoting at times. |
| **SOL (when enabled)** | High | **~82 bps** avg lead skew vs Binance + **5k L3** events; **1 SOL** min contract — avoid on $200 demo. |
| **Only ~77–80 MM_ORDER** in full log | Medium | Very low **order placement count** vs metrics samples → much time in L3/warmup/reject loops. |

**Bottom line:** Demo run validates **plumbing** (orders can place; ETH more active than BTC). It does **not** validate economic edge. Biggest operational drags are **regime L3 on thin demo depth** and **margin mode/balance**, not “wrong fair value” alone.

---

## Hard numbers

### Economics files (bot-side)

| Symbol | Fills | Position | Realized PnL | Fees |
|--------|-------|----------|--------------|------|
| BTCUSDT | 10 | 0 | 0 | 0 |
| ETHUSDT | 46 | 0 | 0 | 0 |

Flat inventory → round-trips or accounting not yet building position; **no realized PnL** to score strategy.

### Log aggregates (full `delta-mm-run.log`)

- **MM_METRICS samples:** BTC ~8.9k, ETH ~5.3k, SOL ~5.9k (SOL from earlier runs)
- **MM_ORDER:** ~80 placements total
- **L3 cancel-all:** BTC ~17.9k, ETH ~21.1k, SOL ~5k (**44k total**)
- **When quoting (L0 samples):** spread ~24–31 bps avg; lead skew |avg| ~13–14 bps (BTC/ETH); SOL lead skew ~82 bps
- **Reject lines:** ~65 (many `insufficient_margin` / isolated margin on BTC)

### After 2026-09-23 restart (short window)

Bot resumed placing orders; dashboard showed **order_placed_total** rising and ongoing **reject_ETHUSDT** / **reject_BTCUSDT** counts — check dashboard for live counters.

---

## What is working

1. **Quote engine + Binance lead** — recent metrics show **lead skew ~0.3–0.7 bps** (BTC/ETH aligned with Binance), spread **24 bps** (BTC).
2. **Post-only orders** — MM_ORDER lines for both sides ETH/BTC after restart.
3. **Queue guard fix** (historical) — orders actually reach the exchange vs prior “metrics only” period.
4. **ETH contract sizing** — `MM_ORDER_QTY_ETHUSDT=0.01` matches Delta **0.01 ETH** per contract.

---

## What is not working / misleading on demo

1. **Regime L3 on demo L2** — `depth_ratio` on fake/thin books triggers `L3Crash` often (`MM_REGIME_L3_DEPTH_RATIO=0.05` still strict). Metrics snapshots mostly **L0** because L3 loops **skip** normal MM_METRICS regime reporting in the same way — but cancels dominate wall time.
2. **Demo ≠ mainnet liquidity** — do not tune spread capture expectations from demo fills ([liquidity-comparison-report.md](liquidity-comparison-report.md)).
3. **Margin** — errors show **~$3.6 available** vs **~$5.1 required** per side — likely **isolated margin per product** or depleted demo balance; blocks two-sided BTC.
4. **No markout evidence** — research and [STRATEGY.md](../../STRATEGY.md) require **signed markout at 1s/5s/30s** before mainnet promotion ([docs/MAINNET_GATE.md](../docs/MAINNET_GATE.md)).

---

## Improvement roadmap (prioritized)

Aligned with industry practice ([markouts as truth serum](https://aligrithm.com/markouts-the-truth-serum-of-market-making/), [toxicity scoring](https://quantmemo.com/concepts/counterparty-toxicity-scoring), [DWF dynamic spread + inventory](https://www.dwf-labs.com/news/4-common-strategies-that-crypto-market-makers-use)).

### P0 — Make demo runs usable (ops)

1. **Delta account:** Switch to **cross margin** (or allocate margin per symbol) so BTC bid+ask can rest; top up demo USD if balance is ~$3.
2. **Lower L3 sensitivity on demo only** — e.g. per-symbol `MM_REGIME_L3_DEPTH_RATIO_ETHUSDT=0.02`, raise `MM_REGIME_L3_JUMP_BPS`, or **disable L3 depth trigger on demo** via code flag (product change).
3. **Keep SOL out** of `MM_SYMBOLS` on demo until mainnet + sizing plan.
4. **Align kill switch with account size** — `MM_DAILY_LOSS_LIMIT_USD` ≪ balance on small accounts.

### P1 — Measure edge (strategy)

1. **Export markout report** — persist 1s/5s/30s signed markout per fill to `artifacts/markout/` and dashboard (validates spread vs adverse).
2. **Use markout guard for real** — when `rolling_adverse_bps` > 0, verify `markout_extra_*` widens quotes; tune `MM_MARKOUT_THRESHOLD_BPS` / `MM_MARKOUT_WIDEN_BPS`.
3. **OFI beta calibration** — regression of OFI → forward return on your venue (mm-live / research pattern); avoid fixed `MM_OFI_BETA=0.01` on all symbols.
4. **Symbol scoring** — EWMA markout per symbol; reduce size or widen on negative markout symbols ([dynamic symbol selection](https://aligrithm.com/markouts-the-truth-serum-of-market-making/)).

### P2 — Tune economics (after markout data)

1. **Spread** — 24 bps may be wide for BTC on competitive venues but **right for Delta demo noise**; on mainnet start **≥2×** backtest-calibrated half-spread ([MAINNET_GATE.md](../docs/MAINNET_GATE.md)).
2. **Lead weight** — test `lead_weight` 0.3–0.7 when Delta–Binance basis is stable vs volatile.
3. **Inventory skew** — you stay flat; when fills accumulate, verify reservation skew reduces one-sided risk without over-skewing benign flow ([toxic vs inventory](https://aligrithm.com/toxic-flow-vs-inventory-risk/)).
4. **Queue / off-touch** — already using queue guard; on mainnet consider **one tick off touch** if touch markouts are negative (research: touch quoting often loses net markout).

### P3 — Infrastructure before mainnet

1. **India VPS** — low latency to Delta India, stable uptime.
2. **Recorder + replay** — calibrate vol/kappa/spread on **mainnet L2 recordings**, not demo.
3. **4-week gate** — [docs/MAINNET_GATE.md](../docs/MAINNET_GATE.md).

---

## Research takeaways (web, 2024–2025)

- Optimize **net markout**, not fill rate — widen or pull quotes where post-fill drift is negative.
- **Toxic flow ≠ inventory risk** — skew to avoid informed flow loading, not only to flatten flat inventory.
- **Regime / vol widening** — standard for crypto MM when measurement lag or vol spikes ([DWF](https://www.dwf-labs.com/news/4-common-strategies-that-crypto-market-makers-use)).
- Educational MM stacks (e.g. [mm-live](https://github.com/Aliipou/mm-live)) emphasize **weeks of paper trading + markout validation** before live — same bar as this repo’s Slice 8.

---

## Suggested next experiments (1–2 weeks demo)

1. Fix margin → run **48h** with only BTC+ETH; log **fills/hour**, **L3/hour**, **reject rate**.
2. Add or run existing **markout export** after fills; target **positive 5s markout** on average before tightening spread.
3. Compare **spread 24 vs 32 bps** on ETH only (A/B via env) — which has better markout-adjusted score?

---

*Not investment advice. Demo PnL is not indicative of mainnet.*
