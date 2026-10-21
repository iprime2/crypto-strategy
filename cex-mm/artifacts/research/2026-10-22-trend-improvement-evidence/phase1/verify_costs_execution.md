# Adversarial verification: COSTS_EXECUTION family (COST-1 .. COST-6), 2026-10-21

Role: refute. Verdict = keep / refine / drop. Read-only on the repo; no orders. New computation in this pass:
`research2/verify_tools/cost2_diag.py` (zero-cost and sub-period re-runs of the existing `sim/sim_costs.py`; output
`verify_tools/cost2_diag_out.txt`). Fetched and read (raw.githubusercontent.com, saved in `research2/verify_dl/`):
pysystemtrade `sysdata/config/defaults.yaml` (buffer_method forecast, buffer_size 0.10, buffer_trade_to_edge True: VERIFIED),
`sysexecution/algos/algo_original_best.py` (PASSIVE_TIME_OUT 300, TOTAL_TIME_OUT 600, IMBALANCE_THRESHOLD 5,
IMBALANCE_ADJ_FACTOR 3, SIZE_LIMIT 1: VERIFIED), `systems/buffering.py`. Delta `/v2/products` (local copy
`research2/products.json`): maker 0.0002 / taker 0.0005 on all nine, BTC tick 0.5, liquidation penalty 0.5 (BTC) / 0.2 (alts): VERIFIED.

## 0. What the repo already tested (the comparison set)

- `backtest_results.md` T3c (weekly Mon TV 0.25): no-trade band 0/5/10/20 % of target notional -> Sharpe 1.12/1.12/1.12/1.11,
  trades/yr 278/221/192/163. Daily TV 0.40 + 10 % band: 1.25, 531 trades/yr. T1: daily TV 0.25 band 10 %: 1.25, 538 orders, fees 0.67 %
  (vs 0.72 % no band). The band was adopted into the design (resource/07 rule block: `skip if |trade| < 10 % of |target notional|`).
- `calc/d2_checks_output.txt` 2a (daily, unrounded): band 0 / 0.10 / 0.25 -> Sharpe 1.25 / 1.25 / 1.25, trades 1773 / 531 / 433, fees 1.1 / 1.1 / 1.0 %/yr
  at TV 0.40; same at TV 0.25. 2c (Delta, whole contracts, band 0.10): $1,000 TV 0.40 0.93 -> 0.93 (566 -> 423 orders), $5,000 1.00 -> 1.01.
  So a 25 % proportional band was already run: zero Sharpe effect, fees -0.1 pp/yr. This brackets COST-1.
- T5: whole-contract rounding is +-0.08 of Sharpe, non-monotone in capital ($500 1.09, $1,000 0.93, $2,500 0.97, $5,000 1.00 on the daily rule;
  0.72 / 0.81 / 0.70 / 0.69 vs 0.70 unrounded on the weekly design). This is the noise floor for any whole-contract test at $1,000.
- T3l slippage 2/5/10 bps -> 1.12/1.11/1.10 (weekly). T3k late execution +4 h -> 1.09, +8 h 1.11, +24 h 1.15 (within noise): a 4 h passive
  window costs nothing measurable on the weekly series; the daily series was not tested for lag.
- T3m / T1: fees 1.14 %/yr (daily TV 0.40), 0.25 % (weekly TV 0.25); funding 3.43 % / 2.11 % (Binance), 1.86 % / 1.04 % (Delta). Sharpe SE 0.50 (T6f).
- `sim/binance_out.txt` part C (local, this sweep): cost per side 7.31 -> 5.31 -> 3.0 -> 1.0 -> 0 bps gives Sharpe 1.24 -> 1.26 -> 1.28 -> 1.29 -> 1.30
  (Binance) and 0.93 -> 0.94 -> 0.95 -> 0.99 -> 0.99 (Delta). The whole execution-cost channel is worth <= 0.06 of Sharpe on the daily book.
- `2026-10-13-live-run-pickoff.md`: real-money MM run on ADA, 172 maker fills, net60 -3.6 bps/fill, fills arrive when quotes are stale
  (Binance moved 1.97 bps toward the quote in the 2 s before); 13 of 3,247 post-only placements rejected (`immediate_execution_post_only`).
  `.claude/rules/cex-mm.md`: Delta book froze 44 min on 17 Oct with frames still arriving.
- `designs/D2.md` 2.6 (rejected design): "limit order at the touch, post-only, for 60 s; if unfilled, replace with an IOC limit at the far touch";
  judges' objection was the taker order path breaking the MM bot's post-only invariant and the unverified bot, not the execution economics.
  Never backtested in the repo.
