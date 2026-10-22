# Evidence: previous-week highs and lows on crypto perps (2026-10-22)

Memo: `cex-mm/artifacts/research/2026-10-22-prev-week-levels.md`. Public data only; no script places an order or reads a key.

| Path | Contents |
|---|---|
| `plan.md`, `plan_sha256.txt` | Phase 1 plan, frozen before any run (sha256 `8c7bf923...f19a`): the reel's three trades (fade F, confirmed breakout B, failed breakout S), the price-shifted control P1, the window-shifted control P2, costs, the week-cluster bootstrap and the pass rules. |
| `phase2_plan.md`, `phase2_plan_sha256.txt` | Phase 2 plan, frozen before any run (sha256 `940a391b...40f2`): the touch-breakout T on two out-of-sample panels, OT (Binance spot 2017–20) and OX (15 perps chosen by 2021-Q4 volume, 2022–26), with the Thursday-anchored control P3. |
| `phase1/judge.py`, `phase1/judge_out.txt` | The mechanical application of Phase 1's pass rules to the final results, with every cell. |
| `phase1/engine/` | The plan-faithful Phase 1 engine (implementation Y after reconciliation, plus the panel-B hole fix): `loaders.py`, `engine.py`, `run.py`, tests, `fixes.md`, `results.json`. |
| `phase1/reconcile.md` | The diff between the two independent implementations, every disagreement and its resolution. |
| `phase1/workflow_result.json` | The full structured record of Phase 1: data download, both implementations, reconciliation, the three adversarial checks (look-ahead and fills; controls and statistics; data), the fix and the re-check. The checkers' findings live here, because subagents could not write report files. |
| `phase1/data/` | The 5 m download, patch and audit scripts, `data_report.md`, `patch_log.json`, `week_coverage.csv`. |
| `phase2/engine/` | The Phase 2 extension (T, P3, P1 split, new loaders), `results.json`, `summary.md`, and the out-of-sample event files `events_OT.csv.gz`, `events_OX.csv.gz`. |
| `phase2/summary_table.txt` | Every T cell at 1 h / 4 h / 24 h for A, OT and OX, with per-year and per-coin means. |
| `phase2/data_ot/`, `phase2/data_ox/` | Download and audit scripts and reports; `data_ox/selection.csv` is the OX ranking, written before any 5 m data was downloaded. |
| `phase2/check_independent/` | The independent recompute of the gating numbers and its comparison with the run. |
| `phase2/check_adversarial/` | The adversarial review's scripts and outputs (fills, data, concentration, the wider OT coin set, P1/P3 rebuild). |
| `phase2/workflow_result.json` | The structured record of Phase 2, including every finding. |
| `literature/literature.md` | Prior evidence: Osler on support, resistance and stop-loss clustering in FX, range breaks, opening-range breakouts, crypto round numbers and liquidations, with URLs and [VERIFIED] / [UNVERIFIED] tags. |

Not included: the downloaded klines (about 1 GB, public; the download scripts rebuild them), the Phase 1 event files and the intermediate implementations. The scripts use absolute paths under the session scratchpad (`/tmp/claude-0/.../scratchpad/`), which is not kept; edit them before re-running.
