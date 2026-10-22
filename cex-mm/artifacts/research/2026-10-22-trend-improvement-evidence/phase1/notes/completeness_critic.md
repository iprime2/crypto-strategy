# Completeness critic: what phase1_plan.md and master_candidates.md miss (2026-10-21)

Read-only pass. Read in full: `phase1_plan.md`, `verify_data.md`, `notes/phase1_plan_notes.md`, `cex-mm/scripts/trend_backtest.py`,
`cex-mm/scripts/trend_paper.py`, `tools2/sim.py::simulate`, resource/07 (tax table, risk table, kill criteria, 8-week gates),
`backtest_results.md` T6b-T6e, the daily/weekly paper-book journals (scratchpad copies). Skimmed: master_candidates.md (headings,
header, appendix B), all nine notes files (headings + search logs), `adv_ops/liq_check.py` head.
Web: 7 WebSearch calls (extended), 1 WebFetch (guides.delta.exchange: ENOTFOUND). Fetched from data.binance.vision: 12 monthly 5m
kline zips (BTC, ADA; 2024-01..03, 2025-09..10, 2026-03) and `BTCUSDT-metrics-2021-01-01.zip` into `notes/critic_dl/` (isolated dir);
HEAD probes. Delta API: `/v2/history/candles` last-trade vs `MARK:` daily closes for ADAUSD, BCHUSD (2026-10-08..20).
Script: `notes/critic_tools/drift5m.py` (run with `python3 -I`).

## Local measurements (VERIFIED, my own computation)

### 00:00 -> 00:05 UTC drift on Binance 5m klines (6 months, 177 days per coin)
```
ADAUSDT  00:00->00:05 close      n=177 mean=+1.40 bps sd=31.16 mean|r|=21.27 median|r|=15.29 t=+0.60
ADAUSDT  12:00->12:05 (control)  n=183 mean=-0.43 bps sd=32.64 mean|r|=20.15 median|r|=14.25 t=-0.18
BTCUSDT  00:00->00:05 close      n=177 mean=+0.18 bps sd=15.23 mean|r|= 9.65 median|r|= 6.35 t=+0.16
BTCUSDT  12:00->12:05 (control)  n=183 mean=+1.23 bps sd=19.31 mean|r|=11.58 median|r|= 9.20 t=+0.86
```
Unconditional mean ~0 (not a cost in expectation on this sample) but the per-order noise (sd 15-31 bps) is 2-4x the 7.31 bps
cost and the median |drift| on ADA (15 bps) exceeds the kill-3 threshold (2 x 7.31 = 14.6 bps). The backtest fills at the
00:00 close; the VM book fills at 00:05:13-00:05:29 (journal, 11 of 11 rebalances) by walking the L2 book; the paper book's
"model" line uses the same 00:05 mids on both sides, so the drift is invisible in paper-vs-model. Conditional-on-trade-direction
mean not measured (needs the full-sample run proposed below).

### Delta last-trade vs MARK daily closes (api.india.delta.exchange, 2026-10-08..20)
ADAUSD: diffs -15.9..+15.6 bps (|diff| median ~7 bps); BCHUSD: -7.3..+10.2 bps. `MARK:<sym>` 1d candles exist. ADAUSD product:
initial_margin 1 %, maintenance_margin 0.5 %, default_leverage 100, annualized_funding 10.95 (the 0.01 %/8 h default),
funding_method mark_price, liquidation_penalty_factor 0.2.

### Binance futures metrics archive
`data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-2020-12-01.zip` and `...2021-01-01.zip` -> HTTP 200; columns
create_time, symbol, sum_open_interest, sum_open_interest_value, count_toptrader_long_short_ratio,
sum_toptrader_long_short_ratio, count_long_short_ratio, sum_taker_long_short_vol_ratio (5-minute rows).
`ADAUSDT-metrics-2021-06-01.zip` -> 404 (coverage is per-symbol and partial; must be listed before use).
5m klines: `.../monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2020-06.zip` -> 200.

### Paper-book journals (scratchpad copies)
Daily book: 11 rebalances 2026-10-08..18, all at 00:05:13-00:05:29 except the 16:37 first run; gross 0.64x -> 0.11-0.20x;
dust orders every day (ADA +-1 contract = $0.2 notional at 6-9 bps slippage); paper equity 996.41 vs model 995.31 on 10-18.
Weekly book: 1 rebalance (2026-10-19 00:05:29), gross 0.08x, 6 orders.

