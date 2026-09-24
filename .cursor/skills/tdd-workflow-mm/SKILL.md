---
name: tdd-workflow-mm
description: >-
  Test-first workflow for mm-core quote engine, OFI, regime, markout guards, and
  economics. Use when changing compute_quote, fair value, or toxicity floors.
---

# TDD workflow (mm-core)

## When to use

- Changes to `mm-core/src/strategy.rs`, `fair.rs`, `ofi.rs`, `regime.rs`, `economics.rs`, `lib.rs` quote path
- Bug fixes where markout sign, reservation, or spread floor was wrong

## Loop

1. **Red:** add or extend a unit test in the same module’s `#[cfg(test)]` (mirror GoDark test names where applicable).
2. **Green:** smallest change to pass.
3. **Refactor:** only if clarity demands it; no drive-by API renames.

## Test ideas

- Synthetic book → expected bid/ask ordering and spread bps bounds
- Inventory one-sided flags at soft/hard cap
- Side-aware markout widens bid only / ask only
- OFI drift sign; α·μ floor raises spread under adverse series
- Regime L1+ multiplies spread in metrics path (via `compute_quote_cex`)

## Command

```bash
cd crypto-strategy/cex-mm && cargo test -p mm-core
```

## Exit

All mm-core tests pass; new behavior has at least one test that would fail on revert.
