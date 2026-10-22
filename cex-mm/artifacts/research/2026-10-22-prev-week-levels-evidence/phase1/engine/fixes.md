# Fixes to the final previous-week-level results

Plan: `research3/plan.md`, sha256 `8c7bf92317e2b18d5aac9ba001bb264a10039cdb2347f390a36ef0a0c782f19a`. Reference `8c7bf92317e2b18d5aac9ba001bb264a10039cdb2347f390a36ef0a0c782f19a`: MATCH (unchanged). No definition, parameter or pass rule in plan sections 1 to 5 was changed.

Base: implementation Y as reconciled (`reconcile/final/`: loaders.py, engine.py, run.py, test_engine.py, test_s_ties.py), copied into `final/`. Its pre-fix outputs are kept in `final/before/` for the comparison. engine.py is byte-identical to the reconciled copy. Only loaders.py and run.py changed.

## 1. Blocking defects and what was done

| id | defect (adversarial check, lens) | real deviation from the plan? | action |
|---|---|---|---|
| B1 | data: panel B misses 120 hourly bars (2022-02-26 00:00 to 02-28 23:00 and 2022-04-01 00:00 to 04-02 23:00) for XRP, LTC, IOTA, TRX, VET, XLM and ZEC. The holes are inside Binance's checksum-valid **monthly** 1 h zips. Binance's **daily** 1 h zips for those days are complete. 35 coin-weeks were skipped for this reason, and the skip count mixed this data loss with listing and delisting skips. | **Yes, in the data, not in the engine.** The 99 % rule was applied correctly. But plan §1 defines panel B as the Binance USDT-M 1 h series over the window. Binance publishes these 120 hours for the same contract at the same resolution, so the local input was an incomplete copy of that series. Panel A's identical holes (XRP, LTC, same days) were repaired from the daily archive before the study ran (`research3/data/patch_from_daily.py`, data_report §3). Leaving B unrepaired treated the two Binance panels differently. The plan does not say to keep known archive holes; for A it says "any missing month is reported, never silently dropped". The plan also names the local files as B's source. Read strictly, the unrepaired run followed the plan: the 99 % rule handled the missing bars and the skips were counted. Here the file names are read as where the series sits, not as a choice to keep holes Binance itself fills. Under either reading the gate outcome is the same (§5). | Fixed (§2). The engine and every rule are unchanged. Skips are now reported by reason. |

Not changed, because the plan states it: the 99 % coin-week rule itself. Listing and delisting weeks are still skipped and counted. The DOGE weeks before its first full prior week now appear under `listing`. Plan §1 says "DOGE starts with its first full prior week after its 2020-07-10 listing", so the plan expects them; they are reported separately, not dropped.

## 2. Fix B1: code and data changes

**Data.** `tools/fetch_daily_1h.py` (run with `python3 -I`) downloaded each daily zip and its `.CHECKSUM` into its own new, empty folder under `data_patch/raw/`, compared the sha256, and read only the one expected CSV member. Files: 63 (7 coins × (5 hole days + 4 boundary days)). Checksums OK: 63 of 63. Hole rows written to `data_patch/patch_B_holes.csv`: 840 (each row carries its source zip and sha256; full list in `data_patch/provenance.json`). Checks, all passed:

1. Every hole day has 24 rows on the hour, with close_time = open_time + 3,599,999 ms (fails recorded: 0).
2. For each coin, the 120 fetched open times are exactly the hours missing from the local file between 2022-02-25 00:00 and 2022-04-03 23:00: XRP 120/120 match, LTC 120/120 match, IOTA 120/120 match, TRX 120/120 match, VET 120/120 match, XLM 120/120 match, ZEC 120/120 match.
3. Boundary days (2022-02-25, 03-01, 03-31, 04-03): the daily rows equal the local monthly rows in open, high, low and close for all 7 coins × 4 days × 24 h: yes, 672 of 672. So the daily and monthly archives carry the same series.
4. XRP and LTC: each hole hour equals the 1 h aggregation of panel A's already-repaired 5 m bars: XRP 120/120, LTC 120/120.
5. The rows equal the adversarial check's own fetch (`verify/data/dl/daily_hole_rows.json`): 840 of 840.

