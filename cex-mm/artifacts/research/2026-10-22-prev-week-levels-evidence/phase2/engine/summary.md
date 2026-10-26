# Phase 2 run: touch-breakout T on OT and OX (panel A for reference)

Plan `research3/phase2_plan.md`: sha256 now `940a391bac20fd6bc4cc366b38aaca3bf2742d75f1d74f95cec2e07fae2c40f2`, reference `940a391bac20fd6bc4cc366b38aaca3bf2742d75f1d74f95cec2e07fae2c40f2`, MATCH (not edited). Phase 1 definitions from `research3/plan.md`. Code: the reconciled Phase 1 engine from `research3/final/` (copied unchanged to `phase1_copy/`), extended in this folder. Public Binance data only, read from local files. No order placed, no key or .env read, nothing outside `research3/p2/run/` written.

## 1. Verdict (plan section 4, h = 4 h, all four tests on BOTH OT and OX)

| test | OT | OX | A (reference, not gating) |
|---|---|---|---|
| 1. real net (base 14.62) > 0, P(net <= 0) <= 0.01 | 43.85 bps, P 0.0005: **pass** | 7.76 bps, P 0.2455: **fail** | 18.42 bps, P 0.0200: **fail** |
| 2. real - P1 gross > 0, P(diff <= 0) <= 0.01 | 41.98 bps [26.61, 57.62], P 0.0000: **pass** | 19.40 bps [9.82, 28.76], P 0.0000: **pass** | 26.19 bps [17.94, 34.58], P 0.0000: **pass** |
| 3. real net > 0 in both halves | 46.67 / 42.20: **pass** | -1.89 / 18.36: **fail** | 18.97 / 17.90: **pass** |
| 4. real net > 0 on >= 2/3 of coins | 12 of 13 (need 9): **pass** | 10 of 15 (need 10): **pass** | 8 of 9 (need 6): **pass** |
| all four | **pass** | **fail** | **fail** |

**Overall: FAIL.** OT passes all four tests. OX passes tests 2 and 4 and fails tests 1 and 3: its 4 h net is positive but not significant, and its first half is negative. The rule needs both panels, so per plan section 5 the touch-breakout is recorded as rejected with these numbers and gets no further work. The level effect itself (test 2, real - P1 gross > 0 with P <= 0.01) holds on OT, OX and A.

## 2. Reproduction check on Phase 1 panel A (before OT / OX were run)

- The copied engine re-run on A gives 42,876 F rows (real + P1, 3 horizons), against 42,876 in `final/events_A.csv.gz`. Rows only in Phase 1: 0; only here: 0. Max |delta| of gross: 0.0 bps; of level price: 0.0; of exit price: 0.0. Entry and exit times are identical: yes.
- T = -F exactly (bit for bit) on 50,682 of 50,682 rows (real, P1, P3); max |T + F| = 0.0 bps. The same assertion runs on every panel.
- T pooled gross against minus the Phase 1 F gross (`final/results.json`), tolerance 0.01 bps:

| horizon, control | Phase 1 F gross (n) | T gross here (n) | abs(T + F) | within 0.01 bps |
|---|---|---|---|---|
| 1h, real | -17.6505 (2,692) | 17.6505 (2,692) | 0.0 | yes |
| 1h, P1 | -0.8629 (11,600) | 0.8629 (11,600) | 0.0 | yes |
| 4h, real | -33.0395 (2,692) | 33.0395 (2,692) | 0.0 | yes |
| 4h, P1 | -6.8464 (11,600) | 6.8464 (11,600) | 0.0 | yes |
| 24h, real | -62.9339 (2,692) | 62.9339 (2,692) | 0.0 | yes |
| 24h, P1 | -33.6839 (11,600) | 33.6839 (11,600) | 0.0 | yes |

Recorded: T gross at 4 h on A is +33.04 real and +6.85 P1 (Phase 1 F: -33.04 and -6.85), |delta| = 0. Check passed: yes. The bootstrap CI of real - P1 on A, [17.94, 34.58], is the mirror of Phase 1's F interval [-34.58, -17.94].

## 3. Every choice made

