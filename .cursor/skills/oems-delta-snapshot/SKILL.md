---
name: oems-delta-snapshot
description: >-
  Delta wallet and position snapshot for the cex-mm OEMS. Use when polling
  balances, positions, or marks into Postgres. Venue size wins over the bot.
paths:
  - crypto-strategy/cex-mm/backend/**
---

# OEMS Delta snapshot

Port the read path in `crypto-strategy/cex-mm/dashboard/delta_pnl.py`. Poll about every 10 seconds. Keys come from `cex-mm/quote-bot/.env` for the new wallet. Do not read `cex-mm/.env` for this loop.

## Endpoints

- `GET /v2/wallet/balances` — USD row: balance, available, blocked margin. Account `net_equity` from the response meta.
- `GET /v2/positions/margined` — each open contract.

Testnet base: `https://cdn-ind.testnet.deltaex.org`. Mainnet only if `MM_ENV=mainnet` on the new-wallet env.

## Map

- `BTCUSD` → `BTCUSDT`, `ETHUSD` → `ETHUSDT`, `SOLUSD` → `SOLUSDT`.
- Position base = contract `size` × `contract_value`.
- Store entry, mark, realized, unrealized, and margin.
- Sign: positive size is long. Unrealized should match `size × (mark − entry)` in direction.

## Store

Insert `balances`, `positions`, and fold into `pnl_snapshots` about once a minute. On each position row, keep the latest bot qty for that strategy and symbol. If they differ by more than `1e-5`, set the mismatch flag. The number the UI shows as size is the venue size.

## Do not

Log the API key, secret, or signature. Do not place or cancel orders from the snapshot loop.
