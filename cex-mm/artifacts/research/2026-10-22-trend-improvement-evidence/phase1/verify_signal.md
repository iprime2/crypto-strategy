# Adversarial verification: SIGNAL family (SIG-1..SIG-12), 2026-10-21

Verifier pass over the 12 consolidated signal candidates. Job: refute. Verdict per candidate: keep / refine / drop,
with the prior repo test that already covers it, the honest evidence grade, the exact refined rule, and the cost to
backtest in a pure-Python daily engine on the local data.

## What was read (read-only; nothing in the repo edited, nothing run that places orders)

Repo evidence:
- `resource/07-trend-rule-and-prop-trading-research.md` section "What was considered and rejected" (lines 167-193):
  single lookback / no vol targeting (T3d; B8-B9), regime filters (T3j, d3_regime_filter_output.txt), day stop (T3i),
  drawdown de-leveraging, BTC-only / BTC+ETH, shorts, changing the weekday/hour, ML / stacking.
- `cex-mm/artifacts/research/2026-10-13-prop-strategy-evidence/backtest_results.md`: pre-registered plan (T0-T7),
  T3 table, T3d lookbacks, T3j regime filters, T3k lag/hour, T6, T7 red flags.
- `d3_runs/d3_tests_output.txt` (A1-A4 benchmarks incl. A4 always-long vol-targeted basket Sharpe 0.96 / DD -54%; B0-B9
  ablations), `d3_tests2_output.txt`, `d3_tests3_output.txt`, `d3_regime_filter_output.txt`.
- `av_runs/av_universe_9.txt` (ex-ante 24-perp universe: daily 0.86, weekly 0.82), `av_sub.txt` (sub-periods; signal
  contribution: rule vs always-long basket at matched TV/cadence/costs: weekly 1.12 vs 0.99, DD -16.9% vs -36.6%),
  `av_delta.txt`, `av_dsr.txt`, `av_lows*.txt`, `props_*.txt`.
- `cex-mm/artifacts/research/2026-10-08-trend-following-backtest.md` (the --grid: 18 settings, Sharpe 0.99-1.25 Binance,
  0.48-1.02 Delta; (10,30,60), (20,60,120), (50,100,200), (20,), (60,), (120,) x TV 0.25/0.40/0.60).
- `cex-mm/scripts/trend_backtest.py::target_weights` (sign() returns -1/0/+1; mean over looks; floor at 0 for
  long-only => the mapping from "number of positive lookbacks" to signal is {0:0, 1:0, 2:1/3, 3:1}).

Scratchpad (not repo) evidence that bears on this family:
- `scratchpad/tools2/{rules,sim,evaluate,variants}.py`: the phase-2 numpy harness. `rules.py` already implements
  sig_continuous (z-score cap), sig_tstat, sig_ols_tstat (BK 2013 and 2020 forms), sig_ewmac / sig_ewmac_carver,
  sig_breakout, sig_donchian (WITHOUT the ratcheting stop), sig_macd_baz, sig_signcount, sig_sepp_ls. The harness
  reproduces the repo baseline to printed precision (check_baseline.py; phase2/baseline.json A-daily 1.2498).
- `scratchpad/research2/phase2/sig_continuous.json` (2026-10-20, labelled a harness smoke test, NOT pre-registered):
  signal = max(mean_L clip(z_L,-2,2)/2, 0), z_L = r_L/(vol60*sqrt(L/365)), repo sizing. Results vs baseline.json:
    A-daily  (9 coins, TV0.40)   Sharpe 1.18 vs 1.25 | CAGR 15.5% vs 24.2% | vol 13.0% vs 18.7% | DD -18.8% vs -21.9% | gross 0.12 vs 0.20 | turnover 7.1x vs 15.7x
    A-weekly (9 coins, TV0.25)   Sharpe 0.98 vs 1.12 | DD -14.7% vs -16.9% | 2022-26 Sharpe 0.50 vs 0.66
    B-daily  (24 ex-ante)        Sharpe 0.75 vs 0.85 | DD -19.4% vs -24.7% | 2022-26 0.60 vs 0.59
    B-weekly (24 ex-ante)        Sharpe 0.70 vs 0.81 | DD -12.7% vs -17.0%
  Sharpe is scale-free (costs and funding are proportional), so the comparison stands; the lower maxDD is bought with
  30% less vol and is no better once vol-matched (-18.8% x 18.7/13.0 ~ -27%). This is a LOCAL, in-sample smoke result,
  but it is a direct test of "proportional trend-strength sizing" on exactly our data and it went the wrong way on all
  four panels.
