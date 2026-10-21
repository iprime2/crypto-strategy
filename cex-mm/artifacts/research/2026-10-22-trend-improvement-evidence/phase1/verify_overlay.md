# Adversarial verification: OVERLAY family (OVL-1 .. OVL-7), 2026-10-21

Role: refute. Verdict = keep / refine / drop. Read-only on the repo; no orders; nothing in the repo edited.
Tags: [VERIFIED] = file opened or computed here; [LOCAL] = computed in this pass on the Binance daily cache
(`scratchpad/trend-cache`, 9 coins, 2020-05-01..2026-09-30, 2,344 days) with `verify_tools/ovl_states.py` and
`verify_tools/ovl1_thresholds.py` (outputs `ovl_states_out.txt`, `ovl1_thresholds_out.txt`); [SECONDARY] = a third
party's notes on a paper; [UNVERIFIED] = search snippet or abstract only. The diagnostics report STATE FREQUENCIES,
OVERLAPS and the baseline's GROSS HELD in each state only; no returns-by-state were computed, so Phase 2 stays blind.

## 0. The prior-test ledger (what the repo and this round already tested; verified by reading)

- `resource/07-trend-rule-and-prop-trading-research.md` "What was considered and rejected": BTC-200-day or realized-vol
  regime filters ("on the daily rule the 200-day filter leaves Sharpe at 1.25 with a worse drawdown (-25.9%); vol filters
  cut Sharpe to 1.00-1.18 by skipping 2021"); drawdown de-leveraging on own capital ("Sharpe 1.13-1.23 vs 1.25 ... at
  every dd_max; the rule already vol-targets"); intraday day-stop (-0.07..-0.13 Sharpe); shorts (0.78 vs 1.25; "the short
  leg is where crypto momentum crashes"); funding as a directional signal (R^2 ~12.5% at 7 d, BTC funding pinned at the
  0.01% floor 78% of Q3 2025); cross-sectional alt momentum (negative OOS 2025-26); single lookback (20: 0.90; 60: 0.92).
- `backtest_results.md` T3j (weekly Mon TV 0.25 band 10): none 1.12 (-16.9%) / BTC < 200-day -> flat 1.18 (-14.4%; 2022 +0.1%,
  2021 +30.5%) / BTC 30-day vol > 70% 1.02 / > 90% 1.00. "Not adopted." T3a: TV 0.15..0.40 -> Sharpe 1.12..1.13, DD and
  worst day linear in TV (a gross cut is Sharpe-neutral). T3d: (20,) 0.90 (-22.2%), (10,30,60) 1.08, (120,) 1.21.
  T3h kill: -15% weekly fires once (2022-11-14), -20% never at TV 0.25. T3i day stops 1.05/1.02/0.99. T6f: design Sharpe SE
  0.50; 2022-26 CI [-0.28, 1.58]. T6g: a -20% kill fires on 11-18% of two-year paths at Sharpe 0.5-0.7 (path luck).
- `d3_runs/d3_regime_filter_output.txt` (daily TV 0.40): none 1.25 (-21.9%; 2021 +47%) / --btc-filter 1.25 (-25.9%; 2021 +37%,
  2022 +0%, 2023 +12%) / --vol-filter 0.90 1.09 (2021 +18%) / 0.70 1.18 (2021 +27%). Implementation in
  `tools/qd_engine.py` (btc_filter: all weights 0 when BTC close < 200-day mean) and `tools/trend_hourly.py`.
- `calc/d2_checks2_output.txt` (b): mult = clip(1 - dd/dd_max, 0.25, 1) at TV 0.25: none 1.25; dd_max 0.1/0.15/0.2/0.3 ->
  1.13/1.18/1.21/1.23; CAGR 15.0 -> 9.2/10.8/11.9/13.0%.
