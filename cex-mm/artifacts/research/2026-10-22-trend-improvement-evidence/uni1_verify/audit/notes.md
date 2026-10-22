# UNI-1 audit: look-ahead and data (lens: LOOK-AHEAD AND DATA AUDIT)

Date 2026-10-21. Everything here is read-only on tools2/ and research2/. The scripts are in this folder, and each one has a `*_out.txt` with its output.
Reproduction: `base.py` rebuilds UNI-1 through `variants_universe` and gets daily FULL 1.0497 / weekly 0.9838 against static-24 0.8512 / 0.8101.
These match phase2/UNI-1.json exactly.

## Verdict from this lens

- I found no look-ahead and no bad prints, and no delisting or funding effect flatters the result.
- I did find one real data defect. **Fixing it flips UNI-1's daily maxDD clause (R3) from pass to FAIL**:
  - matched-vol maxDD becomes -24.51 % against static-24's -24.01 %. Before the fix it was -24.19 % against -24.74 %.
  - The weekly book still passes R3, by 0.16 pp.
  - The Sharpe uplift survives the fix: POST delta +0.256 daily, +0.273 weekly, P about 0.13.
  - So the cell's PASS (all four clauses on both books) does not hold on corrected data. The Sharpe number itself is not refuted.
- The same fix moves the static-24 gate to 0.860 / 0.819, maxDD -24.0 / -16.75 %. That is the plan's quoted av_runs figures (0.86 / 0.82, -24.1 / -16.8 %).
  This most likely explains the "0.01 gap" in the D-0 precondition note in verdicts.md.

## (1) Look-ahead (trunc.py)

- **Truncation test.** I cut the panel at 30 dates and compared against the full-panel run: 16 random dates plus 14 hand-picked ones (reset rows, the days before resets, 2022-05-10 LUNA, 2022-11-09 FTX, 2024-09-10 MATIC, 2025-05-21 EOS).
  - Cells: UNI-1, UNI-1__quarterly, UNI-1__age121, UNI-1__N12. Cadences: daily and weekly.
  - Rows <= d of U and of W, and the simulated returns dated <= d, came out bit-identical: 240/240.
- **Perturbation test.** Same 30 dates, with every C, Q and F after d replaced by noise (random walks, random zeros and NaNs, random funding): 240/240 identical.
- **Code reading.** `_lives().LAST` uses a backward pass, but only `delisting_events` reads it, which is reporting. W never reads it.
  - AGE, LIFE, pos, d0_clean, rolling_valid(121), vol_cc and sig all use rows <= t.
  - The 30-row turnover median ends at the reset row, which is the decision close.
- **One forward read.** The simulator reads `valid_next[t+1]`: it flattens at close t when row t+1 has no close. On UNI-1 rows that held or targeted a coin this fired 0 times, on both books. On static-24 it fired once (EOS 2025-05-21, weight 0.47 %).
- **Effect on Sharpe: 0.000.**

## (2) Delistings and zombies (delist.py, luna.py)

- UNI-1 only ever held 14 coins: BTC ETH BNB XRP LINK LTC BCH XTZ EOS MATIC SOL DOGE AVAX 1000PEPE.
- Only one delisting falls inside U: MATIC, last Q>0 close 2024-09-04 at 0.3846, followed by 7 zero-volume rows that were correctly removed.
  - Weight held was 0.0000 on both books, so its delisting P&L is 0. MATIC's total P&L was +1.00 % (daily) and +0.73 % (weekly).
- EOS's delisting (2025-05-21) came after EOS had left U at the 2023 reset.
- LUNA, FTT and SRM were never in UNI-1's U.
  - LUNA's age at the 2022-01-01 reset was 339 closes, against the 365 floor. SRM's rank was 48 and FTT's age 214.
  - Zombie rows are removed by the Q>0 rule: FTT 1416, SRM 560, WAVES 841, LUNA 1. LUNA ends at 0.008 on 2022-05-12, as the plan says.
