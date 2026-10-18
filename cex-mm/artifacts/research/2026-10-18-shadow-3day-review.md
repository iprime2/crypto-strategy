# Quant memo: the 64 h shadow run on the anchored fair
**Date:** 2026-10-18 · **Venue:** Delta India mainnet public data, no orders (shadow test) · **Symbols:** ADAUSDT (decision symbol), BERAUSDT, DUSKUSDT, KITEUSDT · **Data:** run `20261015T105419Z`, build 0d70ca6 (anchored fair on, basis from the L1 book, OFI inside the anchored fair), 2026-10-15T10:54:32Z to 2026-10-18T02:51:43Z (63.95 h), 2,270,917 quote rows, 20,373 recorded trades (ADA 5,599, BERA 2,064, DUSK 12,252, KITE 458) · **Tools:** `scripts/shadow_fill_sim.py`, `scripts/fair_exposure.py`, `scripts/basis_replay.py` (PR D, unmerged), one-off scripts on a byte-exact local copy of the run.

## Question
Three days in, how is the anchored fair doing on the 13 Oct interim memo's targets, what does the first window over 24 h say about the pre-registered gate in `plans/live-basis.plan.md`, and is the recorded data fit to judge?

## Outcome
- **ADA is the only candidate, and it looks better than on 13 Oct.** The anchored quotes meet every interim target, the fair's lead over Delta is confirmed Binance-free on every day, and the simulator's net60 is positive on every day.
- **The gate replay says PR C's two changes are both necessary.** On ADA with the depth basis and OFI out, G1, G2, G3 and G4@60 pass over 64 h. With the book basis as coded, G1, G3 and G4 fail. With the depth basis but OFI kept, G3 fails.
- **The gate still reads INCOMPLETE on ADA**, because the plan's oracle rule rules out G4@5, G5@30 and G5@60 on 64 h just as it did on 0.4 h and 2.65 h. The plan says the gate table needs a decision if a 24 h run repeats that. It has.
- **New risk: a 37-minute Delta-side freeze on 17 Oct that the bot cannot detect.**
- **The simulator still cannot see pick-off.** Its +2.41 bps is the same kind of number that read +4.7 before the 13 Oct live run lost 3.6 bps per fill.

## PnL attribution (simulator, maker only; strict rule, 300 ms, $50 quotes, cap 3 quotes)

| Symbol | Fills | Capture | Markout 60 s | Fee | net60 | Inventory $ / spread $ / fee $ | Verdict |
|---|---|---|---|---|---|---|---|
| ADA | 2,889 | +4.79 | −0.26 | −2.12 | **+2.41** | +12.72 / +28.29 / −12.54 | PASS |
| BERA | 575 | +5.48 | +1.30 | −2.12 | +4.66 | −2.19 / +8.69 / −3.35 | PASS, latency-fragile |
| DUSK | 2,096 | +2.37 | −1.15 | −2.12 | **−0.90** | −61.24 / +18.33 / −16.29 | STOP |
| KITE | 162 | +4.33 | −0.57 | −2.12 | +1.64 | −1.02 / +2.39 / −1.17 | CONTINUE (under 300 fills) |

- ADA net60 range across 0 / 300 / 1000 ms and the strict and touch rules: +2.13 to +2.61. Hour-block bootstrap 95% CI at 300 ms strict: [+1.69, +3.27].
- ADA per UTC day (strict, 300 ms): 15 Oct +3.35 (813 fills), 16 Oct **+1.47** (1,206), 17 Oct +2.82 (804). Capture is flat (4.70 to 4.96); the day-to-day swing is markout (+0.52, −1.11, +0.19). The 24 h target of +2 bps is missed on 16 Oct.
- The ADA inventory term (+$12.72) is directional luck under the cap (short 59% of the time while ADA fell), not edge. Only spread net of fee (+$5.9 a day at $50 quotes) is repeatable in principle.
- Width sweep (ADA): net60 per fill rises with width, 3 bps +0.63 to 8 bps +4.74, but dollars per day peak at 5 to 6 bps and halve at 8. Keep 5.
- Anchored vs old fair on simulated PnL (ADA, paired hour blocks): +0.20 bps at 300 ms, CI [−0.37, +0.82]. With 17 times the fills of the interim memo, the simulator still cannot separate the two fairs.