**Engine (minimal extension).** `engine.py` vs `phase1_copy/engine.py`: (1) in `level_events`, each F row is followed by a T row with the same entry time, entry price L and exit, and gross = -sgn_F * (exit/L - 1) * 1e4. Multiplying by +-1 is exact, so T gross is the exact negation of F gross. (2) `rinfo['t0']` (touch-bar open time) is recorded, used only to count dropped exits by reason. (3) New `coin_events_p3`, which calls the unchanged `week_levels`, `first_touch` and `level_events`. F, B and S are still computed but not reported; Phase 1 P2 levels are still generated but dropped from Phase 2 outputs. `loaders.py`: new `load_panel_OT` and `load_panel_OX`. `PATCH_B` now points to the read-only `research3/final/data_patch/` because the copy moved. `run.py`: the Phase 1 functions are unchanged and new Phase 2 functions are appended; the entry point is now `main2`. `test_fix_b1.py`: only its relative path to the reconciled loader changed. The Phase 1 tests (test_engine, test_s_ties, test_fix_b1) and the new `test_phase2.py` (T = -F, P3 levels, touch window and coverage, Monday mapping, OX cut) all pass.

**T outcome.** Entry at the first touch of L (Phase 1 rule: first bar with high > L(1 + 0.5 bp) / low < L(1 - 0.5 bp) inside the week), in the breakout direction (long at PWH, short at PWL), filled at L. Exit is the close of the bar that ends h after the touch bar opens, h = 1 h / 4 h / 24 h (the Phase 1 F exit). net_base = gross - 14.62; net_stress = gross - 30.62. hit = share with net_base > 0 (hit_stress also in results.json). The fill at L is kept even when the touch bar gaps or wicks through L (fill optimism; for the adversarial review).

**Weeks and coverage (Phase 1 rules).** A week runs Monday 00:00 to Monday 00:00 UTC. A coin-week is used only if it and the prior week each have >= 99 % of 2,016 bars, counted by open time. Zero-volume flat bars count as bars, as in Phase 1. An exit whose bar is missing (an exchange outage) or falls after the data end is dropped, as in Phase 1. Dropped exits (results.json `dropped_exits`, after_end + missing_bar), 1 h / 4 h / 24 h: OT real 1/1/0, P1 1/2/0, P3 1/0/0; OX real 0/0/0, P1 0/0/0, P3 0/0/0; A real 0/0/0, P1 0/0/0, P3 0/0/0. All OT drops are missing_bar (an exit inside an exchange outage).

**OT.** Each coin starts at its first full prior week (plan section 2): the first candidate week is the first Monday week starting at or after the coin's first bar, plus one week. Candidates run through the week starting 2020-04-20. Data are capped at 2020-05-01 00:00 (the end of the download). The week of 2020-04-20 fails the 99 % rule on all 13 coins (2020-04-25 maintenance), so the last used week is 2020-04-13. Halves by week start: before 2019-01-01, or from it. Used / skipped coin-weeks: 1,060 / 292, all skips data_loss, i.e. Binance-wide outage weeks and the weeks after them ({'listing': 0, 'delisting': 0, 'data_loss': 292}); halves {'H1': 397, 'H2': 663}. These equal the data audit's event_eligible flags: 0 mismatches in 1,352 coin-weeks, 0 bar-count mismatches. The data audit's patches (the off-grid 2018-02-09/10 days replaced from daily files, 4 inserted zero-length bars) are taken as delivered.

