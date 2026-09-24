---
name: oems-frontend
description: >-
  Implements the cex-mm OEMS UI with Vite, React, and Tailwind. Use for
  cex-mm/web screens: PnL, positions, orders, TCA, reconcile, and strategy
  start/stop/config.
paths:
  - crypto-strategy/cex-mm/web/**
---

# OEMS frontend

Adapted from Command Center `frontend-engineer`. Thin client of the Rust OEMS.

## Stack

Vite + React + React Router + Tailwind in `crypto-strategy/cex-mm/web`. One API base URL in config. No second backend in Node.

## Screens

- Equity, realized PnL, unrealized PnL, and a time series from the OEMS.
- Positions with venue size. Flag a row when bot qty and venue qty differ.
- Orders and fills.
- TCA table and slippage chart.
- Start, stop, and strategy config. The form has no API key or secret fields.
- Strategy filter so a second strategy uses the same screens.

## Patterns

- Loading, empty, and error states on every data view.
- Labels on controls. Disable submit while a start/stop/config request is in flight.
- Do not tail logs. Do not recompute slippage or PnL in the browser.

## Verify

From `cex-mm/web`: install, typecheck, and build with the scripts in `package.json`. Exercise the changed screen in the browser against the local OEMS.

## Anti-patterns

- Scattered `fetch` with a second copy of API types
- Showing or editing `DELTA_API_KEY` / `DELTA_API_SECRET`
- Start/stop controls that target the already-running demo bot
