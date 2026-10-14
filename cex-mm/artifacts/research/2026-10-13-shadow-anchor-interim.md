# Quant memo: the Binance-anchored fair in the shadow test, interim read
**Date:** 2026-10-13 · **Venue:** Delta India mainnet public data, no orders (shadow test) · **Symbols:** ADAUSDT (main), BERAUSDT, KITEUSDT, DUSKUSDT · **Data:** anchored run `20261013T073943Z` (W = 1, basis EMA half-life 120 s; 07:41–10:19Z, 2.65 h, 796 ADA trades); old-fair runs `20261012T075609Z` (9.5 h) and `20261012T173401Z` (11.3 h, live window 03:14–05:52Z excluded); the 172 real maker fills of live run `20261013T031435Z` · **Tools:** `scripts/fair_exposure.py`, `scripts/shadow_fill_sim.py`, one-off scripts on local copies of the logs. Every headline was re-derived independently by an adversarial check (four skeptics and a critic), which corrected several first-pass claims (listed at the end).

## Question
Does anchoring the fair to Binance (fair = Binance mid × (1 + basis EMA)) fix the stale quotes that lost money in the first live run, judged on the 2026-10-13 pick-off memo's targets? This is a 2.65 h read, 11% of the planned 24 h.

## Outcome
- **In the shadow, on ADA, the anchor does what it was built to do.**
  - Its deviation from Delta's mid carries real information about where Delta goes next.
  - The simulator cannot tell the two fairs apart on PnL, and cannot see pick-off at all.
- **Replayed against the live run's real fills, the anchor would have stood back from most of the fills that lost money.**
- **As coded, the anchor would be worse than the old fair in a live run.**
  - With our own quotes at the Delta touch, the basis almost never updates, and the samples it does get are biased.
  - A live start with the anchor is already refused (`scripts/live.sh`, and the bot without `MM_FAIR_ANCHOR_LIVE=1`), and must stay so until the basis source is fixed.

## Findings, ranked by money at stake

1. **The anchor targets the fills that lost money live.**
   - Method: the anchored resting quotes (fair ± 5 bps, 3 bps requote rule) were rebuilt over the live window from the Binance mid the shadow logged beside the live bot. The basis was frozen from the clean hour before the start (02:14–03:14Z, −8.51 bps), with a sensitivity range of −9.5 to −5.0 bps (the fills themselves imply −4.95).
   - Result: 55–63% of the 172 real fills, and 66–74% of the 47 whole-order fills, came at a price the anchored quote would have stood at least 2 bps clear of.
   - Those fills had a 60 s markout against Binance of −4.5 to −5.8 bps. The rest had +1.0 to +2.3.
   - The markout is the future Binance move, so it is not set by the selection. The capture split is circular (selected and scored on the same Binance price) and is not used here.
   - [UNVERIFIED] whether those takers would have traded at the anchored price anyway. n = 172 over 2.6 h, with no block bootstrap.

2. **As coded, the anchor would make live quoting worse.**
   - Replay of the current gate (the basis updates only while neither of our hypothetical quotes is the touch; it re-warms after 300 s; the bot falls back to the old fair otherwise):
     - ADA's Delta spread (median 12.6 bps) is wider than our 10 bps quote width 70–91% of the time, so our quotes would be the touch about 95% of the time.
     - The basis would update on 7.6% / 6.9% / 2.8% of samples (new run / run 1 / run 2). The anchor would be on 74% / 72% / 39% of the time.
     - The samples it does get come from moments when Delta's spread is tight, and sit about ±2 bps off the true basis, with the sign changing by run.
   - Against Delta's mid 1 s and 5 s later, exposure is +15.7 and +11.4 percentage points worse than the old fair on the new run (block-bootstrap 95% CIs [+10.0, +21.7] and [+6.5, +16.4]).
   - Caveat: the replay assumes the rest of the book is unchanged by our presence, and the fallback old fair would itself read our quotes live.

3. **Binance-free evidence: real but small.**
   - Regression of Delta's future mid move on (fair − Delta mid), on a 2 s grid, with block-bootstrap CIs.
   - Over 20 h of older ADA data, with the anchor rebuilt offline (correlation 1.000 with the logged anchor on the new run):

     | Horizon | Slope, anchored fair | Slope, old fair |
     |---|---|---|
     | 5 s | 0.42 | 0.17 |
     | 60 s | 0.63 | 0.30 (difference CI [0.19, 0.46]) |

   - The new run agrees: 0.36 vs 0.14 at 5 s, and about 0.6–0.75 vs 0.29 at 60 s.
   - R² is only 1–3% at 60 s, and most of the convergence happens within 2–10 s.
   - About 70–80% of the gap closes by Delta moving and 20–30% by Binance moving the other way, so the anchored fair overshoots where the two prices meet.
   - On BERA the pattern repeats (0.95 vs 0.32 at 60 s). On KITE it is reversed (−0.32 vs +0.49), and on DUSK it is absent.

