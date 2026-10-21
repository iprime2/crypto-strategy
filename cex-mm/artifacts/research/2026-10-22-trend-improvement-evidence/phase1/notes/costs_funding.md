# Angle: costs, funding and execution on Delta India — research notes

Date 2026-10-21 (Delta API snapshots ~04:00 UTC). Subagent of the strategy-improvement workflow; read-only on the repo, no orders placed.

## 0. Method and what could not be done

- **Web search was unavailable for this whole turn**: the first four WebSearch calls returned "web search budget is used up (200 per turn, shared by every agent)". No search query of this angle ran. Everything below therefore comes from (a) the Delta India public REST API (fetchable), (b) raw.githubusercontent.com (fetchable: pysystemtrade docs and defaults), (c) the repo's own evidence and research notes (which themselves cite earlier search snippets), (d) my own simulations on the cached Binance 2020-05..2026-09 and Delta 2024-08..2026-10-12 data, and (e) memory, tagged [MEMORY, UNVERIFIED].
- `docs.india.delta.exchange` does not resolve (ENOTFOUND). Delta's fee page, VIP/tier page, funding-formula page and support articles were not readable (same as the 2026-10-13 session).
- Simulations are **indicative, in-sample and not pre-registered**. They reuse `cex-mm/scripts/trend_backtest.py::target_weights` unchanged and the repo's cost model (taker 5.31 + 2 bps slippage per side, funding charged daily). Whole-contract runs use today's contract values over the whole history, as the repo's `--capital` mode does. Scripts and raw outputs: `/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research2/sim/` (`sim_costs.py`, `delta_out2.txt`, `binance_out.txt`, `funding_grid.txt`, `funding_bucket_diag.txt`, `passive_exec.py`, `passive_out.txt`). Downloaded data: `../delta_data/` (daily and hourly candles), `../fund_*.json` (hourly FUNDING candles 2025-01-01..2026-10-21), `../products.json`, `../tickers.json`, `../ob_*.json`.

## 1. Delta India venue facts (API, verified 2026-10-21 unless tagged)

### 1.1 Fees
- `/v2/products?contract_types=perpetual_futures` (237 products): all nine perps have `maker_commission_rate 0.0002`, `taker_commission_rate 0.0005` (2 / 5 bps before tax). **Verified.**
- After 18% GST: 2.36 / 5.90 bps. The repo's 2.12 / 5.31 bps equals 0.018% / 0.045% × 1.18, i.e. the base schedule with a 10% (referral) discount then GST — arithmetic from the 2026-10-13 note `risk_execution_india_regime.md` KQ2 [SYNTHETIC]. GST-on-fee source cited there: Outlook Business spotlight piece https://www.outlookbusiness.com/spotlight/news-wire/how-delta-exchange-india-makes-crypto-trading-simple-and-affordable [UNVERIFIED]; BrokerListings review https://brokerlistings.com/scams/delta-exchange [UNVERIFIED].
- Tiers / VIP / maker rebate / referral size: **not found**. No source read in this or the 2026-10-13 session shows a retail maker rebate on Delta India. CLAUDE.md's "passive quoting cannot beat fees without a rebate" stands.
- Post-only: Delta's order API accepts `post_only` (and `time_in_force` gtc/ioc/fok). **Verified in repo code** `cex-mm/quote-bot/mm-delta/src/rest.rs` (`place_limit_post_only`, `edit_post_only`, IOC reduce-only path), used live on mainnet by the MM bot (`2026-10-13-live-run-pickoff.md`).

