---
name: cex-mm
description: >-
  Implement and operate the Rust CEX MM bot in crypto-strategy/cex-mm/. Use when
  editing mm-core, mm-bybit, mm-bot, testnet runs, recorder, or universe/top-N
  symbol selection. Read STRATEGY.md and plans/ before behavior changes.
---

# CEX-MM (Rust bot)

Not sure which skill to use? Read **`using-cs-skills`** first.

## Roots

- **Design:** `crypto-strategy/STRATEGY.md` + `resource/`
- **Build plan:** `crypto-strategy/plans/cex_mm_rust_bot.plan.md` (and siblings in `plans/`)
- **Code:** `crypto-strategy/cex-mm/` only

Do not add new plan files or agent skills under `cex-mm/`—keep them in `crypto-strategy/plans/` and `crypto-strategy/.cursor/skills/`.

## Stack

- Rust workspace: `mm-core`, `mm-bybit`, `mm-binance`, `mm-bot`
- Bybit testnet first; mainnet only per `cex-mm/docs/MAINNET_GATE.md`
- Secrets: `cex-mm/.env` (gitignored), Read+Trade keys only

## Common commands

```bash
cd crypto-strategy/cex-mm
cargo test -p mm-core
cargo run -p mm-bot -- universe --top-n 10 --env testnet
cargo run -p mm-bot -- dry-run --top-n 5 --env testnet
cargo run -p mm-bot -- run --env testnet   # needs .env keys
```

## Symbol universe

- Manual: `MM_SYMBOLS` or `--symbols`
- Auto: `MM_TOP_N` / `--top-n` (Bybit 24h turnover at startup)
- Per-symbol env: `MM_ORDER_QTY_ETHUSDT`, `MM_MAX_INVENTORY_ETHUSDT`, etc.

## Delivery

For non-trivial changes, follow `lead-engineer` skill: slices, tests, evidence in the report.
