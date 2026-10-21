# Phase-2 diagnostics (pre-registered, not trials)


## D-1 states, nine, 2020-05-01..2026-09-30 (next-7-day log return, NW t lag 6)

| state | mean (all) | t | n | mean (sig>0) | t | n |
|---|---|---|---|---|---|---|
| Bull | +1.995% | +5.22 | 6426 | +1.995% | +5.22 | 6426 |
| Correction | +0.297% | +0.76 | 4102 | +0.843% | +1.63 | 2456 |
| Bear | +0.086% | +0.28 | 6279 | +nan% | +nan | 0 |
| Rebound | -0.605% | -1.73 | 3895 | -0.457% | -0.91 | 1782 |

## D-1 states, nine, 2022-01-01..2026-09-30 (next-7-day log return, NW t lag 6)

| state | mean (all) | t | n | mean (sig>0) | t | n |
|---|---|---|---|---|---|---|
| Bull | +0.759% | +2.00 | 3835 | +0.759% | +2.00 | 3835 |
| Correction | -0.038% | -0.09 | 2733 | +0.513% | +0.99 | 1555 |
| Bear | -0.173% | -0.55 | 5561 | +nan% | +nan | 0 |
| Rebound | -0.982% | -2.75 | 3367 | -0.889% | -1.74 | 1412 |

## D-1 states, 24 ex-ante, 2020-05-01..2026-09-30 (next-7-day log return, NW t lag 6)

| state | mean (all) | t | n | mean (sig>0) | t | n |
|---|---|---|---|---|---|---|
| Bull | +0.884% | +3.27 | 15037 | +0.885% | +3.27 | 15035 |
| Correction | -0.306% | -1.17 | 10341 | +0.605% | +1.63 | 5731 |
| Bear | +0.094% | +0.51 | 18541 | +nan% | +nan | 0 |
| Rebound | -0.365% | -1.54 | 10774 | +0.259% | +0.73 | 4814 |

## D-1 states, 24 ex-ante, 2022-01-01..2026-09-30 (next-7-day log return, NW t lag 6)

| state | mean (all) | t | n | mean (sig>0) | t | n |
|---|---|---|---|---|---|---|
| Bull | +0.045% | +0.16 | 8916 | +0.046% | +0.16 | 8914 |
| Correction | -0.790% | -3.10 | 6805 | +0.092% | +0.26 | 3587 |
| Bear | -0.233% | -1.22 | 15954 | +nan% | +nan | 0 |
| Rebound | -0.944% | -3.81 | 9008 | -0.235% | -0.61 | 3642 |

**Gate:** SIG-9 runs = False (Correction >= Bull on the 24-coin panel in both windows); OVL-3 runs = True (Correction <= 0 with t < 0 in both windows).


## D-3 decision-to-fill drift (Binance 5 m, 2024-01..2026-09, signed 00:00 -> 00:05 UTC return by trade direction)

| direction | mean bps | NW t | n |
|---|---|---|---|
| buy | +0.05 | +0.07 | 2250 |
| sell | +3.79 | +3.55 | 2302 |
| none | +0.51 | +0.94 | 4475 |

Per coin (buy / sell mean bps): BTC +1.9/-0.4, ETH -1.0/+2.2, XRP -2.8/+8.3, BNB +2.0/+3.1, ADA +3.5/+10.4, LTC -0.8/+1.8, LINK +1.3/-0.4, DOGE -5.1/+9.4, BCH -0.2/+1.8

**Gate:** re-run daily cost lines with drift = YES (|mean| > 2 bps on buys or sells: buys +0.05, sells +3.79; a positive buy drift is a cost to the buyer, a negative sell drift a cost to the seller).


## D-4 Delta MARK vs last-trade daily closes (sign agreement per sleeve; Sharpe of the daily rule on each series)

sign agreement 20/60/120: 0.9961 / 0.9986 / 0.9989; |MARK - last| median 2.5 bps, 95th pct 27.6 bps, n = 8403
- last-trade daily: Sharpe 0.994 CAGR +16.5% maxDD -14.1% turnover 14.8x
- last-trade weekly: Sharpe 0.704 CAGR +7.0% maxDD -9.1% turnover 3.2x
- MARK daily: Sharpe 0.985 CAGR +16.3% maxDD -14.0% turnover 14.9x
- MARK weekly: Sharpe 0.709 CAGR +7.1% maxDD -9.1% turnover 3.2x