**OX.** Weeks 2022-01-03..2026-09-21 for all 15 coins; data capped at 2026-10-01. Halves by week start: before 2024-05-01, or from it. Delisted coins ("stay in until their last full week"): the loader cuts each series after its last bar with volume > 0, so the effective data end is the last traded bar + 5 min. Binance's flat zero-volume placeholder bars after delisting are therefore not used as data. With that cut, the delisting week fails the 99 % rule and exits after the effective end drop. Bars cut: LUNA 183, FTM 7,379, MATIC 2,025, LRC 2,195, others 0. This differs from the data audit's suggestion of a 99 %-traded-bars rule, but on this data the two give exactly the same used coin-weeks: 0 mismatches in 3,705 against the audit's week_coverage.csv under (bars >= 99 % and traded bars >= 99 %, week and prior week). No volume rule is applied to OT, whose 99 % rule stays Phase 1's bar count, so DOGE's and LINK's thin-book zero-volume bars count, as in Phase 1. Used / skipped: 3,251 / 454, all skips delisting ({'listing': 0, 'delisting': 454, 'data_loss': 0}); halves {'H1': 1726, 'H2': 1525}; per coin {'1000SHIB': 247, 'SOL': 247, 'SAND': 247, 'LUNA': 18, 'MANA': 247, 'DOT': 247, 'AVAX': 247, 'FTM': 157, 'MATIC': 139, 'GALA': 247, 'AXS': 247, 'DYDX': 247, 'FIL': 247, 'LRC': 220, 'CRV': 247}. These per-coin counts equal the data audit's table. The audit's stated total of 3,004 is an arithmetic slip: its own per-coin counts sum to 11 x 247 + 18 + 157 + 139 + 220 = 3,251. The coin selection (universe/cache_all plus universe/cache, the data step's documented deviation) is taken as delivered and not redone. No splicing to POL or S.

**A (reference).** Exactly Phase 1: weeks 2020-05-04..2026-09-21, cap 2026-10-01, halves split at 2023-07-01, DOGE's 11 pre-listing weeks counted as skipped (listing). Used / skipped 2,995 / 11.

**P1.** As Phase 1: m in {0.5, 0.75, 1.25, 1.5}, same side, same week, same first-touch and outcome code. P1_in means m < 1 (0.5, 0.75; levels inside last week's range). P1_out means m > 1 (1.25, 1.5; levels beyond it). P1 pooled is the gating control.

**P3 (reported, not gating).** Anchors at Thursday 12:00 UTC: every Thursday from the one before a coin's first candidate Monday to the one inside its last candidate Monday week. For anchor A, the levels are the max high and min low of [A - 168 h, A); O is the first bar's open at or after A; the first touch is searched in [A, A + 168 h). The 99 % coverage rule is applied to both 168 h windows (P3's own coverage). Only the real-level construction is used, not P1 around P3. Each P3 event gets the Monday week containing its touch, which is also its bootstrap cluster and its `week_start` in the events file. **Primary P3 sample:** the touch must lie in a Monday week that is a used coin-week of the same coin. P3 is then scored over the same coin-weeks as the real levels, inside each delisted coin's last full week, and outside outage weeks. **Sensitivity P3_owncov:** P3's own coverage only, touch in any Monday week of the bootstrap set. Counts at 4 h (scored / primary / owncov): OT [933, 860, 866], OX [2919, 2913, 2913], A [2602, 2602, 2602]. P3 anchor weeks used / skipped by P3 coverage: OT 1,066 / 299, OX 3,252 / 468, A 2,994 / 21. The anchor counts include the end anchors whose windows lie outside a coin's data.

**Bootstrap (as Phase 1).** For each panel, one shared set of 2,000 resamples: `default_rng(11).integers(0, W, (2000, W))` over the W Monday weeks with at least one used coin-week (Phase 1's `boot_weights`). Every event is clustered by its Monday week, and a draw's mean is sum(weight x week sums) / sum(weight x week counts). P(net <= 0) and P(diff <= 0) are the shares of draws <= 0; CIs are the 2.5 / 97.5 percentiles. Weeks: OT 111 (2017-08-28..2020-04-13), OX 247, A 334. NaN draws: 0.

**Per coin, Sharpe, years.** The coin threshold is ceil(2n/3): OT 9 of 13, OX 10 of 15, A 6 of 9. The daily Sharpe follows Phase 1: real events, net summed per UTC exit day, zero on days without exits, calendar from the first candidate Monday to the last candidate Monday + 8 days, x sqrt(365); given at base and stress costs. Per-year means use the calendar year of the Monday week start.

**Event files.** `events_<panel>.csv.gz`: T rows only, controls real (PWH/PWL), P1 (P1H_m / P1L_m) and primary P3 (P3H / P3L). The columns are Phase 1's (coin, week_start, level_kind, level_px, pattern, horizon, entry_time, entry_px, exit_time, exit_px, gross_bps) plus net_base. For P3 rows, week_start is the Monday week of the touch, and the anchor is the last Thursday 12:00 at or before entry_time. `events_<panel>_p3owncov.csv.gz` holds the P3 sensitivity sample in the same columns. `coin_weeks_<panel>.csv.gz` and `p3_weeks_<panel>.csv.gz` hold the coverage of every candidate week.

## 4. Results by panel

### OT

Coin-weeks used / skipped: 1,060 / 292 {'listing': 0, 'delisting': 0, 'data_loss': 292}.

| h | control | n | gross | net base | net stress | hit (base) |
|---|---|---|---|---|---|---|
| 1h | real | 887 | 51.79 | 37.17 | 21.17 | 0.5175 |
| 1h | P1 | 3,869 | 18.83 | 4.21 | -11.79 | 0.4487 |
| 1h | P1_in | 2,382 | 15.47 | 0.85 | -15.15 | 0.4303 |
| 1h | P1_out | 1,487 | 24.21 | 9.59 | -6.41 | 0.4781 |
| 1h | P3 | 859 | 35.13 | 20.51 | 4.51 | 0.4808 |
| 1h | P3_owncov | 865 | 36.70 | 22.08 | 6.08 | 0.4832 |
| 4h | real | 887 | 58.47 | 43.85 | 27.85 | 0.5242 |
| 4h | P1 | 3,868 | 16.49 | 1.87 | -14.13 | 0.4672 |
| 4h | P1_in | 2,380 | 9.74 | -4.88 | -20.88 | 0.4508 |
| 4h | P1_out | 1,488 | 27.28 | 12.66 | -3.34 | 0.4933 |
| 4h | P3 | 860 | 25.16 | 10.54 | -5.46 | 0.4849 |
| 4h | P3_owncov | 866 | 27.17 | 12.55 | -3.45 | 0.4873 |
| 24h | real | 888 | 185.15 | 170.53 | 154.53 | 0.5574 |
| 24h | P1 | 3,870 | 122.34 | 107.72 | 91.72 | 0.5158 |
| 24h | P1_in | 2,382 | 110.06 | 95.44 | 79.44 | 0.4983 |
| 24h | P1_out | 1,488 | 142.00 | 127.38 | 111.38 | 0.5437 |
| 24h | P3 | 860 | 102.57 | 87.95 | 71.95 | 0.4802 |
| 24h | P3_owncov | 866 | 103.37 | 88.75 | 72.75 | 0.4815 |

| h | real net base [95 % CI], P(net <= 0) | real net stress, P(<= 0) | real - P1 [CI], P | real - P1_in, P | real - P1_out, P | real - P3 [CI], P | real - P3_owncov, P |
|---|---|---|---|---|---|---|---|
| 1h | 37.17 [15.76, 59.88], 0.0000 | 21.17, 0.0260 | 32.96 [16.11, 50.43], 0.0000 | 36.32, 0.0000 | 27.58, 0.0105 | 16.66 [-8.03, 39.77], 0.0865 | 15.09, 0.1070 |
| 4h | 43.85 [15.98, 72.98], 0.0005 | 27.85, 0.0255 | 41.98 [26.61, 57.62], 0.0000 | 48.73, 0.0000 | 31.19, 0.0010 | 33.31 [2.63, 64.38], 0.0155 | 31.30, 0.0220 |
| 24h | 170.53 [88.35, 253.54], 0.0000 | 154.53, 0.0000 | 62.81 [31.08, 99.14], 0.0000 | 75.10, 0.0015 | 43.15, 0.0105 | 82.58 [5.21, 163.86], 0.0175 | 81.78, 0.0185 |

| h | half | n | gross | net base | net stress | P1 gross | real - P1 | real - P3 |
|---|---|---|---|---|---|---|---|---|
| 1h | H1 2017-08..2018-12 | 327 | 56.50 | 41.88 | 25.88 | 11.73 | 44.77 | 14.91 |
| 1h | H2 2019-01..2020-04 | 560 | 49.04 | 34.42 | 18.42 | 23.07 | 25.97 | 17.67 |
| 4h | H1 2017-08..2018-12 | 327 | 61.29 | 46.67 | 30.67 | 15.89 | 45.40 | 33.65 |
| 4h | H2 2019-01..2020-04 | 560 | 56.82 | 42.20 | 26.20 | 16.84 | 39.98 | 33.11 |
| 24h | H1 2017-08..2018-12 | 328 | 220.99 | 206.37 | 190.37 | 141.79 | 79.19 | 6.07 |
| 24h | H2 2019-01..2020-04 | 560 | 164.16 | 149.54 | 133.54 | 110.71 | 53.45 | 127.18 |

Per coin at 4 h: net > 0 on 12 of 13 (base), 11 (stress); real - P1 > 0 on 13.

| coin | n | gross | net base | net stress | P1 gross | real - P1 |
|---|---|---|---|---|---|---|
| BTC | 98 | 33.50 | 18.88 | 2.88 | 3.75 | 29.75 |
| ETH | 93 | 61.44 | 46.82 | 30.82 | 17.65 | 43.79 |
| BNB | 82 | 63.41 | 48.79 | 32.79 | -7.73 | 71.14 |
| LTC | 81 | 72.92 | 58.30 | 42.30 | 22.56 | 50.36 |
| NEO | 81 | 24.49 | 9.87 | -6.13 | -22.63 | 47.12 |
| XRP | 60 | 113.29 | 98.67 | 82.67 | 44.22 | 69.07 |
| ADA | 72 | 37.37 | 22.75 | 6.75 | 24.80 | 12.57 |
| EOS | 68 | 108.60 | 93.98 | 77.98 | 70.81 | 37.78 |
| XLM | 63 | 66.25 | 51.63 | 35.63 | 42.17 | 24.08 |
| TRX | 61 | 54.14 | 39.52 | 23.52 | 2.29 | 51.85 |
| ETC | 64 | 40.99 | 26.37 | 10.37 | 22.66 | 18.34 |
| LINK | 42 | 75.27 | 60.65 | 44.65 | 58.77 | 16.50 |
| DOGE | 22 | -16.37 | -30.99 | -46.99 | -92.91 | 76.54 |

Daily-P&L Sharpe (annualised, calendar 2017-08-28..2020-04-28, 975 days): 1 h 1.981 / 1.163, 4 h 1.627 / 1.059, 24 h 2.396 / 2.196 (base / stress).

| year (4 h) | n | gross | net base | net stress | P1 gross | real - P1 |
|---|---|---|---|---|---|---|
| 2017 | 37 | -63.87 | -78.49 | -94.49 | -101.21 | 37.33 |
| 2018 | 290 | 77.26 | 62.64 | 46.64 | 31.18 | 46.08 |
| 2019 | 454 | 56.25 | 41.63 | 25.63 | 19.60 | 36.65 |
| 2020 | 106 | 59.25 | 44.63 | 28.63 | 5.04 | 54.21 |

### OX

Coin-weeks used / skipped: 3,251 / 454 {'listing': 0, 'delisting': 454, 'data_loss': 0}.

| h | control | n | gross | net base | net stress | hit (base) |
|---|---|---|---|---|---|---|
| 1h | real | 2,960 | 15.07 | 0.45 | -15.55 | 0.4551 |
| 1h | P1 | 12,796 | -1.30 | -15.92 | -31.92 | 0.4016 |
| 1h | P1_in | 7,950 | -2.37 | -16.99 | -32.99 | 0.3992 |
| 1h | P1_out | 4,846 | 0.44 | -14.18 | -30.18 | 0.4055 |
| 1h | P3 | 2,913 | 5.51 | -9.11 | -25.11 | 0.4360 |
| 1h | P3_owncov | 2,913 | 5.51 | -9.11 | -25.11 | 0.4360 |
| 4h | real | 2,960 | 22.38 | 7.76 | -8.24 | 0.4561 |
| 4h | P1 | 12,796 | 2.98 | -11.64 | -27.64 | 0.4351 |
| 4h | P1_in | 7,950 | 3.35 | -11.27 | -27.27 | 0.4307 |
| 4h | P1_out | 4,846 | 2.37 | -12.25 | -28.25 | 0.4422 |
| 4h | P3 | 2,913 | 15.13 | 0.51 | -15.49 | 0.4497 |
| 4h | P3_owncov | 2,913 | 15.13 | 0.51 | -15.49 | 0.4497 |
| 24h | real | 2,960 | 3.39 | -11.23 | -27.23 | 0.4554 |
| 24h | P1 | 12,796 | -13.24 | -27.86 | -43.86 | 0.4429 |
| 24h | P1_in | 7,950 | -14.45 | -29.07 | -45.07 | 0.4497 |
| 24h | P1_out | 4,846 | -11.25 | -25.87 | -41.87 | 0.4317 |
| 24h | P3 | 2,913 | 75.14 | 60.52 | 44.52 | 0.5053 |
| 24h | P3_owncov | 2,913 | 75.14 | 60.52 | 44.52 | 0.5053 |

| h | real net base [95 % CI], P(net <= 0) | real net stress, P(<= 0) | real - P1 [CI], P | real - P1_in, P | real - P1_out, P | real - P3 [CI], P | real - P3_owncov, P |
|---|---|---|---|---|---|---|---|
| 1h | 0.45 [-13.23, 15.22], 0.4840 | -15.55, 0.9815 | 16.38 [9.48, 23.23], 0.0000 | 17.44, 0.0000 | 14.63, 0.0130 | 9.56 [-5.54, 27.15], 0.1155 | 9.56, 0.1155 |
| 4h | 7.76 [-12.81, 30.41], 0.2455 | -8.24, 0.7665 | 19.40 [9.82, 28.76], 0.0000 | 19.02, 0.0025 | 20.01, 0.0025 | 7.24 [-18.78, 34.02], 0.2985 | 7.24, 0.2985 |
| 24h | -11.23 [-51.77, 31.17], 0.7030 | -27.23, 0.8950 | 16.63 [0.37, 34.00], 0.0210 | 17.84, 0.0850 | 14.65, 0.1280 | -71.74 [-122.14, -21.75], 0.9985 | -71.74, 0.9985 |

| h | half | n | gross | net base | net stress | P1 gross | real - P1 | real - P3 |
|---|---|---|---|---|---|---|---|---|
| 1h | H1 2022-01..2024-04 | 1,550 | 7.44 | -7.18 | -23.18 | -13.55 | 20.99 | 8.54 |
| 1h | H2 2024-05..2026-09 | 1,410 | 23.46 | 8.84 | -7.16 | 12.43 | 11.03 | 11.06 |
| 4h | H1 2022-01..2024-04 | 1,550 | 12.73 | -1.89 | -17.89 | -9.88 | 22.61 | 2.91 |
| 4h | H2 2024-05..2026-09 | 1,410 | 32.98 | 18.36 | 2.36 | 17.41 | 15.57 | 12.31 |
| 24h | H1 2022-01..2024-04 | 1,550 | 12.61 | -2.01 | -18.01 | -14.49 | 27.11 | -50.04 |
| 24h | H2 2024-05..2026-09 | 1,410 | -6.74 | -21.36 | -37.36 | -11.83 | 5.08 | -94.90 |

Per coin at 4 h: net > 0 on 10 of 15 (base), 9 (stress); real - P1 > 0 on 12.

| coin | n | gross | net base | net stress | P1 gross | real - P1 |
|---|---|---|---|---|---|---|
| 1000SHIB | 201 | 10.97 | -3.65 | -19.65 | 10.05 | 0.92 |
| SOL | 222 | 26.26 | 11.64 | -4.36 | 0.38 | 25.88 |
| SAND | 227 | -20.33 | -34.95 | -50.95 | -4.74 | -15.59 |
| LUNA | 17 | 72.09 | 57.47 | 41.47 | 52.71 | 19.38 |
| MANA | 228 | -0.90 | -15.52 | -31.52 | 0.79 | -1.69 |
| DOT | 235 | 39.60 | 24.98 | 8.98 | 11.89 | 27.72 |
| AVAX | 222 | 12.06 | -2.56 | -18.56 | 8.73 | 3.33 |
| FTM | 143 | 41.55 | 26.93 | 10.93 | 16.84 | 24.72 |
| MATIC | 121 | 58.33 | 43.71 | 27.71 | 2.96 | 55.37 |
| GALA | 222 | 35.54 | 20.92 | 4.92 | -1.21 | 36.75 |
| AXS | 235 | 51.17 | 36.55 | 20.55 | 18.82 | 32.35 |
| DYDX | 237 | -41.38 | -56.00 | -72.00 | -26.42 | -14.95 |
| FIL | 216 | 43.98 | 29.36 | 13.36 | 5.54 | 38.44 |
| LRC | 196 | 44.85 | 30.23 | 14.23 | 6.64 | 38.20 |
| CRV | 238 | 35.35 | 20.73 | 4.73 | -7.01 | 42.36 |

Daily-P&L Sharpe (annualised, calendar 2022-01-03..2026-09-29, 1731 days): 1 h 0.028 / -0.955, 4 h 0.317 / -0.341, 24 h -0.239 / -0.580 (base / stress).

| year (4 h) | n | gross | net base | net stress | P1 gross | real - P1 |
|---|---|---|---|---|---|---|
| 2022 | 683 | 24.68 | 10.06 | -5.94 | 7.99 | 16.69 |
| 2023 | 661 | -8.15 | -22.77 | -38.77 | -26.04 | 17.90 |
| 2024 | 657 | 8.47 | -6.15 | -22.15 | -12.66 | 21.13 |
| 2025 | 577 | 65.79 | 51.17 | 35.17 | 51.17 | 14.62 |
| 2026 | 382 | 29.43 | 14.81 | -1.19 | -1.23 | 30.65 |

### A

Coin-weeks used / skipped: 2,995 / 11 {'listing': 11, 'delisting': 0, 'data_loss': 0}.

| h | control | n | gross | net base | net stress | hit (base) |
|---|---|---|---|---|---|---|
| 1h | real | 2,692 | 17.65 | 3.03 | -12.97 | 0.4558 |
| 1h | P1 | 11,600 | 0.86 | -13.76 | -29.76 | 0.3897 |
| 1h | P1_in | 7,200 | 2.06 | -12.56 | -28.56 | 0.3818 |
| 1h | P1_out | 4,400 | -1.09 | -15.71 | -31.71 | 0.4025 |
| 1h | P3 | 2,602 | 1.80 | -12.82 | -28.82 | 0.4105 |
| 1h | P3_owncov | 2,602 | 1.80 | -12.82 | -28.82 | 0.4105 |
| 4h | real | 2,692 | 33.04 | 18.42 | 2.42 | 0.4755 |
| 4h | P1 | 11,600 | 6.85 | -7.77 | -23.77 | 0.4280 |
| 4h | P1_in | 7,200 | 11.73 | -2.89 | -18.89 | 0.4251 |
| 4h | P1_out | 4,400 | -1.15 | -15.77 | -31.77 | 0.4327 |
| 4h | P3 | 2,602 | 5.23 | -9.39 | -25.39 | 0.4427 |
| 4h | P3_owncov | 2,602 | 5.23 | -9.39 | -25.39 | 0.4427 |
| 24h | real | 2,692 | 62.93 | 48.31 | 32.31 | 0.4699 |
| 24h | P1 | 11,600 | 33.68 | 19.06 | 3.06 | 0.4508 |
| 24h | P1_in | 7,200 | 36.67 | 22.05 | 6.05 | 0.4544 |
| 24h | P1_out | 4,400 | 28.80 | 14.18 | -1.82 | 0.4448 |
| 24h | P3 | 2,602 | 75.52 | 60.90 | 44.90 | 0.4704 |
| 24h | P3_owncov | 2,602 | 75.52 | 60.90 | 44.90 | 0.4704 |

| h | real net base [95 % CI], P(net <= 0) | real net stress, P(<= 0) | real - P1 [CI], P | real - P1_in, P | real - P1_out, P | real - P3 [CI], P | real - P3_owncov, P |
|---|---|---|---|---|---|---|---|
| 1h | 3.03 [-9.04, 15.58], 0.3085 | -12.97, 0.9790 | 16.79 [10.50, 23.31], 0.0000 | 15.59, 0.0000 | 18.74, 0.0000 | 15.86 [3.28, 28.48], 0.0065 | 15.86, 0.0065 |
| 4h | 18.42 [0.58, 35.99], 0.0200 | 2.42, 0.4100 | 26.19 [17.94, 34.58], 0.0000 | 21.31, 0.0000 | 34.19, 0.0000 | 27.81 [8.88, 47.93], 0.0040 | 27.81, 0.0040 |
| 24h | 48.31 [0.85, 111.73], 0.0235 | 32.31, 0.1190 | 29.25 [15.55, 42.98], 0.0000 | 26.26, 0.0065 | 34.13, 0.0005 | -12.58 [-53.41, 26.61], 0.7320 | -12.58, 0.7320 |

| h | half | n | gross | net base | net stress | P1 gross | real - P1 | real - P3 |
|---|---|---|---|---|---|---|---|---|
| 1h | H1 2020-05..2023-06 | 1,309 | 24.19 | 9.57 | -6.43 | -1.72 | 25.92 | 22.38 |
| 1h | H2 2023-07..2026-09 | 1,383 | 11.46 | -3.16 | -19.16 | 3.33 | 8.13 | 9.67 |
| 4h | H1 2020-05..2023-06 | 1,309 | 33.59 | 18.97 | 2.97 | 0.26 | 33.33 | 29.52 |
| 4h | H2 2023-07..2026-09 | 1,383 | 32.52 | 17.90 | 1.90 | 13.12 | 19.41 | 26.25 |
| 24h | H1 2020-05..2023-06 | 1,309 | 120.18 | 105.56 | 89.56 | 76.83 | 43.35 | 2.25 |
| 24h | H2 2023-07..2026-09 | 1,383 | 8.75 | -5.87 | -21.87 | -7.38 | 16.14 | -28.86 |

Per coin at 4 h: net > 0 on 8 of 9 (base), 5 (stress); real - P1 > 0 on 9.

| coin | n | gross | net base | net stress | P1 gross | real - P1 |
|---|---|---|---|---|---|---|
| BTC | 317 | 14.28 | -0.34 | -16.34 | 4.84 | 9.44 |
| ETH | 307 | 30.69 | 16.07 | 0.07 | 7.29 | 23.40 |
| XRP | 289 | 58.66 | 44.04 | 28.04 | 20.32 | 38.34 |
| BNB | 298 | 23.54 | 8.92 | -7.08 | -0.51 | 24.05 |
| ADA | 310 | 49.16 | 34.54 | 18.54 | 15.86 | 33.31 |
| LTC | 300 | 17.17 | 2.55 | -13.45 | 5.53 | 11.64 |
| LINK | 308 | 28.14 | 13.52 | -2.48 | 2.55 | 25.58 |
| DOGE | 264 | 40.48 | 25.86 | 9.86 | 0.75 | 39.73 |
| BCH | 299 | 37.72 | 23.10 | 7.10 | 4.83 | 32.89 |

Daily-P&L Sharpe (annualised, calendar 2020-05-04..2026-09-29, 2340 days): 1 h 0.192 / -0.827, 4 h 0.791 / 0.105, 24 h 0.631 / 0.423 (base / stress).

| year (4 h) | n | gross | net base | net stress | P1 gross | real - P1 |
|---|---|---|---|---|---|---|
| 2020 | 276 | 51.68 | 37.06 | 21.06 | 8.30 | 43.38 |
| 2021 | 396 | 32.87 | 18.25 | 2.25 | -9.43 | 42.31 |
| 2022 | 429 | 35.28 | 20.66 | 4.66 | 5.89 | 29.39 |
| 2023 | 424 | 4.98 | -9.64 | -25.64 | -4.03 | 9.00 |
| 2024 | 438 | 35.49 | 20.87 | 4.87 | -0.32 | 35.82 |
| 2025 | 430 | 61.77 | 47.15 | 31.15 | 40.98 | 20.79 |
| 2026 | 299 | 7.72 | -6.90 | -22.90 | 6.31 | 1.41 |

## 5. Post hoc, not pre-registered, not gating (`tools/checks_posthoc.py`, `checks_posthoc.json`)

- OT, 4 h real T: mean net 43.85, median net 14.78; median gross 29.40 against P1 median gross -0.77; 1 % trimmed mean net 37.95, 2.5 % trimmed 35.30. The 10 largest |gross| events carry 32.3 % of the net sum.
- OX, 4 h real T: mean net 7.76, median net -21.79; median gross -7.17 against P1 median gross -20.64; 1 % trimmed mean net 4.23, 2.5 % trimmed 0.32. The 10 largest |gross| events carry 48.5 % of the net sum.
- OT without the four coin-weeks the data audit flagged for 15-60 % wicks (DOGE 2020-02-03, LTC 2018-06-18, NEO 2017-12-18, TRX 2018-08-13; 4 real 4 h events): n 883, net 44.13, real - P1 41.50.
- OX: 6 of the 10 largest |gross| 4 h events are PWL breakouts in the 2025-10-10 crash (AXS, CRV, DOT, GALA, FIL, LRC), all gains. The largest single event, AXS 2022-11-13 13:40, is a real squeeze bar (open 7.596, high 13.343, close 9.361, 106k trades) through the PWH of 11.84, followed by a 4 h exit at 7.139, -3,970 bps. A real stop fill in such a bar is uncertain in both directions.

## 6. Checks and files

- Tests: `test_engine.py`, `test_s_ties.py`, `test_fix_b1.py` (Phase 1) and `test_phase2.py` pass.
- Deterministic: two full runs gave identical results.json (4,400 leaves, 0 differences outside runtime).
- `tools/recompute_gates.py` rebuilds the four gating numbers and the 4 h n of each panel from the event files and coin-week files alone. Max |delta| vs results.json: 7.1e-15.
- Still owed by plan section 6: an independent recomputation of the gating numbers on both panels with separate code (tolerance 0.1 bps and 1 event), and the adversarial review of data, fills and look-ahead. Neither is done here.

| file | sha256 |
|---|---|
| `results.json` | `721c12af098e6b34` |
| `events_OT.csv.gz` | `dc7f7a1e277dda5d` |
| `events_OX.csv.gz` | `a7fae41f7d6928ba` |
| `events_A.csv.gz` | `b95322642b2b7672` |
| `events_OT_p3owncov.csv.gz` | `bfeefcd9b11f7fdb` |
| `events_OX_p3owncov.csv.gz` | `ad4977fa92935b48` |
| `events_A_p3owncov.csv.gz` | `2ae00620063bb865` |
| `coin_weeks_OT.csv.gz` | `b41d1f3350de1b86` |
| `coin_weeks_OX.csv.gz` | `136aa10e21f54143` |
| `coin_weeks_A.csv.gz` | `99a4368f6cb23e34` |
| `p3_weeks_OT.csv.gz` | `56d217843fe70188` |
| `p3_weeks_OX.csv.gz` | `d6d596dc287023b1` |
| `p3_weeks_A.csv.gz` | `b5c4a24046643a72` |
| `checks_posthoc.json` | `8be391d7ccf99407` |
| `engine.py` | `0104fc511f7c6dcb` |
| `loaders.py` | `49472c80279769cf` |
| `run.py` | `3acc6d8e61eb58a2` |
| `test_phase2.py` | `d7655581336411ec` |
| `test_engine.py` | `090a3bbe43a297c8` |
| `test_s_ties.py` | `7ce162a3253d5ba4` |
| `test_fix_b1.py` | `9d3b7470a203cf27` |
| `tools/checks_posthoc.py` | `850a0e8d0baf82b7` |
| `tools/recompute_gates.py` | `a9d58dd0cab67ae6` |
| `tools/make_summary.py` | `3b48169ab57e6e81` |

Run: `python3 -I -B run.py A OT OX` (about 22 s on 4 CPUs; log in `run_log.txt`), then `python3 -I -B tools/checks_posthoc.py`, `tools/recompute_gates.py`, `tools/make_summary.py`.
