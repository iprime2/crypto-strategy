# Quant memo: the live stop rule for the real-money DISM run
**Date:** 2026-10-12 · **Venue:** Delta India mainnet (real money, `scripts/live.sh`, ADA only, fair ±5 bps, $50 quotes) · **Data:** shadow run `20261006T161427Z` (6–12 Oct, 9,392 simulated ADA fills at 300 ms), split into 31 blocks of 300 fills · **Tool:** `scripts/live_vs_shadow.py` · **Corrected 2026-10-12:** the Binance-reference findings (frozen feed, see below)

## Question
The 2026-10-05 and 2026-10-09 memos stop the live pilot when **net60 < 0 after 300 fills**. Does that rule still work once real orders are on the book, and if not, what replaces it?

## Why net60 on the Delta mid stops working live
- The bot quotes fair ±5 bps on ADA, whose touch is about 12 bps wide, so its quotes are the Delta touch most of the time (2026-09-30 memo). With real orders resting, the Delta L1 mid that net60 is measured against is mostly our own two quotes. Capture is then about 5 bps by construction, and the 60 s markout tracks our own sticky fair, not the market. Real net60 can read positive while real PnL bleeds.
- The same contamination hits the shadow running next to the live bot: trades that fill us print at our price, which the simulator's strict rule does not count. `live_vs_shadow.py` therefore compares real fills with the simulator on the shadow **before** the live start.
- An independent reference, the Binance mid in `MM_METRICS` (spot ADAUSDT shifted by the Delta–Binance basis), cannot be moved by our orders and works **while its feed is live**. On the part of the run before the freeze below (6 Oct 16:14Z to 8 Oct 17:02Z, 48.8 h), Delta traded a median 3.9 bps below Binance (7.3 bps on 6 Oct), and net60 on the Binance mid matched the clean Delta mid: +1.96 vs +1.99 bps at 20 ms (2,752 fills), +1.80 vs +1.81 at 300 ms (2,784 fills).
- **But the feed froze without an error.** The Binance mid in the shadow log stayed at 0.22715 from 8 Oct 17:02Z to 12 Oct 05:26Z (3.5 days) while Delta moved, so the apparent basis read +467 to +1,162 bps a day. The first version of this memo took that for a real basis that "moves intraday" and concluded the reference was unusable (net60 +0.13 on Binance vs +2.44 on Delta, block SD 2.58). Those numbers came from the frozen feed and are withdrawn. `live_vs_shadow.py` now ignores a Binance mid unchanged for more than 15 minutes (the longest unchanged stretch with a live feed, 6–8 Oct, was 275 s; one tick is about 4 bps) and reports the `b*` columns as unavailable when no fresh mid is left.
- The bot's Binance lead term uses Binance *moves*, so the freeze switched it off: the shadow quoted without the lead from 8 Oct 17:02Z to 12 Oct 05:26Z. Simulated ADA net60 was not lower on those days (20 ms: +2.64, +2.81, +2.79 for 9–11 Oct vs +2.21, +2.11 for 7–8 Oct; 2026-10-09 memo), but market conditions differ between days, so this is not a test of the lead.

## Noise of the candidates
Measured by the 2026-10-12 code review on the 6–12 Oct shadow, 300 ms. Each block is treated as a live run starting flat (`exp_flatstart.py`):

| Metric at the 300-fill check | Mean (bps) | SD (bps) | Blocks below 0 |
|---|---|---|---|
| net60, Delta mid (clean shadow only) | +2.26 | 0.91 | 1/31 |
| net60, Binance mid + basis (6–8 Oct only, live feed) | +1.89 | 0.86 | 0/9 |
| PnL per $ traded (cash + inventory marked − fees) | +2.59 | 2.6 | 5/31 |

The Binance row covers only the 48.8 h with a live feed (9 blocks); the same 9 blocks read +1.88 / 0.86 on the clean Delta mid.

PnL per dollar traded needs no price reference, apart from marking the last few quotes of inventory. It is the real-money number, but at 300 fills it is about 3x noisier than clean net60. Checked again every 50 fills between 300 and 1,200, it fell below 0 in 9/31 blocks.

## Decision (user, 2026-10-12)
**STOP if real PnL per dollar traded is below −2.6 bps after 300 fills, or below 0 after 1,000 fills.** It is counted over every real fill in the run, with the inventory marked at the live bot's own last mid, so it does not depend on the shadow running.
- −2.6 bps is about the flat-start mean minus 2 SD at 300 fills. At 1,000 fills the SD shrinks by about √(300/1000) to about 1.4 bps, so a 0 threshold is about 1.8 SD below the mean. Together they give about **5% false stops** on a strategy that behaves like the shadow. This is an estimate that assumes roughly normal block PnL [SYNTHETIC].
- ADA quoted about 1,700–1,900 simulated fills a day in the shadow, so the 1,000-fill check comes after about half a day *(start)*.
- The rule is printed by `scripts/live.sh report`. Acting on it is the operator's call. The bot's own $15 daily loss stop (`MM_DAILY_LOSS_LIMIT_USD`) stays the automatic hard limit.
- Recalibrate from the live run's own fills once it has about 3,000 of them.
- **Open after the correction above (for the user):** the Binance-reference net60 over real fills (`bnet60` in `live.sh report`) is about 3x quieter than PnL per dollar at 300 fills and is not biased by our own quotes, but it is only valid while the feed is live, and it froze silently once. The decision was made on the withdrawn numbers. It stands as written; whether to add `bnet60 < 0` after 300 fills as an earlier warning, when the report shows a fresh basis, is the user's call.
