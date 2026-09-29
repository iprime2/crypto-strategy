# Quant memo: Where the ETH market maker can find edge (fees aside)
**Date:** 2026-09-29 · **Venue:** Delta India demo · **Symbols:** ETHUSD (Binance ETHUSDT as reference)

## Question
With the fee question sent to Delta (RMM), what changes to the strategy itself can make a maker fill profitable?

## What the fills say (from 2026-09-29 live-readiness memo)
- Maker fills lose about 1.0 bp one minute later, before a 2.12 bp maker fee.
- Delta ETHUSD touch spread is 0.18 bps. Our minimum half-spread is 8 bps, so we fill mostly when the price runs through us.

## Test: does Binance lead Delta?
Data: 35,048 `MM_METRICS` samples over 50.6 hours (2026-09-23/24 log), Binance mid vs Delta venue mid.

| Signal | Next Delta move | Slope | Same direction |
|--------|-----------------|------:|---------------:|
| Binance move over last 2 s, when > 3 bps | next 5 s | 0.98 | 77.3% (n=1,177) |
| Binance move over last 5 s, when > 3 bps | next 5 s | 0.77 | 77.5% (n=2,922) |
| Binance move over last 5 s, when > 3 bps | next 15 s | 0.75 | 68.1% |
| Raw Binance − Delta gap (not demeaned) | next 5 s | 0.02 | 47.7% |
| Gap minus its 5-minute average | next 30 s | 0.36 | corr 0.29 |

Delta follows a Binance move almost one-for-one within a few seconds. A resting Delta quote on the side Binance just moved toward is the order that gets picked off.

## What the bot does today
`mm-core/src/fair.rs`: `fair += 0.5 × (binance_mid − fair_native)`.
- This uses the raw price gap. The gap averages −11.9 bps with a standard deviation of 30.5 bps, because Binance ETHUSDT and Delta demo ETHUSD are different contracts in different quote currencies.
- So fair value is pushed about 6 bps away from Delta's price on average, and wobbles by about 15 bps. That noise moves quotes more than 3 bps often, which is also what drove the requote churn.
- The raw gap has no predictive power (slope 0.02, 47.7% direction).

## Changes, ranked by evidence
1. **Lead on Binance returns, not the level gap.** Shift fair by the recent Binance move (or the gap minus its rolling average). This keeps the lead signal and drops the structural offset.
2. **Fade the side about to be hit.** When Binance has moved more than about 3 bps in the last few seconds, pull or move back the quote on the side Delta is about to trade into. Leave the other side up. This is the direct fix for negative maker markout.
3. **Set the half-spread from break-even, not a fixed 8 bps.** Break-even per side is about the maker fee plus the loss after a fill. With a working fade, test a floor near 3–4 bps so fills come from normal flow instead of only price sweeps. Only after item 2 shows maker markout at or above zero.
4. **Keep maker-only exits.** Immediate reduce-only exits paid 5.31 bps and were 58% of fees. Keep that path only for a real limit breach.
5. **Microprice is already blended** (30% weight). Leave it; it is not the bottleneck.

## Limits
- Demo prices, not mainnet. Delta demo may track Binance differently from live.
- The lead-lag sample is from the older log; newer runs do not write `MM_METRICS` because the supervisor discards stdout.

## Next experiment (one knob)
**Hypothesis:** Using the recent Binance move instead of the raw price gap removes the fair-value offset and raises maker markout.
- Change: `fair.rs` lead term only. Everything else stays the same.
- Measure over the next 300 maker fills: maker markout at 1 minute, fills per hour, edits per minute.
- Success: maker markout ≥ 0 bps (from −1.02) with fills per hour not below the current run.
- Stop: maker markout below −2 bps over 100 fills.
- Then, as a separate test, add the fade from item 2.