## What the code actually does (vs config)
- **The stale-book guard watches arrival, not change.** `book_age_ms` is the age of the last frame received. During the freeze Delta kept re-sending unchanged frames, so it stayed at 0 and `BookWatch` (`MM_BOOK_STALE_MS` 2000) never fired.
- **The basis EMA learns a frozen book.** During the freeze the ADA basis EMA walked from −7 to −41 bps. After Delta came back it took about ten minutes to recover (half-life 120 s, ±5 bps clamp per sample), with the anchored fair 12 to 18 bps off Delta's mid and ADA one-sided 93% of 20:15Z to 20:20Z.
- **The old fair hides the freeze.** It is the frozen book, so its gap read zero throughout.
- **Every one-sided row is the fair-jump defence** (|fair / Delta mid − 1| ≥ 12 bps), as expected in a dry-run without inventory.
- **The calendar pause** (08:28 to 08:35 and 14:28 to 14:35 New York time, 16 min a day) logs as "risk kill — cancel all ... reject_count=0". It is not a fault.

## Findings, ranked by money at stake

1. **A frozen Delta feed is invisible to the bot.**
   - 17 Oct 19:35Z to 20:10Z: zero mid changes and zero trades on all four Delta books, while Binance moved 2 to 77 times per 5 minutes per symbol (ADA +13.5 bps, DUSK +356 bps over the window).
   - Three independent channels agree: the bot's `ob_l1` socket, the recorder's `ob_l2` and trades socket, and Delta's REST ticker, whose mark price stopped updating 19:35Z to 20:05Z (normally 50 changes per 5 min) while every poll still succeeded.
   - [UNVERIFIED] whether Delta's matching engine accepted or filled orders during the window.
   - Live, either fair would have rested quotes on a dead book. A frozen-feed detector is a precondition for any live run and is not in the plan's gate.

2. **PR C's depth basis and OFI removal are each needed (gate replay, ADA, 64 h, live mode, q = 200).**

   | Variant | G1 anchor on | G2 p90 / pivot | G3 p99 | G4 slope 60 s new / old (CI of diff) | Verdict |
   |---|---|---|---|---|---|
   | Depth basis, OFI out (PR C) | 99.8% PASS | 0.78 bps / 0.04% PASS | **0.000 bps PASS** | 0.448 / 0.172 ([+0.17, +0.39]) PASS at 60 s | INCOMPLETE |
   | Depth basis, OFI in (as coded) | 99.8% PASS | PASS | **4.82 bps FAIL** | 0.351 / 0.172 | FAIL (G3) |
   | Book basis (as coded) | **43.7% FAIL** | PASS | **7.18 bps FAIL** | 0.178 / 0.172, CI [−0.08, +0.09] FAIL | FAIL (G1, G3, G4) |
   | Old fair (weight 0) | 0% | PASS | n/a | 0.080 / 0.172 FAIL | FAIL (G1, G4) |

   - Shadow-mode agreement with the logged basis: within 1e-3 bps on 100.00% of 568,336 rows (max deviation 0.00033 bps), with the EMA re-read after each of the 13 log gaps.
   - The PR C variant is INCOMPLETE only because the oracle rule rules out G4@5, G5@30 and G5@60. Both oracles fail those components on 64 h: the +5 s oracle is +3.6 pp more exposed than the old fair at +30 s and +4.4 pp at +60 s; the +60 s oracle has a 5 s slope of 0.088 against the old fair's 0.160.

