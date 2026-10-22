# Twenty-Six Ways to Change the Trend Rule, and Why None Is Adopted

**Date:** 2026-10-22 · **Status:** research report. Nothing was traded, no paper book was changed or restarted, and no live system was touched. **Evidence:** every number below comes from the evidence pack `cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/` and is cited by its path from the repository root. After the first full path in a passage, `…/` abbreviates `cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/`. **Tags:** [VERIFIED] = file or API opened in this study (raw GitHub files, data.binance.vision, api.india.delta.exchange, repo files); [SECONDARY] = a third party's transcription of a paper was opened, not the paper; [UNVERIFIED] = search-result summary or memory only, because the sandbox proxy blocked the page; [LOCAL] = computed in Phase 1 on cached data, indicative and not pre-registered; [SYNTHETIC] = arithmetic done for this report. This report follows `resource/07-trend-rule-and-prop-trading-research.md`, which specifies the rule, and `cex-mm/artifacts/research/2026-10-13-prop-strategy-research.md`, which sets its gates. The one-page memo for this study is `cex-mm/artifacts/research/2026-10-22-trend-improvement.md`.

## Executive summary: the rule stays as it is

- **Decision: no change.** The running rule and both paper books (daily TV 0.40 band 0 since 2026-10-08; weekly TV 0.25 band 10 % at Monday 00:00 UTC since 2026-10-19) stay exactly as they are. There is no third paper book and no restart, because nothing changed. The live ADA market-making run that another session started on mainnet (`cex-mm/artifacts/research/2026-10-21-live-stage1-2-tick-pickoff-latency.md`) is a different strategy and was not touched.
- **Why:** 26 pre-registered cells were judged and none passed the rule fixed before the first run. One of them, SIG-9, was gated off by its own diagnostic and never ran. The bar was a Sharpe gain on the 24-coin ex-ante panel from 2022 of at least max(0.05, 2.37 × its bootstrap sd), plus no loss elsewhere, or equal Sharpe with a named operational gain.
- **Closest class I miss:** tranching the weekly book (TIME-1) gained +0.176 (95 % CI +0.03 to +0.33, P 0.009) against a hurdle of 0.183, and needs 594 orders a year at $1,000 on the nine (409 on Delta) against a cap of 350. TIME-4 (two hand sessions) fails the same way: +0.159 against a 0.169 hurdle, and 332 orders a year at $1,000 on the nine against a cap of 220. COMBO-C misses its hurdle (+0.165 against 0.184) and sits below TIME-1 alone on every panel.
- **The one structural finding is timing luck.** The weekly book's slot is the worst of the seven weekdays on all three panels: Sharpe 1.121 vs a mean of 1.230 (Binance nine), 0.810 vs 0.895 (24 ex-ante), 0.704 vs 0.980 (Delta). Tranching lands on the mean at no expected cost, but it needs daily execution, which means a bot.
- **UNI-1** (a yearly liquidity-ranked universe) first passed as a research number, then failed on corrected data. It is parked with a fixed re-test for the annual review.
- **Everything else fails clearly:** graded and alternative signals (SIG-2, SIG-3b, SIG-1B, SIG-3a, SIG-4, SIG-7A, SIG-10, SIG-11, SIG-13; SIG-9 gated off), three vol estimators, a correlation factor, a minimum-contract rule, gold, the funding cut-out (OVL-2), the fast-exit veto (OVL-3), the decision-hour tranche and two combinations (COMBO-A, COMBO-B).
- **Costs:** a contract buffer (COST-2) cuts daily-book orders by 35–48 % (37–48 % on the nine, 35–42 % on Delta, whole contracts at $1,000–$5,000) for B POST +0.030 (unrounded), but misses its fee bar. Fill drift and MARK closes change nothing.
- **Tax matters more than any rule change.** Under the per-coin-day VDA reading every line is negative after tax (weekly baseline on the 24 coins: −12.0 % a year). Gate 0, a written CA opinion, stays first.
- **Two defects were found and corrected:** gaps in the Binance archive (patched for the UNI-1 re-check; other cells' panel-B numbers were not recomputed, and `fetch_all.py` still drops failed downloads silently) and a bug in the engine's buffer code (fixed before judging). A third, wrong contract values in the UNI-1 gate, is recorded, not fixed.
- **What would change the decision:** the annual review with one more year of data, capital of $5,000 or more, a bot book replacing hand execution, or a CA opinion.

## The question and the method

The user asked for the trend strategy to be re-analysed against research papers and practitioner blogs, then improved and restarted if the evidence allowed it. The strategy is the long/flat time-series-momentum rule on nine Delta India perps, specified in `resource/07-trend-rule-and-prop-trading-research.md`. At each 00:00 UTC close the signal is `max(mean_L sign(P_t/P_{t-L} − 1), 0)` over L = 20, 60 and 120 days, so zero to three positive lookbacks map to 0, 0, 1/3 and 1. The weight is `sig × (TV/N) / max(vol60, 0.05)`. Costs are 7.31 bps a side (5.31 taker incl. GST plus 2 slippage), and longs pay funding. The two baselines are D (daily, TV 0.40, cap 2x, band 0) and W (weekly, TV 0.25, cap 1x, 10 % band, decision on the Sunday candle, executed Monday 00:05 UTC) (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase1_plan.md` §1).

The study ran in three phases. Every result was judged against a plan frozen before the first backtest. Four departures from that plan are listed under Limits; none changes a verdict.

| Phase | What was done | Output |
|---|---|---|
| 1 Research | Nine angles were researched: academic signal, academic sizing, crypto academic, practitioner trend (Carver and pysystemtrade), crypto practitioners, universe, costs and funding on Delta, overlays, timing and cadence. A tenth angle, "extra data and open-source code", was dropped for capacity. The nine produced 77 raw candidates, which became 57 unique entries after 20 duplicates were merged. Adversarial verification against everything the repo had already tested kept or refined 28. The plan froze 26 primary cells plus neighbours and listed 36 candidates (in 33 one-line entries) that it deliberately did not pursue, plus the 2026-10-13 rejected list. | `…/phase1/notes/*.md`, `…/phase1/master_candidates.md`, `…/phase1/verify_*.md`, `…/phase1_plan.md` |
| 2 Backtests | A numpy engine that reproduces `cex-mm/scripts/trend_backtest.py` to 1e-15 per day ran every cell and its neighbours. Each ran on the panels and cadences its plan entry names (A, B and C where applicable) and four windows. A mechanical judge applied the plan. | `…/phase2/summary.md`, `…/phase2/verdicts.md`, `…/phase2/diagnostics.md`, `…/phase2/reference.md`, `…/phase2/results/*.json` |
| UNI-1 check | The one cell that passed was re-checked through four lenses: an independent rebuild, a data audit, a robustness pass and live feasibility on Delta. | `…/uni1_verify/synthesis.md`, `…/uni1_verify/{rebuild,audit,robust,live}/notes.md` |

The plan was frozen at 2026-10-21T14:08:16Z, with sha256 `9ad0a829f7bc269f5ce99e7c4e57a09ef89ffe1699776b479abe9b291418c095` (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/plan_sha256.txt`; `…/phase2/summary.md` line 3).

**Datasets** (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase1_plan.md` §2):

| Panel | Universe | Window | Role |
|---|---|---|---|
| A | The nine (BTC ETH XRP BNB ADA LTC LINK DOGE BCH), Binance USDT-M | 2020-05-01..2026-09-30 (2,344 days) | Must not lose (a hindsight universe) |
| **B** | The 24 USDT-M perps listed by 2020-02-20 (ex ante; EOS flattened at its 2025-05 delisting) | Same | **Primary panel** |
| C | The nine on Delta India, close only | 2024-08-10..2026-10-12 (794 days) | Must not lose (venue-native) |
| Bw | 696 USDT-M symbols including delisted ones (the 896 archived symbols with at least six months of daily bars), with quote volume | Same as A | UNI-1 only |

The windows are FULL, POST (2022-01-01..2026-09-30, 1,734 days), H1 (to 2023-12-31) and H2 (from 2024-01-01). **The primary metric is the Sharpe gain on B over POST against the baseline.** It comes from a paired block bootstrap with 20-day blocks, 1,000 draws and seed 7 (`…/phase1_plan.md` §3–4).

**Decision rule, fixed before any run** (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase1_plan.md` §5):

- **Class I (Sharpe gain).** A cell passes only if all of these hold:
  - the B POST gain is at least the hurdle, with P(gain ≤ 0) ≤ 0.10;
  - no loss below −0.03 on A POST, A FULL or C FULL;
  - a positive gain in both halves of B;
  - every neighbour's B POST gain at least 0 and no more than 0.10 below the primary's;
  - drawdown at matched vol no worse than the baseline's by 2 pp, and worst 7-day by 1 pp;
  - the cell's own extra conditions.
- **Class II (same Sharpe, cheaper).** A cell passes only if all of these hold:
  - the B POST gain is at least −0.03, with a CI lower bound of at least −0.10;
  - at least −0.03 on A POST, A FULL and C FULL, and neither half of B below −0.05;
  - a named operational metric improves by the stated amount on A, B and C;
  - no neighbour below −0.08 on B POST, and the operational gain holds in every neighbour;
  - drawdown at matched vol no worse than the baseline's by 2 pp, and worst 7-day by 1 pp;
  - the cell's own extra conditions.
- **Research class (UNI-1 only).** UNI-1 is compared with the static ex-ante 24, never with the hindsight nine. A pass is a number for the annual review, and a live rule only at $5,000 or more.
- **Default.** Any failure on any item means "do nothing".

**Multiple-testing haircut.** The hurdle is the expected maximum of N null differences (Bailey and López de Prado, [SSRN 2460551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) [UNVERIFIED]). At N = 24 that is 1.98 × the cell's own bootstrap sd. Amendment A3 raised N to an effective 90: the 26 cells, 4 Phase 1 smoke runs and 60 prior cells from the 2026-10-13 study. The plan states the multiplier as 2.37, and the judge used it. The plan's own formula gives 2.49 at N = 90, and 2.37 corresponds to N of about 64 (`verdicts.md` says about 66, an arithmetic slip). No verdict differs between 2.37 and 2.49 (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase2/verdicts.md`, "How each condition was read" and flag 1).

**Amendment A-2026-10-21** was added before run 1. Its text says sections 1–9 stand as written, but A3 replaced the 1.98 multiplier in section 5 condition 1 with 2.37, and A6 added a condition-2 check on the Delta-funding line (`…/phase1_plan.md` §10):

| Item | What it added |
|---|---|
| A1 | After-tax CAGR on three readings: VDA 30 % per realized coin segment, VDA 30 % per positive coin-day, slab 30 % on net |
| A2 | D-3, the drift from the 00:00 decision to the 00:05 fill, conditional on trade direction; if the absolute mean drift on buys or sells exceeds 2 bps, re-run the daily cost lines with it |
| A3 | Haircut with N_eff = 90, and a flag for parameters already seen in a local run (COST-2 m, SIG-2 d, OVL-2 window and threshold, TIME-1 K) |
| A4 | Phase 3 pass rule on fidelity only: paper equity within $8 a month of its model line at $1,000, orders, fees and funding within 20 %, every rebalance executed |
| A5 | Intraday-low equity and on-venue leverage reporting |
| A6 | Delta-funding stress line: majors floored at 0.01 %/8 h, other coins scaled by the 2025–26 Delta/Binance ratio (as written; the harness ran a different floor, see Funding and Limits) |
| A7, A8 | New cells SZ-17 (hourly realized-variance vol) and SIG-13 (trend on the funding-adjusted index) |
| A9 | Open-interest diagnostic D-2, deferred to the annual review |
| A10 | D-4, Delta MARK closes against last-trade closes on panel C |

**Deliberately not pursued** (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase1_plan.md` §8; one line each there):

| Candidate | Reason it was not run |
|---|---|
| SIG-5 Sepp-Lucic LS(250,20) | Weakest of three systems in its own verified source (0.47 vs 0.55) with 2–3x the turnover; a 750-day warm-up removes panel C |
| SIG-6 Baz MACD trio | Below the sign rule on zero-cost futures (1.11 vs 1.39) |
| SIG-8 14/28-day votes | 81 % agreement with the 20-day sign; (10,30,60) already tested at 1.08 |
| SIG-12 skip-k signal lag | A control expected to be negative in crypto; +24 h lag already within noise |
| SZ-2 CC30 / EWMA 32–35 | Already run: null on A and B, −0.13 to −0.16 on C, turnover +8–11 % |
| SZ-4 fractional Kelly TV | Sharpe-neutral by construction; a sentence, not a backtest |
| SZ-5 vol floor | The low-vol-before-crash mechanism is absent locally; binds only on BTC and BNB |
| SZ-7 portfolio covariance targeting | Already run: failed on A and C (DD −30.6 %, turnover 2.3x) |
| SZ-8, SZ-9 own-P&L vol targeting | A long/flat book's own vol measures participation, not risk |
| SZ-10 semi-deviation | No return-vol asymmetry locally (−0.141 vs −0.143) |
| SZ-11, SZ-12 conditional vol, attenuation | The rejected realized-vol filter family in continuous form |
| SZ-14 greedy integer optimiser | Prize inside the ±0.08 rounding noise; cannot be hand-executed |
| SZ-15 proportional funding penalty | Already run: harmful (1.25 → 1.08 / 1.20; Delta 0.99 → 0.54 / 0.84) |
| SZ-16 Parkinson / GK / YZ vol | At 30 days noisier than CC60 and 8–10 % above it; at 60 days a 37–41 % over-forecast of realized vol; the Delta loader has O = H = L = C |
| UNI-3 age floor, UNI-5 capital-aware N | Folded into UNI-1 as a neighbour and as its feasibility gate |
| UNI-4 liquidity floor | A universe change by the back door, for a slippage prize of at most 0.02 Sharpe |
| UNI-6 correlation-aware selection | The low-correlation names (TRX, XMR, ZEC) are untradeable at this size |
| UNI-7 funding eligibility gate | Cells below 30 % and all 60-day cells lose; OVL-2 covers the question |
| COST-1 Carver proportional buffer | Collapses to rounding below $2,500; run as COST-2 neighbours |
| COST-3 weekly contract buffer | Fails its own acceptance (Delta $1,000 −0.07) |
| COST-4 passive post-only with taker fallback | Not testable on candles; needs a real order path and the user's go-ahead |
| COST-5 fee tier, COST-6 speed limit | A checklist item and a heuristic, not trials |
| OVL-1 market-drawdown de-risking | The "crash state" covers 73 % of days |
| OVL-4 Daniel-Moskowitz | Fires on 0.8 % of days; the mechanism needs a short leg |
| OVL-5 correlation spike | SZ-6b carries the one correlation trial |
| OVL-6 basket gate, OVL-7 dominance gate | Close to the rejected BTC-200-day state; a BTC tilt in disguise |
| TIME-2, TIME-5 | Run as labelled neighbours of TIME-1, never selected |
| TIME-6 asymmetric cadence, TIME-7 cool-down | No study; measured cost of 0.03–0.06 Sharpe |
| DATA-2 per-coin half-spread | Inside the tested 2–10 bps envelope |
| The 2026-10-13 rejected list | Market making, option selling, carry, ML, on-chain, sentiment, shorts, regime filters, stops, weekday choice and so on: none re-run |

## What the literature says, angle by angle

Web access was poor. The proxy blocked arXiv, SSRN, journals and blogs. Only raw GitHub files, data.binance.vision and the Delta India API opened, and several angles ran after the shared search budget was spent. So most literature facts below are search-summary level. The code facts are first-hand (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase1/notes/academic_signal.md`, the Sourcing and proxy-probe paragraphs and §0; `…/phase1/notes/costs_funding.md` §0; `…/phase1/notes/overlays.md`, Method).

### Academic signal construction

- **At matched speed, the shape of the signal is a second-order effect.**
  - Levine and Pedersen show that time-series momentum and moving-average crossovers are the same linear filters, and they perform similarly at every horizon ([SSRN 2603731](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2603731) [UNVERIFIED]).
  - Sepp and Lucic test 84 futures (data 1959–2026). Against the SG Trend Index over 2000–2026, net of costs and 2/20 fees, their linear system scores Sharpe 0.47, their binary system 0.50 and their normalised-sign system 0.55. Ledoit-Wolf p-values of 0.96, 0.82 and 0.62 cannot tell them apart, and the binary system turns over about half as much ([tsmom_system.md](https://raw.githubusercontent.com/ArturSepp/TrendFollowingSystems/405871df74923634f1b1eb38e53cfcfa7fd7aa60/docs/tsmom_system.md) [VERIFIED]). Their Bussgang argument says a sign signal keeps about 0.80 of the linear signal's covariance with returns.
  - On 88 futures at zero cost, the continuous MACD trio scored 1.111 against 1.392 for the 12-month sign ([arXiv 1904.04912](https://arxiv.org/abs/1904.04912) [UNVERIFIED]).
  - Baltas and Kosowski's t-statistic "TREND" rule is "insignificantly different" from sign. Its turnover saving is quoted as 24 % (TREND alone), more than a third (TREND with Yang-Zhang vol) or two thirds (an earlier version) in different summaries ([CME PDF](https://www.cmegroup.com/education/files/demystifiing-time-series-momentum-strategies.pdf) [UNVERIFIED]).
- **Speed.** Moskowitz, Ooi and Pedersen find all 12 monthly lags positive and longer lags mostly negative ([SSRN 2089463](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463) [UNVERIFIED]). Hurst, Ooi and Pedersen blend 1-, 3- and 12-month signals over 67 markets back to 1880 ([AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing) [UNVERIFIED]). Blending speeds is the standard design, and our 20/60/120-day blend follows it. A blend does not always beat the best single speed, though. Goulding, Harvey and Mazzoleni's equal slow/fast blend beats both legs on US equities (0.51 against 0.41 and 0.34), but on 43 futures over 1990–2022 the 1/3/12-month average scores 0.59 against 0.64 for the static 12-month rule ([tradingstrategy-ai notes](https://raw.githubusercontent.com/tradingstrategy-ai/docs/master/source/learn/trend-following.rst) [SECONDARY]). In the repo's own grid the 120-day lookback alone scored 1.21 against 1.12 for the blend, a pick `resource/07-trend-rule-and-prop-trading-research.md` rejects as selection.
- **Turning points.** Goulding, Harvey and Mazzoleni's dynamic slow/fast rule scores 0.80 against 0.64 for a static 12-month rule on 43 futures from 1990 to 2022. Over 2009–2022 it scores 0.22 against 0.06, and the authors write "the fix is not to trade faster" ([tradingstrategy-ai notes](https://raw.githubusercontent.com/tradingstrategy-ai/docs/master/source/learn/trend-following.rst) [SECONDARY]).
- **Barbell.** A vendor paper that drops the 125-day horizon is in-sample and Bayesian-weighted ([arXiv 2510.23150](https://arxiv.org/abs/2510.23150) [UNVERIFIED]).
- **What Phase 2 found.** Every signal cell was flat or worse, which is what this literature predicts (results table below).

### Academic sizing (volatility targeting)

- **Vol targeting cuts tails everywhere but raises Sharpe mainly for risk assets.** That is Harvey et al. on 60+ assets from 1926 to 2017 ([SSRN 3175538](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538) [UNVERIFIED]). Kim, Tse and Wald find time-series momentum profits "largely driven by volatility scaling" on 55 futures ([SSRN 2786955](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2786955) [UNVERIFIED]), which matches the repo's finding that the signal adds only 0.1–0.2 Sharpe.
- **Scaling a book by its own variance fails out of sample.** Moreira-Muir-style scaling failed for most of 103 equity strategies (Cederburg et al., [RePEc](https://ideas.repec.org/a/eee/jfinec/v138y2020i1p95-117.html) [UNVERIFIED]). That is why own-P&L scaling was not run.
- **Carver's production estimator** is a 35-day EWMA blended 0.7/0.3 with a long-run mean ([vol.py](https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/sysquant/estimators/vol.py) [VERIFIED]).
- **Local diagnostics** [LOCAL]:
  - A centre-of-mass-60 EWMA has 40 % less weekly noise than the rule's 60-day window (0.067 vs 0.113) and slightly better 30-day accuracy.
  - The 30-day range estimators run 8–10 % above close-to-close vol and forecast it worse; the 60-day ones forecast better but 37–41 % too high (`…/phase1/verify_sizing.md` SZ-16).
  - Average pairwise correlation sits at a median of 0.72, so the Baltas-Kosowski correlation factor barely moves (1.07–1.37) (`…/phase1/notes/academic_sizing.md` §2).
- **What Phase 2 found.** SZ-1, SZ-3, SZ-17 and SZ-6b all failed.

### Crypto academic

- **Strongest support.** Han, Kang and Ryu find that time-series momentum survives costs and liquidation of leveraged positions while cross-sectional momentum does not. Their best pair (28-day lookback, 5-day hold) scores Sharpe 1.51 against 0.84 for the market, "mainly from reduced downside" ([AUT PDF](https://acfr.aut.ac.nz/__data/assets/pdf_file/0009/918729/Time_Series_and_Cross_Sectional_Momentum_in_the_Cryptocurrency_Market_with_IA.pdf) [UNVERIFIED]).
- **Speed.** Kang and Ryu find a slow 12-week signal beats fast ones in Bitcoin, and dynamic speed "adds little" ([Springer](https://link.springer.com/article/10.1057/s41283-026-00234-7) [UNVERIFIED]).
- **The short leg is the problem.** Grobys et al. trace cross-sectional crypto momentum crashes to single coins in the short leg ([Springer](https://link.springer.com/article/10.1007/s11408-025-00474-9) [UNVERIFIED]), and find no momentum payoff among survivor coins ([RePEc](https://ideas.repec.org/a/eee/finlet/v92y2026ics1544612326001339.html) [UNVERIFIED]). Both support staying long/flat.
- **Donchian ensemble.** Zarattini, Pagani and Barbon report BTC from 2015 net of costs at Sharpe 1.56 and drawdown −19 % ([SSRN 5209907](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907) [UNVERIFIED]; rules from third-party transcriptions [SECONDARY]). This is a vendor paper and in-sample on crypto only. The one independent pre-registered re-test (BTC 2023–26) got Sharpe 0.97 against 0.975 for buy-and-hold, with drawdown −15.0 % against −53.0 % ([galata-research](https://raw.githubusercontent.com/sercanatalik/galata-research/29d35e1ffee5d26d9700de9d890a2f9d0693725a/planning/preregistered/donchian-ensemble.md) [SECONDARY]). That is the same shape as our rule: drawdown control, not extra Sharpe.
- **Pre/post spot ETF.** A small preprint reports Sharpe 0.82 before against 1.22 after, with p = 0.58 ([Zenodo](https://zenodo.org/records/19671502) [UNVERIFIED]).
- **Day of week.** That literature is unstable in sign and sample (`…/phase1/notes/crypto_academic.md` §1.29).
- **The plain caveat:** nearly all of this is in-sample, crypto only, often three to twenty coins, and several papers are vendor or single-author.

### Practitioner trend (Carver, AQR, Man AHL, Clenow)

- **Carver's code** [VERIFIED]:
  - EWMAC is `(EWMA_fast − EWMA_slow) / 35-day price vol`, and breakout is `40 × (P − mid)/(max − min)`, smoothed ([ewmac.py](https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/systems/provided/rules/ewmac.py), [breakout.py](https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/systems/provided/rules/breakout.py)).
  - The defaults buffer 10 % of the average position and trade to the edge of the buffer ([defaults.yaml](https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/sysdata/config/defaults.yaml)).
- **Notes on Carver's 2023 book** say "evidence in favour of using trend strength in a forecast to size positions was weak, at least for the EWMAC64", and that rules slower than EWMAC(64,256) are "too correlated with a long only strategy" ([AFTS notes](https://raw.githubusercontent.com/majkong14/advanced-futures-notes/main/README.md) [SECONDARY]).
- **Carver's cost units, applied to our books** [SYNTHETIC]: trading costs come to 0.03–0.10 Sharpe a year, while funding on longs costs 0.23–0.33. Funding, not fees, is the binding cost (`…/phase1/notes/practitioner_trend.md` §1).
- **Diversification comes from uncorrelated groups.** AQR's "Trends Everywhere" reports gross Sharpe 1.17 for traditional assets, 1.34 for alternatives and 1.60 combined ([AQR PDF](https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/AQR-Trends-Everywhere_JOIM.pdf) [UNVERIFIED]).
- **Stops reshape drawdown, not edge.** A Clenow replication finds the EMA filter alone earns as much as the full model, and the stop only cuts drawdown from −28 % to −21 % ([replication](https://github.com/lwang-genomics/trend-following-replication) [UNVERIFIED]).

### Crypto practitioners and open-source code

- **"Shape, not return" is the consensus.** Summitward (BTC, ETH and SOL, 2017–2025) finds vol scaling alone at Sharpe 0.74 and drawdown −17 %, and the full trend rule at 0.79 and about −15 % ([Summitward](https://summitward.com/learn/crypto-trend-following) [UNVERIFIED]).
- **Man Group** puts peak risk-adjusted return at 10–15 coins, a cost and liquidity statement ([Man](https://www.man.com/insights/in-crypto-we-trend) [UNVERIFIED]).
- **Grayscale** finds BTC moving-average rules "not particularly sensitive to the choice of the lookback window" ([Grayscale](https://research.grayscale.com/reports/the-trend-is-your-friend-managing-bitcoins-volatility-with-momentum-signals) [UNVERIFIED]).
- **Every single-author crypto trend repo read is in-sample.**
  - TrendCore beats buy-and-hold Sharpe on only 50 % of 64 other assets, but has a shallower drawdown on all of them, after about 350 logged trials ([README](https://raw.githubusercontent.com/0x-boss/quant_crypto_strategy/master/README.md) [VERIFIED]).
  - The one repo read with a train and out-of-sample split is a cross-sectional one, a rejected family. It goes from training Sharpe 0.42 to −2.18 out of sample in 2025–26 ([README](https://raw.githubusercontent.com/prams2104/crypto-momentum-backtest/main/README.md) [VERIFIED]).
- **Carver's execution algorithm** rests passively for up to 300 s, then crosses on time-out, adverse move or book imbalance ([algo_original_best.py](https://raw.githubusercontent.com/robcarver17/pysystemtrade/master/sysexecution/algos/algo_original_best.py) [VERIFIED]). It is the model for the untested COST-4.

### Universe and diversification

- **Within crypto, breadth is not a lever.** Carver measures 102 futures as about 4.3 independent bets ([blog](https://qoppac.blogspot.com/2023/03/i-got-more-than-99-instruments-in-my.html) [UNVERIFIED]). Locally [LOCAL], nine large caps are 1.50 effective bets and 25 are 1.53, with correlation near 0.75 in bear years. That is why adding names did not help (`…/phase1/notes/universe.md` F3).
- **Survivorship bias.** Ammann et al. put it at 0.93 % a year value-weighted and 62.19 % equal-weighted on 3,904 coins ([SSRN 4287573](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4287573) [UNVERIFIED]). Hence the delisting-inclusive loader D-0.
- **Gold is the only real diversifier on Delta.** Its correlation to the nine-coin basket is 0.14 [LOCAL] and its funding about 5.5 % a year. Tokenized equity perps pay about 10.9 % a year at the funding cap, which prices them out [VERIFIED API] (`…/phase1/notes/universe.md` F4–F5).
- **At $1,000, whole contracts cap the universe near nine coins** (F7).

### Costs, funding and execution on Delta

- **Fees** [VERIFIED, [Delta API](https://api.india.delta.exchange/v2/products?contract_types=perpetual_futures)]: maker 0.0002, taker 0.0005 before GST, i.e. 2.36 / 5.90 bps after 18 % GST. The 2.12 / 5.31 bps in every cost line assumes a 10 % referral discount (0.018 % / 0.045 % × 1.18) that no source read in this study confirmed [SYNTHETIC] (`…/phase1/notes/costs_funding.md` §1.1). At 5.90 bps the daily book's fees would rise by about 0.09 % a year (14.8x turnover × 0.59 bps) and the weekly book's by about 0.02 % [SYNTHETIC]; COST-5 (confirm the tier from the first fills) covers this.
- **Funding mechanics.** Funding stamps change only at 00:00, 08:00 and 16:00 UTC. BTC never printed above 0.01 %/8 h in 22 months.
- **Realized funding paid by longs, 2025-01..2026-10:** BTC 8.09 %, ETH 7.75 %, BNB 11.62 %, XRP 5.42 %, DOGE 4.44 %, ADA −2.26 %, LTC −2.24 %, LINK −0.58 %, BCH −3.98 % a year of notional (`…/phase1/notes/costs_funding.md` §1.3).
- **Funding is a real cost but not an independent one** [LOCAL]. With the signal on, coin-days with trailing 7-day funding of 12–30 % a year are the best trend days on Delta: +74.5 bps (12–20 %, t 3.1) and +129.2 bps (20–30 %, t 3.2) next-day gross, against +31.4 bps at 30–50 % and −8.2 bps above 50 %. Binance 2022–26 has the same shape (+51.3 and +73.9 against +23.7 and +22.1). On Binance 2020–26 every bucket above 12 % earns about the same (+61.9 to +67.5 bps). A rule that trims exposure in proportion to funding was harmful (`…/phase1/notes/costs_funding.md` §2.2).
- **Passive execution study** [LOCAL]. Post-only orders with a 4 h taker fallback save 2–3 bps a side on BTC, ETH and XRP. They lose 1–6 bps on the thin alts, where 5–7 % go unfilled (§4).
- **Measured slippage.** Taker slippage in the daily paper book runs from 0.03 bps (BTC) to 6.61 bps (ADA) (§1.4).
- **Literature.** Patient execution beats market orders for slow traders (Harris and Hasbrouck, [doi](https://doi.org/10.2307/2331388); Frazzini, Israel and Moskowitz, [SSRN 3229719](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3229719); both [UNVERIFIED], from memory).

### Overlays

- **Crash timing comes from the short leg.** Daniel and Moskowitz's crash rule exists for the loser leg's rebound in long/short equity momentum ([notes](https://raw.githubusercontent.com/August-B-F/quantitative-trading-system/main/research/papers/momentum/momentum_crashes_daniel_moskowitz.md) [SECONDARY]). A long/flat book has no such leg. Locally [LOCAL], the bear state covers 27.6 % of days, and on those days the rule holds more gross, not less (`…/phase1/notes/overlays.md`).
- **Vol management is real but narrow.** A Moreira-Muir replication raises momentum Sharpe from 0.51 to 0.89 ([README](https://raw.githubusercontent.com/tanishhky/Equity-Factor-Volatility-Analysis/main/README.md) [VERIFIED]). Out-of-sample studies find it lower for most factors ([deep-dive notes](https://raw.githubusercontent.com/ms-tristan/trading/main/research/literature/sources/volatility_targeting_trend_deep_dive.md) [SECONDARY]).
- **Correlation does not predict losses.** Average correlation predicts higher next-quarter equity returns, not lower (Pollet and Wilson, via [notes](https://raw.githubusercontent.com/Sami-Andaloussi/alpha-factory/main/alpha-lab/strategies/CA-015-01-average-correlation-timing/reasoning.md) [SECONDARY]).
- **Reading.** Risk-stabilising overlays have small, multi-asset support. Return-timing overlays bind on exactly the recoveries that make the long-only book's year.

### Timing and cadence

- **Rebalance timing luck is real and documented across assets.** It is the spread of returns between identical portfolios rebalanced on different dates, and it falls roughly as 1/N with N staggered tranches (Hoffstein, Sibears and Faber, [SSRN 3319045](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3319045) [UNVERIFIED]). Smart-beta indices show it "often exceeding 100 bps annualized" ([Newfound](https://blog.thinknewfound.com/2019/11/the-dumb-timing-luck-of-smart-beta/) [UNVERIFIED]).
- **The closest cross-asset analogue.** J.P. Morgan's multi-asset 12-month time-series momentum ranges from Sharpe 1.08 to 1.26 by rebalance day ([CME PDF](https://www.cmegroup.com/education/files/jpm-momentum-strategies-2015-04-15-1681565.pdf) [UNVERIFIED]). That 0.18 range is close to our FULL weekday range on A and B (0.21, 0.22); POST and Delta are wider (0.25–0.44) (`…/phase2/reference.md`) [SYNTHETIC ranges].
- **Tranching has a cost for small accounts.** Concretum finds about 350 bps a year between the best and worst schedule in US equity momentum, and says a $25k account is better off with about two tranches because trading frictions dominate. That is a vendor paper ([Concretum PDF](https://concretumgroup.com/wp-content/uploads/2026/02/The-Tranching-Dilemma.pdf) [UNVERIFIED]).
- **Overlapping portfolios** are standard in the momentum literature (Jegadeesh and Titman, [NBER w7159](https://www.nber.org/system/files/working_papers/w7159/w7159.pdf) [UNVERIFIED]).
- **No crypto paper on timing luck was found.**
- **Repo evidence.** A pure execution delay of up to 24 hours is free; which close the signal samples is not (`…/phase1/notes/timing_cadence.md` §0, §4).

### The dropped tenth angle

"Extra data and open-source code" was dropped for capacity. Part of it was covered by the completeness critic, which found the Binance open-interest archive. The open-interest diagnostic D-2 is deferred to the annual review under amendment A9 (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase1/notes/completeness_critic.md`).

## Results

All 26 primary cells, from `cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase2/verdicts.md` (table and detail sections). B POST gains are paired against the target baseline. d = daily book vs D, w = weekly book vs W, t = tranche book vs W. The hurdle is max(0.05, 2.37 × sd), and it applies to class I only. Panel B figures are on the unpatched archive except UNI-1's, which come from `…/uni1_verify/synthesis.md` §1.

| Cell | Change | Class | B POST gain | 95 % CI | Hurdle | Verdict and decisive number |
|---|---|---|---|---|---|---|
| SIG-2 | Vol-normalised clipped ensemble | I/II | d +0.016, w −0.128 | d −0.17..+0.23, w −0.33..+0.04 | 0.240, 0.221 | FAIL: loses on Delta, C FULL d −0.144, w −0.233 |
| SIG-1B | t-stat dead zone | I/II | d −0.115, w −0.157 | d −0.39..+0.22, w −0.46..+0.16 | 0.365, 0.373 | FAIL: funding −36 to −42 % as hoped, but B H1 d −0.388 |
| SIG-3a | EWMAC binary | I/II | d −0.105, w −0.074 | d −0.48..+0.30, w −0.42..+0.33 | 0.473, 0.451 | FAIL: gross +36 to +42 % (hidden beta); A POST d −0.282 |
| SIG-3b | EWMAC continuous | I/II | d −0.127, w −0.091 | d −0.53..+0.35, w −0.50..+0.43 | 0.531, 0.558 | FAIL: C FULL d −0.619 |
| SIG-4 | Donchian ratchet ensemble | I/II | d +0.008, w −0.049 | d −0.28..+0.32, w −0.34..+0.22 | 0.364, 0.340 | FAIL: C FULL d −0.365, w −0.397 |
| SIG-7A | Add a 250-day sleeve | I | d −0.229, w −0.061 | d −0.46..+0.02, w −0.27..+0.20 | 0.293, 0.285 | FAIL: P(gain ≤ 0) 0.96 on the daily book |
| SIG-10 | Linear agreement count | I | d −0.063, w −0.149 | d −0.37..+0.24, w −0.39..+0.11 | 0.366, 0.297 | FAIL: gross +47 to +57 %; Delta-funding stress A POST d −0.105 |
| SIG-9 | Turning-point tilt | I | not run | | | FAIL by gate D-1: Correction below Bull on the 24 in both windows: −0.31 % vs +0.88 % (2020–26) and −0.79 % vs +0.05 % (2022–26), next 7 days |
| SIG-11 | 50/50 breakout + sign | I | d +0.011, w −0.020 | d −0.07..+0.10, w −0.10..+0.07 | 0.105, 0.103 | FAIL: breakout alone below sign, A FULL d −0.172 |
| SIG-13 | Sign on funding-adjusted index | I | d −0.036, w −0.016 | d −0.09..+0.04, w −0.10..+0.06 | 0.081, 0.092 | FAIL: negative in both B halves on daily (−0.067, −0.062) |
| SZ-1 | EWMA vol, COM 60 | II | d −0.058, w −0.045 | d −0.15..+0.02, w −0.12..+0.02 | | FAIL: turnover only −7 to −13 % on A, B and C (needed −15 %) |
| SZ-3 | Carver mixed vol 0.7/0.3 | II | d −0.060, w −0.066 | d −0.15..+0.04, w −0.15..+0.03 | | FAIL: turnover −2 to −5 % (needed −10 %) |
| SZ-17 | Hourly realized-variance vol | II (A, C) | no B | | | FAIL: A POST d −0.080, C FULL d −0.151 |
| SZ-6b | Correlation factor | I | d +0.011, w +0.001 | d −0.03..+0.05, w −0.04..+0.04 | 0.050, 0.050 | FAIL: extra +0.05 on A, B, C; A FULL −0.019 |
| SZ-13 | Minimum-contract eligibility | II ($1,000) | no B | | | FAIL: orders barely move (A daily 871.5 → 871.5 a year; C weekly −3.9 %) |
| UNI-1 | Yearly liquidity-ranked 9 | Research | d +0.256, w +0.273 | d −0.24..+0.73, w −0.24..+0.77 | | FAIL after the data fix: daily matched-vol maxDD −24.51 % vs −24.01 % |
| UNI-2 | Gold as a tenth instrument (its B is the 24 plus DOGE, plus gold, vs those 25) | I | d +0.093, w +0.088 | d +0.01..+0.20, w +0.02..+0.18 | 0.112, 0.100 | FAIL: below hurdle; B+gold H1 −0.017 |
| COST-2 | Contract buffer, b 0.10, m 0.75 | II | d +0.030 | −0.01..+0.07 | | FAIL: fee cut 0.189 pp at A $1,000 (bar 0.20); C $1,000 path effect +0.133 (bound ±0.08) |
| OVL-2 | Funding cut-out, 30 d > 30 % a year | I | d +0.138, w +0.105 | d −0.04..+0.46, w −0.05..+0.32 | 0.305, 0.225 | FAIL: P 0.12, 0.13; B H1 d −0.125 |
| OVL-3 | Fast-exit veto | I | d −0.075, w −0.029 | d −0.19..+0.02, w −0.13..+0.05 | 0.125, 0.107 | FAIL: negative on A, B and C |
| TIME-1 | Tranche K = 7, TV 0.25 | I vs W | t +0.176 | +0.03..+0.33 | 0.183 | FAIL on two: 0.007 short (P 0.009); 594 orders a year at $1,000 on A (cap 350) |
| TIME-3 | Decision-hour tranche | I | d +0.059, w +0.007 | d −0.05..+0.17, w −0.13..+0.12 | 0.131, 0.151 | FAIL: weekly A FULL 1.110 vs six-hour mean 1.21 |
| TIME-4 | Two hand sessions, Mon + Thu | I vs W | w +0.159 | +0.03..+0.31 | 0.169 | FAIL on two: 0.010 short (P 0.005); 332 orders a year at $1,000 (cap 220) |
| COMBO-A | TIME-1 + SZ-1 + COST-2 | I vs W | t +0.123 | −0.05..+0.29 | 0.205 | FAIL: B POST 0.053 below TIME-1 alone (allowed 0.03) |
| COMBO-B | SIG-2 + SZ-1 + COST-2 | I/II | d −0.045 | −0.25..+0.14 | 0.236 | FAIL: orders rise 1–38 % instead of falling 30 % |
| COMBO-C | TIME-1 + TIME-3 | I vs W | t +0.165 | +0.02..+0.32 | 0.184 | FAIL: below TIME-1 on every panel (B POST −0.010) |

No class I or class II cell failed exactly one condition; the closest were TIME-1 and TIME-4, with two failures each (`…/phase2/verdicts.md`, "Near misses"). UNI-1 (research class) fails exactly one clause on corrected data: daily matched-vol maxDD −24.51 % vs −24.01 % (`…/uni1_verify/synthesis.md` §1; the verdicts' "Near misses" section predates that correction). The final line of the verdicts reads: "no cell passes. The running rule is unchanged; no third paper book."

### Timing luck: the weekly book sits on the worst weekday

The weekly book decides on the Sunday candle and trades at Monday 00:05 UTC. Across the seven possible decision candles, that slot is the lowest on every panel and window measured (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase2/reference.md`; TIME-1 lines from `…/phase2/verdicts.md` TIME-1, condition 6a):

| Decision candle | A FULL | A POST | B FULL | B POST | C FULL |
|---|---|---|---|---|---|
| Mon | 1.263 | 0.788 | 0.856 | 0.509 | 1.012 |
| Tue | 1.184 | 0.797 | 0.870 | 0.617 | 0.956 |
| Wed | 1.335 | 0.906 | 0.964 | 0.775 | 1.069 |
| Thu | 1.314 | 0.910 | 1.032 | 0.826 | 1.055 |
| Fri | 1.226 | 0.834 | 0.908 | 0.663 | 1.141 |
| Sat | 1.164 | 0.752 | 0.822 | 0.563 | 0.919 |
| **Sun (the running weekly book)** | **1.121** | **0.660** | **0.810** | **0.492** | **0.704** |
| Seven-weekday mean | 1.230 | 0.807 | 0.895 | 0.635 | 0.980 |
| sd across weekdays [SYNTHETIC] | 0.079 | 0.088 | 0.080 | 0.128 | 0.142 |
| Daily book at TV 0.25, band 10 | 1.252 | 0.849 | 0.856 | 0.596 | 1.011 |
| TIME-1 tranche | 1.239 | 0.818 | 0.920 | 0.667 | 0.976 |

Choosing any one weekday is a lottery of about ±0.1 Sharpe. The design kept the worst one on purpose, so as not to fit the weekday to the data (`resource/07-trend-rule-and-prop-trading-research.md`). Tranching removes the lottery instead of choosing a winner. TIME-1 trades daily toward the mean of the last seven daily targets, which is the netted position of seven weekly books, one for each weekday.

TIME-1's FULL Sharpe lands within 0.03 of the seven-weekday mean on all three panels: A +0.010, B +0.025, C −0.003. Its turnover is no higher than the weekly book's (B 2.87x against 2.94x a year). It also improves drawdown on B FULL to −14.3 % from −17.0 %. The plan required the gain to be split into two parts:

| Panel | TIME-1 vs weekly book | Weekday luck (mean − Sunday) | Variance reduction (TIME-1 − mean) |
|---|---|---|---|
| A | +0.119 | +0.109 | +0.010 |
| B | +0.110 | +0.085 | +0.025 |
| C | +0.272 | +0.275 | −0.003 |

So almost all of the gain is the running book's bad weekday, not a skill of tranching. The skill part is +0.010, +0.025 and −0.003. On the primary metric, TIME-1 gained +0.176 (CI +0.03 to +0.33, P 0.009, sd 0.0773). That is 0.007 below the 0.183 hurdle. It also needs 594 orders a year at $1,000 on A, and 409 on C, against a cap of 350 (the weekly book makes 171 and 131). The cap fails at every capital tested ($1,000 / $2,500 / $5,000: 594 / 774 / 875 orders on A).

The control line shows what tranching buys. The daily book at TV 0.25 (K = 1) gains +0.105 on B POST but turns over 7.99x a year. TIME-1 gains +0.176 at 2.87x.

The other timing cells say the same thing. TIME-4 (two hand sessions, Monday and Thursday) gained +0.159 against a 0.169 hurdle, and needs 332 orders a year at $1,000 against a 220 cap. TIME-3, which averages the signal over six decision hours, gained only +0.007 on the weekly book. COMBO-C, which stacks both axes, came in 0.010 below TIME-1 alone on B POST, so the hour axis adds nothing on top of the weekday axis (`…/phase2/verdicts.md` TIME-3, TIME-4, COMBO-C).

The practical reading:

- Tranching costs nothing on average and removes about ±0.1 Sharpe of path luck.
- It needs daily execution, which in this repo means a bot.
- If the weekly hand book is ever replaced by a bot book, tranching is the first change to re-test on the gap-patched data. It must be tested against the bot version `resource/07-trend-rule-and-prop-trading-research.md` already names, the daily rule with the 10 % band, which this study did not run as such. The nearest line here is the K = 1 control (daily at TV 0.25 with a 10 % band). It gains less than TIME-1 on B POST (+0.105 against +0.176) at 2.8 times the turnover, but more on A FULL (+0.132 against +0.119) and on C (+0.307 against +0.272) (`…/phase2/verdicts.md` TIME-1).
- Today it is designed only. `cex-mm/scripts/trend_paper.py` has `--weekly`, `--band`, `--target-vol` and `--orders-only` flags and no tranche mode (checked 2026-10-22).

### UNI-1: a number that reproduces but fails its own rule

UNI-1 resets the universe every January to the nine USDT-M perps with the highest trailing 30-day median turnover. Entrants need at least 365 closes, and incumbents stay while ranked 18 or better. On the original data it passed the research-number rule. The four-lens check then found the pass rested on a data defect (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/uni1_verify/synthesis.md` §1).

The archive downloader dropped failed files silently. DASHUSDT for 2022-10 was missing, and Binance's monthly files lack 2022-02-26..28 and 2022-04-01..02 for 51 symbols. Each gap restarts the 121-close rule. Filling the 71 coin-rows from Binance's own files moved static-24 to 0.860 daily and 0.819 weekly, which is the plan's own gate. On that data the daily book fails the drawdown clause:

| Book | FULL Sharpe vs static-24 | POST gain [95 % CI], P | H1 / H2 gain | Matched-vol maxDD vs static-24 | Raw maxDD |
|---|---|---|---|---|---|
| Daily | 1.046 vs 0.860 | +0.256 [−0.24, +0.73], 0.13 | +0.161 / +0.231 | −24.51 % vs −24.01 %, **FAIL** | −26.82 % vs −24.01 % |
| Weekly | 0.984 vs 0.819 | +0.273 [−0.24, +0.77], 0.13 | +0.083 / +0.296 | −16.59 % vs −16.75 %, ok | −18.20 % vs −16.75 % |

**What survives.** An independent rebuild reproduced every number to four decimals. No look-ahead was found in 480 of 480 tests. A placebo of nine random coins drawn each January from the eligible top 18 puts UNI-1 at the 96.5th (daily) and 100th (weekly) percentile. The sign of the gain survives shifting the reset date, N from 5 to 12, and the Delta-funding stress. The one exception is the weekly book with SOL removed from the world (−0.008) (§2).

**What narrows it.**

- **Timing.** On the daily book the POST gain comes mostly from 2023 and 2024 (vol-matched yearly return gap +11.6 % and +5.9 %; 2022 −0.1 %, 2025 +2.8 %, 2026 +0.6 %; `…/uni1_verify/robust/notes.md` §1). The POST gain over 2025–26 alone is +0.095 daily and +0.002 weekly.
- **Concentration.** The nine coins UNI-1 shares with the static 24 earn +1.038 in UNI-1 against +0.421 in static-24, at about 2.7x the weight. Coins only UNI-1 holds add +0.271 (summed daily P&L before costs, FULL, daily book), of which SOL is +0.128 and DOGE +0.109.
- **Knife edges.** In 2023, EOS missed rank 18 by 2.5 % of turnover. LUNA missed the age floor by 26 days. With no hysteresis the weekly gain is +0.025.
- **Against the books that actually run.** From 2024-05, UNI-1 beats the live nine by +0.04 daily (P 0.42) at 0.96 correlation (§3).

**It cannot be traded at $1,000.** SOL holds 0.66 (daily, TV 0.40) / 0.42 (weekly, TV 0.25) contracts at full signal at $1,000. The gate code used contract values 7.65x too large for SOL, which wrongly drops it at every capital up to $5,000. Delta funding ran about twice Binance's at book level in 2026-Q3: 3.09 % vs 1.54 % a year on the UNI-1 daily book, and the same 2.01 ratio on the nine (§4–5; `…/uni1_verify/live/notes.md` §5).

**Decision.** UNI-1 is "do nothing". A parked spec for a $5,000 daily paper book exists, to be used only if the annual review passes (synthesis §5).

### Gold

Adding gold as a tenth instrument (UNI-2, PAXG spot as the proxy, synthetic funding of 5.5 % a year) gained +0.093 daily and +0.088 weekly on B+gold vs the 25 coins (the 24 ex-ante perps plus DOGE), POST. The CIs exclude zero (P 0.012 and 0.009), but the gains fall short of the 0.112 and 0.100 hurdles. The decisive failure is timing. B+gold H1 is −0.017 on both books, and the extra condition on the pre-bull window fails (A+gold H1 −0.047). Meanwhile A+gold POST is +0.21. The gain is the 2024–26 gold bull, the thing the plan wrote its extra condition to exclude (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase2/verdicts.md` UNI-2). PAXG returned +30 % in 2024 and +65 % in 2025 (`…/phase1/notes/universe.md` F4).

The diversification case remains real. Gold's correlation to the nine is 0.14, which takes effective bets from 1.50 to 1.75. But about six years of gold data, with one bull run in them, cannot separate diversification from that bull. The pre-registered realistic-cost neighbour, at XAUT's 1 bp taker fee, was never run, and its code is a no-op (verdicts UNI-2; `…/phase1/verify_universe.md`).

### Funding

Funding is the book's largest running cost. The weekly baseline pays 1.93 % of equity a year on B against 0.22 % in fees (`…/phase2/summary.md`; verdicts OVL-3 detail). It is also the most tempting thing to "fix", and every fix failed:

- **OVL-2, the funding cut-out**, goes flat on a coin while its 30-day funding exceeds 30 % a year. It cut funding on B daily from 3.13 % to 1.25 % and gained +0.138 / +0.105, but at P 0.12 / 0.13 and with a negative H1 (−0.125 / −0.067). It also cost 2.33 pp of CAGR. Outside 2021 (the plan's count leaves 2021 out) it binds in 88 episodes on the daily book, 58 of them in 2020, and 72 on the weekly. Only 30 and 27 of them are from 2022 on, and 23 of those coin-runs sit in one 2024-03/04 cluster (`…/phase2/verdicts.md` OVL-2).
- **SIG-13**, which runs the signal on a funding-adjusted price index, lowered funding but lost Sharpe on both books.
- **SZ-15**, a proportional funding penalty, was already harmful in Phase 1 and was not re-run.
- **The Delta-funding stress line (A6)**, as the harness ran it, floors each of the nine at its own Delta 2025–26 mean funding and leaves every other coin on Binance funding (`…/engine/harness.py`, `delta_funding_stress`). The floors are BNB 11.62, BTC 8.09, ETH 7.75, XRP 5.42 and DOGE 4.44 % a year. For LINK, LTC, ADA and BCH the mean is negative, so their floor binds only on days when Binance funding is even lower. That line lowers the baseline's A POST Sharpe from 0.837 to 0.787 daily and from 0.660 to 0.608 weekly, and B weekly POST from 0.492 to 0.471 (`…/phase2/results/baseline.json`, `…/phase2/results/TIME-1.json`).
  - The plan's A6 text is different: max(Binance, 0.01 %/8 h) for BTC, ETH, BNB, LTC and BCH, and Binance × the Delta/Binance mean ratio for the other coins. It was run after the review, unchanged in every other respect (`…/phase2/a6_plan/`). Read literally, the ratios for ADA (−0.76) and LINK (−0.12) are negative, and the 15 coins with no Delta record take a pooled ratio of 0.52, so on B the "stress" lowers funding. A POST is then unchanged from the as-run line (0.787 / 0.608), and B POST rises slightly on the daily book (0.586 to 0.590) and stays at 0.492 on the weekly.
  - With every ratio clipped at 1, so the line is never milder than Binance, A POST falls to 0.753 daily and 0.577 weekly, and B POST to 0.552 and 0.459.
  - No verdict moves under any of the three readings. A6 gates condition 2 only for SIG-3a, SIG-10 and UNI-2. On A POST SIG-3a stays at −0.29 to −0.31 daily and SIG-10 at −0.10 to −0.11, both below −0.03, and UNI-2 stays above +0.20. All three fail class I condition 1 anyway.
  - It is a level cost, not a reason to change the rule.

### Costs and execution diagnostics

- **COST-2, the contract buffer** (daily book: hold while the position is within max(0.10 × target, 0.75 contracts) of the unrounded target). It cut orders by 37 / 43 / 48 % at $1,000 / $2,500 / $5,000 on A, and by 35–42 % on C, for B POST +0.030 [−0.01, +0.07] (unrounded). It fails on four counts:
  - the fee cut on A is 0.189, 0.188 and 0.197 pp, under the 0.20 pp bar (condition 3);
  - its neighbours m = 1.0 and the two COST-1 cells do not keep the fee-and-orders gain (condition 4);
  - on Delta at $1,000 the Sharpe effect is +0.133, outside the ±0.08 bound that marks a position-path effect rather than a cost saving (extra 6a);
  - its required 2022–23 and 2025–26 windows were not produced (extra 6b).

  Against the 10 % band, COST-2 trades the same number of orders at A $1,000 (548 vs 549) for 0.15 pp less in fees (`…/phase2/verdicts.md` COST-2).
- **D-3, decision-to-fill drift, 00:00 → about 00:10 UTC** (Binance 5 m, 2024-01..2026-09). The code takes the 00:00 bar's open and the close of the bar that opens at 00:05, so the window is about ten minutes, although `…/phase2/diagnostics.md` labels it 00:00 → 00:05; the VM book fills at about 00:05:13–00:05:29 (`…/phase1/notes/completeness_critic.md`). Buys drift +0.05 bps (t 0.07) and sells +3.79 bps (t 3.55). Prices rise before the book sells, which favours the seller. The A2 trigger (an absolute mean above 2 bps) fired on sells; because the drift favours the seller, the re-run was waived and every cell kept the 7.31 bps line (`…/phase2/diagnostics.md` D-3; decision in `…/phase2/summary.md`, Diagnostic outcomes).
- **D-4, Delta MARK vs last-trade closes.** The sleeve signs agree 99.61 / 99.86 / 99.89 % of the time. The daily rule scores 0.994 on last-trade and 0.985 on MARK; the weekly 0.704 and 0.709. Either series is fine. A third book would use last-trade closes, as the parked UNI-1 spec does.
- **COST-4, passive execution,** was not tested. It needs a real order path and the user's go-ahead (`…/phase1_plan.md` §9).

### Tax lines

Amendment A1 carried three after-tax readings on every line. Over the FULL window (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase2/results/TIME-1.json` `base_tax` and `tax`; `…/phase2/results/COST-2.json` B-daily `base_tax`):

| Line | Pre-tax CAGR | VDA 30 % per segment | VDA 30 % per coin-day | Slab 30 % on net |
|---|---|---|---|---|
| B, weekly baseline | 8.7 % | +3.9 % | **−12.0 %** | +5.8 % |
| B, weekly baseline, POST only | 4.4 % | +1.1 % | −12.1 % | +2.7 % |
| B, TIME-1 tranche | 9.6 % | +5.0 % | −10.7 % | +6.5 % |
| B, daily baseline (TV 0.40) | 13.6 % | +4.1 % | −18.4 % | +9.2 % |
| C, weekly baseline (Delta) | 7.0 % | +2.7 % | −10.7 % | +4.7 % |

These are backtest CAGRs (B over 2020-05..2026-09, C over 2024-08..2026-10), not forecasts. `resource/07-trend-rule-and-prop-trading-research.md` sets the forward expectation at Sharpe 0.3–0.8, about +4 % to +9 % a year before tax. Over 2025-01..2026-10 the weekly book on Delta, unrounded, made +0.1 % a year before tax (at $1,000 in whole contracts, resource/07's line, +4.5 % in 2025 and −0.6 % in 2026, about +2.1 % a year; `TIME-1.json` C-tranche `capital` `1000.0` `base`), and −0.2 % / −2.5 % / −13.7 % after the slab / per-segment / per-coin-day readings (`…/phase2/results/TIME-1.json`, C-tranche h2 `base`, `base_tax`).

Under the per-coin-day reading, all 1,040 after-tax lines in the result files (520 `tax`, 520 `base_tax`) are negative. The least negative is −3.7 % (SIG-3b weekly on the nine, H1 2020–23, a book that is mostly flat); on B it is −4.1 % (SIG-3b weekly, POST). The spread between the slab and per-coin-day readings on the weekly baseline is about 18 points a year (+5.8 % vs −12.0 %), twice the baseline's pre-tax CAGR of 8.7 % [SYNTHETIC]. No tested change makes the per-coin-day reading positive. Gate 0, a written CA opinion on which reading applies, stays the first step before any money (`resource/07-trend-rule-and-prop-trading-research.md`, Gate 0).

## Data and engine defects found (fixed, or recorded for later)

| Defect | Effect | Fix and consequence |
|---|---|---|
| The downloader dropped failed files silently (DASHUSDT 2022-10), and Binance's monthly files lack 2022-02-26..28 and 2022-04-01..02 for 51 symbols | Each gap restarts the 121-close rule and removes the coin for about four months; static-24 read 0.851 / 0.810 instead of 0.860 / 0.819 | 71 coin-rows filled from Binance's own files, for the UNI-1 re-check only. UNI-1 flips to FAIL. Every other verdict stands: each failing cell except OVL-2 also fails a condition that does not use panel B. OVL-2's three failures (B POST +0.138 vs hurdle 0.305, B H1 −0.125, B FULL CAGR −2.33 pp) all use panel B and were not recomputed on patched data. The patch moved static-24 by 0.009, against a 0.167 gap to the hurdle, so a flip is unlikely but unchecked (`…/uni1_verify/synthesis.md` §1, §4; `…/phase2/verdicts.md` correction and OVL-2) |
| COST-2 engine bug: the 0.75-contract floor was applied to unrounded lines and centred on the rounded target | The first COST-2 and COMBO-A runs barely traded (B FULL Sharpe 0.33 for COST-2 and 0.14 for COMBO-A, turnover 0.2x and 0.0x) | Fixed to the plan's rule before judging; the baseline re-verified to 1e-15; the invalid runs are struck through (`…/phase2/summary.md` engine note) |
| Zombie archive files keep zero-volume rows after delisting | A frozen close would leave a dead position at the 5 % vol floor | Membership by quote volume above zero; delisting day = last day with volume (`…/phase1/verify_data.md`) |
| UNI-1 gate used $25 / first close as the contract value for coins outside the nine | Off by 7.65x for SOL, 7.1x AVAX, 6.7x 1000PEPE, 3.5x ZEC | Recorded; to be fixed before any UNI-1 book (`…/uni1_verify/synthesis.md` §4) |
| Judge-time flags | Haircut multiplier 2.37 vs the formula's 2.49; sd = CI width / 3.92; COMBO-A's unrounded line used the buffer; UNI-2 neighbour (b) never ran; COST-2 windows missing; some report items saved nowhere | None changes a verdict (`…/phase2/verdicts.md`, data and implementation flags) |

`resource/07-trend-rule-and-prop-trading-research.md` had already recorded five missing 2022 closes in XRP and LTC as immaterial on the nine (T7 #4). These are the same gaps (2022-02-26..28 and 2022-04-01..02), so panel A and the running rule's backtests carry them too. On the 24-coin panel they hit seven coins (XRP, LTC, TRX, XLM, ZEC, IOTA and VET; 51 symbols across the audited pool). They are not what flips UNI-1's daily drawdown clause. Patched alone, they leave static-24's max drawdown at −24.67 %. The missing DASHUSDT 2022-10 file, patched alone, takes it from −24.74 % to −24.08 %, past UNI-1's matched-vol −24.19 % (`…/uni1_verify/audit/patch_attr_out.txt`; `…/uni1_verify/audit/notes.md` §5).

## What would change the decision

- **The annual review, with one more year of data.** The UNI-1 re-test is fixed now, so nothing new is tuned later (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/uni1_verify/synthesis.md` §5):
  - settings: N 9, January reset, 30-day median turnover, age 365, keep-rank 18, start from the top 9 on 2020-04-30;
  - data: the gap-patched survivorship-free panel, extended through the latest quarter;
  - clauses: all four on both books, with matched-vol drawdown against the patched static-24, plus raw drawdown and the Delta-funding line reported;
  - comparator: static-24, never the nine.

  A third book starts only if every clause passes on both books, and only with the user's go-ahead. Optionally, the 2027-01-01 reset can be computed and archived untraded, so the review has a truly ex-ante membership list.
- **A bot book replacing the hand book.** Re-test TIME-1 on gap-patched data with the order count measured at the real capital, against resource/07's daily 10 %-band bot version. Tranching is the first change to re-test in that case.
- **Capital of $5,000 or more.** That is the plan's live floor for UNI-1. The 2026 universe reaches two contracts per member at about $3.1k daily and $4.9k weekly. The expected 2027 entrant ZEC needs about $8.3k daily and $13.3k weekly, so the weekly UNI-1 is not recommended below about $13.3k (`…/uni1_verify/live/notes.md` §3; synthesis §5).
- **A CA opinion.** It decides whether any version earns money after tax.
- **The paper books' own gates continue unchanged.** The daily book's four-week paper test ends around 5 November (four weeks from 8 October, `cex-mm/artifacts/research/2026-10-08-trend-following-backtest.md`). The weekly book's Gate A falls around 16 November (four Mondays from 19 October, `cex-mm/artifacts/research/2026-10-13-prop-strategy-research.md`) [SYNTHETIC dates].

## Limits

- **The literature is snippet-level.** Almost every paper and blog number above is a search summary. The proxy blocked the pages, and some angles ran with no web search at all. Only the pysystemtrade code, a few READMEs, the Sepp-Lucic documents, data.binance.vision and the Delta API were read first-hand. The literature shaped which cells were tested. It did not decide any verdict.
- **Binance is a proxy for Delta.** Panels A and B use Binance USDT-M prices and funding. Delta's funding on the majors is higher (the A6 stress costs 0.05 to 0.08 Sharpe on A POST, depending on the reading; see Funding). Panel C is only 794 days, and the slowest signals barely warm up on it.
- **The sample is short.** POST is 1,734 days, in a market whose correlation regime changes every year. Most CIs in the table span zero by a wide margin. A 0.1 Sharpe effect needs years to confirm.
- **Panels A and B in the table are unpatched.** Only UNI-1's numbers were recomputed on the patched archive. Every other verdict stands because each failing cell except OVL-2 also fails a condition that does not use panel B. OVL-2's three failures (B POST +0.138 vs hurdle 0.305, B H1 −0.125, B FULL CAGR −2.33 pp) all use panel B and were not recomputed; the patch moved static-24 by 0.009, against a 0.167 gap to the hurdle, so a flip is unlikely but unchecked. SIG-9's D-1 gate is also read on the 24 coins, but there Correction sits 1.2 and 0.8 percentage points of 7-day return below Bull, far beyond what the patch could move. The B levels will move by about 0.01.
- **A5 was only partly reported.** The intraday-low equity line was not written to any result file. Only max gross and the share of days above 0.6x were. Under A5, UNI-2 is flagged: on the nine plus gold, daily, max gross is 1.15x against 0.87x, and gross is above 0.6x on 11.8 % of days against 4.6 % (`…/phase2/results/UNI-2.json`, A10-daily). No other variant crosses the 0.2x line.
- **Four departures from the frozen plan, none of which changes a verdict:**
  - the A6 stress line floored the nine at their own Delta 2025–26 means and left other coins on Binance funding, instead of the plan's 0.01 %/8 h floor on BTC, ETH, BNB, LTC and BCH and the Delta/Binance ratio elsewhere; the review of this write-up found it, and the plan's version was then run and moves no verdict (Funding above; `…/phase2/a6_plan/notes.md`);
  - the T0/D-0 gate was missed (static-24 0.851 / 0.810 against 0.86 / 0.82) and waived by the judge as an engine difference; the UNI-1 check later traced it to the archive gaps (`…/uni1_verify/synthesis.md` §1);
  - A2 required the daily cost lines to be re-run with the D-3 drift, because sells drifted +3.79 bps; this was not done, and no gain was credited (`…/phase2/summary.md`, Diagnostic outcomes, D-3);
  - OVL-3 was opened on the unconditional Correction state, while on the signal-on reading of its cited source its gate was closed (+0.61 % / +0.09 %); the cell fails either way (`…/phase2/verdicts.md` OVL-3).
- **The TIME-1 knife edge cuts both ways.** It missed the hurdle by 0.007, about 4 % of the hurdle.
  - At the plan's original multiplier (1.98, hurdle 0.153) it would pass that condition. At the plan's own N = 90 formula (2.49, hurdle 0.193) it misses by 0.017. The 2.37 was fixed before the run, and changing it after seeing 0.176 would be exactly the tuning the plan exists to prevent.
  - In the other direction, the order cap fails at every capital whatever the hurdle, so the cell fails anyway. The B number is on unpatched data and could move either way. And the part of the gain that is skill rather than escaping the bad weekday is only +0.025 on B.
  - The honest summary: tranching very likely removes the weekday lottery, and very likely adds no edge beyond that. The test was not powered to prove the first part at this hurdle.
- **The judge is mechanical.** Where the plan text was ambiguous, the judge took the reading closest to it and recorded the choice (`cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase2/verdicts.md`, "How each condition was read"). Missing evidence counted as a failure.

## In plain English

**What we asked.** We have a simple rule. Hold a full position in a coin when its price is above where it was 20, 60 and 120 days ago, a third of a position when two of the three are true, and nothing otherwise. The position is sized so that jumpy coins get less money. We asked whether research papers or professional traders know a better version, and tested every idea we found.

**What we found.** The rule already sits close to what the literature recommends:

- it blends several lookbacks;
- it scales positions by volatility;
- it never goes short, which is where crypto momentum crashes;
- its 20-, 60- and 120-day lookbacks overlap the range the crypto papers found best, roughly one to thirteen weeks, and the 120-day leg is slower than most of them (`…/phase1/notes/crypto_academic.md`, summary table; `…/phase1/notes/academic_signal.md` §2, point 3).

Most "improvements" turned out to be noise or hidden beta. Some made the book hold more crypto more of the time. That looks better in a rising market and worse on a fair test. Gold looked good only because gold had a great 2024–25. Smarter volatility formulas and fancier signals changed the main test by less than its noise, and several were clearly worse on the Delta data.

**The one real issue.** The weekly book decides at Monday 00:00 UTC (05:30 IST), on the daily candle of the Sunday that just ended. In our history that happens to be the unluckiest of the seven days, on every data set we have. That is not a flaw anyone can predict or fix by picking another day, because the "best" day would just be the luckiest one in hindsight. The cure is to spread the decision over all seven days. This costs nothing on average and removes the luck, which is worth about ±0.1 Sharpe either way. But it means trading a little every day, which needs a bot. So it waits until a bot book replaces hand execution.

**What matters more than any of this.** How Indian tax treats these contracts. Under the strictest reading (30 % on every profitable coin-day, no set-off) every version loses money after tax. Under 30 % on each coin's realized gains with no set-off, the weekly book keeps under half of its backtest return (+3.9 % of +8.7 % a year) and the daily book under a third (+4.1 % of +13.6 %). Only if the profit is taxed as business income at a 30 % slab on the net does it keep about two thirds (+5.8 %, +9.2 %). These are backtest returns, not forecasts. A written opinion from a chartered accountant comes first.

**What happens now.** Nothing changes. Both paper books keep running as they are, and their four-week checks continue. The ideas that came close are written down with fixed re-tests for next year, so that no one can tune them after seeing more data.

## Sources (evidence pack files)

- `cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase1_plan.md` and `…/plan_sha256.txt`: frozen plan, amendments, not-pursued list.
- `cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase1/notes/{academic_signal,academic_sizing,crypto_academic,practitioner_trend,crypto_practitioners,universe,costs_funding,overlays,timing_cadence,completeness_critic}.md`: literature with URLs and tags.
- `cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase1/master_candidates.md` and `…/phase1/verify_*.md`: candidate list and adversarial verifications.
- `cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/phase2/summary.md`, `…/phase2/verdicts.md` (including its 2026-10-22 correction), `…/phase2/diagnostics.md`, `…/phase2/reference.md`, `…/phase2/results/*.json`.
- `cex-mm/artifacts/research/2026-10-22-trend-improvement-evidence/uni1_verify/synthesis.md`, `…/uni1_verify/{rebuild,audit,robust,live}/notes.md`, `…/uni1_verify/synth/rerun_patched_clauses.txt`.
