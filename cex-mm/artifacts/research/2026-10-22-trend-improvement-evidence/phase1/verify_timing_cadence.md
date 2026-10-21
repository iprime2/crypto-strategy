# Adversarial verification: TIMING_CADENCE family (TIME-1..TIME-7), 2026-10-21

Verifier pass. Job: refute. Verdict per candidate: keep / refine / drop, the prior repo test that covers it, the
honest evidence grade, the refined rule, and the cost to backtest in a pure-Python daily engine on local data.
Read-only: nothing in the repo edited, no orders placed, `.env` not read. One local computation was run on an
existing return series (section 2), nothing else.

## 1. What was read

Repo evidence:
- `resource/07-trend-rule-and-prop-trading-research.md` lines 55-100 (the rule, execution, late-execution rule) and
  167-193 "What was considered and rejected": the cadence row says "Daily rebalancing with a bot on own capital: same
  Sharpe as the weekly mean, thinner tails (hourly DD -14.5% vs -17.7%) but needs a watcher ... kept as the upgrade
  path" (T1). D2's "moving the decision hour from 00:00 to 04:00 UTC for convenience raised Sharpe 1.26 -> 1.32" is the
  rejected weekday/hour selection. No row tests tranching, smoothing, partial adjustment, asymmetric cadence or a
  post-crash cool-down.
- `backtest_results.md` pre-registered plan T0-T7; T1 (weekly 1.12 / +14.1% / -16.9% / 192 trades; daily TV0.25
  band10 1.25 / +15.0% / -14.1% / 538; daily TV0.25 band0 1.25 / 1,773 trades); T3b weekday (Mon-candle 1.26, Tue 1.18,
  Wed 1.34, Thu 1.31, Fri 1.23, Sat 1.16, Sun = design 1.12; 7-day mean 1.23; "the 7-day mean vs daily" in the plan
  was reported as the mean of seven Sharpes, NOT a tranched book); T3c band 0/5/10/20% -> 1.12/1.12/1.12/1.11 at
  278/221/192/163 trades; T3k execution lag +0/+4/+8/+12/+24 h -> 1.12/1.09/1.11/1.09/1.15 and decision hour
  00/04/08/12/16/20 UTC -> 1.12/1.21/1.24/1.16/1.18/1.32 (lag +24 h is the longest lag tested); T3i day stops cost
  0.07-0.13 Sharpe; T5/T5c Delta 2024-08..2026-10: design weekday 0.70 unrounded (TV0.25), 0.81 at $1,000, other
  weekdays 0.92-1.14; section 5.2 grafts: G4 re-entry-room and G5 chop-detector "no measurable effect"; T6c flat 16%
  of days; T7 red flag 2 (design sits at the bottom of two path-luck distributions, each a ~0.2 Sharpe spread).
- `d3_runs/d3_tests_output.txt` (B0-B9 ablations, B6 weekly offset-0 1.33), `d3_tests2_output.txt` R2b (weekday
  offsets 0..6 on three universes: 9 coins 1.12-1.34 full, Delta 0.69-1.15), `d3_tests3_output.txt`,
  `d3_regime_filter_output.txt`. `av_runs/*.txt` (av_sub: design ex-2020-21 Sharpe 0.66, 2025-26 0.26; av_universe_9:
  24-perp ex-ante weekly 0.82 / daily 0.86; av_dsr; av_lows; props_*). 2026-10-08 memo `--grid` (18 settings:
  lookbacks x TV only; no cadence or timing knob).
- `cex-mm/scripts/trend_backtest.py::target_weights` (lines 125-140) and `trend_paper.py` flags (`--weekly`, `--band`,
  `--orders-only`): no smoothing, tranche or lambda knob exists in the repo.
- Evidence engine `tools/qd_engine.py`: knobs `--rebal`, `--wd`, `--band`, `--exec-lag`, `--H` (h_aligned_closes from
  the hourly files), `--capital` (whole contracts). Data present in the scratchpad: Binance 1d for 24+ perps
  (`trend-cache/`, `av_cache/`), hourly 1h for the 9 (`hourly/*USDT-1h.csv`), Delta daily and hourly JSON for the 9
  (`research2/delta_data/`), strategy return series (`qd_runs/hourly_daily_tv40.csv`,
  `qd_runs/hourly_design_weekly_tv25_band10.csv`).