4. **The headline exposure numbers are circular.**
   - Against the memo's reference (Binance × centred 20-min median basis), resting-quote exposure on ADA fell from 2.5% bid / 8.2% ask (old fair, rounded and clamped) to 0.0 / 0.1%. The p90 gap fell from 4.21 to 1.31 bps.
   - The same cut appears on the 20 h of older data with the anchor rebuilt (−10.8 and −14.2 percentage points), and a trailing-only reference gives the same.
   - But the reference is Binance times a smoother of the same basis, so near-zero exposure follows from the definition.
   - Against Delta's own future mid, the shadow-anchored quotes are +2.4 pp more exposed at 1 s, +0.2 at 5 s and −1.9 at 60 s. This yardstick favours a Delta-based fair at short horizons, because Delta lags, so neither reference settles pick-off. Only live fills can (finding 1 is the closest proxy).

5. **The simulator cannot separate the fairs.**
   - Same ADA tape, 300 ms, strict rule, all fills with a 60 s mark: anchored net60 +3.35 bps (n = 173) vs old fair +3.49 (n = 155).
   - Paired block-bootstrap CI on the difference: about [−1.9, +1.6]. The 60 s marked PnL is $1.12 vs $1.13.
   - On the 20 h older tape with the anchor rebuilt: +3.14 (2,024 fills) vs +3.19 (1,745), difference CI [−1.06, +0.88].
   - The simulator only fills on recorded prints, so it never charges for pick-off. Its A/B leans toward the old fair, whose resting quotes sat through the Binance-implied price about 7× as often (2.33% vs 0.33% of side-time).

6. **The Binance reference moves in 4.2 bps steps.**
   - All 23,977 Binance ADA spot mids in the new run sit exactly on a half-tick, and every change is one tick (~4.2 bps; KITE 7.9, BERA 2.3).
   - So the anchored fair carries up to ±2.1 bps of quantization.
   - `mm-binance` drops the bookTicker quantities (`B`, `A`), which would allow a queue-weighted price inside the tick.

7. **Per symbol.**
   - **ADA:** clean. The recorder never dropped, the longest trade gap was 4.4 min, the Binance message age was under 5 s 99.6% of the time, the bot was anchored 99.6%, and one-sided 0.03%.
   - **BERA:** the gain is real but small, and there were only 17 trades in 2.65 h.
   - **KITE:** the anchor predicts worse than the old fair. Binance spot is silent for more than 5 s 22% of the time, so the anchor is off then.
   - **DUSK:**
     - One-sided 19.2% of the time (13.4% after 08:00).
     - The side-dropping rule compares the anchored fair with the current Delta mid (12 bps). DUSK's basis swings 20–40 bps within 5 minutes, and a 120 s EMA cannot follow it (removing the ±5 bps clamp only takes this to 14.8%).
     - KITE's simulated net60 is negative in every run, but no CI excludes zero. DUSK's sign depends on the fill rule.

## Against the 24 h targets (provisional, 2.65 h)

| Target | Status |
|---|---|
| p90 gap < 3 bps | Met (1.31), but circular. Fails in the live-mode replay (4.2–4.6). |
| Exposure < 3% each side | Met (0.0 / 0.1%), but circular. Fails in the live-mode replay (3.4 / 10.3% and up). |
| One-sided < 5% | Met for ADA, BERA and KITE. Failed for DUSK. |
| bnet60 ≥ +2 bps over ≥ 300 fills | Level passes (+3.35), but n = 173. bnet is circular, and the old fair scores the same. |
| Fills a day within 30% of the old shadow | Borderline: 1,505 vs 2,063 and 1,173. Half of the new tape is one burst of 1-contract prints. |

## Next experiment and work
1. **Leave the shadow running to 24 h** (about 07:40Z on 14 Oct) for the ≥ 300-fill numbers and more market regimes. It cannot answer the live question.
2. **A basis our own quotes cannot move** (one change, live-mode replay as the test). Candidates:
   - (a) The Delta book with our own orders removed, using L2 depth.
   - (b) Delta's mark or index price.
   - (c) A slow basis from a clean window, refreshed only while we are not at the touch. Finding 1 suggests even a basis frozen for 2.6 h works for ADA.
   - Record (a) and (b) first: the recorder now logs only trades and heartbeats.
   - **Success:** in a live-mode replay over ≥ 24 h, the anchor is on ≥ 95% of the time, the p90 gap is < 3 bps, and exposure against Delta's mid 1 s and 5 s later is no worse than the old fair's.
   - **Stop:** any of those missed.
3. **The Binance microprice from the bookTicker quantities.** Log `B` / `A` first, then test against the plain mid.
4. **Per-symbol anchor weight 0 for DUSK and KITE** at the next shadow restart.
5. **The real bot stays off.** Live quoting with the anchor waits for item 2.

## Corrections made by the adversarial check
- **The old run had no recorder outage.** Its "160-minute gap" was the excluded live window, and its other gaps were quiet Indian-night trading with the recorder alive (~56 s lost in total). Its lower fill rate reflects a quieter market.
- **"13% more fills with the anchor" does not hold.** By notional it is +3.5%, and it reverses when the inventory cap changes.
- **The first DUSK comparison quoted the old fair on both sides at all times.** With the old fair's real side-dropping rule, DUSK reads +1.9 bps (CI includes 0), not −5.1.
- **"Binance fresh 100%" used a 15-minute frozen-feed test.** The 5 s message age is the meaningful figure.