- Held coins had 0 frozen bars with Q>0, and 0 rows below $1M turnover while in U.
- **LUNA in the age-121 neighbor**, which admits it: weight was 0 from 2022-05-01 to 05-12, so it took no crash P&L. LUNA's total was -0.94 % (daily) and -0.57 % (weekly).
  - With LUNA's P&L removed, age121 scores 0.975 instead of 0.966. The neighbor's shortfall comes from LUNA and SAND taking the free slots, which kept SOL out until 2024. LUNA's own losses are a small part of it.
- **Effect on Sharpe: 0.000.**

## (3) Bad prints (prints.py)

- I listed the 20 largest coin-day contributions on each book. All are known real events:
  - XRP 2020-11-21 +40 % and 2023-07-13 +73 %, BNB 2021-02-19 +71 %, BCH 2021-05-05 +53 %, BNB 2022-11-09 -18.5 %, LTC 2021-05-19 -37 %, and others.
  - On every one, O and C lie within [L, H], and the open equals the prior close to within 0.03 %.
  - The four 2024 dates (LINK 12-02, XRP 11-16, BNB 12-03, DOGE 11-10) match Delta India daily returns to within 0.3 pp.
- A scan of the 14 held coins over 2020-26 found no bar with C or O outside [L, H]. The only open-vs-prior-close gaps above 1 % are XRP on 2020-01-16 and 01-18, before the window.
- **Zeroing each book's own top-20 coin-days:**

| Book | UNI-1 | static-24 |
|---|---|---|
| Daily | 0.903 | 0.691 |
| Weekly | 0.765 | 0.644 |

  - The gap gets wider, not narrower. Top-20 sums: UNI-1 +0.228, static +0.199.
- **Effect on Sharpe: 0.000.**

## (4) Funding (funding.py, extra.py)