Scratchpad Phase-2 harness (not repo; `scratchpad/tools2/{rules,sim,evaluate,variants}.py`, results in
`research2/phase2/*.json`, dated 2026-10-20, labelled smoke tests, NOT pre-registered):
- `baseline.json` reproduces the repo: A-daily 1.2498 / +24.2% / -21.9%; A-weekly 1.12 / +14.1% / -16.9%; B (24-perp
  ex-ante) daily 0.85 / weekly 0.81; C (Delta 2024-08..2026-10) daily 0.99 / weekly 0.70.
- `tranche7_smoke.json` = `variants.tranche7_smoke`: baseline weights with `tranches: 7`; `evaluate.run` simulates
  seven weekly books on the seven decision weekdays (each with the 10% band, unrounded, costs charged per book) and
  averages their daily returns (continuous rebalancing between tranches, no netting of offsetting orders). Results:
    A-weekly: Sharpe 1.25 (vs 1.12), CAGR +15.5% (+14.1%), maxDD -13.9% (-16.9%), turnover 3.4x (3.4x), fees 0.25%,
              2022 -5.0% (-6.9%), 2022-26 Sharpe 0.82 (0.66), 2024-26 1.06 (0.86)
    B-weekly: 0.91 (0.81), DD -15.2% (-17.0%), 2022-26 0.64 (0.49), 2024-26 0.87 (0.69)
    C-weekly: 1.00 (0.70), DD -7.9% (-9.1%), 2024-26 1.16 (0.84)
    daily rows unchanged (the kwarg applies to the weekly cadence only).
  Reading: the tranched weekly book lands at the daily book's Sharpe (1.25) with the weekly book's turnover (3.4x vs
  15.7x) and a maxDD below both. The 7-weekday mean of Sharpes is 1.23; the average book scores slightly above the
  mean because averaging lowers vol (timing diversification), as the RTL literature predicts. On Delta the design
  weekday was the worst of seven (0.70 vs 0.92-1.14) and the tranche lands at ~1.00, i.e. at the cross-weekday mean,
  not at the best weekday: no sign of a bug or of selection. Caveats: unrounded (no whole contracts), no netting, no
  order count, in-sample, one smoke run.
- `sig_continuous.json` (relevant to TIME-2's Baltas-Kosowski evidence): a continuous z-score signal instead of
  sign() scored 1.18 vs 1.25 (A-daily), 0.98 vs 1.12 (A-weekly), 0.75 vs 0.85 (B-daily), 0.70 vs 0.81 (B-weekly) at
  about half the turnover. So "continuous signal cuts turnover with no performance loss" did not hold on this data.

## 2. Local check run by me (TIME-7 and, indirectly, TIME-6)

`python3 -I` on the existing series (daily returns compounded from the hourly rows; no new backtest):
```
daily TV0.40 native (2344 d, Sharpe 1.25, CAGR +24.2%, maxDD -21.9%)
  events r < -3%: 30; next-1d +0.46% (t 1.35), next-2d +0.91%, next-3d +0.87% (t 1.94), next-5d +1.06%; unconditional 3d +0.19%
    cool-down K=3 x0.5 (candidate):  Sharpe 1.19  CAGR +22.1%  maxDD -19.8%   (no extra trading cost charged)
    cool-down K=1 flat:              Sharpe 1.16  CAGR +21.6%  maxDD -21.0%
    cool-down K=3 flat:              Sharpe 1.11  CAGR +19.9%  maxDD -17.7%
  events r < -2%: 61; next-3d +0.52% (t 1.59); K=3 x0.5 -> Sharpe 1.21, maxDD -21.2%
  events r < -4%: 13; next-3d +1.03% (t 1.44); K=3 x0.5 -> Sharpe 1.23, maxDD -21.9%
weekly design TV0.25 band10 (Sharpe 1.12, CAGR +14.1%, maxDD -16.9%)
  events r < -3%: 9; next-3d +1.28% (t 2.20); K=3 x0.5 -> Sharpe 1.09, CAGR +13.3%, maxDD -17.3% (worse)
  events r < -2%: 30; next-3d +0.96% (t 3.21); K=3 x0.5 -> Sharpe 1.02, maxDD -15.7%
```
After a strategy day below -3% the next three days are the strategy's BEST days (4-10x the unconditional 3-day
mean, t 1.9-2.2 on 30 / 9 events). Halving gross for three days costs 0.03-0.06 Sharpe and 2 pp of CAGR before the
two extra round trips are charged, and buys at most 2 pp of max drawdown on the daily line and nothing on the weekly
line. Sign of the effect is the opposite of the candidate's premise. Thirty events: the point estimates are noisy, but
every threshold and every K went the same way.

