---
name: oems-supervisor
description: >-
  Start and stop only the new-wallet cex-mm quote bot from the OEMS. Use when
  implementing strategy control, pid tracking, or config apply. Never signals
  the bot that is already quoting on cex-mm/.env.
paths:
  - crypto-strategy/cex-mm/backend/**
---

# OEMS process supervisor

## Two processes

| | Already quoting | New wallet |
|---|---|---|
| Binary cwd | `cex-mm/` | `cex-mm/quote-bot/` |
| Env file | `cex-mm/.env` | `cex-mm/quote-bot/.env` |
| Who may stop it | The operator, by hand | This supervisor |

Do not SIGTERM, flatten, or rewrite `cex-mm/.env`. Do not attach the live pid to a strategy row.

## Start

1. Refuse if `desired_state` is already `running` and the pid is alive.
2. Spawn `mm-bot` with config from the latest `strategy_config` row injected as env, plus keys loaded from `quote-bot/.env`.
3. Store pid and `desired_state=running`.

## Stop

1. Set `desired_state=stopped`.
2. SIGTERM that pid only.
3. Cancel open orders for that strategy’s symbols on Delta. Leave the position.

## Config apply

Stopped: insert a new config version. Running: insert the version, stop, then start. No hot reload.

## Verify

A unit or process test that a stop request does not match a pid started outside `quote-bot/.env`.
