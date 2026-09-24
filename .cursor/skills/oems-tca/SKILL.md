---
name: oems-tca
description: >-
  Transaction-cost formulas for cex-mm OEMS fills: slippage, effective spread,
  fee, and markout at 1s, 5s, and 30s. Use when computing or displaying TCA.
paths:
  - crypto-strategy/cex-mm/backend/**
  - crypto-strategy/cex-mm/web/**
---

# OEMS TCA

Compute in Rust when the fill is stored. The UI only displays the stored numbers. `side` is `+1` for a buy and `−1` for a sell. Bps means multiply the ratio by `10_000`.

## Fields

- **Arrival mid** — venue mid when the order was sent. The bot includes it on the fill event.
- **Slippage bps** — `side × (fill_price − arrival_mid) / arrival_mid × 10_000`. Negative means the fill was worse than that mid.
- **Quoted half-spread bps** — distance from arrival mid to the limit price we sent.
- **Effective spread bps** — `2 × side × (fill_price − mid_at_fill) / mid_at_fill × 10_000`. Uses the mid at the fill, not the arrival mid.
- **Fee** — venue fee in quote currency, and the same fee in bps of notional.
- **Markout bps** at 1s, 5s, and 30s — `side × (mid_after − arrival_mid) / arrival_mid × 10_000`. Fill these when a later mid snapshot exists. Same sign convention as `crypto-strategy/resource/05` section 1.2.
- **Net at 5s** — effective spread bps minus fee bps minus adverse markout at 5s. Adverse markout is the negative part of the 5s markout. This is the sort key on the TCA screen.

## Tests

Unit-test a buy and a sell: worse-than-mid slippage is negative; effective spread uses `mid_at_fill`; missing 5s mid leaves net null rather than zero.

## Do not

Recompute TCA in React. Do not use the arrival mid for effective spread.