- `av_runs/av_sub.txt`: rule minus vol-matched always-long basket Sharpe 0.18 full, 0.11 (2022-26), 0.27 (2024-26); the
  signal's whole contribution is drawdown shape (-16.9% vs -36.6%). `av_runs/av_universe_9.txt`: 24 ex-ante perps daily
  0.86 / weekly 0.82; 25 incl. DOGE 0.92 / 0.87. `local_evidence.md`: worst days 2021-05-19 -7.3%, 2020-11-26 -5.9%,
  2020-09-03 -5.3%, 2025-10-10 -5.0%, 2024-12-09 -5.0%, 2024-03-19 -4.9%: all crashes while long after a run-up.
- 2026-10-08 memo `--grid`: 18 settings (lookbacks x TV), all positive; TV does not change Sharpe.
- This round, `sim/funding_grid.txt` + `notes/costs_funding.md` 2.2 [VERIFIED]: skip-coin-while-trailing-funding > X, W in
  {7,14,30,60} d x {15..50}%: daily full-sample 7d>15% 0.87, 7d>20% 1.05, 7d>30% 1.20, 7d>50% 1.29, 14d>30% 1.29, 14d>40%
  1.41, 14d>50% 1.30, 30d>20% 1.32, 30d>30% 1.37, 30d>40% 1.22, 30d>50% 1.14, 60d>30/40/50% 1.15/1.16/1.16 vs 1.25
  (7 of 14 cells below baseline). SZ-15 proportional Carver form harmful (1.25 -> 1.08/1.20; Delta 0.99 -> 0.54/0.84).
  Bucket diagnostic `sim/funding_bucket_diag.txt`: next-day gross return with signal on, by trailing-7d funding: Binance
  2020-26 >50%/yr bucket n=1172 +61.9 bps (t 2.49), funding paid 22.3 bps/day, net +39.5; 30-50% n=881 +67.5 (t 2.68);
  Binance 2022-26 >50% n=105 +22.1 (t 0.36) net +7.9; Delta 2024-26 >50% n=48 -8.2 (t -0.09) net -19.2; 12-30% buckets
  +51 to +129 bps (t 2.6-4.5) on all samples.
- `verify_sizing.md` SZ-6 -> refined to ONE correlation cell (b): m_t = EWMA_20(CF_t / CF_ref,t) on the signed coins,
  judged at equal realized vol; local quintile diagnostic (`sizing_diag_out.txt` s.3): next-7d EW basket Sharpe by 60d
  avg-correlation quintile Q1 (rho 0.51) 1.44, Q2 0.45, Q3 -0.88, Q4 -0.63, Q5 (0.82) 0.82 (non-monotone).
- `verify_signal.md` SIG-9 -> refine: free diagnostic first (next-7-day return by Bull/Correction/Bear/Rebound state,
  SLOW = sign(P/P-120), FAST = sign(P/P-20), on 9 and 24 coins, 2020-26 and 2022-26), then one conditional blend line.
- `verify_universe.md` UNI-7 (funding eligibility gate) -> drop; "if a record is wanted, OVL-2's two tail cells on the
  ex-ante universe close it."
- `scratchpad/tools2/cache_binance_25c_*.npz` [VERIFIED]: the 25-coin Binance panel carries funding for every coin
  (BTC/ETH/BCH 2,465 funding days, BNB 1,672, DOGE 2,274, the 16 extras 2,405-2,458), so a funding overlay on the ex-ante
  universe needs no new data.

## 1. New diagnostics this pass [LOCAL] (`verify_tools/ovl_states_out.txt`, `ovl1_thresholds_out.txt`)

Baseline mean gross 0.198x. BTC < 200-day state (the T3j filter) is on 40.3% of days (2022 100%, 2026 84%, 2021 29%,
2023 19%, 2024 20%, 2025 27%); gross held in that state 0.048x vs 0.299x outside.