## 3. External sources: what the searches confirmed (nothing could be opened; concretumgroup.com and
w4.stern.nyu.edu returned ENOTFOUND; only raw.githubusercontent.com, data.binance.vision and api.india.delta.exchange
are reachable)

- Hoffstein, Sibears, Faber, "Rebalance Timing Luck: The Difference Between Hired and Fired", SSRN 3319045 (Oct 2018;
  JII 2019). Search summary of the abstract: RTL = std of returns between identically managed portfolios rebalanced on
  different dates; sub-indexes have identical ex-ante expected returns and realized differences do not mean-revert;
  "equally-weighting across N sub-indexes reduces rebalance timing luck by 1/N". https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3319045 [UNVERIFIED full text; abstract-level confirmation only]
- Hoffstein 2019 thread: L = 0.5 x (T/F) x S with S = "how different our portfolio can be from one rebalance to the
  next" (NOT a volatility); the 0.5 appears only in the thread. https://www.linkedin.com/pulse/rebalance-timing-luck-corey-hoffstein ; https://x.com/choffstein/status/1196126894732664832 [UNVERIFIED]
- Hoffstein, Faber, Braun "The Dumb (Timing) Luck of Smart Beta": RTL often > 100 bps/yr; depends on holdings count,
  turnover and rebalance frequency. https://blog.thinknewfound.com/2019/11/the-dumb-timing-luck-of-smart-beta/ [UNVERIFIED]
- Zarattini, Pagani (Concretum) "The Tranching Dilemma" (SSRN 5747964, Nov 2025): US equity momentum 1991-2024,
  best-vs-worst monthly schedule ~350 bps/yr CAGR; RTL ~1/N; average return and annual turnover broadly unchanged;
  small (~$25K) accounts better off with ~2 tranches because frictions dominate. Quantpedia / Substack summaries only.
  https://quantpedia.com/the-tranching-dilemma/ ; https://concretumgroup.substack.com/p/the-tranching-dilemma [UNVERIFIED]. Note: the "$25K -> 2 tranches" result rests on per-order
  commissions in US equities; Delta charges proportional fees with no minimum, so on Delta the tranche count is bounded
  by whole-contract granularity, not by commissions. The argument does not transfer as stated.
- Newfound US Trend Equity Index: 20 equal tranches rebalanced on a staggered daily basis (confirmed by search);
  "Tranching, Trend, and Mean Reversion" (Apr 2020) confirmed to exist; the "2 of 14 asset classes" post was NOT found.
  https://www.thinknewfound.com/newfound-research-us-trend-equity-index ; https://blog.thinknewfound.com/2020/04/tranching-trend-and-mean-reversion/ [UNVERIFIED]
- J.P. Morgan "Momentum Strategies Across Asset Classes" (Kolanovic, Wei, 2015-04-15): exists; the rebalance-day
  Sharpe 1.08-1.26 figures were not surfaced. https://www.cmegroup.com/education/files/jpm-momentum-strategies-2015-04-15-1681565.pdf [UNVERIFIED]
- Allocate Smartly "Taming Excessive Timing Luck in TAA by Tranching Strategies": exists; no 2/4/8-tranche numbers
  surfaced. https://allocatesmartly.com/taming-excessive-timing-luck-in-taa-by-tranching-strategies/ [UNVERIFIED]
- Jegadeesh, Titman 2001 (JF 56:699-720; NBER w7159): overlapping-portfolio methodology confirmed as a statistical
  construction; the quoted "no significant difference in returns" sentence was NOT found by search. [UNVERIFIED]
- Baltas, Kosowski 2012 "Momentum Strategies in Futures Markets and Trend-following Funds" (SSRN 1968996): follows the
  J-T overlapping methodology at monthly/weekly/daily; Sharpe figures not surfaced. [UNVERIFIED]
