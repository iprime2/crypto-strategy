# Live ADA, stages 1 and 2: the first anchored run pays, pick-offs come from the Binance tick, and the order path is the latency

**Date:** 2026-10-21 · **Venue:** Delta India mainnet, real orders · **Symbol:** ADAUSD · **Runs:** `20261020T110544Z` (stage 1, 100 contracts a quote, cap 300, 11:05–15:57Z) and `20261020T155754Z` (stage 2, 200 / 600, from 15:58Z, still running at 02:38Z) · **Build:** d9d4aa7 then 44664e8 (#52 reconcile fix, #53 size stage 2) · **Account:** $292.16 at the 20 Oct start.

Scripts used (read-only, on the VM, copies in the session scratchpad): `scripts/live.sh report`, `scripts/shadow_fill_sim.py`, and ad-hoc `verdict.py`, `stale.py`, `guard.py`, `steps.py`, `tickrate.py`, `editwin.py`, `capstats.py`. Markouts are against the Binance mid; "net60" = capture at the fill + 60 s markout − fee, notional-weighted, in bps per $ traded unless stated.

## Headline

| | Stage 1 (4.87 h) | Stage 2 (10.67 h, to 02:38Z) |
|---|---|---|
| Fills | 332 (1,672 / day) | 262 (589 / day) |
| $ traded / day | 20,243 | 11,903 |
| PnL (spread / inventory / fees) | **+$0.50** (+1.43 / −0.45 / −0.48) | **+$3.08** (+2.33 / +1.43 / −0.68) |
| PnL per $ traded | +1.25 bps | +5.81 bps |
| net60 weighted / unweighted ± 95% | +0.74 / +1.21 ± 2.36 | +1.98 / +2.87 ± 1.09 |
| Fee paid (Scalper Offer joined 11:30Z) | 1.20 bps | 1.28 bps |
| Stop rule | OK at 300 | CONTINUE (262 / 300) |
| Aborts (anchor on, basis vs shadow, OFI, pegged) | none | none |
| Inventory range vs cap | −379 / +300 vs 300 (old build) | −600 / +600 vs 600, never beyond |

Equity: $292.16 → $292.49 at the stage 1 stop → $294.61 at 02:37Z (position −395 at the time). The size ladder's stage 2 gate (≥ +1 bp per $ after 300 fills, no abort) was met by stage 1 at 15:52Z and #53 was merged on it.

The 13 Oct pick-off (whole-order fills with a −2.77 bps 60 s markout) is gone under the anchored fair: whole-quote fills had +0.22 (stage 1) and −1.90 (stage 2) 60 s markouts and net60 +2.24 / +1.19.

## Findings, ranked by money at stake

1. **The remaining losses come in the moment after a Binance tick, and the tick is 4.5 bps.**
   - Binance spot ADAUSDT has a $0.0001 tick: at $0.22 that is 4.5 bps. In stage 1 the Binance mid changed 3,394 times in 4.9 h (median every 2.4 s), every step 4.44–4.62 bps. The anchored fair follows: 3,277 of its steps were 3–5 bps. Delta's own mid moves in 0.5–2 bps steps (p50 2.26).
   - With the half-spread at 5 bps, one Binance tick toward a quote leaves that quote 0.5 bps from the new fair until the bot moves it.
   - Stage 1 fills within 2 s of a ≥ 3 bps Binance move toward us: 107 (36% of volume), capture −0.83, 60 s markout −3.0, **net60 −3.76**. The other 226 fills: **net60 +3.3**. Removing the first group would have taken the run from +0.76 to about +3.3 bps per $ traded.
   - Those fills came within one loop tick of the Binance move: the quote was already exposed at the last 400 ms sample before the fill in 68% of them and one sample earlier in only 1%. The quote's own age at the fill was 0.8 s (median): the bot had just moved it, and the move continued.
   - The 2 s pre-move is bimodal (exactly 0, or ≥ 3 bps): that is the tick size, not a feed fault.
   - Stage 2 overnight, a calm market (hourly ranges 40–150 bps against 300–340 in the 14–15Z rally and reversal): 48 such fills of 262 (20% of volume), net60 −5.4 on the 29 with capture under 2 bps. Pick-offs per Binance tick toward a quoted side: 3.7% in stage 1 (5.0% and 4.3% in the 14Z and 15Z hours, 0–2% in calm hours), 1.8% in stage 2.

2. **The requote tolerance is not the lever.** 1 bps instead of 3 bps on the two clean shadow days (18 and 19 Oct, simulator, fair ± 5, $45 quotes, cap 3): net60 2.14 vs 2.16 and 3.00 vs 3.00. The 13 Oct memo found the same for the old fair. A 4.5 bps tick already exceeds the 3 bps tolerance, so the bot requotes on every tick; the delay is elsewhere (finding 4).

3. **A "pull the side after a Binance jump" guard is the wrong tool.** Counterfactual on stage 1's fills (threshold 2–4 bps over 1–3 s, side off 3–20 s): it would hold a side off 39–89% of the time, because Binance ticks every few seconds. The per-$ figure rises (avoided fills net −$0.36 of the +$0.30) but at the cost of most of the quoting time.

4. **The order path is the latency, and it is the venue's, serialised by us.** From the live logs (an `MM_METRICS` row is written before the tick's order calls, an `MM_ORDER` line after each returns):

   | Call | Stage 1 (n) | Stage 2 first hour (n) |
   |---|---|---|
   | Edit (PUT /v2/orders), first of the tick | p10 568 / p50 577 / p90 668 / p99 729 ms (3,420) | 569 / 621 / 708 / 720 (662) |
   | Edit, second of the tick | 570 / 621 / 667 / 686 (2,208) | 567 / 616 / 664 / 698 (644) |
   | Place (POST), first | 531 / 585 / 676 / 1,683 (136) | 529 / 614 / 624 / 664 (13) |
   | Signed GETs (positions, order state, balances, open orders), timed separately | 30–80 ms | |

   - The bot awaits the bid edit, then the ask edit (`runner.rs` 1604–1640), so a two-sided requote freezes the loop for about 1.2 s. 2,208 of stage 1's 3,420 requote ticks were edit+edit. Over the whole of stage 1, 5.3% of all tick gaps were 1.0–1.5 s (7.4% in stage 2's first hour); a sub-100 ms catch-up tick followed 1,645 of 2,630 long gaps (tokio's default `MissedTickBehavior::Burst`).
   - The old quote stays hittable while the edit is in flight: of 235 stage 1 fills that landed in a tick which edited or placed the hit side, 209 hit the old price before the edit returned, most within 60 ms of the row. The taker reaches the quote at about the moment the bot first sees the tick.
   - The loop is timer-driven only (400 ms; nothing wakes it on a Binance or Delta update, fills wait for the next tick), the REST client has no timeout, and the venue reconcile GET runs inside the tick every 5 s (fast, 30 ms, not the stall).
   - A 200 ms dry-run next to the shadow (no REST calls) had loop gaps of a flat 200 / 200 / 201 ms over 10 h: the stalls are REST waits, not compute.
   - What the Delta edit latency is made of is not measurable from here; the REST host resolves to a CloudFront distribution and the GETs are fast, so it is the order path itself. [UNVERIFIED: whether a cancel is as fast as a GET; the cancel-all ticks could not be timed from the log.]

5. **Widening the half-spread is a weaker case than it looked before the overnight data.** Simulator on the clean days ($45 quotes, cap 3, Scalper Offer, whole-day dollars):

   | Half-spread | 18 Oct fills/day, $ | 19 Oct fills/day, $ |
   |---|---|---|
   | 5 bps | 1,074, $6.7 | 920, $6.6 |
   | 6 bps | 862, $10.3 | 670, $4.7 |
   | 7 bps | 407, $4.9 | 316, $4.5 |

   The simulator never charges for pick-off, which favours 6 bps; the plan's own rule is not to widen to compensate (`plans/live-basis.plan.md`), and stage 2 made +5.8 bps per $ at 5 bps in a calm market. Hold at 5 bps; revisit with fast-market evidence under the latency fix.

6. **Inventory lean: lower priority at the 600 cap.** Stage 1 (cap 300) quoted one side only 25.9% of the time and sat at ≥ half the cap 66% of the time; stage 2's first hour, 1.4% and 52%. The design for a lean in fixed mode (centre shift of `MM_FIXED_LEAN_BPS × inventory / cap`, default 0, replayed in the simulator against its own inventory) is recorded in the session's workflow output and can be a later PR; STRATEGY.md §6.1 would need a line for it.

## Should the bot move to C++ / Cap'n Proto / sockets? No.

The bot is one Rust process; the shadow test is the same binary in dry-run plus Python offline. Per-tick compute is under 1 ms (VM load 0.0). Cap'n Proto is a serialisation format for IPC and there is no IPC: every hand-off is an in-process tokio channel, and the only wire formats are the venues' JSON over TLS, which they dictate. The budget that matters is 0–400 ms of timer sampling, about 580 ms per order edit or place at Delta, those awaited one after the other, and a REST client with no timeout: all in the existing Rust bot, none touched by a language change. A rewrite would re-derive about 10,700 lines and 190 tests of venue quirks (channel names, order state trailing the fills feed, the heartbeat schema) for no gain. Three independent reviews reached the same verdict.

## Also found overnight (stage 2, 15:58–02:38Z)

- Ten "anchor off; quotes pulled" events, all `binance_stale`, about 10 s each (20:23, 21:29–21:46 ×5, 23:57, 00:07, 00:54, 02:09). The Binance bookTicker only sends on change; a quiet book can look like silence. Harmless (quotes pulled, no risk) but it costs quoting time at night. [UNVERIFIED whether these were true feed gaps or unchanged books.]
- The private fills feed reconnected three times (18:01 after 45 s of silence; 21:03 and 21:59 on connection resets). The bot logged 262 fill events; Delta's fills endpoint has 262 in the window. No fill was lost.
- The venue reconcile adopted a position twice within 5 s at 02:18:53–59 (−309 → −352 → −309): a transient venue reading, corrected by the next read. The #52 guard worked as designed; the cap was never exceeded.
- Two frozen-book cancels (21:29, 21:42: top unchanged 120 s while Binance moved 0 bps), each fresh again 400 ms later; one ob_l2 reconnect; one post-only reject.
- The 18:28Z calendar pause fired ("risk kill — cancel all", 1,200 lines over its window).

## Recommended next steps (in order)

1. **Keep stage 2 running** under the stop rule and the $15 daily stop; the 300-fill mark is imminent.
2. **Quote-path latency PR** (Rust, no strategy change): log elapsed ms per REST call and `tick_ms` / `rest_calls` in `MM_METRICS`; a 1.5 s request timeout on the Delta client; `MissedTickBehavior::Skip`; run the bid and ask order chains concurrently (or Delta's batch edit); move the fill-settle and reconcile GETs off the loop. Expected: a two-sided requote freezes the loop ~0.6 s instead of 1.2 s and the 1.0–1.5 s stalls disappear. Verify on a demo QA run, then restart live.
3. **Demo probe of cancel vs edit vs place latency** (one far-from-market post-only order on the demo account). If a cancel is ~50 ms, add "cancel the exposed side first, re-place after" on a Binance tick against it, and an event-driven wake on the Binance tick, since only then can the bot beat the taker.
4. **Log the Binance bid/ask sizes** in `MM_METRICS` (they are in the bookTicker already) so a microprice anchor, which anticipates the 4.5 bps tick, can be evaluated on recorded data before any quoting change.
5. Hold the half-spread at 5 bps and the lean for later, as above.