| state | on % days | gross held in / out | binds (state & gross > 0.05x) | P(btc200 \| state) / P(state \| btc200) / Jaccard | by year |
|---|---|---|---|---|---|
| OVL-1 EW index < 0.85 x trailing-365d peak | 73.0% | 0.128x / 0.387x | 41.8% | 55% / 100% / 0.55 | 2020 55%, 2021 67%, 2022 100%, 2023 63%, 2024 57%, 2025 70%, 2026 100% |
| OVL-1 threshold 10% / 20% | 79.0% / 65.8% | 0.141 / 0.413x; 0.118 / 0.351x | 47.8% / 34.9% | 51% / 100%; 60% / 99% | 2022 and 2026 100% at every threshold |
| OVL-1 all-time peak, 15% | 84.2% | 0.163x / 0.382x | 53.0% | 48% / 100% / 0.48 | 2023 100%, 2024 92% |
| OVL-4 bear24 AND hivol | 0.8% | 0.007x / 0.199x | 0.0% | 100% / 2% | 2022 1%, 2026 5%, else 0 |
| OVL-4 bear24 only (BTC 730-d return < 0) | 20.4% (27.6% on diag.py's denominator) | 0.239x / 0.187x | 14.8% | 37% / 19% | 2023 100%, 2022 13%, 2026 22% |
| OVL-6 basket 3-lookback signal <= 0 | 45.4% | 0.044x / 0.326x | 15.0% | 74% / 83% / 0.64 | 2022 82%, 2026 75%, 2025 56%, 2024 38% |
| OVL-7 BTC leads alts over 90 d | 67.5% | alt gross 0.140x / 0.205x | 42.4% | 43% / 72% / 0.37 | 2023 79%, 2024 83%, 2026 90% |

OVL-1 by threshold (share of the baseline's gross-days that fall inside the state; x0.5 therefore cuts mean gross by half
that share): 10% -> 56.1% (cut 28%); 15% -> 47.1% (cut 23.5%); 20% -> 39.3% (20%); 30% -> 26.0% (13%; state on 48.5% of
days, 75% of them BTC<200d days); 40% -> 19.0% (9.5%; 34.9% of days, 83% inside BTC<200d; 2024 0%); 50% -> 10.3% (5%;
26.2% of days, 91% inside BTC<200d); 60% -> 3.9% (13.9% of days, 100% inside BTC<200d). The EW index's drawdown from its
trailing one-year peak has median -29% (p10 -64%, p90 -4%). OVL-1 15% episodes: 2020-05-01..07-07, 2020-09..10,
2021-05-19..11-07, 2021-11-15..2023-05-16 (548 d), 2023-08..10, 2024-04..05, 2024-06-07..11-08 (155 d, the run-up to the
Q4-2024 rally), 2025-02-01..07-16, 2025-10-28..2026-09-30 (338 d). OVL-6 long episodes: 2021-12-04..2022-03-21,
2022-04-08..08-09, 2024-06-17..10-04 (two runs, 109 d), 2025-11-01..2026-04-10, 2026-05-15..08-04.

## 2. External checks this pass

- WebSearch (extended) for the Howden-Andreev preprint: SSRN 7115459, posted 30 Jul 2026, 6 pages, not peer-reviewed.
  Per the search summary of the abstract [UNVERIFIED, SSRN blocked]: BTC ETH BNB XRP ADA SOL DOGE; each asset held while
  its trailing 30-day cumulative log return > 0, else cash; gross halved when the aggregate market is > 15% below its
  trailing peak; net Sharpe 1.41 vs 0.70 buy-and-hold, maxDD -44.6% vs -84.4%, overlay -> about -28%; "walk-forward
  out-of-sample" claimed; framed as risk-managed beta, not alpha; and "layering volatility targeting or Kelly sizing on
  top settled null". The base book is therefore an UNSCALED long/cash rule; the overlay does for it what per-coin vol
  scaling already does for the repo's rule. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7115459
  Also surfaced, not opened: Grobys et al. "Cryptocurrency momentum has (not) its moments" (risk-managing crypto momentum
  reduces crashes but average payoffs stay negative in robustness checks) https://link.springer.com/article/10.1007/s11408-025-00474-9
  [UNVERIFIED]; arXiv 2602.11708 "Systematic Trend-Following with Adaptive Portfolio Construction" (crypto) https://arxiv.org/pdf/2602.11708 [UNVERIFIED, not opened].
- WebSearch for average-pairwise-correlation return prediction in crypto: nothing direct; only descriptive pieces (average
  pairwise correlation ~0.60, stable; arXiv 2412.04263 https://arxiv.org/pdf/2412.04263; cryptoticker blog) [UNVERIFIED].
  No crypto study of correlation as a timing variable was found.
- WebSearch for BTC-dominance / Altcoin-Season-Index backtests: no Sharpe, no out-of-sample test, no performance figure
  anywhere; only index definitions (CoinMarketCap top-100, 90-day, 75% threshold) and current readings (index 57, dominance
  60.1% on 2026-10-20 per TokenPost) [UNVERIFIED]. Confirms the 2026-10-13 review (`alternative_edges.md` KQ7).

## 3. Verdicts

### OVL-1 Market-drawdown crash-state de-risking (Howden-Andreev) -> DROP
- Prior tests: T3j / `d3_regime_filter_output.txt` (BTC < 200-day -> flat: daily 1.25 -> 1.25 with DD -21.9 -> -25.9%; weekly
  1.12 -> 1.18, not adopted), `calc/d2_checks2_output.txt` (drawdown de-lever 1.13-1.23 vs 1.25), T3a (gross cuts are
  Sharpe-neutral). The BTC<200d state is a strict subset of the OVL-1 state (P(state | btc200) = 100% at 10/15/20%).
- Refutation: (1) In crypto a 15% drawdown from the trailing one-year peak is the DEFAULT state, not a crash state: 73% of
  days (median drawdown -29%); 2022 and 2026 100%, 2024 57%, 2021 67%. The whole pre-registered grid (10/15/20%) binds on
  66-79% of days; the all-time-peak variant on 84%. (2) The rule already de-risks there: gross held in state 0.128x vs
  0.387x outside, because the signal is mostly flat and the 60-day vol scaling has already shrunk what is left. (3) x0.5 on
  47% of the baseline's gross-days is a 23.5% cut in mean gross, i.e. a TV reduction (Sharpe-neutral by T3a, CAGR and DD
  down together) plus the 200-day-type timing on the 55% of state days that are also 200-day days, which T3j measured as
  neutral on the daily book with a worse DD. (4) The in-state days that still carry gross (> 0.2x on 17% of all days)
  are the early recoveries (2020-05..07, 2023 H2, 2024-06..11 before the Q4 rally, 2025 H1): exactly where the long/flat
  book earns its year. (5) The paper's base book is unscaled long/cash and its abstract reports vol targeting / Kelly on
  top as null [UNVERIFIED]; the repo's rule already sits at DD -21.9% / Sharpe 1.25 at TV 0.40 against their -44.6% /
  1.41, so the overlay's job is already done by the vol scaling. (6) Deeper thresholds do not rescue it: at 40% the state
  is 35% of days, 83% of them inside the BTC<200d state, 2024 0% -> a weaker copy of the tested filter; at 60% it is 14%
  of days, 100% inside BTC<200d, holding 3.9% of gross-days -> no-op. (7) The paper is a 6-page non-peer-reviewed grid on
  7 coins including SOL (hindsight), abstract only, single crypto sample. The cap-weighted index variant needs a market-cap
  history the repo does not hold (large), and the EW variant is already refuted by state frequency.
- Evidence quality: single_study. Test cost: trivial as written (EW index + trailing max, ~10 lines); cap-weighted variant
  large. Refined rule: none.

### OVL-2 Funding tail cut-out (flat in a coin while trailing 30-day funding > 30%/yr; alt 14 d > 40%) -> REFINE
- Prior tests: resource/07 rejected "funding rate as a directional signal" (continuous, majors, R^2 12.5% at 7 d, no
  variance on BTC); this round's 14-cell grid (`sim/funding_grid.txt`, 7 of 14 daily cells below baseline), the proportional
  SZ-15 (harmful), and UNI-7 (slow eligibility gate; dropped). Nothing in the repo tested a binary tail cut-out.
- Why it is materially different from the rejected signal use: binary; removes exposure only; binds on <= 10% of coin-days
  (0.5-3% post-2021); never sizes up; two parameters; and it has a cost mechanism the signal use lacks (funding paid in the
  > 30-50%/yr buckets is 9-22 bps/day = 33-80%/yr of notional; Delta alt funding is uncapped, max +0.17%/8 h). It is the
  cost-avoidance tail of a rule the repo already pays 1.9-3.4%/yr of equity for.
- Refutation points that stand: (1) selection: (30 d, 30%) and (14 d, 40%) are the best 2 of 14 cells on the sample they
  were chosen on; the surface is non-monotone (30d>20% 1.32, 30d>30% 1.37, 30d>40% 1.22, 30d>50% 1.14). (2) The
  directional mechanism is NOT supported on Binance: the > 50%/yr bucket still earns +62 bps/day gross (t 2.5) on 2020-26 and
  +22 bps (t 0.4) on 2022-26; only Delta's n = 48 bucket is negative. The full-sample Sharpe gain is a vol cut (CAGR 24.2 ->
  21.6%, vol 18.7 -> 15.1%, DD -21.9 -> -14.0%) concentrated in 2021; it is a "lower return per unit of risk in the
  crowded tail" effect, which is weaker than the candidate text implies. (3) Post-2021 the rule binds on 0.5-3% of
  coin-days: the +0.03..+0.13 increments on Binance 2022-26 and Delta rest on a handful of episodes (DOGE/XRP Nov-Dec 2024,
  BNB 2026) that have not been counted. (4) Every panel the candidate cites (9-coin Binance full and 2022-26, Delta) has
  been looked at; the deflated-Sharpe budget (`av_dsr.txt`) is already spent on this family. (5) Live mismatch: the
  backtest uses Binance funding pre-2024, but Delta charges majors 1.8-17x Binance and alts are uncapped, so live binding
  frequency will exceed the backtest's (a conservative direction for a cut-out, but it means the weekly operator will see
  the rule fire more often than the T5-style record suggests).
