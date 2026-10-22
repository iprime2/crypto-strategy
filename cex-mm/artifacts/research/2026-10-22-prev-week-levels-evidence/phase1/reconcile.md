# Reconciliation of implementations X and Y (previous-week high / low study)

Plan: `research3/plan.md`, sha256 `8c7bf92317e2b18d5aac9ba001bb264a10039cdb2347f390a36ef0a0c782f19a`; reference `8c7bf92317e2b18d5aac9ba001bb264a10039cdb2347f390a36ef0a0c782f19a`; MATCH (unchanged). Nothing in implX/ or implY/ was edited. One read-only check imported implY/engine.py and left an `implY/__pycache__/` behind; it has been deleted, and no source or output file there changed (mtimes 16:20–16:24).

**Chosen results:** `/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research3/reconcile/final/results.json` (implementation Y's code, copied unchanged to `reconcile/final/` and re-run there; bit-identical to `implY/results.json` and its three event files).

## 1. Verdict

- results.json: 2,822 numbers compared (every leaf of panels A, B, C). 1,895 are exactly equal and 574 differ only by float noise (≤ 1e-9). 81 differ by more than that but stay inside the tolerance, and 272 are outside it. Every one of the 353 real differences traces to one of three causes, D1–D3 below. By cause: {'D1': 323, 'D1+D3': 9, 'D2': 3, 'D3': 18}. Outside tolerance: {'D1': 254, 'D1+D3': 7, 'D2': 3, 'D3': 8}.
- Tolerances: 1 event in a count, 0.1 bps in a mean, 0.01 in a bootstrap P or CI bound. Rates (hit, touch, reel) and Sharpe have no tolerance in the task. Here they are held to 1e-4 and 1e-3, and every miss on them is also traced.
- Event files, joined row by row on (coin, week_start, level_kind, pattern, horizon): A: X 108,591 rows, Y 108,576, common 108,576, X-only 15, Y-only 0, common rows with a different entry/exit/gross 15; B: X 299,547 rows, Y 299,385, common 299,385, X-only 162, Y-only 0, common rows with a different entry/exit/gross 186; C: X 29,580 rows, Y 29,574, common 29,574, X-only 6, Y-only 0, common rows with a different entry/exit/gross 0. Every X-only row and every differing row is pattern S. They are exactly the S events whose first 1 h close after the touch equals L exactly (D1).
- All F and B rows, all P1 rows, all level prices, and all touch and reel numbers agree. Outside D1 the largest |Δ gross| on a common row is A 1.5e-11 bps, B 1.5e-11 bps, C 1.8e-12 bps, which is float noise.
- Pass rules (plan §5): the gate outcome is the same under X and under the final numbers. No pattern passes the level-edge rules or the tradable rules (§4 below). The reconciliation changes no conclusion.

## 2. Disagreements, causes and resolutions

| id | what differs | cause in code | plan text | resolution |
|---|---|---|---|---|
| D1 | S events when a 1 h close equals L exactly: A 10 level-events, B 116, C 2 (X's own count of equal closes; Y counts 10 / 121 / 2 because it counts every equal close it meets in a scan). These are the only event-level differences. | X `engine.py` `level_events`, S loop: `if side*(cpx-L) > 0: break`, otherwise enter. So close == L counts as "inside" and enters at L. Y `engine.py` `level_events`, S loop: three-way. Beyond means break, strictly inside means enter, and equal means `n_equal += 1` and the scan continues. | "if a 1 h close back inside L comes within 4 h of the touch and before any 1 h close beyond L, enter at that close" | **Y.** Both readings are defensible, and Y's is the more literal. (a) Where the plan means a non-strict relation it says so: "at least r inside L", "≥ 99 %", "≥ 10 bps", "≥ 6 of the 9". Every unqualified relation it spells out is strict: high_t > L·(1+0.5 bp), D_H > 0, and "beyond L" (both read it as strict). (b) The plan's own step "O … always inside [PWL, PWH] … D_H = ln(PWH/O) > 0" only works if "inside" is strict. So a close exactly at L is neither "back inside L" nor "beyond L", and the scan goes on. X's reading, inside = not beyond, is a fair partition, but the plan text does not state it. |
| D2 | `coin_weeks_skipped`: A 20 vs 11, B 142 vs 117, C 9 vs 0, exactly one coin-week per coin. No used week, event, mean or test differs. | X `run.py`: candidate weeks run to `WIN_END_EXCL - 1` (A/B) or `G.end - G.dt` (C), so the partial trailing week (A/B 2026-09-28, C 2026-10-19) becomes a candidate that fails the 99 % rule. Y `run.py`: candidate weeks must lie wholly inside the window (A/B last 2026-09-21; C last full week 2026-10-12). | A, B: "2020-05-01..2026-09-30"; C: "(full weeks only …)"; "A coin-week is used only if it and the prior week each have ≥ 99 % of their bars; otherwise it is skipped and counted." | **Y.** C says "full weeks only" outright. For A and B, the week starting 2026-09-28 lies mostly outside the stated window, so it is not a coin-week of the panel. It is not a coin-week with a data gap. The 99 % rule is about missing bars, not about where the window is cut. |
| D3 | `daily_sharpe` (all 9 per panel; on S also D1). Largest |Δ| on F and B is 0.0107 (C.daily_sharpe.F.1h). | X `engine.daily_sharpe`: calendar from the first used week to the **last real exit day**: A 2026-09-22, B 2026-09-27, C 2026-10-16 (2,333 / 2,338 / 642 days). Y `run.panel_stats`: calendar from the first candidate Monday to the **last candidate Monday + 8 days**: A/B 2026-09-29, C 2026-10-20 (2,340 / 2,340 / 646 days). | "A daily P&L series per pattern (equal notional per event, booked on the exit day) gives an annualised Sharpe, as information." The plan gives no calendar. | **Y.** Both are defensible. Y's calendar is fixed by the study window plus the longest possible hold (a B confirmation at the last hourly close of the week, held 24 h). X's end date depends on when the last real exit happened to fall. The number is for information only and gates nothing. |
| D4 | No number differs. X adds a ≥ 99 % coverage rule on the P2 window; Y has none. This affects the P2 levels of 1 A coin-week (DOGE 2020-07-20) and 8 B coin-weeks (DOGE 2020-07-20; XRP, LTC, IOTA, TRX, VET, XLM, ZEC 2022-04-11). | X `engine.coin_levels`: `if nwin < 0.99*…: reason = window_coverage`. X lists this as "a rule the plan does not state". | P2 definition in §2: no coverage condition. | **Y** (no rule). Checked by running Y's `week_levels` on those 9 coin-weeks. Y creates one P2H level in each (P2L fails the unbroken or 10 bps test), and none of the 9 is touched in week w, so the rule changes no event and no number. |

Effect of D1 at the primary S horizon (4 h), X → final:

| panel | real n | real gross | real net | real−P1 diff | 95 % CI | P(diff ≤ 0) | P(net ≤ 0) |
|---|---|---|---|---|---|---|---|
| A | 1,316 / 1,311 | -15.41 / -15.48 | -30.03 / -30.10 | -10.63 / -10.70 | [-24.68, 2.92] / [-24.89, 2.96] | 0.9315 / 0.9325 | 1.0000 / 1.0000 |
| B | 3,755 / 3,710 | -14.71 / -14.12 | -29.33 / -28.74 | -13.10 / -12.50 | [-25.32, -2.78] / [-24.67, -2.59] | 0.9925 / 0.9935 | 1.0000 / 1.0000 |
| C | 338 / 336 | -25.88 / -25.79 | -40.50 / -40.41 | -7.50 / -7.41 | [-43.34, 20.85] / [-43.94, 20.87] | 0.6375 / 0.6345 | 0.9665 / 0.9645 |

D1 event detail: "dropped" means an S event in X that Y does not have (the next non-equal close was beyond L, or the 4 h window ran out). "Moved" means Y enters later, at the first strictly-inside close.

| panel | tie level-events | dropped (by control) | moved later (by control) | Y entry lag, hours: count | X entry px == L |
|---|---|---|---|---|---|
| A | 10 | 5 {'real': 5} | 5 {'real': 3, 'P2': 2} | {1: 5} | 10 of 10 |
| B | 116 | 54 {'real': 45, 'P2': 9} | 62 {'real': 54, 'P2': 8} | {1: 59, 2: 2, 3: 1} | 116 of 116 |
| C | 2 | 2 {'real': 2} | 0 {} | {} | 2 of 2 |

P1 levels never tie: they are irrational prices O·exp(m·D). Only PWH/PWL and P2 levels, which are traded prices, can equal a close exactly. Two cases checked by hand from the raw 5 m CSVs:
- ADA 2022-08-08 PWH 0.538. The touch bar opens at 05:50 (high 0.5392). The 06:00 hourly close is 0.538, exactly L. The next closes are 0.5423, 0.5398 and 0.5482, all beyond L. X shorts at 0.538. Y finds the next close beyond L and creates no S event.
- DOGE 2022-03-14 PWH 0.12444. The touch bar opens at 2022-03-19 14:55. The 15:00 close is 0.12444, exactly L. The 16:00 close is 0.12419, inside. X enters at 15:00 at 0.12444; Y enters at 16:00 at 0.12419.

## 3. Verification

1. **Each results.json follows from its own event files.** `recompute_from_events.py` is a third statistics layer, written separately. From each events_*.csv.gz alone it rebuilds every cell and every test: bootstrap with `default_rng(11).integers(0, W, (2000, W))` over all Mondays of the panel (334 for A and B, 92 for C), halves, and per-coin counts. On 1,638 numbers per implementation it matches implX/results.json and implY/results.json with 0 mismatches above 1e-9. So every results.json difference comes from the event files, and so from D1, plus D2 and D3, which are not event-based.
2. **The final run is deterministic.** Y's code (loaders.py, engine.py, run.py, test_engine.py, sha256 identical to implY) was re-run in `reconcile/final/`. The result: 2,822 of 2,822 results.json numbers are exactly equal to implY (max |Δ| 0), and all three event files are byte-identical after decompression.
3. **D1–D4 are the whole story.** `reconcile/X_patched/` is a copy of X's engine.py and run.py with four marked edits (`# RECONCILE`): the S tie rule, no P2-window coverage rule, full-week candidate weeks, and the Y Sharpe calendar. Its output matches final/results.json on all 2,822 numbers (0 outside tolerance, max |Δ| 1.8e-13), and every event row of A, B and C matches.
4. Tests: Y's `test_engine.py` passes in the copy. A new `final/test_s_ties.py` checks the chosen tie rule in 4 synthetic cases: an equal close then an inside close gives S one hour later; an equal close then a beyond close gives no S; four equal closes give no S; a strictly inside touch-bar close is unchanged. All 4 pass.

## 4. Pass-rule inputs at the primary horizons (plan §5), X → final

| pattern | A diff ≥ +5 and P ≤ 0.003 | A halves diff > 0 | A coins diff > 0 (≥ 6) | B diff > 0 | A net > 0, P(net ≤ 0) ≤ 0.003 | A halves net > 0 | A coins net > 0 (≥ 6) | B net > 0 | C net > 0 (n) | level edge | tradable |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F 4h | -26.19, P 1.0000 → -26.19, P 1.0000 | -33.33 / -19.41 → -33.33 / -19.41 | 0 → 0 | -16.72 → -16.72 | -42.47, P 1.0000 → -42.47, P 1.0000 | -43.02 / -41.95 → -43.02 / -41.95 | 0 → 0 | -25.62 → -25.62 | -51.37 (737) → -51.37 (737) | fail → fail | fail → fail |
| B 24h | -6.53, P 0.7670 → -6.53, P 0.7670 | -14.54 / 0.92 → -14.54 / 0.92 | 4 → 4 | -4.06 → -4.06 | 13.03, P 0.2820 → 13.03, P 0.2820 | 48.36 / -20.54 → 48.36 / -20.54 | 5 → 5 | -11.50 → -11.50 | -51.10 (675) → -51.10 (675) | fail → fail | fail → fail |
| S 4h | -10.63, P 0.9315 → -10.70, P 0.9325 | -11.87 / -9.63 → -12.19 / -9.49 | 1 → 1 | -13.10 → -12.50 | -30.03, P 1.0000 → -30.10, P 1.0000 | -33.22 / -27.20 → -33.54 / -27.07 | 0 → 0 | -29.33 → -28.74 | -40.50 (338) → -40.41 (336) | fail → fail | fail → fail |

## 5. Readings both implementations share (no disagreement; flagged for the adversarial check)

- The 11 DOGE coin-weeks before its first full prior week (A and B, 2020-05-04 to 2020-07-13) are counted as skipped. On panel A they are all 11 of the skips. The plan says "DOGE starts with its first full prior week after its 2020-07-10 listing", so a stricter count would leave them out. This changes only the count.
- D ≤ 0: the real level is scored and that side gets no P1 levels. This covers A 1/0, B 5/1 and C 3/2 coin-weeks (H/L). O equals PWH or PWL exactly everywhere except 2 H and 2 L coin-weeks on C, where the Delta week open lies outside [PWL, PWH]. The plan's "D_H, D_L > 0" fails in these coin-weeks.
- Reel "continued": a 5 m bar that reaches both C(1±r) and L is counted as not continued. On A this covers 347 of 2,422 real confirmations. Both report the sensitivity: 0.8679 if ties count as continued, 0.8458 if they are excluded.
- `coins_pos_diff` is literally real − P1 on every row, P2 rows included. Each implementation also keeps the real − own-control count in its diagnostics.
- S is not restricted to week w; B is (the plan restricts only B). F is filled at L on the touch bar even when that bar gaps through L. This fill optimism is for the adversarial check.

## 6. Every compared number (X / Y; final = Y exactly)

Status: "=" means identical to ≤ 1e-9. "Dn (in tol)" means it differs within the tolerance, with cause Dn. **bold** means outside the tolerance, with cause Dn. The machine-readable list of all 2,822 leaves, with |Δ|, tolerance and cause, is `reconcile/cmp_X_vs_Y.csv`.

### Panel A

| quantity | X / Y | status |
|---|---|---|
| coin_weeks_used | 2,995 / 2,995 | = |
| coin_weeks_skipped | 20 / 11 | **D2 out of tol** |
| touch_rates.any | 0.8007 / 0.8007 | = |
| touch_rates.pwh | 0.4728 / 0.4728 | = |
| touch_rates.pwl | 0.4260 / 0.4260 | = |
| reel.real.reject60 | 0.4417 / 0.4417 | = |
| reel.real.continued | 0.7246 / 0.7246 | = |
| reel.P1.reject60 | 0.5463 / 0.5463 | = |
| reel.P1.continued | 0.7048 / 0.7048 | = |
| reel.P2.reject60 | 0.4718 / 0.4718 | = |
| reel.P2.continued | 0.6784 / 0.6784 | = |
| daily_sharpe.F.1h | -1.6753 / -1.6728 | **D3 out of tol** |
| daily_sharpe.F.4h | -1.7844 / -1.7817 | **D3 out of tol** |
| daily_sharpe.F.24h | -0.9444 / -0.9430 | **D3 out of tol** |
| daily_sharpe.B.1h | -0.8851 / -0.8838 | **D3 out of tol** |
| daily_sharpe.B.4h | -0.1079 / -0.1077 | D3 (in tol) |
| daily_sharpe.B.24h | 0.1891 / 0.1888 | D3 (in tol) |
| daily_sharpe.S.1h | -1.2877 / -1.2669 | **D1+D3 out of tol** |
| daily_sharpe.S.4h | -1.2235 / -1.2205 | **D1+D3 out of tol** |
| daily_sharpe.S.24h | -0.8595 / -0.8596 | D1+D3 (in tol) |

Cells (bps; hit = share with net > 0):

| pattern | side | horizon | control | n | gross | net | hit | status |
|---|---|---|---|---|---|---|---|---|
| F | pooled | 1h | real | 2,692 / 2,692 | -17.650 / -17.650 | -27.080 / -27.080 | 0.4603 / 0.4603 | = |
| F | pooled | 1h | P1 | 11,600 / 11,600 | -0.863 / -0.863 | -10.293 / -10.293 | 0.5171 / 0.5171 | = |
| F | pooled | 1h | P2 | 568 / 568 | 26.796 / 26.796 | 17.366 / 17.366 | 0.5528 / 0.5528 | = |
| F | pooled | 4h | real | 2,692 / 2,692 | -33.040 / -33.040 | -42.470 / -42.470 | 0.4699 / 0.4699 | = |
| F | pooled | 4h | P1 | 11,600 / 11,600 | -6.846 / -6.846 | -16.276 / -16.276 | 0.5128 / 0.5128 | = |
| F | pooled | 4h | P2 | 568 / 568 | 29.437 / 29.437 | 20.007 / 20.007 | 0.5528 / 0.5528 | = |
| F | pooled | 24h | real | 2,692 / 2,692 | -62.934 / -62.934 | -72.364 / -72.364 | 0.5011 / 0.5011 | = |
| F | pooled | 24h | P1 | 11,600 / 11,600 | -33.684 / -33.684 | -43.114 / -43.114 | 0.5253 / 0.5253 | = |
| F | pooled | 24h | P2 | 568 / 568 | -59.606 / -59.606 | -69.036 / -69.036 | 0.5616 / 0.5616 | = |
| F | H | 1h | real | 1,416 / 1,416 | -33.797 / -33.797 | -43.227 / -43.227 | 0.4251 / 0.4251 | = |
| F | H | 1h | P1 | 6,002 / 6,002 | -22.237 / -22.237 | -31.667 / -31.667 | 0.4820 / 0.4820 | = |
| F | H | 1h | P2 | 282 / 282 | -25.246 / -25.246 | -34.676 / -34.676 | 0.5035 / 0.5035 | = |
| F | H | 4h | real | 1,416 / 1,416 | -49.382 / -49.382 | -58.812 / -58.812 | 0.4499 / 0.4499 | = |
| F | H | 4h | P1 | 6,002 / 6,002 | -28.440 / -28.440 | -37.870 / -37.870 | 0.4858 / 0.4858 | = |
| F | H | 4h | P2 | 282 / 282 | -28.191 / -28.191 | -37.621 / -37.621 | 0.4858 / 0.4858 | = |
| F | H | 24h | real | 1,416 / 1,416 | -132.176 / -132.176 | -141.606 / -141.606 | 0.4725 / 0.4725 | = |
| F | H | 24h | P1 | 6,002 / 6,002 | -100.715 / -100.715 | -110.145 / -110.145 | 0.4963 / 0.4963 | = |
| F | H | 24h | P2 | 282 / 282 | -222.747 / -222.747 | -232.177 / -232.177 | 0.5461 / 0.5461 | = |
| F | L | 1h | real | 1,276 / 1,276 | 0.267 / 0.267 | -9.163 / -9.163 | 0.4992 / 0.4992 | = |
| F | L | 1h | P1 | 5,598 / 5,598 | 22.054 / 22.054 | 12.624 / 12.624 | 0.5547 / 0.5547 | = |
| F | L | 1h | P2 | 286 / 286 | 78.111 / 78.111 | 68.681 / 68.681 | 0.6014 / 0.6014 | = |
| F | L | 4h | real | 1,276 / 1,276 | -14.904 / -14.904 | -24.334 / -24.334 | 0.4922 / 0.4922 | = |
| F | L | 4h | P1 | 5,598 / 5,598 | 16.305 / 16.305 | 6.875 / 6.875 | 0.5416 / 0.5416 | = |
| F | L | 4h | P2 | 286 / 286 | 86.259 / 86.259 | 76.829 / 76.829 | 0.6189 / 0.6189 | = |
| F | L | 24h | real | 1,276 / 1,276 | 13.906 / 13.906 | 4.476 / 4.476 | 0.5329 / 0.5329 | = |
| F | L | 24h | P1 | 5,598 / 5,598 | 38.185 / 38.185 | 28.755 / 28.755 | 0.5563 / 0.5563 | = |
| F | L | 24h | P2 | 286 / 286 | 101.253 / 101.253 | 91.823 / 91.823 | 0.5769 / 0.5769 | = |
| B | pooled | 1h | real | 2,422 / 2,422 | 3.074 / 3.074 | -11.546 / -11.546 | 0.3840 / 0.3840 | = |
| B | pooled | 1h | P1 | 10,319 / 10,319 | 5.428 / 5.428 | -9.192 / -9.192 | 0.3779 / 0.3779 | = |
| B | pooled | 1h | P2 | 482 / 482 | -4.688 / -4.688 | -19.308 / -19.308 | 0.3776 / 0.3776 | = |
| B | pooled | 4h | real | 2,422 / 2,422 | 12.299 / 12.299 | -2.321 / -2.321 | 0.4430 / 0.4430 | = |
| B | pooled | 4h | P1 | 10,319 / 10,319 | 9.823 / 9.823 | -4.797 / -4.797 | 0.4358 / 0.4358 | = |
| B | pooled | 4h | P2 | 482 / 482 | -0.455 / -0.455 | -15.075 / -15.075 | 0.4108 / 0.4108 | = |
| B | pooled | 24h | real | 2,422 / 2,422 | 27.647 / 27.647 | 13.027 / 13.027 | 0.4517 / 0.4517 | = |
| B | pooled | 24h | P1 | 10,319 / 10,319 | 34.175 / 34.175 | 19.555 / 19.555 | 0.4498 / 0.4498 | = |
| B | pooled | 24h | P2 | 482 / 482 | 59.874 / 59.874 | 45.254 / 45.254 | 0.4025 / 0.4025 | = |
| B | H | 1h | real | 1,304 / 1,304 | 9.556 / 9.556 | -5.064 / -5.064 | 0.4049 / 0.4049 | = |
| B | H | 1h | P1 | 5,471 / 5,471 | 11.202 / 11.202 | -3.418 / -3.418 | 0.4036 / 0.4036 | = |
| B | H | 1h | P2 | 250 / 250 | 0.912 / 0.912 | -13.708 / -13.708 | 0.4080 / 0.4080 | = |
| B | H | 4h | real | 1,304 / 1,304 | 23.340 / 23.340 | 8.720 / 8.720 | 0.4578 / 0.4578 | = |
| B | H | 4h | P1 | 5,471 / 5,471 | 20.467 / 20.467 | 5.847 / 5.847 | 0.4582 / 0.4582 | = |
| B | H | 4h | P2 | 250 / 250 | 23.631 / 23.631 | 9.011 / 9.011 | 0.4160 / 0.4160 | = |
| B | H | 24h | real | 1,304 / 1,304 | 96.007 / 96.007 | 81.387 / 81.387 | 0.4854 / 0.4854 | = |
| B | H | 24h | P1 | 5,471 / 5,471 | 91.574 / 91.574 | 76.954 / 76.954 | 0.4708 / 0.4708 | = |
| B | H | 24h | P2 | 250 / 250 | 186.886 / 186.886 | 172.266 / 172.266 | 0.4200 / 0.4200 | = |
| B | L | 1h | real | 1,118 / 1,118 | -4.487 / -4.487 | -19.107 / -19.107 | 0.3596 / 0.3596 | = |
| B | L | 1h | P1 | 4,848 / 4,848 | -1.087 / -1.087 | -15.707 / -15.707 | 0.3490 / 0.3490 | = |
| B | L | 1h | P2 | 232 / 232 | -10.723 / -10.723 | -25.343 / -25.343 | 0.3448 / 0.3448 | = |
| B | L | 4h | real | 1,118 / 1,118 | -0.579 / -0.579 | -15.199 / -15.199 | 0.4258 / 0.4258 | = |
| B | L | 4h | P1 | 4,848 / 4,848 | -2.190 / -2.190 | -16.810 / -16.810 | 0.4105 / 0.4105 | = |
| B | L | 4h | P2 | 232 / 232 | -26.410 / -26.410 | -41.030 / -41.030 | 0.4052 / 0.4052 | = |
| B | L | 24h | real | 1,118 / 1,118 | -52.086 / -52.086 | -66.706 / -66.706 | 0.4123 / 0.4123 | = |
| B | L | 24h | P1 | 4,848 / 4,848 | -30.599 / -30.599 | -45.219 / -45.219 | 0.4259 / 0.4259 | = |
| B | L | 24h | P2 | 232 / 232 | -76.992 / -76.992 | -91.612 / -91.612 | 0.3836 / 0.3836 | = |
| S | pooled | 1h | real | 1,316 / 1,311 | -13.903 / -13.582 | -28.523 / -28.202 | 0.4407 / 0.4416 | **D1 out of tol** |
| S | pooled | 1h | P1 | 6,482 / 6,482 | -5.596 / -5.596 | -20.216 / -20.216 | 0.4421 / 0.4421 | = |
| S | pooled | 1h | P2 | 316 / 316 | 8.440 / 8.191 | -6.180 / -6.429 | 0.4778 / 0.4747 | **D1 out of tol** |
| S | pooled | 4h | real | 1,316 / 1,311 | -15.413 / -15.483 | -30.033 / -30.103 | 0.4772 / 0.4767 | **D1 out of tol** |
| S | pooled | 4h | P1 | 6,482 / 6,482 | -4.779 / -4.779 | -19.399 / -19.399 | 0.4838 / 0.4838 | = |
| S | pooled | 4h | P2 | 316 / 316 | 13.897 / 13.972 | -0.723 / -0.648 | 0.5095 / 0.5095 | D1 (in tol) |
| S | pooled | 24h | real | 1,316 / 1,311 | -29.247 / -29.489 | -43.867 / -44.109 | 0.5213 / 0.5217 | **D1 out of tol** |
| S | pooled | 24h | P1 | 6,482 / 6,482 | -6.680 / -6.680 | -21.300 / -21.300 | 0.5262 / 0.5262 | = |
| S | pooled | 24h | P2 | 316 / 316 | 44.688 / 44.792 | 30.068 / 30.172 | 0.5380 / 0.5411 | **D1 out of tol** |
| S | H | 1h | real | 648 / 645 | -5.414 / -5.283 | -20.034 / -19.903 | 0.4213 / 0.4217 | **D1 out of tol** |
| S | H | 1h | P1 | 3,180 / 3,180 | -5.005 / -5.005 | -19.625 / -19.625 | 0.4267 / 0.4267 | = |
| S | H | 1h | P2 | 140 / 140 | 6.956 / 6.666 | -7.664 / -7.954 | 0.4357 / 0.4357 | **D1 out of tol** |
| S | H | 4h | real | 648 / 645 | -23.210 / -23.400 | -37.830 / -38.020 | 0.4506 / 0.4496 | **D1 out of tol** |
| S | H | 4h | P1 | 3,180 / 3,180 | -6.504 / -6.504 | -21.124 / -21.124 | 0.4723 / 0.4723 | = |
| S | H | 4h | P2 | 140 / 140 | 18.975 / 19.049 | 4.355 / 4.429 | 0.5143 / 0.5143 | D1 (in tol) |
| S | H | 24h | real | 648 / 645 | -63.309 / -63.454 | -77.929 / -78.074 | 0.5123 / 0.5132 | **D1 out of tol** |
| S | H | 24h | P1 | 3,180 / 3,180 | -29.578 / -29.578 | -44.198 / -44.198 | 0.5220 / 0.5220 | = |
| S | H | 24h | P2 | 140 / 140 | 32.924 / 33.242 | 18.304 / 18.622 | 0.5143 / 0.5214 | **D1 out of tol** |
| S | L | 1h | real | 668 / 666 | -22.138 / -21.620 | -36.758 / -36.240 | 0.4596 / 0.4610 | **D1 out of tol** |
| S | L | 1h | P1 | 3,302 / 3,302 | -6.164 / -6.164 | -20.784 / -20.784 | 0.4570 / 0.4570 | = |
| S | L | 1h | P2 | 176 / 176 | 9.621 / 9.404 | -4.999 / -5.216 | 0.5114 / 0.5057 | **D1 out of tol** |
| S | L | 4h | real | 668 / 666 | -7.849 / -7.816 | -22.469 / -22.436 | 0.5030 / 0.5030 | **D1 out of tol** |
| S | L | 4h | P1 | 3,302 / 3,302 | -3.119 / -3.119 | -17.739 / -17.739 | 0.4949 / 0.4949 | = |
| S | L | 4h | P2 | 176 / 176 | 9.858 / 9.933 | -4.762 / -4.687 | 0.5057 / 0.5057 | D1 (in tol) |
| S | L | 24h | real | 668 / 666 | 3.796 / 3.404 | -10.824 / -11.216 | 0.5299 / 0.5300 | **D1 out of tol** |
| S | L | 24h | P1 | 3,302 / 3,302 | 15.372 / 15.372 | 0.752 / 0.752 | 0.5303 / 0.5303 | = |
| S | L | 24h | P2 | 176 / 176 | 54.045 / 53.980 | 39.425 / 39.360 | 0.5568 / 0.5568 | D1 (in tol) |

Tests (real − control, gross bps; week-cluster bootstrap):

| pattern | horizon | control | diff | CI lo | CI hi | P(diff ≤ 0) | real net | P(net ≤ 0) | status |
|---|---|---|---|---|---|---|---|---|---|
| F | 1h | P1 | -16.788 / -16.788 | -23.315 / -23.315 | -10.498 / -10.498 | 1.0000 / 1.0000 | -27.080 / -27.080 | 1.0000 / 1.0000 | = |
| F | 1h | P2 | -44.447 / -44.447 | -75.154 / -75.154 | -13.095 / -13.095 | 0.9960 / 0.9960 | -27.080 / -27.080 | 1.0000 / 1.0000 | = |
| F | 4h | P1 | -26.193 / -26.193 | -34.578 / -34.578 | -17.942 / -17.942 | 1.0000 / 1.0000 | -42.470 / -42.470 | 1.0000 / 1.0000 | = |
| F | 4h | P2 | -62.477 / -62.477 | -100.413 / -100.413 | -24.855 / -24.855 | 0.9990 / 0.9990 | -42.470 / -42.470 | 1.0000 / 1.0000 | = |
| F | 24h | P1 | -29.250 / -29.250 | -42.984 / -42.984 | -15.551 / -15.551 | 1.0000 / 1.0000 | -72.364 / -72.364 | 0.9995 / 0.9995 | = |
| F | 24h | P2 | -3.328 / -3.328 | -133.958 / -133.958 | 203.128 / 203.128 | 0.5645 / 0.5645 | -72.364 / -72.364 | 0.9995 / 0.9995 | = |
| B | 1h | P1 | -2.355 / -2.355 | -8.625 / -8.625 | 3.771 / 3.771 | 0.7655 / 0.7655 | -11.546 / -11.546 | 0.9810 / 0.9810 | = |
| B | 1h | P2 | 7.762 / 7.762 | -21.745 / -21.745 | 31.976 / 31.976 | 0.2720 / 0.2720 | -11.546 / -11.546 | 0.9810 / 0.9810 | = |
| B | 4h | P1 | 2.476 / 2.476 | -8.255 / -8.255 | 11.524 / 11.524 | 0.2925 / 0.2925 | -2.321 / -2.321 | 0.5795 / 0.5795 | = |
| B | 4h | P2 | 12.754 / 12.754 | -24.188 / -24.188 | 47.979 / 47.979 | 0.2540 / 0.2540 | -2.321 / -2.321 | 0.5795 / 0.5795 | = |
| B | 24h | P1 | -6.528 / -6.528 | -23.988 / -23.988 | 9.934 / 9.934 | 0.7670 / 0.7670 | 13.027 / 13.027 | 0.2820 / 0.2820 | = |
| B | 24h | P2 | -32.227 / -32.227 | -226.994 / -226.994 | 95.429 / 95.429 | 0.5995 / 0.5995 | 13.027 / 13.027 | 0.2820 / 0.2820 | = |
| S | 1h | P1 | -8.308 / -7.987 | -23.202 / -22.810 | 3.924 / 4.439 | 0.8885 / 0.8780 | -28.523 / -28.202 | 1.0000 / 1.0000 | **D1 out of tol** |
| S | 1h | P2 | -22.343 / -21.774 | -49.708 / -48.733 | 2.427 / 3.118 | 0.9630 / 0.9610 | -28.523 / -28.202 | 1.0000 / 1.0000 | **D1 out of tol** |
| S | 4h | P1 | -10.634 / -10.704 | -24.684 / -24.888 | 2.925 / 2.960 | 0.9315 / 0.9325 | -30.033 / -30.103 | 1.0000 / 1.0000 | **D1 out of tol** |
| S | 4h | P2 | -29.310 / -29.455 | -66.825 / -67.028 | 2.308 / 2.342 | 0.9660 / 0.9665 | -30.033 / -30.103 | 1.0000 / 1.0000 | **D1 out of tol** |
| S | 24h | P1 | -22.567 / -22.810 | -50.773 / -51.373 | 5.058 / 5.138 | 0.9410 / 0.9430 | -43.867 / -44.109 | 0.9870 / 0.9875 | **D1 out of tol** |
| S | 24h | P2 | -73.934 / -74.282 | -143.735 / -144.657 | -13.089 / -13.336 | 0.9895 / 0.9895 | -43.867 / -44.109 | 0.9870 / 0.9875 | **D1 out of tol** |

Halves and per-coin counts:

| pattern | horizon | control | H1 diff | H1 real net | H1 n | H2 diff | H2 real net | H2 n | coins_pos_diff | coins_pos_net | status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F | 1h | P1 | -25.918 / -25.918 | -33.623 / -33.623 | 1,309 / 1,309 | -8.132 / -8.132 | -20.888 / -20.888 | 1,383 / 1,383 | 0 / 0 | 0 / 0 | = |
| F | 1h | P2 | -87.827 / -87.827 | -33.623 / -33.623 | 1,309 / 1,309 | -2.440 / -2.440 | -20.888 / -20.888 | 1,383 / 1,383 | 0 / 0 | 0 / 0 | = |
| F | 4h | P1 | -33.327 / -33.327 | -43.016 / -43.016 | 1,309 / 1,309 | -19.406 / -19.406 | -41.952 / -41.952 | 1,383 / 1,383 | 0 / 0 | 0 / 0 | = |
| F | 4h | P2 | -107.662 / -107.662 | -43.016 / -43.016 | 1,309 / 1,309 | -18.560 / -18.560 | -41.952 / -41.952 | 1,383 / 1,383 | 0 / 0 | 0 / 0 | = |
| F | 24h | P1 | -43.351 / -43.351 | -129.610 / -129.610 | 1,309 / 1,309 | -16.136 / -16.136 | -18.181 / -18.181 | 1,383 / 1,383 | 0 / 0 | 1 / 1 | = |
| F | 24h | P2 | -14.896 / -14.896 | -129.610 / -129.610 | 1,309 / 1,309 | 6.446 / 6.446 | -18.181 / -18.181 | 1,383 / 1,383 | 0 / 0 | 1 / 1 | = |
| B | 1h | P1 | -4.566 / -4.566 | -19.775 / -19.775 | 1,180 / 1,180 | -0.230 / -0.230 | -3.728 / -3.728 | 1,242 / 1,242 | 3 / 3 | 0 / 0 | = |
| B | 1h | P2 | 32.699 / 32.699 | -19.775 / -19.775 | 1,180 / 1,180 | -16.771 / -16.771 | -3.728 / -3.728 | 1,242 / 1,242 | 3 / 3 | 0 / 0 | = |
| B | 4h | P1 | 1.548 / 1.548 | -11.295 / -11.295 | 1,180 / 1,180 | 3.389 / 3.389 | 6.205 / 6.205 | 1,242 / 1,242 | 5 / 5 | 4 / 4 | = |
| B | 4h | P2 | 58.268 / 58.268 | -11.295 / -11.295 | 1,180 / 1,180 | -31.869 / -31.869 | 6.205 / 6.205 | 1,242 / 1,242 | 5 / 5 | 4 / 4 | = |
| B | 24h | P1 | -14.542 / -14.542 | 48.360 / 48.360 | 1,180 / 1,180 | 0.919 / 0.919 | -20.542 / -20.542 | 1,242 / 1,242 | 4 / 4 | 5 / 5 | = |
| B | 24h | P2 | -17.795 / -17.795 | 48.360 / 48.360 | 1,180 / 1,180 | -45.410 / -45.410 | -20.542 / -20.542 | 1,242 / 1,242 | 4 / 4 | 5 / 5 | = |
| S | 1h | P1 | -9.742 / -9.159 | -27.034 / -26.451 | 619 / 615 | -6.895 / -6.799 | -29.845 / -29.750 | 697 / 696 | 3 / 3 | 0 / 0 | **D1 out of tol** |
| S | 1h | P2 | -23.828 / -23.244 | -27.034 / -26.451 | 619 / 615 | -20.803 / -20.219 | -29.845 / -29.750 | 697 / 696 | 3 / 3 | 0 / 0 | **D1 out of tol** |
| S | 4h | P1 | -11.872 / -12.191 | -33.219 / -33.538 | 619 / 615 | -9.626 / -9.491 | -27.204 / -27.068 | 697 / 696 | 1 / 1 | 0 / 0 | **D1 out of tol** |
| S | 4h | P2 | -15.100 / -15.419 | -33.219 / -33.538 | 619 / 615 | -43.229 / -43.241 | -27.204 / -27.068 | 697 / 696 | 1 / 1 | 0 / 0 | **D1 out of tol** |
| S | 24h | P1 | -27.930 / -28.255 | -73.627 / -73.952 | 619 / 615 | -18.960 / -19.263 | -17.437 / -17.740 | 697 / 696 | 3 / 3 | 0 / 0 | **D1 out of tol** |
| S | 24h | P2 | -71.698 / -72.023 | -73.627 / -73.952 | 619 / 615 | -78.309 / -78.817 | -17.437 / -17.740 | 697 / 696 | 3 / 3 | 0 / 0 | **D1 out of tol** |

### Panel B

| quantity | X / Y | status |
|---|---|---|
| coin_weeks_used | 8,233 / 8,233 | = |
| coin_weeks_skipped | 142 / 117 | **D2 out of tol** |
| touch_rates.any | 0.8018 / 0.8018 | = |
| touch_rates.pwh | 0.4562 / 0.4562 | = |
| touch_rates.pwl | 0.4437 / 0.4437 | = |
| daily_sharpe.F.1h | -1.0547 / -1.0543 | D3 (in tol) |
| daily_sharpe.F.4h | -1.2894 / -1.2888 | D3 (in tol) |
| daily_sharpe.F.24h | -0.8818 / -0.8814 | D3 (in tol) |
| daily_sharpe.B.1h | -1.1163 / -1.1158 | D3 (in tol) |
| daily_sharpe.B.4h | -0.5206 / -0.5204 | D3 (in tol) |
| daily_sharpe.B.24h | -0.2430 / -0.2429 | D3 (in tol) |
| daily_sharpe.S.1h | -1.3509 / -1.3760 | **D1+D3 out of tol** |
| daily_sharpe.S.4h | -1.2203 / -1.2199 | D1+D3 (in tol) |
| daily_sharpe.S.24h | -0.6138 / -0.6204 | **D1+D3 out of tol** |

Cells (bps; hit = share with net > 0):

| pattern | side | horizon | control | n | gross | net | hit | status |
|---|---|---|---|---|---|---|---|---|
| F | pooled | 1h | real | 7,409 / 7,409 | -3.115 / -3.115 | -12.545 / -12.545 | 0.4473 / 0.4473 | = |
| F | pooled | 1h | P1 | 31,925 / 31,925 | 8.385 / 8.385 | -1.045 / -1.045 | 0.5008 / 0.5008 | = |
| F | pooled | 1h | P2 | 1,575 / 1,575 | 33.201 / 33.201 | 23.771 / 23.771 | 0.5162 / 0.5162 | = |
| F | pooled | 4h | real | 7,409 / 7,409 | -16.193 / -16.193 | -25.623 / -25.623 | 0.4917 / 0.4917 | = |
| F | pooled | 4h | P1 | 31,925 / 31,925 | 0.531 / 0.531 | -8.899 / -8.899 | 0.5217 / 0.5217 | = |
| F | pooled | 4h | P2 | 1,575 / 1,575 | 31.555 / 31.555 | 22.125 / 22.125 | 0.5422 / 0.5422 | = |
| F | pooled | 24h | real | 7,409 / 7,409 | -32.829 / -32.829 | -42.259 / -42.259 | 0.5169 / 0.5169 | = |
| F | pooled | 24h | P1 | 31,925 / 31,925 | -9.133 / -9.133 | -18.563 / -18.563 | 0.5286 / 0.5286 | = |
| F | pooled | 24h | P2 | 1,575 / 1,575 | -20.634 / -20.634 | -30.064 / -30.064 | 0.5422 / 0.5422 | = |
| F | H | 1h | real | 3,756 / 3,756 | -19.099 / -19.099 | -28.529 / -28.529 | 0.4092 / 0.4092 | = |
| F | H | 1h | P1 | 16,052 / 16,052 | -7.987 / -7.987 | -17.417 / -17.417 | 0.4684 / 0.4684 | = |
| F | H | 1h | P2 | 777 / 777 | -14.288 / -14.288 | -23.718 / -23.718 | 0.4530 / 0.4530 | = |
| F | H | 4h | real | 3,756 / 3,756 | -28.775 / -28.775 | -38.205 / -38.205 | 0.4774 / 0.4774 | = |
| F | H | 4h | P1 | 16,052 / 16,052 | -12.765 / -12.765 | -22.195 / -22.195 | 0.5044 / 0.5044 | = |
| F | H | 4h | P2 | 777 / 777 | -21.689 / -21.689 | -31.119 / -31.119 | 0.4801 / 0.4801 | = |
| F | H | 24h | real | 3,756 / 3,756 | -65.566 / -65.566 | -74.996 / -74.996 | 0.5053 / 0.5053 | = |
| F | H | 24h | P1 | 16,052 / 16,052 | -44.249 / -44.249 | -53.679 / -53.679 | 0.5176 / 0.5176 | = |
| F | H | 24h | P2 | 777 / 777 | -116.827 / -116.827 | -126.257 / -126.257 | 0.5367 / 0.5367 | = |
| F | L | 1h | real | 3,653 / 3,653 | 13.320 / 13.320 | 3.890 / 3.890 | 0.4864 / 0.4864 | = |
| F | L | 1h | P1 | 15,873 / 15,873 | 24.942 / 24.942 | 15.512 / 15.512 | 0.5336 / 0.5336 | = |
| F | L | 1h | P2 | 798 / 798 | 79.441 / 79.441 | 70.011 / 70.011 | 0.5777 / 0.5777 | = |
| F | L | 4h | real | 3,653 / 3,653 | -3.256 / -3.256 | -12.686 / -12.686 | 0.5064 / 0.5064 | = |
| F | L | 4h | P1 | 15,873 / 15,873 | 13.977 / 13.977 | 4.547 / 4.547 | 0.5391 / 0.5391 | = |
| F | L | 4h | P2 | 798 / 798 | 83.399 / 83.399 | 73.969 / 73.969 | 0.6028 / 0.6028 | = |
| F | L | 24h | real | 3,653 / 3,653 | 0.831 / 0.831 | -8.599 / -8.599 | 0.5289 / 0.5289 | = |
| F | L | 24h | P1 | 15,873 / 15,873 | 26.379 / 26.379 | 16.949 / 16.949 | 0.5397 / 0.5397 | = |
| F | L | 24h | P2 | 798 / 798 | 73.029 / 73.029 | 63.599 / 63.599 | 0.5476 / 0.5476 | = |
| B | pooled | 1h | real | 6,694 / 6,694 | 3.198 / 3.198 | -11.422 / -11.422 | 0.3923 / 0.3923 | = |
| B | pooled | 1h | P1 | 28,470 / 28,470 | 3.390 / 3.390 | -11.230 / -11.230 | 0.3809 / 0.3809 | = |
| B | pooled | 1h | P2 | 1,347 / 1,347 | -0.922 / -0.922 | -15.542 / -15.542 | 0.3957 / 0.3957 | = |
| B | pooled | 4h | real | 6,694 / 6,694 | 5.972 / 5.972 | -8.648 / -8.648 | 0.4314 / 0.4314 | = |
| B | pooled | 4h | P1 | 28,470 / 28,470 | 5.597 / 5.597 | -9.023 / -9.023 | 0.4261 / 0.4261 | = |
| B | pooled | 4h | P2 | 1,347 / 1,347 | 0.180 / 0.180 | -14.440 / -14.440 | 0.4143 / 0.4143 | = |
| B | pooled | 24h | real | 6,694 / 6,694 | 3.122 / 3.122 | -11.498 / -11.498 | 0.4386 / 0.4386 | = |
| B | pooled | 24h | P1 | 28,470 / 28,470 | 7.180 / 7.180 | -7.440 / -7.440 | 0.4408 / 0.4408 | = |
| B | pooled | 24h | P2 | 1,347 / 1,347 | 17.665 / 17.665 | 3.045 / 3.045 | 0.4239 / 0.4239 | = |
| B | H | 1h | real | 3,460 / 3,460 | 1.470 / 1.470 | -13.150 / -13.150 | 0.4006 / 0.4006 | = |
| B | H | 1h | P1 | 14,600 / 14,600 | 2.911 / 2.911 | -11.709 / -11.709 | 0.3903 / 0.3903 | = |
| B | H | 1h | P2 | 689 / 689 | 7.936 / 7.936 | -6.684 / -6.684 | 0.4151 / 0.4151 | = |
| B | H | 4h | real | 3,460 / 3,460 | 8.832 / 8.832 | -5.788 / -5.788 | 0.4367 / 0.4367 | = |
| B | H | 4h | P1 | 14,600 / 14,600 | 10.518 / 10.518 | -4.102 / -4.102 | 0.4382 / 0.4382 | = |
| B | H | 4h | P2 | 689 / 689 | 17.829 / 17.829 | 3.209 / 3.209 | 0.4296 / 0.4296 | = |
| B | H | 24h | real | 3,460 / 3,460 | 31.609 / 31.609 | 16.989 / 16.989 | 0.4468 / 0.4468 | = |
| B | H | 24h | P1 | 14,600 / 14,600 | 34.429 / 34.429 | 19.809 / 19.809 | 0.4496 / 0.4496 | = |
| B | H | 24h | P2 | 689 / 689 | 98.512 / 98.512 | 83.892 / 83.892 | 0.4369 / 0.4369 | = |
| B | L | 1h | real | 3,234 / 3,234 | 5.046 / 5.046 | -9.574 / -9.574 | 0.3834 / 0.3834 | = |
| B | L | 1h | P1 | 13,870 / 13,870 | 3.895 / 3.895 | -10.725 / -10.725 | 0.3709 / 0.3709 | = |
| B | L | 1h | P2 | 658 / 658 | -10.197 / -10.197 | -24.817 / -24.817 | 0.3754 / 0.3754 | = |
| B | L | 4h | real | 3,234 / 3,234 | 2.912 / 2.912 | -11.708 / -11.708 | 0.4258 / 0.4258 | = |
| B | L | 4h | P1 | 13,870 / 13,870 | 0.416 / 0.416 | -14.204 / -14.204 | 0.4133 / 0.4133 | = |
| B | L | 4h | P2 | 658 / 658 | -18.301 / -18.301 | -32.921 / -32.921 | 0.3982 / 0.3982 | = |
| B | L | 24h | real | 3,234 / 3,234 | -27.355 / -27.355 | -41.975 / -41.975 | 0.4298 / 0.4298 | = |
| B | L | 24h | P1 | 13,870 / 13,870 | -21.504 / -21.504 | -36.124 / -36.124 | 0.4315 / 0.4315 | = |
| B | L | 24h | P2 | 658 / 658 | -66.991 / -66.991 | -81.611 / -81.611 | 0.4103 / 0.4103 | = |
| S | pooled | 1h | real | 3,755 / 3,710 | -10.036 / -9.837 | -24.656 / -24.457 | 0.4517 / 0.4518 | **D1 out of tol** |
| S | pooled | 1h | P1 | 17,782 / 17,782 | -4.421 / -4.421 | -19.041 / -19.041 | 0.4538 / 0.4538 | = |
| S | pooled | 1h | P2 | 892 / 883 | -1.329 / -0.988 | -15.949 / -15.608 | 0.4518 / 0.4553 | **D1 out of tol** |
| S | pooled | 4h | real | 3,755 / 3,710 | -14.714 / -14.117 | -29.334 / -28.737 | 0.4847 / 0.4825 | **D1 out of tol** |
| S | pooled | 4h | P1 | 17,782 / 17,782 | -1.613 / -1.613 | -16.233 / -16.233 | 0.4962 / 0.4962 | = |
| S | pooled | 4h | P2 | 892 / 883 | 3.549 / 4.334 | -11.071 / -10.286 | 0.5011 / 0.5062 | **D1 out of tol** |
| S | pooled | 24h | real | 3,755 / 3,710 | -12.360 / -12.785 | -26.980 / -27.405 | 0.5318 / 0.5313 | **D1 out of tol** |
| S | pooled | 24h | P1 | 17,782 / 17,782 | 4.080 / 4.080 | -10.540 / -10.540 | 0.5306 / 0.5306 | = |
| S | pooled | 24h | P2 | 892 / 883 | -2.007 / -2.698 | -16.627 / -17.318 | 0.5314 / 0.5323 | **D1 out of tol** |
| S | H | 1h | real | 1,791 / 1,762 | -5.913 / -5.742 | -20.533 / -20.362 | 0.4216 / 0.4217 | **D1 out of tol** |
| S | H | 1h | P1 | 8,570 / 8,570 | -2.218 / -2.218 | -16.838 / -16.838 | 0.4398 / 0.4398 | = |
| S | H | 1h | P2 | 395 / 389 | 5.955 / 6.739 | -8.665 / -7.881 | 0.4304 / 0.4370 | **D1 out of tol** |
| S | H | 4h | real | 1,791 / 1,762 | -16.587 / -15.627 | -31.207 / -30.247 | 0.4768 / 0.4722 | **D1 out of tol** |
| S | H | 4h | P1 | 8,570 / 8,570 | -0.028 / -0.028 | -14.648 / -14.648 | 0.4917 / 0.4917 | = |
| S | H | 4h | P2 | 395 / 389 | 8.142 / 10.177 | -6.478 / -4.443 | 0.4835 / 0.4910 | **D1 out of tol** |
| S | H | 24h | real | 1,791 / 1,762 | -15.515 / -14.711 | -30.135 / -29.331 | 0.5265 / 0.5261 | **D1 out of tol** |
| S | H | 24h | P1 | 8,570 / 8,570 | -2.519 / -2.519 | -17.139 / -17.139 | 0.5316 / 0.5316 | = |
| S | H | 24h | P2 | 395 / 389 | -22.145 / -22.145 | -36.765 / -36.765 | 0.5342 / 0.5373 | **D1 out of tol** |
| S | L | 1h | real | 1,964 / 1,948 | -13.796 / -13.540 | -28.416 / -28.160 | 0.4791 / 0.4790 | **D1 out of tol** |
| S | L | 1h | P1 | 9,212 / 9,212 | -6.470 / -6.470 | -21.090 / -21.090 | 0.4669 / 0.4669 | = |
| S | L | 1h | P2 | 497 / 494 | -7.119 / -7.071 | -21.739 / -21.691 | 0.4688 / 0.4696 | **D1 out of tol** |
| S | L | 4h | real | 1,964 / 1,948 | -13.006 / -12.751 | -27.626 / -27.371 | 0.4919 / 0.4918 | **D1 out of tol** |
| S | L | 4h | P1 | 9,212 / 9,212 | -3.087 / -3.087 | -17.707 / -17.707 | 0.5003 / 0.5003 | = |
| S | L | 4h | P2 | 497 / 494 | -0.100 / -0.267 | -14.720 / -14.887 | 0.5151 / 0.5182 | **D1 out of tol** |
| S | L | 24h | real | 1,964 / 1,948 | -9.482 / -11.043 | -24.102 / -25.663 | 0.5367 / 0.5359 | **D1 out of tol** |
| S | L | 24h | P1 | 9,212 / 9,212 | 10.219 / 10.219 | -4.401 / -4.401 | 0.5296 / 0.5296 | = |
| S | L | 24h | P2 | 497 / 494 | 13.998 / 12.614 | -0.622 / -2.006 | 0.5292 / 0.5283 | **D1 out of tol** |

Tests (real − control, gross bps; week-cluster bootstrap):

| pattern | horizon | control | diff | CI lo | CI hi | P(diff ≤ 0) | real net | P(net ≤ 0) | status |
|---|---|---|---|---|---|---|---|---|---|
| F | 1h | P1 | -11.500 / -11.500 | -16.339 / -16.339 | -6.452 / -6.452 | 1.0000 / 1.0000 | -12.545 / -12.545 | 0.9935 / 0.9935 | = |
| F | 1h | P2 | -36.316 / -36.316 | -56.347 / -56.347 | -17.190 / -17.190 | 1.0000 / 1.0000 | -12.545 / -12.545 | 0.9935 / 0.9935 | = |
| F | 4h | P1 | -16.724 / -16.724 | -22.570 / -22.570 | -10.789 / -10.789 | 1.0000 / 1.0000 | -25.623 / -25.623 | 1.0000 / 1.0000 | = |
| F | 4h | P2 | -47.749 / -47.749 | -75.622 / -75.622 | -18.346 / -18.346 | 0.9995 / 0.9995 | -25.623 / -25.623 | 1.0000 / 1.0000 | = |
| F | 24h | P1 | -23.696 / -23.696 | -33.808 / -33.808 | -13.914 / -13.914 | 1.0000 / 1.0000 | -42.259 / -42.259 | 0.9915 / 0.9915 | = |
| F | 24h | P2 | -12.195 / -12.195 | -85.348 / -85.348 | 84.748 / 84.748 | 0.6380 / 0.6380 | -42.259 / -42.259 | 0.9915 / 0.9915 | = |
| B | 1h | P1 | -0.192 / -0.192 | -4.656 / -4.656 | 4.118 / 4.118 | 0.5375 / 0.5375 | -11.422 / -11.422 | 0.9965 / 0.9965 | = |
| B | 1h | P2 | 4.120 / 4.120 | -12.150 / -12.150 | 19.079 / 19.079 | 0.3060 / 0.3060 | -11.422 / -11.422 | 0.9965 / 0.9965 | = |
| B | 4h | P1 | 0.375 / 0.375 | -7.042 / -7.042 | 7.688 / 7.688 | 0.4480 / 0.4480 | -8.648 / -8.648 | 0.8825 / 0.8825 | = |
| B | 4h | P2 | 5.792 / 5.792 | -19.935 / -19.935 | 30.738 / 30.738 | 0.3310 / 0.3310 | -8.648 / -8.648 | 0.8825 / 0.8825 | = |
| B | 24h | P1 | -4.058 / -4.058 | -15.890 / -15.890 | 7.995 / 7.995 | 0.7295 / 0.7295 | -11.498 / -11.498 | 0.7275 / 0.7275 | = |
| B | 24h | P2 | -14.543 / -14.543 | -95.206 / -95.206 | 49.237 / 49.237 | 0.6305 / 0.6305 | -11.498 / -11.498 | 0.7275 / 0.7275 | = |
| S | 1h | P1 | -5.615 / -5.416 | -15.434 / -14.776 | 1.868 / 1.769 | 0.9055 / 0.9120 | -24.656 / -24.457 | 1.0000 / 1.0000 | **D1 out of tol** |
| S | 1h | P2 | -8.707 / -8.849 | -30.798 / -31.006 | 13.646 / 13.763 | 0.7845 / 0.7905 | -24.656 / -24.457 | 1.0000 / 1.0000 | **D1 out of tol** |
| S | 4h | P1 | -13.101 / -12.504 | -25.319 / -24.665 | -2.783 / -2.590 | 0.9925 / 0.9935 | -29.334 / -28.737 | 1.0000 / 1.0000 | **D1 out of tol** |
| S | 4h | P2 | -18.264 / -18.451 | -46.328 / -46.184 | 8.060 / 7.727 | 0.9150 / 0.9145 | -29.334 / -28.737 | 1.0000 / 1.0000 | **D1 out of tol** |
| S | 24h | P1 | -16.440 / -16.865 | -34.266 / -34.905 | 2.365 / 1.792 | 0.9545 / 0.9625 | -26.980 / -27.405 | 0.9490 / 0.9510 | **D1 out of tol** |
| S | 24h | P2 | -10.353 / -10.087 | -65.824 / -65.227 | 46.076 / 46.244 | 0.6330 / 0.6275 | -26.980 / -27.405 | 0.9490 / 0.9510 | **D1 out of tol** |

Halves and per-coin counts:

| pattern | horizon | control | H1 diff | H1 real net | H1 n | H2 diff | H2 real net | H2 n | coins_pos_diff | coins_pos_net | status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F | 1h | P1 | -14.971 / -14.971 | -11.465 / -11.465 | 3,639 / 3,639 | -8.158 / -8.158 | -13.587 / -13.587 | 3,770 / 3,770 | – / – | – / – | = |
| F | 1h | P2 | -42.838 / -42.838 | -11.465 / -11.465 | 3,639 / 3,639 | -30.106 / -30.106 | -13.587 / -13.587 | 3,770 / 3,770 | – / – | – / – | = |
| F | 4h | P1 | -21.119 / -21.119 | -23.495 / -23.495 | 3,639 / 3,639 | -12.495 / -12.495 | -27.677 / -27.677 | 3,770 / 3,770 | – / – | – / – | = |
| F | 4h | P2 | -71.983 / -71.983 | -23.495 / -23.495 | 3,639 / 3,639 | -24.651 / -24.651 | -27.677 / -27.677 | 3,770 / 3,770 | – / – | – / – | = |
| F | 24h | P1 | -38.452 / -38.452 | -80.585 / -80.585 | 3,639 / 3,639 | -9.406 / -9.406 | -5.265 / -5.265 | 3,770 / 3,770 | – / – | – / – | = |
| F | 24h | P2 | -37.229 / -37.229 | -80.585 / -80.585 | 3,639 / 3,639 | 12.116 / 12.116 | -5.265 / -5.265 | 3,770 / 3,770 | – / – | – / – | = |
| B | 1h | P1 | 2.690 / 2.690 | -15.783 / -15.783 | 3,279 / 3,279 | -2.968 / -2.968 | -7.235 / -7.235 | 3,415 / 3,415 | – / – | – / – | = |
| B | 1h | P2 | 20.220 / 20.220 | -15.783 / -15.783 | 3,279 / 3,279 | -12.003 / -12.003 | -7.235 / -7.235 | 3,415 / 3,415 | – / – | – / – | = |
| B | 4h | P1 | 4.385 / 4.385 | -11.315 / -11.315 | 3,279 / 3,279 | -3.482 / -3.482 | -6.087 / -6.087 | 3,415 / 3,415 | – / – | – / – | = |
| B | 4h | P2 | 35.401 / 35.401 | -11.315 / -11.315 | 3,279 / 3,279 | -23.684 / -23.684 | -6.087 / -6.087 | 3,415 / 3,415 | – / – | – / – | = |
| B | 24h | P1 | 1.995 / 1.995 | 16.825 / 16.825 | 3,279 / 3,279 | -9.844 / -9.844 | -38.693 / -38.693 | 3,415 / 3,415 | – / – | – / – | = |
| B | 24h | P2 | 28.024 / 28.024 | 16.825 / 16.825 | 3,279 / 3,279 | -55.877 / -55.877 | -38.693 / -38.693 | 3,415 / 3,415 | – / – | – / – | = |
| S | 1h | P1 | -1.200 / -1.391 | -18.795 / -18.986 | 1,802 / 1,785 | -9.635 / -9.100 | -30.064 / -29.529 | 1,953 / 1,925 | – / – | – / – | **D1 out of tol** |
| S | 1h | P2 | -14.112 / -14.500 | -18.795 / -18.986 | 1,802 / 1,785 | -4.401 / -4.326 | -30.064 / -29.529 | 1,953 / 1,925 | – / – | – / – | **D1 out of tol** |
| S | 4h | P1 | -2.060 / -2.606 | -22.701 / -23.246 | 1,802 / 1,785 | -23.455 / -21.829 | -35.455 / -33.829 | 1,953 / 1,925 | – / – | – / – | **D1 out of tol** |
| S | 4h | P2 | -11.202 / -13.029 | -22.701 / -23.246 | 1,802 / 1,785 | -24.753 / -23.484 | -35.455 / -33.829 | 1,953 / 1,925 | – / – | – / – | **D1 out of tol** |
| S | 24h | P1 | -17.563 / -17.935 | -45.412 / -45.784 | 1,802 / 1,785 | -16.055 / -16.445 | -9.973 / -10.363 | 1,953 / 1,925 | – / – | – / – | **D1 out of tol** |
| S | 24h | P2 | -31.294 / -30.160 | -45.412 / -45.784 | 1,802 / 1,785 | 8.817 / 8.418 | -9.973 / -10.363 | 1,953 / 1,925 | – / – | – / – | **D1 out of tol** |

### Panel C

| quantity | X / Y | status |
|---|---|---|
| coin_weeks_used | 828 / 828 | = |
| coin_weeks_skipped | 9 / 0 | **D2 out of tol** |
| touch_rates.any | 0.7862 / 0.7862 | = |
| touch_rates.pwh | 0.4251 / 0.4251 | = |
| touch_rates.pwl | 0.4650 / 0.4650 | = |
| daily_sharpe.F.1h | -3.3422 / -3.3315 | **D3 out of tol** |
| daily_sharpe.F.4h | -2.2597 / -2.2526 | **D3 out of tol** |
| daily_sharpe.F.24h | -0.0701 / -0.0699 | D3 (in tol) |
| daily_sharpe.B.1h | -0.5132 / -0.5116 | **D3 out of tol** |
| daily_sharpe.B.4h | 0.2148 / 0.2141 | D3 (in tol) |
| daily_sharpe.B.24h | -1.0430 / -1.0398 | **D3 out of tol** |
| daily_sharpe.S.1h | -1.1949 / -1.1822 | **D1+D3 out of tol** |
| daily_sharpe.S.4h | -1.0669 / -1.0550 | **D1+D3 out of tol** |
| daily_sharpe.S.24h | 0.5743 / 0.5924 | **D1+D3 out of tol** |

Cells (bps; hit = share with net > 0):

| pattern | side | horizon | control | n | gross | net | hit | status |
|---|---|---|---|---|---|---|---|---|
| F | pooled | 1h | real | 737 / 737 | -14.788 / -14.788 | -24.218 / -24.218 | 0.4098 / 0.4098 | = |
| F | pooled | 1h | P1 | 3,155 / 3,155 | -6.795 / -6.795 | -16.225 / -16.225 | 0.4596 / 0.4596 | = |
| F | pooled | 1h | P2 | 156 / 156 | -9.117 / -9.117 | -18.547 / -18.547 | 0.4423 / 0.4423 | = |
| F | pooled | 4h | real | 737 / 737 | -41.943 / -41.943 | -51.373 / -51.373 | 0.4654 / 0.4654 | = |
| F | pooled | 4h | P1 | 3,155 / 3,155 | -28.307 / -28.307 | -37.737 / -37.737 | 0.4945 / 0.4945 | = |
| F | pooled | 4h | P2 | 156 / 156 | -58.282 / -58.282 | -67.712 / -67.712 | 0.4872 / 0.4872 | = |
| F | pooled | 24h | real | 737 / 737 | 6.795 / 6.795 | -2.635 / -2.635 | 0.5427 / 0.5427 | = |
| F | pooled | 24h | P1 | 3,155 / 3,155 | 16.179 / 16.179 | 6.749 / 6.749 | 0.5407 / 0.5407 | = |
| F | pooled | 24h | P2 | 156 / 156 | -29.833 / -29.833 | -39.263 / -39.263 | 0.5128 / 0.5128 | = |
| F | H | 1h | real | 352 / 352 | -10.009 / -10.009 | -19.439 / -19.439 | 0.4119 / 0.4119 | = |
| F | H | 1h | P1 | 1,537 / 1,537 | -2.267 / -2.267 | -11.697 / -11.697 | 0.4619 / 0.4619 | = |
| F | H | 1h | P2 | 66 / 66 | -32.789 / -32.789 | -42.219 / -42.219 | 0.4242 / 0.4242 | = |
| F | H | 4h | real | 352 / 352 | -12.479 / -12.479 | -21.909 / -21.909 | 0.4830 / 0.4830 | = |
| F | H | 4h | P1 | 1,537 / 1,537 | -6.155 / -6.155 | -15.585 / -15.585 | 0.5075 / 0.5075 | = |
| F | H | 4h | P2 | 66 / 66 | -88.239 / -88.239 | -97.669 / -97.669 | 0.4242 / 0.4242 | = |
| F | H | 24h | real | 352 / 352 | -2.862 / -2.862 | -12.292 / -12.292 | 0.5455 / 0.5455 | = |
| F | H | 24h | P1 | 1,537 / 1,537 | 18.051 / 18.051 | 8.621 / 8.621 | 0.5472 / 0.5472 | = |
| F | H | 24h | P2 | 66 / 66 | -136.543 / -136.543 | -145.973 / -145.973 | 0.4394 / 0.4394 | = |
| F | L | 1h | real | 385 / 385 | -19.158 / -19.158 | -28.588 / -28.588 | 0.4078 / 0.4078 | = |
| F | L | 1h | P1 | 1,618 / 1,618 | -11.097 / -11.097 | -20.527 / -20.527 | 0.4574 / 0.4574 | = |
| F | L | 1h | P2 | 90 / 90 | 8.243 / 8.243 | -1.187 / -1.187 | 0.4556 / 0.4556 | = |
| F | L | 4h | real | 385 / 385 | -68.882 / -68.882 | -78.312 / -78.312 | 0.4494 / 0.4494 | = |
| F | L | 4h | P1 | 1,618 / 1,618 | -49.349 / -49.349 | -58.779 / -58.779 | 0.4821 / 0.4821 | = |
| F | L | 4h | P2 | 90 / 90 | -36.314 / -36.314 | -45.744 / -45.744 | 0.5333 / 0.5333 | = |
| F | L | 24h | real | 385 / 385 | 15.624 / 15.624 | 6.194 / 6.194 | 0.5403 / 0.5403 | = |
| F | L | 24h | P1 | 1,618 / 1,618 | 14.401 / 14.401 | 4.971 / 4.971 | 0.5346 / 0.5346 | = |
| F | L | 24h | P2 | 90 / 90 | 48.420 / 48.420 | 38.990 / 38.990 | 0.5667 / 0.5667 | = |
| B | pooled | 1h | real | 675 / 675 | 9.670 / 9.670 | -4.950 / -4.950 | 0.3896 / 0.3896 | = |
| B | pooled | 1h | P1 | 2,905 / 2,905 | 14.666 / 14.666 | 0.046 / 0.046 | 0.3886 / 0.3886 | = |
| B | pooled | 1h | P2 | 142 / 142 | 49.880 / 49.880 | 35.260 / 35.260 | 0.4014 / 0.4014 | = |
| B | pooled | 4h | real | 675 / 675 | 18.205 / 18.205 | 3.585 / 3.585 | 0.4548 / 0.4548 | = |
| B | pooled | 4h | P1 | 2,905 / 2,905 | 20.556 / 20.556 | 5.936 / 5.936 | 0.4516 / 0.4516 | = |
| B | pooled | 4h | P2 | 142 / 142 | 55.971 / 55.971 | 41.351 / 41.351 | 0.5000 / 0.5000 | = |
| B | pooled | 24h | real | 675 / 675 | -36.475 / -36.475 | -51.095 / -51.095 | 0.4104 / 0.4104 | = |
| B | pooled | 24h | P1 | 2,905 / 2,905 | -36.943 / -36.943 | -51.563 / -51.563 | 0.4096 / 0.4096 | = |
| B | pooled | 24h | P2 | 142 / 142 | 35.765 / 35.765 | 21.145 / 21.145 | 0.4296 / 0.4296 | = |
| B | H | 1h | real | 320 / 320 | 7.205 / 7.205 | -7.415 / -7.415 | 0.3937 / 0.3937 | = |
| B | H | 1h | P1 | 1,411 / 1,411 | 12.084 / 12.084 | -2.536 / -2.536 | 0.4011 / 0.4011 | = |
| B | H | 1h | P2 | 61 / 61 | 46.605 / 46.605 | 31.985 / 31.985 | 0.4262 / 0.4262 | = |
| B | H | 4h | real | 320 / 320 | 7.545 / 7.545 | -7.075 / -7.075 | 0.4625 / 0.4625 | = |
| B | H | 4h | P1 | 1,411 / 1,411 | 7.403 / 7.403 | -7.217 / -7.217 | 0.4359 / 0.4359 | = |
| B | H | 4h | P2 | 61 / 61 | 68.842 / 68.842 | 54.222 / 54.222 | 0.5246 / 0.5246 | = |
| B | H | 24h | real | 320 / 320 | 8.009 / 8.009 | -6.611 / -6.611 | 0.4375 / 0.4375 | = |
| B | H | 24h | P1 | 1,411 / 1,411 | -13.979 / -13.979 | -28.599 / -28.599 | 0.4082 / 0.4082 | = |
| B | H | 24h | P2 | 61 / 61 | 106.160 / 106.160 | 91.540 / 91.540 | 0.4590 / 0.4590 | = |
| B | L | 1h | real | 355 / 355 | 11.892 / 11.892 | -2.728 / -2.728 | 0.3859 / 0.3859 | = |
| B | L | 1h | P1 | 1,494 / 1,494 | 17.104 / 17.104 | 2.484 / 2.484 | 0.3768 / 0.3768 | = |
| B | L | 1h | P2 | 81 / 81 | 52.347 / 52.347 | 37.727 / 37.727 | 0.3827 / 0.3827 | = |
| B | L | 4h | real | 355 / 355 | 27.815 / 27.815 | 13.195 / 13.195 | 0.4479 / 0.4479 | = |
| B | L | 4h | P1 | 1,494 / 1,494 | 32.978 / 32.978 | 18.358 / 18.358 | 0.4665 / 0.4665 | = |
| B | L | 4h | P2 | 81 / 81 | 46.278 / 46.278 | 31.658 / 31.658 | 0.4815 / 0.4815 | = |
| B | L | 24h | real | 355 / 355 | -76.574 / -76.574 | -91.194 / -91.194 | 0.3859 / 0.3859 | = |
| B | L | 24h | P1 | 1,494 / 1,494 | -58.633 / -58.633 | -73.253 / -73.253 | 0.4110 / 0.4110 | = |
| B | L | 24h | P2 | 81 / 81 | -17.249 / -17.249 | -31.869 / -31.869 | 0.4074 / 0.4074 | = |
| S | pooled | 1h | real | 338 / 336 | -22.750 / -22.686 | -37.370 / -37.306 | 0.4527 / 0.4554 | **D1 out of tol** |
| S | pooled | 1h | P1 | 1,673 / 1,673 | -14.770 / -14.770 | -29.390 / -29.390 | 0.4202 / 0.4202 | = |
| S | pooled | 1h | P2 | 79 / 79 | -3.182 / -3.182 | -17.802 / -17.802 | 0.3797 / 0.3797 | = |
| S | pooled | 4h | real | 338 / 336 | -25.884 / -25.791 | -40.504 / -40.411 | 0.4615 / 0.4613 | **D1 out of tol** |
| S | pooled | 4h | P1 | 1,673 / 1,673 | -18.380 / -18.380 | -33.000 / -33.000 | 0.4758 / 0.4758 | = |
| S | pooled | 4h | P2 | 79 / 79 | 5.383 / 5.383 | -9.237 / -9.237 | 0.5063 / 0.5063 | = |
| S | pooled | 24h | real | 338 / 336 | 37.615 / 38.502 | 22.995 / 23.882 | 0.5533 / 0.5536 | **D1 out of tol** |
| S | pooled | 24h | P1 | 1,673 / 1,673 | 26.806 / 26.806 | 12.186 / 12.186 | 0.5475 / 0.5475 | = |
| S | pooled | 24h | P2 | 79 / 79 | 23.473 / 23.473 | 8.853 / 8.853 | 0.5316 / 0.5316 | = |
| S | H | 1h | real | 164 / 164 | 5.339 / 5.339 | -9.281 / -9.281 | 0.4512 / 0.4512 | = |
| S | H | 1h | P1 | 825 / 825 | -6.013 / -6.013 | -20.633 / -20.633 | 0.4158 / 0.4158 | = |
| S | H | 1h | P2 | 34 / 34 | 2.665 / 2.665 | -11.955 / -11.955 | 0.5000 / 0.5000 | = |
| S | H | 4h | real | 164 / 164 | 19.065 / 19.065 | 4.445 / 4.445 | 0.5122 / 0.5122 | = |
| S | H | 4h | P1 | 825 / 825 | 2.982 / 2.982 | -11.638 / -11.638 | 0.4788 / 0.4788 | = |
| S | H | 4h | P2 | 34 / 34 | -18.532 / -18.532 | -33.152 / -33.152 | 0.5588 / 0.5588 | = |
| S | H | 24h | real | 164 / 164 | 53.727 / 53.727 | 39.107 / 39.107 | 0.5854 / 0.5854 | = |
| S | H | 24h | P1 | 825 / 825 | 49.725 / 49.725 | 35.105 / 35.105 | 0.5721 / 0.5721 | = |
| S | H | 24h | P2 | 34 / 34 | -144.826 / -144.826 | -159.446 / -159.446 | 0.4118 / 0.4118 | = |
| S | L | 1h | real | 174 / 172 | -49.226 / -49.408 | -63.846 / -64.028 | 0.4540 / 0.4593 | **D1 out of tol** |
| S | L | 1h | P1 | 848 / 848 | -23.290 / -23.290 | -37.910 / -37.910 | 0.4245 / 0.4245 | = |
| S | L | 1h | P2 | 45 / 45 | -7.600 / -7.600 | -22.220 / -22.220 | 0.2889 / 0.2889 | = |
| S | L | 4h | real | 174 / 172 | -68.250 / -68.561 | -82.870 / -83.181 | 0.4138 / 0.4128 | **D1 out of tol** |
| S | L | 4h | P1 | 848 / 848 | -39.162 / -39.162 | -53.782 / -53.782 | 0.4729 / 0.4729 | = |
| S | L | 4h | P2 | 45 / 45 | 23.452 / 23.452 | 8.832 / 8.832 | 0.4667 / 0.4667 | = |
| S | L | 24h | real | 174 / 172 | 22.429 / 23.985 | 7.809 / 9.365 | 0.5230 / 0.5233 | **D1 out of tol** |
| S | L | 24h | P1 | 848 / 848 | 4.509 / 4.509 | -10.111 / -10.111 | 0.5236 / 0.5236 | = |
| S | L | 24h | P2 | 45 / 45 | 150.632 / 150.632 | 136.012 / 136.012 | 0.6222 / 0.6222 | = |

Tests (real − control, gross bps; week-cluster bootstrap):

| pattern | horizon | control | diff | CI lo | CI hi | P(diff ≤ 0) | real net | P(net ≤ 0) | status |
|---|---|---|---|---|---|---|---|---|---|
| F | 1h | P1 | -7.993 / -7.993 | -15.847 / -15.847 | 0.479 / 0.479 | 0.9705 / 0.9705 | -24.218 / -24.218 | 1.0000 / 1.0000 | = |
| F | 1h | P2 | -5.672 / -5.672 | -31.992 / -31.992 | 19.504 / 19.504 | 0.6335 / 0.6335 | -24.218 / -24.218 | 1.0000 / 1.0000 | = |
| F | 4h | P1 | -13.636 / -13.636 | -26.514 / -26.514 | -0.999 / -0.999 | 0.9800 / 0.9800 | -51.373 / -51.373 | 1.0000 / 1.0000 | = |
| F | 4h | P2 | 16.339 / 16.339 | -40.993 / -40.993 | 73.731 / 73.731 | 0.3015 / 0.3015 | -51.373 / -51.373 | 1.0000 / 1.0000 | = |
| F | 24h | P1 | -9.385 / -9.385 | -29.690 / -29.690 | 10.029 / 10.029 | 0.8220 / 0.8220 | -2.635 / -2.635 | 0.5125 / 0.5125 | = |
| F | 24h | P2 | 36.628 / 36.628 | -64.533 / -64.533 | 154.569 / 154.569 | 0.2760 / 0.2760 | -2.635 / -2.635 | 0.5125 / 0.5125 | = |
| B | 1h | P1 | -4.996 / -4.996 | -13.607 / -13.607 | 3.210 / 3.210 | 0.8895 / 0.8895 | -4.950 / -4.950 | 0.7720 / 0.7720 | = |
| B | 1h | P2 | -40.211 / -40.211 | -114.446 / -114.446 | 15.882 / 15.882 | 0.8850 / 0.8850 | -4.950 / -4.950 | 0.7720 / 0.7720 | = |
| B | 4h | P1 | -2.351 / -2.351 | -20.014 / -20.014 | 14.705 / 14.705 | 0.6180 / 0.6180 | 3.585 / 3.585 | 0.4235 / 0.4235 | = |
| B | 4h | P2 | -37.766 / -37.766 | -101.469 / -101.469 | 16.804 / 16.804 | 0.8875 / 0.8875 | 3.585 / 3.585 | 0.4235 / 0.4235 | = |
| B | 24h | P1 | 0.468 / 0.468 | -22.856 / -22.856 | 23.307 / 23.307 | 0.4930 / 0.4930 | -51.095 / -51.095 | 0.9245 / 0.9245 | = |
| B | 24h | P2 | -72.240 / -72.240 | -215.988 / -215.988 | 54.930 / 54.930 | 0.8475 / 0.8475 | -51.095 / -51.095 | 0.9245 / 0.9245 | = |
| S | 1h | P1 | -7.980 / -7.916 | -37.045 / -37.306 | 11.410 / 11.683 | 0.6810 / 0.6770 | -37.370 / -37.306 | 1.0000 / 1.0000 | **D1 out of tol** |
| S | 1h | P2 | -19.568 / -19.504 | -74.244 / -74.397 | 18.548 / 18.862 | 0.7725 / 0.7690 | -37.370 / -37.306 | 1.0000 / 1.0000 | **D1 out of tol** |
| S | 4h | P1 | -7.504 / -7.411 | -43.340 / -43.941 | 20.854 / 20.871 | 0.6375 / 0.6345 | -40.504 / -40.411 | 0.9665 / 0.9645 | **D1 out of tol** |
| S | 4h | P2 | -31.267 / -31.174 | -106.348 / -107.134 | 35.169 / 35.369 | 0.8100 / 0.8065 | -40.504 / -40.411 | 0.9665 / 0.9645 | **D1 out of tol** |
| S | 24h | P1 | 10.809 / 11.696 | -24.120 / -23.493 | 43.185 / 44.108 | 0.2775 / 0.2565 | 22.995 / 23.882 | 0.1870 / 0.1795 | **D1 out of tol** |
| S | 24h | P2 | 14.142 / 15.029 | -127.897 / -127.840 | 182.811 / 184.221 | 0.4620 / 0.4600 | 22.995 / 23.882 | 0.1870 / 0.1795 | **D1 out of tol** |

## 7. Files (all under `/tmp/claude-0/-home-user-crypto-strategy/06a4a035-9ed5-5cdd-b015-c18e9399531d/scratchpad/research3/reconcile/`)

- `final/results.json`: chosen, final results (Y code, re-run here)
- `final/events_{A,B,C}.csv.gz`: final event files
- `final/{loaders,engine,run,test_engine}.py`: Y code, unchanged; `test_s_ties.py` new tie-rule test
- `X_patched/`: X code with the four reconcile edits; reproduces final
- `compare_results.py, cmp_X_vs_Y.json/.csv, cmp_Y_vs_final.json, cmp_final_vs_Xpatched.json`: leaf-by-leaf results.json comparisons
- `compare_events.py, events_compare.json, events_{A,B,C}_unmatched.csv, events_{A,B,C}_mismatched.csv`: row-by-row event joins and the differing rows
- `recompute_from_events.py`: third statistics layer rebuilt from the event files
- `make_reconcile_md.py`: this report
