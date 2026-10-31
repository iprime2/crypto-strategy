# Quant memo: the 30 Oct ADA stop. Every loss came in two volatility spikes; no size or cap reaches +1 bp/$; a missed fill broke the cap

**Date:** 2026-10-30 · **Venue:** Delta India mainnet (real money) + shadow public data · **Symbols:** ADAUSD · **Data:** live run `20261028T164352Z` (binary 05c87578, PR 74; 28 Oct 16:43:52Z – 30 Oct 02:02:52Z, 33.3 h, 1,930 maker fills + 18-contract taker flatten, Delta `/v2/fills` and wallet ledger); shadow `20261025T174640Z` ADA quotes and tape from 26 Oct 18:30Z to 30 Oct 02:03Z (79.4 h, 707,675 samples, 7,969 trades)

Evidence is in `2026-10-30-ada-stop-postmortem-evidence/`:
- `PREREG.md` (md5 fcdba7b8…), written 02:11Z, before any variant was run. The first variant runs started about 02:18Z.
- Raw outputs (`test1_out.txt`, `test2_out.txt`, …) and the scripts that produced them. `clip_replay_prereg.py` is Test 1 exactly as pre-registered.
- `FORWARD_PREREG.md` (md5 9605df5c…), written 02:26Z, pins the next experiment before any later data was simulated.

The scripts read only local copies and call no API.

## Question

The owner stopped the run when the stop rule said STOP (−1.14 bps per $ over 1,829 fills). We then flattened it.

- Where did the money go?
- Would a smaller quote or a smaller inventory cap have held +1 bp per dollar traded or better?
- If so, when can the bot restart?

## PnL attribution (capture / markout / fees / inventory), maker vs taker

Delta's wallet ledger over the run:

| Item | Amount |
|---|---|
| Balance at start | $332.60 |
| Balance at end | $330.83 |
| Cash flow | +$2.25 |
| Commission | −$3.95 |
| Funding | −$0.08 |
| **Total** | **−$1.77** |
| Trading only | −$1.69 = −0.51 bp/$ on $33,327 traded |

- The position was 0 at the start.
- All fills were maker except the flatten (18 at 0.1861, taker 5.31 bps).

Per fill, using the shadow's anchored fair as the reference (`clip_replay.py`; holding = position revaluation beyond 60 s):

| Window | Fills | ADA move | Time at 600 cap | Total | Capture | 60 s markout | Holding | Fees |
|---|---|---|---|---|---|---|---|---|
| W1 29 Oct 19:30–21:30Z | 136 | −4.1% | 19% | **−$7.52** | −0.83 | −0.61 | **−5.75** | −0.33 |
| W2 29 Oct 23:30Z–30 Oct 01:30Z | 182 | −2.6% | 22% | **−$2.28** | +0.34 | **−1.66** | −0.47 | −0.50 |
| Rest of the run | 1,612 | | | **+$8.10** | | | | |
| Whole run | 1,930 | −7.4% | 21% | −$1.70 | +11.58 | −4.76 | −4.57 | −3.95 |

**W1 was an inventory loss.** The bot was long and kept buying the dip up to the cap while ADA fell 4.1% in two hours. **W2 was adverse selection.**

Split by each hour's own realized volatility (median hour 61 bps; `hourly_split.py`):

| Hours | Fills | Notional | PnL | bp/$ |
|---|---|---|---|---|
| Calm (≤ 2× median) | 1,180 | $16,983 | +$4.28 | **+2.52** |
| Volatile (> 2× median) | 750 | $16,344 | −$5.98 | **−3.66** |

Volatile hours were 20:00Z (4.9× median), 00:00Z (6.2×) and their neighbours. Half the run's notional traded in them, because fills come faster when the price runs.

This split uses an hour's volatility known only at its end. It describes what happened; it is not a rule the bot could trade on.

**Fees.**
- 766 of the 1,930 fills (42% of notional) paid nothing under Delta's Scalper Offer (`scalper_offer_applied` in the fill metadata).
- The average maker fee was **1.18 bps, not the 2.12 list rate**.
- At list rate the run would have lost about −$4.81 (−1.44 bp/$).