- The one untouched, decisive panel exists and is runnable at no data cost: the 24/25-coin ex-ante Binance panel carries
  funding for every coin (section 0). 2021 alt funding of 100%+/yr gives many binding episodes there, and that is where
  the rule must earn its keep against Sharpe 0.86 / 0.82 baselines.
- Refined rule (one primary cell, one declared secondary, acceptance fixed before the run): F_i(d) = 365 x mean over the
  last 30 calendar days of the daily funding fraction paid by longs (Binance fundingRate archive summed per day before
  2024-04; Delta FUNDING:<sym> candles, three 8-h settlements summed per day, from 2024-04; the weekly book reads it at the
  Monday 00:00 UTC decision). If F_i(d) > 0.30, w_i = 0 for the next holding period; otherwise `target_weights` unchanged;
  the rule never increases a weight. Secondary cell, declared now and not chosen afterwards: W = 14 d, 40%. Decisive
  test: panel B (24 ex-ante perps; also 25 with DOGE) daily TV 0.40 and weekly Mon TV 0.25 band 10, 2020-05..2026-09 and
  2022-01..2026-09, paired 20-day block bootstrap of Sharpe(variant) - Sharpe(baseline). Accept iff on BOTH B lines:
  Sharpe +0.05 with P(diff <= 0) <= 0.25, maxDD not worse, CAGR not lower by more than 1 pp, and the rule binds in >= 8
  distinct episodes (coin x contiguous run >= 3 days) outside 2021. Report the 9-coin and Delta lines for the record only;
  report CAGR, vol, funding/yr and episode count alongside Sharpe. If adopted, `trend_paper.py --orders-only` prints F_i
  per coin so the hand book can apply it.
