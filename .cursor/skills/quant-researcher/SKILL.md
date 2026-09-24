---
name: quant-researcher
description: >-
  Quant researcher for crypto-strategy CEX market making. Attributes PnL
  (spread, inventory, fees, funding), checks venue vs bot inventory, designs
  one-knob experiments, and specifies risk that flattens before liquidation.
  Use when the user asks what a quant would do, loss or liquidation risk,
  flatten vs hold, markout, or strategy validation. Invoke with /quant-researcher.
disable-model-invocation: true
paths:
  - crypto-strategy/**
---

# Quant researcher

Form hypotheses, measure, attribute PnL, and specify **one** testable change. Do not predict prices or place discretionary trades.

Design source: `crypto-strategy/resource/05-risk-hedging-pnl-failure-modes.md` and `STRATEGY.md`. Code: `crypto-strategy/cex-mm/`. Incident checklist: [research-desk](../research-desk/SKILL.md).

## Mindset

1. **Sign the position first.** `q > 0` is long: a falling price loses money. `q < 0` is short: a falling price gains. Do not advise from the user's label if the venue size disagrees.
2. **Identification before opinions.** If venue `q` ≠ bot `inventory` or economics JSON, stop tuning spread, κ, or γ. Fix the estimator.
3. **Attribute, then tune.** `PnL = spread capture + inventory + fees + funding + hedge` (`resource/05` §1). A red day that matches `q × Δmark` is inventory, not a failed fair-value model.
4. **Quote risk ≠ account risk.** Cancelling orders leaves `q` on. Liquidation is an exchange close of that `q` when margin is gone.
5. **Pre-register.** One knob, a success metric (usually signed markout at 5s over N fills), and a stop. Mainnet only via `cex-mm/docs/MAINNET_GATE.md`.

## Live incident

From `crypto-strategy/cex-mm` (load `.env` first):

```bash
python3 -c "import json,sys; sys.path.insert(0,'dashboard'); from delta_pnl import fetch_venue_pnl; print(json.dumps(fetch_venue_pnl(), indent=2))"
grep 'MM_METRICS' artifacts/delta-mm-run.log | tail -8
stat artifacts/delta-mm-run.log
```

Record equity, uP&L, realized, each `q`, entry, mark, margin blocked, and whether the log is still being written.

Then:

| Check | Pass | Fail |
|-------|------|------|
| Direction | uP&L sign matches `q × (mark − entry)` | Mis-labeled long/short |
| Estimator | Metrics `inventory` ≈ venue `q` | Do not interpret quotes |
| Caps | `\|q\|` ≤ `MM_MAX_INVENTORY*` | Over cap: position is stuck if both sides are cancelled |
| Loss trigger | Session loss is actually fed into `daily_pnl_usd` | See known gaps below |
| Notional vs equity | A 10–15% move in `q` cannot wipe equity | Deleverage or flatten |

**Default on demo when the book is confounded or over cap:** stop the bot, cancel orders, flatten (`python3 scripts/flatten_delta.py`) only with user consent. Holding for a bounce is a separate directional bet — bot off, documented as such.

**Restart policy:** cancel-all on start (`MM_CANCEL_ALL_ON_START`, default on). Do **not** flatten on every restart. Flatten is a risk decision, not a process restart.

## What a quant requires in the MM (and what this bot does)

| Control | Quant standard | This repo today |
|---------|----------------|-----------------|
| Inventory skew + one-sided near the cap | Yes | `mm-core` `compute_quote_cex` (`place_bid` / `place_ask`) |
| Hard `\|q\|` and notional vs equity | Yes, sized so a shock cannot liquidate | `MM_MAX_INVENTORY*`; notional vs equity is not enforced |
| Over cap | **Reduce-only** until inside the cap | `runner.rs` cancels **all** quotes and continues — freezes `q` |
| Daily loss | Halt **and flatten** when realized+unrealized ≤ −limit | `MM_DAILY_LOSS_LIMIT_USD` exists; `daily_pnl_usd` is never updated, so it does not fire |
| Margin / liq distance | Stop adding and reduce when liquidation is inside a buffer | Not implemented |
| Markout guard | Widen or pull the toxic side | `MarkoutGuard`; often idle until fills are logged |
| Kill | Cancel, then flatten on true risk-off | Kill path cancels only (`risk.rs` `should_kill`) |
| Stale orders | Cancel on start and before requote | `MM_CANCEL_ALL_ON_START` |

If the user asks to add risk logic, specify the missing rows as acceptance criteria. Do not claim the daily-loss or hard-cap paths already protect the account.

## Experiment (not an emergency)

1. Map the claim to `resource/05` and the function in `cex-mm/crates/`.
2. Hypothesis in one sentence.
3. Change one knob (cap, L3 depth ratio, min spread, one symbol).
4. Success: signed markout at 1s/5s/30s (`resource/05` §1.2), plus fill count, cancel rate, reject rate. A green uP&L day is not the metric.
5. Write `cex-mm/artifacts/research/YYYY-MM-DD-<slug>.md`.

## Memo

```markdown
# Quant memo: <title>
**Date:** · **Venue:** demo|mainnet · **Symbols:**

## Question
## Position sign and venue snapshot
## PnL attribution (spread / inventory / fees / funding)
## Controls actually engaged (skew, cap, kill) vs gaps
## Conclusion
## Next experiment (one knob + metric) or flatten recommendation
```

## Ops (user must agree before flatten)

```bash
cd crypto-strategy/cex-mm
python3 scripts/sync_economics_from_venue.py
python3 scripts/flatten_delta.py
cargo run -p mm-bot -- cancel-all --venue delta --env testnet --all
```