## What the code actually does (vs config)

- **Quotes are the anchored fair ± 5 bps exactly.** The simulator's "bot quotes" row is identical to "fair +/- 5" in every leg. `MM_FIXED_HALF_SPREAD_BPS=5` overrides the 4–6 regime band.
- **The cap is enforced against the bot's believed inventory only.**
  - At 20:48:19.9Z the private fill feed dropped (connection reset), with a 3 s reconnect delay. Bid 1640249200 filled at 20:48:20.5Z inside that gap, and the feed never delivered the fill.
  - The next edit and cancel of that bid failed (400). The bot read the order state (`closed`) and `after_cancel` forgot the quote (`gone_after_cancel(false, Some("closed"))` → `clear_side`) without counting the 200 contracts.
  - Believing it held 400, the bot placed a new full-size bid (1640249324). It filled at 20:48:23.06Z: **position 800, cap 600.** The next 5 s position poll (20:48:23.47Z) caught up, and the bot sold back to 600 at 20:48:26.6Z.
  - Direct cost was small (−$0.08). But the hard limit failed in the middle of the worst dump.
  - This is the third overshoot of this kind, after −360 (reconcile overwrite) and 754 (PR #62). The common cause: inventory comes only from the private feed, there is no fills catch-up after a reconnect, and a quote found `closed` is not booked as filled.
- **The hourly check missed the breach.** It counts `over600` from the bot's own `MM_METRICS` inventory, which never showed more than 600. It should check the venue's fills.

## Findings, ranked by money at stake

1. **The strategy loses in volatility spikes and earns in calm.** −$9.80 in W1 + W2 against +$8.10 in the remaining 29 h. No size or cap change fixes this on its own (finding 2). The knob that addresses it is when to quote and how wide, not how much.

2. **Size and cap, as pre-registered: no restart candidate.**
   - **Test 1 is void.** Its sanity check failed: replaying variant A at the pre-registered 2.12 bps fee gave −$4.99 against the ledger's −$1.69 (diff −$3.29, limit $1.00). The 2.12 bps fee was wrong because of the Scalper Offer.
   - The decision rule requires Test 1, so **no variant qualifies.**
   - Test 2 (simulator, 2.12 bps, 27–30 Oct; PnL per $ at 300 ms strict / 1000 ms strict / 300 ms touch):

     | Variant (quote/cap) | 300 strict | 1000 strict | 300 touch | T2 |
     |---|---|---|---|---|
     | A 200/600 (live) | 0.56 | 1.02 | 1.72 | fail |
     | B 200/400 | 1.94 | 2.34 | 2.27 | pass |
     | C 200/200 | 2.74 | 2.86 | 2.54 | pass |
     | D 150/300 | 1.88 | 2.26 | 2.40 | pass |
     | E 100/300 | 0.92 | 1.05 | 2.21 | fail |
     | F 100/200 | 2.01 | 2.26 | 2.52 | pass |

   - **Exploratory, not pre-registered:** Test 1 again, with each real fill's own charged fee rate. The sanity check now holds (−$1.87 vs −$1.69).

     | Variant (quote/cap) | PnL | bp/$ | W1 |
     |---|---|---|---|
     | A 200/600 | −$1.87 | −0.56 | −$7.69 |
     | B 200/400 | +$1.90 | **+0.60** | −$5.04 |
     | C 200/200 | +$1.32 | +0.51 | −$3.69 |
     | D 150/300 | +$1.42 | +0.60 | −$3.78 |
     | E 100/300 | −$0.93 | −0.56 | −$3.85 |
     | F 100/200 | +$0.95 | +0.60 | −$2.52 |

     **None reaches +1.0.** In this replay only the cap counted in orders matters: 3 orders −0.56, 2 orders +0.60, 1 order +0.51. The quote size just scales the dollars. A 2-order cap would have taken a third off the W1 loss.

3. **The cap breach (bug above).** A hard risk limit failed during a dump. It needs a fix before any restart, whatever the strategy verdict.

4. **The shadow's headline leg was much too generous for ADA.** On the live span itself (`live_span_out.txt`, variant A):

   | Leg | Fills | Capture | 60 s markout | net60 at 2.12 | PnL bp/$ (Scalper fees) |
   |---|---|---|---|---|---|
   | 300 ms strict | 821 | 5.10 | +0.01 | +2.99 | −1.69 |
   | 300 ms touch | 1,864 | 5.16 | −0.81 | +2.23 | +1.79 |
   | **1000 ms touch** | **1,929** | 5.32 | **−2.67** | +0.53 | +0.86 |
   | **Real** | **1,930** | 4.47 | **−2.62** | **−0.27** | **−0.51** (as charged) |

   - The 1000 ms touch leg reproduces the real fill count and markout almost exactly. Its capture is 0.85 bp too high: the live bot skews its quotes for inventory and the shadow does not.
   - That leg still overstates real PnL by about 1.4 bp/$.
   - The 300 ms strict leg, which promoted ADA, overstated per-fill net60 by 3.3 bps.
   - **From now on, judge ADA on 1000 ms touch with the Scalper Offer on (`--scalper-window-min 15`), and subtract 1.4 bp/$.**

5. **The pre-registration's fee assumption was wrong.** For ADA, the list maker fee overstates real fees by about 0.9 bp. Future ADA tests use the Scalper Offer columns, with the list rate as a stress case.

## Exploratory: wider quotes (1000 ms touch, Scalper Offer, 27–30 Oct)

From `explore_out.txt`. Not pre-registered; this only picks the next candidate.

| Quote/cap | Half-spread | Fills | net60 | PnL | bp/$ | W1 | W2 |
|---|---|---|---|---|---|---|---|
| 200/600 | ±5 (live) | 3,643 | 2.36 | $11.46 | 1.97 | −6.59 | −2.41 |
| 200/600 | ±6 | 1,322 | 3.86 | $8.32 | 2.41 | −4.69 | +1.47 |
| 200/400 | ±5 | 3,467 | 2.20 | $13.29 | 2.45 | −4.93 | −1.37 |
| **200/400** | **±6** | 1,230 | 3.85 | $11.28 | **3.52** | −3.27 | +0.44 |
| 200/200 | ±6 | 1,020 | 3.83 | $13.05 | 4.94 | −1.52 | +0.88 |
| 100/200 | ±6 | 1,175 | 3.77 | $5.98 | 3.48 | −1.57 | +0.19 |

- ±6 beats ±5 at every cap. It cuts fills by about two thirds and raises net60 from about 2.3 to about 3.8 bps. ±7 and ±8 are worse than ±6.
- After the 1.4 bp/$ haircut, 200/400 ±6 would sit near +2.1 bp/$. This is on the same data that chose it, so it is a hypothesis, not a result.
- A 1-order cap is not proposed: the known gap that skew saturates after one fill and the exit quote clamps to fair ± 1 tick.

## Next experiment (one config, metric, success, stop)

- **Config:** quote 200, cap 400 (2 orders), fair ± 6 bps. In the live env, that is `MM_FIXED_HALF_SPREAD_BPS=6` and `MM_MAX_INVENTORY_ADAUSDT=400`. No code change.
- **Test:** forward and out of sample, on shadow data received after 2026-10-30T02:03:00Z. It re-prices around the logged fair, so it needs no orders and no shadow restart.
- **Metric:** PnL per $ on the calibrated leg (1000 ms, touch, Scalper Offer 15 min fifo).
- **Pass:**
  - The calibrated leg is ≥ +2.4 bp/$ (+1.0, plus the 1.4 by which this leg overstated the real run).
  - 1000 ms strict is ≥ 0.
  - At least 300 fills over at least 24 h.
  - At least one hour above 2× median vol in the window, so a calm-only stretch cannot pass. If none comes, extend up to 72 h.
- **Stop:** a fail at 72 h keeps ADA off. The next knob is then a volatility pause: stop adding when the trailing 15-minute realized vol exceeds a multiple of its trailing median, defined on past data only.
- **A live restart also needs:**
  - The cap-breach fix merged and demo-QA'd. Proposed fix: a quote found `closed` counts its uncounted contracts as filled until the next position read, and a private-feed reconnect blocks the adding side until fills are caught up.
  - The hourly check reading the venue position against the cap.
  - A calm market: 2 h without an abort trip, and ADA hourly vol back under 2× median. At 01:00Z it was 2.7×.
  - The owner's word.
- **Earliest restart:** 31 Oct about 02:30Z (08:00 IST), if all of the above hold.

## Addendum, 31 Oct 2026: forward test result (PASS)

Evaluated at 02:15Z on 31 Oct against `FORWARD_PREREG.md` (md5 9605df5c), with `shadow_fill_sim.py` at md5 a93c1658 (`forward_eval.py`, output in `forward_out.txt`).

**Data:**
- Window: 30 Oct 02:03:00Z to 31 Oct 02:09:59Z, 24.1 h.
- Source: ADA `MM_METRICS` and the Delta public trade tape from three shadow runs:
  - 20261025T174640Z (to 06:42Z)
  - 20261030T064228Z (to 10:55Z)
  - 20261030T105549Z
- Totals: 214,475 quote samples and 1,973 ADAUSD trades.
- Where two runs overlap, the earlier run's rows stop at the later run's first row.

**Config:** fair ± 6 bps, quote 200 (ref fair 0.19075), cap 400.

The live bot quoted ADA from 06:43Z, so its own fills are in the tape. The 1.4 bp haircut in gate 1 was set on data of that kind.

| Leg | Fills | Notional | PnL | Spread | Inventory | Fees | bp/$ |
|---|---|---|---|---|---|---|---|
| 1000 ms touch, Scalper 15 min fifo (calibrated) | 874 | $17,201 | +$7.99 | +$10.52 | −$0.44 | −$2.10 | **+4.65** |
| 1000 ms strict, list fee 2.12 | 589 | $14,108 | +$5.21 | +$8.32 | −$0.12 | −$2.99 | **+3.69** |
| 300 ms strict, list fee 2.12 | 604 | $14,530 | +$5.60 | +$8.17 | +$0.51 | −$3.08 | +3.85 |
| 300 ms touch, Scalper 15 min fifo | 887 | $17,599 | +$8.50 | +$10.28 | +$0.37 | −$2.15 | +4.83 |

**Gates:**
1. Calibrated leg ≥ +2.4 bp/$: **PASS** (+4.65).
2. 1000 ms strict ≥ 0: **PASS** (+3.69).
3. ≥ 300 fills over ≥ 24 h: **PASS** (874 fills, 24.1 h).
4. An hour above 2 × 61 bps: **PASS, by a hair.**
   - 13:00Z on 30 Oct had 122.3 bps against a bar of 122.0.
   - 15:00Z (119) and 14:00Z (116) fell just under.
   - The window's median hour was 72 bps.
   - Nothing like 29 Oct's 20:00Z (4.9×) or 00:00Z (6.2×) occurred, so this test says little about a dump.

**Verdict: PASS.** Keep running on these settings. The stop rule and the $10 UTC-day loss stop still apply.

**Live, same period** (runs 20261030T064303Z and 20261030T105618Z, from 06:43:03Z):
- 591 fills, $13,034 traded, +$6.44, which is **+4.94 bp/$** (from Delta fills via the live dashboard).
- Equity went from $330.83 to $337.26.
- Delta's wallet ledger agrees to the cent: realized +$8.10, fees −$1.56, funding −$0.09.
- The calibrated leg (+4.65) sat within 0.3 bp of the live figure, against the 1.4 bp it overstated the stopped run by. The windows differ, though: the simulation also covers 02:03–06:43Z, when the live bot was off.
