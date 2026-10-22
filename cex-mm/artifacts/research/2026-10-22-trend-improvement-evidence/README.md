# Evidence pack: trend rule improvement study (2026-10-22)

This folder holds the evidence behind the memo `cex-mm/artifacts/research/2026-10-22-trend-improvement.md` and the report `resource/08-trend-rule-improvement-research.md`. The study asked whether the long/flat trend rule on the nine Delta India perps can be improved. It ran in three phases:
- research and adversarial verification of the candidates;
- a frozen pre-registered plan;
- backtests judged mechanically against that plan.

The answer was no: no cell passed, and the two running paper books were not changed.

## No secrets, no orders
- **Public data only.** Every script here reads only public sources:
  - the data.binance.vision archive and its S3 listing;
  - Delta India's public REST API (`/v2/history/candles`, `/v2/products`, `/v2/tickers`, order books).
- **No order paths or keys.** No script places, edits or cancels an order. None reads an API key, a `.env` file or a signature.
- **No code, book or live system was touched.** Outside this pack the study added only the memo, `resource/08-trend-rule-improvement-research.md`, 11 rows and a closing sentence in `resource/07-trend-rule-and-prop-trading-research.md` (plus, after the review, corrections to its signal-mapping comment and plain-English line, which disagreed with `trend_backtest.py`, and to its universe paragraph), and two lines in the repository `README.md` (the tree entry and reading-order item 7). It changed no file in `cex-mm/scripts/`, `mm-bot` or `mm-oems`, and it did not touch the VM, the paper books or the live market-making run.