### Prior trials on the same data (for the haircut)
`backtest_results.md`: 20 distinct T-sections (T1..T7 with a-m sub-cells, the 18-cell grid, R2b 7 x 3); Phase 1 smoke/diag runs:
`phase2/{sig_continuous,tranche7_smoke,vol_ewma32,portfolio_vol}.json`, `sim/funding_grid.txt`, `sim/funding_bucket_diag.txt`,
`sim/passive_out.txt`, `verify_tools/{cost2_diag,ovl1_thresholds,ovl_states}_out.txt`, `diag_sizing*.txt`, `sizing_diag_out.txt`.
Parameters the plan calls "fixed from the literature" that were in fact chosen after a local run: COST-2 m = 0.75 ("the only floor
whose position-path effect never went negative in cost2_diag_out.txt"), SIG-2 d = 1 ("the d = 2 cousin already ran negative"),
OVL-2 30 d / 30 % ("the 9-coin grid's cells were picked in-sample (7 of 14 below baseline)"), TIME-1 K = 7 after
`tranche7_smoke.json` (+0.13 on A). The plan's own text admits each.

## Web facts (all [UNVERIFIED]: snippets only; hosts blocked)
- Delta India user guide (guides.delta.exchange/delta-exchange-india-user-guide, ENOTFOUND on fetch; search snippet): for
  futures/options "users never really interact with crypto ... balances and unrealised profits remain in INR, so the 1 % TDS and
  30 % flat tax are not applicable"; applicable on spot. Third-party pages claim the opposite (1 % TDS "on all trades"). No
  statute or CBDT text found. Resource/07 Gate 0 (CA opinion) already covers this; the plan has no tax line at all.
- Bollerslev, Hood, Huss, Pedersen, "Risk Everywhere: Modeling and Managing Volatility", RFS 2018
  (https://public.econ.duke.edu/~boller/Published_Papers/rfs_18.pdf; AQR page): 50+ futures, high-frequency realized vol,
  panel RV models, risk targeting; utility gains from better vol forecasts. Numbers not opened.
- Liu, Patton, Sheppard 2015 "Does anything beat 5-minute RV?" (memory, not searched directly).
- "Comparing Daily Volatility Proxies for Cryptocurrency Forecasting Under a Unified Intraday Construction Framework",
  Mathematics 14(10):1728, 2026 (https://doi.org/10.3390/math14101728): calendar-boundary-augmented RV best under QLIKE.
- Perpetual-futures papers (arXiv 2212.06888 "Fundamentals of Perpetual Futures"; Ackerer-Hugonnier-Jermann "Perpetual Futures
  Pricing", NBER w32936): total return = price + funding components; funding settled 00:00/08:00/16:00 UTC on CeFi. No study of a
  00:00 UTC price drift found; an MDPI 2026 microstructure paper reports spread peaks ~2 h after settlement.
- MOP 2012 (elmwealth PDF / NYU Stern PDF): TSMOM signal on the excess-return total-return index of the most liquid contract.
- Hong & Yogo 2012 JFE "What does futures market interest tell us about the macroeconomy and asset prices?": OI growth predicts
  commodity futures returns (memory; not opened).
- Deflated Sharpe (Bailey & Lopez de Prado, SSRN 2460551): "honesty depends entirely on honestly counting N"; hold-out does not
  remove snooping when many strategies hit the same hold-out.

## The ten items (ordered) are in the structured output; summary of each "how to add"
1 Tax line per variant (T6b machinery into sim.simulate; per-segment / per-coin-day VDA / slab-net; tie-breaker for class II).
2 Decision->fill drift: full-sample 5m diagnostic conditional on trade direction; redefine kill-3 on fill-vs-arrival; drift line.
3 Haircut N_eff >= 60; declare class before the run; parameters seen in local runs flagged; orders metric defined on rounded lines.
4 Phase 3 gate pre-registered on implementation fidelity, not Sharpe.
5 Intraday-low equity and on-venue leverage lines (hourly lows on disk; gross/0.30 vs 2x); reconcile D's 2x cap with resource/07.
6 Delta-level funding stress line on A/B (0.01 %/8 h floor on capped majors; per-coin Delta/Binance ratio).
7 SZ-17 hourly realized-variance vol estimator (EWMA COM 60 of daily RV from 24 hourly returns), class II.
8 SIG-13 trend on the funding-adjusted total-return index (MOP construction), class I, cheap.
9 D-2 open-interest crowding diagnostic from the Binance metrics archive; conditional cell only.
10 Live-signal data quality: MARK candles for the live rule; explicit catch-up rule for a missed Monday.
