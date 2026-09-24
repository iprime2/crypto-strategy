# Quant memo: How this book can earn instead of lose

**Date:** 2026-09-24 · **Venue:** Delta demo · **Symbols:** BTCUSDT, ETHUSDT

## Question

What one change makes this strategy earn the spread instead of losing on inventory?

## What the account shows

- Equity about **$149**. Open ETH is **+0.01**, unrealized about **−$0.03**, realized on that contract about **−$0.09**.
- Wallet was about **$206** before the large long, about **$169** after that long was closed, and about **$149** now. The loss is already booked. The open coin is not the loss.
- Bot files show **749** BTC fills and **764** ETH fills with **realized PnL stored as 0**, so the bot is not keeping score.

## Why it loses

1. **It holds coins in a falling market.** Caps are 0.01 BTC and 0.05 ETH. On a $149 account, 0.01 BTC is about $830, several times the account. A small price drop is a large dollar loss.
2. **It keeps buying after it is already long.** ETH size 0.01 is below 35% of the 0.05 cap, so both bid and ask stay on.
3. **Getting out pays the spread.** Reduce-only sells hit the bid. That gives away the gap the strategy is supposed to earn.
4. **Fills are toxic, but not the whole story.** Adverse markout is about 6–7 bps. Quoted spread is about 24 bps. The inventory losses are larger than that drag.

## One change to try first

**Hypothesis:** If the bot stops bidding once it holds one order of inventory, and it only sells with a resting ask (not a hit-the-bid order) until the hard cap, equity stops falling from directional longs and the ask can earn the spread.

**Knob:** `MM_INV_ONE_SIDED_RATIO` so the adding side turns off at about one order (ETH: bid off once long ≥ 0.01). Do not send reduce-only unless size is over the hard cap or a loss limit hits.

**Success:** Over the next session, inventory stays inside one order, and realized PnL from round-trips is positive after fees. A green mark on the open coin is not the metric.

**Not in this change:** new spread model, new fair value, rebuilding the OEMS.

## After that, if markouts stay negative

Widen the quoted spread until half the spread is larger than the 6–7 bps adverse reading plus fees. Shrink the BTC cap to about 0.001 so one fill cannot dominate a $149 account.
