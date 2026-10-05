# Quant memo: DISM live gate, six coins over ~67 hours
**Date:** 2026-10-05 · **Venue:** Delta India mainnet public data (no orders) · **Strategy:** Delta Inside-Spread Maker (DISM)
**Data:** five runs with ADA, KITE, BERA, MUBARAK, DUSK, RED: `20261001T174754Z` (REST book, 6.3 h), `20261002T000422Z` (2.8 h), `20261002T025147Z` (12.6 h), `20261003T031308Z` (~13 h), `20261004T021209Z` (32.1 h); the last four use the `ob_l1` websocket book. Strict fills (trade must print through our price), 300 ms latency, $50 quotes, inventory cap 3 quotes, maker fee 2.12 bps. `scripts/shadow_fill_sim.py --sweep 3,4,5,6,8 --latencies 0,300,1000`.

## Question
Which symbols and which quote rule pass the live gate (net60 ≥ +0.5 bps over ≥ 300 fills, positive across runs)?

## Results (net60 = spread captured + 60 s markout − fee, bps per fill, fill-weighted over all runs)
| Symbol | Rule | Fills | net60 | net300 | Per-run net60 | Verdict |
|---|---|---|---|---|---|---|
| ADA | fair ±5 bps | 4,117 | **+1.90** | +0.95 | +3.0, +2.6, +0.8, +2.9, +1.9 | **Pass** |
| ADA | fair ±4 bps | 5,612 | +1.06 | +0.32 | +1.9, +2.6, −0.4, +2.1, +1.1 | Pass, one negative run |
| ADA | bot's own quotes | 4,031 | +0.32 | −0.57 | +0.3, −0.1, −0.2, +1.5, +0.3 | Break-even |
| KITE | fair ±5 bps | 464 | +0.91 | +2.04 | +1.7, +1.3, −1.6, −0.5, +2.8 | Inconclusive (mixed, PnL −$1.27) |
| BERA | fair ±5 bps | 166 | +5.05 | +2.86 | +6.1, +6.7, +7.5, +3.9, −14.7 | Inconclusive (few fills, last run bad) |
| DUSK | fair ±5 bps | 28 | −0.21 | −1.39 | — | Inconclusive (no fills) |
| MUBARAK | fair ±5 bps | 6,794 | −1.06 | −1.58 | mostly negative | Fail (−$27.57) |
| RED | fair ±5 bps | 33 | −3.46 | +3.38 | very noisy | Fail |

- ADA ±5 bps is positive in every run, including the 32 h run (2,865 fills, +1.95, simulated PnL +$5.40 = spread +$37.95, fees −$16.20, inventory −$16.34).
- The bot's own quotes (AS path, ~4 bps half-spread plus skew) stay near zero, as in the 30 Sep memo. The edge is the fixed ±5 bps rule.
- About 40% of the spread goes to fees and 40% to inventory drift at $50 quotes with no skew; net300 is half of net60.
- Home-network outages (19 on 4–5 Oct, 54 min total) are excluded by the stale-book guard; quoting time on both sides was ~80% in the 32 h run.

## Decision
Live pilot on **ADA only**, quote rule **fair ±5 bps** (`MM_FIXED_HALF_SPREAD_BPS=5`, profile `config/dism.env`), $50 quotes, $150 inventory cap. KITE and BERA stay in the shadow test; MUBARAK and RED are dropped at the next restart.

## Next
1. Restart the shadow test on the DISM profile so the bot-quotes row is the live rule itself (dry-run check: 140/140 quotes equal the simulator's ±5 rule).
2. Live stop rule: net60 < 0 after 300 live fills → stop, same as the shadow gate.
3. Inventory drift is the largest cost after fees; measure it live before raising size.
