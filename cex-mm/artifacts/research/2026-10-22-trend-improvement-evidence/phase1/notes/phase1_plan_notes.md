# Notes behind phase1_plan.md (head of research, 2026-10-21)

Read-only pass; nothing in the repo edited, no orders, no external fetch needed (every input was already on disk).

## What was read (all VERIFIED by opening the file)
- `research2/verify_signal.md`, `verify_sizing.md`, `verify_universe.md`, `verify_costs_execution.md`, `verify_overlay.md`,
  `verify_timing_cadence.md`, `verify_data.md` (the seven adversarial verifications; verdicts and refined rules taken as given).
- `research2/master_candidates.md` (head and the stacking/combination lines; 57 entries).
- `tools2/{evaluate,sim,data,rules,variants,registry,check_baseline}.py`: the Phase 2 harness. numpy 2.5.3 is installed, scipy is not;
  the repo engine `cex-mm/scripts/trend_backtest.py` is pure Python. The plan's bootstrap is specified in pure Python (random,
  statistics, math) so it runs in either; `sim.block_bootstrap_diff` (numpy, 20-day blocks, 1000 draws, seed 7) is an accepted implementation.
- `research2/phase2/baseline.json` (A-daily 1.2498, A-weekly 1.1206, B-daily 0.8512 / POST 0.5863, B-weekly 0.8101 / POST 0.4915,
  C-daily 0.9941, C-weekly 0.7041; yearly tables; worst years: A 2022 -5.0 % / -6.9 %, B 2022 -8.4 % / -6.9 %, C 2026 +2.7 % / -1.9 %).
- `av_runs/av_universe_9.txt` (static sets; 24 ex-ante 0.86 / 0.82, maxDD -24.1 % / -16.8 %); `av_runs/av_dsr.txt` (E[max null Sharpe]
  0.15-0.28 at 18 trials, sd 0.08-0.15).
- `backtest_results.md` sections T3 (a-m), T5, T6 (a-f): the prior-test ledger and the Sharpe SE (0.50 full, 0.51 POST, 0.77-0.80 recent).
- `cex-mm/scripts/trend_backtest.py::target_weights` and `::backtest` (the exact baseline).
- Data on disk: `tools2/cache_binance_{10c,25c,696c}_*.npz` (nine+gold, 25 ex-ante with funding, 696-symbol wide panel),
  `trend-cache/delta-2026-10-12.json`, `hourly/*-1h.csv` (nine), `research2/delta_data/hourly_*.json` (nine), `universe/cache_all`
  (survivorship-free, quote_volume), `research2/dl/paxg_spot` (74 zips), `research2/data/delta_daily_turnover_400d.json`,
  `research2/data/products.json`.

## Decisions taken in the plan and why
- 24 primary cells (9 signal, 4 sizing, 2 universe, 1 cost, 2 overlay, 3 timing, 3 combos); 3 are conditional on the SIG-9 state
  diagnostic (SIG-9, OVL-3; mutually exclusive) or run regardless at low priority (SIG-11). N = 24 fixed for the haircut whether or not
  the conditionals run.
- Haircut = 1.98 x sd_Delta (Bailey-Lopez de Prado expected max of 24 null differences, multiplier computed with
  statistics.NormalDist: 1.575 at N=10, 1.922 at 21, 1.98 at 24, 2.073 at 30). Uses the variant's own paired-bootstrap sd so a variant
  that barely moves the book gets a small haircut.
- Two acceptance classes because most surviving candidates claim lower orders/funding at equal Sharpe (class II, non-inferiority with
  a -0.03 margin), not a Sharpe gain (class I).
- TIME-1's decomposition (design weekday worst of seven vs genuine variance reduction) must be printed because ~0.10 of the expected
  +0.13 on A is the former; the change is still legitimate (RTL removal) and is judged vs the live design it would replace.
- UNI-1 is judged vs the static ex-ante line (B), never vs the nine; Binance quote_volume ranks throughout (Delta turnover history on
  disk is 400 days only).
- UNI-2's primary is B+gold vs B (ex-ante + gold), with A+gold vs A reported, and the pre-bull window (2020-08..2023-12) as an extra
  condition because gold's 2024-25 is in the sample.
- COST-2's claim is cost-only (|Delta| <= 0.08, CI containing 0) because `verify_tools/cost2_diag_out.txt` showed the Sharpe effect is
  position path that flips sign by sub-period.
- Whole-contract judgement at $1,000 on A (Delta contract values) and C; B unrounded (the 15 extras have no Delta contract).

## Could not verify / caveats carried
- Every external paper number remains as tagged by the verifiers ([UNVERIFIED]/[SECONDARY]); the plan's expectations cite the local
  diagnostics and repo tests first.
- Delta XAUTUSD daily candles from 2026-04-17 are not yet on disk (api.india.delta.exchange is reachable; the PAXG spot series covers the
  whole window, so UNI-2 can run without the stitch).
- TIME-3 on panel B needs ~1,150 monthly 1h zips from data.binance.vision; the A/C-only fallback is pre-registered.