- resource/07 plan, weeks 1-4, Gate A: "one 1-contract round trip per coin to read real fees and slippage; measured cost <= 2 x 7.31 bps per side".
  Fee measurement from first fills is already in the plan.
- resource/07 "considered and rejected": daily bot cadence kept as the upgrade path ("the daily rule with the 10 % band is the bot version").
  The live daily paper book runs with band 0 (costs_funding note 1.5), i.e. the already-tested band is not even switched on.

## 1. New diagnostic: is the COST-2 Sharpe gain fees or position path? (`verify_tools/cost2_diag_out.txt`)

Daily TV 0.40, $1,000, whole contracts; "ZERO cost" = same engine with cost = 0 so the only difference between rules is the position path.

| sample | round-nearest 7.31 / ZERO | buffer b.10 m.75 7.31 / ZERO | buffer b.10 m1.0 7.31 / ZERO | buffer b.25 m1.0 7.31 / ZERO |
|---|---|---|---|---|
| Delta 2024-08..2026-10 | 0.93 / 0.99 | 1.06 / 1.13 | 1.09 / 1.13 | 1.12 / 1.16 |
| Binance 2020-05..2026-09 | 1.24 / 1.30 | 1.26 / 1.31 | 1.28 / 1.32 | 1.24 / 1.28 |
| Binance 2022-01..2023-12 | 0.42 / 0.49 | 0.44 / 0.49 | 0.49 / 0.55 | 0.48 / 0.56 |
| Binance 2025-01..2026-09 | 0.50 / 0.58 | 0.53 / 0.58 | **0.38 / 0.42** | **0.39 / 0.45** |
| Binance 2024-01..2026-09 | 1.08 / 1.15 | 1.17 / 1.20 | 1.14 / 1.19 | 1.15 / 1.18 |
| Binance 2020-26, 7 coins (BTC and BNB removed) | 1.07 | - | 1.08 | - |

Reading:
- The fee channel is worth +0.01 to +0.03 of Sharpe everywhere (round-nearest 7.31 vs ZERO is 0.06-0.08; the buffer closes a third of that).
  That part is arithmetic and robust: fees 1.08-1.15 %/yr -> 0.68-0.96 %/yr at 16.9-18.7 % vol.
- Everything beyond that is position path: at ZERO cost the Delta sample still shows 0.99 -> 1.13 (+0.14) and the 2025-26 sample shows
  0.58 -> 0.42 (-0.16) for m = 1.0. Removing BTC and BNB from the book (the two coins whose full-signal position is ~1 contract at $1,000)
  removes the effect entirely (1.07 -> 1.08). Mechanism: with m >= 0.75 and a full-signal position A_i of ~1.2 contracts, BTC/BNB are opened
  at a 2/3 signal (m = 0.75) or only at a full signal (m = 1.0) and closed only when the signal is exactly 0, i.e. a 1/3 signal keeps a
  $73-83 contract against a $24-28 target. That is hysteresis on the two largest coins, not cost saving, and its sign flips by sub-period.
- m = 0.75 never goes negative in any window tested (path effect 0.00 to +0.14); m = 1.0 is -0.16 in 2025-26. The candidate's primary m = 1.0
  is the wrong primary.
- The 10 %-of-target band cuts order count (872 -> 550) but not dollars (15.7 -> 15.2x) because a 0<->1 contract flip is 100 % of its target:
  that claim in the candidate is confirmed by the engine output and is the real argument for a contract-space floor.

## 2. Verdicts

### COST-1 Carver forecast buffering, B_i = F x A_i (full-on position), trade to edge -> REFINE (fold into the COST-2 grid; no standalone claim)
- Prior test: T3c (band 0/5/10/20 % of target), `calc/d2_checks_output.txt` band 0.25 (Sharpe 1.25 -> 1.25, fees 1.1 -> 1.0 %/yr, orders 1773 -> 433).
  At full signal F x A_i = F x target, so F = 0.10 is the T3c 10 % band; at a 1/3 signal it is a 30 % band. The 10 % and 25 % proportional bands
  bracket it and both give identical Sharpe. Not an untested idea; a re-parameterisation of a tested one.
- Small-account arithmetic (the candidate states it, the numbers confirm it): the rounded edges collapse to plain rounding unless F x A_i >= 0.5
  contracts, i.e. A_i >= 5 contracts at F = 0.10. At $1,000: A_BTC ~1.2, A_BNB ~1.0, A_ETH ~3 contracts -> rounding on the three coins that
  generate the flips (costs_funding 1.5: BNB $365 + BTC $165 + ETH $122 of $1,320 traded in 11 days). At $2,500 BTC/BNB still collapse.
  So at the user's capital COST-1 acts only on XRP/ADA/DOGE/LINK/LTC/BCH, where the existing band already acts. Expected fee saving
  between `--band 0.10` (1.11 %) and the m = 0.5 cell (1.03 %): ~0.1 pp/yr = 0.005 of Sharpe. Bounded above by the whole cost channel (0.06 SR).