### 1.2 Funding mechanics
- Product fields (BTCUSD, same on all nine): `funding_method mark_price`, `product_specs.rate_exchange_interval 28800`, `expiry_interval 28800`, `funding_twap_linear_weighted_enabled true`, `funding_clamp_value 0.05`, `annualized_funding "10.95"`, `basis_factor_max_limit "10.95"`, `impact_notional 1000000`, `impact_size 10000`, `price_band 5`. **Verified fields; meaning of `funding_clamp_value` unverified** (observed alt extremes of ±0.2%/8h show it is not a ±0.05%/8h cap on the charged rate).
- Settlement stamps: hourly `FUNDING:<sym>` candles change value only at 00:00, 08:00, 16:00 UTC (BTC: 305 / 309 / 291 of 905 changes 2025-01..2026-10); the value is constant for the eight hours after a stamp. So funding is exchanged at **05:30 / 13:30 / 21:30 IST** and the hourly candle at a stamp is the rate charged for that interval. **Verified from data**; matches the Delta support article 80001183756 cited by the repo (https://www.delta.exchange/support/solutions/articles/80001183756-update-on-funding-exchange-schedule-for-perpetual-contracts) [UNVERIFIED page] and `resource/07` §Execution.
- Units: candle values are **percent per 8 h** (0.01 = 1 bp per interval = 10.95%/yr), as the repo already assumes (`trend_backtest.load_delta`: `/100*3`).

### 1.3 Realized Delta funding 2025-01-01..2026-10-21 (1,975 settlement stamps per coin; long pays positive)

| coin | mean %/8h | ann. %/yr | 2025 | 2026 YTD | % stamps exactly 0.0100 | % negative | % above 0.0100 | max | min |
|---|---|---|---|---|---|---|---|---|---|
| BTC | 0.00738 | **8.09** | 8.12 | 8.04 | 61.4 | 8.8 | **0.0** | 0.0100 | −0.0801 |
| ETH | 0.00707 | **7.75** | 9.39 | 5.70 | 62.3 | 9.6 | 0.1 | 0.0146 | −0.0250 |
| XRP | 0.00495 | 5.42 | 2.97 | 8.48 | 46.5 | 22.0 | 2.9 | 0.1548 | −0.0441 |
| BNB | 0.01061 | **11.62** | 4.79 | 20.12 | 63.8 | 12.1 | 19.6 | 0.1476 | −0.1165 |
| ADA | −0.00206 | −2.26 | −3.34 | −0.90 | 54.1 | 37.0 | 2.7 | 0.1175 | −0.1995 |
| LTC | −0.00204 | −2.24 | −5.80 | 2.20 | 26.0 | 57.2 | 7.3 | 0.1094 | −0.1144 |
| LINK | −0.00053 | −0.58 | −0.56 | −0.61 | 28.7 | 49.8 | 1.9 | 0.1737 | −0.0518 |
| DOGE | 0.00406 | 4.44 | −7.52 | 19.33 | 15.8 | 46.8 | 22.2 | 0.1261 | −0.0371 |
| BCH | −0.00363 | −3.98 | −17.29 | 12.58 | 48.8 | 40.1 | 6.6 | 0.0947 | −0.0926 |

- BTC never printed above 0.0100 in 22 months and ETH did on 0.1% of stamps: **0.01%/8h (10.95%/yr) is an effective cap for the majors** (consistent with `basis_factor_max_limit 10.95`). The alts are not capped there (observed up to +0.17%/8h). The 2026-10-13 memo's "61–86% of intervals at the cap" is reproduced (61–64%).
- Share of time the trailing-7-day mean exceeds 30%/yr: BTC/ETH 0%, XRP 0.9%, ADA 1.1%, LINK 1.7%, LTC 3.4%, BCH 6.6%, BNB 8.8%, DOGE 15.1% (>50%: BNB 4.9%, BCH 3.6%, DOGE 2.2%, others ≤1.3%).
- Current (2026-10-21 04:00 UTC, `/v2/tickers`): BTC 0.00495, ETH 0.00309, XRP/LTC/LINK/BNB/BCH 0.0100, DOGE 0.0314, ADA −0.00034 %/8h.
- Strategy-level funding bill (simulated with the repo rule): Delta 2024-08..2026-10 daily TV0.40 **1.86%/yr of equity** (fees 1.08%), weekly TV0.25 **1.04%** (fees 0.24%); Binance 2020-26 3.43% / 2.10% (the Binance series includes 2021's 30–100% alt funding). Funding is 1.7–4x the fee line on Delta, 3–8x on Binance.

### 1.4 Liquidity and spreads (2026-10-21 ~04:00 UTC)
- `/v2/l2orderbook/<sym>?depth=5` spreads in bps: **BTC 0.06, ETH 0.20, BNB 0.41, XRP 1.50, LINK 2.43, LTC 3.23, DOGE 3.67, BCH 4.21, ADA 9.85**. Top-of-book sizes (contracts): BTC 4,836 / 2,152 (≈$400k / $178k), ETH 5,541 / 7,083, BNB 132 / 260, XRP 15,490 / 5,605, ADA 32,144 / 47 (ask ≈ $10), LTC 888 / 1,664, LINK 5,020 / 3,570, DOGE 1,543 / 3,187, BCH 1,431 / 2,708.
- `/v2/tickers` 24h turnover (USD): BTC 1,056M, ETH 707M, XRP 11.9M, DOGE 3.5M, BNB 2.3M, LTC 1.7M, LINK 1.6M, BCH 1.4M, ADA 0.78M. OI (USD): BTC 63.1M, ETH 52.8M, XRP 4.9M, LINK 1.27M, DOGE 1.04M, LTC 0.95M, ADA 0.70M, BNB 0.49M, BCH 0.37M.
- Realized taker slippage vs mid in the daily paper book (34 fills 2026-10-08..18, clips of 1–246 contracts, walked through the live L2): BTC 0.03, ETH 0.10, BNB 0.18 (0.14–0.21), XRP 0.73, LINK 0.79, DOGE 1.58 (1.19–1.80), LTC 1.62, BCH 2.18, **ADA 6.61 (5.96–8.70)** bps. The flat 2 bps model is conservative for eight coins and optimistic for ADA.
- Tick sizes (bps at current prices): BTC 0.5 → 0.06; ETH 0.05 → 0.20; BNB 0.001 → 0.013; XRP 0.0001 → 0.75; LINK 0.001 → 0.81; LTC 0.01 → 1.6; DOGE 0.000001 → 0.12; BCH 0.01 → 0.35; ADA 0.00001 → 0.45.

### 1.5 Turnover of the live paper books (local copies of the VM journals in `scratchpad/daily-book`, `scratchpad/weekly-book`)
- Daily book (TV 0.40, band 0, $1,000): 11 records 2026-10-08..10-18, 34 orders, **$1,320 traded**, fees $0.70, funding $0.18, equity 999.6 → 996.4 (model 995.3). Of the $1,320: initial build on signal day 10-07 $540; 10-08 de-risking (−2 BNB, −2 ETH, −5 DOGE, −28 XRP …) ≈ $300. Per coin: BNB $365 (3 orders: +2, −2, +1 contract = 0↔1↔2 flips of a $73 contract), LINK $176 (5), BTC $165 (+1, −1: an $83 contract flip), ETH $122, DOGE $118, LTC $112, ADA $98 (11 orders, nine of them $0–3), XRP $96, BCH $69. So ≈40% of the first 11 days' traded dollars are 0↔1 contract flips in BNB/BTC/ETH. Annualising $1,320/11 d gives 44x/yr, but that window includes the build; the 26-month Delta simulation of the same configuration gives a steady state of **14.7x/yr (fees 1.08%/yr at 7.31 bps, 566 orders/yr)**; Binance 2020-26: 15.7x/yr, 1.15%/yr.
- Weekly book (TV 0.25, band 10%, $1,000): first rebalance 2026-10-19 00:05 UTC, 6 orders, $79 traded, fees $0.04. Simulated steady state 3.4x/yr, fees 0.25%/yr, 131 orders/yr (Delta) — matches `backtest_results.md` T1/T5.

## 2. Funding-aware position rules (cost rules, not funding-as-signal)

### 2.1 What the literature says (what I could reach)
- Carver, pysystemtrade `docs/backtesting.md` (raw GitHub, **verified**): position buffering — "We compare the current position to the optimal position. If it's not within 10% (the 'buffer') then we trade to the optimal position"; forecast buffering sizes the buffer from the average absolute position; "if outside the buffer we trade to the nearest edge of the buffer, rather than going to the optimal position"; "Position inertia, or buffering, is a way of reducing trading costs"; costs are applied "according to the standardised cost in Sharpe ratio terms and the estimated turnover". `sysdata/config/defaults.yaml` (**verified**): `buffer_method: forecast`, `buffer_size: 0.10`, `buffer_trade_to_edge: True`, `use_SR_costs: False`, `multiply_roll_costs_by: 0.5`, `forecast_cap: 20.0`, `average_absolute_forecast: 10.0`. The docs make no quantitative performance claim; the book-level claim (turnover down by roughly a third at no measurable loss, and the "speed limit" of ≤ ~0.13 SR of annual costs per rule) is [MEMORY, UNVERIFIED] from *Systematic Trading* (2015), https://www.systematicmoney.org/systematic-trading.
- Carver's "cost-adjusted forecast" / holding-cost treatment in *Advanced Futures Trading Strategies* (2023) [MEMORY, UNVERIFIED]: holding costs (roll/carry) are subtracted from expected returns in SR units; for us the analogue is funding. On Delta, a BTC long pays ~8–11%/yr against ~45% vol: 0.18–0.24 SR units per unit of exposure — already above Carver's speed limit for a single rule, which is why the question matters.
- "Momentum returns net of funding" papers: **none retrieved** (no search this turn). The repo's own backtests already report funding separately (fund/yr lines), which is the number such a paper would give.
- Le (2026) "Funding-aware optimal market making for perpetual DEXs" (local PDF, `resource/01` §11.1): funding as a carry term −q·f on inventory; a market-making result, not a trend result.

### 2.2 Simulations (indicative, in-sample; 9-coin universe; unrounded weights)
Baselines: Binance 2020-05..2026-09 daily TV0.40 SR 1.25 / maxDD −21.9% / fund 3.43%/yr; weekly TV0.25 SR 1.12 / −17.0% / 2.10%. Delta 2024-08-10..2026-10-12 daily SR 0.99 / −14.1% / 1.86%; weekly 0.70 / −9.1% / 1.04%.

**(a) Skip a coin while trailing funding exceeds a threshold** (F = annualized trailing mean, W-day window):

| rule | Binance 2020-26 daily | Binance weekly | Binance 2022-26 daily | Delta daily | Delta weekly |
|---|---|---|---|---|---|
| 7d > 15% | 0.87 (fund 0.65%) | 0.90 | — | 0.55 | 0.25 |
| 7d > 20% | 1.05 | 1.10 | — | 0.73 | 0.37 |
| 7d > 30% | 1.20 | 1.24 | — | 0.97 | 0.62 |
| 7d > 50% | 1.29 | 1.13 | — | 1.05 | 0.75 |
| 14d > 30% | 1.29 (DD −14.7) | 1.23 | 0.94 | 1.00 | 0.64 |
| 14d > 40% | **1.41** (DD −16.3) | 1.26 | 0.96 | 1.05 | 0.80 |
| 14d > 50% | 1.30 | 1.13 | 0.90 | 1.08 | 0.74 |
| 30d > 20% | 1.32 | 1.19 | — | 0.56 | 0.19 |
| 30d > 30% | **1.37** (DD −14.0, binds 9.8%) | 1.19 | 0.96 (binds 1.5%) | **1.09** (binds 2.8%) | **0.83** |
| 30d > 40% | 1.22 | 1.08 | 0.91 | 1.01 | 0.73 |
| 30d > 50% | 1.14 | 0.96 | 0.84 (never binds) | 0.99 | 0.70 |
| 60d > 30% | 1.15 | 1.00 | 0.87 | 0.98 | 0.74 |
| 60d > 40% | 1.16 | 1.03 | 0.84 | 1.02 | 0.72 |
| 60d > 50% | 1.16 | 1.03 | 0.84 | 0.99 | 0.70 |

Reading: thresholds below ~30% destroy the strategy (they remove exactly the coin-days where trends are strongest); the 14–30 d windows at 30–40% improve Sharpe and drawdown on the full Binance sample but almost all of that comes from the 2021 mania/crash (post-2021 the rule binds on 0.5–2% of coin-days and adds +0.03 to +0.12 with maxDD −17.0 → −14.0); 60-day windows hurt everywhere on the full sample because they stay "off" into the post-crash recovery. 4 of 9 full-sample daily cells are positive, 5 negative: a fragile surface, one episode.

**(b) Carver-style proportional cost adjustment** `w ← w × clip(1 − F7/(SR_a × vol60), 0, 1)`: Binance daily 1.25 → 1.08 (SR_a 0.5) / 1.20 (1.0), CAGR 24.2 → 10.9 / 15.7%; weekly 1.12 → 1.06 / 1.11; Delta daily 0.99 → 0.54 / 0.84; weekly 0.70 → 0.18 / 0.55. **Harmful on both samples.**

**(c) Why**: bucket next-day gross return of coin-days with the signal on by trailing-7d funding.

| F7 bucket | Delta n / gross bps / funding bps/day / net | Binance 2020-26 n / gross / funding / net | Binance 2022-26 n / gross / funding / net |
|---|---|---|---|
| <0% | 728 / +2.0 / −3.1 / +5.0 | 1307 / +30.8 / −3.7 / +34.6 | 988 / +12.2 / −3.3 / +15.6 |
| 0–5% | 264 / +19.2 / 0.6 / +18.6 | 1429 / +19.4 / 1.0 / +18.4 | 1276 / +11.7 / 1.0 / +10.7 |
| 5–12% | 1389 / +10.6 / 2.6 / +8.0 | 4019 / +15.2 / 2.4 / +12.8 | 3325 / +7.9 / 2.3 / +5.6 |
| 12–20% | 368 / **+74.5** (t 3.1) / 4.5 / +70.0 | 1146 / **+66.7** (t 4.5) / 5.0 / +61.7 | 629 / +51.3 (t 2.9) / 4.7 / +46.5 |
| 20–30% | 163 / **+129.2** (t 3.2) / 7.1 / +122.1 | 740 / +62.2 (t 3.0) / 7.9 / +54.4 | 305 / +73.9 (t 2.6) / 6.5 / +67.5 |
| 30–50% | 200 / +31.4 / 9.4 / +22.0 | 881 / +67.5 / 11.3 / +56.2 | 201 / +23.7 / 9.1 / +14.6 |
| >50% | 48 / −8.2 / 11.0 / −19.2 | 1172 / +61.9 / 22.3 / +39.5 | 105 / +22.1 / 14.2 / +7.9 |

Funding of 12–30%/yr coincides with the best trend days (crowded longs in a rally); only the extreme tail (>30–50%) fades, and even there the Binance full sample stays net positive. So funding is a real cost (~2–3.4% of equity a year) but **not an independent one**: any rule that trims exposure in proportion to funding trims the return more than the cost. The only version worth a pre-registered test is a tail cut-out (14–30 d, 30–40%), and its decisive sample is the 24-perp ex-ante universe, where 2021 alt funding gives many more binding episodes than the hindsight 9-coin set.

### 2.3 Funding-timestamp timing
- The books rebalance at 00:05 UTC, five minutes **after** the 00:00 UTC settlement: new longs skip one interval (good); reductions have just paid one interval they could have avoided by exiting at 23:55. Saving if exits moved before the stamp: exits ≈ half of 14.7x/yr turnover × one interval (≈ daily funding/3; held-position funding ≈ 1.86%/0.19 gross/365 ≈ 2.7 bps/day → 0.9 bps per interval) ≈ 6–7 bps/yr on the daily book, ~2 bps/yr weekly, and it would require acting on a pre-close signal (23:00 hourly close), which changes the rule. **Not worth it; no candidate.**

## 3. Turnover reduction: whole contracts, bands and buffering (indicative, whole contracts, 7.31 bps/side)

Rules compared: round-to-nearest every rebalance (today's daily book); `trend_paper --band 0.10` (skip a trade smaller than 10% of its target in contracts; closes always trade); contract-space position buffering: unrounded target u (contracts), buffer B = max(b·|u|, m); hold if held ∈ [u−B, u+B]; else trade to the integer inside the band nearest to the current position (if none, round(u)); u = 0 → close.

| capital / book | rule | Binance 2020-26 SR / fees %/yr / turnover x/yr / trades/yr / maxDD | Delta 2024-26 SR / fees / turnover / trades / maxDD |
|---|---|---|---|
| $1,000 daily TV0.40 | round-nearest | 1.24 / 1.15 / 15.7 / 872 / −21.7 | 0.93 / 1.08 / 14.7 / 566 / −15.2 |
| | band 10% | 1.23 / 1.11 / 15.2 / 550 / −22.2 | 0.93 / 1.06 / 14.5 / 428 / −15.2 |
| | buffer b.10 m.50 | 1.25 / 1.03 / 14.1 / 580 / −20.9 | 0.95 / 1.02 / 13.9 / 434 / −14.9 |
| | buffer b.10 m.75 | 1.26 / 0.96 / 13.1 / 548 / −20.9 | 1.06 / 0.74 / 10.2 / 366 / −12.6 |
| | buffer b.20 m.75 | 1.23 / 0.84 / 11.6 / 501 / −21.2 | 1.10 / 0.69 / 9.5 / 354 / −11.5 |
| | **buffer b.10 m1.0** | **1.28 / 0.90 / 12.3 / 538 / −20.8** | **1.09 / 0.68 / 9.3 / 352 / −11.9** |
| | buffer b.25 m1.0 | 1.24 / 0.74 / 10.2 / 484 / −20.8 | 1.12 / 0.60 / 8.2 / 337 / −11.6 |
| | buffer b0 m1.0 | 1.26 / 0.96 / 13.2 / 697 / −21.7 | 1.06 / 0.70 / 9.6 / 409 / −12.2 |
| $2,500 daily | round-nearest | 1.24 / 1.15 / 15.7 / 1083 | 0.97 / 1.07 / 14.7 / 726 |
| | band 10% | 1.25 / 1.09 / 14.9 / 564 | 1.00 / 1.05 / 14.4 / 465 |
| | buffer b.10 m1.0 | 1.25 / 0.94 / 12.9 / 606 | 1.03 / 0.84 / 11.5 / 464 |
| | buffer b.25 m1.0 | 1.25 / 0.74 / 10.1 / 536 | 1.07 / 0.71 / 9.8 / 430 |
| $5,000 daily | round-nearest | 1.25 / 1.14 / 15.7 / 1262 | 1.00 / 1.08 / 14.7 / 857 |
| | band 10% | 1.25 / 1.08 / 14.7 / 550 | 1.02 / 1.04 / 14.2 / 471 |
| | buffer b.10 m1.0 | 1.26 / 0.94 / 12.9 / 655 | 1.02 / 0.89 / 12.2 / 494 |
| | buffer b.25 m1.0 | 1.25 / 0.72 / 9.9 / 569 | 1.06 / 0.72 / 9.9 / 451 |
| $1,000 weekly TV0.25 | round-nearest | 1.10 / 0.26 / 3.56 / 188 / −17.4 | 0.79 / 0.25 / 3.42 / 138 / −9.5 |
| | band 10% (design) | 1.10 / 0.26 / 3.53 / 172 / −17.4 | 0.79 / 0.25 / 3.41 / 131 / −9.5 |
| | buffer b.10 m.75 | 1.11 / 0.21 / 2.84 / 154 / −18.7 | 0.72 / 0.17 / 2.38 / 107 / −9.5 |
| | buffer b.10 m1.0 | 1.09 / 0.19 / 2.63 / 147 / −20.0 | 0.63 / 0.14 / 1.97 / 100 / −9.0 |
| $2,500 weekly | band 10% | 1.10 / 0.25 / 3.48 / 188 | 0.70 / 0.24 / 3.31 / 152 |
| | buffer b.10 m.75 | 1.12 / 0.23 / 3.10 / 188 | 0.70 / 0.21 / 2.86 / 148 |
| $5,000 weekly | band 10% | 1.12 / 0.25 / 3.44 / 192 | 0.69 / 0.24 / 3.24 / 159 |
| | buffer b.10 m.75 | 1.11 / 0.23 / 3.11 / 197 | 0.72 / 0.21 / 2.93 / 166 |

Reading: the 10%-of-target band removes small trades (orders −37%) but not dollars (turnover −3%) because a 0↔1-contract flip is 100% of its target. A deadband of ≥0.75 contracts around the unrounded target stops those flips: daily-book fees fall by 20–45 bps/yr of equity (most at $1,000) with Sharpe flat on Binance (1.23–1.28 vs 1.24) and up on Delta (0.93 → 1.06–1.12; partly luck in a 26-month sample). For the weekly book the saving is 3–8 bps/yr and ~35 hand orders a year, Sharpe within noise (slightly negative at $1,000 on Delta for m = 1.0). Cost-sensitivity ceiling (daily, $1,000, round-nearest): 7.31 → 1.0 bps/side is SR 0.93 → 0.99 (Delta), 1.24 → 1.29 (Binance), fees 1.1% → 0.15%/yr — execution improvements are bounded at ~95 bps/yr and buffering captures 25–45 of them for free.

## 4. Passive execution for a slow rebalancer (indicative, Delta hourly candles 2025-01-01..2026-10-21)

Model: at the 00:00 UTC arrival mid, post a post-only limit at the touch (bid for buys, ask for sells; spread s from the 2026-10-21 L2 snapshot); the order fills if the price trades **through** the level by ≥ 1 tick within H hours (a queue-back order is filled once the level is swept); otherwise cross at the hour-H close. Cost vs arrival mid: filled → −s/2 + 2.12 bps; unfilled → H-hour drift + s/2 + 5.31. Taker benchmark at arrival: s/2 + 5.31. "Buy in uptrend" conditions on a positive 20-day return (what the rule does when it adds), "sell in downtrend" on a negative one (what it does when it cuts). Full table in `sim/passive_out.txt`; H = 4 h summary (fill %, expected cost bps, saving vs taker bps):

| coin (s bps) | buy | sell | buy in uptrend | sell in downtrend |
|---|---|---|---|---|
| BTC (0.06) | 98.9%, 3.33, **+2.0** | 99.1%, 2.71, **+2.6** | 99.0%, 3.18, +2.2 | 99.1%, 2.54, +2.8 |
| ETH (0.20) | 98.7%, 3.45, **+2.0** | 99.2%, 3.03, **+2.4** | 99.7%, 2.08, +3.3 | 99.7%, 2.44, +3.0 |
| XRP (1.5) | 98.6%, 2.77, **+3.3** | 97.8%, 3.84, **+2.2** | 100%, 1.37, +4.7 | 98.0%, 2.98, +3.1 |
| BNB (0.4) | 94.5%, 7.47, −2.0 | 95.5%, 6.63, −1.1 | 94.7%, 6.41, −0.9 | 96.4%, 7.24, −1.7 |
| LINK (2.4) | 93.4%, 12.7, −6.2 | 93.9%, 12.9, −6.3 | 93.5%, 12.4, −5.9 | 95.1%, 9.8, −3.3 |
| LTC (3.2) | 92.9%, 10.3, −3.4 | 94.0%, 9.2, −2.3 | 93.1%, 10.2, −3.3 | 96.4%, 5.4, +1.6 |
| DOGE (3.7) | 96.7%, 5.9, +1.3 | 95.3%, 9.0, −1.8 | 98.2%, 4.0, +3.2 | 95.5%, 9.0, −1.8 |
| BCH (4.2) | 93.7%, 10.6, −3.2 | 93.3%, 9.3, −1.9 | 93.9%, 9.4, −2.0 | 92.6%, 9.2, −1.8 |
| ADA (9.9) | 94.8%, 6.1, +4.2 | 94.0%, 12.1, −1.8 | 95.8%, 6.6, +3.7 | 94.7%, 11.8, −1.6 |

Reading: on the three deep books (BTC, ETH, XRP; 24h turnover ≥ $12M) the touch is swept within 1–4 h 97–99% of the time and the saving is close to the fee differential (5.31 − 2.12 = 3.19 bps) minus the non-fill drift: **+2 to +3 bps per side**, stable across H = 1–8 h and across trend conditioning. On the thin alts (BNB, LINK, LTC, BCH; turnover ≤ $2.3M/day) 5–7% of orders go unfilled and those cost 50–100 bps of adverse drift, so passive is **worse** than taker by 1–6 bps. Book share of BTC+ETH+XRP in the daily book's traded dollars ≈ 29% → saving ≈ 14.7 × 0.29 × 2.5 bps ≈ **11 bps/yr** before buffering, ≈ 7 bps/yr after. Caveats: hourly candles (Delta prints) stand in for the real queue; sparse-trading coins make the hourly open a noisy arrival price; no live post-only fills of the trend book exist yet. Literature [MEMORY, UNVERIFIED]: Harris & Hasbrouck (1996, JFQA, "Market vs. limit orders: the SuperDOT evidence on order submission strategy", https://doi.org/10.2307/2331388) and Frazzini, Israel & Moskowitz (2018, "Trading Costs", https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3229719) both find that patient limit/passive execution beats immediate market orders for traders without short-horizon alpha; the repo's own −3.6 bps net per fill (live MM, `2026-10-13-live-run-pickoff.md`) is a continuous-quoting result at seconds and does not transfer to a once-a-day clip that can wait hours.

## 5. Candidate list (what went into the structured result)
1. Contract-space position buffering for the daily book (b = 0.10, m = 1.0 contracts) — plausibility 5; 25–45 bps/yr at $1,000, 20 bps at $2.5–5k, Sharpe flat-to-up on both samples.
2. Passive post-only entry with 4 h taker fallback on BTC/ETH/XRP only (bot book) — plausibility 3; ≈ 7–11 bps/yr.
3. Funding tail cut-out (flat while 30 d funding > 30%/yr; alt cell 14 d > 40%) — plausibility 2; +0.10 to +0.16 SR on Binance full sample, +0.03–0.12 post-2021 and on Delta, but 5 of 9 full-sample grid cells negative; cousin of the rejected funding signal; decisive test is the 24-perp universe.
4. Carver proportional cost-adjusted forecast — plausibility 1; tested, harmful (Binance 1.25 → 1.08/1.20; Delta 0.99 → 0.54/0.84). Listed so it is not re-tested.
5. Weekly hand book: contract deadband m = 0.75 — plausibility 3; 3–8 bps/yr and ~35 fewer hand orders, Sharpe within noise.
6. Fee tier: confirm the referral tier (0.045% taker before GST) — plausibility 4 on arithmetic (0.59 bps/side = 8.7 bps/yr daily, 2 bps/yr weekly), availability unverified.
7. Cost-model calibration: per-coin measured half-spread instead of flat 2 bps — plausibility 3; accounting only.
Not a candidate: moving exits before the 00:00 UTC funding stamp (~6–7 bps/yr, needs a pre-close signal).

## 6. Sources (all URLs; verification status)
- Delta India REST API, fetched 2026-10-21: https://api.india.delta.exchange/v2/products?contract_types=perpetual_futures ; https://api.india.delta.exchange/v2/tickers?contract_types=perpetual_futures ; https://api.india.delta.exchange/v2/l2orderbook/BTCUSD?depth=5 (and the other eight) ; https://api.india.delta.exchange/v2/history/candles?resolution=1h&symbol=FUNDING:BTCUSD&start=1735689600&end=1792540800 (and 1d/1h price candles). **Verified.**
- pysystemtrade docs, Carver: https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/docs/backtesting.md ("Buffering and position inertia", "Costs") and https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/sysdata/config/defaults.yaml. **Verified.**
- Carver, *Systematic Trading* (2015) and *Advanced Futures Trading Strategies* (2023), https://www.systematicmoney.org/ — buffering turnover claim, speed limit, cost-adjusted forecasts. [MEMORY, UNVERIFIED]
- Delta support article on the funding schedule: https://www.delta.exchange/support/solutions/articles/80001183756-update-on-funding-exchange-schedule-for-perpetual-contracts (via repo `resource/07`, `backtest_results.md`). [UNVERIFIED page; schedule confirmed from data]
- Delta India user/derivatives guide: https://guides.delta.exchange/delta-exchange-india-user-guide (via repo notes). [UNVERIFIED]
- GST on Delta fees: https://www.outlookbusiness.com/spotlight/news-wire/how-delta-exchange-india-makes-crypto-trading-simple-and-affordable ; https://brokerlistings.com/scams/delta-exchange (via repo note 2026-10-13). [UNVERIFIED]
- Harris & Hasbrouck (1996) https://doi.org/10.2307/2331388 ; Frazzini, Israel & Moskowitz (2018) https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3229719. [MEMORY, UNVERIFIED]
- Le (2026) funding-aware MM for perpetual DEXs — local PDF `resource/papers/le-2026-funding-aware-optimal-mm-perpetual-dexs.pdf`, summarized in `resource/01-academic-papers.md` §11.1. **Local, read via the repo summary.**
- Repo evidence: `cex-mm/artifacts/research/2026-10-13-prop-strategy-evidence/backtest_results.md` (T1, T3c, T3k, T3l, T5), `av_runs/av_delta.txt`, `adv_ops/checks.py`, `research_notes/Crypto strategy for prop trading/risk_execution_india_regime.md`, `funding_carry_basis.md`; `resource/07-trend-rule-and-prop-trading-research.md`; `cex-mm/scripts/trend_backtest.py`, `trend_paper.py`; `cex-mm/quote-bot/mm-delta/src/rest.rs`; paper journals in the scratchpad `daily-book/journal.jsonl`, `weekly-book/paper-weekly_journal.jsonl`. **Read.**
