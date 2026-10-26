# Screen RESID-1: BTC-hedged "co-movement break, follow it" (frozen spec)

Written 2026-10-24 before any RESID-1 result was computed in this folder. Implements the frozen proposal
`ext_repo/review/stat-arb-and-macro/screen_RESID1_frozen.txt` (sha256 9f5a62a0efc4f6ddf5e97089f2b8fcc0e7de1479caec8293837003227afc8e60,
re-hashed and matched before writing this file). Where that file is silent, the readings below are fixed here, before any run.
No parameter search. The parameters are the source repo's defaults (je-suis-tm "Oil Money project/Oil Money Trading backtest.py",
`signal_generation(holding_threshold=10, stop=0.5, rsquared_threshold=0.7, train_len=50)`, lines 55-178, read as data, never
executed): train window 50, R^2 > 0.7, band +/- 2 sigma with sigma = np.std (ddof 0) of the window residual, counter > 10 exit.
The price stop is dropped, as the frozen file says. Nothing from the external repo is imported or executed.

Prior evidence checked (no earlier backtest of this rule exists in our repo):
- resource/07 lines 167-196 ("What was considered and rejected"): line 179 cross-sectional alt momentum / beta-neutral baskets
  (literature and a GitHub README only), line 180 lead-lag BTC -> alts (seconds scale, not daily), line 183 shorts (long/short trend),
  line 173 funding carry / basis, line 196 previous-week levels. None is a daily BTC-hedged residual-break test.
- resource/07 line 237: "no shorts ... no second strategy". A pass here would only make a paper candidate needing the user's decision.
- resource/08 lines 205-225 (results table): 26 pre-registered trend cells (EWMAC, Donchian, breakout blend, vol estimators), none
  passed; no hedged or residual cell. The unhedged single-leg form overlaps the rejected breakout cells (SIG-11, SIG-4).
- cex-mm/artifacts/research/2026-10-22-prev-week-levels.md: PWH/PWL fades, breakouts, failed breakouts rejected; no residual content.
- 2026-10-22-trend-improvement-evidence/phase1/master_candidates.md lines 460-463 and phase1_plan.md line 407: OVL-7 relative
  strength vs BTC dropped with "no backtest exists anywhere". phase1/notes/crypto_academic.md line 129: residual momentum is a
  literature note only.
- STRATEGY.md and resource/01-06: market-making design; hedging appears only as MM inventory hedging (resource/01 sections 9, 11).

## Data (public, on disk, read with own code)
- In-sample prices: Binance USDT-M 5 m klines, `scratchpad/universe/klines5m/binance-<SYM>USDT-5m-YYYY-MM.csv` (old files have no
  header; open_time in ms; a value > 1e14 is read as microseconds). Only top-level files of each folder are read.
- From the 5 m bars, per coin and UTC date D:
  - C[D], "the close of day D" = close of the 5 m bar whose open time is D 00:00 minus 5 min (it closes at 00:00:00 UTC of D).
    This equals the Binance 1d kline close of the candle opened on D-1 (checked, see Engineering checks). If that bar is missing,
    the last 5 m close with open time in [D-1 23:00, D-1 23:55] is used; if none, C[D] is missing.
  - P01[D] = close of the 5 m bar whose open time is D 00:55 (it closes at 01:00:00 UTC of D) = the 01:00 UTC hourly close.
- Funding: Binance `binance-<SYM>USDT-fundingRate-YYYY-MM.csv` (calc_time ms, funding_interval_hours, last_funding_rate), every stamp,
  searched in `trend-cache`, `av_cache`, `universe/cache`, `universe/cache_all` in that order (first file name wins, as tools2/data.py).
  A coin-month with no file pays no funding; the count of such months over held periods is reported.
  Stamp price = open of the 5 m bar that opens at the stamp time (fallback: the last 5 m close before it).

## Universe and windows
- In-sample: the nine BTC ETH XRP BNB ADA LTC LINK DOGE BCH. Driver X = BTC; traded Y = the 8 alts ETH XRP BNB ADA LTC LINK DOGE BCH.
- In-sample window: decision / mark days D = 2020-05-01 .. 2026-09-30. Closes before 2020-05-01 (from 2020-01) are used only to fill
  the first OLS windows. Every alt starts flat and untrained at the first window day.

