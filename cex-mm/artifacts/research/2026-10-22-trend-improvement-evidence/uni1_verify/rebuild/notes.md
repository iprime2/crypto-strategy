# UNI-1 independent rebuild (lens: INDEPENDENT REBUILD)

Written 2026-10-21. I did not open `tools2/variants_universe.py` or `research2/phase2/logs_universe/`. Universe selection, candidacy,
delisting flatten, age floor, hysteresis, start rule and N were written from plan sections 6.0 and 6.3 and the task context.
Reused, read-only: `data.load_binance` (Bw = pool_all.json, 696 coins), `sim.simulate` / `sim.stats` / `sim.block_bootstrap_diff`,
`rules.rolling_valid` / `sig_sign_mean` / `vol_cc` / `baseline_weights` / `decide_weekly`.

Files (all in this directory): `uni1.py` (D-0 trim, universe, weights), `run_base.py`, `run_primary.py`, `run_grid.py` -> `grid.json`,
`robust.py` + `run_robust.py` -> `robust.log` / `robust.json`, `run_final.py` -> `final.log`, `run_extra.py`, `check_members.py`, `check2.py`.

## 1. Static-24 baseline through my D-0 loader (gate)

D-0 as I wrote it: a coin is a candidate on day d only if quote_volume(d) > 0; closes after the last qv > 0 day are removed, so the
simulator flattens at that close at taker cost. Static-24 = `rules.baseline_weights` on Bw.sub(EXANTE24).

| book | FULL Sharpe | vol | maxDD | POST Sharpe | H1 | H2 |
|---|---|---|---|---|---|---|
| daily | **0.8512** | 0.1665 | -0.2474 | 0.5863 | 0.8533 | 0.8491 |
| weekly | **0.8101** | 0.1101 | -0.1697 | 0.4915 | 0.8943 | 0.6897 |

This matches the target 0.851 / 0.810. The only delisting in the 24 is EOS on 2025-05-21. Trimming zombie rows has no effect on the 24.

## 2. UNI-1 matches the reported number exactly under one reading

I ran a grid of 48 readings x cadence (`grid.json`). Exactly one reproduces every reported figure to 4 decimals:

- start set = top-9 crypto candidates by trailing 30-day median quote volume on 2020-04-30, with no history requirement
  (BTC ETH LINK BCH XTZ LTC BNB EOS XRP; several of them have fewer than 121 closes and start trading as they reach 121);
- the age floor of >= 365 closes applies to **entrants only**;
- at each reset, incumbents are ranked within (age-eligible candidates plus incumbents) and kept if their rank is <= 18; free slots go to
  the best-ranked eligible non-members until there are 9;