- Baltas, Kosowski "Demystifying TSMOM": turnover cut "by more than one third" from a better vol estimator and the
  TREND (t-stat) signal; a Return Stacked review attributes ~24% to the signal, ~17% to the Yang-Zhang estimator. This
  is evidence for a DIFFERENT signal, not for time-averaging sign(); the local sig_continuous smoke went the other way.
  https://www.cmegroup.com/education/files/demystifiing-time-series-momentum-strategies.pdf [UNVERIFIED]
- Garleanu, Pedersen 2013 JF 68(6) 2309-2340: "aim in front of the target, trade partially toward the aim";
  x_t = x_{t-1} + lambda (aim - x_{t-1}); derived under QUADRATIC transaction costs; commodity-futures implementation
  "superior net returns relative to more naive benchmarks". https://www.nber.org/papers/w15205 [UNVERIFIED full text]. Under proportional (linear) costs,
  which is Delta's fee structure at $1-5k, the optimal policy is a no-trade band (Constantinides-type), i.e. T3c / the
  COST buffer, not a constant trading rate. Partial adjustment still diversifies timing luck (it is an exponentially
  weighted tranche), which is the only mechanism that applies here.
- AQR "Portfolio Rebalancing Part 1": rebalancing only 25% toward target achieves similar long-term statistics; partial
  rebalancing gives a larger cost saving for a smaller increase in allocation drift than less frequent rebalancing.
  Strategic 60/40-type allocation, not trend. https://images.aqr.com/-/media/AQR/Documents/Insights/White-Papers/Portfolio-Rebalancing-Part-1-Strategic-Asset-Allocation.pdf [UNVERIFIED]
- Sepp, Lucic arXiv 2607.19497 "The Science and Practice of Trend-Following Systems": exists; the "discrete systems
  have half the turnover" claim was not surfaced by search (the SIGNAL verifier's downloaded case study confirms
  American/discrete systems trade at 125-200%/yr vs 300-400% for continuous ones). https://arxiv.org/abs/2607.19497 [UNVERIFIED]
- Crypto-specific RTL / tranching: two searches found no study. Related: MDPI JRFM 19(9):692 (2026) lagged momentum and
  reversal in BTC/ETH by 12-h session: results session- and period-dependent, BTC rule fails out of sample, BTC
  daily edge 4.24 bps -> 0.14 bps at a 2 bps cost. Not supportive of any intraday timing choice. https://doi.org/10.3390/jrfm19090692 [UNVERIFIED]
- Short-term reversal in crypto (TIME-7 contrary evidence): Dobrynskaya, "Cryptocurrency Momentum and Reversal" (JAI
  2023; 2,000 coins 2014-2020): momentum up to 2-4 weeks, reversal beyond ~1 month, loser side drives it; Kozlowski,
  Puleo, Zhou, "Cryptocurrency return reversals" (Applied Economics Letters 28(11), 2021; 200 coins 2015-2019):
  next-day reversal, strongest in illiquid small coins. Both cross-sectional; neither tests a strategy-level loss day.
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3913263 ; https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4256709 [UNVERIFIED]
- Asymmetric cadence (TIME-6): one search, no study of weekly-entries / daily-exits found; the nearest practitioner
  result says widening the entry window cuts trades but gives back the saving by entering later. [UNVERIFIED]

## 4. Verdicts

### TIME-1 Tranched weekly book (daily rebalance toward the 7-day mean of the daily target weights) -> KEEP
- Prior repo test: none as a book. T3b measured the seven weekday books separately (1.12-1.34, mean 1.23) and the plan's
  "7-day mean vs daily" line reported the mean of Sharpes only. T3k lag +24 h costs <= 0.03. The scratchpad Phase-2
  smoke `phase2/tranche7_smoke.json` (2026-10-20, unrounded, not pre-registered) is the first measured tranche book:
  A-weekly 1.25 / -13.9% / 3.4x (vs 1.12 / -16.9% / 3.4x), B-weekly 0.91 (0.81), C-weekly 1.00 (0.70).
- Not a duplicate of the rejected "pick the weekday/hour" (nothing is chosen; the result is the cross-weekday mean, not
  the best weekday) and not the "daily vs weekly" comparison (weekly-book turnover with daily-book timing diversification
  was never run in the repo).
- Mechanism: RTL falls ~1/N; mean return unchanged; the gain is variance reduction plus a lower-vol average path. Local
  smoke is consistent on all three panels (lands at the weekday mean, better DD, same turnover).