- `scratchpad/research2/tools/diag.py` output (overlays angle): positive-lookback count 0/1/2/3 on 24.7/23.6/25.4/26.3%
  of coin-days; veto state 11.8%; z20 > 2 on 23.2% of full-signal coin-days.

Sources re-opened by me (raw.githubusercontent.com; files saved under `scratchpad/research2/verify_dl/`):
- ExpectedReturns `Improving-time-series-momentum.Rmd` [VERIFIED]: TREND(t-J,t) = +1 if t(beta) > +2, -1 if t(beta) < -2,
  else 0, where t(beta) is the t-stat of the OLS slope of a linear time trend on price. SMT adds R^2 > 0.65. "TREND and
  SMT are the only signals that can result in inactive positions." So the 2013 BK rule is a +/-2 dead zone on the OLS
  slope, not the +/-1 clip; the +/-1 clip of the daily-return t-stat is the 2017/2020 "Demystifying" form [UNVERIFIED].
- Sepp-Lucic `case_study_futures_evidence.md` [VERIFIED]: SG Trend comparison 1999-12-31..2026-07-10, European /
  American / TSMOM net Sharpe 0.47 / 0.50 / 0.55 vs index 0.47, Ledoit-Wolf p 0.96 / 0.82 / 0.62; vol-normalised
  turnover 300-400%/yr for European and TSMOM vs 125-200% for American ("trades discretely", ~50% lower costs);
  LS(250,20) "reasonable long-term performance at moderate turnover"; closed-form Sharpe predicts realised with corr 0.99.
- galata-research `donchian-ensemble.md` [VERIFIED]: pre-registered 2026-09-25, BTC/ETH Hyperliquid perps, 1,216 days
  2023-05-28..2026-09-24, 4.5 bps taker, NO funding, lev cap 1. Sized BTC Sharpe 0.97 vs B&H 0.97, DD -15.0% vs -53.0%;
  ETH 0.72 vs 0.50, DD -14.0% vs -67.6%; DSR 0.921 (N=4), PBO 0.631 -> "not supported on this record"; post hoc: DD cut
  to ~1/4 of B&H at the same or better Sharpe. Rule text confirms the ratcheting mid-line stop and "exit before entry".
- AFTS reader notes README [VERIFIED as text]: "Carver noted that evidence in favor of using trend strength in a forecast
  to size positions was weak, at least for the EWMAC64 and introduced forecast capping as a fait accompli"; on the
  trend-strength adjustments (double-V, scale-and-cap at 15): "Very small impact, Carver, himself, wouldn't trade it".

Local diagnostics run by me (`scratchpad/research2/tools/verify_sig_diag.py`, Binance 9 coins 2020-05-01..2026-09-30,
descriptive only, no strategy returns):
```
L= 20: coin-days 20916; |t|<1 69.8%; |t|<2 95.7%; t>0 50.2%; 0<t<1 (graded long region) 33.3% = 66% of positive days
L= 60: coin-days 20774; |t|<1 66.5%; |t|<2 96.0%; t>0 52.4%; 0<t<1 (graded long region) 33.1% = 63% of positive days
L=120: coin-days 20500; |t|<1 67.0%; |t|<2 95.1%; t>0 51.6%; 0<t<1 (graded long region) 31.4% = 61% of positive days
sign(14d) == sign(20d) on 80.8% of 20976 coin-days
sign(28d) == sign(20d) on 80.8% of 20968 coin-days
sign(28d) == sign(60d) on 73.3% of 20938 coin-days
sign(250d) == sign(120d) on 72.7% of 19615 coin-days
sign(360d) == sign(120d) on 69.1% of 18625 coin-days
sign(10d) == sign(20d) on 73.5% of 20976 coin-days
sign(30d) == sign(20d) on 79.4% of 20966 coin-days
first day with 250 prior closes (Binance): BTC:2020-09-07, ETH:2020-09-07, XRP:2020-09-12, BNB:2020-10-17, ADA:2020-10-07, LTC:2020-09-15, LINK:2020-09-23, DOGE:2021-03-17, BCH:2020-09-07
first day with 360 prior closes (Binance): BTC:2020-12-26, ETH:2020-12-26, XRP:2020-12-31, BNB:2021-02-04, ADA:2021-01-25, LTC:2021-01-03, LINK:2021-01-11, DOGE:2021-07-05, BCH:2020-12-26
average signal level: current 34.7%, linear count 51.1%, any-sleeve 'max' 75.3%, always-long 100% (coin-days 20772)
```
Readings: (i) a +/-2 dead zone (the verified 2013 TREND form) is inactive on 95-96% of coin-days per lookback, so it
is not a viable rule here; a +/-1 dead zone or clip grades 61-66% of the positive days. (ii) 14- and 28-day signs
agree with the 20-day sign on 81% of coin-days, i.e. they re-weight the ensemble toward the fast end rather than add
information. (iii) The exposure-raising mappings sit on one line: current 35% -> linear count 51% -> any-sleeve 75% ->
always-long 100%; the repo has measured the right-hand end (av_sub: weekly Sharpe 0.99 vs 1.12, DD -36.6% vs -16.9%;
d3 A4 daily 0.96 vs 1.25, DD -54% vs -22%).

