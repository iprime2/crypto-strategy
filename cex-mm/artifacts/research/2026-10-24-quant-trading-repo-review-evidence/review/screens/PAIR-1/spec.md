# Screen PAIR-1: daily cointegration spread reversion, market-neutral pairs (frozen spec)

Written 2026-10-24 before any PAIR-1 result was computed in this folder. Implements the frozen proposal
`ext_repo/review/stat-arb-and-macro/screen_PAIR1_frozen.txt` (sha256 5556a0cdcc03c5e4ae1df28bb3ad3d543decfbb82898f970595a4a28c8a70c06,
re-hashed and matched before writing this file). Where that file is silent, the readings below are fixed here, before any run.
No parameter search: the parameters are the frozen file's. The source repo's defaults (je-suis-tm "Pair trading backtest.py":
250-day window, ADF p < 0.05 on the residual, +/-1 sigma bands, no stop) were already run descriptively in
`stat-arb-and-macro/quick_check_output.txt` (Sharpe -0.42) and are not re-selected here.

Prior evidence checked (no earlier backtest of this rule exists):
- resource/07 lines 167-196 ("What was considered and rejected"): line 179 cross-sectional alt momentum / beta-neutral baskets,
  line 180 seconds-scale lead-lag, line 183 trend shorts, line 173 funding carry / basis. None is a daily cointegration pairs test.
- resource/07 line 237: "no shorts ... no second strategy". A pass here would only make a paper candidate needing the user's decision.
- resource/08: 26 pre-registered trend cells, none passed; no pairs cell.
- cex-mm/artifacts/research/2026-10-22-prev-week-levels.md: PWH/PWL trades rejected; no pairs content.
- practitioner_strategies.md (2026-10-13-prop-strategy-evidence/research_notes/...) lines 107-134: literature only; line 128 says daily
  cointegration on large coins is the only stat-arb variant reported net-positive (Utupub thesis, 2020-22). No backtest in the repo.
- STRATEGY.md and resource/01-06: market-making design; pairs appear only as a book chapter title (resource/01 line 167).

## Data (public, on disk, read with own code; nothing from the external repo is imported or executed)
- Daily closes: Binance USDT-M 1d klines in scratchpad caches `trend-cache`, `av_cache`, `universe/cache`, `universe/cache_all`
  (first file wins, as `tools2/data.py`). The candle opened on date d closes at 00:00 UTC of d+1; that price is "the close of day D",
  D = d+1. All decisions are taken on these closes.
- Hourly: `scratchpad/hourly/<SYM>USDT-1h.csv` (the nine) and `universe/hourly_extra/` (the other 16 of the 24-panel).
  P01[D] = close of the 1 h bar that opens at 00:00 UTC on D (it closes at 01:00 UTC). Fill time = 01:00:00 UTC of D.
- Funding: Binance `binance-<SYM>USDT-fundingRate-YYYY-MM.csv` (calc_time ms, last_funding_rate), every stamp, from the same caches.
- Universe (in-sample): the nine BTC ETH XRP BNB ADA LTC LINK DOGE BCH, all 36 unordered pairs.
  X = the coin earlier in [BTC, ETH, XRP, BNB, ADA, LTC, LINK, DOGE, BCH], Y = the later one.

## Formation (every Monday M, using the closes of days M-179 .. M only, i.e. data up to and including the 00:00 UTC close of M)
- Both coins need all 180 closes finite, else the pair is ineligible that week.
- OLS  y = ln P_Y = a + b x,  x = ln P_X; residual e (180 values); mean_e = mean(e); sd_e = std(e, ddof=1).
- Engle-Granger p: ADF on e with no deterministic term, lag order 0..10 chosen by AIC on a common sample (the 169 rows usable at
  lag 10), then re-estimated at the chosen lag on all usable rows; statistic = t of the lagged level; p = MacKinnon (1994)
  approximate p-value for regression "c", N = 2 (exactly statsmodels 0.14.4 `coint(y, x, trend="c", maxlag=10, autolag="aic")`;
  implemented in numpy and cross-checked against statsmodels on real formations; statsmodels is used only in the cross-check).
- Half-life: OLS de_t = k + c e_{t-1}, t = 2..180 (179 rows). Requires -1 < c < 0; h = -ln 2 / ln(1+c).
- Eligible iff p < 0.05 and 0.25 <= b <= 4 and 2 <= h <= 30 (days).
- Spread vol (for sizing): sigma_ann = std(diff(e), ddof=1) x sqrt(365).
- Selection S_M: eligible pairs sorted by p ascending (ties by pair order), added greedily while every coin is in <= 2 selected
  pairs, up to K = 4. S_M governs entries at the closes D = M .. M+6.

## Signal and entry (decision on the closed 00:00 UTC daily bar D; fill at P01[D], never at the decision price)
- For a flat pair in S_M: z_D = (ln P_Y,D - b ln P_X,D - a - mean_e) / sd_e with M's parameters.
- +2 <= z_D < +4: short spread = short Y notional N, long X notional b N.  -4 < z_D <= -2: long spread (reverse).
  (|z| >= 4 at entry is not entered: it is already at the frozen stop.)
- No entry in a pair for 3 decision days after a stop exit (stop decided at D_s blocks D_s+1 .. D_s+3).
- A pair exited at D can be re-entered from the close D+1 on.
- Sizing: N = E_D x min(0.05 / sigma_ann, 0.5 / (1 + b)), where 0.05 = 0.10 / sqrt(K) and E_D is book equity at close D.
  Units fixed at entry: Y units = N / P01_Y, X units = b N / P01_X (signs by side). No rebalancing while open.
- Total gross cap 2.0 x equity: if the new pair's gross at its fill prices would take the book's gross above 2.0 x E_D,
  N is scaled down to fit; skipped if no room. Open pairs that drop out of a later S keep running under their own exits.

