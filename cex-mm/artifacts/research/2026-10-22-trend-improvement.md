# Quant memo: can the trend rule be improved? No change, one structural finding
**Date:** 2026-10-22 · **Venue:** Delta Exchange India public data and the Binance USDT-M perp archive as a proxy (no orders placed, no keys used) · **Symbols:** the running nine (BTC, ETH, XRP, BNB, ADA, LTC, LINK, DOGE, BCH perps); the 24 Binance USDT-M perps listed by 2020-02-20 as the ex-ante panel; a survivorship-free pool of 696 USDT-M symbols for the universe test (the 896 archived symbols with at least six months of daily bars, delisted ones included) · **Data:** daily closes and funding, Binance 2020-05-01..2026-09-30 (2,344 return days), Delta 2024-08-10..2026-10-12 (794 return days); Binance 5 m klines and Delta MARK closes for the diagnostics, and Binance and Delta 1 h candles for TIME-3 and SZ-17 · **Full report:** `resource/08-trend-rule-improvement-research.md` · **Evidence:** `cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/` (frozen plan, phase 1 notes and verifications, phase 2 results and verdicts, the UNI-1 verification, the engine; see its `README.md`)

## Question
The user asked for a re-analysis of the trend strategy: the long/flat time-series-momentum rule on nine Delta India perps, run as two paper books (daily, TV 0.40, band 0; weekly, TV 0.25, 10 % band, Monday 00:00 UTC). The brief was to read papers and practitioner blogs, decide, improve, and restart.

