# Adversarial verification: SIZING family (SZ-1 .. SZ-16), 2026-10-21

Role: refute. Verdict = keep / refine / drop. Everything below was read from the repo evidence pack, the scratchpad
diagnostics, or the phase2 scratch engine; nothing external was fetched in this pass (the proxy blocks every paper/blog host).

## 0. What the repo and scratchpad had already tested (the comparison set)

Repo (verified by reading the files):
- `resource/07-trend-rule-and-prop-trading-research.md` "What was considered and rejected": regime filters (BTC<200d: Sharpe 1.25, DD -25.9% daily;
  vol filters 1.00-1.18), drawdown de-leveraging (1.13-1.23 vs 1.25), day-stops (-0.07..-0.13), single lookback / no vol targeting
  (1.04-1.08, DD -35..-54%), BTC-only / BTC+ETH (0.85 / 0.95), weekday/hour selection.
- `backtest_results.md` T3a: TV 0.15/0.20/0.25/0.30/0.40 -> Sharpe 1.12/1.12/1.12/1.13/1.13; DD -10.5/-13.7/-16.9/-20.2/-26.2%;
  worst day -3.0/-3.9/-4.9/-5.9/-7.8%. TV is Sharpe-neutral; DD and worst day are linear in TV.
- T3e vol window 30/60/90 (weekly Mon TV 0.25 band 10%): Sharpe 1.16/1.12/1.08; DD -15.6/-16.9/-17.0%; 2024-26 0.91/0.86/0.83;
  trades/yr 209/192/184; fees/yr 0.28/0.25/0.23%. Monotone but 0.04 apart (Sharpe SE 0.50, T6f).
- T3f universe: 9 -> 1.12; BTC 0.85; BTC+ETH 0.95; top-5 1.27 (post hoc). `av_runs/av_universe_9.txt`: 7 = 9 minus DOGE, BNB -> daily 1.02,
  weekly 0.91; 24 ex-ante perps 0.86 / 0.82.
- T3g gross cap 1.0 vs 2.0: identical, max gross 0.56x (TV 0.25) / 0.88x (TV 0.40). The cap never binds.
- T3j regime filters (weekly): BTC<200d 1.18 (-14.4%); BTC 30d vol >70% 1.02; >90% 1.00. `d3_runs/d3_regime_filter_output.txt` (daily TV 0.40):
  none 1.25; BTC filter 1.25 (DD -25.9%); vol >0.90 1.09; vol >0.70 1.18 (2021 +47% -> +18%/+27%).
- `calc/d2_checks2_output.txt` drawdown de-lever mult=clip(1-dd/dd_max,0.25,1), TV 0.25: none 1.25; dd_max 0.1/0.15/0.2/0.3 -> 1.13/1.18/1.21/1.23,
  CAGR 15.0 -> 9.2/10.8/11.9/13.0%.
- T5 whole contracts, Delta 2024-08-10..2026-10-12: repo daily TV 0.40 unrounded 0.99; $500/1,000/2,500/5,000 -> 1.09/0.93/0.97/1.00.
  Design weekly TV 0.25 band 10%: unrounded 0.70 (gross 0.12x); $500 0.72 (gross 0.09x), $1,000 0.81 (0.11x), $2,500 0.70, $5,000 0.69.
  Rounding is +-0.08 noise and non-monotone in capital.
- T6a: vol-scaled always-long basket weekly TV 0.25: Sharpe 0.99, vol 23.0%, DD -36.6%; design 1.12, vol 12.4%, DD -16.9%.
  `av_sub.txt`: rule minus vol-matched basket Sharpe 0.18 full, 0.11 (2022-26), 0.27 (2024-26).
- T6f: design Sharpe SE 0.50; 2022-26 CI [-0.28, 1.58]; 2025-26 0.26 CI [-1.06, 1.36]. `av_dsr.txt`: at 100 trials with sd 0.25 the deflated-Sharpe
  P(true SR > 0) falls from 99.8% to 89%: every extra cell costs.