- Evidence quality: single_study (local in-sample grid; no external study reached; the mechanism half-holds). Test cost:
  trivial (`sim/sim_costs.py` fmode='skip' exists; panel B loader `tools2/data.py` exists with funding).

### OVL-3 Fast-exit veto (20-day return <= 0 forces flat) -> REFINE (no standalone cell; conditional on the SIG-9 diagnostic)
- Prior tests: T3d (20,) alone 0.90 (DD -22.2%), (10,30,60) 1.08 vs 1.12: faster is worse on this book; T3i day stops
  1.05/1.02/0.99 and the per-position stop 1.25 -> 1.13 (price/PnL exits cost Sharpe); the current {0, 0, 1/3, 1} mapping
  already gives the Correction state (r20 <= 0, r60 > 0, r120 > 0) the lowest non-zero weight. Not tested as a gate.
- Refutation: (1) the cited multi-asset evidence argues against the rule: Goulding-Harvey-Mazzoleni's dynamic Correction
  weight is between 0 and 1, never 0 ("the fix is not to trade faster"), static 1-month trend is the worst speed in their
  43-futures sample (0.36; -0.14 in 2009-19) [SECONDARY], Lemperiere et al.: fast trends withered [SECONDARY]; the only
  pro-veto evidence (Han-Zhou-Zhu stop-loss) is cross-sectional equity momentum. (2) Locally the state is 11.8% of coin-days
  at 1/3 weight, so about 4% of coin-day weight is at stake, against a 14.6 bps round trip every time r20 crosses zero;
  on the weekly book the veto adds flips to a 192-trade/yr book, on the daily book it adds turnover where fees are already
  1.1%/yr. (3) The 10-day and EMA_20 variants are extra parameters with no evidence. (4) The question "is the Correction
  state's weight too high" is answered for free by the SIG-9 state diagnostic already ordered by the signal verifier.
