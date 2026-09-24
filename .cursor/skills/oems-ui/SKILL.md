---
name: oems-ui
description: >-
  UX for the cex-mm OEMS dashboard: PnL first, risk flags, start/stop clarity,
  loading and error states. Use when designing or polishing cex-mm/web screens.
paths:
  - crypto-strategy/cex-mm/web/**
---

# OEMS UI

Adapted from Command Center `ui-ux-engineer` for an operator book, not a command-center Today page.

## Jobs

See if the book is earning, see inventory versus the exchange, see slippage, and start or stop the new-wallet strategy without touching the bot that is already running.

## Layout

- Header: equity, unrealized PnL, strategy status (running or stopped).
- One primary action on the control view: Start or Stop, labeled with the strategy id.
- Config sits behind that, with the active version visible.
- Red or warning treatment when bot qty differs from venue qty, or when a 10% move in notional is large versus equity. Do not use color as the only signal; add text.

## States

Every panel has loading, empty (“No snapshots yet”), and error with a retry. Start, stop, and save show a disabled control and the API error text.

## Visual

Tailwind spacing scale. No gradients, glow, or emoji decoration. Real `button` and `label` elements. Visible keyboard focus.

## Boundary

The UI calls the OEMS. It does not compute TCA or decide reduce-only.
