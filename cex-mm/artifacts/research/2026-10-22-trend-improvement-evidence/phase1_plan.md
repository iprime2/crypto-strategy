# Phase 2 pre-registered test plan: long/flat TSMOM on Delta India perps

Written 2026-10-21 by the head of research, before any Phase 2 run. Inputs: `master_candidates.md` (57 entries) and the seven
adversarial verifications `verify_{signal,sizing,universe,costs_execution,overlay,timing_cadence,data}.md` in this directory.
Status: FROZEN once the first Phase 2 run starts. Record `sha256sum phase1_plan.md` in `phase2/summary.md` before run 1. Any later
change is appended under section 10 "Amendments" with a date and the affected variant is marked post hoc in every table.

Scope, in one paragraph. Nothing in the repo is modified by Phase 2 (the engine lives in the scratchpad), no orders are placed, and
the two running paper books (daily VM book TV 0.40 band 0; weekly hand book TV 0.25 band 10 Monday) are NOT changed by any result
below. A passing variant goes to Phase 3 as a proposal for a THIRD paper book run alongside the two for at least 8 weeks, then a user
decision. The only change this plan would make to a running book without new evidence (`--band 0.10` on the daily paper book, T3c and
d2_checks 2c) is outside Phase 2 and still needs the user's explicit go-ahead.

## 1. Baseline (the current rule, exactly)

`cex-mm/scripts/trend_backtest.py::target_weights`: at the 00:00 UTC close of day t, per coin with 121 closes, `s = mean_L sign(P_t/P_{t-L} - 1)`,
L in (20, 60, 120); `sig = max(s, 0)` (so a count of 0 / 1 / 2 / 3 positive sleeves maps to a signal of 0 / 0 / 1/3 / 1); `vol = sqrt(365 x mean of the last 60
squared daily log returns)` (uncentered); `w_i = sig_i x (TV/N)/max(vol_i, 0.05)` with N = coins that have 121 closes that day; gross cap.
Position set at t close, held over t -> t+1. Costs 7.31 bps per side on traded notional (5.31 taker incl. GST + 2 slippage); funding paid
on longs from the archive (Binance: daily sum of the 8 h fractions; Delta: mean hourly FUNDING:<sym> rate x 3 / 100).

Two baseline books (harness `evaluate.py` DAILY / WEEKLY):
- **D** daily: TV 0.40, cap 2x, band 0, rebalance every day.
- **W** weekly: TV 0.25, cap 1x, 10 % band (skip when |target - held| < 0.10 |target|, closes always trade), decision on the Sunday
  candle = Monday 00:00 UTC, executed Monday 00:05.
Reference lines computed in T0 and reported next to every timing variant (not trials): D at TV 0.25 band 10 (T1: A 1.25); the mean of the
seven single-weekday W books (A 1.23); the mean of the six single-decision-hour W books (A 1.21).

T0 (before run 1): the engine must reproduce `phase2/baseline.json` to 4 decimals (A-daily 1.2498 / A-weekly 1.1206 / B-daily 0.8512 /
B-weekly 0.8101 / C-daily 0.9941 / C-weekly 0.7041; max |daily return diff| vs the repo function < 1e-9 on A-daily), and the ex-ante
cohort must reproduce `av_runs/av_universe_9.txt` (24 perps daily 0.86, weekly 0.82).

## 2. Datasets (all on disk; nothing to fetch except TIME-3's hourly files)

| id | universe | window | source on disk |
|---|---|---|---|
| **A** | the nine (BTC ETH XRP BNB ADA LTC LINK DOGE BCH), Binance USDT-M | 2020-05-01..2026-09-30 (2,344 return days) | `tools2/cache_binance_25c_*.npz` (sub NINE); raw `trend-cache/`, `av_cache/` |
| **B** | the 24 USDT-M perps listed by 2020-02-20 (`data.EXANTE24`, EOS to its 2025-05 delisting, flattened at the last close at taker cost); also reported with DOGE (25) | same | same npz (funding present for all 25) |
| **C** | the nine on Delta India (close only) | 2024-08-10..2026-10-12 (794 return days) | `trend-cache/delta-2026-10-12.json` via `tools2/data.load_delta` |
| B+ | B plus PAXG/XAUT (UNI-2) | A window; gold from its 121st close (2020-12-27) | `research2/dl/paxg_spot` (74 monthly spot zips), `universe/spot/`; `tools2/cache_binance_10c_*.npz` is nine+gold |
| Bw | the survivorship-free pool for UNI-1 (896 USDT-M symbols incl. delisted) | A window | `universe/cache_all` + `universe/cache` + `av_cache` + `trend-cache`; `tools2/cache_binance_696c_*.npz`; quote_volume in every row |
| hourly | 1 h closes for TIME-3 | A, C windows | `hourly/*USDT-1h.csv` (nine), `research2/delta_data/hourly_*.json` (nine); the 15 extra B coins: monthly 1h zips from `data.binance.vision/data/futures/um/monthly/klines/<SYM>/1h/` (reachable; ~1,150 files) |

Windows: FULL = the dataset window; POST = 2022-01-01..2026-09-30 (B, A: 1,734 days; C: not applicable, C is post by construction);
H1 = 2020-05-01..2023-12-31; H2 = 2024-01-01..2026-09-30 (A, B); for C, H2 = 2025-01-01..2026-10-12 only.

## 3. Metrics (per variant, per panel, per cadence, per window)

Sharpe = mean/sd(ddof 1) of daily returns x sqrt(365); CAGR; vol; maxDD (daily closes); worst day; worst 7-day (min rolling 7-day
compounded return); worst calendar year; turnover = traded notional / equity / yr; fees/yr = turnover x 7.31 bps; funding/yr;
orders/yr = coin-days with a non-zero trade / yr; avg gross; fee_SR = fees_yr / vol and funding_SR = funding_yr / vol (reporting only).
Matched-vol line: when the variant's realized vol on the panel differs from the baseline's by more than 5 %, re-run it once with
TV' = TV x vol_base / vol_var and report maxDD, worst 7-day and Sharpe from that re-run (Sharpe is scale-free, T3a; the linear
approximation maxDD x vol_base/vol_var is NOT used for decisions). Whole-contract lines: `capital` in {1000, 2500, 5000} with the
Delta contract values (`data.CVALS`) on A and C; B is run unrounded (optional rounded B uses cv_i = $25 / first close for coins without
a Delta contract, information only). Every variant writes `phase2/<id>.json` with the full A/B/C x daily/weekly x FULL/POST/H1/H2 grid
plus the bootstrap block, and one line per panel/cadence into `phase2/summary.md`.

## 4. Statistics, fixed now