- Refined rule: do not run a standalone veto cell. First the SIG-9 diagnostic (next-7-day mean return and t-stat by
  Bull/Correction/Bear/Rebound with SLOW = sign(P/P-120 - 1), FAST = sign(P/P-20 - 1), on the 9 and the 24 ex-ante coins,
  2020-26 and 2022-26). Only if the Correction-state forward return with the signal on is <= 0 (t < 0) on the 24-coin panel
  in BOTH windows, run ONE line: w_i = 0 whenever P_t/P_{t-20} <= 1 and the rule would otherwise hold 1/3 (entries and
  the 60/120 sleeves unchanged; 20-day only; no 10-day, no EMA variant), judged on panel B with the OVL-2 acceptance form
  plus flips/yr and fees/yr. If the Correction return is positive but below Bull, the mapping question belongs to SIG-10,
  not to a veto.
- Evidence quality: single_study (GHM is multi-asset but second-hand, and its conclusion is the opposite of a full veto).
  Test cost: trivial (one line in `target_weights`) after the small SIG-9 diagnostic.

### OVL-4 Daniel-Moskowitz momentum-crash indicator (bear + high vol) -> DROP
- Prior tests: T3j / d3_regime (BTC < 200-day: the same "bear" direction, neutral on daily, worse DD), realized-vol filters
  (1.02/1.00 weekly; 1.18/1.09 daily, by skipping 2021), shorts rejected (0.78 vs 1.25) — and shorts are where the DM
  effect lives.
- Refutation: (1) [LOCAL] as specified the indicator is a no-op: BTC 24-month return < 0 AND 60-day basket vol above its
  trailing 2-year median holds on 0.8% of days (2022 1%, 2026 5%), with 0.007x gross held, because crypto's bear states
  (2022 H2-2023, 2026) are LOW-vol relative to their own two-year history; the DM "high vol during a bear" conjunction
  that marks equity rebounds is almost empty here. (2) The bear-only fallback (20-27% of days, all of 2023) halves exposure
  where the baseline holds MORE gross (0.239x vs 0.187x), i.e. through the +16% 2023 recovery. (3) The mechanism, past
  losers as a call option on the market whose rebound crushes the short leg, needs a loser leg; the long/flat book has
  none, and its worst days (2021-05-19, 2020-11-26, 2025-10-10, 2024-12-09) are parabolic reversals while long, the
  opposite state. (4) The continuous DM variant needs in-sample state means (mu_hat, sigma_hat) and is a curve fit on 5
  bear episodes. DM 2016 is replicated across equity markets for cross-sectional momentum [SECONDARY]; there is no
  evidence at all for the long-only time-series application. Grobys 2025 (crypto CS momentum crashes come from single
  coins / the short leg) [UNVERIFIED] points the same way.
- Evidence quality: single_study (replicated for CS equity momentum; none for this book). Test cost: trivial (but a no-op).
  Refined rule: none.