Cross-cutting facts that apply to every continuous candidate (SIG-1, 2, 3, 5, 6, 11):
- At $1,000 the per-coin full budget is ~$46 at TV 0.25 (~$110 at TV 0.40 daily), below one BTC (~$80) or BNB (~$73)
  contract, so graded exposure rounds to 0 or 1 contract on the two largest coins; grading exists only from ~$5,000.
  Judge these on the unrounded series and at $5,000; report turnover and funding/yr, not only Sharpe.
- T3c: the 10% band cut weekly trades 278 -> 192 at identical Sharpe and the daily band cut 1,773 -> 531 at 1.25:
  turnover is not what limits the Sharpe, so "lower turnover" is only a win if it shows up as lower funding at the
  same Sharpe. Funding is 2.1%/yr (weekly) / 3.4%/yr (daily) of equity and scales with gross.
- Levine-Pedersen (unverified) and Sepp-Lucic (verified) both say the filter shape is second order at matched speed;
  the only verified direct test of graded exposure on our data (the smoke run above) lost 0.07-0.14 Sharpe on all four
  panels. The family's prior is therefore "Sharpe flat to slightly negative; turnover down"; one or two lines deserve a
  pre-registered run, not twelve variants.

## Verdicts

### SIG-1 BK TREND t-statistic (clip +/-1; dead-zone variant) -> REFINE
- Prior test in repo: none. Scratchpad smoke `phase2/sig_continuous.json` tested the cousin clip(z,+/-2)/2 mapping on
  the same data: worse on all four panels (see above). T3c shows turnover is not binding.
- Evidence: BK ~75 futures 1974-2013 "insignificantly different from SIGN" [UNVERIFIED]; Sepp-Lucic 84 futures
  linear 0.47 / binary 0.50 / TSMOM 0.55, p 0.62-0.96 [VERIFIED docs]; BK 2011 WP 12 futures in-sample 1.18 vs 1.00
  [SECONDARY]. Replicated, multi-asset, and a null. The turnover claim is self-contradictory across summaries
  (-24% vs -66%) and unverified.
- Refutation points: (a) the verified 2013 definition is a +/-2 dead zone on the OLS-slope t-stat, which is inactive
  on 95-96% of our coin-days: not viable; (b) the candidate bundles 3 numerators x 2 mappings x 2 thresholds = 12
  variants; (c) Mapping A clip(t,-1,1) with t = sqrt(L)*mean/sd is, up to the vol window, the same object as SIG-2(b)
  with d = 1 (z_L = r_L/(vol60*sqrt(L/365))), so SIG-1A and SIG-2 are one test, not two; (d) at $1,000 grading is
  rounded away on BTC/BNB.
- Refined rule (two lines, merged with SIG-2): t_L = mean(r)/(sd(r)/sqrt(L)) over the last L daily log returns, plain
  (no Newey-West, no OLS slope). Line A: s_L = clip(t_L,-1,+1). Line B (sparsifying, the materially different
  mechanism): s_L = 0 if |t_L| < 1 else sign(t_L). signal_i = max(mean_L s_L, 0); sizing, vol, cap, cadence unchanged.
  Pre-registered acceptance: on the ex-ante 24-perp panel 2022-26, Sharpe within -0.03 of baseline AND trades/yr and
  funding/yr down >= 25%; or Sharpe +0.05 on both halves. Report unrounded and $5,000; $1,000 for information only.
- Cost: trivial (rules.sig_tstat exists; ~10 lines in target_weights).

### SIG-2 Vol-normalised z-score with proportional cap (Carver continuous forecast) -> REFINE (merge into SIG-1 line A)
- Prior test in repo: none. Scratchpad smoke `phase2/sig_continuous.json` = variant (b) with d = 2 up to the order of
  floor and mean: Sharpe -0.07 / -0.14 / -0.10 / -0.11 on A-daily / A-weekly / B-daily / B-weekly, gross -40%,
  turnover -55%, vol-matched DD no better.
