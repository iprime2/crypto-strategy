---
name: mm-ops
description: >-
  Operate the crypto-strategy market maker safely: check or restart the live
  Delta demo bot through the OEMS, run dry-runs and the mainnet shadow test,
  start dashboards, record data, cancel all orders, fire drill, and flatten.
  Use for any request to run, start, stop, restart, check status, or clean up
  positions or orders. Every action that touches the live bot or the account
  needs the user's explicit go-ahead first.
---

# MM operations

Commands run from `cex-mm/` unless stated. Build with `export PATH="$HOME/.local/bin-wrappers:$PATH"`.

## Safety ladder

| Level | Examples | Needs user go-ahead |
|---|---|---|
| Read-only | status, logs, venue PnL, fills, dashboards, `dry-run`, shadow test | No |
| Orders on demo | start / stop / restart the live bot, `cancel-all`, fire drill | **Yes** |
| Position change | `flatten_delta.py`, reduce-only by hand | **Yes, and state the position and expected cost first** |
| Mainnet orders | anything with keys and `--env mainnet` | **Only via `docs/MAINNET_GATE.md` and an explicit request** |

## What is running

| Service | Address | Check |
|---|---|---|
| Live demo bot (`mm-bot run --venue delta --env testnet`) | spawned by the OEMS, env from `quote-bot/.env` | `curl -s localhost:8791/api/strategies` → `desired_state`, `last_pid` |
| OEMS API | 127.0.0.1:8791 | `curl -s localhost:8791/api/snapshots/latest` |
| TimescaleDB | 127.0.0.1:5462 | used by the OEMS only |
| Web UI | 127.0.0.1:5179 | `cd web && npm run dev` |
| Shadow test | `artifacts/shadow/current/` | `scripts/shadow.sh status` |
| Shadow dashboard | 127.0.0.1:8788 | `scripts/shadow.sh dashboard` |

The live bot's stdout goes to /dev/null, so there is no `MM_METRICS` log for it. Use venue data and the OEMS instead.

## Live demo bot (ask first)

```bash
curl -s -X POST localhost:8791/api/strategies/mm/stop     # stops the pid the OEMS spawned, cancels its orders, leaves the position
curl -s -X POST localhost:8791/api/strategies/mm/start    # cancels open orders, then quotes with quote-bot/.env + latest config
```

Restart after a code change only after `cargo build -p mm-bot` (the OEMS runs `target/debug/mm-bot`). Confirm afterwards: the pid is alive, and open orders on Delta look as intended. Never signal a process the OEMS did not start.

## Real-money DISM pilot (ask first, every time)

Strategy `dism` (mainnet, settings `config/dism.env`, ADA only). Needs `DELTA_MAINNET_API_KEY/SECRET` in `quote-bot/.env`, the OEMS started with `OEMS_ALLOW_MAINNET=1`, and the typed confirmation:

```bash
curl -s -X POST -H 'X-OEMS-Client: cli' -H 'Content-Type: application/json' -d '{"confirm":"START REAL"}' localhost:8791/api/strategies/dism/start
curl -s -X POST -H 'X-OEMS-Client: cli' localhost:8791/api/strategies/dism/stop
```

The bot itself arms Delta's dead man's switch, a $15 daily loss stop and the taker-fill guard (`mm-bot/src/account.rs`). Never start it without the user's explicit go-ahead in this conversation.

## Read-only venue checks

```bash
python3 -c "import json,sys; sys.path.insert(0,'dashboard'); from delta_pnl import fetch_venue_pnl; print(json.dumps(fetch_venue_pnl(), indent=2))"
python3 ../.claude/skills/quant-researcher/scripts/fetch_delta_fills.py --out /tmp/fills.json
```

## Shadow test (mainnet data, no keys, no orders)

```bash
scripts/shadow.sh start ADAUSDT,NEARUSDT
scripts/shadow.sh status
scripts/shadow.sh report --sweep 3,4,5,6,8 --latencies 0,300,1000
scripts/shadow.sh dashboard
scripts/shadow.sh stop
```

Runs survive the session but not a WSL shutdown or reboot. After a restart, check `status` and start again; a new run gets a new directory.

## Kill path and cleanup (ask first)

```bash
cargo run -p mm-bot -- cancel-all --venue delta --env testnet --symbol ETHUSDT
MM_SYMBOL=ETHUSDT ./scripts/fire_drill.sh    # cancel-all timing drill; defaults to BTCUSDT, and `cargo run` build time counts toward its 2 s target, so build first
python3 scripts/flatten_delta.py             # market-closes positions: state size and cost to the user first
python3 scripts/sync_economics_from_venue.py # reset bot-side economics to the venue
```

Cancel-all on start is correct. Flattening on every restart is not: flattening is a risk decision.

## What each environment proves

- Demo: plumbing (auth, post-only, edits, fills routing, cancel-all). Not edge: demo flow and prices differ from mainnet.
- Shadow test: whether a quote would have earned spread after fees against real mainnet trades, under a conservative fill model.
- Mainnet small size: the only proof of edge, per `docs/MAINNET_GATE.md`.
