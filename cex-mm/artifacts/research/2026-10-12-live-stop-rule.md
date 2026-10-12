# Quant memo: the live stop rule for the real-money DISM run
**Date:** 2026-10-12 · **Venue:** Delta India mainnet (real money, `scripts/live.sh`, ADA only, fair ±5 bps, $50 quotes) · **Data:** shadow run `20261006T161427Z` (6–12 Oct, 9,392 simulated ADA fills at 300 ms), split into 31 blocks of 300 fills · **Tool:** `scripts/live_vs_shadow.py`

## Question
The 2026-10-05 and 2026-10-09 memos stop the live pilot when **net60 < 0 after 300 fills**. Does that rule still work once real orders are on the book, and if not, what replaces it?

## Why net60 on the Delta mid stops working live
- The bot quotes fair ±5 bps on ADA, whose touch is about 12 bps wide, so its quotes are the Delta touch most of the time (2026-09-30 memo). With real orders resting, the Delta L1 mid that net60 is measured against is mostly our own two quotes. Capture is then about 5 bps by construction, and the 60 s markout tracks our own sticky fair, not the market. Real net60 can read positive while real PnL bleeds.
- The same contamination hits the shadow running next to the live bot: trades that fill us print at our price, which the simulator's strict rule does not count. `live_vs_shadow.py` therefore compares real fills with the simulator on the shadow **before** the live start.
- An independent reference, the Binance mid in `MM_METRICS` (spot ADAUSDT), is no cure. The Delta–Binance basis was **+295 bps** (median, 8–9 Oct) and moves intraday. On the clean pre-live shadow, 20 ms latency, net60 is +2.44 bps on the Delta mid but only +0.13 bps on the basis-shifted Binance mid. That reference would call a profitable day break-even. Simulated PnL that day was +$11.58.

## Noise of the candidates
Measured by the 2026-10-12 code review on the 6–12 Oct shadow, 300 ms. Each block is treated as a live run starting flat (`exp_flatstart.py`):

| Metric at the 300-fill check | Mean (bps) | SD (bps) | Blocks below 0 |
|---|---|---|---|
| net60, Delta mid (clean shadow only) | +2.26 | 0.91 | 1/31 |
| net60, Binance mid + basis | | 2.58 | 4/31 |
| PnL per $ traded (cash + inventory marked − fees) | +2.59 | 2.6 | 5/31 |

PnL per dollar traded needs no price reference, apart from marking the last few quotes of inventory. It is the real-money number, but at 300 fills it is about 3x noisier than clean net60. Checked again every 50 fills between 300 and 1,200, it fell below 0 in 9/31 blocks.

## Decision (user, 2026-10-12)
**STOP if real PnL per dollar traded is below −2.6 bps after 300 fills, or below 0 after 1,000 fills.** It is counted over every real fill in the run, with the inventory marked at the live bot's own last mid, so it does not depend on the shadow running.
- −2.6 bps is about the flat-start mean minus 2 SD at 300 fills. At 1,000 fills the SD shrinks by about √(300/1000) to about 1.4 bps, so a 0 threshold is about 1.8 SD below the mean. Together they give about **5% false stops** on a strategy that behaves like the shadow. This is an estimate that assumes roughly normal block PnL [SYNTHETIC].
- ADA quoted about 1,700–1,900 simulated fills a day in the shadow, so the 1,000-fill check comes after about half a day *(start)*.
- The rule is printed by `scripts/live.sh report`. Acting on it is the operator's call. The bot's own $15 daily loss stop (`MM_DAILY_LOSS_LIMIT_USD`) stays the automatic hard limit.
- Recalibrate from the live run's own fills once it has about 3,000 of them.