- hysteresis is checked **only at the yearly reset** (Jan 1 row; for the weekly book, the first-Sunday reset gives the same result);
- a delisted member goes flat and is not replaced;
- N = **members with 121 closes and qv > 0 that day** (the baseline's N), not |U|.

| | FULL Sharpe | vol | maxDD | CAGR | POST Sharpe | ΔPOST vs static-24 [95 % CI], P(Δ<=0) | H1 Δ | H2 Δ | matched-vol TV / maxDD / worst7 |
|---|---|---|---|---|---|---|---|---|---|
| daily, mine | **1.0497** | 0.1837 | -0.2649 | 19.2 % | 0.8618 | +0.2755 [-0.224, +0.741], 0.119 | +0.182 | +0.231 | 0.3625 / -0.2419 / -0.1007 |
| daily, reported | 1.0497 | 0.1837 | -0.2649 | 19.2 % | 0.8618 | +0.2755 [-0.224, +0.741], 0.119 | +0.182 | +0.231 | 0.3625 / -0.2419 / -0.1007 |
| weekly, mine | **0.9838** | 0.1215 | -0.1823 | 11.9 % | 0.7771 | +0.2855 [-0.233, +0.786], 0.123 | +0.097 | +0.296 | 0.2265 / -0.1662 / -0.0688 |
| weekly, reported | 0.9838 | 0.1215 | -0.1823 | 11.9 % | 0.7771 | +0.2855 [-0.233, +0.786], 0.123 | +0.097 | +0.296 | 0.2265 / -0.1662 / -0.0688 |

FULL Sharpe Δ vs static-24: daily +0.199 (CI -0.170..+0.531, P 0.159); weekly +0.174 (CI -0.183..+0.524, P 0.183).

Yearly returns, UNI-1 vs static-24. Daily: 2020 +42.9 % vs +23.6 %, 2021 +21.1 vs +28.8, 2022 -9.4 vs -8.4, 2023 +25.2 vs +11.1,
2024 +39.5 vs +29.6, 2025 +3.6 vs +0.5, 2026 YTD +9.1 vs +7.6. Weekly: 2020 +24.4 vs +16.5, 2021 +16.0 vs +19.3, 2022 -6.2 vs -6.9,
2023 +15.8 vs +9.6, 2024 +23.0 vs +14.5, 2025 +4.4 vs +1.4, 2026 YTD +2.1 vs +3.6.

### Universe membership by year (both books use the same membership)

| from | members | change (incumbent rank at the reset) |
|---|---|---|
| 2020-04-30 | BTC ETH XRP BNB LINK LTC BCH EOS XTZ | start set |
| 2021-01-01 | same | no change. Only BTC, ETH and BCH had >= 365 closes, so no entrant qualified and the incumbents took ranks 1-9 |
| 2022-01-01 | BTC ETH XRP BNB LINK LTC EOS SOL MATIC | out: BCH (rank 29), XTZ (21); in: SOL, MATIC |
| 2023-01-01 | BTC ETH XRP BNB LINK LTC MATIC SOL DOGE | out: EOS (19); in: DOGE |
| 2024-01-01 | BTC ETH XRP BNB LINK MATIC SOL DOGE AVAX | out: LTC (20); in: AVAX. MATIC was delisted on 2024-09-04 (POL rename), so 8 members for the rest of 2024 |
| 2025-01-01 | BTC ETH XRP BNB LINK SOL DOGE AVAX 1000PEPE | in: 1000PEPE |
| 2026-01-01 | same | no change |

One delisting was hit: MATIC on 2024-09-04. The target weight was 0 the day before, so the event had no P&L. LUNA, FTT, SRM and the
other blow-ups never entered under the 365 floor. No excluded tag (metal, xStock, stablecoin, index) ever ranked high enough to matter:
membership is identical with no exclusions.

## 3. Sensitivity to the reading (same data and simulator; static-24 fixed)

Pass line from section 6.3: R1 FULL >= 0.86 daily / 0.82 weekly; R2 ΔPOST >= 0; R3 maxDD no worse than static-24 (mv = at matched vol,
which is the verdict's decision line); R4 both halves not below static-24.

| reading | daily FULL / POST | weekly FULL / POST | R3 mv (d/w) | R3 raw | R4 |
|---|---|---|---|---|---|
| reproduced reading | 1.050 / 0.862 | 0.984 / 0.777 | pass / pass | fail | pass |
| N = \|U\| at the reset (literal "N = \|U\| after the gate") | 1.027 / 0.831 | 0.975 / 0.755 | pass / pass | fail | pass |
| age floor also applies to incumbents (2021 = BTC ETH BCH) | 1.079 / 0.873 | 0.923 / 0.782 | pass / pass | pass | pass |
| continuous hysteresis (rank checked daily, no replacement) | 0.992 / 0.775 | 0.928 / 0.687 | **fail / fail** | fail | pass |
| start set needs 121 closes (BTC ETH BCH in 2020) | 1.120 / 0.873 | 0.999 / 0.782 | pass / pass | pass | pass |
| rank among all ages (young coins push incumbents down) | 1.061 / 0.845 | 0.986 / 0.766 | **fail / fail** | fail | pass |
| reset on the Dec-31 row (the 00:00 Jan 1 decision) | 1.050 / 0.862 | 0.990 / 0.788 | pass / pass | fail | pass |

Readings that combine the age floor on incumbents with continuous hysteresis fall to 0.63-0.87 daily (grid.json). I treat those as
implausible: they empty the universe within the year.

## 4. Fragility of the pre-registered settings (information, not a re-selection)

- **Age floor cliff (LUNA).** LUNA had 339 closes on 2022-01-01 and ranked third by turnover. Any floor from 121 to 330 admits it:
  0.966-0.968 daily, 0.912-0.922 weekly, and the weekly H1 falls below static-24 (R4 fails). Floors of 340-400 give 1.050 / 0.98, 450
  gives 1.063 / 1.002, and 540 gives 0.989 / 0.931. The 365 floor was fixed in advance, but it kept LUNA out by 26 days.
- **Keep-rank.** 9 gives 0.960 / 0.922, 12 gives 1.066 / 1.024, 15 gives 1.044 / 0.979, 18 gives 1.050 / 0.984, 24 or 27 gives
  0.976 / 0.934, and never dropping gives 0.891 / 0.833.
- **N, with keep = 2N.** 6: 1.000 / 0.945; 7: 1.061 / 0.891; 8: 1.027 / 0.878 (weekly R4 fails); 10: 1.032 / 0.975; 11: 1.014 / 0.907;
  12: 1.004 / 0.875 (weekly R4 fails).
- **Median window.** 7 days: 0.952 / 0.855 (R4 fails on both books); 14: 1.037 / 0.975; 20: 0.956 / 0.872; 30 and 45: 1.050 / 0.984;
  60: 1.092 / 1.004; 90: 0.978 / 0.933. A ranking lag of 1-7 days changes nothing; 14 days gives 1.106 / 1.040.
- **Start-set day.** Choosing the start set on any day from 2020-04-23 to 2020-05-07 gives 1.043-1.050 / 0.984-0.990, so this is robust.
- **Reset month** (yearly reset on the 1st of month m). Daily runs 0.958-1.119 and weekly 0.880-1.026, and R1 and R2 pass in all 12
  months. Both books pass all four clauses only in January, March and June. R3 mv fails on at least one book in the other 9 months, and
  July also fails R4.
- **Where the lift comes from.** Freezing the 2020-04-30 top-9 with no resets gives 0.884 / 0.819 (the weekly book fails R1 and R4).
  Applying the UNI-1 rule inside the 24 only gives 0.932 / 0.850. Most of the +0.20 FULL lift therefore comes from rotating into
  post-2020 listings: SOL and MATIC in 2022, DOGE in 2023, AVAX in 2024 and 1000PEPE in 2025.

## 5. Data checks

- Funding is present for every member. BNB's funding is zero on about 31 % of its days (2020-26), the same in both books. SOL's 2022
  funding is -38.6 %/yr, which longs receive; this is a real event (the FTX period).
- Bars are missing on 2022-02-26 to 02-28 and 2022-04-01 to 04-02 for LTC, XRP and others. The simulator flattens and re-enters on
  those days, the same way in both books.
- Largest member daily moves: SOL on 2022-11-09 (23.82 to 11.70, real) and BNB/BCH on 2020-03-12 (before the window).

## Verdict from this lens

**The number is not refuted.** An independent implementation reproduces UNI-1 exactly (1.0497 / 0.9838 FULL; POST 0.8618 / 0.7771;
maxDD -26.49 % / -18.23 %; vol 18.37 % / 12.15 %; bootstrap Δ and CIs identical). The number is the output of one specific reading
(N = valid members; age floor only for entrants; hysteresis only at the reset). The most literal alternative, N = |U|, gives
1.027 / 0.975 (-0.023 / -0.008).

Every defensible reading keeps R1 and R2: daily 0.99-1.12, weekly 0.92-1.00, and ΔPOST from +0.19 to +0.29. The **PASS** verdict is
more fragile than the number. It rests on R3 at matched vol, with margins of 0.55 pp daily and 0.35 pp weekly. That clause fails under
2 of 6 alternative readings, in 9 of 12 alternative reset months, and at keep-rank 12 or 24. A floor 26 days lower would have let LUNA
in, after which R4 fails on the weekly book. None of this changes the pre-registered result, but it supports treating it as a research
number with a CI that includes 0 (P 0.12), not as evidence of an edge.