- 2026-10-08 memo `--grid`: lookbacks x TV 25/40/60 (18 settings), all positive, Sharpe 0.99-1.25 Binance, 0.48-1.02 Delta; TV does not change Sharpe.
  Rounding table: $280 1.11, $1,000 1.08, $2,300 1.15, $5,000 1.15.
- Fees are 0.25%/yr on the weekly book and 1.1%/yr on the daily book (T1/T3m). A 15% cut in turnover is therefore worth <= 0.04%/yr (weekly) and
  ~0.17%/yr (daily), i.e. <= 0.01-0.02 of Sharpe. The sizing family's turnover channel is OPERATIONAL (fewer hand orders, fewer 1-contract flips),
  not P&L. Its P&L channel is DD / worst-7-day at equal Sharpe.

Scratchpad phase2 engine (`scratchpad/tools2/{rules,variants,evaluate,sim}.py`, outputs `scratchpad/research2/phase2/*.json`, run 2026-10-20),
three panels: A = 9 coins Binance 2020-05..2026-09, B = 24 ex-ante perps, C = Delta 9 coins 2024-08-10..2026-10-12; daily TV 0.40 and weekly
Monday TV 0.25 band 10%; boot = paired 20-day block bootstrap of Sharpe(variant) - Sharpe(baseline), [mean, lo, hi, P(diff<=0)].
Baseline reproduces the repo: A-daily 1.250 / A-weekly 1.121 / B-daily 0.851 / B-weekly 0.810 / C-daily 0.994 / C-weekly 0.704.

