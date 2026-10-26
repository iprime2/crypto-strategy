# OPT-W1: weekly short ATM straddle on Delta India BTC/ETH options (screen spec)

Frozen 2026-10-24, before any weekly-option P&L was computed. Research only, public Delta India
data, no orders, no keys. Nothing from je-suis-tm/quant-trading is executed or imported.

## Why this is a new test (prior evidence checked)

- `options-research/README.md:12-15`: daily 12:00 UTC expiries, 24 h entry: no edge in sample or in the
  pre-registered out-of-sample test. `:17-18`: weekly/monthly expiries and delta-hedged straddles **not tested**.
- `options-research/backtest.py:10-11, :213-214`: only daily expiries with a 24 h entry were run.
- `cex-mm/artifacts/research/2026-10-13-prop-strategy-evidence/designs/D2.md:196`: "Weekly/monthly VRP untested".
- `resource/07-trend-rule-and-prop-trading-research.md:172`: daily option selling rejected (OOS BTC ~0, ETH -16.1 bps/day).
- `resource/08-trend-rule-improvement-research.md:111`: option selling on the rejected list, not re-run.
- `cex-mm/artifacts/research/2026-10-13-prop-strategy-evidence/designs/D3.md:201`: "no option selling" (owner decision).
- `cex-mm/artifacts/research/2026-10-22-prev-week-levels.md`: perp price-level rules, not options; no overlap.

## Universe and window

- Delta India BTC and ETH European options (XAUT excluded: only 2 expiries listed).
- Expiries: every Friday 12:00 UTC settlement from 2023-12-01 to 2026-10-23 (the last settled Friday before
  2026-10-24) for which at least one contract of that underlying and expiry has `launch_time <= expiry - 168 h`.
  The count per coin is Step 0 and is reported.
- The task template's "nine coins, 2020-05..2026-09" universe does not apply: Delta lists options only on
  BTC, ETH and XAUT, and Delta option history starts in Dec 2023. The template's "6 of 9 coins" clause becomes
  "2 of 2 coins"; its halves become the two sub-periods below.
- Sub-periods: A = expiries 2023-12-01 .. 2025-09-28; B = expiries 2025-09-29 .. 2026-10-23
  (the same boundary as `options-research` in-sample start 2025-09-29).

## Data (all public Delta India API, `https://api.india.delta.exchange`, cached to disk)

- Products: `/v2/products?contract_types=call_options|put_options&states=expired`, paginated with `after`, as
  `options-research/fetch_products.py` (fields symbol, type, underlying, strike, settlement_time, launch_time).
- Index 1 m candles `.DEXBTUSD` / `.DEETHUSD` (`/v2/history/candles`, resolution 1m).
- MARK 1 h candles per contract (`MARK:<symbol>`, resolution 1h), fetched from entry - 1 h to expiry.

## Rule

- Entry time E = expiry T - 7 x 86,400 s (Friday 12:00 UTC one week before expiry).
- S0 = open of the 1 m index candle stamped E; if absent, close of the latest 1 m candle in [E - 300 s, E).
  If neither exists the coin-week is skipped (counted and reported).
- Strike K: among strikes of that expiry that have BOTH a call and a put with `launch_time <= E`, order by
  |K - S0| ascending (tie: lower strike). Take the first of the 3 nearest whose call and put both have a MARK
  at E; one strike for both legs. If none of the 3 has both marks, skip the coin-week (counted).
- MARK at E for a contract = open of its 1 h MARK candle stamped E; else close of the latest 1 h candle before E
  within [E - 3,600 s, E) (as `backtest.py:103-106`). Marks must be > 0.
- No look-ahead: S0, the strike grid (launch_time <= E) and the marks are all known at E. The fill is a stated
  resting price at E: MARK x (1 - h) per leg (sold), h = 0.05 (primary, the options-research spread convention).
  Sensitivities h = 0.02 and h = 0.10 are reported and cannot be selected.
- Sell 1 call + 1 put at K, 1 unit of underlying notional per straddle. Hold to expiry. No stops, no hedge.
- Settlement S_T = mean of the closes of the 1 m index candles stamped in [T - 1,800 s, T - 60 s]
  (30-minute TWAP, as `backtest.py:79,83`); at least 20 candles required, else skip (counted).

