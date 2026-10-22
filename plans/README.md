# Plans (crypto-strategy)

Build and delivery plans for this product live **here**, at the `crypto-strategy/` root—not inside `cex-mm/`.

| Plan | Description |
|------|-------------|
| [cex_mm_rust_bot.plan.md](./cex_mm_rust_bot.plan.md) | Rust CEX MM bot (Bybit-first), slices 0–8 + 3b/6b/7b |
| [live-basis.plan.md](./live-basis.plan.md) | Live basis source for the Binance-anchored fair (PRs A–E, the gate, the first live run) |
| [oems-live.plan.md](./oems-live.plan.md) | The live DISM strategy in the OEMS, observe-only first (on hold) |

When creating a new plan in Cursor, save or copy the markdown into this directory so it stays with the repo and separate from implementation code.

If a duplicate exists under `~/.cursor/plans/`, treat **`crypto-strategy/plans/`** as the canonical copy for this workspace.
