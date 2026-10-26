# Quant memo: the je-suis-tm/quant-trading repo has nothing we can use; its three untested ideas fail on our data
**Date:** 2026-10-24 · **Subject:** https://github.com/je-suis-tm/quant-trading (Apache-2.0, 10.8k stars, last commit 2024-04-14, cloned at `611b73f`), shared by the user from an Instagram post ("17 trading strategies in Python") · **Data for the screens:** Binance USDT-M 5 m klines for the nine, 2020-05..2026-09; holdouts never used in-sample: Binance spot 5 m 2017-08..2020-04 (12–13 pairs) and 15 perps chosen by 2021-Q4 volume, 2022-01..2026-09; Delta India public option products, MARK and index candles, 2024-01..2026-10 · **Evidence:** `cex-mm/artifacts/research/2026-10-24-quant-trading-repo-review-evidence/` (per-family review notes and checks, each screen's frozen spec with sha256, code and outputs, the skeptic's re-derivations, and the full workflow record)

## Question
The user asked whether this repo is useful to us. "Us" means the post-only market maker on Delta India and the two trend paper books on nine Delta perps.

How it was answered:
- **Code review.** The repo was cloned read-only and never executed. Five reviewers took one strategy family each (trend indicators; intraday breakouts; mean-reversion patterns; stat arb and macro projects; options and volatility). For each strategy they recorded:
  - what the code actually does;
  - its flaws;
  - the closest evidence already in this repo, by file and line;
  - whether it fits Delta at our costs.
- **Screens.** Families that were genuinely untested here got one screen each. The rule was written down and hashed before any result was computed. A rule that passed in-sample was then run once on the two holdout panels with no changes.
- **Check.** A skeptic re-derived trades by hand from raw data for every screen.

## Outcome
- **Do not use the repo's code.** It is an educational collection, not a set of backtests:
  - none of its 14 backtest scripts charges trading costs (its README says "all trades are frictionless");
  - most compute no P&L at all, only a signal plot of one stock or currency over a few weeks;
  - several use same-bar or future data;
  - several have bugs that change the answer, or silently do nothing on current pandas.
- **Its strategies are either already tested and rejected here, or do not fit 24/7 crypto perps.** The table below gives each one.
- **The three ideas we had not tested all fail on our data:**
  - Cointegration pairs lose.
  - A BTC-hedged "follow the break" rule has mixed evidence and fails its frozen rule.
  - Selling weekly straddles on Delta loses.
- **Nothing changes.** No book, bot or order path was touched.
- **The one usable fact.** Delta's option tickers already carry mark, bid and ask implied vol and greeks, so a 30-day implied-vol number can be computed in about 60 lines of our own code if it is ever needed: 35.5 % for BTC and 49.8 % for ETH at 2026-10-24 06:33 UTC. Nothing in the trend books or the market maker currently uses one.

## What each strategy is, and why it is no use to us
| Repo strategy | What the code actually does | Verdict and reason | Our prior evidence |
|---|---|---|---|
| MACD oscillator | Long/flat SMA crossover with hand-typed windows; no P&L; a chained assignment that does nothing on pandas 3 | Already tested: the linear-filter family (EWMAC binary and continuous, Baz MACD, faster lookbacks) failed | `resource/08` SIG-3a, SIG-3b, SIG-6; `resource/07` rejected rows |
| Awesome oscillator | Effectively an SMA5/SMA34 crossover on the median price; the "saucer" never changes a trade, and its signs are inverted | Already tested: a faster member of the same family | as above |
| Heikin-Ashi | Buys into accelerating falls; its stats run on about 50 bars | Not applicable: no evidence of edge, and our nearest evidence points the other way | `resource/07` short-horizon direction row; `2026-10-22-prev-week-levels.md` |
| Parabolic SAR | Not Wilder's SAR (whipsaws about a third more on test data); no P&L | Already tested: trailing-exit trend systems (Donchian ratchet, breakout blend, stops) failed | `resource/08` SIG-4, SIG-11 |
| London Breakout | An FX session rule; one day of one pair; a NameError in its plot | Not applicable: crypto has no session open, and an arbitrary UTC hour would be curve fitting | `resource/07` seasonality and decision-hour rows |
| Dual Thrust | Same-day look-ahead in its thresholds; one plotted day | Already tested: the closest equivalent, a stop entry at a prior-range level, fails at Delta costs | `2026-10-22-prev-week-levels.md` |
| Bollinger "bottom W", RSI 30/70, RSI head-and-shoulders, shooting star | No P&L; thresholds in absolute price; the shooting star fires 0 times on our coins (it needs session gaps) | Already tested or not applicable: fades and failed breakouts were rejected; the shorts are banned | `2026-10-22-prev-week-levels.md`; `resource/07` shorts row |
| Pair trading | Broken band arithmetic, look-ahead sizing, an exit at the band, no costs | Untested here, so screened (PAIR-1): fails | literature only before this |
| Oil Money (FX vs crude) | Single-leg, grid-optimised, same-close fills; scripts that do not run | Its BTC-hedged transplant was untested, so screened (RESID-1): fails its frozen rule | `resource/07` cross-sectional alt row (literature only) |
| Ore Money, Smart Farmers, Wisdom of Crowds, Portfolio Optimization | Charts, a crop-planting model, analyst-forecast aggregation, graph-based weights | Not applicable, or already tested (correlation-aware weighting failed) | `resource/08` SZ-6b |
| Monte Carlo project | Shows that a best-fit GBM path does not forecast prices | Correct, and already how we work (bootstrap, not path forecasts) | — |
| Options straddle (long) | A unit bug turns losses into profits: on its own data every traded strike loses in consistent units | Already tested on Delta: buying daily straddles loses | `options-research/README.md` |
| Short straddle (comments only) | Not implemented | Weekly expiries were untested here, so screened (OPT-W1): fails | `options-research/README.md` "Not tested" |
| VIX calculator | Strike units are wrong (3.0 instead of about 64 on its own data), and the ATM strike is always dropped | Useful only as an idea; do not reuse the code. Delta publishes no vol index | — |