3. **BERA should not be anchored on the depth basis at X = 10,000.**
   - Gate replay, live, depth: G2 FAIL (p90 depth vs clean-L1 basis 8.16 bps, pivot share 5.8%), G3 FAIL (p99 2.25 bps), G4 FAIL (60 s slope 0.214 vs old 0.259).
   - The shadow-mode replay on the clean book also fails G2 and G4.
   - The PR C profile anchors BERA. Weight 0 for BERA, like DUSK and KITE, would leave ADA as the only anchored symbol.

4. **The anchored fair's lead over Delta holds Binance-free on every ADA day.**
   - Regression of Delta's future mid move on (fair − Delta mid), 2 s grid, 5-min block bootstrap, the freeze window excluded: 60 s slope 0.51 anchored vs 0.17 old, difference CI [+0.27, +0.41]. Per day the lower CI bound is +0.13 to +0.26. R² stays about 1%.
   - Including the freeze, 17 Oct alone shows no difference ([−0.13, +0.16]).
   - KITE is reversed (60 s difference −0.12, CI [−0.22, −0.04]) and DUSK shows nothing, as on 13 Oct.

5. **Quote exposure: the anchored fair meets every interim target; the old fair fails exposure on every symbol.**

   | ADA | p90 gap to Binance-implied | Exposed bid / ask | One-sided |
   |---|---|---|---|
   | Anchored, 64 h | 2.09 bps | 0.53% / 0.41% | 0.34% |
   | Anchored, freeze excluded | 2.02 bps | 0.02% / 0.02% | 0.06% |
   | Old fair, 64 h | 4.44 bps | 8.10% / 9.23% | n/a |

   - The anchored figures against the Binance-implied price are partly circular (two smoothers of one series). The Binance-free check: against Delta's own mid 60 s later, anchored ADA quotes are 3.05 pp less exposed than the old fair's (CI [−3.47, −2.60]). The interim memo's 2.65 h read had them 2.4 pp more exposed at 1 s; over 64 h they are 1.6 pp less exposed at 1 s.
   - DUSK is the only target miss: 5.66% one-sided on the freeze day.

6. **DUSK loses money in the simulator and the anchor cannot follow it.**
   - net60 −0.90 at 300 ms, −0.98 under the touch rule, STOP at every width from 3 to 8 bps. The loss is inventory: −$61.24 of −$59.20 total, at the cap 30.5% of the time.
   - Delta's touch spread (5.94 bps) is narrower than our 10.9 bps quote width, so our quotes are inside it only 45% of the time.
   - DUSK's raw L1 basis moves 25 to 41 bps within 5 minutes; the clamped EMA moves 1.9 to 3.4.

## Run health
- Loop coverage 98.7% of 400 ms slots (ADA). All gaps over 60 s are the calendar pauses. 806 five-second L3 pauses (DUSK 676, BERA 78, KITE 39, ADA 13); 31 stale-book cancels, each followed by "book fresh again" within a second.
- Binance spot older than 5 s (anchor off, old fair quoted): ADA 2.6%, DUSK 4.3%, BERA 15.8%, KITE 18.7% of rows.
- Recorder: 16 websocket reconnects, all recovered. Trades re-counted within 0.3% of the dashboard.
- Disk: the current run grows about 1.15 GB a day; the VM had 12 GB free on 18 Oct. Housekeeping never deletes the current run, so this run alone fills the disk in about ten days. A restart on PR C starts a new run directory.
- The fill simulator needs about 0.7 GB RAM on this run. The VM (2 vCPU, 1.8 GB RAM) cannot run it beside the shadow without swapping; run reports on a copy.

## Next experiment
- **Knob:** none on the strategy. Merge PR C with ADA as the only anchored symbol, restart the shadow, and add a frozen-feed detector before any live run.
- **Metric:** the PR D gate on ADA over the first 24 h on the PR C build, plus the 1e-3 bps agreement check on PR C's logged `basis_t`.
- **Success:** G1, G2, G3 and G4@60 pass again on the PR C build's own log, and the owner has decided how the oracle-ruled components are judged.
- **Stop:** any of G1 to G3 fails on the PR C build, or a second freeze shows the detector does not fire.
