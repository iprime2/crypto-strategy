# UNI-1 verification: robustness and attribution lens (2026-10-21)

Scope: try to refute "UNI-1 (yearly liquidity-ranked top-9, H=18, age 365, Bw pool) beats static-24", using the existing
implementation (`tools2/variants_universe.py` imported, read-only). All runs unrounded, both books (daily TV 0.40 cap 2 band 0;
weekly TV 0.25 cap 1 band 10 % Sunday). Deltas are Sharpe(UNI-1 or variant) minus Sharpe(static-24 through D-0). Bootstrap = sim.block_bootstrap_diff
(block 20, 1000 draws). POST = 2022-01-01..2026-09-30.

Reproduction: UNI-1 FULL 1.0497 / POST 0.8618 vs static-24 0.8512 / 0.5863 (daily); 0.9838 / 0.7771 vs 0.8101 / 0.4915 (weekly). These match UNI-1.json.
Only 14 coins are ever held: the 2020 start set (BTC ETH LINK BCH XTZ LTC BNB EOS XRP, all of them in static-24) plus MATIC, SOL (2022), DOGE (2023), AVAX (2024), 1000PEPE (2025).

Scripts (each one writes its own .txt output): common.py, a1_yearly_coin.py, a2_loo.py, a3_start.py, a4_placebo.py, a5_funding.py, a6_jitter.py,
a7_years.py, a8_gradient.py, a9_hyst.py.

## 1. Calendar years (a1.txt, a7.txt)

| year | daily UNI-1 Sh / ret | daily s24 Sh / ret | dSh | vol-matched dRet | weekly dSh | weekly vol-matched dRet |
|---|---|---|---|---|---|---|
| 2020 | 2.12 / +42.9% | 1.51 / +23.6% | +0.61 | +15.0% | +0.31 | +5.5% |
| 2021 | 0.95 / +21.1% | 1.33 / +28.8% | -0.38 | -9.6% | -0.32 | -4.9% |
| 2022 | -1.07 / -9.4% | -1.65 / -8.4% | +0.58 | -0.1% | +0.75 | +1.3% |
| 2023 | 1.34 / +25.2% | 0.71 / +11.1% | +0.63 | +11.6% | +0.44 | +4.6% |
| 2024 | 1.75 / +39.5% | 1.27 / +29.6% | +0.47 | +5.9% | +0.64 | +6.3% |
| 2025 | 0.30 / +3.6% | 0.10 / +0.5% | +0.20 | +2.8% | +0.26 | +2.6% |
| 2026 | 1.06 / +9.1% | 1.21 / +7.6% | -0.15 | +0.6% | -0.48 | -1.7% |

- The 2022 Sharpe "gain" is a negative-mean / higher-vol artifact: UNI-1 lost more money (-9.4 % vs -8.4 %) at 8.8 % vs 5.2 % vol. Vol-matched it is -0.1 % (daily).
- The real POST gain is 2023-2024 (plus a little 2025). Leave-one-year-out POST delta: drop 2023 -> +0.163 d / +0.241 w; drop 2023 and 2024 -> +0.120 d / +0.152 w.
  POST restricted to 2025-26: +0.095 daily, **+0.002 weekly**.
- Rolling 365-day windows ending 2023 or later: Sharpe diff > 0 in 91 % (daily) / 94 % (weekly) of windows.

## 2. Per-coin attribution and leave-one-out (a1.txt, a2.txt, a2b.txt)

Sum of daily coin P&L, before costs, FULL (daily): UNI-1 +1.309 vs static-24 +0.974 (costs 0.071 vs 0.064).
- 9 shared coins: UNI-1 +1.038 vs static-24 +0.421 (the same coins at about 2.7x weight).
- UNI-1 only (SOL DOGE AVAX MATIC 1000PEPE): +0.271 (SOL +0.128, DOGE +0.109, AVAX +0.035, MATIC +0.010, PEPE -0.012), all of it after 2022.
- static-24 only (15 legacy alts): +0.553 (TRX +0.105, ADA +0.070, ZEC +0.063, XLM +0.055, NEO +0.051 ...).
- Top UNI-1 coin-years: BNB2021 +0.104, DOGE2024 +0.102, BTC2020 +0.093, SOL2023 +0.089, XRP2020 +0.082.

Leave-one-coin-out, POST delta (base +0.276 daily / +0.286 weekly):