## Exit (checked at every close D' after the entry close, with the pair's entry a, b, mean_e, sd_e, h; fill at P01[D'])
- Stop: short spread z' >= +4; long spread z' <= -4.
- Target: short spread z' <= +0.5; long spread z' >= -0.5 (covers |z'| <= 0.5 and any overshoot through the mean).
- Re-test: D' is a Monday and the EG p on the fresh 180-close window ending D' is > 0.20 (or not computable).
- Time: D' - D_entry (days) > min(2h, 30).
- Reason precedence if several fire: stop, target, re-test, time. Trades open at the end are closed at P01 of the last window day.

## Missing data
- If P01 is missing for a leg on a fill day, the fill uses the first later hourly close on that day (01:00..23:00 opens); if none,
  an entry is skipped and an exit moves to the next day with a price. A coin without a daily close at D takes no decisions at D.
- Marks use P01 forward-filled. Counts of fallback fills are reported.

## Costs, funding, P&L
- Every leg fill pays 7.31 bps of its notional (taker 5.31 incl. GST + 2 bps slippage). Pair round trip = 4 fills = 29.24 bps of
  the average leg notional. Stress run: 15.31 bps per leg fill (10 bps slippage). No maker fills.
- Funding at every Binance stamp s with entry fill time < s < exit fill time, on each leg: -units x price_s x rate
  (long pays a positive rate, short receives). price_s = open of the 1 h bar starting at the stamp's hour (fallback: last close).
- Daily mark-to-market at 01:00 UTC. Day D's P&L covers (01:00 D-1, 01:00 D]: price change of open legs to the mark (or to the fill),
  fills' costs, and funding stamps in that interval. r_D = PnL_D / E_{D-1}; E compounds from 1.
- Window: mark days 2020-05-01 .. 2026-09-30. The book starts flat; days before the first possible formation (first Monday with 180
  closes, about 2020-06-29; DOGE pairs about 2021-01) count as zero-return days.

## Metrics
- Trade = one pair round trip. Leg notional L = (|N_Y| + |N_X|) / 2 at entry fills.
  net bps = 1e4 x (price P&L of both legs + funding received - costs) / L; gross bps excludes costs and funding.
- Mean net bps per trade with a week-cluster bootstrap: clusters = Monday-start UTC weeks of the entry decision date; all weeks of
  the window; 2,000 resamples of the weeks with replacement from numpy default_rng(11); per draw the pooled mean (sum net / count);
  one-sided P = share of draws with mean <= 0.
- Annualised Sharpe of the daily returns r_D (mean / std ddof=1 x sqrt(365)), all window days.
- Trades per year = trades / (window days / 365.25). Also CAGR, max DD, exit-reason counts, funding share, mean days held.

## Pass rule of this screen (governs the verdict; base costs)
1. Mean net bps per trade > 0 with one-sided bootstrap P <= 0.01, on the nine 2020-05..2026-09.
2. Mean net bps per trade > 0 in both halves by entry date: 2020-05-01..2023-06-30 and 2023-07-01..2026-09-30.
3. On >= 6 of the 9 coins, the mean net bps of the trades in which that coin is a leg is > 0 (a coin with no trade fails).
PASS only if 1, 2 and 3 all hold.

## Frozen-file criteria, reported alongside (all must also hold for the frozen file's own pass)
F1 Sharpe >= 0.50 (nine, 2020-05..2026-09). F2 Sharpe > 0 in 2020-05..2023-12 and 2024-01..2026-09. F3 Sharpe > 0 on the 24 ex-ante
panel 2022-01..2026-09. F4 mean net >= +29.24 bps per round trip. F5 week-cluster bootstrap of the daily returns (Monday weeks,
2,000 draws, a separate default_rng(11)) P(Sharpe <= 0) <= 0.10. F6 Sharpe > 0 at 10 bps slippage. F7 |corr| of daily returns with
the weekly TV 0.25 trend book <= 0.30; that book is `tools2` baseline_weights(tv=0.25, max_gross=1.0), decided on the Sunday candle,
10 % band, 7.31 bps, on the nine (the configuration of tools2/check_baseline.py); its return for candle date c is aligned to D = c+1.
Labelled neighbours, reported on the nine at base costs and never selected: window 120 and 365; entry 1.5 and 2.5; K 2 and 6
(K also sets 0.10/sqrt(K)).

## Gated runs (only if the nine PASS the screen's rule; otherwise skipped and reported as skipped)
- F3, the 24 ex-ante panel (the 24 in tools2/data.py EXANTE24), 276 pairs, book starts flat 2022-01-01, window to 2026-09-30;
  X/Y ordered by median daily quote turnover over the candles 2020-01-21..2020-02-19 (descending).
- Holdout A: Binance spot 5 m 2017-08..2020-04, 13 pairs (files universe/spot5m), daily closes and 01:00 fills built from the 5 m bars,
  no funding. Holdout B: Binance perps 5 m 2021-12..2026-09, the 15 coins in universe/ox5m, funding if on disk (else none, stated).
  Both: identical rule; X/Y ordered by median daily quote turnover over the 30 days before the first possible formation Monday;
  same pass rule with test 3 read as ">= 2/3 of the coins" (spot 13 -> 9, perps 15 -> 10), halves split at the window midpoint date.

## Engineering checks (before reading results)
- EG p-values: numpy implementation vs statsmodels 0.14.4 on >= 200 real formations; max |dp| reported.
- No look-ahead: run on data truncated at a cut date; every trade entered and exited before the cut must match the full run exactly.
- Synthetic: a constructed cointegrated pair must be selected and traded; two independent random walks must rarely be.
