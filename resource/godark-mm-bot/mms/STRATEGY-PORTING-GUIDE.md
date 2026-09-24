# Strategy porting guide (copy)

Full document for CEX porting and GoDark context:

**`~/scripts/docs/godark-mm-strategy-cex-porting-guide.md`**

This file is duplicated in the export zip under `docs/` for agents without repo access.

Quick start in this bundle:

- **Strategy source:** `vanilla-mm-rust/src/strategy.rs`, `main.rs`, `lib.rs`
- **Tuning:** `mm-tuning.env`, `artifacts/*/mm-tuning.env`, `mm-tuning-testnet.env`, `mm-tuning-devnet.env`
- **Run:** `start-mm-daemon.sh` / `start-mm-devnet-daemon.sh` (GoDark only)

Build: `cd vanilla-mm-rust && cargo build --release --bins`