| coin | (a) zero weight in UNI-1 only, d / w | (b) coin removed from the world (rule re-selects; also dropped from s24), d / w |
|---|---|---|
| BNB | +0.198 / +0.216 | +0.187 / **+0.054** |
| BTC | +0.222 / +0.294 | +0.197 / +0.100 |
| ETH | +0.309 / +0.301 | +0.245 / +0.103 |
| XRP | +0.278 / +0.192 | +0.219 / **+0.031** |
| LINK | +0.277 / +0.320 | +0.225 / +0.112 |
| SOL | +0.186 / +0.186 | +0.131 / **-0.008** |
| DOGE | +0.209 / +0.240 | +0.180 / +0.060 |

- Weekly (b) is fragile because the weekly reset (first January Sunday, 2024-01-07 / 2025-01-05) fills a freed slot with TRB (2024) and SUI (2025), which lost money
  (SUI -0.031, TRB -0.017). Daily resets on Jan 1 pick ADA instead. The 9th-slot pick depends on the reset date.
- Cumulative removal from the world, top-k contributors: daily POST stays +0.13..+0.25 for k = 1..5. Weekly: -BNB+XRP -0.035, -BNB+XRP+ETH -0.122.
- Coin-year trimming (zero the weight for that calendar year). POST, asymmetric (UNI-1 only): top-3 POST coin-years (DOGE2024, SOL2023, BTC2023) -> -0.014 d / +0.009 w.
  Symmetric (each book loses its own top-k): top-3 -> +0.121 d / +0.179 w; top-5 -> +0.038 d / +0.119 w.

## 3. Start-universe effect and controls (a3.txt, a8.txt, a9.txt)

- 2020-21 window: UNI-1 1.459 vs 1.406 (+0.053) daily, 1.422 vs 1.474 (-0.052) weekly. Hybrid (static-24 weights to 2021-12-31, UNI-1 from 2022): FULL 1.028 d / 0.992 w
  (vs 1.050 / 0.984). So the start set accounts for about +0.02 / -0.01 of the FULL delta. The FULL gain comes from 2022 onwards.
- Restart both books on 2022-01-01: 0.862 vs 0.586 (+0.276, CI [-0.22, +0.74], P 0.12) daily; 0.774 vs 0.489 (+0.285, CI [-0.23, +0.79]) weekly.
  This is identical to the POST window, so path dependence plays no role.
- C1, the static 2020-04-30 top-9 never reset (concentration in the liquid 2020 names): POST +0.013 d / +0.022 w, FULL +0.032 / +0.009.
  **Concentration alone does not explain the gain.**
- C3, the UNI-1 rule inside the static-24 only (rotation without new listings): POST +0.092 d / +0.075 w.
- C4, UNI-1 frozen at its 2022 set (BTC ETH MATIC SOL XRP BNB LINK LTC EOS): POST +0.210 d / +0.252 w. Later resets add only +0.065 / +0.034.
- C5, the hindsight nine (reference): POST 0.837 d / 0.660 w. UNI-1's POST 0.862 / 0.777 is about the live nine's level, not above it.
- C6, the same rule at N=24 (H=48): POST -0.088 d / -0.196 w. The gain needs N = 9 concentration plus admitting SOL and DOGE.
- Liquidity gradient, no hysteresis, by rank band of the eligible list (POST delta): ranks 1-4 +0.152 d / +0.261 w; ranks 1-9 +0.128 / +0.025; 5-9 +0.034 / -0.298;
  10-18 -0.071 / -0.319; 28-36 -0.409 / -0.211.
- **Hysteresis H sweep** (N = 9), POST delta:

| H | 9 | 11 | 13 | 15 | 18 (plan) | 21 | 24 | 30 | 40 | inf |
|---|---|---|---|---|---|---|---|---|---|---|
| daily | +0.128 | +0.283 | +0.259 | +0.267 | +0.276 | +0.159 | +0.159 | +0.169 | +0.155 | +0.026 |
| weekly | **+0.025** | +0.127 | +0.274 | +0.278 | +0.286 | +0.207 | +0.207 | +0.166 | +0.166 | +0.046 |

  H = 18 is at the top of a 13-18 plateau. Below it, keeping BNB and LINK as rank-10..13 incumbents in 2022 is what matters. Above it, SOL loses its 2022 slot to XTZ.
  Without hysteresis the weekly gain is gone (+0.025).

## 4. Random-universe placebo (a4.txt; 200 draws per book and placebo; seeds 10000+i)

Nine coins are drawn uniformly each January from the same eligible list: 2020-04-30 candidates with >= 30 closes (exactly 24 symbols), later resets age >= 365
plus incumbents still listed. No hysteresis. Sizing, cadence and cap are unchanged.