- Evidence for the improvement: Carver "continuous capped beats binary" is memory [UNVERIFIED]; AFTS notes [VERIFIED
  text] say the trend-strength evidence is weak and the adjustments have "very small impact, Carver himself wouldn't
  trade it"; Sepp-Lucic [VERIFIED] null; Gbadebo 2026 vendor-ish single in-sample [UNVERIFIED]. Multi-asset evidence
  exists and it is a replicated null; the one local test is negative.
- Refutation points: three parameterisations (a: k=1.25/cap 2 = clip(0.625*mean z,0,1), i.e. d = 1.6 on the mean;
  b: d in {1,2,3}; c: expanding median z*, which fits a scalar in-sample) = five trials for one idea; d = 2 already
  lost; (c) is a fitted scalar; the sign ensemble is already four-level, so the "grading" the candidate adds is
  inside each sleeve, where the Bussgang 0.80 factor is the whole theoretical case and the realised net numbers do not
  show it.
- Refined rule: exactly one line, s_L = clip(z_L, 0, 1), z_L = ln(P_t/P_{t-L})/(vol60_daily*sqrt(L)), sig_i = mean_L
  s_L (this is SIG-1 line A with the 60-day vol in the denominator; run SIG-1A and this as the same slot, pick the vol60
  form because it reuses the rule's own estimator). Drop (a) and (c). Acceptance as SIG-1. Expectation entered in the
  pre-registration: Sharpe -0.05 to 0.00, turnover -30%.
- Cost: trivial (rules.sig_continuous with cap 1 and a one-sided clip; ~8 lines in target_weights).

### SIG-3 EWMAC multi-speed continuous ensemble (16/64, 32/128, 64/256) -> REFINE
- Prior test in repo: none for EWMAC; T3d brackets the speed dimension in sign form ((10,30,60) 1.08, (20,60,120)
  1.12, (50,100,200) 0.95); the scratchpad smoke covers the "graded exposure" mechanism (negative).
- Evidence: Levine-Pedersen equivalence [UNVERIFIED]; Carver scalars and rule code [VERIFIED pysystemtrade];
  Lim-Zohren-Roberts MACD trio 1.11 < sign(12m) 1.39 zero-cost [UNVERIFIED secondary]; Rozario BTC hourly no-cost
  [UNVERIFIED, not usable]. Replicated multi-asset null on the shape question; nothing says EWMAC beats sign.
- Refutation points: (a) the spec has free choices (3 or 4 speeds, two scalar sets, FDM 1.2, cap 1/1.5/2): FDM 1.2
  with f = combined/10 in [0,2] lets a coin take 2x the sign rule's per-coin budget, so the test confounds shape with
  leverage; (b) span 256 needs ~3 spans (~770 days) to lose its initialisation, so the Delta-native panel (alts from
  2024-04-10, ~900 days) is a weak OOS check for the slowest pair; (c) EWMAC(64,256) is close to long-only on crypto
  (Carver's own note that slower than (64,256) is ~long-only), which drags the ensemble toward the always-long
  endpoint the repo has measured as worse.
- Refined rule: pairs (16,64),(32,128),(64,256) only; sigma_px = EWMA-35 std of daily price changes; raw_n =
  (EWMA_n - EWMA_4n)/sigma_px; scaled_n = raw_n * {3.75, 2.65, 1.87} (chapter-15 values, fixed); capped_n = clip(scaled_n,
  -20, 20); combined = mean_n capped_n (FDM 1.0); f_i = clip(combined, 0, 20)/20 in [0,1] so the per-coin budget
  matches the sign rule; w_i = f_i*(TV/N)/max(vol60,0.05). The /10 -> [0,2] version is a labelled secondary line at
  most. Binary control sig = mean_n 1[raw_n > 0] separates kernel from grading (that control is the real "EWMAC vs
  point-to-point sign" test and should be the first line run). Acceptance as SIG-1, plus maxDD at matched vol no worse.
- Cost: small (an EWMA over prices and a price-unit vol; rules.sig_ewmac_carver exists; ~30 lines pure Python).

### SIG-4 Donchian channel ensemble with ratcheting mid-line exit (Zarattini-Pagani-Barbon) -> KEEP
- Prior test in repo: none (cited in `research_notes/practitioner_strategies.md`, never run). The rejected
  "per-position stops" (T4 pos-stop 3% series; resource/07 table) are fixed-percentage loss stops; the channel
  mid-line exit is the trend definition's own exit, a different mechanism, and this must be said in the memo.
- Evidence: vendor (Concretum) in-sample crypto 2015-2025, PDF not opened, four GitHub transcriptions agree
  [SECONDHAND]; independent pre-registered replication [VERIFIED file]: Sharpe not above B&H (0.97 vs 0.97 BTC;
  0.72 vs 0.50 ETH), DSR 0.92, PBO 0.63 -> "not supported", DD cut to ~1/4 of B&H; Zarattini-Antonacci 48 industries
  1926-2024 long-only Donchian [UNVERIFIED]; Sepp-Lucic [VERIFIED]: stateful/discrete designs have ~50% lower
  vol-normalised turnover. Grade: single_study (crypto, vendor), with one failed replication on Sharpe and a
  consistent drawdown result.
- Why it survives: the only candidate that is (a) never tested here, (b) binary and stateful (survives $1,000
  rounding exactly as the sign rule does; turnover lower by construction), (c) fully specified with costs and a
  cost-mitigation rule, (d) a genuinely different speed mix (5-360 days) rather than a re-mapping of the same three
  returns. The replication's picture (Sharpe = beta, DD halved) is the same as the repo rule's own (av_sub), so the
  question Phase 2 can answer is whether DD/Calmar at matched vol and turnover improve over the sign rule, not
  whether it "has alpha".
- Refutation points to carry into the pre-registration: the paper's single-lookback BTC Sharpes (5d 1.66 ... 150d
  0.99, combo 1.58) show the combo is not above the best singles and the sample includes 2015-17 and 2020-21
  melt-ups; the 360-day channel starts 2020-12..2021-07 on Binance (DOGE 2021-07-05) and 2025-04 on Delta, so the
  2020 melt-up drops out unless eligible-channel normalisation is used (report both the 9-lookback and the
  7-lookback <= 150 variants, and start the comparison on the same days as the baseline); the 5- and 10-day channels
  trade ~15-30 round trips a year each on BTC (paper Table 1: 292 and 156 trades in 10 years), fine at 7.31 bps but
  they are the sleeves most exposed to the Monday-only execution of the weekly book.
- Refined rule (as proposed, pinned): per coin, per n in {5,10,20,30,60,90,150,250,360} on daily closes: Up_n = max
  close over the last n days incl. t, Down_n = min, Mid_n = (Up_n+Down_n)/2; exit first: Pos_n = 1 and close <= Stop_n
  -> 0; entry: Pos_n = 0 and close >= Up_n -> 1 with Stop_n = Mid_n; while long Stop_n(t+1) = max(Stop_n(t), Mid_n(t)).
  signal_i = (# channels long)/(# channels with history). Primary sizing: repo form sig_i*(TV/N)/max(vol60,0.05)
  (only the signal changes); secondary: paper form sig_i*min(0.25/vol90, 2). Daily book: trade on any Pos change,
  band only on vol-driven changes. Weekly book: evaluate daily, trade Monday. Lines: 9-lookback and 7-lookback (<=150).
  Acceptance: on the ex-ante 24 panel 2022-26, Sharpe >= baseline -0.03 with maxDD at matched vol >= 3 pp better and
  trades/yr lower; or Sharpe +0.05 on both halves.
- Cost: small (a stateful per-channel loop, ~40 lines; rules.sig_donchian exists but lacks the ratchet and the
  exit-before-entry order).

### SIG-5 Sepp-Lucic European LS(250,20) linear filter -> DROP
- Prior test in repo: none; the scratchpad smoke covers the graded-linear mechanism (negative); T3d (50,100,200)
  covers the slow-kernel direction in sign form (0.95, worst of six).
- Evidence [VERIFIED docs]: on 84 futures 2000-2026 the European design is the weakest of the three (0.47 vs
  American 0.50 vs TSMOM 0.55, index 0.47, Ledoit-Wolf cannot separate them) with 300-400%/yr vol-normalised turnover
  against 125-200% for the discrete design. Replicated, multi-asset, and pointing away from the change.
- Why drop: it is the same linear-filter idea as SIG-2/SIG-3 (Levine-Pedersen) with no advantage on any axis its own
  authors measured (Sharpe no higher, turnover 2-3x the stateful design); the only distinct features (per-day
  r/sigma normalisation, 250-span kernel) add a ~750-day warm-up that removes the Delta-native panel as a check and
  the 2020-21 half of the Binance sample; the candidate's own expectation is "Sharpe equal within noise, higher
  turnover". There is no evidence path to an improvement, so a trial buys only DSR cost.
- If someone insists: one line only, S_t = c*(EWMA_20(z) - EWMA_250(z)), z_t = ln(P_t/P_{t-1})/sigma_{t-1} (EWMA
  span 33), c variance-preserving, signal_i = max(min(S_t, 2), 0)/2 so the per-coin budget matches the sign
  rule's; run only if SIG-2's single line is not rejected. Cost small (rules.sig_sepp_ls exists).

### SIG-6 Baz MACD trio with Gaussian response -> DROP
- Prior test in repo: none for the formula; T3d says the faster direction is worse ((10,30,60) 1.08; 2024-26 0.72
  vs 0.86); the speeds here (EWMA half-lives 8-96 days) are faster than the rule's 20-120-day returns.
- Evidence: the only number is negative: Lim-Zohren-Roberts 88 futures zero-cost MACD trio Sharpe 1.11 (MDD 0.317)
  vs sign(12m) 1.39 (MDD 0.264) [UNVERIFIED secondary table]; formula verified from the reference implementation.
- Why drop: (a) its own evidence has it below the sign family; (b) the response function phi(y) = y*exp(-y^2/4)/0.89
  peaks at |y| = sqrt(2) and shrinks beyond, i.e. it cuts exposure in the strongest trends, which locally are frequent
  (z20 > 2 on 23% of full-signal coin-days) and are where the rule's years are made (2020-21, 2024); (c) three pairs,
  a 63-day price std, a 252-day std of q and the response function = many parameters with a ~1-year warm-up; (d) it
  is dominated by SIG-3 (same EWMA-difference family with a cap instead of a Gaussian shrink). The candidate itself is
  marked "low priority".
- If a "shrink at extremes" control is ever wanted it is one labelled line inside SIG-3, reporting the share of
  coin-days with |y| > sqrt(2). Cost small (rules.sig_macd_baz exists).

### SIG-7 Barbell / add a 250-day sleeve -> REFINE (variant A only, low priority)
- Prior test in repo: T3d (50,100,200) -> 0.95, worst of six, DD -21.7%, 2023 +3.1%, 2025 -2.8%; (120,) -> 1.21 but
  2025 -3.1%; memo --grid (50,100,200) at daily. These test "all sleeves slower", not "add a slow sleeve to the
  existing three", so variant A differs materially; variants B and C do not add information.
- Evidence: Etienne et al. (Ai For Alpha, vendor, in-sample Bayesian horizon weights) "125-day layer redundant"
  [UNVERIFIED]; HOP/MOP 12-month futures evidence [UNVERIFIED, standard]; against: Liu-Tsyvinski / Dobrynskaya
  compressed crypto horizon [UNVERIFIED]; Kang-Ryu "slow beats fast" is a 12-week (~84-day) signal, inside the
  current window, not 250 [UNVERIFIED]. Grade: vendor_or_blog for the barbell claim.
- Refutation points: sign(250d) disagrees with sign(120d) on 27% of coin-days, so the sleeve is not redundant, but
  the repo's slow runs show those disagreements cost money in 2022-25; the 250-day history starts 2020-09..10
  (DOGE 2021-03) on Binance and 2025-01 on Delta, so "exclude until eligible" would change the universe in 2020 and
  the Delta check would cover ~20 months; variant B drops the repo's best single sleeve on a vendor claim; variant C
  (21,63,252) is variant A/B re-labelled.
- Refined rule: looks = (20,60,120,250), signal_i = max(mean over the sleeves the coin has history for, 0)
  (eligible-sleeve normalisation, so the 2020 universe is unchanged); everything else unchanged; one line; expectation
  entered: neutral to negative. Acceptance: Sharpe +0.05 on the ex-ante 24 panel 2022-26 with maxDD no worse; else no.
- Cost: trivial (looks tuple plus a per-coin eligible-sleeve count in target_weights).

### SIG-8 Add 14- and 28-day votes -> DROP
- Prior test in repo: T3d (10,30,60) -> 1.08 vs 1.12 full sample and 0.72 vs 0.86 in 2024-26 (the candidate's own
  stop rule "reject if 2024-26 worsens" is already met by the nearest tested set); memo --grid (10,30,60) daily;
  T3d (20,) single 0.90 (the closest implementable analogue of a 20-30-day long/flat rule).
- Evidence: Han-Kang-Ryu 28d/5d Sharpe 1.51 [UNVERIFIED]; Howden-Andreev 30-day long/flat 7 majors incl. SOL
  (hindsight) 6-page preprint [UNVERIFIED]; Liu-Tsyvinski and Ficura-Colak are factor/cross-sectional return
  predictability, not an ensemble vote [UNVERIFIED]; Kang-Ryu says fast signals overreact in BTC [UNVERIFIED]. Grade:
  snippet_only, and the cited rules are single-lookback, which the repo rejected.
- Why drop: sign(14d) and sign(28d) each agree with sign(20d) on 80.8% of coin-days, so the two extra votes mostly
  duplicate the existing fast sleeve and shift ensemble weight toward the end T3d found worse; the 1-4-week
  predictability mechanism is already in the rule through the 20-day sleeve and the weekly book's 7-day hold; the
  proposed set sits between (10,30,60) and (20,60,120), both on file. No information expected for one DSR trial.
- If a fast control is wanted, T3d's (10,30,60) line already exists. Cost trivial.

### SIG-9 Turning-point aggregation (max / Correction-only / 0.8-0.2 tilt) -> REFINE (diagnostic first; one conditional line)
- Prior test in repo: none for the state machine; the exposure-raising variants (i) and (ii) are bracketed: average
  signal level current 34.7% -> 'max' 75.3% -> always-long 100%, and the repo measured the always-long vol-scaled
  basket at the same TV/cadence/costs (av_sub weekly 0.99 vs 1.12, DD -36.6% vs -16.9%; d3 A4 daily 0.96 vs 1.25,
  DD -54% vs -22%); SIG-10 covers the mildest step on the same line.
- Evidence: Garg et al. JFE 2023, 20 equity markets, dynamic 0.52 vs static 0.51 (1969-2018), 0.61 vs 0.57
  (2004-18) [SECONDARY/UNVERIFIED]; Breaking Bad Trends 43-55 futures dynamic 0.80 vs static 12m 0.64 with turnover
  399% vs 229% [SECONDARY]; Kang-Ryu BTC: dynamic speed adds little [UNVERIFIED]. Grade: single_study (one research
  group, secondhand numbers, estimated weights).
- Refutation points: (i) 'max' is "long unless all three are negative", a leverage-up in ambiguous states (49% of
  coin-days) that the always-long endpoint says costs Sharpe and doubles DD; (ii) 'Correction-only' is (i) restricted
  to the 11.8% veto state; (iii) changes three things at once (drops the 60-day sleeve, replaces 120 with a 2-sleeve
  blend, adds a 20-day post-turn memory with weights the paper estimated in-sample), and its effect in both
  disagreement states is "stay 0.6 long for a month", i.e. more beta.
- Refined rule: first the free diagnostic (no trial): per coin-day classify Bull/Correction/Bear/Rebound with
  SLOW = sign(P_t/P_{t-120}-1), FAST = sign(P_t/P_{t-20}-1) and report the mean and t-stat of the next-7-day return by
  state on the 9 and the 24 ex-ante coins, 2020-26 and 2022-26. Only if Correction-state forward returns are not
  below Bull-state (the mechanism's precondition) run one line: signal_i = max(w_S*SLOW + (1-w_S)*FAST, 0) with
  w_S = 0.5 in Bull/Bear, 0.8 for the 20 trading days after a Correction entry, 0.2 for 20 days after a Rebound entry,
  everything else unchanged. Drop (i) and (ii).
- Cost: small (state machine ~30 lines; the diagnostic ~20).

### SIG-10 Linear agreement count {0,1/3,2/3,1} -> KEEP
- Prior test in repo: none; the current {0,0,1/3,1} mapping is an artefact of flooring the mean of three signs and was
  never justified. Bracketed on one side by the always-long basket (av_sub; d3 A4): moving toward it cost Sharpe and
  doubled DD, so the pre-registered expectation is "CAGR up, beta up, Sharpe flat to lower, DD at matched vol worse".
- Evidence: HOP 2017's canonical multi-horizon TSMOM is linear in the count of agreeing 1/3/12-month signals
  [SECONDARY]; Garg et al. equal blend 0.51 vs 0.41/0.34 in US equities, beats avg(slow,fast) in all 20 markets
  [SECONDARY]; Breaking Bad Trends 1/3/12 average 0.59 < static 12m 0.64 in futures [SECONDARY]. No source compares
  the two mappings directly. Grade: snippet_only for the specific claim; the keep rests on cost (one line) and on
  the mapping being the field's default.
- Local: adds 1/3 on 23.6% of coin-days and raises 25.4% from 1/3 to 2/3; average signal 34.7% -> 51.1%, so funding
  paid rises ~1.5x unless TV is cut; compare at matched realised vol.
- Refined rule (pinned): sig_i = (1/3)*sum_{L in (20,60,120)} 1[P_t/P_{t-L} > 1]; sizing, vol window, cap, cadence
  unchanged; one line; the (0.5,0.3,0.2) mirror weights are a second trial and are dropped. Acceptance: Sharpe
  +0.05 on the ex-ante 24 panel 2022-26 AND maxDD at matched vol no worse (it raises beta, so a flat Sharpe is a
  rejection, not a tie).
- Cost: trivial (one line in target_weights).

### SIG-11 Add Carver's continuous breakout forecast 50/50 -> REFINE (matched speed; run only with SIG-4; low priority)
- Prior test in repo: none. Overlaps SIG-4 (same channel object: continuous channel position vs binary channel
  state with a ratchet).
- Evidence: Carver "comparable Sharpe, imperfect correlation, combination adds a small, probably not significant
  amount" [UNVERIFIED blog memory]; breakout.py and the production config (breakout10..320, scalars 0.60-0.74)
  [VERIFIED code]; the crypto breakout repos are hyperopt/in-sample READMEs and are not evidence [VERIFIED as such].
  Grade: vendor_or_blog.
- Refutation points: lookbacks (20,80,160) differ from the sign rule's (20,60,120), so the proposed test confounds a
  speed change with the shape change; at matched speed Carver's own correlation (0.93 breakout vs EWMAC) says the
  diversification is small; a 50/50 with the sign ensemble halves the weight on the only signal with repo evidence
  for an expected gain of <= +0.05.
- Refined rule: lookbacks (20,60,120) to match the sign rule; b_L = 40*(P - mid_L)/(max_L - min_L) smoothed by EWMA
  span max(int(L/4),1), clipped to [-20,20]; f_B = max(mean_L b_L/20, 0); lines: breakout-only (f_B) and
  sig_i = 0.5*sig_sign + 0.5*f_B, FDM 1.0; run only if SIG-4 is run (same family, shared report); adopt the 50/50
  only if breakout-only >= sign-only on both universes AND the combination beats both.
- Cost: small (rolling max/min over three windows plus an EWMA; rules.sig_breakout exists without the smoothing).

### SIG-12 Skip the most recent k days -> DROP
- Prior test in repo: T3k execution lag +24h (a one-day-stale signal with a shifted holding window) -> 1.15 vs 1.12,
  within noise; nothing on a 2-5-day signal skip.
- Evidence: equities cross-section only (Novy-Marx; Ehsani-Linnainmaa t 1.64) [UNVERIFIED]; crypto evidence of
  continuation at 1-6 days and 1-8 weeks (Liu-Tsyvinski; Han-Kang-Ryu 28d/5d) [UNVERIFIED]. Grade: snippet_only, and
  the proposer labels it a documented negative.
- Why drop: it is a control, not a candidate improvement; the expected direction in crypto is negative; the repo's
  +24h lag already shows a one-day-stale signal is noise; running k = 2 and 5 would spend two DSR trials to confirm
  a result nobody would act on.
- Cost trivial if ever run (shift the price index by k).

## Summary

| id | verdict | prior test | evidence grade | cost |
|---|---|---|---|---|
| SIG-1 | refine (two lines, merged with SIG-2) | none in repo; scratchpad smoke of clip(z,2)/2 negative on 4/4 panels | replicated multi-asset null | trivial |
| SIG-2 | refine (one line = SIG-1A with vol60) | none in repo; scratchpad smoke = variant (b) d=2, negative | replicated multi-asset null; local negative | trivial |
| SIG-3 | refine (fixed spec, f in [0,1], binary control first) | none; T3d brackets speed; smoke covers grading | replicated multi-asset null | small |
| SIG-4 | keep | none (never run; pos-stops are a different mechanism) | single study (vendor crypto) + failed replication on Sharpe, DD holds | small |
| SIG-5 | drop | none; dominated by SIG-2/3 | replicated multi-asset, points away | small |
| SIG-6 | drop | none; T3d says faster is worse | single study, negative | small |
| SIG-7 | refine (variant A only) | T3d (50,100,200) 0.95; (120,) 1.21 but 2025 -3.1% | vendor | trivial |
| SIG-8 | drop | T3d (10,30,60) 1.08 / 0.72 in 2024-26; (20,) 0.90 | snippet only | trivial |
| SIG-9 | refine (diagnostic; one conditional line) | none; (i)/(ii) bracketed by av_sub always-long basket | single study (secondhand) | small |
| SIG-10 | keep | none; bracketed by av_sub / d3 A4 | snippet only (canonical construction) | trivial |
| SIG-11 | refine (matched speed, with SIG-4 only) | none | vendor/blog | small |
| SIG-12 | drop | T3k +24h lag within noise | snippet only | trivial |

Trial budget implied: SIG-1A/2 (1 line), SIG-1B (1), SIG-3 (binary control + continuous = 2), SIG-4 (9- and
7-lookback = 2), SIG-7A (1), SIG-9 (0-1), SIG-10 (1), SIG-11 (0-2 if SIG-4 runs) = 8-11 lines against the
av_dsr.txt reference (E[max null Sharpe] 0.15-0.28 at 18 trials with sd 0.08-0.15). Every line should be reported on
the ex-ante 24 panel 2022-26 first, at matched realised vol, with trades/yr and funding/yr next to Sharpe and maxDD.
