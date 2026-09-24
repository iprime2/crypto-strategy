---
name: research-desk
description: >-
  Short incident desk for crypto-strategy CEX MM: venue vs bot snapshot, loss
  type, and flatten vs skew vs hold. Use for a quick "are we in trouble" check
  before a full quant memo. Invoke with /research-desk. For attribution,
  experiments, or risk design, use /quant-researcher.
disable-model-invocation: true
paths:
  - crypto-strategy/**
---

# Research desk

Five-minute incident check. Full quant workflow: [quant-researcher](../quant-researcher/SKILL.md). Design: `crypto-strategy/resource/05-risk-hedging-pnl-failure-modes.md`.

## Steps

1. **Venue.** From `crypto-strategy/cex-mm` with `.env` loaded, call `dashboard/delta_pnl.py` `fetch_venue_pnl`. Record equity, uP&L, and each position's sign and size.
2. **Bot.** Last `MM_METRICS` lines and log mtime in `cex-mm/artifacts/delta-mm-run.log`. Stale log means the process is stopped.
3. **Match.** Venue `q` must match `inventory`. If not, label it an estimator bug and stop strategy conclusions.
4. **Classify.** Inventory if uP&L ≈ `q × (mark − entry)`. Adverse selection only with negative markout after fills. Ops if rejects, hard-cap loops, or a dead log.
5. **Recommend** using the matrix below. User decides flatten.

| State | Call |
|-------|------|
| Synced, inside cap, skew on (`place_bid` false when long) | Let the reducing side work, or flatten to reset the demo |
| `\|q\|` above `MM_MAX_INVENTORY*` | Stop bot. Hard cap only cancels quotes; it does not exit. Flatten or reduce-only |
| Bot flat, venue not | Pause, `scripts/sync_economics_from_venue.py`, rebuild before quoting |
| User wants a bounce | Bot off. That is a directional hold, not MM |

Cancel-all on every bot start is correct. Flatten on every restart is not.

## Memo

`cex-mm/artifacts/research/YYYY-MM-DD-<slug>.md`: question, venue snapshot, bot snapshot, diagnosis, options, recommendation.
