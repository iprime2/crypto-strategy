# Quant memo: Is the ETH strategy ready for a ₹90,000 live account?
**Date:** 2026-09-29 · **Venue:** Delta India demo (compared with mainnet book) · **Symbols:** ETHUSD

## Question
Does the market maker earn money after fees, and what has to change before it runs on a live account of about ₹90,000 (about $1,080)?

## Position sign and venue snapshot
- Wallet $135.36, available $129.88, blocked $5.48.
- Last position from fills: +0.01 ETH, entry about 2718.95. Bot is running, quoting one lot each side.
- Touch spread, ETHUSD: demo 0.18 bps (0.05 tick), mainnet 0.18 bps with about 3x the depth.

## PnL attribution (2026-09-24 → 2026-09-29, 1,642 ETHUSD fills, $44,362 traded)
| Part | USD | Note |
|------|-----|------|
| Gross trading PnL | +10.66 | +10.21 of it is one day (09-28), closing a 0.19 ETH long. That is inventory, not spread. |
| Gross excluding 09-28 | +0.45 | About 0.1 bps on $43.8k of volume. The quoted spread was not kept. |
| Fees | −14.44 | Maker 2.12 bps on $28.6k, taker 5.31 bps on $15.7k |
| Net | −3.78 | Without the one directional day, about −13.8 |

Per fill, using the ETH price one minute later (1-minute candle close, so this is coarse):
| Role | Fills | Mean markout vs fill | Fee | Net per fill |
|------|------:|---------------------:|----:|-------------:|
| Maker | 1,072 | −1.02 bps | 2.12 bps | about −3.1 bps |
| Taker | 570 | +0.37 bps | 5.31 bps | about −4.9 bps |

## Why it does not earn the spread
1. **The fee is larger than the market’s spread.** The book is 0.18 bps wide. A round trip as maker costs about 4.2 bps in fees. Even capturing the full touch every time loses money at this fee tier.
2. **Wide quotes get filled only when the price runs through them.** Minimum half-spread is 8 bps, so our orders sit far from the touch. They fill mostly when ETH moves through them, and the price keeps going: maker markout is −1 bp on average, so the whole quoted edge is gone before fees.
3. **A third of the volume was taker exits.** Hard-cap reduce-only orders cross the spread and pay 5.31 bps. That was $8.36 of the $14.44 in fees.
4. **Cancel-and-replace churn.** On Delta the bot cancels both sides whenever the target moves more than 3 bps, then re-sends. Today’s last 100 orders were all `cancelled_by_user` within about 3 minutes, with no fill after 14:06 IST. Quotes live about a second and never keep queue priority. Delta supports Edit Order and batch edit, so this cancel step is not required.

## Controls actually engaged vs gaps
- Engaged: inventory skew, one-sided near cap, cancel-all on start, venue position reconcile.
- Not protecting the account: daily loss limit (`daily_pnl_usd` is never updated), notional vs equity cap, liquidation-distance stop.

## Conclusion
Do not move this strategy to the live account expecting spread income. At the retail maker fee on Delta India, this design loses about 3 bps on every maker fill and about 5 bps on every taker fill. A larger account makes the same result larger. The one profitable day was a directional position, which is not market making.

## What would change the result, in order
1. **Fees.** Ask `insti-support@delta.exchange` about the Registered Market Maker program. RMM accounts can get fee discounts or rebates, higher rate limits, and up to 200 live orders per contract. A rebate changes the sign of the maker fill; nothing else here does.
2. **Stop cancelling to requote.** Use Edit Order / batch edit so one side is never pulled while the other is replaced, and quotes keep their place.
3. **No taker exits except risk-off.** Let skew and the reducing quote bring inventory back; keep the IOC path for a real limit breach only.
4. **Use the Binance lead to avoid being picked off.** When Binance moves ahead of Delta, pull or move the side that is about to be hit. This is the only lever on the −1 bp markout.
5. **Wire the live safety checks** before any real money: daily loss halt fed from venue equity, and a notional cap as a percent of equity.

## Next experiment (one knob)
**Hypothesis:** Replacing cancel-and-replace with Edit Order raises fill count and does not make maker markout worse.
- Change: Delta quote updates use Edit Order; everything else unchanged.
- Measure over the next 300 maker fills: fills per hour, cancel count, maker markout at 1 minute, maker fee bps.
- Success: fills per hour up, maker markout ≥ −1.0 bps.
- Stop: maker markout below −2 bps over 100 fills, or position above the 0.01 ETH cap.
- This does not make the strategy profitable by itself. Profit needs item 1 (fees) or a markout above about +2.1 bps per maker fill.