### OVL-5 Correlation-spike de-risking (reduce-only above rho 0.80) -> DROP
- Prior tests: realized-vol filter (T3j 1.02/1.00; d3 1.18/1.09 — the closest cousin, since correlation and vol spike
  together in crypto sell-offs); SZ-6 refined by the sizing verifier to ONE correlation cell (b) whose multiplier already
  falls when rho rises (CF = sqrt(N/(1+(N-1)rho)) relative to a 0.70 reference, EWMA-smoothed); the local correlation-
  quintile diagnostic (`sizing_diag_out.txt` s.3): next-7-day EW basket Sharpe Q1 (rho 0.51) 1.44, Q2 0.45, Q3 -0.88,
  Q4 -0.63, Q5 (rho 0.82) 0.82 — non-monotone, and the top quintile where OVL-5 binds is not a low-return state.
- Refutation: (1) the sign is contested even in equities (Baltas-Kosowski's post-2008 story for; Pollet-Wilson 2010's
  positive correlation-return relation against; Boyer-Gibson-Loretan: conditional correlation spikes are partly a
  measurement artefact) [all SECONDARY]; no crypto evidence exists (WebSearch this pass found none). (2) [LOCAL] rho > 0.80
  on 15.8% of days, > 0.85 (the 0.5 floor) on 5.0%, yearly medians 0.73-0.77 in 2022 and 2025-26 vs 0.64-0.65 in 2023-24:
  the state is the sell-off state in which the signal is already flat, so the increment is small and of uncertain sign.
  (3) It is the one-sided copy of SZ-6(b), which already gets the family's single correlation trial; a second correlation
  cell doubles the trial count for an expected effect inside +-0.03 Sharpe (SE 0.50). (4) It is not reduce-only in effect
  on a vol-targeted book: cutting gross when rho is high and leaving it when rho is low is a TV tilt toward low-rho days,
  which the quintile diagnostic says is not where the return is.
- Evidence quality: single_study (secondary notes on futures/equities; no crypto). Test cost: trivial (`rules.corr_factor_bk`
  exists). Refined rule: none; SZ-6(b) covers the direction.

### OVL-6 Basket-trend gate (halve when the EW basket's own 3-lookback signal <= 0) -> DROP
- Prior tests: T3j / `d3_regime_filter_output.txt` BTC < 200-day -> flat (daily 1.25 -> 1.25, DD -21.9 -> -25.9%; weekly
  1.12 -> 1.18, -14.4%, "not adopted", post hoc); resource/07 lists the regime-filter family as rejected.
- Refutation: (1) [LOCAL] the gate state (45.4% of days) is the tested state in different clothes: Jaccard 0.64 with
  BTC<200d, 74% of gate days are 200-day days and 83% of 200-day days are gate days. (2) In the state the rule already
  holds 0.044x gross (vs 0.326x outside): with average pairwise correlation 0.72 the basket's trend is already inside each
  coin's signal, so the gate re-halves a book that is already nearly flat; the whole effect sits on the 15% of days
  where the rule holds > 0.05x against a negative basket, which are the idiosyncratic alt trends (DOGE 2021, XRP late
  2024) the universe's return came from, and the long gate episodes 2024-06-17..10-04 and 2025-11..2026-04 bracket the
  rule's good runs. (3) The equity evidence (Cooper-Gutierrez-Hameed: CS momentum profits only after UP markets) is
  cross-sectional and about the loser leg; Zakamulin's "bear weights close to zero" describes what the floor already does.
  (4) T3j already bounds the family: neutral-to-negative on the daily book, +0.06 (0.12 SE) on the weekly; a cousin with
  a 0.64 overlap cannot do materially better and would be the third regime-filter trial on the same sample. The x0
  variant is "flat on 45% of days".
