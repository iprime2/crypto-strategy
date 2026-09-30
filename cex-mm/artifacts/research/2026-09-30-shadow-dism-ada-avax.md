# Quant memo: DISM shadow test after ~16 hours (ADA, AVAX, NEAR)
**Date:** 2026-09-30 · **Venue:** Delta India mainnet public data (no orders) · **Strategy:** Delta Inside-Spread Maker (DISM)
**Data:** run 1 `20260929T115546Z` (ADA+NEAR, 4.5 h, 29 Sep 16:00–21:00 IST); run 2 `20260929T162441Z` (ADA+AVAX, 11.3 h, 29 Sep 22:00 – 30 Sep 09:15 IST). Strict fills (trade must print through our price), 300 ms order latency, $50 quotes, inventory cap 3 quotes, maker fee 2.12 bps.

## Question
Does quoting inside Delta's spread earn more than the maker fee after adverse selection, on which pairs, and is it robust?

## Results (net60 = spread captured + 60 s markout − fee, bps per fill)
| Pair / quotes | Run 1 | Run 2 | Combined | 90% CI (hour-block bootstrap) |
|---|---|---|---|---|
| ADA, fair ±5 bps | +3.06 (373 fills) | **+2.41 (373 fills, t 3.5, 9/12 h positive)** | +2.75 (746) | +1.90 … +3.49 |
| ADA, fair ±4 bps | +1.58 | +0.99 | +1.30 (784) | +0.88 … +2.37 |
| ADA, bot's own quotes (~4.1 bps, widens to 6 in vol) | +0.87 | +0.81 | +0.84 (553) | +0.24 … +1.92 |
| AVAX, bot quotes | — | −0.41 (396) | — | STOP |
| NEAR, bot quotes | −4.09 (185) | — | — | STOP |

- ±5 bps was chosen after run 1; run 2 is out-of-sample for it and confirms it.
- The edge needs a spread that is wide in bps **and** fine in ticks, so we can rest inside the touch ≥ ~4–5 bps from mid. ADA: 12.3 bps = 30 ticks, our quote inside the touch 94–97% of the time. AVAX (3.8 bps) and NEAR (6.1 bps): inside only 16–37% → fills come from sweeps → negative.
- Robust to latency: ADA bot quotes net60 +0.68 / +0.83 / +0.89 at 0 / 300 / 1000 ms.
- Dollars are small at $50 quotes: ±5 bps total PnL +$2.66 (run 1) and −$0.49 (run 2; spread +$3.89, fees −$1.77, inventory −$2.61). The dry-run has no inventory skew, so held inventory drifts; the live bot's skew/exit logic matters for dollar PnL.
- Activity depends on time of day: ~2,000 fills/day-equivalent in the IST evening vs ~790 overnight.
- Current scan: no other liquid Delta perp matches ADA's wide-and-fine-tick profile; BERA, STRK, RARE, AIN are 2–4 ticks wide (one tick inside ≈ 2 bps from mid ≈ the fee).

## Conclusion
DISM on ADA at ~5 bps half-spread shows a statistically clear per-fill edge (+2.4 to +3.1 bps net of fees in two sessions). AVAX and NEAR fail and are dropped. Dollar PnL is small at $50 quotes and sensitive to inventory handling.

## Next
1. Keep ADA running to 3 days (target ~Oct 2) to cover weekday day sessions; report per-day results.
2. Replace AVAX with nothing or one tick-structure test (e.g. STRK). Do not expect a second ADA.
3. For the live pilot, set ADA half-spread to a fixed 5 bps (MM_MIN=MM_MAX=5) so the vol multiplier cannot push quotes outside the touch, and verify inventory skew exits positions within minutes.