How it was tested, in three phases:
- **Research.** Nine angles (academic signal, academic sizing, crypto academic, practitioner trend including Carver's pysystemtrade, crypto practitioners, universe, costs and funding on Delta, overlays, timing and cadence) gave 77 raw candidates, 57 after merging 20 duplicates (`phase1/master_candidates.md`). Adversarial verification against everything the repo had already tested kept or refined 28 (`phase1/verify_*.md`).
- **Pre-registration.** The plan was frozen before any run (`phase1_plan.md`, sha256 `9ad0a829...c095` in `plan_sha256.txt`; amendment A-2026-10-21 added after-tax lines, a Delta-funding stress line, intraday and leverage reporting, the N_eff = 90 haircut, a Phase 3 fidelity rule, and cells SZ-17 and SIG-13). It has 26 primary cells plus neighbors (25 ran; SIG-9 was gated off by its diagnostic). Its section 8 lists the 36 candidates not pursued, in 33 one-line entries, next to the 2026-10-13 rejected list.
- **Backtests.** A numpy engine that reproduces `cex-mm/scripts/trend_backtest.py` to 1e-15 per day (`phase2/summary.md`, engine note). Panels: A = Binance nine, B = the 24 ex-ante perps (primary), C = Delta nine. Primary metric: Sharpe on B over 2022-01..2026-09 ("B POST") against the running book, by a paired 20-day block bootstrap.

The pass rule (`phase1_plan.md` section 5) has two classes. Class I needs every one of these:
- a gain of at least max(0.05, 2.37 × sd) with P(gain ≤ 0) ≤ 0.10;
- no gain below −0.03 on A POST, A FULL or C FULL;
- a positive gain in both halves;
- neighbors that agree;
- matched-vol max drawdown no more than 2 pp worse and worst 7-day no more than 1 pp worse;
- the cell's own extra conditions.

Class II needs all of: equal Sharpe (B POST at least −0.03 with a CI lower bound of at least −0.10; at least −0.03 on A POST, A FULL and C FULL; neither B half below −0.05); a named operational metric that improves on A, B and C and holds in every neighbour (no neighbour below −0.08 on B POST); matched-vol drawdown and worst 7-day no worse by 2 pp / 1 pp; and the cell's own extra conditions.

## Outcome
- **No change.** No cell passes the pre-registered rule (`phase2/verdicts.md`, including the correction at its end).
  - Both paper books stay exactly as they are.
  - No third paper book.
  - No restart: nothing changed, so a restart would change nothing.
  - The live ADA market-making run on mainnet (`2026-10-21-live-stage1-2-tick-pickoff-latency.md`) is a different strategy. It was not touched.
- **The one structural finding is rebalance timing luck.** Picking a single weekday is a lottery of about ±0.1 Sharpe on A and B, and wider on Delta. The weekly book's slot (the Sunday candle, decided Monday 00:00 UTC) is the worst of the seven on all three panels. Tranching removes the lottery at no expected cost, but it needs daily execution, which means a bot. So it is the first thing to re-test if the weekly hand book is ever replaced by a bot book, against the daily 10 %-band rule that resource/07 names as the bot version. The idea and the 1/N scaling are Hoffstein, Sibears and Faber's ([SSRN 3319045](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3319045) [UNVERIFIED]).
- **The rotating ex-ante universe (UNI-1) was refuted.** It first passed as a research number, then failed on corrected data. A re-test is fixed now for the annual review, so nothing is tuned later.
- **Tax matters more than any rule change.** Gate 0, a written CA opinion, stays first.
- **What would change the decision:**
  - the annual review with one more year of data (the UNI-1 re-test as fixed, and TIME-1 if a bot book replaces hand execution, both on gap-patched data);
  - capital of at least $5,000;
  - a CA opinion.

  The paper books' own gates continue: the daily book's four-week paper test ends around 5 Nov (four weeks from 8 Oct, `2026-10-08-trend-following-backtest.md`), and the weekly book's Gate A falls around 16 Nov (four Mondays from 19 Oct, `2026-10-13-prop-strategy-research.md`).

## Findings, ranked by money at stake
| # | Finding | Numbers | Source |
|---|---|---|---|
| 1 | Tax moves the result more than any rule change. Under the per-coin-day VDA reading every after-tax line in the study is negative | Weekly book on B, full window: pre-tax CAGR +8.7 % becomes −12.0 % per-coin-day VDA, +3.9 % per-segment VDA, +5.8 % slab 30 % on net. Daily book: +13.6 % becomes −18.4 % / +4.1 % / +9.2 %. Best per-coin-day line of all 1,040 tax and base_tax lines (520 of each) in the results: −3.7 %/yr (SIG-3b weekly, A H1). These are backtest CAGRs, not forecasts: resource/07 sets the forward expectation at Sharpe 0.3–0.8, about +4 % to +9 % a year before tax, and over 2025-01..2026-10 the weekly book on Delta, unrounded, made +0.1 % a year before tax (about +2.1 % a year [SYNTHETIC] at $1,000 in whole contracts, from resource/07's T5 line) and −0.2 % / −2.5 % / −13.7 % after the slab / per-segment / per-coin-day readings | `phase2/results/TIME-1.json`, `SZ-1.json` (`base_tax`, B FULL); `TIME-1.json` C-tranche h2 (`base`, `base_tax`); every `tax.coinday` and `base_tax.coinday` field in `phase2/results/*.json`; `resource/07-trend-rule-and-prop-trading-research.md` (expected performance) |
| 2 | The weekly book's decision slot is the worst of seven weekdays on every panel | FULL Sharpe, Sunday candle vs the seven-weekday mean (range): A 1.121 vs 1.230 (1.121–1.335); B 0.810 vs 0.895 (0.810–1.032); C 0.704 vs 0.980 (0.704–1.141) | `phase2/reference.md` |
| 3 | Tranching (TIME-1: trade daily toward the 7-day mean of the daily targets, TV 0.25) lands on the seven-weekday mean. It is the closest class I miss and still fails | B POST +0.176 vs the weekly book (CI +0.03 to +0.33, P 0.009); hurdle 0.183; orders 594/yr at $1,000 on A and 409 on C, against a cap of 350. FULL gain = weekday luck + variance reduction: A 0.109 + 0.010, B 0.085 + 0.025, C 0.275 − 0.003. TIME-4 (two hand sessions): +0.159 vs 0.169, orders 332 / 238 against 220. COMBO-C: +0.165 vs 0.184, and below TIME-1 on every panel | `phase2/verdicts.md` TIME-1, TIME-4, COMBO-C |
| 4 | UNI-1 (yearly ex-ante liquidity-ranked universe, N 9) is refuted on gap-patched data | The uplift reproduces: daily 1.046 vs 0.860, weekly 0.984 vs 0.819; placebo at the 96.5th / 100th percentile. But the daily book fails the drawdown clause (matched-vol max DD −24.51 % vs −24.01 %). The 2025–26 POST gain is +0.095 daily and +0.002 weekly. The gain is concentration (the nine coins it shares with static-24 sum +1.038 vs +0.421 in daily P&L before costs, FULL, daily book) plus SOL +0.128 and DOGE +0.109 on the same basis. At $1,000 SOL holds 0.66 (daily, TV 0.40) / 0.42 (weekly, TV 0.25) contracts at full signal | `uni1_verify/synthesis.md` sections 1–5; `uni1_verify/robust/notes.md` section 2; `uni1_verify/live/notes.md` section 3; `phase2/verdicts.md` correction |
| 5 | Gold as a tenth instrument (UNI-2) is the 2024–26 gold bull | Its B is the 25 coins (the 24 ex-ante perps plus DOGE) plus gold, against those 25. B POST +0.093 daily / +0.088 weekly, against hurdles of 0.112 / 0.100. Before the bull (2020–23): B+gold −0.017, A+gold −0.047 | `phase2/verdicts.md` UNI-2 |
| 6 | The funding tail cut-out (OVL-2) lowers funding but fails on Sharpe | B POST +0.138 / +0.105 (P 0.12 / 0.13), against hurdles of 0.305 / 0.225. B in 2020–23: −0.125 / −0.067. CAGR down 2.33 / 1.54 pp | `phase2/verdicts.md` OVL-2 |
| 7 | Signal changes lose or tie (B POST, daily / weekly) | SIG-2 continuous z +0.016 / −0.128 (hurdle 0.240); SIG-3b continuous EWMAC −0.127 / −0.091; SIG-1B t-stat dead zone −0.115 / −0.157; SIG-3a EWMAC binary −0.105 / −0.074; SIG-4 Donchian ratchet +0.008 / −0.049 (A POST −0.200 / −0.272); SIG-7A 250-day sleeve −0.229 / −0.061; SIG-10 agreement count −0.063 / −0.149; SIG-11 breakout blend +0.011 / −0.020; SIG-13 funding-adjusted index −0.036 / −0.016. SIG-9 (turning point) was gated off by D-1: Correction below Bull on the 24 in both windows: −0.31 % vs +0.88 % (2020–26) and −0.79 % vs +0.05 % (2022–26), next 7 days | `phase2/verdicts.md`; `phase2/diagnostics.md` D-1 |
| 8 | Sizing, overlay and timing changes lose or tie | SZ-1 EWMA COM 60 −0.058 / −0.045, with turnover down only 7–13 % on A, B and C (FULL; bar 15 %); SZ-3 Carver mix −0.060 / −0.066; SZ-17 hourly RV: A POST −0.080 daily, C −0.151, orders down 4–8 % (A and C at $1,000); SZ-6b correlation factor +0.011 / +0.001 (floor 0.05); SZ-13 minimum contract: orders barely move at $1,000 (A daily 871.5 to 871.5; C weekly −3.9 %); OVL-3 fast-exit veto −0.075 / −0.029; TIME-3 decision-hour tranche +0.059 / +0.007 (hurdles 0.131 / 0.151); COMBO-A +0.123 (hurdle 0.205); COMBO-B −0.045 | `phase2/verdicts.md` |
| 9 | Costs and execution: the one saving is too small, and neither fill drift nor the choice of price series hides a cost | COST-2 contract buffer (b 0.10, m 0.75 contracts): cuts daily-book orders 37–48 % on the nine (35–42 % on Delta), whole contracts at $1,000–$5,000, for B POST +0.030 (unrounded), but fees fall only 0.189 pp on A at $1,000 (bar 0.20 pp), and the path effect on C at $1,000 is +0.133 (bound ±0.08). D-3 fill drift from the 00:00 open to the close of the 00:05 bar (about 00:10 UTC; `diagnostics.md` labels it 00:00 to 00:05): sells +3.79 bps (t 3.55), buys +0.05 (t 0.07). That fires the A2 re-run trigger (above 2 bps), but the drift favours the seller, so the re-run was waived: favourable, not credited. D-4: Delta MARK vs last-trade sleeve sign agreement 99.61 / 99.86 / 99.89 % | `phase2/verdicts.md` COST-2; `phase2/diagnostics.md` D-3, D-4; `phase2/summary.md` (Diagnostic outcomes, D-3) |
| 10 | An engine bug was fixed before judging; a data defect was found afterwards, in the UNI-1 verification, and corrected for the UNI-1 re-check only (other cells' panel-B numbers were not recomputed; see Limits) | Binance archive gaps: DASHUSDT 2022-10 missing, and 2022-02-26..28 and 2022-04-01..02 missing for 51 symbols. Patching them moved static-24 from 0.851 to 0.860 daily and from 0.810 to 0.819 weekly. The COST-2 buffer applied its 0.75-contract floor to unrounded lines; it was fixed and the baseline re-verified to 1e-15 | `uni1_verify/synthesis.md` sections 1 and 4; `phase2/summary.md` engine note |

## What the code actually does
- **The running books are unchanged.** The daily VM book is `cex-mm/scripts/trend_paper.py` at TV 0.40, band 0. The weekly book is a paper book: `trend_paper.py --weekly --target-vol 0.25 --band 0.10 --state-dir artifacts/trend/paper-weekly`, run on the VM by `cex-mm-trend-paper-weekly.timer` with paper taker fills; `--orders-only` prints the Monday order list that the live design will execute by hand after Gate A (`cex-mm/artifacts/research/2026-10-13-prop-strategy-research.md`). No file under `cex-mm/scripts/` changed, no timer was touched, and nothing was restarted.
- **The research engine lives in the evidence pack** (`engine/`), not in `cex-mm/scripts/`.
  - It is a numpy re-implementation of `trend_backtest.py::target_weights` and its simulator.
  - It holds the pre-registered cells (`variants_*.py`) and the harness; the mechanical judge is `phase2/judge.py`.
  - It is research code with absolute scratchpad paths. It is not wired to any book, bot or order path.
- **A UNI-1 book would need code that does not exist.** `trend_paper.py` is hard-wired to `tb.COINS`, the nine. Such a book needs a universe file, a per-coin Delta product lookup and a yearly reset job (`uni1_verify/synthesis.md` section 4). It would be built through the lead-engineer flow, and only on the user's request.
- **A TIME-1 book would need daily execution.** No order path for the trend rule exists in the repo: `trend_paper.py` fills both books on paper, and the live design executes the weekly list by hand. A TIME-1 paper book would need a tranche mode in `trend_paper.py` (it has none); a live TIME-1 book would need daily execution, i.e. a bot. `mm-bot`, `mm-oems` and every market-making order path are unaffected.

## Next experiment (one knob, metric, success, stop)
There is no knob on the running books. Two re-tests are fixed now, so nothing is tuned later.

**1. Annual review: re-test UNI-1 exactly as frozen.** The spec is `uni1_verify/synthesis.md` section 5.
- **Settings:** N 9, January reset, 30-day median turnover, age 365, keep-rank 18, start from the top 9 on 2020-04-30.
- **Data:** the gap-patched pool, extended through the latest quarter.
- **Metric:**
  - all four research-number clauses on both books;
  - the drawdown clause at matched vol against the patched static-24;
  - raw max DD and the Delta-funding stress line in both readings (the harness floor, as in `uni1_verify/robust/a5_funding.py` S0, and the plan's A6 text, as in `phase2/a6_plan/`), also reported;
  - static-24 as the comparator, never the nine.
- **Success:** every clause passes on both books. Then, and only with the user's go-ahead, a daily third paper book starts at $5,000 paper capital (the parked spec).
- **Stop:** any clause fails, and UNI-1 stays rejected.
- **Optional:** on the 2027-01-01 candle, compute and archive the reset list without trading it. The review then has a membership list that was truly ex ante.

**2. Only if a bot book ever replaces hand execution: re-test TIME-1 exactly as frozen.**
- **Settings:** K 7, TV 0.25, 10 % band, taker fills at 00:05 UTC.
- **Data:** gap-patched data with one more year.
- **Metric:** B POST Sharpe gain vs the weekly book.
- **Also report:** the same lines for resource/07's bot version, the daily rule with the 10 % band, since a bot book chooses between the two; this study ran it only unjudged, as the plan's reference line and TIME-1's K = 1 control (D at TV 0.25 band 10: B POST +0.105 vs the weekly book).
- **Success:** the class I rule as written. Whether the 350-orders-a-year cap at $1,000 still applies to a bot book must be decided and recorded before the run, not after it.
- **Stop:** a failure keeps the weekly hand book.

## Limits
- **The literature is search-summary level.** The sandbox proxy blocked every web page except raw GitHub files, data.binance.vision and api.india.delta.exchange, so most paper and blog facts are tagged [UNVERIFIED] in `phase1/notes/`.
- **Two parts of the research are missing.** A planned tenth angle (extra data and open-source code) was dropped for capacity, and the open-interest diagnostic was deferred (plan A9).
- **The backtests are in-sample on a proxy.**
  - Panels A and B are Binance prices and funding.
  - The Delta panel has 794 return days.
  - In 2026-Q3 (Jul–Sep), Delta funding ran about 2.0x Binance's at book level: 3.09 % vs 1.54 %/yr on the UNI-1 daily book, and the same 2.01 ratio on the nine (`uni1_verify/live/notes.md` section 5).
- **Panels A and B were judged on the gap-affected archive for every cell except UNI-1** (A carries the five-day XRP and LTC gap that resource/07 found immaterial).
  - Both arms of each paired delta use the same panel.
  - Every failing cell except OVL-2 also fails a condition that does not use B (`phase2/verdicts.md` correction). OVL-2's three failures (B POST +0.138 vs hurdle 0.305, B H1 −0.125, B FULL CAGR −2.33 pp) all use B and were not recomputed; the patch moved static-24 by 0.009, against a 0.167 gap to the hurdle, so a flip is unlikely but unchecked. SIG-9's D-1 gate is also read on the 24, but Correction sits 1.2 and 0.8 percentage points of 7-day return below Bull, far beyond what the patch could move.
  - The B figures above are not recomputed.
- **The statistics have known gaps.**
  - The haircut uses 2.37 × sd (plan A3, replacing section 5's 1.98), while the plan's own formula gives 2.49 at N 90; 2.37 corresponds to N of about 64. No cell clears either.
  - sd is the bootstrap CI width / 3.92.
  - Missing evidence counted as a fail: UNI-2's realistic-cost neighbor never ran; COST-2's 2022–23 and 2025–26 windows and its paired comparison against band 0.10 at each capital were not produced; SIG-2 has no $5,000 line.
  - A5 was only partly reported (no intraday-low equity line). Under A5, UNI-2 is flagged: on the nine plus gold, daily, max gross is 1.15x against 0.87x, and gross is above 0.6x on 11.8 % of days against 4.6 % (`phase2/results/UNI-2.json`, A10-daily). No other variant crosses the 0.2x line.
- **Four departures from the frozen plan, none of which changes a verdict:**
  - the A6 Delta-funding stress line floored the nine at their own Delta 2025–26 means and left other coins on Binance funding, instead of the plan's 0.01 %/8 h floor on BTC, ETH, BNB, LTC and BCH and the Delta/Binance ratio elsewhere. The review of this write-up found it. The plan's version, run afterwards (`phase2/a6_plan/`), leaves A POST at 0.787 / 0.608 read literally and gives 0.753 / 0.577 with every ratio clipped at 1; SIG-3a and SIG-10 still fail condition 2 on it and UNI-2 still passes that check (it fails condition 1), so no verdict moves (resource/08, Funding);
  - the T0/D-0 gate was missed (static-24 0.851 / 0.810 vs 0.86 / 0.82) and waived by the judge as an engine difference; the UNI-1 check later traced it to the archive gaps (`uni1_verify/synthesis.md` section 1);
  - A2's D-3 was measured from 00:00 to about 00:10 instead of the plan's 00:00 to 00:05, and the daily cost re-run it then required (sells drifted +3.79 bps) was not done and no gain was credited (`phase2/summary.md`, D-3);
  - OVL-3 was opened on the unconditional Correction state, while on the signal-on reading of its cited source its gate was closed; the cell fails either way (`phase2/verdicts.md` OVL-3).
- **The three tax readings are models, not advice.** They are per-coin realized-segment VDA 30 % on gross gains, per-coin-day VDA 30 % on positive coin-days (both with no set-off), and slab 30 % on the net annual return (plan A1). Which one applies is the CA's question.
