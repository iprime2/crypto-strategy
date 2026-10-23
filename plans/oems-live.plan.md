---
name: Live strategy in the OEMS (observe first)
overview: Make the OEMS the book of record for the real-money DISM run on Delta India mainnet: PnL, uPnL, fees, funding, volume, slippage against the bot's fair, order history, position and charts, with the stop rule and aborts computed in one tested place. The OEMS observes only; the live bot keeps running under scripts/live.sh until the OEMS has matched the scripts for a week. Replaces the temporary dashboard (~/mm-dash on the VM).
todos:
  - id: s0-vm-ops
    content: "S0 (VM ops): rotate artifacts/live/*/bot.log, keep scripts reading rotated logs; disk increase (owner, cloud console)"
    status: pending
  - id: s1-observe
    content: "S1: observe-only control mode for a strategy (control routes refused); telemetry tails an external run log; OEMS installed on the VM (owner's go for sudo)"
    status: pending
  - id: s2-ledger
    content: "S2: wallet-transaction ledger (Delta cashflow, commission, funding) + uPnL from venue position x mark; /api/performance by day and by run"
    status: pending
  - id: s3-tca-fair
    content: "S3: TCA against the bot's anchored fair (per-second fair from MM_METRICS), markouts 1/5/30/60/300 s; one-off import of past runs"
    status: pending
  - id: s4-orders-runs-rules
    content: "S4: order-history sync; runs table from artifacts/live/<run>/config.txt; stop rule and anchored aborts in Rust with tests"
    status: pending
  - id: s5-web
    content: "S5: web pages for dism: Performance (PnL curve, day/run tables, edge/markout, fees, volume), Trade (position, open orders, history, fills on candles), Risk (cap, liquidation, health)"
    status: pending
  - id: s6-supervise
    content: "S6 (later, owner's call): the OEMS supervises the live bot instead of live.sh"
    status: pending
isProject: false
---

# Live strategy in the OEMS (observe first)

## Why now

About 1,800 real-money fills since 20 Oct 2026 sit in run folders, Python reports (`scripts/live_vs_shadow.py`) and ad-hoc scripts. Hourly checks run over SSH. Stage 3 of the size ladder (more capital or a second market) multiplies that. The OEMS already has most of the machinery (`dism` mainnet strategy, Delta fill/position/equity sync, TCA, Performance/Risk/Trade pages, `START REAL` guard); it was verified on the VM on 12 Oct 2026 and switched off.

The temporary dashboard (`~/mm-dash/live_dash.py`, user unit `cex-mm-live-dashboard`, 127.0.0.1:8789) is the reference these slices must match. On 22 Oct 2026 its net PnL (Delta wallet transactions + open position at mark) matched the venue equity change since 20 Oct to $0.002.

## Gaps

| Need | OEMS today | Change |
|---|---|---|
| Realized PnL, fees, funding | Derived from fills (`pnl_snapshots`, `tca_fills`) | Delta's own ledger: `/v2/wallet/transactions` types `cashflow`, `commission`, `funding` (S2) |
| uPnL | Venue position snapshot | Position × mark; mark from the ticker (S2) |
| Slippage / edge, markouts | Against the Delta mid at fill (`sync.rs` `mid_for_fill`), which is mostly our own quote while we quote | Against the bot's anchored fair (`MM_METRICS.fair` = Binance mid × (1 + basis)); Delta-mid columns kept, labelled (S3) |
| Bot telemetry | Only logs of bots the supervisor started | Tail an external log (`artifacts/live/current/bot.log`) (S1) |
| Order history | Open orders every 3 s | `/v2/orders/history` sync (S4) |
| Runs, stop rule, aborts | Not there (`live_vs_shadow.py`, ad-hoc watch script) | Runs table; rules in Rust with tests (S4) |
| Control | Supervisor can start `dism` | Observe-only mode while `live.sh` runs the bot (S1) |

## Design rules

- **Observe only.** A strategy in `observe` mode refuses start, stop, config, cancel-all and close with 409 `observe_only`; the UI shows no control buttons for it. Two bots on one account fight; `live.sh` refuses to start next to any `mm-bot run`, but the OEMS does not check for a bot it did not start.
- **The venue is the truth.** PnL comes from Delta's wallet ledger and position, never from the bot's economics files.
- **Slippage against a price our quotes cannot move.** The 13 Oct run looked profitable against a fair that read our own quotes; it was being picked off.
- No quote math in the OEMS. Parameterized SQL, idempotent writes, bounded list endpoints, no keys in logs or responses (existing `oems` skill rules).
- Delta rate limit: the OEMS shares the bot's key. Polling at the temporary dashboard's rates (account 15 s, fills and transactions 30 s, order history 60 s) is about 100 calls per 5 minutes against a 20,000-weight budget. A read-only monitoring key, if Delta offers one, is better [UNVERIFIED].

## Slices

Each slice is one PR (≤ 5 files plus docs), CI green, the owner's merge. None needs the live bot stopped.

| Slice | Acceptance (command or check) |
|---|---|
| **S0** VM ops | `logrotate` for `artifacts/live/*/bot.log` (copytruncate, daily, keep uncompressed 2 days); `df` flat over 24 h; `live_vs_shadow.py` and the temporary dashboard still read the current run. Disk increase by the owner. |
| **S1** observe + telemetry + install | `POST /api/strategies/dism/start` → 409 `observe_only`; `/api/bot/telemetry?strategy_id=dism` shows the live bot's newest `MM_METRICS` row ≤ 10 s old; `/api/overview` equity = Delta `net_equity` ± $0.01; `pgrep -af 'mm-bot run'` shows only the `live.sh` bot. `cargo test -p mm-oems`. Installing Docker/Postgres on the VM needs the owner's go (sudo). |
| **S2** ledger | Migration `005_wallet_tx`; incremental sync; `/api/performance?strategy_id=dism` returns realized, fees, funding, uPnL, net, volume by day and by run. Net PnL − equity change since 20 Oct within $0.05; per-day PnL equal to the temporary dashboard within $0.01. Unit tests for the ledger fold (buy and sell, flip through zero). |
| **S3** TCA vs fair | Per-second fair stored from telemetry; `mm-oems import-run <dir>` backfills past runs from their logs; edge and 60 s markout (notional-weighted) equal to the temporary dashboard within 0.05 bps on the four runs since 20 Oct. Tests for each formula on a buy and a sell. |
| **S4** orders, runs, rules | Order history stored with state and fills; runs from `config.txt` (build, quote, cap); the stop rule's verdict equals `scripts/live.sh report` on the four runs; the anchored aborts equal the watch script's on the last 2 h. |
| **S5** web | Performance, Trade and Risk pages scoped to `dism`; `npm run typecheck && npm run build`; screenshots at desktop and phone width; every number on screen equals its API field. |
| **S6** supervision (later) | Only after S1–S5 have matched the temporary dashboard and the scripts for 7 days, and on the owner's word: the OEMS starts the live bot; `live.sh` stays as the fallback. |

When S2–S5 match the temporary dashboard for 3 days, it is switched off (`systemctl --user disable --now cex-mm-live-dashboard`).

## Risks

- **VM resources:** 2 vCPU, 1.8 GB RAM, 6.3 GB disk free on 22 Oct; `bot.log` grows about 300 MB a day; Postgres in Docker adds about 2 GB. Hence S0 first and Postgres capped at 128 MB `shared_buffers` (`infra/vm/oems-compose.override.yml`).
- **A second controller:** observe mode, plus the OEMS refusing to start any strategy while an `mm-bot run` it did not start is alive.
- **Misleading TCA:** S3's fair reference is required before the Performance page is trusted.