- All 14 held coins and all 24 static coins have a fundingRate file for every month that has a 1d file. There are 3 funding events per coin-day throughout.
- 391 of the 10,530 held coin-days (3.7 %) on the daily book have F = 0: BNB 337, LINK 41, LTC 13. The weekly book has 420.
  - These are recorded zero rates (`0E-8`, from BNB's 0 % interest component, and LINK/LTC in 2020). They are not missing data, and the static-24 arm holds the same coins on the same days.
- **Stress 1: impute BTC/ETH funding on every F = 0 held day.**
  - Daily: UNI-1 1.0497 → 1.0452, static 0.8512 → 0.8493, so the delta moves -0.003.
  - Weekly: the delta moves -0.003.
- **Stress 2: add +10 %/yr funding to the 5 coins only UNI-1 holds (SOL, MATIC, AVAX, DOGE, 1000PEPE).**
  - Daily 1.031 (-0.019), weekly 0.967 (-0.017).
- Funding paid per year: UNI-1 3.65 % of equity at 0.192 mean gross, against static 3.13 % at 0.167. Per unit of gross it is about the same.
- **Effect on Sharpe: at most -0.02.**

## (5) Archive completeness: the material finding (archive_check.py, patch_gaps.py, patched_clauses.py, patch_attr.py)

- **Silently failed downloads.** `universe/fetch_all.py` returns False on any exception, so a failed download leaves no trace.
  - I compared the cache against the live S3 listing for 179 symbols: the top-30 by turnover at any reset, the static 24, and the age-blocked coins.
  - 3 monthly files were missing from the cache: DASHUSDT-1d-2022-10 (DASH is in the static 24), NMRUSDT 2024-10 and HUSDT 2025-06.
- **Missing rows inside Binance's monthly files.** 2022-02-26..28 and 2022-04-01..02 are missing for 51 symbols. Among them are XRP, LTC and SOL (held by UNI-1) and XRP, LTC, TRX, XLM, ZEC, IOTA and VET (static 24).
  - The daily archive has all 40 of these files (HTTP 200).
  - Each gap restarts the 121-close validity rule, which takes the coin out of the book for about 4 months and shrinks N_t.
- **The fix.** I filled 71 coin-rows from Binance's own daily and monthly files in dl_raw/. The filled rows are continuous: O = prior C.
  - Membership is unchanged.

| Clause | Original | Gap-patched |
|---|---|---|
| Daily R1 FULL | 1.050 vs 0.851 | 1.046 vs 0.860 |
| Daily R2 POST delta | +0.276 [-0.22, +0.74] P 0.12 | +0.256 [-0.24, +0.73] P 0.13 |
| Daily R3 mv maxDD | -24.19 % vs -24.74 % (ok) | -24.51 % vs -24.01 % (**FAIL**) |
| Daily R4 H1 / H2 | +0.182 / +0.231 | +0.161 / +0.231 |
| Weekly R1 FULL | 0.984 vs 0.810 | 0.984 vs 0.819 |
| Weekly R2 POST delta | +0.286 P 0.12 | +0.273 P 0.13 |
| Weekly R3 mv maxDD | -16.62 % vs -16.97 % (ok) | -16.59 % vs -16.75 % (ok) |
| Weekly R4 H1 / H2 | +0.097 / +0.296 | +0.083 / +0.296 |

- **Attribution.**
  - The DASH month alone moves static-24 from 0.851 to 0.859 and maxDD from -24.74 % to -24.08 %.
  - The Feb/Apr rows alone move UNI-1 daily from 1.050 to 1.046 and its raw maxDD from -26.49 % to -26.82 %.
- Raw maxDD was already worse before the fix, and the gap widens: daily -26.8 % vs -24.0 %, weekly -18.2 % vs -16.75 %.
- **Effect.** FULL delta -0.013 daily and -0.009 weekly. POST delta -0.020 daily and -0.013 weekly. The daily book's R3 flips to FAIL.

## (6) Fragility in the turnover data: knife-edge resets (margin.py, qnoise.py, luna.py)

This is not a data error, but small turnover differences move the result a lot.

- **2023-01-01 reset.** Incumbent EOS ranked 19th with $100.1M turnover, against rank-18 WAVES at $102.6M. EOS needed only +2.5 % more turnover to stay.
  - Had EOS stayed, DOGE would not have entered for 2023.
  - Raising EOS's Q by 3 % gives daily 0.990 / POST 0.767 (POST delta +0.181, down from +0.276), and weekly 0.872 / 0.594 (POST delta +0.103, down from +0.286).
- **2024-01-01 reset.** LTC needed +5.3 % (daily) or +3.5 % (weekly) to stay. Raising LTC's Q by 6 % gives daily 1.047 and weekly 1.032.
- **Monte Carlo.** I applied a per-coin, per-year multiplicative error to Q, 100 draws at each size:

| Q error | Daily POST Sharpe, p5 | Weekly POST Sharpe, p5 | Draws with POST <= static |
|---|---|---|---|
| 5 % | 0.767 | 0.594 | 0 % (both books) |
| 10 % | 0.704 | 0.543 | 0 % daily, 1 % weekly |

  - The sign of the uplift survives the noise, but its size can roughly halve or more.
  - All Q values agree with V×C to within ±11 % for every coin ranked <= 30 at a reset.
- **Age floor.** At the 2022-01-01 reset LUNA had 339 closes and SAND 342. S3 confirms both listed in 2021-01, so the ages are correct.
  - Any floor of 335 or less gives daily 0.968 / weekly 0.922 (POST 0.733 / 0.679).
  - Floors 345–400 give 1.050 / 0.984. A floor of 450 gives 1.063 / 1.002.
- **Hysteresis.** H = 17 gives 1.044 / 0.979. H = 19 gives 0.990 / 0.872, because EOS stays in 2023.

## Each issue's effect on Sharpe

- Look-ahead: 0.
- Delistings: 0.
- Bad prints: 0.
- Funding: -0.003 on the delta (imputation stress), -0.02 under a +10 %/yr stress on UNI-only coins.
- Archive gaps: about -0.01 to -0.02 on the delta, and the daily R3 clause flips to fail.
- Turnover knife edges: up to -0.10 (daily) and -0.18 (weekly) on POST Sharpe for a 3 % Q change on one coin. These are fixed parameters of the plan, not errors, but they show how fragile the uplift is.
