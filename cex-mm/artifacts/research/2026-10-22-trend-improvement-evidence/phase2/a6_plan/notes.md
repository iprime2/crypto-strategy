# A6 Delta-funding stress line, as the plan wrote it (run 2026-10-22, after the PR review)

**Why this exists.** The review of the write-up (PR 58) found that `engine/harness.py::delta_funding_stress` did not implement amendment A6 as frozen. The plan (`phase1_plan.md` A6) says: per-coin-day funding = max(Binance, 0.01 %/8 h x 3) for BTC, ETH, BNB, LTC and BCH, and Binance x the 2025-26 Delta/Binance mean ratio for the other coins. The harness instead floored each of the nine at its own Delta 2025-26 mean (`funding_summary.json` `<sym>USD|all` `ann`) and left every other coin on Binance funding. This folder runs the plan's version for the baseline and for the three cells A6 gates (SIG-3a, SIG-10, UNI-2), next to the as-run line.

**Interpretation, fixed before the run.**
- Majors (BTC, ETH, BNB, LTC, BCH): F' = max(F_binance, 0.0003 a day) on days with a close.
- XRP, ADA, LINK, DOGE: r = Delta mean daily funding / Binance mean daily funding of the same coin over 2025-01-01..2026-09-30; F' = F_binance x r.
- Coins with no Delta record (the 16 other ex-ante perps, GOLD): the pooled ratio of those four, sum of Delta means / sum of Binance means.
- "plan" is that reading literally. "plan_clip1" clips every ratio at 1, so the line is never milder than Binance funding.
- Everything else is the harness's `cell()` logic unchanged: same panels, windows (POST = 2022-01..2026-09), costs, base lines and `base_coins`.

**Ratios** (Binance / Delta mean, % a year of notional, 2025-01..2026-09 / 2025-01..2026-10):

| coin | Binance | Delta | ratio |
|---|---|---|---|
| XRP | 1.91 | 5.42 | 2.839 |
| ADA | 2.96 | −2.26 | −0.761 |
| LINK | 4.96 | −0.58 | −0.117 |
| DOGE | 3.77 | 4.44 | 1.179 |
| pooled (the four) | | | 0.517 |

Read literally, the negative ADA and LINK ratios flip the sign of their funding and the pooled 0.52 halves funding on the 16 other coins, so on panel B the plan's line is milder than Binance funding. That is why the clipped reading is reported too.

**Baseline POST Sharpe** (`plan_a6.json`):

| line | Binance funding | as run (harness) | plan, literal | plan, ratios clipped at 1 |
|---|---|---|---|---|
| A daily | 0.837 | 0.787 | 0.787 | 0.753 |
| A weekly | 0.660 | 0.608 | 0.608 | 0.577 |
| B daily | 0.586 | 0.566 | 0.590 | 0.552 |
| B weekly | 0.492 | 0.471 | 0.492 | 0.459 |

The as-run column reproduces `phase2/results/*.json` `delta_funding_stress` to four decimals (e.g. A daily 0.7872, B weekly 0.4706; SIG-3a A daily 0.4926; SIG-10 B weekly 0.3180; UNI-2 B25G weekly 0.5721).

**The condition-2 check A6 adds** (stress A POST, variant − base, must be ≥ −0.03 for a cell that raises gross by more than 10 %):

| cell | as run d / w | plan d / w | clipped d / w |
|---|---|---|---|
| SIG-3a | −0.295 / −0.164 | −0.307 / −0.176 | −0.305 / −0.176 |
| SIG-10 | −0.105 / −0.090 | −0.110 / −0.096 | −0.113 / −0.099 |
| UNI-2 (A10) | +0.208 / +0.205 | +0.208 / +0.205 | +0.209 / +0.205 |

SIG-3a and SIG-10 fail it on every reading and UNI-2 passes it on every reading, as with the as-run line. All three fail class I condition 1 regardless. **No verdict changes.**

**Files.** `plan_a6.py` (run from the scratchpad layout as `research2/a6_plan/`, next to `tools2/`), `plan_a6.json` (every line: Sharpe, funding a year and CAGR for variant and base under the four funding readings).