## The three screens
| Screen | Rule (frozen before any result) | In-sample, the nine 2020–26 | Holdouts | Verdict |
|---|---|---|---|---|
| PAIR-1, cointegration pairs | 36 pairs of the nine; daily Engle–Granger selection; ±2σ entry, mean exit, stop and time exit; 7.31 bps per leg fill plus funding | −304 bps net per round trip (P(mean ≤ 0) 0.992), both halves negative, 1 of 9 coins positive, Sharpe −0.99. The skeptic found a re-entry deviation worth +8.3 bps; it does not change the fail | not run (in-sample fail) | Rejected. Single coins jumping while a leg is short dominate the losses (BNB +60 % in February 2021, BCH +47 % in March 2024) |
| RESID-1, BTC-hedged "follow the break" | Alt vs BTC on a 50-day OLS of log prices, R² > 0.7, enter in the direction of a 2σ break, exit after 10 days; the repo's defaults | +223 bps net per trade, P 0.0100 (exactly at the threshold; fails with more bootstrap draws), Sharpe 0.95, second half only +39 bps, 6 of 8 alts. Not blind: this result was seen before the freeze | Spot 2017–20: +8.7 bps, P 0.43, Sharpe −0.11 (fail; −43.9 % in 2020). 15 perps 2022–26: +322 bps, P 0.0075 (pass). 16 unseen ex-ante perps 2020–26: passes the screen but fails its frozen correlation clause with the weekly trend book (+0.303 against 0.30) | Rejected under its rule. It also needs shorts and a second strategy, both of which `resource/07` bars. Its only clean time holdout fails, and the panels that pass share the 2020–26 calendar |
| OPT-W1, weekly short ATM straddle on Delta | Sell the BTC and ETH ATM straddle 168 h before the Friday 12:00 UTC expiry at MARK × 0.95; hold to settlement (30-min index TWAP); Delta fees plus GST | Pooled −26.3 bps per week (t −0.63, bootstrap P 0.71), 145 weeks, worst week −2,062 bps; the credit is below the realised move in 3 of 4 coin-periods | none possible (no option prices before 2024) | Rejected. With the daily-expiry result (`options-research/`), option selling on Delta is closed. Monthly and delta-hedged variants are closed by policy, not by a test |

## What the code actually does
- **Nothing in the repo changed apart from this memo, its evidence, three rows in resource/07's rejected table and one line in `options-research/README.md`.** No file under `cex-mm/scripts/`, `quote-bot/`, `backend/` or `web/` changed, and no order was placed.
- **The external repo was never executed.** Reviewers re-typed specific lines into their own scratch code to check behaviour (for example the pandas 3 chained-assignment no-op and the Parabolic SAR recursion). The screens use only our own code.
- **The screens are research code.** They live in the evidence pack with absolute scratchpad paths.

## Limits
- **The screens test one natural specification per idea, using the repo's defaults where they exist.** A different pairs selection or residual model might do better. Trying several until one passes would be the parameter search these rules exist to stop.
- **The options screen has 145 weeks of data.** Its fail is a lack of evidence for an edge, and it does not prove the option is mispriced.
- **The review judged the repo's code as published (2024-04).** It did not judge later forks or the author's other repositories.