## Rule (per alt Y, ln prices of the daily closes; the repo's signal_generation loop, one iteration per day)
State: holding in {-1, 0, +1}, trained (bool), counter (int), frozen a, b, sigma.
Days D are taken in calendar order. A day where C[D] is missing for Y or for BTC is skipped for that alt (no state change).
For each day D (decision at the 00:00 UTC close of D, using only C up to and including D):
1. If holding != 0:
   - if counter > 10: decide the exit (holding = 0, trained = False, counter = 0) and go to the next day (no fit, no entry on D);
   - else counter += 1.
   (Entry on D_e, counter 0; exit is decided on D_e + 12 when no day is skipped: 12 days held.)
2. Else (flat):
   - if not trained: OLS ln Y = a + b ln BTC with a constant on the closes of the 50 calendar days D-50 .. D-1 (all 50 must exist for
     both coins, else no fit on D). R^2 is the usual centred R^2. If R^2 > 0.70: trained = True; keep a, b and
     sigma = np.std(ln Y - (a + b ln BTC), ddof=0) over the window. The model stays frozen until the next trade closes.
   - if trained (also on the day it was trained, as in the repo): f = a + b ln BTC[D];
     ln Y[D] > f + 2 sigma -> holding = +1 (enter); ln Y[D] < f - 2 sigma -> holding = -1 (enter); counter stays 0.
3. No price stop, no other exit.

## Position, fills
- holding = +1: long Y notional N, short b*N of BTC; holding = -1: short Y notional N, long b*N of BTC (b as estimated; a negative b
  flips the BTC leg's side). Hedge units fixed at entry, never rebalanced.
- N = E_{D-1} / n_alts, where E_{D-1} is book equity at the 01:00 UTC mark of the day before the entry day (E starts at 1.0) and
  n_alts = number of alts in the panel (8 in-sample). Each alt is its own sleeve; BTC hedge legs of different alts are not netted.
- Entry and exit fill at P01 of the decision day (01:00 UTC, one hour after the decision close; never at the decision price).
  Units: Y = s N / P01_Y[D], BTC = -s b N / P01_BTC[D], s = holding.
- If P01 is missing for a leg on a fill day, the fill uses the first later 5 m close that day (bars opening 01:00 .. 23:55); if none,
  an entry is skipped (the alt stays flat and trained) and an exit is retried on the next day with a price. Fallbacks are counted.
- A trade still open at the end of the window is closed at P01 of the last window day (costs charged) and counted (flagged).
  A coin whose data ends inside the window (delisting) has its open trade closed at its last available 5 m close (flagged).

## Costs, funding, P&L
- Every leg fill pays 7.31 bps of its notional (taker 5.31 incl. GST + 2 bps slippage). An equal-legged round trip (|b| = 1) is
  4 fills = 29.24 bps of alt notional; in general 14.62 x (1 + |b|) bps of N. No maker fills are assumed.
- Stress run: 15.31 bps per leg fill (10 bps slippage), same rule, re-simulated.
- Funding at every Binance stamp s with entry fill time < s < exit fill time, on each leg: cash = -units x price_s x rate.
- Daily mark at 01:00 UTC. Mark day D's P&L covers (01:00 D-1, 01:00 D]: for each open leg, units x (mark_D - last mark), where the
  last mark is the entry fill price or the previous day's mark, mark_D = P01[D] forward-filled, or the exit fill price on an exit day;
  plus funding stamps in the interval; minus the costs of fills booked on D. r_D = PnL_D / E_{D-1}; E compounds from 1.0.
- All window days are in the daily series (days with no position are zero-return days).

## Metrics
- Trade = one alt round trip (both legs). net bps = 1e4 x (price P&L of both legs + funding cash - costs) / N.
  gross bps = price P&L only. Cost bps and funding bps reported separately.
- Mean net bps per trade with a week-cluster bootstrap: clusters = Monday-start UTC weeks of the entry decision date; all weeks of the
  window (weeks without trades included); 2,000 resamples of the weeks with replacement from numpy default_rng(11); per draw the
  pooled mean (sum net / count, draws with zero trades count as mean 0); one-sided P = share of draws with mean <= 0.
- Annualised Sharpe of r_D = mean / std(ddof=1) x sqrt(365), all window days. Trades per year = trades / (window days / 365.25).
- Also: CAGR, max DD, median net bps, hit rate, long-alt vs short-alt split, by calendar year, funding share, mean |b|,
  per-alt counts and means, counts of fallback fills and forced end closes.

## Pass rule of this screen (governs the verdict; base costs)
1. Pooled mean net bps per trade > 0 with one-sided bootstrap P <= 0.01, on the nine 2020-05..2026-09.
2. Mean net bps per trade > 0 in both halves by entry decision date: 2020-05-01..2023-06-30 and 2023-07-01..2026-09-30.
3. ">= 6 of 9 coins": BTC is the hedge leg of every trade and is not scored as a traded coin, so it counts as a fail; the test is that
   >= 6 of the 8 alts have a mean net bps per trade > 0 (an alt with no trade fails).
PASS only if 1, 2 and 3 all hold.

## Frozen-file criteria, reported alongside on the nine (descriptive here; the frozen file scores them on the 16 unseen perps)
F1 Sharpe >= 0.50. F2 Sharpe > 0 in 2020-05..2023-12 and 2024-01..2026-09. F3 mean net >= +29.24 bps per round trip of alt notional.
F4 week-cluster bootstrap of the daily returns (Monday weeks of mark days, 2,000 draws, a separate numpy default_rng(11)):
P(Sharpe <= 0) <= 0.10. F5 Sharpe > 0 at 10 bps slippage. F6 |corr| of daily returns with the weekly TV 0.25 trend book <= 0.30; that
book is tools2 `rules.baseline_weights(C, tv=0.25, max_gross=1.0)`, decided on the Sunday candle (`decide_weekly(dates, 6)`), band 0.10,
7.31 bps, `sim.simulate` on `data.load_binance()` for the same coins, 2020-05-01..2026-09-30; its return for candle date c is aligned to
D = c + 1 (one hour offset from our 01:00 marks, accepted).
Labelled neighbours (reported on the nine at base costs, never selected): fill at the decision close C[D]; refit daily while flat
(trained reset each flat day); R^2 0.6 and 0.8; band 1.5 and 2.5 sigma; exit counter > 5 and > 16 (hold 6 / 18 days); unhedged
single leg (Y only, no BTC leg).

## Gated runs (only if the nine PASS this screen's rule; otherwise skipped and reported as skipped)
- G0, the frozen file's own pass panel: the 16 ex-ante Binance USDT-M perps outside the nine (ATOM BAT DASH EOS ETC IOST IOTA NEO ONT
  QTUM TRX VET XLM XMR XTZ ZEC), driver BTC, window 2020-05-01..2026-09-30, n_alts = 16. Prices from `universe/hourly_extra` 1 h bars
  (C[D] = close of the 1 h bar opening D-1 23:00; P01[D] = close of the 1 h bar opening D 00:00), BTC from the same 5 m source as
  in-sample. Frozen criteria F1-F6 (F6 against the weekly trend book on the same 16) plus this screen's rule with test 3 read as
  ">= 2/3 of the alts" (11 of 16).