## Costs

- Option fee per opened leg: min(0.0001 x S0, 0.035 x price) x 1.18 (GST).
- A leg that settles in the money pays 0.0001 x S_T x 1.18 again at settlement (as `backtest.py:126`).
- The leg spread cost is the haircut h above (taker-equivalent; no maker fill is assumed, so no trade-through
  condition is needed). The template's perp cost (taker 5.31 + 2 bps slippage = 7.31 bps per side) applies only
  to the delta-hedged follow-up, which is run only if this screen passes. There is no perp leg here.

## P&L per coin-week (bps of S0)

pnl = sum over the two legs of (price - intrinsic(S_T) - fee_open - fee_settle), divided by S0, x 10,000.
Pooled equal-weight weekly series: for each expiry date, the mean of the available coins' pnl.

## Reported (h = 0.05 unless labelled)

- Step 0 counts; skipped coin-weeks and reasons.
- Per coin and pooled: n, mean, sd, t = mean / (sd / sqrt(n)), win rate, worst week, max drawdown of the
  cumulative bps sum, results by calendar year, h = 0.02 and h = 0.10 means.
- Mean ATM credit (h = 0 and h = 0.05) vs mean realised |S_T / S0 - 1|, bps, per coin, in A and in B.
- The 2025-10-10 week on its own: the expiry 2025-10-10 week and, labelled, the expiry 2025-10-17 week
  (entry 2025-10-10 12:00 UTC, which contains the 10 Oct 2025 evening liquidation cascade).
- Template metrics: mean net bps per trade (trade = one coin-week straddle) with a week-cluster bootstrap
  (clusters = expiry dates; 2,000 draws; `numpy.random.default_rng(11)`; one-sided P = share of draws with
  per-trade mean <= 0); annualised Sharpe (x sqrt(365)) of the daily P&L, marked to MARK (h = 0) at 12:00 UTC
  each day between entry and expiry (entry day uses the haircut price and opening fees, the last day the
  settlement intrinsic and settlement fees, so the daily sum equals the weekly P&L; pooled daily = mean over the
  coins with a position that day); trades per year (straddles per coin per year).
- Labelled neighbour, cannot be selected: short strangle with offset m = (ATM call MARK + ATM put MARK at K) / 2
  (that week's implied move read literally as credit/2, h = 0, price units); call = listed call (launch <= E)
  nearest S0 + m, put = listed put nearest S0 - m (ties: further OTM); MARK fallback to the next strike further
  OTM, up to 3; priced and charged exactly like the straddle at h = 0.05.

## Pass rule (all required, h = 0.05). No parameter search; nothing below is tuned after results.

Proposal clauses:
1. mean > 0 for BTC and mean > 0 for ETH, separately.
2. Pooled equal-weight weekly series t >= 2.0.
3. Mean credit (h = 0.05) > mean realised |S_T/S0 - 1| for BTC and for ETH, in A and in B (4 checks).
4. Pooled series positive in at least 2 of the 3 calendar years 2024, 2025, 2026 (the Dec-2023 stub is reported,
   not counted).
5. Pooled mean > 0 and |worst pooled week| <= 52 x pooled mean weekly P&L.

Template clauses (adapted to 2 coins):
6. Per-trade mean > 0 with week-cluster bootstrap one-sided P <= 0.01.
7. Per-trade mean > 0 in A and in B.
8. Positive on 2 of 2 coins (same as clause 1).

Outcome: Fail -> close the option-selling family (including monthly expiries and delta-hedged variants).
Pass -> only then a delta-hedged version (daily perp hedge at 5.31 + 2 bps per side); nothing goes to paper
without the owner revisiting D3.md:201 "no option selling".

## Holdouts

The two holdouts (Binance spot 5 m 2017-08..2020-04; 15 Binance perps 5 m 2021-12..2026-09) contain no option
prices, so this spec cannot be run on them. If the in-sample passes, the holdout is reported as not runnable
(passed_holdout = false) and the proposal's own next step applies. If the in-sample fails, holdouts are skipped.