- Evidence quality: snippet_only (CGH not opened; applicable evidence is the repo's own T3j). Test cost: trivial.
  Refined rule: none.

### OVL-7 BTC-dominance / altseason gate -> DROP
- Prior tests: T3f (BTC only 0.85, BTC+ETH 0.95, 9 coins 1.12: tilting the book toward BTC costs Sharpe); resource/07
  rejected cross-sectional alt momentum / relative strength; `alternative_edges.md` KQ7: "altseason rules have no
  backtested evidence at all", documented false signal Sept 2025.
- Refutation: (1) [LOCAL] BTC leads the 8-alt basket over 90 days on 67.5% of days (2023 79%, 2024 83%, 2026 90%); alt
  gross held in the state 0.140x vs 0.205x outside; halving alts there is a permanent ~23% cut of alt gross, i.e. a tilt
  toward BTC that T3f shows lowers Sharpe, applied most in the rule's best years. (2) The mechanism is two-sided: D_t > 0
  both when BTC rallies faster than alts and when alts sell off harder than BTC, so the gate mixes the alt-rally
  precursor with the alt-crash state. (3) It is a cross-sectional relative-strength rule in disguise (rejected family;
  negative OOS 2025-26). (4) No backtest exists anywhere: this pass's WebSearch found only index definitions and current
  readings; the sources are The Block and a Pantera quote [UNVERIFIED]. (5) The Altcoin-Season-Index variant needs a
  top-50/100 market-cap history the repo does not hold.
- Evidence quality: snippet_only. Test cost: trivial for D_t (large for the index variant). Refined rule: none.

## 4. Summary

| id | verdict | one line |
|---|---|---|
| OVL-1 | drop | the "crash state" is on 73% of days; x0.5 there is a 23.5% TV cut plus the 200-day timing T3j already found neutral; the paper's base book lacks the vol scaling this rule has |
| OVL-2 | refine | materially different from the rejected signal use (binary tail, exposure-removing, cost mechanism), but its cells were picked on the sample; one primary cell (30 d, 30%) + declared secondary, decided on the untouched 24-perp panel with fixed acceptance |
| OVL-3 | refine | no standalone cell; the SIG-9 state diagnostic decides; one conditional veto line only if Correction-state forward returns are <= 0 on the 24-coin panel |
| OVL-4 | drop | fires on 0.8% of days (no-op); the bear-only fallback halves exposure through 2023 where the rule holds more gross; the mechanism is the short leg |
| OVL-5 | drop | contested sign, no crypto evidence, top-correlation quintile is not a low-return state locally; SZ-6(b) already holds the family's one correlation trial |
| OVL-6 | drop | Jaccard 0.64 with the tested BTC<200d state; the rule already holds 0.044x there; the only bite is on the idiosyncratic alt trends that made the return |
| OVL-7 | drop | state on 67.5% of days; a permanent BTC tilt that T3f shows costs Sharpe; relative strength in disguise; no backtest exists |

Trials the overlay family puts forward for Phase 2: one (OVL-2 primary cell, with its declared secondary as a robustness
line) plus one conditional line (OVL-3) that runs only if a free diagnostic says so. Expected effect of OVL-2 on the 9-coin
Delta book post-2021: +0.0 to +0.1 Sharpe from a handful of alt episodes, mostly lower funding paid; it is a cost rule,
not an edge.

## 5. Verification status
VERIFIED by reading: resource/07 rejected table and kill table; backtest_results.md pre-registered plan, T3 table, T6, T7;
d3_runs/d3_regime_filter_output.txt and the d3_tests outputs; calc/d2_checks2_output.txt; av_runs/av_sub.txt,
av_universe_9.txt, av_delta.txt; local_evidence.md tails; 2026-10-08 and 2026-10-13 memos; trend_backtest.py::target_weights;
tools/qd_engine.py btc_filter; research2 notes (overlays.md, crypto_academic.md 1.18, costs_funding.md 2.2), sim outputs
(funding_grid.txt, funding_bucket_diag.txt), verify_sizing.md SZ-6, verify_signal.md SIG-9, verify_universe.md UNI-7,
tools2/cache_binance_25c funding coverage, master_candidates.md OVL section. COMPUTED here: ovl_states_out.txt,
ovl1_thresholds_out.txt. UNVERIFIED: the Howden-Andreev abstract (search summary only), Daniel-Moskowitz, Cooper-Gutierrez-
Hameed, Pollet-Wilson, Baltas-Kosowski, Lemperiere, Grobys 2025, The Block / Pantera items; SSRN, arXiv, Springer and
journal hosts are blocked by the proxy.