| variant | A-daily | A-weekly | B-daily | B-weekly | C-daily | C-weekly | turnover (A-daily, A-weekly) | maxDD A-daily, A-weekly |
|---|---|---|---|---|---|---|---|---|
| baseline | 1.250 | 1.121 | 0.851 | 0.810 | 0.994 | 0.704 | 15.65x, 3.43x | -21.9%, -16.9% |
| vol_ewma32 (EWMA span 32 of r^2, else unchanged) | 1.204 | 1.121 | 0.854 | 0.820 | 0.830 | 0.573 | 17.07x (+9%), 3.69x (+8%) | -21.2%, -15.8% |
| portfolio_vol (w x TV_port/sqrt(w'S60 w), TV_port = 0.5 TV, NO clip) | 1.174 | 1.032 | 0.997 | 1.006 | 0.562 | 0.554 | 36.35x (+132%), 6.59x (+92%) | -30.6%, -20.0% |

vol_ewma32 bootstrap P(diff<=0): A-daily 0.78, A-weekly 0.47, B 0.45/0.41, C 0.91/0.86. portfolio_vol: A 0.64/0.68, B 0.29/0.23, C 0.84/0.68.
`rules.py` already contains `vol_carver_blend`, `corr_factor_bk`, `vol_floor_percentile`, `strategy_vol_multiplier`, `vol_parkinson/garman_klass/yang_zhang`;
`variants.py` has `bsc_scaled`. None of those were run (no JSON). `data.py` loads Delta with O = H = L = C, so a range estimator cannot be
tested natively on Delta without a new loader.

Local diagnostics (verified by reading the outputs):
- `research2/notes/diag_sizing_output.txt` (median coin, 9 coins, 2020-07..2026-09): weekly log-change sd of the estimate / RMSE7 / RMSE30 / level vs CC60:
  CC60 0.113/0.563/0.425/1.000; CC30 0.192/0.539/0.424/0.972; EWMA35 0.177/0.531/0.407/0.973; EWMA60 0.119/0.539/0.393/1.015;
  EWMA121 (COM 60) 0.067/0.553/0.384/1.041; PARK30 0.175/0.578/0.440/1.081; GK30 0.178/0.597/0.456/1.096.
- `diag_sizing2_output.txt`: blend 0.7 EWMA35 + 0.3 LR365: noise 0.114, RMSE7 0.524, RMSE30 0.373, bias30 +0.081; max(CC60,0.40): noise 0.101, binds 3%
  pooled (BTC 29%, BNB 20%); max(CC60, 0.7 LR365): noise 0.089, RMSE30 0.401, binds 16%. 9-coin rho_bar p5/p50/p95 0.48/0.72/0.85 -> CF 1.37/1.15/1.07.
- `research2/sizing_diag_out.txt` (pooled, QLIKE, bias = median realized/forecast, turnover per rebalance): 7-day horizon CC60 QLIKE 0.656 bias 0.82 turn/wk 0.071;
  EWMA60 0.587/0.81/0.079; EWMA35 0.624/0.84/0.124; CC30 0.704/0.86/0.129; PK60 0.606/0.73/0.061; GK60 0.611/0.71/0.060; BLEND 0.552/0.81/0.083.
  Section 3: 60d avg pairwise correlation quintile -> next-7d EW basket Sharpe: Q1 (rho 0.51) 1.44, Q2 0.45, Q3 -0.88, Q4 -0.63, Q5 (0.82) 0.82 (non-monotone).
  Section 4: relative-vol (CC30 / own 365d median) quintile -> next-7d scaled-SR: 0.38 / 0.17 / 0.35 / 0.63 / 0.12 (non-monotone; the lowest-vol
  quintile is NOT followed by crashes; the highest has ~0 return). Asymmetry: corr(today's return, change in fwd vol) = -0.013; after a >+3% day the
  7d vol change is -0.141, after a <-3% day -0.143: NO leverage effect in either direction in this data.
  Section 5/6: always-long basket realizes 0.92x nominal TV; ex-ante portfolio scaler k = TV / ex-ante vol: mean 1.20, p10 1.09, p90 1.38, max 1.61.
- `research2/sim/binance_out.txt` lines 10-11, 19-20 and `delta_out2.txt` lines 10-11, 19-20 (SZ-15): Binance daily 1.25 -> 1.08 (SR_a 0.5) / 1.20 (1.0),
  weekly 1.12 -> 1.06 / 1.11; Delta daily 0.99 -> 0.54 / 0.84, weekly 0.70 -> 0.18 / 0.55. `funding_bucket_diag.txt`: next-day gross return with the
  signal on is highest at trailing funding 12-30%/yr (+62..+129 bps/day, t 3.0-4.5) on Delta and on both Binance windows.
- Delta notionals today (`research2/tickers.json`): BTC $82.76, BNB $74.12, ETH $24.47, LINK $12.35, DOGE $8.17, LTC $6.19, BCH $2.85, XRP $1.33, ADA $0.22.
- Paper daily book journal (`scratchpad/daily-book/journal.jsonl`, 2026-10-07..10-17, 11 rebalances, $1,000, TV 0.40): 0<->1-contract flips are
  12% of traded dollars (23% excluding the initial build), all BTC and BNB. The candidates' "~40%" is overstated; the direction holds.

## 1. Verdicts

### SZ-1 EWMA vol, centre of mass 60 d (MOP spec) -- KEEP (single cell)
- Prior test: none of this estimator. Nearest: T3e flat 30/60/90 (1.16/1.12/1.08) and phase2 vol_ewma32 (a different, 4x shorter memory: null on A/B,
  -0.13..-0.16 on C, turnover +8-11%).
- Mechanism check (my own): alpha = 1/61 vs the flat window's 1/60, so the day-1 reaction to a spike is identical; the difference is that the spike decays
  geometrically (half-life 42 d) instead of being carried at full weight for 60 days and then dropped, which is exactly the "echo" that makes CC60 noisy.
  So the DD tail should be unchanged and the vol-driven turnover should fall (local: weekly noise 0.067 vs 0.113, -40%).
- Refutation attempt: (1) COM 60 = mean lag 60 d, twice CC60's mean lag of 30 d; T3e says longer memory scores lower (CC90 1.08), so expect a Sharpe
  of ~1.05-1.12, not a gain. (2) Level +4% -> compare at equal realized vol. (3) The fee saving is <= 0.04%/yr on the weekly book: the value is
  fewer hand orders and fewer 1-contract flips, not P&L. (4) No paper reports a Sharpe gain for EWMA over a flat window; MOP/AQR/Harvey use it as the
  default and Harvey says "similar results" [UNVERIFIED]. Evidence for the estimator choice is therefore replicated as a convention, not as an effect.
- Keep because it is one parameter, the cheapest change in the family, and the operational payoff is real for the hand book. Drop V2 (span 60, COM 30):
  noise 0.119 = CC60, no thesis; the short-memory direction is already covered by vol_ewma32.
- Refined: s_t = (60/61) s_{t-1} + (1/61) r_t^2 (uncentered, like the repo), seeded with the first 60 squared returns; vol = sqrt(365 s_t);
  w_i = sig_i (TV/N)/max(vol_i, 0.05); cap 2x. Report A/B/C, both books, at equal realized vol. Accept iff Sharpe within 0.03 of baseline on all
  three panels AND orders/yr down >= 15% AND worst-7-day no worse. One trial.
- Evidence quality: replicated_multi_asset (as a spec, not as a measured gain). Cost: trivial (rules.ewma exists).

### SZ-2 Shorter memory: CC30 or EWMA span 35 -- DROP
- Prior test: T3e CC30 (+0.04 in-sample on the weekly 9-coin line, inside the 0.50 SE; trades/yr +9%; not run on B or C); phase2 vol_ewma32 (span 32,
  materially the same as span 35): A-daily 1.25 -> 1.20, A-weekly 1.12 -> 1.12, B 0.85 -> 0.85 / 0.81 -> 0.82, C 0.99 -> 0.83 / 0.70 -> 0.57,
  turnover +8-11%, bootstrap P(diff<=0) 0.41-0.91.
- The EWMA form the candidate prefers has been run and is null on A/B and negative on Delta; both forms raise turnover, the opposite of the family's goal.
  The two local accuracy diagnostics disagree on CC30 vs CC60 (RMSE-of-log says CC30 slightly better at 7 d, pooled QLIKE says worse at both horizons);
  they agree on +70% noise. The "1-month is the literature standard" claim concerns vol targeting versus none, not window choice.
- Evidence quality: single_study (T3e, in-sample 9 coins). Cost: trivial. Refined: none; the memory axis is covered by SZ-1 (COM 60) vs vol_ewma32 (COM 16).

### SZ-3 Carver mixed vol (0.7 EWMA35 + 0.3 long-run) -- REFINE to one cell
- Prior test: phase2 vol_ewma32 = the fast leg alone (null/negative, turnover up). The slow anchor is what brings the noise back to CC60's level
  (0.114) while keeping the best 30-day forecast (RMSE30 0.373 vs 0.425); that is a material difference, so not covered.
- Refutation: Harvey et al. 2018 is cited as support, but its numbers (0.40 -> 0.48-0.51, vol-of-vol 4.6 -> 1.8%) compare vol targeting with no targeting
  and rest on the equity leverage effect, which is absent here (local asymmetry = 0). It says nothing about estimator choice. The remaining support is
  pysystemtrade defaults with no published P&L. The candidate as merged has 4-5 free choices (span 32/35/HL20, slow definition x4, blend in vol or
  variance, GARCH weights, quantile floor, YZ) = at least 8 cells; each is a trial against a 0.50 Sharpe SE. The YZ sub-variant is refuted locally
  (see SZ-16). The quantile floor adds a parameter the blend already handles softly.
- Refined (exactly one cell, run as the third arm of the estimator comparison next to CC60 and SZ-1): sigma_fast = EWMA (span 35, min 10 obs) std of
  daily log returns; sigma_slow = trailing 365-day simple mean of sigma_fast (needs >= 120 obs, else sigma_slow = sigma_fast); vol = sqrt(365) x
  (0.7 sigma_fast + 0.3 sigma_slow) in vol units; keep the 0.05 floor; no quantile floor, no YZ, no GARCH weights. Compare at equal realized vol
  (+8% level bias). Accept iff trades/yr <= baseline, Sharpe within 0.03 on A/B/C, worst-7-day no worse.
- Evidence quality: vendor_or_blog (practitioner code, no P&L). Cost: trivial (rules.vol_carver_blend exists).

### SZ-4 Fractional-Kelly rule for TV and the cap -- DROP (not a testable rule)
- Prior test: T3a (Sharpe 1.12-1.13 flat over TV 0.15-0.40; DD and worst day linear) and the memo `--grid` (TV 25/40/60 -> same Sharpe); T3g (cap never binds).
- It is Sharpe-neutral by construction, so there is nothing to backtest; its only content is "run the daily book at TV 0.25-0.30", which T3a already prices
  (DD -16.9% at 0.25, -20.2% at 0.30) and which the memo leaves to the user ("Before going live, the user decides the target vol"). The arithmetic is
  correct and worth one memo line: realized 12.4% at TV 0.25 = quarter-Kelly at SR 0.5; realized 18.7% at TV 0.40 = 0.37-Kelly at SR 0.5 and
  0.72-Kelly at SR 0.26 (2025-26). Re-deriving SR_hat yearly would be a performance-chasing knob the resource doc forbids ("never raise TV after a good month").
- Evidence quality: vendor_or_blog (standard formula; Carver/Chan posts). Cost: trivial. Refined: none; one sentence in the memo.

### SZ-5 Vol floor (absolute 0.40 / relative 0.7 x 1-y mean) -- DROP
- Prior test: none exact. Closest: d2_checks2 (de-levering: cuts Sharpe), T3j (vol filters cut Sharpe).
- Refutation: Cui et al.'s mechanism is "low vol precedes crashes, so 1/sigma over-levers into them". Locally the lowest relative-vol quintile has next-7d
  scaled-SR 0.38 (Q3 0.35, Q4 0.63): no such pattern in the pooled 9-coin data. The absolute floor binds BTC 29% / BNB 20% of days and nowhere else,
  i.e. it only shrinks the two coins that already round to zero at $1,000. The relative floor is SZ-3's mechanism (anchor to a long-run level) in a
  harder form with worse forecast stats (RMSE30 0.401 vs 0.373) and the same noise class (0.089 vs 0.114). Single US-equity study [UNVERIFIED].
- Evidence quality: single_study. Cost: trivial. Refined: none; if SZ-3 passes, max(blend, 0.7 LR365) may be added later as a sensitivity, not now.

### SZ-6 Baltas-Kosowski correlation factor / Carver IDM -- REFINE to variant (b) only (the family's one correlation cell)
- Prior test: phase2 portfolio_vol is the full-covariance cousin (unclipped, TV_port = 0.5 TV): A-daily 1.25 -> 1.17 with maxDD -21.9 -> -30.6% and
  turnover x2.3; A-weekly 1.12 -> 1.03, DD -16.9 -> -20.0%; C 0.99 -> 0.56 / 0.70 -> 0.55; B 0.85 -> 1.00 / 0.81 -> 1.01. CF differs materially:
  it is bounded (1.07-1.37 on the local rho range), uses only the average correlation and N_t, and does not blow up when few coins are long.
- Refutation: B&K's full-sample gain is +0.01 (1.04 -> 1.05) [UNVERIFIED, second-hand]; the post-2008 story needs correlations that rise from ~0.3 to ~0.6,
  while crypto's never leave 0.48-0.85. Variants (a) and (c) are leverage levels (+15% mean gross = +0.3%/yr funding), Sharpe-neutral by T3a. Only the time
  variation (b) can carry Sharpe, and the local correlation-quintile diagnostic is non-monotone (1.44/0.45/-0.88/-0.63/0.82). Yearly medians (0.64-0.65 in
  the good years 2023-24, 0.73-0.78 in 2022 and 2025-26) are seven observations. Expected result: null.
- Refined (one cell): rho_bar_t = mean pairwise 60-day Pearson correlation of daily log returns among coins with sig_i > 0 (all nine if fewer than three),
  each pair floored at 0; N_t = that count; CF_t = sqrt(N_t/(1+(N_t-1) rho_bar_t)); CF_ref,t = sqrt(N_t/(1+(N_t-1) x 0.70)) with the same N_t; m_t =
  EWMA_span20(CF_t/CF_ref,t); w_i <- w_i m_t; TV and cap unchanged. Judge at equal realized vol. Accept iff Sharpe +0.05 on all of A/B/C; otherwise
  close the question. SZ-7 is folded into this cell.
- Evidence quality: single_study. Cost: trivial (rules.corr_factor_bk exists; add the reference and smoothing).

### SZ-7 Ex-ante portfolio covariance vol targeting -- DROP
- Prior test: phase2 portfolio_vol IS this rule without the clip (numbers under SZ-6). It failed on the design universe and on Delta in the two ways the
  candidate itself predicted (DD +9 pp, turnover x2.3, concentration when few coins are long) and helped only on the 24-perp panel, where the
  diversification is real and the Delta book does not have it.
- The clip does not rescue it: ex-ante book vol has p10 1.5%, p50 12.2% against a TV_port of ~0.12-0.20, so m is >= 1.5 on most thin-signal days and
  1.0-1.26 otherwise; the clipped rule is "x1.5 on the lowest-conviction days", the observed failure mode. SZ-6 (b) is the bounded, mechanism-faithful
  form of the same idea and gets the family's single correlation trial.
- Evidence quality: single_study (B&K second-hand; macro-backtester README has no before/after). Cost: trivial. Refined: none.

### SZ-8 Second-layer book vol targeting on own P&L (Barroso-Santa-Clara) -- DROP
- Prior test: none exact; the two legs map onto tested families. Leg 1 (m -> 0.5 after a vol spike while long) is the realized-vol filter family:
  T3j 1.02/1.00, d3_regime 1.18/1.09, all by cutting 2021. Leg 2 (m -> 1.5 when the book's own vol has been low) levers up thin, low-conviction books,
  which is what phase2 portfolio_vol did (C-daily 0.99 -> 0.56). d2_checks2 shows the de-lever direction costs Sharpe at every setting.
- Mechanism: a long/flat, per-asset vol-targeted book's own realized vol measures participation (flat 16% of days; 21-day RV p10 0.6% .. 57%), not
  market risk; a 60-day window softens but does not change that. Crypto evidence is cross-sectional long/short (Yang 2025) where the short leg crashes;
  Howden-Andreev report vol targeting / Kelly on a crypto TSMOM sleeve as a null; Cederburg et al. find real-time vol management fails except for momentum
  (and that result is the short-leg crash hedge). All [UNVERIFIED].
- Evidence quality: single_study. Cost: trivial (variants.bsc_scaled exists), but a trial against a 0.50 SE with an inapplicable mechanism. Refined: none.

### SZ-9 Moreira-Muir c/RV literal -- DROP (concur)
- Prior test: none; listed to prevent testing. Local: 21-day RV spans 0.6%..57% so c/RV swings ~2,500x; clipping to [0.5,2] leaves SZ-8's two legs.
  Real-time failure in Cederburg 2020 / DeMiguel 2024 [UNVERIFIED]; the one robust equity win is the momentum short-leg crash hedge.
- Evidence quality: replicated_multi_asset for the equity-factor in-sample result, but with documented out-of-sample failure. Cost: trivial. Refined: none.

### SZ-10 Downside semi-deviation scaler -- DROP
- Prior test: none. Mechanism check: the candidate rests on the inverted leverage effect (Baur-Dimpfl). Locally corr(today's return, change in forward
  7-day vol) = -0.013, and the vol change after a >+3% day (-0.141) equals that after a <-3% day (-0.143): no asymmetry in either direction in the
  pooled 9-coin daily data, so total-vol scaling does not systematically cut longs after rallies here. Semi-deviation uses about half the observations
  (sqrt(2) noisier) -> more turnover, against the family's goal. Wang-Yan is US equity factors; no crypto or TSMOM evidence [UNVERIFIED].
- Evidence quality: single_study. Cost: trivial. Refined: none.

### SZ-11 Conditional vol targeting (extreme-quantile switching) -- DROP
- Prior test: T3j / d3_regime (the high-vol leg: binary BTC-vol filters cut Sharpe by skipping 2021). The candidate already concedes it should only be
  tested after SZ-1/SZ-3 and rejected if the gain comes from 2021-05 and 2022-11. Four parameters (span 250, span 35, 730-day quantile window, 0.2/0.8
  thresholds). The one local support, Q5 relative vol -> next-7d SR 0.00, is exactly what T3j monetised and lost on. Ten equity markets, one study
  [UNVERIFIED]; the turnover halving it advertises is what SZ-1 delivers with one parameter.
- Evidence quality: single_study. Cost: small (quantile machinery). Refined: none.

### SZ-12 Carver vol attenuation multiplier -- DROP
- Prior test: T3j (weekly 1.12 -> 1.02/1.00) and d3_regime_filter (daily 1.25 -> 1.18/1.09) for the binary absolute-vol version. The continuous relative
  version is new in form only. Local relative-vol quintiles -> next-7d scaled-SR 0.38/0.17/0.35/0.63/0.12: the multiplier 2-1.5Q would double exposure in
  Q1 (0.38), cut Q4 (0.63, the best quintile) to ~0.7x and halve Q5 (0.12); net ambiguous-to-negative. Support is a 3-year futures QuantConnect sample and
  Carver's "small gain" [UNVERIFIED vendor/blog].
- Evidence quality: vendor_or_blog. Cost: trivial. Refined: none.

### SZ-13 Minimum-contract rule with risk re-allocation -- REFINE (threshold corrected)
- Prior test: T5 (rounding without re-allocation: +-0.08 noise, non-monotone; $500 gross 0.09x vs 0.12x); av_universe_9 and T3f (universe subsets cost
  0.1-0.3 Sharpe, so dropping coins is not free); no re-allocation variant anywhere.
- Refutation of the spec: with today's notionals (BTC $82.76, BNB $74.12, ETH $24.47) and median 60-day vols (0.54/0.56/0.71), at $1,000 and TV 0.25 the
  full-signal position is BTC 0.62, BNB 0.67, ETH 1.60 contracts: the "full_i >= 2" threshold removes ETH as well (N_eff = 6), not the N_eff = 7 the
  candidate states (it assumed 50% vol). At TV 0.40 BTC is 0.99 contracts, so a threshold of 1 re-evaluated daily would churn BTC in and out with its vol.
  The "~40% of traded dollars are 0<->1 flips" figure is overstated: the journal shows 12% (23% excluding the initial build), all BTC/BNB, over 10 days.
  Each such flip costs ~$0.12; the case is operational (orders with no signal content) and the restoration of the risk budget at $500-1,000, not P&L.
- Refined: full_i = (TV/N)/max(vol_i,0.05) x E/(cv_i P_i); eligible iff full_i >= 1.0 contract, re-evaluated on the first decision day of each month
  with hysteresis (enter at >= 1.0, leave at < 0.8); N_eff = number eligible; w_i = sig_i (TV/N_eff)/max(vol_i,0.05) for eligible coins, 0 otherwise;
  report threshold 2 as the only sensitivity; drop threshold 4 and Variant B. Run on the whole-contract engine (T5b / trend_backtest --capital) at
  $500/$1,000/$2,500/$5,000 on C and on A with Delta contract values. Accept iff at $1,000 realized vol is within 10% of the unrounded line, Sharpe within
  0.05 of it on A and C, and orders/yr fall. No-op at $5,000 by construction, so it does not change the strategy's design.
- Evidence quality: vendor_or_blog (Carver heuristic, no P&L). Cost: small (equity-dependent eligibility in the whole-contract loop).

### SZ-14 Greedy minimum-tracking-error contract optimiser -- DROP
- Prior test: T5 and the memo rounding table bound the whole prize: rounding costs < 1.5%/yr and +-0.08 Sharpe, non-monotone ($500 beat $5,000 on the
  repo run; $1,000 beat unrounded on the design line). There is no measurable target to recover. The optimiser substitutes correlated coins for the
  ones that round to zero (ETH for BTC), which changes composition rather than fixing rounding; Carver's first integer version failed and the greedy
  version's gain is unquantified [UNVERIFIED blog]. SZ-13 addresses the same small-account problem in eight lines.
- Evidence quality: vendor_or_blog. Cost: small (greedy TE loop with covariance, ~60 lines). Refined: none.

### SZ-15 Proportional funding-cost-adjusted forecast -- DROP (concur, tested negative)
- Prior test: `research2/sim/binance_out.txt` lines 10-11, 19-20 and `delta_out2.txt` lines 10-11, 19-20 (both verified): Binance daily 1.25 -> 1.08 / 1.20,
  weekly 1.12 -> 1.06 / 1.11; Delta daily 0.99 -> 0.54 / 0.84, weekly 0.70 -> 0.18 / 0.55; CAGR roughly halves. `funding_bucket_diag.txt`: with the signal on,
  next-day gross return is highest at trailing funding 12-30%/yr (+62..+129 bps/day, t 3.0-4.5) on Delta and both Binance windows, so a proportional
  penalty trims the best positions; same failure as the rejected funding-as-signal row in resource/07.
- Evidence quality: single_study (local, in-sample, but negative on both samples and both books). Cost: trivial. Refined: none.

### SZ-16 Range-based OHLC estimator (Parkinson / GK / YZ) -- DROP
- Prior test: none in the repo; two local diagnostics. PARK30/GK30 run 8-10% above CC60 in level, their weekly noise (0.175/0.178) is far above CC60's 0.113
  (only 9% below CC30), and they forecast future close-to-close vol worse (RMSE7 0.578/0.597 vs 0.563; RMSE30 0.440/0.456 vs 0.425). PK60/GK60 (pooled QLIKE)
  are better than CC60 at both horizons but with bias 0.73/0.71 (forecast 37-41% above realized) and only -14% turnover vs CC60, less than EWMA-COM60's -40%.
  B&K's YZ result is turnover only (-17%, no performance change) [UNVERIFIED]. Delta candles are index-marked and `data.py` loads Delta with O = H = L = C,
  so the rule cannot be tested on the venue's own data without a new loader. SZ-1 dominates on the turnover channel with no level bias.
- Evidence quality: single_study. Cost: trivial on Binance (OHLC cached; rules.py has the estimators), large for a Delta-native test. Refined: none.

## 2. What survives, and the trial budget
Four cells: SZ-1 (EWMA COM 60), SZ-3 (one blend cell) as the estimator comparison against CC60; SZ-6 (b) as the single correlation cell; SZ-13 (threshold 1,
monthly eligibility) for the small-account books. Twelve dropped. The expected P&L effect of all four is within +-0.03 Sharpe; the measurable goals are
orders/yr, 1-contract flips and worst-7-day at equal Sharpe and equal realized vol, on all three panels (A, B, C) and both books.

## 3. Verification status
VERIFIED by reading: resource/07 rejected table; backtest_results.md T0-T7; d3_runs/*.txt; av_runs/*.txt; calc/d2_checks2_output.txt; 2026-10-08 memo;
trend_backtest.py::target_weights; phase2/*.json with tools2/{rules,variants,evaluate,data,check_baseline}.py; research2 diag outputs and sim outputs;
tickers.json notionals; daily-book/journal.jsonl. UNVERIFIED (snippets only, as tagged by the candidates): every MOP / Harvey / B&K / Carver-blog /
Cui / Bongaerts / Wang-Yan / Barroso / Yang / Grobys / Howden / Cederburg / QuantConnect number. No external fetch was attempted in this pass.