- Evidence quality: pysystemtrade defaults VERIFIED (forecast / 0.10 / trade-to-edge), AFTS formula via reader notes; multi-asset practitioner
  default with a mechanism, but no published before/after numbers (Carver's "doesn't hurt if not too wide" is a blog claim, UNVERIFIED).
- Refined rule: run as one or two cells of the COST-2 grid (F = 0.10 and 0.20 of A_i = (TV/N)/max(sigma_i, 0.05) x E/(P_i x cv_i), lower = round(N_i - B),
  upper = round(N_i + B), trade to the nearer edge, N_i = 0 -> close), reported next to the proportional band and the floored buffer, same
  acceptance as COST-2; it is the >= $5,000 form of the same mechanic. Test cost: trivial (sim_costs.run already computes sigma_i in its
  fmode branch; ~10 lines to pass A_i).

### COST-2 Contract deadband B_i = max(b|u_i|, m) for the daily bot book -> REFINE (cost-only claim, m = 0.75 primary, pre-registered acceptance)
- Prior test: T3c / d2_checks (proportional band, zero Sharpe effect); T5 (rounding noise +-0.08). Materially different: absolute floor in contracts,
  trade-to-edge, hold-through-1/3-signal hysteresis on 1-contract coins. The local sim (sim/binance_out.txt, delta_out2.txt, VERIFIED by re-running)
  is the only evidence and is in-sample on the 9-coin hindsight universe.
- Refutation of the headline: the candidate sells Sharpe 0.93 -> 1.09 (Delta) and -15.2 -> -11.9 % DD. Section 1 shows 0.14 of the 0.16 is
  position path that reverses to -0.16 in 2025-26 for the same m = 1.0, and vanishes when BTC/BNB are removed. The 2024-26 Delta window is
  2.2 years dominated by Aug-Dec 2024 (T7 #5), exactly where holding BTC through 1/3 signals paid. The honest claim is fees -0.25 to -0.45 pp/yr
  (= +0.01 to +0.03 SR), orders -35 to -40 %, with Sharpe and DD within rounding noise.
- What survives: the mechanism (a 0<->1 contract flip costs 2 x 7.31 bps on a ~$80 position for a 1/3-signal change that the unrounded rule would
  have traded as $24) is real and specific to whole contracts at $1,000-2,500; Carver's own note that 10 %-of-average buffers fail on small
  positions (UNVERIFIED thread) is the same point. It is also free to implement (plan_orders in trend_paper.py, ~15 lines).
- Refined rule: at each 00:05 UTC rebalance u_i = w_i E/(P_i cv_i); B_i = max(0.10 |u_i|, 0.75) contracts; u_i == 0 -> close; held_i in
  [u_i - B_i, u_i + B_i] -> no trade; else trade to the integer inside the band nearest held_i (none -> round(u_i)). Sensitivity cells m = 1.0 and
  b = 0.25 reported, never selected. Pre-registered acceptance: fees/yr down >= 0.20 pp AND paired 20-day block-bootstrap Sharpe difference vs
  round-nearest with |mean| <= 0.08 and the CI containing 0 on all of: Binance 9-coin 2020-26, 24-perp ex-ante 2020-26, Delta 2024-26, sub-windows
  2022-23 and 2025-26, at $1,000 / $2,500 / $5,000. Also print the share of coin-days on which B_i > A_i/3 (band wider than one signal step) so the
  hysteresis is visible; if that share exceeds ~20 % at $1,000 the rule is a signal change for those coins and must be stated as such.
- Test cost: trivial for the 9-coin panels (engine exists); small for the 24-perp panel (sim_costs uses tb.COINS and the memo contract values;
  needs a universe loader and contract values for the 15 extra perps, which Delta does not list for all of them -> use notional-rounded
  pseudo-contracts of $25). Note the daily paper book runs with band 0 today; `--band 0.10` is already tested (T3c, d2_checks 2c) and is a
  no-evidence-needed switch.

### COST-3 Weekly hand book contract deadband m = 0.75 -> DROP
- Prior test: T3c (weekly band 0/5/10/20 %: 1.12/1.12/1.12/1.11, orders 278 -> 192 -> 163), T5 (band removes 2-28 orders/yr at rounded sizes, no Sharpe change).
  The candidate's own numbers (sim/binance_out.txt, delta_out2.txt weekly rows): fees 0.26 -> 0.21 %/yr (Binance), 0.25 -> 0.17 (Delta);
  Sharpe Binance 1.10 -> 1.11 / 1.12 / 1.11, Delta $1,000 0.79 -> 0.72, $2,500 0.70 -> 0.70, $5,000 0.69 -> 0.72; m = 1.0 at $1,000 Delta 0.63;
  Binance $1,000 maxDD -17.4 -> -18.7 %. Hand orders 172 -> 154 (Binance) and 131 -> 107 (Delta) per year, i.e. 18-24 fewer, not 35
  (the 35 compares against round-nearest, which the design does not use).
- The candidate's own acceptance (|dSharpe| <= 0.05 on all three samples) is already failed by its own evidence: Delta $1,000 is -0.07.
- Ceiling: the weekly book's entire fee line is 0.25 %/yr = 0.02 SR; the saving is 3-8 bps/yr = $0.3-0.8 at $1,000, below the T6d measurement
  floor ($3.88/30 d) by an order of magnitude. The only benefit is ~20 fewer hand orders a year against a hand process whose documented main
  risk is operator error; a second band definition (contracts and percent) in a spreadsheet is a complication, not a simplification.
- If COST-2 passes, the weekly book inherits the same plan_orders code at no evidence cost; no separate candidate is needed. Test cost trivial, but not worth a cell.

### COST-4 Passive post-only at the touch with taker fallback -> REFINE (coin-scoped, one parameter, live A/B item, not a Phase 2 backtest)
- Prior test: none in the repo. Closest: D2 2.6 "post-only at the touch for 60 s, then IOC" (never run; design rejected on other grounds);
  live MM run (-3.6 bps/fill net60, continuous quoting, does not transfer: a one-shot order whose counterfactual is a taker fill at the same
  arrival benefits from any fill at or inside the arrival mid regardless of the 60 s markout; the conditional non-fill branch is where the
  cost sits and the local sim prices it from real hourly paths). T3k: +4 h lag on the weekly series 1.12 -> 1.09 (noise), so the window is affordable.
- Local evidence (sim/passive_out.txt, passive_exec.py VERIFIED read): Delta hourly 2025-01..2026-10, fill if the level is traded through by
  >= 1 tick within H; at H = 4 h BTC fill 98.9/99.1 %, saving +2.0/+2.6 bps per side; ETH +2.0/+2.4; XRP +3.3/+2.2; stable across H 1-8 h and
  trend conditioning. Thin alts negative (BNB -1 to -2, LINK -6, LTC -2 to -3, BCH -2 to -3). The saving is just the maker/taker differential
  3.19 bps minus the non-fill drift, so it is fee arithmetic on verified fees, not a crypto anomaly.
- Refutations of the candidate as written:
  (1) The all-coin 300 s / 600 s variant has no evidence: the sim never ran H < 1 h, and its own table says passive loses on 5 of 9 coins. Drop that variant.
  (2) The adverse-move (3 bps) and imbalance (5:1, 3x) triggers are Carver's futures defaults (VERIFIED constants) with no measurement here;
      they add 3 free parameters that cannot be backtested on candles. Drop them; keep the single H and the stale/frozen -> taker rule the
      bot already implements (BookWatch / FrozenBookWatch thresholds, not new numbers).
  (3) Size of the prize at the user's capital: 14.7x/yr turnover x 29 % share (BTC+ETH+XRP) x ~2.5 bps = ~11 bps/yr before buffering, ~7 after:
      $0.7-5.5/yr at $1,000-5,000, +0.005 of Sharpe. The candidate's "+0.3-0.7 %/yr daily" is the all-coin extrapolation its own sim refutes.
  (4) It cannot be verified from public data: hourly candles stand in for a queue; the real fill rate needs >= 100 live orders, which needs a
      real order path for the trend book (none exists; the books are paper) and the user's explicit approval. So it is not a Phase 2 item.
  (5) Operational: a resting order through a 44-minute frozen book (17 Oct) is a new failure mode for a once-a-day bot; the fallback must be
      the existing frozen/stale detection plus a hard H, nothing discretionary.
- Refined rule: for coins with L1 spread <= 1.5 bps and 24 h turnover >= $10M at decision time (today BTC, ETH, XRP), post-only limit at the
  best price on our side for the full size at 00:05 UTC; poll every 5 s; at H = 4 h (or on stale/frozen book per BookWatch/FrozenBookWatch)
  cancel and send IOC at the far touch for the remainder; all other coins taker as now. Log arrival mid, fill price, fee class, fill time.
  Evaluate only live, on alternating days (passive vs taker) over >= 100 orders per coin, metric = fill vs arrival mid incl. fees; adopt if the
  mean saving > 0 with a 95 % CI excluding 0. Test cost: large (new live order path + approval); no further backtest is informative.

### COST-5 Referral fee tier and measured TAKER_BPS -> KEEP (operational checklist item; trivial; no backtest)
- Prior: resource/07 Gate A already measures fees from 1-contract round trips in weeks 1-4; trend_backtest.py comments TAKER_BPS 5.31 as
  "incl. GST (10 % referral discount)". The only new element is checking the tier before the first fill rather than after.
- Verified: base maker 0.0002 / taker 0.0005 on all nine products (API). Unverified: the 10 % referral discount, 18 % GST on fees, any VIP tier
  or maker rebate (none found in two sessions). Risk is asymmetric: the backtests already assume the discounted 5.31; without it the daily book
  pays 5.90 + slippage, i.e. 0.59 bps/side x 14.7x = 8.7 bps/yr more than modelled (2 bps/yr weekly). Worth <= 0.005 of Sharpe either way.
- Keep as written: confirm the tier on the account before the first fill, read the realized commission from the first fills (Delta fill records
  carry the commission), set TAKER_BPS and the paper books' fee constant to the measured value, and re-run Phase 2 cost lines only if the
  measured taker fee differs from 5.31 by more than 1 bp. Test cost: trivial (none).

### COST-6 Cadence by Carver's cost speed limit -> DROP
- Not a rule change: a decision heuristic whose output is monotone in an unobservable input (forward pre-cost Sharpe). On the repo's own numbers
  it never discriminates: fee cost in SR units is 0.061 (daily TV 0.40: 1.14 % / 18.7 %), 0.057 (daily TV 0.25 band 10), 0.020 (weekly) against a
  budget of 0.10-0.25 SR at any forward Sharpe >= 0.3-0.45; funding (0.18 SR) is cadence-independent, as the candidate itself concludes
  ("cadence is not a cost question; funding is"). A gate that passes every member of the candidate set, including a 2/week cadence (fees
  between 0.25 and 0.67 %/yr), changes no decision.
- The cadence question was already answered by direct measurement, which dominates a budget heuristic: T1 daily 1.25 vs weekly 1.12 at the same
  vol after all costs; the daily rule's extra 0.42 pp/yr of fees is recovered with 0.13 of Sharpe to spare. Carver's rule is for choosing a
  trading-rule speed when the cost per trade is the binding constraint; here it is not (practitioner_trend note: 39 RT/yr daily sits at the
  0.10 SR line with 55-75 % instrument vol).
- Evidence is a textbook rule of thumb (AFTS notes VERIFIED as a summary; book and blogs UNVERIFIED) with no asset-specific numbers.
- Residue worth keeping, not as a candidate: print fees/vol and funding/vol in SR units on every Phase 2 engine line (one formatting line) so
  cost claims are read in Sharpe, not percent. Test cost: trivial, but there is nothing to test.

## 3. Summary table

| id | decision | prior test in repo | evidence quality | test cost | honest expected effect |
|---|---|---|---|---|---|
| COST-1 | refine (cell of COST-2 grid) | T3c band; d2_checks band 0.25 | replicated practitioner default, no numbers | trivial | <= +0.01 SR; collapses to rounding on BTC/BNB/ETH at <= $2,500 |
| COST-2 | refine (m = 0.75 primary, cost-only claim) | T3c, T5 (noise floor) | single in-sample local sim; mechanism real | trivial (9-coin), small (24-perp) | fees -0.25 to -0.45 pp/yr (+0.01-0.03 SR); Sharpe path effect +-0.15 is noise |
| COST-3 | drop | T3c, T5 | own sim fails own acceptance | trivial | 3-8 bps/yr, Sharpe -0.07..+0.03 |
| COST-4 | refine (BTC/ETH/XRP, H = 4 h, live A/B) | none (D2 2.6 never run; live MM not comparable) | fee arithmetic + hourly-candle sim | large (live path) | ~7-11 bps/yr on the daily book, +0.005 SR |
| COST-5 | keep (ops checklist) | resource/07 Gate A | API verified base fee; tier snippet-only | trivial | avoids paying 8.7 bps/yr more than modelled |
| COST-6 | drop | T1 (cadence measured directly) | textbook heuristic | trivial | none; gate passes every cadence |

Files: this note; `research2/verify_tools/cost2_diag.py`, `research2/verify_tools/cost2_diag_out.txt`; fetched sources in `research2/verify_dl/`.
