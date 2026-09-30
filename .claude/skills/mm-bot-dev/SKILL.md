---
name: mm-bot-dev
description: >-
  Conventions and test-first loop for changing the Rust market-making bot in
  cex-mm/quote-bot: mm-core quote/fair-value/regime/markout math, the Delta,
  Bybit and Binance adapters, and the mm-bot loop, OMS, risk and recorder. Use
  when editing or debugging any crate under cex-mm/quote-bot.
paths:
  - "cex-mm/quote-bot/**"
---

# MM bot development

Crate boundaries and trading invariants: `.claude/rules/cex-mm.md`. Delivery flow for bigger changes: `lead-engineer`.

## Map

| Concern | Where |
|---|---|
| Quote plan (spread, skew, one-sided flags, hard cap) | `mm-core/src/strategy.rs` `compute_quote` |
| Fair value (microprice, Binance move lead, OFI, funding) | `mm-core/src/fair.rs`, `lib.rs` `compute_quote_cex` |
| Regime L0–L3 | `mm-core/src/regime.rs` |
| Metrics struct (`MM_METRICS` JSON) | `mm-core/src/lib.rs` `MmMetrics` |
| Per-symbol loop, OMS, reduce-only, L3 pause | `mm-bot/src/runner.rs` `run_symbol_loop` |
| Fill handling, markout tasks | `runner.rs` `handle_delta_fill_row`, `mm-bot/src/markout.rs` |
| Kill conditions | `mm-bot/src/risk.rs` |
| Delta REST / WS / products | `mm-delta/src/{rest,ws,book,products}.rs` |
| Recorders | `mm-bot/src/record.rs` (Bybit), `record_delta.rs` (Delta public WS) |

## Test-first loop for mm-core

1. **Red:** add a test in the module's `#[cfg(test)]` that fails today.
2. **Green:** the smallest change that passes.
3. **Refactor** only if clarity needs it. No public API renames on the side.

Good test shapes: a synthetic `BookTop` gives bid < fair < ask and a spread inside bounds; one-sided flags at soft and hard caps; side-aware markout widens only one side; sign of the OFI or lead shift; regime multiplier applied through `compute_quote_cex`; units (bps vs fraction) checked with a hand-computed number.

## Conventions

- Units: prices in quote currency, spreads and shifts in bps, sizes in base units at the `mm-core` boundary (contracts only inside `mm-delta`).
- New knob: `env_f64_for_symbol(&symbol, "MM_…", default)` in the loop or `StrategyConfig::from_env`, plus a line in `config/example.env`.
- New metrics field: add it to `MmMetrics` and set it in `runner.rs`. Python consumers (`dashboard/*.py`, `scripts/shadow_fill_sim.py`) read by key, so new fields are safe; renamed fields are not.
- Nothing slow on the per-loop path: no new REST call per loop, no unbounded `Vec`/`VecDeque`.
- Venue input: `unwrap_or` defaults and skip, never `unwrap()` on exchange JSON.

## Verify

```bash
cd cex-mm && export PATH="$HOME/.local/bin-wrappers:$PATH"
cargo test -p mm-core -p mm-bot -p mm-delta
cargo build --release -p mm-bot
./target/release/mm-bot dry-run --venue delta --env mainnet --symbols ADAUSDT --loop-ms 400   # no keys, no orders; Ctrl-C after a few MM_METRICS lines
```

Dry-run takes config only from the environment (there is no `.env` loading in `mm-bot`). Pass the knobs you are testing on the command line.
