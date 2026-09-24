---
name: testnet-ops
description: >-
  Run cex-mm on Bybit testnet safely — dry-run, universe preview, record,
  fire drill, cancel-all. Use when validating plumbing, feeds, or kill path
  without claiming mainnet edge.
---

# Testnet operations

## Prerequisites

- `cex-mm/.env` from `config/example.env` with **testnet** Read+Trade keys
- `cd crypto-strategy/cex-mm`

## Safe progression

1. **Preview universe** (no keys required for public top-N):
   `cargo run -p mm-bot -- universe --top-n 10 --env testnet`
2. **Dry-run** (live feeds, no orders):
   `cargo run -p mm-bot -- dry-run --top-n 3 --env testnet`
3. **Record** (data for backtest):
   `cargo run -p mm-bot -- record --top-n 5 --duration 600 --bybit-env testnet`
4. **Live testnet** (small size, wide limits in env):
   `cargo run -p mm-bot -- run --env testnet --top-n 1`
5. **Kill drill:**
   `./scripts/fire_drill.sh` or `cargo run -p mm-bot -- cancel-all --all --env testnet`

## What testnet proves

- WS/REST auth, post-only placement, execution routing, metrics lines (`MM_METRICS`)
- **Not** mainnet queue quality or adverse selection edge

## Exit

Commands run with exit 0 or documented blocker; no keys in chat logs; cancel-all succeeds within drill target when requested.
