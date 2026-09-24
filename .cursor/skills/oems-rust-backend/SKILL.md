---
name: oems-rust-backend
description: >-
  Implements the cex-mm OEMS in Rust with Axum, SQLx, and Postgres. Use for
  cex-mm/backend/mm-oems handlers, migrations, Delta snapshots, TCA, reconcile,
  and start/stop of the new-wallet bot only.
paths:
  - crypto-strategy/cex-mm/backend/**
---

# OEMS Rust backend

Adapted from Command Center `rust-backend-engineer`. This service is the book of record, not the quoter.

## Stack

Axum + Tokio + SQLx + PostgreSQL. Bind **127.0.0.1** only. Crate: `crypto-strategy/cex-mm/backend/mm-oems`. Migrations live in that crate.

## Boundaries

- Quote math stays in `cex-mm/quote-bot/`. Do not move fair value, skew, or reduce-only here.
- Live size and wallet come from Delta. If bot qty and venue qty differ, store both and treat the venue number as truth.
- Do not SIGTERM, flatten, or retarget the mm-bot that is already quoting on `cex-mm/.env`. Start/stop applies only to the process spawned from `cex-mm/quote-bot/.env`.
- Never log or return API keys. Config endpoints reject secret fields.

## Patterns

- Handlers thin; TCA math and reconcile rules in modules with unit tests.
- SQLx parameterized queries. Schema changes are migrations.
- Idempotent writes on client order id and trade id.
- List endpoints require a limit.
- Every row carries `strategy_id`.

## Verify

From `crypto-strategy/cex-mm`: `cargo test -p mm-oems`. If `cc` is missing, prefix `PATH="$HOME/.local/bin-wrappers:$PATH"`.

## Anti-patterns

- Reading `delta-mm-run.log` as the data source
- Pointing the running demo bot at this database
- Business rules only in the React app