- Holdout A: Binance spot 5 m 2017-08..2020-04, the 13 pairs in `universe/spot5m` (BTC driver + 12 alts), window decision days
  2017-08-01..2020-04-30, no funding (spot), n_alts = 12.
- Holdout B: Binance perps 5 m, the 15 coins in `universe/ox5m` (top-level files only; the `post_delisting_flat` and `replaced_monthly`
  subfolders are not read), BTC from `universe/klines5m`, window decision days 2022-01-01..2026-09-30 (closes from 2021-12 fill the first
  windows), funding from the caches if on disk (else none, stated), n_alts = 15 fixed for sizing.
- Both holdouts: identical rule and costs; the same pass rule, halves split at the midpoint date of the first possible decision day
  (first day with a valid 50-day window for any alt) and the window end; test 3 read as ">= 2/3 of the alts" (12 -> 8, 15 -> 10).

## Engineering checks (before reading results)
- Daily closes from 5 m vs the Binance 1d kline closes in the caches, the nine 2020-05..2026-09: max relative difference reported.
- OLS: numpy implementation vs a direct np.linalg.lstsq on random windows; R^2 and sigma checked against the textbook formulas.
- No look-ahead: run on data truncated at a cut date; every trade entered and exited before the cut must match the full run exactly.
- Synthetic: Y = BTC^1 x exp(noise) with a planted +3 sigma jump that persists must give a +1 trade that earns the jump; a mirror
  jump must give a -1 trade.
- Accounting: sum over trades of net P&L equals the sum of daily P&L (to 1e-9 of equity, on a non-compounding run with N fixed).
