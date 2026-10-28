# Cancel-first requotes: in simulation they rescue AVAX ±6 bps but cost live ADA 3–4%; ADA keeps edits, AVAX waits for fresh data

**Date:** 2026-10-27 · **Venue:** Delta India mainnet public data (shadow test, no orders) · **Symbols:** AVAXUSD, ADAUSD · **Runs:** shadow `20261023T082101Z` (57.4 h) and `20261025T174640Z` (its first 39.8 h) · **Script:** `scripts/shadow_fill_sim.py` with `--cancel-first` (this PR). The six runs used the version at `cec0340` (md5 86004602…, a copy on the VM). `--since-utc`, added afterwards for rule C, changes nothing when unset.

Evidence in `2026-10-27-cancel-first-evidence/`: `PREREG.md` (md5 cf582ca6…, written 09:25:10Z, before the cancel-first model had been run on any data; the runs started 09:29:28Z), `cancel_first_runs.txt` (the six pre-registered runs, raw), `avax6_latency_sweep.txt` (the morning's AVAX ±6 runs, raw). The owner asked for the AVAX verdict, then for this test. Follows `2026-10-21-binance-imbalance-pull-replay.md` (mainnet call timings, finding 4).

## Question

AVAX was kept in the shadow until quoting it at ±6 bps around the anchored fair had 300 simulated fills. The pre-registered bar: net60 > 0 at 300 ms and at 1000 ms quote delay, and under the touch fill rule. Did it pass? If the delay is what kills it, can the bot cut the delay?

## 1. AVAX ±6 bps fails on delay

Classic engine, both runs pooled (fills summed, net60 weighted by fills), maker fee 2.12 bps:

| Quote delay | Fills | net60 (bps per $) |
|---|---|---|
| 300 ms | 275 | +2.63 |
| 500 ms | 334 | +2.80 |
| 700 ms | 373 | +1.43 |
| **1000 ms** | **417** | **−0.08** |
| 300 ms, touch rule | 300 | +2.37 |

- **Verdict: fail.** The 1000 ms leg is negative over 417 fills, so ±6 cannot pass as pre-registered, whatever the 300 ms strict count (275 of 300) does next. Both runs are negative at 1000 ms (−0.04 and −0.19), so this is not one bad run.
- Fills rise as the delay grows (275 → 417), and the added fills are the losers: at 1000 ms the price moves 2.5 bps against an AVAX fill within a minute, about what the spread pays after fees. ADA at the same settings stays at +2.8 to +3.8.
- **Method note.** The `fair +/- N` rows run at `--latency-ms` only; `--latencies` varies only the bot's own quotes. The 1000 ms leg therefore needs its own `--latency-ms 1000` run, which the AVAX check had not done before today.

## 2. Where our delay comes from

| Step | Time on mainnet | Can we cut it? |
|---|---|---|
| Wait for the next loop tick (timer, 400 ms) | 0–400 ms | Yes: wake on the Binance update (not tested here) |
| Network, Tokyo VM to Delta (signed GETs) | p50 22–49 ms | Hardly |
| Edit, `PUT /v2/orders` | p50 667 ms (p10 575, p90 753) | No: Delta's write path |
| Place, `POST /v2/orders` | p50 578 ms | No |
| Cancel one order | ~66 ms (3 samples); cancel-all p50 17 ms | — the fast path |

Source: the 21 Oct memo's table (live run `20261021T170240Z`). Today's live log agrees: at 07:57:21–23Z an edit took 664 ms, a place 528 ms, heartbeats 20–25 ms and a GET 15 ms. A requote today rests at the old price for about 0.7 s, plus the wait for the loop tick.

## 3. Cancel-first, as pre-registered

**Idea:** when the fair moves *against* a resting quote (the bid must go down, the ask up), cancel it and place the new price after the cancel answers. The stale quote is gone after about 70 ms instead of about 670 ms. Moves toward the market keep the edit. It does not show the new price any sooner (70 + 578 ≈ 650 ms against 667), and that side has no quote in between.

**Model** (`simulate_events`, used for both compared rows): the bot decides on each logged sample from the price it last asked for. A side with a call in flight takes no new decision until the call lands. An edit or cancel of an order that has already filled out does nothing. After a fill empties a side, the bot places again one loop later. Timings were fixed from the measurements above, not tuned: base = edit 700 / cancel 70 / re-place 600 ms; stress = 1000 / 150 / 900 ms.

**Results, pooled over both runs** (PnL60 = net60 in dollars, summed):

| Scenario | Quotes | Engine | Fills | net60 | PnL60 |
|---|---|---|---|---|---|
| base, strict | AVAX ±6 | edit | 378 | +1.59 | +$2.55 |
| | | **cancel-first** | **249** | **+3.35** | **+$3.72** |
| stress, strict | AVAX ±6 | edit | 436 | **−0.47** | −$0.87 |
| | | **cancel-first** | **270** | **+3.09** | **+$3.66** |
| base, touch | AVAX ±6 | edit | 411 | +1.43 | +$2.51 |
| | | **cancel-first** | **269** | **+3.08** | **+$3.70** |
| base, strict | ADA, live quotes | **edit** | 1,896 | +3.02 | **+$18.05** |
| | | cancel-first | 1,789 | +3.11 | +$17.58 |
| stress, strict | ADA, live quotes | **edit** | 1,930 | +2.78 | **+$16.60** |
| | | cancel-first | 1,693 | +2.97 | +$15.94 |

The "live quotes" rows replay the quotes the shadow logged for ADA, which runs the live bot's config.

### Pre-registered verdicts

| Rule | Condition | Result |
|---|---|---|
| **A** AVAX ±6 | 1. net60 > 0 in base, stress and touch | pass (+3.35 / +3.09 / +3.08) |
| | 2. ≥ 300 fills in each | **fail (249 / 270 / 269)** |
| | 3. stress: cancel-first net60 > edit's | pass (+3.09 > −0.47) |
| | **Verdict** | **not passed: too few fills** |
| **B** live ADA | PnL60 ≥ edit's in base and in stress | **fail** ($17.58 < $18.05; $15.94 < $16.60) |
| **C** | A or B again on data recorded after the rule was written | pending (see Next) |

## Findings, ranked by money at stake

1. **For live ADA, cancel-first loses money: keep edits.** It lifts net60 by 0.1–0.2 bps but trades 6% (base) to 12% (stress) fewer fills, so PnL60 is 2.6–4.0% lower. Most ADA fills are good, so emptying the side for 0.6 s throws away more good fills than bad. Quote uptime falls from 98–99% to 91–94%.
2. **For AVAX, the stale quote is the whole problem.** Cancel-first drops 34–38% of AVAX ±6 fills, and those are the losers. In the stress case net60 goes from −0.47 to +3.09 bps and PnL60 from −$0.87 to +$3.66. The same holds per run (old run +3.32 vs −0.63, new run +2.61 vs −0.09), at base and under the touch rule.
3. **The same effect on AVAX at the shadow's own quotes (exploratory, not pre-registered).** Stress: edit −0.56 bps, −$1.75 over 746 fills; cancel-first +1.13 bps, +$2.63 over 539. Base: +0.16 bps / $0.46 vs +1.59 bps / $3.66.
4. **AVAX is not yet shown, only indicated.** The fill count misses the bar, and these are the runs that produced the morning's failure. Rule C exists for exactly this.

## Method and its limits

- **Engine check:** with cancel-first off, the event engine's net60 matches the classic engine within 0.15 bps on ADA's live quotes (base 3.07 vs 3.13 and 2.93 vs 2.92; stress 2.67 vs 2.76 and 2.96 vs 2.81, over 700–1,200 fills each). On AVAX ±6's 100–300 fills per run it is within 0.6 bps (stress, new run: −0.09 vs +0.39). Capture and markout split differently between the engines: a fill is stamped with the book at the trade, not one delay earlier. Their sum, net60, barely moves.
- **Not modelled, in cancel-first's favour:** queue position lost by a cancel and re-place. The real loop also waits for both sides' calls, where the engine waits per side.
- **Not modelled, against it:** waking on the Binance update instead of the 400 ms timer would shorten both engines' delay.
- **Rate limits:** about 400 requotes an hour live (weight 5 each against 20,000 per 5 min) is about 1% of Delta's limit, so doubling the calls on adverse moves is safe.
- **Fees:** the sim charges 2.12 bps on every fill. Live ADA paid about 1.24 bps on average (the 06:22Z report), because Delta's Scalper Offer makes a closing leg within 15 minutes free on ADAUSD. Whether AVAXUSD has the offer, and its window, is [UNVERIFIED]. The verdicts ignore it.
- **Cancel timing:** single-cancel timing rests on 3 samples. The stress case (150 ms) still passes for AVAX.

## Next

- **ADA:** no change. Edits stay.
- **AVAX, rule C:** re-run rule A on data received after the rule was written, with the option this PR adds:
  ```
  for r in <shadow runs covering the window>; do
    python3 scripts/shadow_fill_sim.py --run-dir artifacts/shadow/$r --sweep 6 --since-utc 2026-10-27T09:30:00Z --latency-ms 700 --cancel-first 70:600
    python3 scripts/shadow_fill_sim.py --run-dir artifacts/shadow/$r --sweep 6 --since-utc 2026-10-27T09:30:00Z --latency-ms 1000 --cancel-first 150:900
    python3 scripts/shadow_fill_sim.py --run-dir artifacts/shadow/$r --sweep 6 --since-utc 2026-10-27T09:30:00Z --rule touch --latency-ms 700 --cancel-first 70:600
  done
  ```
  Rule A needs 300 cancel-first fills in each scenario. At 50–70 a day (strict) the earliest reading is about 31 Oct to 2 Nov, later than the 48 h minimum. Keep AVAX in the shadow until then.
- **If C passes:** a per-symbol knob, default off and on for AVAX only (the bot's OMS sends cancel then place on an adverse requote; cancel-all must cover the new path), then demo QA (one quote per side at most, the cap holds, post-only), the owner's merge, and AVAX on mainnet only through `docs/MAINNET_GATE.md` at small size.
- **If C fails:** drop cancel-first and AVAX ±6, and record it here.
- **Worth its own test later:** waking the loop on the Binance update. It cuts up to 400 ms for every symbol without emptying a side.
