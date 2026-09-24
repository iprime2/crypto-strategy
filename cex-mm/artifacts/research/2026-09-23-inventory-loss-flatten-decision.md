# Research memo: Long inventory uP&L on Delta demo

**Date:** 2026-09-23  
**Account:** Delta India demo (cross margin)  
**Symbols:** BTCUSDT, ETHUSDT  

## Question

Positions are red (~−$10 uP&L). Flatten, wait for bounce, or let the MM bot manage?

## Venue snapshot (2026-09-23)

| | BTC | ETH | Total |
|---|-----|-----|-------|
| Size | +0.006 | +0.18 | |
| Entry vs mark | ~86,773 vs ~85,915 | ~2,765 vs ~2,736 | |
| uP&L | ~−$5.16 | ~−$5.21 | **~−$10.37** |
| Net equity | | | **~$196** (~5% draw on wallet) |

Realized PnL small positive on ETH history; loss is **open inventory**, not spread capture failing in isolation.

## Bot snapshot

- Last log lines **~2026-09-23T07:54 UTC** — verify process still running before trusting live behavior.
- **ETH:** `inventory: 0.18`, `place_bid: false`, `place_ask: false`, repeated **inventory hard cap — cancel all** (0.18 vs typical cap 0.05).
- **BTC:** `inventory: 0.006`, `place_bid: false`, `place_ask: true` (ask-only skew to reduce long).
- Earlier session risk: bot sometimes showed **inventory 0** while venue was long → **two-sided quoting** and accumulation. Treat as **sync bug** until rebuilt binary with venue reconcile is deployed.

## Diagnosis

**Primary:** inventory / directional (long into a dip).  
**Amplifier:** cap breach on ETH and historical economics/venue mismatch.  
**Not primary:** “Binance fair value wrong” — Binance is reference; loss is held size × price move.

## Options

1. **Flatten** (`scripts/flatten_delta.py`) — accept ~−$10; clean slate for MM experiment. **Research default on demo.**
2. **Skew-only with bot on** — no bids; work off via asks. Still exposed if market falls.
3. **Wait for bounce** — discretionary long; **stop the MM bot** if chosen.

## Recommendation

**Stop bot → cancel open orders → flatten** (or explicit directional hold with bot off).  
Then: `cargo build -p mm-bot` with venue inventory reconcile, tighten **ETH** `MM_MAX_INVENTORY_*` for ~$200 account, widen demo spread until markout evidence exists. See [docs/MAINNET_GATE.md](../../docs/MAINNET_GATE.md) before mainnet.

## Engineering follow-ups

- Venue reconcile + `MM_REJECT` in running binary
- `python3 scripts/sync_economics_from_venue.py` after restarts until reconcile is live
- Dashboard: [docs/DASHBOARD-GLOSSARY.md](../../docs/DASHBOARD-GLOSSARY.md)

## Skill

Repeat this workflow: [research-desk](../../../.cursor/skills/research-desk/SKILL.md) (`/research-desk`).