**Paired block bootstrap of the Sharpe difference** (pure Python, so it runs in `trend_backtest.py` as well as in the numpy harness; the
harness's `sim.block_bootstrap_diff` is an accepted implementation and must be stated as the one used):
```
import math, random, statistics
def sharpe(x):
    s = statistics.stdev(x); return sum(x)/len(x)/s*math.sqrt(365) if s > 0 else 0.0
def boot_diff(ra, rb, n=1000, block=20, seed=7):      # ra = variant, rb = baseline, same dates, same length T
    T = len(ra); rng = random.Random(seed); nb = T//block + 1; diffs = []
    for _ in range(n):
        idx = []
        for _ in range(nb):
            s = rng.randrange(0, T - block + 1); idx.extend(range(s, s + block))
        idx = idx[:T]
        diffs.append(sharpe([ra[i] for i in idx]) - sharpe([rb[i] for i in idx]))
    diffs.sort(); d = sharpe(ra) - sharpe(rb)
    return d, diffs[int(0.025*n)], diffs[int(0.975*n) - 1], sum(x <= 0 for x in diffs)/n, statistics.stdev(diffs)
```
Output per comparison: Delta (point), 95 % CI, P(Delta <= 0), sd_Delta. Run on B POST (primary), B FULL, A POST, A FULL, C FULL, B H1, B H2.

**Multiple-testing haircut.** N = 24 primary cells (section 6; conditional cells count whether or not they run; neighbors never
enter a selection so they do not add to the maximum being selected over). Expected maximum of N null differences (Bailey and Lopez de
Prado): E_N[max] = sd_Delta x ((1 - g) Phi^-1(1 - 1/N) + g Phi^-1(1 - 1/(N e))), g = 0.5772, Phi^-1 = `statistics.NormalDist().inv_cdf`;
at N = 24 the multiplier is 1.98, so the haircut is 1.98 x sd_Delta of the variant's own bootstrap (a variant that barely moves the
book has a small sd_Delta and a small haircut, which is correct). Reference: `av_dsr.txt` (18 trials at sd 0.08-0.15 -> E[max] 0.15-0.28).

## 5. Decision rule (fixed now; applied to the variant's target book(s); "both" means both cadences must pass)

**Class I, Sharpe improvement.** All of:
1. On B POST: Delta >= max(0.05, 1.98 x sd_Delta) AND P(Delta <= 0) <= 0.10.
2. Does not lose elsewhere: Delta >= -0.03 on A POST, A FULL and C FULL.
3. Positive in both halves: Delta(B H1) > 0 and Delta(B H2) > 0.
4. Neighborhood: every neighbor's Delta on B POST >= 0 and >= primary Delta - 0.10. The primary setting is never replaced by a neighbor.
5. maxDD at matched vol on B FULL not worse than the baseline's by more than 2 pp; worst 7-day not worse by more than 1 pp.
6. The variant's own extra conditions in section 6.

**Class II, cost or operational improvement at equal Sharpe** (the claim is "same Sharpe, fewer orders / less funding / smaller DD"). All of:
1. On B POST: Delta >= -0.03 AND the 95 % CI lower bound >= -0.10.
2. Delta >= -0.03 on A POST, A FULL and C FULL; neither B half below -0.05.
3. The named operational metric improves by at least the stated amount on all three panels (A, B, C) on the target cadence.
4. No neighbor's Delta on B POST below -0.08; the operational gain holds in every neighbor.
5. maxDD and worst 7-day at matched vol not worse by more than 2 pp / 1 pp.
Multiplicity for class II is a false-non-inferiority risk, not a false-discovery risk; the protection is the -0.03 margin, the three-panel
and two-half consistency, and the fact that the operational metric is deterministic (order counts, fees) rather than estimated.

**Research-number class (UNI-1 only):** the comparison is rotating-ex-ante vs static-ex-ante (B), never vs the hindsight nine; a pass is
a number for the annual review and a live rule only at >= $5,000.

**"Do nothing"** = any variant that fails its class on any item: the design stays as written, the result and its numbers go into the
memo and into the "considered and rejected" table of resource/07 with the prior-test ledger. A pass on B but a loss on A or C is "do
nothing, revisit at the annual review with one more year of data". A class II pass is an execution change proposal for Phase 3 (third
paper book, or the daily VM book only with the user's go-ahead), not a return claim. Variants with "I/II" pass if either class passes;
the memo states which. No variant is promoted on CAGR, on the hindsight nine alone, on the Delta panel alone, or on a neighbor.

## 6. Variants (24 primary cells; parameters fixed from the literature or the verifier's refined rule, never from our data)

Legend: target book D = daily bot (TV 0.40), W = weekly hand book (TV 0.25 band 10), T = tranche book (daily-executed, TV 0.25),
both = D and W. "Expected" is the pre-registered expectation entered now. Complexity is for the tools2 harness (numpy) or a
pure-Python port of `target_weights`.

### 6.0 Preconditions and diagnostics (not trials)

**D-0 DATA-1 survivorship-free loader** (precondition for UNI-1). Pool = every plain USDT-M symbol in the S3 index of
`data/futures/um/monthly/klines/` (900 names; quarterly `_YYMMDD` contracts excluded); prices from the union of the four cache dirs (896
symbols); funding from the matching fundingRate files (490; missing = 0 and flagged). A symbol is a candidate on decision day d only if
quote_volume(d) > 0 (zombie files: FTT, SC, RAY, FTM keep zero-volume rows for years); its delisting day = last day with quote_volume > 0;
the position is flattened at that close at taker cost (LUNA ends at 0.0080). A renamed symbol (MATIC->POL, FTM->S, RNDR->RENDER, KLAY->KAIA)
is a new listing with no history. Gate: the 24-perp cohort through this loader reproduces 0.86 / 0.82 before any rolling run; report the
number of delisting events hit and their P&L separately.

**D-1 SIG-9 state diagnostic** (gates SIG-9 and OVL-3). Per coin-day: SLOW = sign(P_t/P_{t-120} - 1), FAST = sign(P_t/P_{t-20} - 1);
Bull = (+,+), Correction = (+,-), Bear = (-,-), Rebound = (-,+). Report mean and t-stat (Newey-West lag 6) of the next-7-day log return by
state, with the signal on (sig > 0) and unconditional, on the 9 and the 24 ex-ante coins, 2020-26 and 2022-26. SIG-9 runs only if
Correction >= Bull (mean next-7-day return) on the 24-coin panel in both windows; OVL-3 runs only if Correction <= 0 with t < 0 on the
24-coin panel in both windows. Both cannot be true at once, so at most one of the two conditional lines runs.

### 6.1 Signal family (9 cells)