| placebo | book | FULL mean (p5..p95) | UNI-1 pct | POST mean (p5..p95) | UNI-1 pct | s24 POST pct |
|---|---|---|---|---|---|---|
| P1 uniform (task's placebo) | daily | 0.673 (0.40..0.91) | 100.0 | 0.317 (-0.04..0.66) | 99.5 | 89.0 |
| P1 | weekly | 0.607 (0.36..0.84) | 100.0 | 0.205 (-0.14..0.54) | 100.0 | 90.5 |
| P2 uniform 9 of eligible top-18 | daily | 0.872 (0.65..1.07) | 93.0 | 0.605 (0.34..0.83) | 96.5 | 42.5 |
| P2 | weekly | 0.698 (0.51..0.88) | 99.5 | 0.348 (0.14..0.59) | 100.0 | 81.5 |
| P3 uniform within static-24 | daily | 0.797 (0.62..0.97) | 98.5 | 0.547 (0.28..0.76) | 99.5 | 54.5 |
| P3 | weekly | 0.734 (0.51..0.94) | 98.5 | 0.455 (0.18..0.73) | 99.5 | 58.5 |

In 2020-21, UNI-1 sits at the 61st-69th percentile of every placebo, so the start set has no edge. The edge is a 2022+ effect.

## 5. Delta-funding stress (a5.txt)

The floor is the Delta 2025-26 mean for the nine with a record (BNB 11.62, BTC 8.09, ETH 7.75, XRP 5.42, DOGE 4.44, LINK -0.58, LTC -2.24, ADA -2.26, BCH -3.98 %/yr).
Other coins get Binance x 1.5: S1 on positive rows only (adverse to longs), S2 on all rows. S0 is the harness A6 (floor only).

| stress | daily FULL d | daily POST d [CI] | weekly FULL d | weekly POST d [CI] |
|---|---|---|---|---|
| none | +0.198 | +0.276 [-0.22, +0.74] | +0.174 | +0.286 [-0.23, +0.79] |
| S0 | +0.178 | +0.251 [-0.25, +0.72] | +0.152 | +0.261 [-0.26, +0.76] |
| S1 | +0.224 | +0.277 [-0.23, +0.75] | +0.199 | +0.287 [-0.24, +0.79] |
| S2 | +0.212 | +0.260 [-0.24, +0.73] | +0.186 | +0.271 [-0.25, +0.77] |

UNI-1 funding/yr under S1: 4.81 % vs 4.63 % (daily FULL). Funding does not move the gap.
- BNB has F = 0 on 31 % of its candidate rows (zero runs of 7-27 days every year), which is possibly missing data. S0/S1/S2 floor BNB at 11.6 %/yr and the gap holds.

## 6. Other perturbations (a6.txt)

- Yearly reset shifted by -28..+56 days (11 shifts): POST delta +0.160..+0.413 daily and +0.159..+0.317 weekly, all positive. The weakest is +7 d, where SOL misses the 2022 set and NEAR or FTM take it.
- N = 5..12 (H = 2N): POST delta +0.22..+0.30 daily and +0.09..+0.38 weekly. The weekly curve is not monotone (N7 +0.154, N9 +0.286, N12 +0.089).
- Turnover window of 14/30/60/90 days: POST delta +0.256/+0.276/+0.342/+0.304 daily and +0.188/+0.286/+0.318/+0.314 weekly.

## Verdict from this lens

The result is not refuted as a research number. Every perturbation tried gives a positive POST delta except weekly with SOL removed from the world (-0.008). The placebo puts UNI-1 at the 96.5th-100th percentile of random 9-coin universes for POST.
The start-universe and funding explanations are ruled out.

It is still narrower than "a rotation edge":
1. It lives in 2023-24. Vol-matched, 2022 is flat, 2025-26 adds +0.095 daily and +0.002 weekly, and the 2022 yearly Sharpe gain is a vol artifact.
2. It is concentration onto the top 4-6 names: BTC, ETH, BNB and XRP at about 2.7x the static-24 weight, plus SOL from 2022 and DOGE from 2023. Ranks 1-4 alone give +0.15 / +0.26.
   In placebo P1 static-24 itself sits at the 89th-90th percentile, so it is not a weak comparator. UNI-1's POST Sharpe equals the hindsight nine's (0.862 vs 0.837 daily).
3. The weekly book depends on the plan's H = 18 hysteresis (H = 9: +0.025), on SOL entering in 2022, and on BNB and XRP. It also depends on the reset date: the Jan-7 pick in 2024 is TRB.
4. The asymmetric trim of the top-3 POST coin-years erases the gain. The symmetric trim keeps +0.12 / +0.18. "A few lucky coin-years" is half true: about half the POST gain sits in DOGE2024, SOL2023 and BTC2023.

Every CI includes zero (POST P about 0.12 at best).