## What is in each folder
| Path | Contents |
|---|---|
| `phase1_plan.md`, `plan_sha256.txt` | The frozen Phase 2 plan. It sets the baseline, datasets, metrics, bootstrap, multiple-testing haircut and pass rule (section 5). Section 6 holds the 24 primary cells and their neighbors; amendments A7 and A8 (section 10) add SZ-17 and SIG-13, 26 in all. Section 8 lists the 36 candidates not pursued, in 33 one-line entries, and section 10 holds amendment A-2026-10-21. `plan_sha256.txt` holds its sha256, `9ad0a829...c095`, recorded before run 1. |
| `phase1/notes/` | One note per research angle: `academic_signal`, `academic_sizing`, `crypto_academic`, `practitioner_trend`, `crypto_practitioners`, `universe`, `costs_funding`, `overlays`, `timing_cadence`. Each has its sources, URLs and [UNVERIFIED] / [VERIFIED] / [LOCAL] tags. `phase1_plan_notes.md` holds the planner's working notes. `completeness_critic.md` is the critic pass whose findings became amendment A-2026-10-21; its tool is `critic_tools/drift5m.py`. `diag_sizing*_output.txt` are local sizing diagnostics. |
| `phase1/master_candidates.md` | The consolidated list: 77 raw candidates from nine angles, 57 entries after 20 merges, each with its exact rule, evidence and sources. |
| `phase1/verify_*.md` | The seven adversarial verifications (signal, sizing, universe, costs and execution, overlay, timing and cadence, data). Each gives a keep / refine / drop verdict per candidate, checked against what the repo had already tested. |
| `phase1/funding_summary.json` | Delta funding statistics for the nine (2025, 2026 to date, all). These feed the Delta-funding stress line (amendment A6). The harness reads them from `research2/funding_summary.json`; if that file is missing it runs the stress line with no floors, identical to each cell's Binance-funding line, without an error. |
| `engine/` | The numpy backtest engine, run from the session scratchpad as `tools2/`. See the next table. |
| `data_scripts/` | Scripts that re-download the public data (see "Reproducing"), plus `binance_first_month.json`: the first Binance USDT-M monthly daily file for 181 Delta underlyings. |
| `phase2/summary.md` | One line per cell and cadence: B POST delta, CI, P, sd, hurdle, B FULL Sharpe and drawdown, halves, A and C deltas, turnover, funding and after-tax CAGR. It also holds the diagnostic outcomes and the engine note on the COST-2 buffer bug, which was fixed before judging. Struck-through lines are the invalid pre-fix runs. Its hurdle column is 2.49 x sd (the plan's formula at N 90); the judged hurdle is 2.37 x sd (amendment A3) and is in `verdicts.md`. |
| `phase2/verdicts.md` | The mechanical verdict for every cell: how each condition was read, the verdict table, per-condition detail, and the data and implementation flags. **Read the correction at its end.** The D-0 gap was a data defect, UNI-1 fails on corrected data, and every other verdict stands. Its stated reason (each failing cell also fails a condition that does not use panel B) holds for every cell except OVL-2, whose three failures all use panel B and were not recomputed; the patch moved static-24 by 0.009 against a 0.167 gap to OVL-2's hurdle. |
| `phase2/judge.py` | The script that wrote `verdicts.md` from the results, except the "Correction 2026-10-22" section at its end, which was appended from `uni1_verify/synthesis.md`. It recomputes nothing. Besides `<out.md>` it pickles the parsed results to a hard-coded scratchpad path, `judge/results.pkl` (line 464, an inline literal), which must be edited too, or the run stops before `<out.md>` is written. |
| `phase2/diagnostics.md` | The pre-registered diagnostics, which are not trials: D-1 trend states (gating SIG-9 and OVL-3), D-3 fill drift from 00:00 to about 00:10 UTC (the file labels it 00:05; the code takes the close of the bar that opens at 00:05), and D-4 Delta MARK vs last-trade closes. |
| `phase2/a6_plan/` | Added after the review: the A6 Delta-funding stress line as the plan wrote it (majors floored at 0.01 %/8 h, other coins scaled by the Delta/Binance ratio), next to the line the harness ran. `notes.md` holds the interpretation, the ratios and the result: no verdict changes. |
| `phase2/reference.md`, `reference.json` | Reference lines: the seven single-weekday weekly books and the daily book at TV 0.25 with a 10 % band, on A, B and C. |
| `phase2/results/*.json` | 28 result files: 25 primary cells (SIG-9 was gated off and has none), `D-0`, `D_band10` and `baseline`. Each holds panel x cadence x window rows with the variant and base statistics, bootstrap delta, CI, P, sd, after-tax lines (`tax`, `base_tax`), and the matched-vol, Delta-funding-stress and whole-contract blocks where run. Neighbor files (`<id>__<label>.json`) were not copied. Their numbers are in `summary.md` and `verdicts.md`. |
| `uni1_verify/` | The adversarial verification of UNI-1, the one cell that first passed. `synthesis.md` holds the verdict, the corrected scorecard, the defects, the fixed annual-review re-test and the parked spec. There is one folder per lens: `rebuild/` (an independent re-implementation), `audit/` (data audit and the gap patch; `patched_clauses_out.txt` is the pivotal output), `robust/` (perturbations and placebo) and `live/` (today's Delta products, contract values, funding and books). The `synth/` folder holds the synthesis re-run. |

Engine modules (`engine/`):

| File | Role |
|---|---|
| `data.py` | Loads the Binance caches and the Delta cache into aligned day x coin arrays. Defines `NINE`, `EXANTE24` and the Delta contract values `CVALS`. |
| `rules.py` | Signal, vol and sizing building blocks. `baseline_weights()` reproduces `cex-mm/scripts/trend_backtest.py::target_weights`. |
| `sim.py` | The daily simulator: costs, funding, band, whole contracts, the COST-2 buffer and the paired block bootstrap. |
| `check_baseline.py` | The T0 reproduction against the published baselines and the repo function. |
| `harness.py` | Runs a cell on the panels and cadences the plan names. Writes `<id>.json` and a `summary.md` line. |
| `evaluate.py` | The earlier smoke harness, kept for provenance. |
| `registry.py`, `variants.py` | The variant registry. |
| `variants_p1.py`, `variants_signal.py`, `variants_sizing.py`, `variants_universe.py`, `variants_overlay.py`, `variants_timing.py` | The pre-registered cells and their neighbors, by family. Each docstring lists its self-tests and report items. |
| `diagnostics.py` | Writes `phase2/diagnostics.md`. |

## Errata (the evidence files are left as written)
- **`phase2/verdicts.md`, "How each condition was read" and flag 1:** "2.37 corresponds to N of about 66" is an arithmetic slip. The plan's Bailey-López de Prado formula gives 2.369 at N 64, 2.381 at N 66 and 2.493 at N 90 [SYNTHETIC]. No verdict depends on it.
- **`phase2/verdicts.md`, "Passes" and "Near misses":** both were written while UNI-1 still passed. The correction at the end supersedes them: on gap-patched data UNI-1 fails exactly one clause (daily matched-vol maxDD −24.51 % vs −24.01 %), and no class I or class II cell fails exactly one condition.
- **`engine/harness.py`, `delta_funding_stress`, and every `delta_funding_stress` block in `phase2/results/`:** the stress line floors each of the nine at its own Delta 2025–26 mean and leaves other coins on Binance funding. Amendment A6 asked for max(Binance, 0.01 %/8 h) on BTC, ETH, BNB, LTC and BCH and the Delta/Binance ratio elsewhere (`CAPPED_MAJORS` in `harness.py` is defined for it but never used by the harness; `phase2/a6_plan/plan_a6.py` uses it). `phase2/a6_plan/` runs the plan's version; no verdict changes.
- **`phase2/diagnostics.md`, D-3 heading:** "00:00 -> 00:05" is the decision time to the open of the fill bar; the return measured runs to that bar's close, about 00:10 UTC.
- **`phase2/diagnostics.md`, D-3:** the A2 gate reads "re-run daily cost lines with drift = YES". The re-run was not done; `phase2/summary.md` (Diagnostic outcomes) records the conservative decision to add no cost and credit no gain, because the drift favours the seller.

## Reproducing
The code was run inside the session scratchpad, not from this folder.
- **Absolute paths must be edited.** The engine, the judge and most `uni1_verify/` scripts use absolute paths under `/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/`, the session scratchpad, which is not kept. The places to change are `data.SP` in `engine/data.py`, plus the `sys.path` and path constants in `check_baseline.py`, `phase2/judge.py` (`P` at line 6 and the inline `results.pkl` path at line 464) and the `uni1_verify/` scripts. Point them at a new working directory before running anything. Exceptions: `uni1_verify/live/fetch_delta.py`, `fetch_delta_all.py`, `fetch_funding.py`, `uni1_delta.py`, `uni1_now.py`, `uni1_fundbook.py` and `uni1_funding_corr.py` read and write next to themselves (`dl/`, `delta_out.json`), and `uni1_verify/rebuild/run_robust.py` and `run_grid.py` write `robust.json` and `grid.json` to the current directory; `uni1_now.py`, `uni1_fundbook.py` and `uni1_funding_corr.py` also put the scratchpad `tools2/` on `sys.path`, so edit their `SP` as well. Copy them into the new working directory first: run in place, `fetch_delta.py` writes Delta data dumps into this repository folder, which git does not ignore. `phase2/a6_plan/plan_a6.py` expects the scratchpad layout (`research2/a6_plan/` next to `tools2/`). In that layout the engine sat in `tools2/` and wrote its results to `research2/phase2/`.
- **The engine reads data caches that are not in this pack.** In the old scratchpad layout they are:
  - `trend-cache/`: the nine coins' Binance monthly files and `delta-2026-10-12.json`. Written by `cex-mm/scripts/trend_backtest.py --source both --cache <dir> --end 2026-10-12`.
  - `av_cache/`: the rest of the 24 ex-ante perps. Written by `cex-mm/artifacts/research/2026-10-13-prop-strategy-evidence/tools/av_fetch_extra.py`.
  - `universe/cache/` and `universe/cache_all/`: written by `data_scripts/fetch_universe.py` (needs `universe/delta_perps.json` from Delta `/v2/products`) and `data_scripts/fetch_all.py` (the survivorship-free pool from the S3 index).
  - `universe/klines5m/`, `universe/hourly_extra/` and `universe/delta_mark/`: written by `data_scripts/fetch_extra.py`.
  - `hourly/<SYM>USDT-1h.csv`: written by `cex-mm/artifacts/research/2026-10-13-prop-strategy-evidence/tools/fetch_hourly.py`.
  - `tools2/cache_binance_*.npz`: built by `data.py` on first load.
- **The three `data_scripts/` take their own folder as the base.** They were run from `universe/` in the scratchpad: they read `../trend-cache` and `../av_cache` and write their output folders next to themselves. They need no path edits, but they do not create their output folders, so make those first.
- **These inputs have no fetch script here, or must be put where the engine reads them.** All are public:
  - Delta 1 h price candles (`research2/delta_data/hourly_<SYM>USD.json`, from `/v2/history/candles?resolution=1h`);
  - Binance spot PAXGUSDT daily files for UNI-2 (`research2/dl/paxg_spot`, `universe/spot/`). The engine loads gold as coin `GOLD` from the `data.CACHES` folders only, so the files must also be saved in one of them as `binance-GOLDUSDT-1d-<YYYY-MM>.csv`;
  - `universe/pool_all.json`, the 696-symbol pool read by `engine/harness.py` and `engine/variants_universe.py`; no script here writes it;
  - `research2/funding_summary.json`: copy `phase1/funding_summary.json` there (see its row above);
  - the gap-patch files in `uni1_verify/audit/dl_raw/`, read by `patch_gaps.py`: the 40 Binance USDT-M daily 1d kline zips (`data/futures/um/daily/klines/<SYM>/1d/`) for XRP, LTC, SOL, TRX, XLM, ZEC, IOTA and VET on 2022-02-26..28 and 2022-04-01..02, plus the monthly `DASHUSDT-1d-2022-10.zip` and `DASHUSDT-fundingRate-2022-10.zip`;
  - Delta `/v2/tickers` and `/v2/products` snapshots (`universe/tickers.json`, `universe/products.json`), read by `uni1_verify/live/uni1_live.py`.
- **`fetch_all.py` drops failed downloads silently.** Binance's monthly files also lack 2022-02-26..28 and 2022-04-01..02 for 51 symbols, and DASHUSDT 2022-10 was missing. Check the downloads against the S3 listing, and patch the gaps from Binance's own daily and monthly files as `uni1_verify/audit/patch_gaps.py` does (it reads them from `dl_raw/` and does not download them). Without that, static-24 reproduces 0.851 / 0.810 instead of 0.860 / 0.819 (`phase2/verdicts.md` correction).
- **Order of runs:**
  1. `engine/check_baseline.py` (T0). It must reproduce the six T0 Sharpes in `phase1_plan.md` section 1 (A-daily 1.2498, A-weekly 1.1206, B-daily 0.8512, B-weekly 0.8101, C-daily 0.9941, C-weekly 0.7041; B becomes 0.860 / 0.819 on gap-patched data). `phase2/results/baseline.json` holds only the A-daily line.
  2. `engine/diagnostics.py`.
  3. `engine/harness.py <ID> [--panels A,B,C] [--cadences daily,weekly|tranche] [--capitals 1000,2500,5000] [--vs ...]` for each cell, with the arguments the plan gives that cell.
  4. `phase2/judge.py <out.md>`.

  The Binance archive window is fixed at 2020-05-01..2026-09-30 and the Delta window at 2024-08-10..2026-10-12, so a later download reproduces the same numbers only if it is cut to those dates.