- Weaknesses to carry into the test: (1) at $1,000 the daily 1/7 steps are sub-contract for every coin but XRP/ADA/BCH
  (full-signal weight for a 60%-vol coin is $46, a 1/3-signal step $15, a 1/7 tranche of that $2); the book then trades
  only when the moving average crosses a contract boundary, so the realized construction at $1,000 is "rounding-
  gated"; T5 shows rounding noise of about +/-0.1 Sharpe at $500-1,000, the same size as the claimed gain. (2) The smoke
  averaged seven separately-costed books; the netted single-account version has equal or lower turnover, so the cost
  side is conservative, but order COUNT (the band's job at $1,000) was not reported. (3) It needs the daily VM book,
  i.e. a watcher; the hand book cannot run it (TIME-4 is the hand-book version).
- Evidence quality: replicated_multi_asset (RTL/tranching across equities, TAA, multi-asset trend indices, and the
  local 3-panel smoke) with the caveat that every external source is abstract-level only.
- Refined rule: w_t = target_weights(looks (20,60,120), vol_win 60, TV 0.25, long_only) daily at the 00:00 UTC close;
  ws_t = mean(w_t..w_{t-K+1}), K = 7 primary, {3, 5} sensitivity, K = 1 = the daily band-10 book as control;
  n_i = round(ws_i x E / (P_i cv_i)); 10% band; taker at 00:05 UTC. Pre-register: report unrounded AND whole-contract
  at $1,000 / $2,500 / $5,000 on A, B (24-perp ex-ante) and C (Delta); success = Sharpe within 0.03 of the seven-weekday
  mean on each panel with orders/yr <= 350 at $1,000 and turnover <= the weekly book's; report orders/yr, fees/yr, maxDD,
  2022, 2025-26. Netting at the account level (one position), not seven sub-accounts.
- Test cost: trivial (the harness already runs it unrounded; add the K-day mean of W and `capital` rounding; ~10 lines).

### TIME-2 Signal smoothing: K-day overlapping mean of the sign ensemble before flooring (K = 5 or 7) -> REFINE
- Prior repo test: none. Nearest: T3b/T3k dispersion (what it would cure) and the Phase-2 `tranche7_smoke` (the
  weight-smoothing cousin: smoothing sig/vol instead of sig alone). The B&K "continuous signal cuts turnover > 1/3 with no
  loss" evidence is about replacing sign() with a t-stat signal, which the `sig_continuous` smoke already contradicted
  on all four panels (1.18 vs 1.25, 0.98 vs 1.12, 0.75 vs 0.85, 0.70 vs 0.81); it is not evidence for time-averaging.
- What differs materially from TIME-1: (a) vol is not smoothed, so at the daily cadence TIME-2 is TIME-1 minus the vol
  smoothing (second-order; vol60 moves slowly); (b) the WEEKLY variant is a different object from what the spec claims:
  executing the 7-day-averaged signal once on Monday is NOT "the netted orders of 7 equal tranches". Tranche j's
  decision (made on weekday j) is executed up to six days late and no position changes between Mondays; T3k tested
  execution lags only up to 24 h. The honest label is "weekly book on a lagged/smoothed signal". It may still help (it
  damps single-day sign flips near zero), but its expectation is not the seven-weekday mean.
- Rounding: signal steps of 1/21 (K = 7) are below one contract for BTC/BNB/ETH at $1,000, so at $1,000 the daily
  variant collapses toward the band-10 daily book for the majors.
- Evidence quality: snippet_only for this exact construction (J-T / B&K overlapping portfolios are a statistical
  methodology, not a performance claim; the "no significant difference" sentence was not found; the stock-selection
  warning that a 21-day MA cut gross Sharpe 31% is the over-smoothing risk).
- Refined rule: fold into the TIME-1 sweep as one extra line per K: s_i,t = (1/K) sum_{j<K} (1/3) sum_L sign(P_{t-j}/
  P_{t-j-L} - 1), signal = max(s, 0), vol unsmoothed, daily cadence, K in {3, 5, 7}; decide between "smooth the
  weights" (TIME-1) and "smooth the signal" (TIME-2) by the pre-registered criterion (Sharpe on B 2022-26 at equal
  turnover), not post hoc. Run the weekly-execution variant as a separate, honestly labelled line ("Monday execution of
  the K-day-smoothed signal") only if the hand book must stay at one session a week; success for that line = Sharpe
  >= the design's 1.12 + 0.03 on A and >= 0.70 + 0.1 on C with trades/yr <= 200.
- Test cost: trivial (a rolling mean of the signal matrix; the harness has rolling_mean_rows).

### TIME-3 Decision-hour tranching: average the sign signal over six H-aligned daily close series, execute at 00:05 -> KEEP
- Prior repo test: T3k ran the six single-hour books (1.12-1.32) and the pure execution lags (+4..+24 h: 1.09-1.15),
  never the average. The rejected item is "changing the decision hour for performance" (D2's 00:00 -> 04:00 for
  convenience that raised 1.26 -> 1.32); averaging all six is the opposite operation.
- Construction check: for H > 0 the latest H-close is 4-20 h old at the 00:00 decision, inside the lag range T3k showed
  to be free (<= 0.03), so unlike TIME-2's weekly variant this is a legitimate signal-sampling tranche with zero extra
  executions. It is a mild smoothing: the six closes are within 24 h of each other, so the averaged signal differs from
  the design's only when a lookback return sits near zero at some hours and not others; it removes single-hour sign
  flips (steps of 1/18). The expected gain is the hour-luck variance (T3k sd 0.06, design lowest of six), not alpha.
- Data: Binance 1h for the 9 coins is cached (`scratchpad/hourly/`), Delta hourly JSON for the 9 is in
  `research2/delta_data/`, so panel C is possible; panel B (24 perps) would need hourly downloads from
  data.binance.vision (reachable) for 15 more coins, or run B on daily closes only.
- Rounding: 1/18 steps are sub-contract at $1,000 for the majors (same caveat as TIME-1/2).
- Evidence quality: single_study (the repo's own T3k dispersion plus the RTL mechanism; the Newfound "when" post is an
  unverified blog). No external study of this construction exists.
- Refined rule: at each 00:00 UTC decision, for H in {0,4,8,12,16,20} build C^H (close of the hourly bar ending at H:00;
  for H > 0 use the previous day's H:00 so no look-ahead), s^H_i = (1/3) sum_L sign(C^H_t / C^H_{t-L} - 1), signal_i =
  max(mean_H s^H_i, 0); vol from the 00:00 closes; size, round, band, execute as now. Variants: all 24 hourly offsets.
  Pre-register on A and C at daily and weekly cadence (weekly: Monday decision only); success = Sharpe within 0.03 of
  the six-hour mean (1.21 weekly) on A, no increase in orders/yr, and no loss on C. Treat it as a supplement to TIME-1
  (both can run; they address different luck axes), run after TIME-1.
- Test cost: small (a new signal builder from hourly closes; qd_engine's h_aligned_closes does most of it; ~30 lines).

### TIME-4 Two tranches for the hand book: Monday 00:05 and Thursday 00:05 UTC, half the capital each -> REFINE
- Prior repo test: none as a book; T3b has both single-weekday books. Naming defect: a Thursday 00:05 UTC execution
  uses the WEDNESDAY candle (closes Thu 00:00), which scored 1.34 / -11.2% / 2022 -4.1% in T3b; the spec's "Thu-candle
  1.31" is the Friday 00:00 execution. Either way the in-sample pair average must not be the expectation (the design
  weekday is the worst of seven, so any pair looks good in-sample); the honest expectation is the seven-weekday mean
  with half the RTL removed by K = 2 rather than 6/7 by K = 7.
- Implementation defects in the spec: (1) per-tranche band at half size pushes ETH ($24 x 1/2 = 1 contract or 0),
  LINK, DOGE and BCH to zero at $1,000 (the spec admits this); (2) the half-gap variant n_t = held + round(0.5 x (target
  - held)) never trades a one-contract gap (round(0.5) = 0 under Python's banker's rounding, and 0 under any rounding
  for |gap| = 1), so at $1,000 most coins would never move; it needs "trade ceil(0.5 x |gap|) contracts toward target,
  minimum 1 when |gap| >= 1". (3) Concretum's "~2 tranches at $25K" rests on per-order commissions; on Delta costs are
  proportional, so K is bounded by contract granularity, not commissions; the right K for the hand book is an
  operational choice (sessions per week), not a cost optimum.
- Evidence quality: replicated_multi_asset for the mechanism (same as TIME-1); the K = 2 specifics are vendor-sourced
  and equity-specific.
- Refined rule: one aggregate position; on Monday 00:05 and Thursday 00:05 UTC compute target_t from that day's 00:00
  close (TV 0.25) and trade d = target - held with q = sign(d) x max(1, ceil(0.5 x |d|)) contracts if |d| >= 1, subject
  to the 10% band on the full gap; closes always trade. Test it as the K = 2 line of the TIME-1 sweep (3/4-day spacing)
  with whole contracts at $1,000 / $2,500 / $5,000 on A, B, C, plus a Mon/Fri spacing line as a robustness check only.
  Success = Sharpe >= 1.12 + 0.05 on A weekly and >= 0.70 + 0.1 on C with orders/yr <= 220 at $1,000 and the realized
  gross within 10% of the one-session book (checks that the min-1-contract rule is not inflating exposure).
- Test cost: trivial (second decision weekday + a trade-fraction rule in the simulator).

### TIME-5 Partial adjustment toward the daily target (lambda = 1/5) -> REFINE
- Prior repo test: none. It is the exponentially weighted twin of TIME-1 (SMA K = 7 ~ EWMA lambda = 2/(K+1) = 1/4).
- Mechanism mismatch: Garleanu-Pedersen's constant trading rate is the solution under quadratic (impact) costs. At
  $1-5k on Delta costs are proportional (5.31 bps + spread, no impact), for which the optimal policy is a no-trade zone
  (T3c's band / the COST buffer), not a trading rate. What remains valid is the timing-luck diversification (Hoffstein's
  "correct 1/K of the drift" is exactly this rule), so TIME-5 is not a separate idea: it is TIME-1 with exponential
  weights and one more free parameter (lambda). AQR's "25% toward target is enough" is a strategic-allocation result.
- Rounding: lambda x gap < 1 contract for every coin at $1,000 except XRP/ADA; without a "min 1 contract when |gap|
  >= 1" rule the book never moves on the majors; with it, the rule degenerates to "trade one contract a day toward
  target", which is a reasonable small-account tranche but is a different rule from the spec.
- Evidence quality: single_study (GP 2013 is one theory paper with a commodity-futures implementation; AQR is a vendor
  white paper on a different problem).
- Refined rule: run as ONE line in the TIME-1 sweep: x_t = x_{t-1} + lambda (w_t - x_{t-1}), lambda = 1/4 (the EWMA
  equivalent of K = 7), contracts = round(x_t E / (P cv)) with "min 1 contract toward target when the rounded gap >= 1",
  10% band on the full gap; compare with SMA K = 7 at equal turnover; do not sweep lambda unless the K-sweep is also
  reported in full. Pick SMA or EWMA before the run (SMA K = 7 is the pre-registered primary; the EWMA line is a
  robustness check, not a candidate for selection).
- Test cost: trivial (one line in the weight path).

### TIME-6 Asymmetric cadence: increases weekly, decreases/exits daily -> DROP
- Prior repo test: none directly. Related: T1 (daily book dominates the weekly book on DD, 2022, worst week at the
  same Sharpe and is the documented upgrade path); section 5.2 (the re-entry-room and chop grafts, the two
  "asymmetric" prop grafts, had no measurable effect); T3i (any daily flatten/re-entry costs Sharpe once both legs are
  charged).
- Why drop: (a) no study at all and no verifiable mechanism; (b) the local conditional check (section 2) shows the
  strategy's best days follow its worst days (+0.87% to +1.28% over the next three days after a < -3% day, t 1.9-2.2),
  and a daily-reduce / weekly-add rule systematically holds less exposure in exactly those windows (a signal drop or a
  vol spike on a sell-off day triggers the cut, the add waits for Monday), so its expected effect on return is
  negative and its expected effect on DD is the small one the cool-down check showed (<= 2 pp); (c) it needs a daily
  watcher, so operationally it is the daily book with less of the daily book's benefit; the daily book (and TIME-1)
  dominate it on every metric for the same operational cost; (d) it lowers average gross, so any Sharpe comparison must
  be vol-matched, which the spec does not do.
- Evidence quality: snippet_only.
- Refined rule (only if Phase 2 wants a one-line ablation inside the TIME-1 sweep, not as a candidate): daily target
  w_t; Monday: trade to target both ways; other days: trade only if n_target,i < n_held,i (sell to target), never buy;
  vol-match by scaling TV so realized vol equals the weekly book's; report Sharpe, maxDD, 2022, orders/yr.
- Test cost: trivial (sign condition on the trade), but not recommended.

### TIME-7 Post-crash cool-down: halve gross for three days after a strategy day below -3% -> DROP
- Prior repo test: section 5.2 G4 (re-entry only if room >= 1.5%, else flat to the next 7-day boundary) and G5 (chop
  detector 3 trips / 10 d -> k/2 for 30 d): "no measurable effect"; T3i: every daily flatten-and-re-enter rule costs
  0.07-0.13 Sharpe with both legs charged. The weekly variant ("skip the next Monday's adds after a week below -5%")
  is G4 in weekly clothing.
- Direct refutation (section 2): after a < -3% day the next-3-day return is +0.87% (daily line, t 1.94, 30 events) and
  +1.28% (weekly line, t 2.20, 9 events) against unconditional +0.19% / +0.12%; the K = 3 x 0.5 rule costs Sharpe 1.25 ->
  1.19 and 1.12 -> 1.09 before its two extra round trips, buys <= 2 pp of maxDD on the daily line and makes the weekly
  line's maxDD worse (-17.3% vs -16.9%). The literature cited by the candidate itself (Dobrynskaya loser rebound,
  Kozlowski next-day reversal) points the same way. Thirty events in 6.4 years: any positive result would be noise, and
  the measured result is negative.
- Evidence quality: snippet_only (no supporting source; contrary sources unverified but consistent with the local check).
- Refined rule: none. If anyone insists, the pre-registered test is the one in section 2 with costs charged (two extra
  round trips per event at 7.31 bps per side on half the gross), success = Sharpe not below the base line AND maxDD
  improved by >= 3 pp on A, B and C; it fails on A and C already without costs.
- Test cost: trivial (done above without costs; with costs a few lines), but not recommended.

## 5. Summary table

| id | verdict | prior repo test | evidence | cost | one line |
|---|---|---|---|---|---|
| TIME-1 | keep | T3b seven weekday books (mean 1.23), never averaged; Phase-2 smoke tranche7 1.25 / 0.91 / 1.00 unrounded | replicated_multi_asset (abstracts only) | trivial | the one timing change with a mechanism, multi-asset support and a consistent local smoke; must be re-run rounded at $1k/2.5k/5k |
| TIME-2 | refine | none; sig_continuous smoke contradicts the B&K evidence it cites | snippet_only | trivial | fold into the TIME-1 sweep as "smooth the signal, not the weight"; the weekly variant is a lagged-signal book, not 7 tranches |
| TIME-3 | keep | T3k six single-hour books (1.12-1.32), never averaged | single_study (local) | small | legitimate zero-execution tranche over the signal-sampling hour; run after TIME-1 |
| TIME-4 | refine | none; T3b single-weekday books | replicated_multi_asset (K=2 specifics vendor/equity) | trivial | hand-book K=2 line of the TIME-1 sweep; fix the Wed-candle naming and the round(0.5 x gap) = 0 defect |
| TIME-5 | refine | none | single_study | trivial | EWMA twin of TIME-1; GP's quadratic-cost rate does not apply to proportional fees; one robustness line, no lambda sweep |
| TIME-6 | drop | T1 (daily book dominates), 5.2 G4/G5 null | snippet_only | trivial | no evidence; conditional returns after sell-offs are the strategy's best days, which the rule would under-hold |
| TIME-7 | drop | 5.2 G4/G5 null, T3i | snippet_only | trivial | measured: next-3-day +0.87% / +1.28% after < -3% days; the rule costs 0.03-0.06 Sharpe before costs |

Reading order for Phase 2 in this family: TIME-1 (with TIME-2, TIME-4, TIME-5 as lines of the same K-sweep), then
TIME-3. Every line reported unrounded and whole-contract at $1,000 / $2,500 / $5,000 on the 9-coin, 24-perp ex-ante
and Delta panels, with orders/yr and fees/yr, Sharpe on B 2022-26 as the primary metric, no selection among K or
lambda after the fact.
