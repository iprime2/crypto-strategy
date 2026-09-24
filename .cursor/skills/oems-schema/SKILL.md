---
name: oems-schema
description: >-
  Postgres schema for the cex-mm OEMS: strategy_id, idempotent orders and fills,
  position and balance history, PnL snapshots, TCA rows. Use when adding or
  changing mm-oems migrations or queries.
paths:
  - crypto-strategy/cex-mm/backend/**
---

# OEMS schema

## Tables

- `strategies` — id, name, `desired_state` (`running`|`stopped`), `last_pid`.
- `strategy_config` — new row per save, not an overwrite. Symbols, order qty, max inventory, spread and risk knobs. No API secrets.
- `orders` — unique `(strategy_id, client_order_id)`. Side, price, qty, post-only or reduce-only, reject code.
- `fills` — unique `(strategy_id, trade_id)`. Price, qty, fee. Source of realized PnL.
- `positions` — symbol and time. Venue size, entry, mark, unrealized. Bot size stored beside it.
- `balances` — time. Equity, available, blocked margin.
- `pnl_snapshots` — about once a minute. Realized, unrealized, equity.
- `tca_fills` — one row per fill. Formulas live in `oems-tca`.

Every stored row has `strategy_id`. List queries filter on it and take `limit`.

## Rules

- Migrations only. No schema edits by hand on a running database.
- Parameterized SQL. Idempotent insert: conflict on the unique key updates status, it does not duplicate the row.
- Venue position is the number the UI treats as truth when it differs from bot size.

## Verify

`cargo test -p mm-oems` from `crypto-strategy/cex-mm`.