**SIG-2 Vol-normalised clipped ensemble** (merges SIG-1 line A) | target both | class I/II (II metric: trades/yr AND funding/yr down >= 25 %) | priority 2 | trivial
- Rule: z_L = ln(P_t/P_{t-L}) / (vol60_daily x sqrt(L)), vol60_daily = the rule's 60-day vol / sqrt(365); s_L = clip(z_L / d, 0, 1), d = 1;
  sig_i = mean_L s_L over L in (20, 60, 120); w, cap, band, cadence unchanged.
- Fixed: d = 1 (Carver forecast cap at the vol-normalised unit; the d = 2 cousin already ran negative on all four panels, `phase2/sig_continuous.json`).
- Neighbors: d = 0.5, d = 1.5; SIG-1A form (t_L = mean(r)/(sd_L(r)/sqrt(L)) over the last L log returns, s_L = clip(t_L, 0, 1)).
- Data: A, B, C closes. Judge unrounded and at $5,000; $1,000 information only (grading rounds to 0/1 contract on BTC/BNB).
- Hypothesis: moves the cost term (funding paid falls with lower average exposure, ~-30 % turnover) and the signal term slightly down
  (Bussgang: sign keeps 0.80 of the linear covariance, but local smoke -0.07..-0.14). Expected Sharpe -0.05..0.00; funding -25..-35 %.

**SIG-1B t-stat dead zone** | target both | class I/II (II metric as SIG-2) | priority 2 | trivial
- Rule: t_L = mean(r)/(sd(r)/sqrt(L)) over the last L daily log returns (plain, no Newey-West, no OLS slope); s_L = 0 if |t_L| < 1 else
  sign(t_L); sig_i = max(mean_L s_L, 0); rest unchanged.
- Fixed: threshold 1 (the BK 2013 form uses 2, which is inactive on 95-96 % of coin-days here; 1 is the verified 2017/2020 clip boundary).
- Neighbors: threshold 0.75, 1.25.
- Data: A, B, C. Hypothesis: sparsifies weak trends; funding down 20-30 %, Sharpe -0.05..+0.02 (BK: "insignificantly different from SIGN").

**SIG-3a EWMAC binary control (kernel test)** | target both | class I/II (II metric: orders/yr down >= 15 % at equal Sharpe) | priority 2 | small
- Rule: for pairs (16,64), (32,128), (64,256): raw_n = (EWMA_span n(P) - EWMA_span 4n(P)) / sigma_px, sigma_px = EWMA span-35 std of daily
  price changes (price units); sig_i = mean_n 1[raw_n > 0]; floor at 0 is implicit; sizing unchanged.
- Fixed: pysystemtrade chapter-15 pairs; span 35 (Carver `robust_vol_calc`). No (8,32).
- Neighbors: speed x0.75 {(12,48),(24,96),(48,192)}; speed x1.25 {(20,80),(40,160),(80,320)}.
- Data: A, B, C. Hypothesis: EWMA kernel vs point-to-point sign at matched speed; Levine-Pedersen says second order; expected Sharpe
  -0.05..+0.03, orders -10..-25 % (smoother kernel). Run before SIG-3b.

**SIG-3b EWMAC continuous ensemble** | target both | class I/II (II metric as SIG-2) | priority 2 | small
- Rule: scaled_n = raw_n x {3.75, 2.65, 1.87}; capped_n = clip(scaled_n, -20, 20); combined = mean_n capped_n (FDM 1.0);
  f_i = clip(combined, 0, 20)/20 in [0, 1]; w_i = f_i (TV/N)/max(vol60, 0.05); cap, band, cadence unchanged.
- Fixed: scalars = chapter-15 values; denominator 20 so one coin never exceeds the sign rule's per-coin budget (no /10 -> [0,2] line).
- Neighbors: denominator 15 and 30 (saturation level); speed robustness is read from SIG-3a.
- Data: A, B, C; ~770-day warm-up for span 256 (C is a weak check for the slowest pair, say so in the memo).
- Hypothesis: as SIG-2 (graded exposure lowers funding; smoke says Sharpe flat-to-down); plus maxDD at matched vol no worse (extra condition).

