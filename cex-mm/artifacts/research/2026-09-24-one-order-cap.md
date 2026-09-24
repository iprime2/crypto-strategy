# Quant memo: Cap each symbol at one order

**Date:** 2026-09-24 · **Venue:** Delta demo · **Symbols:** BTCUSDT, ETHUSDT

## Question

What single change stops this account losing money on inventory?

## Position sign and venue snapshot

Equity about **$148**. Available cash about **$3.55**. The rest is blocked margin.

| Symbol | Sign | Size | Entry vs mark | uP&L | Notional |
|---|---|---|---|---|---|
| BTC | long | 0.009 | 83,283 vs 83,249 | −$0.31 | ~$750 |
| ETH | long | 0.04 | 2,652 vs 2,651 | −$0.07 | ~$106 |

uP&L matches `q × (mark − entry)`. Bot `inventory` matches the venue. Bids are already off (`place_bid: false`). The open loss is small. The risk is the notional: a 10% drop is about **$85**, more than half of equity.

## Attribution

This open mark is inventory, not a broken fair value. The larger equity drop from ~$206 to ~$148 was earlier inventory that was closed. Spread capture is not what the bot records (economics realized stays 0).

## Controls

One-sided quoting is on, so the bot is not adding. Caps were still 0.01 BTC and 0.05 ETH, so several orders fit under the cap. Hard-cap reduce-only only runs above those old caps, so this book can sit at 5–6× equity.

## Next experiment

**Hypothesis:** Caps equal to one order (BTC 0.001, ETH 0.01) force the extra size off and keep a later 10% move inside about $10 of equity.

**Knob:** `MM_MAX_INVENTORY=0.001`, `MM_MAX_INVENTORY_ETHUSDT=0.01`.

**Success:** After the extra size is gone, `|q|` stays at one order, and a 10% move in what remains is under about $15.

**Stop:** Reduce-only orders that increase `|q|`.
