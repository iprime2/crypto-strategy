---
name: oems-api-contract
description: >-
  HTTP contract for the cex-mm OEMS: snapshots, orders, fills, reconcile, TCA,
  and strategy control. Use when adding or changing cex-mm/backend routes or
  the Vite client types.
paths:
  - crypto-strategy/cex-mm/backend/**
  - crypto-strategy/cex-mm/web/**
---

# OEMS API contract

Adapted from Command Center `api-contract-design`.

## Principles

- Shapes are defined first, then Axum handlers, then the React client uses those shapes.
- Do not rename a response field without a client change in the same slice.
- Errors share one body: `code`, `message`.
- Lists take `limit`. Default is small.
- Localhost only. Document which routes read data and which start or stop a process.

## Resources

- `GET /health`
- Snapshots: latest balance, positions, PnL series. Query `strategy_id`.
- `POST` orders and fills. Idempotent on client order id and trade id.
- Reconcile: bot qty, venue qty, mismatch flag.
- TCA: slippage, quoted half-spread, effective spread, fee, markout 1s/5s/30s, net at 5s.
- Strategy: status, config versions, start, stop. Config body excludes secrets.

## Checklist

- Path and method name the resource
- Validation enforced in Rust
- Success and error bodies specified
- `strategy_id` on stored rows
- React types match the JSON

## Anti-patterns

- A second DTO in the UI that drifts from the API
- Returning wallet API keys
- Unbounded history dumps