**SIG-4 Donchian channel ensemble with ratcheting mid-line exit** | target both | class I/II (II metric: maxDD at matched vol >= 3 pp better AND trades/yr lower) | priority 2 | small
- Rule: per coin, per n in {5, 10, 20, 30, 60, 90, 150, 250, 360}: Up_n = max close over the last n days incl. t, Down_n = min, Mid_n = (Up_n+Down_n)/2.
  Exit first: Pos_n = 1 and close <= Stop_n -> Pos_n = 0. Entry: Pos_n = 0 and close >= Up_n -> Pos_n = 1, Stop_n = Mid_n. While long
  Stop_n(t+1) = max(Stop_n(t), Mid_n(t)). sig_i = (# channels long)/(# channels with history) (eligible-channel normalisation).
  Sizing repo form (only the signal changes). D book: trade on any Pos change, 10 % band only on vol-driven changes. W book: evaluate
  daily, trade Monday. `rules.sig_donchian` lacks the ratchet and the exit-before-entry order: write it.
- Fixed: the paper's nine lookbacks (Zarattini-Pagani-Barbon).
- Neighbors: 7 lookbacks (<= 150); paper sizing sig_i x min(0.25/vol90, 2.0); start-on-same-days normalisation (count channels only from
  the day all nine exist).
- Data: A, B, C (360-day channel starts 2020-12..2021-07 on Binance, 2025-04 on Delta).
- Hypothesis: a stateful binary rule with ~50 % lower vol-normalised turnover (Sepp-Lucic) and the replication's picture "Sharpe = beta,
  DD cut"; expected Sharpe -0.05..+0.05, maxDD -2..-5 pp at matched vol, trades/yr -30 %. The memo must say this is not the rejected
  fixed-percentage stop (T4), it is the trend definition's own exit.

**SIG-7A Add a 250-day sleeve** | target both | class I | priority 3 | trivial
- Rule: looks = (20, 60, 120, 250); sig_i = max(mean over the sleeves the coin has history for of sign(P_t/P_{t-L} - 1), 0) (eligible-sleeve
  normalisation so the 2020 universe is unchanged); rest unchanged.
- Fixed: 250 (the 12-month futures convention, HOP/MOP). Neighbors: 200, 300.
- Data: A, B, C (Delta covers ~20 months with the sleeve). Hypothesis: slow-sleeve diversification (vendor barbell claim); expected
  neutral to negative (T3d: all-slower 0.95); accept only at +0.05 on B POST with maxDD no worse.

**SIG-10 Linear agreement count** | target both | class I with matched-vol DD | priority 2 | trivial
- Rule: sig_i = (1/3) sum_L 1[P_t/P_{t-L} > 1], L in (20, 60, 120) (mapping {0, 1/3, 2/3, 1} instead of {0, 0, 1/3, 1}); rest unchanged.
- Fixed: equal weights (HOP 2017 multi-horizon default). Neighbors: mapping {0, 1/4, 1/2, 1}; mapping {0, 1/2, 3/4, 1}.
- Data: A, B, C. Hypothesis: raises average exposure 34.7 % -> 51.1 % (more beta, ~1.5x funding); expected CAGR up, Sharpe flat to lower,
  DD at matched vol worse (the always-long endpoint is 0.99 vs 1.12). Because it raises beta a flat Sharpe is a rejection: class I only,
  and condition 5 is judged on the matched-vol re-run.

**SIG-9 Turning-point tilt (conditional on D-1)** | target both | class I | priority 3 | small
- Rule: sig_i = max(w_S SLOW + (1 - w_S) FAST, 0), w_S = 0.5 in Bull/Bear, 0.8 for the 20 trading days after a Correction entry, 0.2 for
  the 20 days after a Rebound entry; SLOW/FAST as in D-1; rest unchanged. Runs only if D-1's SIG-9 condition holds.
- Fixed: 0.8/0.2 and 20 days (Goulding-Harvey-Mazzoleni, secondhand). Neighbors: memory 15 and 30 days (weights fixed).
- Data: A, B, C. Hypothesis: "stay 0.6 long for a month" after a turn, i.e. more beta in disagreement states; expected Sharpe -0.05..+0.05.

**SIG-11 Carver breakout 50/50 with the sign ensemble** | target both | class I | priority 3 | small
- Rule: for L in (20, 60, 120) (matched to the sign rule, not 20/80/160): mid_L = (max_L + min_L)/2 over the last L closes;
  b_L = 40 (P - mid_L)/(max_L - min_L), EWMA-smoothed with span max(int(L/4), 1), clipped to [-20, 20]; f_B = max(mean_L b_L / 20, 0).
  Primary line: sig_i = 0.5 sig_sign + 0.5 f_B (FDM 1.0). Control line: sig_i = f_B (breakout only). Sizing unchanged.
- Fixed: pysystemtrade breakout.py form. Neighbors: lookbacks (20, 80, 160) (the original spec); smoothing span L/8.
- Data: A, B, C. Hypothesis: diversification across signal shapes at matched speed (Carver: breakout vs EWMAC corr 0.93, gain "small");
  expected +0.00..+0.05. Adopt only if breakout-only >= sign-only on A and B AND the 50/50 beats both on B POST (class I vs the baseline).

### 6.2 Sizing family (4 cells)

**SZ-1 EWMA variance, centre of mass 60 d** | target both | class II (metric: orders/yr down >= 15 %) | priority 1 | trivial
- Rule: s_t = (60/61) s_{t-1} + (1/61) r_t^2 (uncentered daily log returns, seeded with the mean of the first 60 squared returns);
  vol_i = sqrt(365 s_t); w_i = sig_i (TV/N)/max(vol_i, 0.05); cap 2x. Signal, band, cadence unchanged.
- Fixed: COM 60 = alpha 1/61 (Moskowitz-Ooi-Pedersen / AQR convention; same day-1 reaction as CC60, geometric decay instead of the 60-day echo).
- Neighbors: COM 45 (alpha 1/46), COM 90 (alpha 1/91).
- Data: A, B, C. Hypothesis: moves the vol-estimate noise term (local weekly estimate noise 0.067 vs 0.113) and hence vol-driven
  turnover (-15..-40 %); Sharpe expected 1.05-1.12 on A-weekly (T3e trend), i.e. within -0.03; level bias +4 % so judge at matched vol;
  extra condition: worst 7-day no worse.

**SZ-3 Carver mixed vol (0.7 fast + 0.3 long-run)** | target both | class II (metric: trades/yr <= baseline, i.e. not higher, AND orders/yr down >= 10 %) | priority 2 | trivial
- Rule: sigma_fast = EWMA span-35 std of daily log returns (min 10 obs); sigma_slow = trailing 365-day simple mean of sigma_fast
  (needs >= 120 obs, else sigma_fast); vol_i = sqrt(365) (0.7 sigma_fast + 0.3 sigma_slow); floor 0.05; w as baseline.
- Fixed: 0.7/0.3, span 35, 365 d (pysystemtrade `mixed_vol_calc` defaults). Neighbors: w_fast 0.6, 0.8.
- Data: A, B, C. Hypothesis: best local 30-day vol forecast (RMSE30 0.373 vs 0.425) at CC60's noise; level bias +8 %, judge at matched
  vol; expected Sharpe within 0.03, orders flat to -10 %, worst 7-day no worse (extra condition).

**SZ-6b Baltas-Kosowski correlation factor, time variation only** | target both | class I (extra: Delta >= +0.05 on A, B and C) | priority 3 | trivial
- Rule: rho_bar_t = mean pairwise 60-day Pearson correlation of daily log returns among coins with sig_i > 0 (all N if fewer than 3), each
  pair floored at 0; N_t = that count; CF_t = sqrt(N_t/(1 + (N_t - 1) rho_bar_t)); CF_ref,t = sqrt(N_t/(1 + (N_t - 1) x 0.70)) with the same
  N_t; m_t = EWMA_span20(CF_t/CF_ref,t); w_i <- w_i m_t; TV and cap unchanged. Judge at matched vol.
- Fixed: 60-day window (B&K use 3 months), reference 0.70 (local median rho 0.72), span 20. Neighbors: reference 0.60, 0.80.
- Data: A, B, C. Hypothesis: diversification term, bounded 1.07-1.37 locally; B&K full-sample gain +0.01 (secondhand); local correlation
  quintiles non-monotone; expected null. One run closes the correlation question (SZ-7 and OVL-5 fold in).

**SZ-13 Minimum-contract eligibility with risk re-allocation** | target both, whole contracts | class II at $1,000 (metric: orders/yr down vs the rounded baseline AND realized vol within 10 % of the unrounded line) | priority 2 | small
- Rule: full_i = (TV/N)/max(vol_i, 0.05) x E/(cv_i P_i) (full-signal position in contracts); eligible iff full_i >= 1.0, re-evaluated on the
  first decision day of each month with hysteresis (enter at >= 1.0, leave at < 0.8); N_eff = number eligible; w_i = sig_i (TV/N_eff)/max(vol_i,
  0.05) for eligible coins, 0 otherwise. Run on the whole-contract engine at $500 / $1,000 / $2,500 / $5,000 on C and on A with Delta
  contract values (B not applicable).
- Fixed: threshold 1 contract, monthly, 0.8 exit (Carver's minimum-capital rule, corrected for today's notionals: BTC 0.62, BNB 0.67, ETH
  1.60 contracts at $1,000 TV 0.25). Neighbors: threshold 2.0 (exit 1.6); exit hysteresis 0.9.
- Data: A, C, `data.CVALS`. Hypothesis: removes 0<->1-contract flips (12-23 % of traded dollars in the paper journal) and restores the risk
  budget at $500-1,000 (T5: gross 0.09x vs 0.12x); Sharpe within rounding noise (+-0.08); a no-op at $5,000 by construction. Primary
  judgement for this cell: C and A at $1,000 (Sharpe within 0.05 of the unrounded line on both, orders/yr down, vol within 10 %).

### 6.3 Universe family (2 cells; D-0 is the precondition)

**UNI-1 Yearly ex-ante liquidity-ranked universe** | target both | research-number class, judged vs B (static ex-ante) | priority 2 | small
- Rule: reset on the first decision day of each January; U = top-9 crypto USDT-M perps by trailing 30-day median USD turnover (Binance
  quote_volume throughout the backtest; today's Delta list is used only for the live note); eligibility >= 365 closes; exclude
  metal/xStock/stablecoin/leveraged/pre-launch tags; an incumbent stays while ranked <= 18; a delisted coin goes flat and is not replaced
  until the next reset; feasibility gate at the reset (UNI-5): E x (TV/N)/max(vol60, 0.05) >= 2 x cv x P (the live nine exempt), N = |U|
  after the gate; signal, TV/N, band, cap unchanged. 2020 starts from the top-9 on 2020-04-30.
- Fixed: N = 9, yearly, 30-day median, age 365, rank-18 hysteresis. Neighbors: (a) age floor 121; (b) quarterly reset; (c) N = 12 at $5,000.
- Data: Bw through D-0 (quote_volume, delistings), `data.CVALS` for the gate at $1,000 / $5,000; report names changed per year, delisting
  events hit, whole-contract lines at $1,000 and $5,000.
- Hypothesis: moves the diversification and liquidity terms; expected Sharpe 0.80-0.90 daily (no uplift over static-24, 0.86/0.82),
  maxDD no worse than -24.1 % / -16.8 %. Pass = daily >= 0.86 and weekly >= 0.82 FULL, Delta >= 0 on B POST, maxDD no worse, both halves
  not below static-24. A pass is a research number for the annual review (kill criterion #6); live use only at >= $5,000 (SOL/ZEC/AAVE round
  to zero at $1,000).

**UNI-2 Add gold (XAUTUSD, PAXG proxy)** | target both | class I (extra: Sharpe on 2020-08-28..2023-12-31 not below the base book's on that window; maxDD not worse; report 2024-26 and ex-2025) | priority 1 | small
- Rule: U = the nine + gold under the identical rule (sign ensemble, (TV/N)/max(vol60, 0.05), N = 10 from gold's 121st close, same band and
  cap). Gold series: Binance spot PAXGUSDT 1d from 2020-08-28 (in `tools2/cache_binance_10c`), stitched to Delta XAUTUSD daily candles from
  2026-04-17 where available; funding 5.5 %/yr synthetic (0.055/365 per day while long) before 2026-04-17, Delta FUNDING:XAUTUSD after;
  cost 7.31 bps/side (conservative line). Comparison: A+gold vs A, and B+gold (25 ex-ante + gold) vs B; primary on B+gold vs B POST.
- Fixed: full risk budget TV/N like any coin. Neighbors: (a) w_gold <= 0.25 E; (b) realistic cost line 1.18 + 2 bps/side on gold.
- Data: as listed; XAUT contract $4.12 (65 contracts at $1,000 fully long), taker 1 bp verified on `/v2/products`.
- Hypothesis: diversification term (local corr(PAXG, EW nine) 0.14; N_eff 1.50 -> 1.75); trend on gold is inside every multi-asset TSMOM
  study; expected +0.05..+0.15 Sharpe full sample, of which the 2024-25 gold bull is most, hence the pre-bull window condition. Live:
  XAUTUSD, fall back to PAXGUSD if XAUT 30-day median turnover < $10M.

### 6.4 Costs and execution (1 cell)

**COST-2 Contract-space buffer for the daily bot book** (absorbs COST-1) | target D, whole contracts | class II (metric: fees/yr down >= 0.20 pp vs round-nearest band 0; orders/yr down >= 30 %) | priority 1 | small
- Rule: at each 00:05 UTC rebalance u_i = w_i E/(P_i cv_i) (unrounded contracts from unchanged `target_weights`); B_i = max(0.10 |u_i|, 0.75)
  contracts; u_i == 0 -> close; held_i in [u_i - B_i, u_i + B_i] -> no trade; else trade to the integer inside the band nearest held_i
  (none -> round(u_i)). `sim.simulate(buffer=(0.10, 0.75), capital=...)` exists.
- Fixed: b = 0.10 (pysystemtrade default), m = 0.75 (the only floor whose position-path effect never went negative in `cost2_diag_out.txt`).
- Neighbors: m = 1.0; b = 0.25; COST-1 cells B_i = F x A_i with A_i = (TV/N)/max(sigma_i, 0.05) x E/(P_i cv_i), F in {0.10, 0.20}.
- Data: A and C with Delta contract values at $1,000 / $2,500 / $5,000; B unrounded information only. Paired comparison vs round-nearest
  band 0 (the live paper book's setting) AND vs band 0.10 rounded (d2_checks 2c), both at the same capital; windows FULL, 2022-23, 2025-26.
- Hypothesis: cost term only: fees -0.25..-0.45 pp/yr (+0.01..+0.03 SR), orders -35..-40 %; the position-path effect (+-0.15 by sub-period)
  is hysteresis on BTC/BNB, not edge: acceptance requires |Delta| <= 0.08 with the CI containing 0 on every window and capital, and the
  share of coin-days with B_i > A_i/3 is printed (if > 20 % at $1,000 the memo states the rule as a signal change for those coins).

### 6.5 Overlays (2 cells)

**OVL-2 Funding tail cut-out** | target both | class I (extras: maxDD not worse, CAGR not lower by > 1 pp, >= 8 distinct binding episodes (coin x contiguous run >= 3 days) outside 2021 on B) | priority 2 | trivial
- Rule: F_i(d) = 365 x mean over the last 30 calendar days of the daily funding fraction paid by longs (Binance archive summed per day before
  2024-04; Delta FUNDING:<sym>, three 8 h settlements per day, after; the W book reads it at the Monday 00:00 decision). If F_i(d) > 0.30
  then w_i = 0 for the next holding period; otherwise unchanged; never raises a weight.
- Fixed: W = 30 d, 30 %/yr. Declared secondary cell (reported, never chosen): W = 14 d, 40 %. Neighbors: (30 d, 40 %) and the secondary.
- Data: B (25c npz carries funding for all 25 coins: the untouched decisive panel), A, C.
- Hypothesis: cost term (funding paid in the > 30-50 %/yr buckets is 9-22 bps/day) with a weak crowding term; the 9-coin grid's cells were
  picked in-sample (7 of 14 below baseline), so the test is B; expected +0.0..+0.1 Sharpe post-2021, mostly lower funding paid.
  If adopted, `trend_paper.py --orders-only` prints F_i per coin for the hand book.

**OVL-3 Fast-exit veto (conditional on D-1)** | target both | class I (OVL-2's form plus flips/yr and fees/yr reported) | priority 3 | trivial
- Rule: w_i = 0 whenever P_t/P_{t-20} <= 1 and the rule would otherwise hold 1/3 (Correction state); entries and the 60/120 sleeves unchanged.
  Runs only if D-1's OVL-3 condition holds (Correction-state next-7-day return <= 0, t < 0, on the 24-coin panel in both windows).
- Fixed: 20-day return, no EMA, no 10-day. Neighbors: none by design (one pre-registered line; robustness = both B windows and both cadences).
- Data: A, B, C. Hypothesis: the Correction state is 11.8 % of coin-days at 1/3 weight (~4 % of coin-day weight); GHM's multi-asset result
  says the weight should be between 0 and 1, never 0; expected negative unless D-1 fires.

### 6.6 Timing and cadence (3 cells)

**TIME-1 Tranched daily-executed book (K = 7)** | target T, judged vs W | class I vs W (extras: Sharpe within 0.03 of the seven-weekday mean on each panel; orders/yr <= 350 at $1,000; turnover <= W's) | priority 1 | trivial
- Rule: daily at the 00:00 UTC close w_t = target_weights(looks (20, 60, 120), vol 60, TV 0.25, long-only, cap 1x); ws_t = mean(w_t, ..., w_{t-6});
  one netted account position n_i = round(ws_i E/(P_i cv_i)) (unrounded line: ws_i); 10 % band on |target - held| vs |target|; taker at 00:05.
- Fixed: K = 7 (one tranche per weekday; Hoffstein RTL ~ 1/N). Neighbors: K = 3, K = 5; TIME-5 line x_t = x_{t-1} + (1/4)(w_t - x_{t-1}) with
  "min 1 contract toward target when the rounded gap >= 1"; TIME-2 line (smooth the signal, not the weight: s_i,t = (1/7) sum_{j<7} (1/3)
  sum_L sign(P_{t-j}/P_{t-j-L} - 1), signal = max(s, 0), vol unsmoothed). Control: K = 1 = D at TV 0.25 band 10.
- Data: A, B, C; unrounded and $1,000 / $2,500 / $5,000.
- Hypothesis: moves the timing-luck term only (mean return unchanged, variance of the outcome down, DD down 2-3 pp); the smoke
  (`phase2/tranche7_smoke.json`, unrounded, seven separately-costed books) gave A-weekly 1.25 vs 1.12, B 0.91 vs 0.81, C 1.00 vs 0.70 at
  unchanged turnover. Expected vs W: +0.10..+0.13 on A (of which ~0.10 is the design weekday being the worst of seven and ~0.02 variance
  reduction; the memo must print both); at $1,000 rounding gates the 1/7 steps so the rounded gain may be inside T5's +-0.08.

**TIME-3 Decision-hour tranche (six H-aligned closes)** | target both | class I (extras: Sharpe within 0.03 of the six-hour mean on A; no increase in orders/yr; no loss on C) | priority 2 | small
- Rule: at each 00:00 UTC decision, for H in {0, 4, 8, 12, 16, 20} build C^H from hourly closes (for H > 0 the previous day's H:00 bar, no
  look-ahead); s^H_i = (1/3) sum_L sign(C^H_t/C^H_{t-L} - 1); sig_i = max(mean_H s^H_i, 0); vol from the 00:00 closes; size, round, band,
  execute at 00:05 as now (zero extra executions).
- Fixed: six 4-hourly offsets (T3k's set). Neighbors: all 24 hourly offsets; three offsets {0, 8, 16}.
- Data: hourly for A (cached), C (cached), B (download the 15 extras' 1h monthly zips; if the download fails B is run on daily closes and
  the cell is reported as A/C only, which is pre-registered here as the fallback).
- Hypothesis: timing-luck term on the hour axis (T3k dispersion 0.06 sd; design lowest of six); expected +0.03..+0.09 on A-weekly vs 1.12,
  ~+0.00 vs the six-hour mean; orders unchanged. Run after TIME-1; can stack (COMBO-C).

**TIME-4 Two-session hand book (Monday and Thursday)** | target W, whole contracts | class I vs W (extras: A-weekly >= 1.17; C >= 0.80; orders/yr <= 220 at $1,000; realized gross within 10 % of the one-session book) | priority 2 | trivial
- Rule: one aggregate position; on Monday 00:05 and Thursday 00:05 UTC compute target_t from that day's 00:00 close (TV 0.25) and trade
  d = target - held with q = sign(d) x max(1, ceil(0.5 |d|)) contracts when |d| >= 1, subject to the 10 % band on the full gap; closes
  always trade in full. (The Thursday session uses the Wednesday candle.)
- Fixed: K = 2, 3/4-day spacing, half-gap with a 1-contract minimum (fixes round(0.5) = 0). Neighbors: Mon/Fri spacing; full-gap trade on
  both sessions (q = d).
- Data: A, B, C; unrounded and $1,000 / $2,500 / $5,000. Hypothesis: half the RTL removed (K = 2) for one extra hand session; expected
  +0.05..+0.08 on A vs W, DD -1..-2 pp, orders +10..+15 %.

### 6.7 Combinations the literature says stack (3 cells, run regardless of the components' results)

**COMBO-A Operational stack: TIME-1 + SZ-1 + COST-2** | target T, whole contracts | class I vs W AND Sharpe >= TIME-1 alone - 0.03 on B POST AND orders/yr <= TIME-1 alone x 0.85 at $1,000 | priority 1 | small
- Rule: TIME-1's K = 7 tranche of daily targets computed with SZ-1's EWMA-COM60 vol, executed through COST-2's contract buffer (b = 0.10,
  m = 0.75) instead of the 10 % band on the rounded lines; the unrounded line uses the 10 % band. TV 0.25, cap 1x.
- Neighbors: TIME-1 + SZ-1 (band 10); TIME-1 + COST-2 (CC60 vol).
- Data: A, B, C; $1,000 / $2,500 / $5,000. Hypothesis: the three order-count reductions are on different axes (timing luck, vol-estimate
  noise, contract granularity) so they should add; expected Sharpe = TIME-1's within 0.03, orders/yr -30..-50 % vs TIME-1 alone.

**COMBO-B Continuous signal + better vol + buffer: SIG-2 + SZ-1 + COST-2** | target D, whole contracts | class I/II (II metric: funding/yr down >= 25 % AND orders/yr down >= 30 % vs D round-nearest) | priority 3 | small
- Rule: SIG-2's clip(z/1, 0, 1) ensemble sized with SZ-1's vol and executed through COST-2's buffer, TV 0.40, cap 2x (the B&K/Carver stack:
  continuous forecast, smoother vol, position buffering).
- Neighbors: SIG-2 + SZ-1 (no buffer); SIG-2 + COST-2 (CC60 vol).
- Data: A, B, C. Hypothesis: all three move the cost term the same way; the signal term is expected flat-to-down (SIG-2); expected
  Sharpe -0.05..+0.02, funding -30 %, orders -50 %.

**COMBO-C Two luck axes: TIME-1 + TIME-3** | target T | class I vs W AND Delta vs TIME-1 alone > 0 on B POST with no panel losing | priority 2 | small
- Rule: TIME-1's K = 7 tranche applied to daily targets whose signal is TIME-3's six-hour average; vol from the 00:00 closes; TV 0.25.
- Neighbors: K = 7 with three hours {0, 8, 16}; K = 5 with six hours.
- Data: as TIME-1 and TIME-3. Hypothesis: weekday and hour luck are different axes (T3b and T3k dispersions are each ~0.2); expected
  +0.00..+0.03 over TIME-1 alone with lower outcome variance. Adopt over TIME-1 only on the stated condition, else TIME-1 alone.

## 7. Run order, budget, outputs

1. T0 reproduction and the three reference lines (section 1) on A, B, C; freeze hash.
2. D-0 loader + cohort gate; D-1 diagnostic (decides SIG-9 / OVL-3).
3. Priority 1: TIME-1, SZ-1, COST-2, UNI-2, COMBO-A.
4. Priority 2: SIG-2, SIG-1B, SIG-3a, SIG-3b, SIG-4, SIG-10, SZ-3, SZ-13, UNI-1, OVL-2, TIME-3, TIME-4, COMBO-C.
5. Priority 3 and conditionals: SIG-7A, SZ-6b, SIG-9, SIG-11, OVL-3, COMBO-B.
Each cell = primary + its neighbors on A/B/C x daily/weekly (or the target cadence) x FULL/POST/H1/H2, unrounded, plus the whole-contract
lines where stated: roughly 24 x (1 + 2-3) x 6 panel-cadence runs, all under a minute each in the numpy harness. Outputs:
`phase2/<id>.json`, `phase2/<id>_<neighbor>.json`, `phase2/summary.md` (one line per cell per cadence with Delta, CI, P, sd_Delta,
1.98 x sd_Delta, class verdict), and the memo `cex-mm/artifacts/research/2026-10-XX-trend-phase2.md` in Phase 3. Variants are registered in
`tools2/variants.py` below the marker line, named by the ids above, nothing else is added.

## 8. Deliberately not pursued (one line each)

- SIG-5 Sepp-Lucic European LS(250,20): its own verified source has it weakest of three (0.47 vs 0.55) with 2-3x turnover; linear-filter mechanism already covered by SIG-2/SIG-3; 750-day warm-up removes C.
- SIG-6 Baz MACD trio: zero-cost futures evidence below sign (1.11 vs 1.39); the Gaussian response cuts exposure in the strongest trends; faster than T3d's losing set.
- SIG-8 14/28-day votes: 81 % agreement with the 20-day sign; (10,30,60) already on file at 1.08 / 0.72 in 2024-26.
- SIG-12 skip-k signal lag: a control with an expected negative in crypto; T3k +24 h already within noise.
- SZ-2 CC30 / EWMA span 32-35: T3e (+0.04, in-sample) and `phase2/vol_ewma32.json` (null on A/B, -0.13..-0.16 on C, turnover +8-11 %).
- SZ-4 fractional Kelly for TV: Sharpe-neutral by construction (T3a); a memo sentence, not a backtest.
- SZ-5 vol floor: the low-vol-precedes-crash mechanism is absent locally (Q1 relative vol next-7d SR 0.38); binds only on BTC/BNB.
- SZ-7 ex-ante portfolio covariance targeting: run as `phase2/portfolio_vol.json`, failed on A and C (DD -30.6 %, turnover x2.3); SZ-6b is its bounded form.
- SZ-8 / SZ-9 own-P&L vol targeting (Barroso-Santa-Clara, Moreira-Muir): a long/flat book's own vol measures participation, not risk; both legs map to tested failures (T3j, d2_checks2, portfolio_vol).
- SZ-10 semi-deviation: no return-vol asymmetry locally (-0.141 vs -0.143); ~sqrt(2) noisier.
- SZ-11 / SZ-12 conditional vol targeting and vol attenuation: the rejected realized-vol filter family (T3j 1.02/1.00; d3 1.18/1.09) in continuous clothes; local relative-vol quintiles non-monotone.
- SZ-14 greedy integer optimiser: the prize is inside T5's +-0.08 rounding noise; cannot be hand-executed.
- SZ-15 proportional funding penalty: tested, harmful on both samples and both books (1.25 -> 1.08/1.20; Delta 0.99 -> 0.54/0.84).
- SZ-16 Parkinson / GK / YZ vol: locally noisier than CC60 with 37-41 % level bias; Delta loader has O = H = L = C.
- UNI-3 listing-age floor: zero effect on the live nine; lives inside UNI-1 as neighbor (a).
- UNI-4 liquidity floor $2M/$0.5M: a universe change by the back door (fails 4-5 of the nine on Delta's last 365 days) for a slippage prize T3l bounds at <= 0.02 Sharpe; the exit rule already exists in resource/07.
- UNI-5 capital-aware N: restates the contract test; lives inside UNI-1 as its feasibility gate.
- UNI-6 correlation-aware selection: the only low-correlation names (TRX, XMR, ZEC) are untradeable on Delta at this size; diversification belongs to sizing (SZ-6b).
- UNI-7 funding eligibility gate: `sim/funding_grid.txt` cells below 30 % and all 60-day cells lose; OVL-2 on B closes the funding question.
- COST-1 Carver proportional buffer: collapses to rounding on BTC/BNB/ETH below $2,500; lives inside COST-2 as neighbor cells.
- COST-3 weekly-book contract buffer: its own sim fails its own acceptance (Delta $1,000 -0.07); the weekly fee line is 0.25 %/yr = 0.02 SR.
- COST-4 passive post-only with taker fallback: fee arithmetic on BTC/ETH/XRP worth ~7-11 bps/yr; not testable on candles; a live A/B item needing a real order path and the user's go-ahead (section 9).
- COST-5 referral tier / measured TAKER_BPS: an operational checklist item (confirm the tier, read commission from the first fills); re-run cost lines only if the measured taker fee differs from 5.31 by > 1 bp.
- COST-6 cost speed limit: a heuristic that passes every cadence on the repo's numbers; T1 measured cadence directly. Residue kept: fee_SR and funding_SR in the output line.
- OVL-1 market-drawdown de-risking: the "crash state" is on 73 % of days; the rule already holds 0.128x there; a TV cut plus the 200-day timing T3j found neutral.
- OVL-4 Daniel-Moskowitz bear+high-vol: fires on 0.8 % of days; the mechanism needs a short leg.
- OVL-5 correlation-spike reduce-only: SZ-6b carries the family's one correlation trial; top-rho quintile is not a low-return state locally.
- OVL-6 basket-trend gate: Jaccard 0.64 with the tested BTC<200d state; rule holds 0.044x there; bites only the idiosyncratic alt trends that made the return.
- OVL-7 BTC-dominance / altseason gate: a permanent BTC tilt (T3f: BTC-only 0.85); relative strength in disguise; no backtest exists anywhere.
- TIME-2 signal smoothing, TIME-5 partial adjustment: not separate ideas; run as labelled lines inside TIME-1's neighborhood, never selected over K = 7.
- TIME-6 asymmetric cadence: no study; the strategy's best days follow its worst (next-3-day +0.87 % / +1.28 % after a < -3 % day), which the rule would under-hold.
- TIME-7 post-crash cool-down: measured on the existing series: costs 0.03-0.06 Sharpe before costs, DD no better on W.
- DATA-2 per-coin half-spread: inside T3l's tested [2, 10] bps envelope (-0.07 %/yr daily); already the Gate A / kill-3 statistic.
- Everything on the task's rejected list (market making, option selling, carry, funding as a signal, ML/stacking, on-chain, sentiment, intraday seasonality, cross-sectional momentum, lead-lag, events, liquidation fades, shorts, BTC 200-day or vol regime filters, drawdown de-leveraging, day stops, per-position stops, BTC-only universes, single lookback, no vol targeting, choosing the weekday/hour) stays rejected; none is re-run.

## 9. Items handed to Phase 3 without a Phase 2 cell

- COST-4 live A/B (BTC/ETH/XRP post-only at the touch, H = 4 h, taker fallback on stale/frozen book per BookWatch/FrozenBookWatch),
  only after a real order path exists for the trend book and only with the user's explicit go-ahead; >= 100 orders per coin, alternating days.
- COST-5 fee-tier confirmation before the first real fill; TAKER_BPS set from the first nine 1-contract fills.
- `--band 0.10` on the daily paper book (T3c, d2_checks 2c): no new evidence needed, still needs the user's go-ahead; not part of Phase 2.

## 10. Amendments

(none)

### A-2026-10-21 (before run 1; critic's findings, decided by the lead engineer; nothing in sections 1-9 is changed)

- **A1 after-tax reporting lines** (critic 1): every `phase2/<id>.json` and summary line also carries after-tax CAGR under (a) per-coin
  realized-segment VDA 30 % on gross gains with no loss set-off (average-cost realization when a coin's units fall), (b) per-coin-day
  VDA 30 % on positive coin-days, no set-off, (c) slab 30 % on the net annual return. Reporting only; no decision rule changes.
- **A2 diagnostic D-3, decision-to-fill drift** (critic 2): Binance 5 m klines for the nine, 2024-01..2026-09; signed 00:00 -> 00:05 UTC
  return conditional on the rule's trade direction that day (buy / sell / none), mean and NW t-stat; if |mean| > 2 bps on buys or sells
  the cost line of every daily-executed cell is re-run with that drift added. Not a trial.
- **A3 haircut N_eff** (critic 3): the summary reports both 1.98 x sd_Delta (N = 26 after A7/A8) and the N_eff multiplier with
  N_eff = 26 + 4 Phase-1 smoke cells (sig_continuous, vol_ewma32, portfolio_vol, tranche7_smoke) + 60 prior ledger cells on panel A
  (2026-10-13 T-sections) = 90 (multiplier 2.37). Class I condition 1 is judged on the N_eff multiplier. A column "primary parameter seen
  in a local run" is added (COST-2 m, SIG-2 d, OVL-2 window/threshold, TIME-1 K: yes).
- **A4 Phase 3 pass rule** (critic 4): a third paper book passes on implementation fidelity only, over 8 weeks: (a) paper equity vs its own
  model line within the T5 rounding bound (USD 8 per month at $1,000), (b) orders/yr, fees/yr and funding/yr within 20 % of the variant's
  $1,000 whole-contract backtest line, (c) every scheduled rebalance executed. Equity curves are not compared across books for selection.
- **A5 intraday-low equity and on-venue leverage** (critic 5): for every variant on A and C, worst intraday equity from positions x hourly
  lows (liq_check construction) on FULL and on 2025-10-10/11; max gross and the share of days with gross > 0.6x (resource/07's 2x on 30 %
  of capital). Reporting; a variant whose max gross exceeds the baseline's by > 0.2x is flagged in the memo.
- **A6 Delta-funding stress line** (critic 6): A and B re-run once with per-coin-day funding = max(Binance, 0.01 %/8 h x 3) for BTC, ETH,
  BNB, LTC, BCH and Binance x the 2025-26 Delta/Binance mean ratio for the other coins (from `research2/funding_summary.json`); Sharpe,
  CAGR and funding/yr reported next to the Binance-funding line. Class I/II condition 2 must also hold on this line for any variant
  that raises average exposure by more than 10 %.
- **A7 new cell SZ-17 hourly realized-variance vol** (critic 7): RV_d = sum of the 24 hourly squared log returns of day d (Binance 1 h for
  A, Delta 1 h for C; B falls back to A's nine with the cell reported as A/C only); s_t = (60/61) s_{t-1} + (1/61) RV_d; vol = sqrt(365 s_t);
  rest as SZ-1. Class II (orders/yr down >= 15 % on the rounded lines, Sharpe within -0.03, matched-vol DD and worst 7-day no worse).
  Neighbors: COM 30 and COM 90.
- **A8 new cell SIG-13 trend on the funding-adjusted total-return index** (critic 8): TR_t = TR_{t-1} (P_t/P_{t-1})(1 - f_t), f_t the daily
  funding fraction paid by longs; the sign ensemble is computed on TR instead of P; sizing unchanged. Class I; extra: funding/yr not
  higher. Neighbors: the adjustment on the 120-day sleeve only; funding x 2.
- **A9 D-2 open-interest diagnostic** (critic 9): deferred to the annual review; not run in Phase 2 (low prior, a new data pipeline, and
  the family was dropped from the Phase 1 sweep for capacity). Recorded here so it is not forgotten.
- **A10 diagnostic D-4, MARK closes on panel C** (critic 10): panel C re-run on Delta MARK:<sym> daily closes where available; sign-agreement
  per sleeve and the C Sharpe on both series reported. The third book, if any, computes its signal from the series this diagnostic
  favours; the running books are not changed.
- Primary cells are now 26 (24 + SZ-17 + SIG-13).