**Code** (`tools/diff_loaders.txt`, `tools/diff_run.py.txt`):
- `loaders.py`, `load_panel_B`: after reading the same files as before, it merges the coin's rows from `data_patch/patch_B_holes.csv`. It asserts that no patch row overlaps an existing bar, that every row is on the hour and unique, and that every row is before the cap. It records `n_patched` (120 for each of the 7 coins, 0 for the other 18). Panels A and C loaders are untouched.
- `run.py`: each skipped coin-week gets a `skip_reason`. `listing` means the coin's first bar is after the start of the prior week. `delisting` means the coin's data ends before week w ends. `data_loss` means both weeks lie inside the coin's data span but have fewer than 99 % of their bars. results.json gains `coin_weeks_skipped_by_reason` per panel (3 counts; they sum to `coin_weeks_skipped`, asserted). extras.json gains the week lists by reason, and `n_patched` per coin. No other line changed.
- `test_fix_b1.py` (new): for all 25 coins, every bar of the old loader is present and unchanged in the new one. The only extra bars are the 840 patch rows. After the patch, panel B has no gap and no duplicate on any coin. `test_engine.py` and `test_s_ties.py` still pass.

## 3. Re-run of all panels and checks

- Panel A: coin-weeks used / skipped 2,995 / 11 → 2,995 / 11. Results leaves changed: 0 of 974. Event file byte-identical to the pre-fix run: yes (108,576 → 108,576 rows).
- Panel B: coin-weeks used / skipped 8,233 / 117 → 8,268 / 82. Results leaves changed: 484 of 969. Event file byte-identical to the pre-fix run: no (299,385 → 300,702 rows).
- Panel C: coin-weeks used / skipped 828 / 0 → 828 / 0. Results leaves changed: 0 of 879. Event file byte-identical to the pre-fix run: yes (29,574 → 29,574 rows).
- Panel B events: 1,317 rows added, 0 removed, 0 existing rows changed. All the added rows lie in the five restored weeks (2022-02-21 288, 2022-02-28 171, 2022-03-07 261, 2022-03-28 309, 2022-04-04 288) and the seven coins (XRP 219, LTC 201, XLM 198, IOTA 183, VET 183, ZEC 171, TRX 162).
- Reproduces the adversarial check's sensitivity run (`verify/data/rerun/B_holes`): 969 of 969 panel-B numbers equal (max |Δ| 0.0; same leaf definition as the 969 above), and events_B is byte-identical: yes.
- **Plan §7 on the repaired data.** Implementation X (`reconcile/X_patched` copied to `final/xcheck/`, with the same patch rows added in its own loader, marked `# FIX B1`; X_patched's four `# RECONCILE` edits kept) was re-run on A, B and C. Against final/results.json: 2,822 numbers compared, 0 outside tolerance, max |Δ| 1.8e-13. Events: A 108,576 / 108,576 rows, X-only 0, final-only 0, differing 0; B 300,702 / 300,702 rows, X-only 0, final-only 0, differing 0; C 29,574 / 29,574 rows, X-only 0, final-only 0, differing 0. The only leaves not in X are the 9 new skip-reason counts.

Coin-weeks skipped, by reason:

| panel | before: total | listing | delisting | data loss | after: total | listing | delisting | data loss |
|---|---|---|---|---|---|---|---|---|
| A | 11 | 11 | 0 | 0 | 11 | 11 | 0 | 0 |
| B | 117 | 11 | 71 | 35 | 82 | 11 | 71 | 0 |
| C | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

After the fix: listing = DOGE 11 weeks (2020-05-04 to 2020-07-13); delisting = EOS 71 weeks (2025-05-19 to 2026-09-21; EOS data ends 2025-05-21 09:00); data loss = none. The before split comes from the same classifier run on the unrepaired loader (`tools/classify_before.py`, `skips_before.json`). Data loss before: XRP 2022-02-21, 2022-02-28, 2022-03-07, 2022-03-28, 2022-04-04; LTC 2022-02-21, 2022-02-28, 2022-03-07, 2022-03-28, 2022-04-04; IOTA 2022-02-21, 2022-02-28, 2022-03-07, 2022-03-28, 2022-04-04; TRX 2022-02-21, 2022-02-28, 2022-03-07, 2022-03-28, 2022-04-04; VET 2022-02-21, 2022-02-28, 2022-03-07, 2022-03-28, 2022-04-04; XLM 2022-02-21, 2022-02-28, 2022-03-07, 2022-03-28, 2022-04-04; ZEC 2022-02-21, 2022-02-28, 2022-03-07, 2022-03-28, 2022-04-04 (35 in all). Panel A's 11 are the DOGE listing weeks.

## 4. Before / after numbers (panel B; A and C unchanged)

Panel B: 484 of 969 results leaves change. Of the 234 means that change, 25 move by more than 1 bps and 163 by more than 0.1 bps. Largest mean move 2.65 bps; largest event-count change 131; largest P change 0.029; pooled real means move by at most 0.69 bps. Panels A and C: 0 changes (max |Δ| 0).

Largest mean moves:

| leaf | before | after | Δ |
|---|---|---|---|
| `B.tests[S|4h|P2].halves.H1.diff_bps` | -13.03 | -10.37 | +2.65 |
| `B.tests[B|24h|P2].halves.H1.diff_bps` | 28.02 | 30.34 | +2.32 |
| `B.cells[S|L|24h|P2].gross_bps` | 12.61 | 10.80 | -1.81 |
| `B.cells[S|L|24h|P2].net_bps` | -2.01 | -3.82 | -1.81 |
| `B.cells[S|L|4h|P2].gross_bps` | -0.27 | -2.04 | -1.78 |
| `B.cells[S|L|4h|P2].net_bps` | -14.89 | -16.66 | -1.78 |
| `B.cells[S|pooled|4h|P2].net_bps` | -10.29 | -11.75 | -1.46 |
| `B.cells[S|pooled|4h|P2].gross_bps` | 4.33 | 2.87 | -1.46 |
| `B.cells[S|L|24h|real].net_bps` | -25.66 | -27.09 | -1.43 |
| `B.cells[S|L|24h|real].gross_bps` | -11.04 | -12.47 | -1.43 |
| `B.cells[S|L|24h|P1].gross_bps` | 10.22 | 8.87 | -1.35 |
| `B.cells[S|L|24h|P1].net_bps` | -4.40 | -5.75 | -1.35 |

Panel B at the primary horizons (pooled sides), before → after:

| pattern | real n | real gross | real net | P(net ≤ 0) | real − P1 | 95 % CI | P(diff ≤ 0) | halves real − P1 | real − P2 | daily Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|
| F 4h | 7,409 → 7,439 | -16.19 → -16.22 | -25.62 → -25.65 | 1.0000 → 1.0000 | -16.72 → -16.84 | [-22.57, -10.79] → [-22.75, -10.86] | 1.0000 → 1.0000 | -21.12 / -12.49 → -21.33 / -12.49 | -47.75 → -47.47 | -1.289 → -1.295 |
| S 4h | 3,710 → 3,728 | -14.12 → -14.32 | -28.74 → -28.94 | 1.0000 → 1.0000 | -12.50 → -12.73 | [-24.67, -2.59] → [-24.85, -2.97] | 0.9935 → 0.9950 | -2.61 / -21.83 → -3.16 / -21.83 | -18.45 → -17.19 | -1.220 → -1.232 |
| B 24h | 6,694 → 6,721 | 3.12 → 3.78 | -11.50 → -10.84 | 0.7275 → 0.7155 | -4.06 → -3.54 | [-15.89, 8.00] → [-15.32, 8.42] | 0.7295 → 0.7005 | 1.99 / -9.84 → 3.01 / -9.84 | -14.54 → -13.22 | -0.243 → -0.230 |

Other moves the adversarial check named, before → after (gross bps):

- S side L 24h real: -11.04 → -12.47 (n 1948 → 1959)
- F side L 24h real: 0.83 → -0.44 (n 3653 → 3672)
- B side L 24h real: -27.36 → -26.02 (n 3234 → 3251)
- S pooled 4h P2: 4.33 → 2.87 (n 883 → 889)
- S 4h real − P2, first half: -13.03 → -10.37
- B 24h real − P2, first half: 28.02 → 30.34

## 5. Pass rules (plan §5) at the primary horizons, before → after

C net gates only with at least 300 events (plan: "information only if fewer than 300 events").

| pattern | A real − P1 ≥ +5, P ≤ 0.003 | A halves > 0 | A coins > 0 (≥ 6) | B real − P1 > 0 | level edge | A net > 0, P ≤ 0.003 | A halves net > 0 | A coins net > 0 | B net > 0 | C net > 0 (n) | tradable |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F 4h | -26.19, P 1.0000 | -33.33 / -19.41 | 0 | -16.72 → -16.84 | fail → fail | -42.47, P 1.0000 | -43.02 / -41.95 | 0 | -25.62 → -25.65 | -51.37 (737) | fail → fail |
| S 4h | -10.70, P 0.9325 | -12.19 / -9.49 | 1 | -12.50 → -12.73 | fail → fail | -30.10, P 1.0000 | -33.54 / -27.07 | 0 | -28.74 → -28.94 | -40.41 (336) | fail → fail |
| B 24h | -6.53, P 0.7670 | -14.54 / 0.92 | 4 | -4.06 → -3.54 | fail → fail | 13.03, P 0.2820 | 48.36 / -20.54 | 5 | -11.50 → -10.84 | -51.10 (675) | fail → fail |

Only the B column moves (A and C are unchanged). No pattern passes the level-edge rules or the tradable rules, before or after. The fix changes no conclusion. Per plan §6 the result stays the null: no Phase 2 backtest.

## 6. Headline: panel A, primary horizons (unchanged by the fix)

| pattern | real n | real gross | real net | hit | P1 n | P1 gross | real − P1 | 95 % CI | P(diff ≤ 0) | P(net ≤ 0) | halves real − P1 | halves net | coins diff > 0 / net > 0 | real − P2 (P) | daily Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F 4h | 2,692 | -33.04 | -42.47 | 0.470 | 11,600 | -6.85 | -26.19 | [-34.58, -17.94] | 1.0000 | 1.0000 | -33.33 / -19.41 | -43.02 / -41.95 | 0 / 0 | -62.48 (0.9990) | -1.782 |
| S 4h | 1,311 | -15.48 | -30.10 | 0.477 | 6,482 | -4.78 | -10.70 | [-24.89, 2.96] | 0.9325 | 1.0000 | -12.19 / -9.49 | -33.54 / -27.07 | 1 / 0 | -29.46 (0.9665) | -1.220 |
| B 24h | 2,422 | 27.65 | 13.03 | 0.452 | 10,319 | 34.18 | -6.53 | [-23.99, 9.93] | 0.7670 | 0.2820 | -14.54 / 0.92 | 48.36 / -20.54 | 4 / 5 | -32.23 (0.5995) | 0.189 |

Reel-style rates on A (descriptive): touched any level 0.8007, PWH 0.4728, PWL 0.4260 of coin-weeks; rejected within 60 min: real 0.4417, P1 0.5463, P2 0.4718; continued after confirmation: real 0.7246, P1 0.7048, P2 0.6784.

## 7. Files

| file | sha256 |
|---|---|
| `final/results.json` | `17338adbcefd41cf` |
| `final/events_A.csv.gz` | `f2152e02982a06fd` |
| `final/events_B.csv.gz` | `a42e07731ca459ff` |
| `final/events_C.csv.gz` | `d98ee86cbce6d1b1` |
| `final/extras.json` | `80c2539c713cb29d` |
| `final/loaders.py` | `3c9524186052a8ee` |
| `final/engine.py` | `04c283bf4ccd4512` |
| `final/run.py` | `7d78385b93f4d0d4` |
| `final/test_engine.py` | `090a3bbe43a297c8` |
| `final/test_s_ties.py` | `7ce162a3253d5ba4` |
| `final/test_fix_b1.py` | `48c11e2898f1f471` |
| `final/data_patch/patch_B_holes.csv` | `b2aed72d96d04825` |
| `final/data_patch/provenance.json` | `30233df28273fa94` |
| `final/tools/fetch_daily_1h.py` | `2b56ad8a7d847e46` |
| `final/tools/compare.py` | `4017d8bace7ebf2d` |
| `final/tools/compare_xcheck.py` | `26bd177a05a88f5e` |
| `final/tools/summarize.py` | `8222c0328ae6af2f` |
| `final/tools/make_fixes_md.py` | `e30f5e11acf6c404` |
| `final/xcheck/engine.py` | `bf81f4a02fdff751` |
| `final/xcheck/run.py` | `2777191fcc6f1c1b` |
| `final/xcheck/results.json` | `6c6a09899e773be6` |

Comparison outputs: `cmp_before_after.json` (every changed leaf), `cmp_xcheck.json` (X vs final), `fix_summary.json` (the numbers in this file). Run log: `run_log.txt`. Pre-fix outputs: `before/`.
