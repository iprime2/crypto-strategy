---
name: oems
description: >-
  Build or change the cex-mm OEMS: the Axum + SQLx backend (mm-oems) with its
  HTTP contract, Postgres/Timescale schema, TCA formulas, Delta wallet and
  position snapshot, and bot process supervisor; and the Vite + React +
  Tailwind operator UI in cex-mm/web. Use when editing cex-mm/backend or
  cex-mm/web.
paths:
  - "cex-mm/backend/**"
  - "cex-mm/web/**"
---

# OEMS (backend + web)

The OEMS is the book of record and the supervisor of the live bot. Quote math never lives here.

## Backend (`cex-mm/backend/mm-oems`)

- Axum + Tokio + SQLx + Postgres/TimescaleDB. Binds 127.0.0.1:8791. DB at 127.0.0.1:5462 (`backend/docker-compose.yml`). Migrations in the crate; schema changes only through a new migration.
- Handlers stay thin. TCA math, reconcile rules and snapshot mapping live in modules with unit tests (`tca.rs`, `analytics.rs`, `snapshot.rs`, `supervisor.rs`).
- Parameterized SQL. Idempotent writes: orders on `(strategy_id, client_order_id)`, fills on `(strategy_id, trade_id)`; a conflict updates, it never duplicates.
- Every stored row carries `strategy_id`. List endpoints take a bounded `limit`.
- Never log or return API keys. Config endpoints reject secret fields.

### Routes (`api.rs`)

- Read: `/api/overview` (header strip: status, balance, day PnL, venue/telemetry health), `/api/performance` (daily, by symbol, net-edge curve), `/api/fills`, `/api/tca`, `/api/venue/orders`, `/api/venue/status`, `/api/bot/telemetry`, `/api/ticks`, `/api/market/{symbol}/{ticker|book|trades|candles}`, `/api/strategies/{id}/effective-config`, plus the older `/api/snapshots/latest`, `/api/pnl`, `/api/positions`, `/api/reconcile`, `/api/analytics`. All take `strategy_id` (default `mm`); venue, market, telemetry and ticks answer from that strategy's environment.
- Control (require the `X-OEMS-Client` header; CORS only allows the web origin): `/api/strategies/{id}/start|stop|config|cancel-all`, `/api/positions/{symbol}/close` (body `{confirm: SYMBOL, strategy_id}`, refused while the bot runs).
- Real money: starting a `mainnet` strategy needs the OEMS started with `OEMS_ALLOW_MAINNET=1` (else 403 `mainnet_disabled`) and body `{confirm: "START REAL"}` (else 400 `confirm_required`). A config change to a running real-money strategy is saved with `restart_required: true` and never restarts it.
- Bot events (`/api/events/orders|fills`) are optional now: fills come from the venue sync.

Contract rules: define the JSON shape first, then the handler, then the TypeScript type in the same change. Errors share one body `{code, message}`. Never rename a response field without updating the client in the same PR.

### Strategies and environments

- `strategies.env` is `demo` or `mainnet`; `strategies.profile` is an optional settings file under `cex-mm/` (migration 004). Seeded: `mm` (demo, no profile) and `dism` (mainnet, `config/dism.env`).
- `runtime.rs` gives each strategy its own market proxy (one per environment), venue state and telemetry; `main.rs` runs sync, snapshot and log tailing per strategy. `ticks` rows carry `env`.
- Keys per environment from `quote-bot/.env`: demo `DELTA_API_KEY/SECRET`, mainnet `DELTA_MAINNET_API_KEY/SECRET` (`DeltaClient::from_env_pairs_for`); never the other environment's. Without keys a strategy only records public ticks.

### Supervisor

- Starts `target/debug/mm-bot run --venue delta --env <testnet|mainnet>` with `env_clear()`. Env (`bot_env_pairs`, later wins): no profile = `quote-bot/.env` minus the other environment's keys, then config overrides; with a profile = only this environment's keys and `RUST_LOG` from `quote-bot/.env`, then the profile, then config overrides (the demo bot's `MM_*` lines never leak into a profile strategy). Config keys map to `MM_*` names (`symbols` → `MM_SYMBOLS`); other keys are ignored.
- Refuses to start without the environment's keys (`missing_keys`) or a missing profile (`missing_profile`).
- Bot stdout/stderr go to `artifacts/logs/mm-bot-<strategy>-<utc>.log`; `telemetry.rs` tails it for `MM_METRICS` and events.
- Each child is reaped by a waiting thread; `pid_alive` treats zombies as dead. On OEMS start, a still-running `mm-bot run` whose pid is in the DB is adopted.
- Stop = SIGTERM, wait up to 5 s, SIGKILL, then cancel its orders at Delta. Positions are left open.

### Venue sync (`sync.rs`)

Open orders every 3 s, fills every 5 s (full history backfilled on first run, stored with role and fee), ticker per active symbol every 2 s into `ticks`. Markouts at 1/5/30/60 s are measured on each fill's own symbol's ticks for 30 minutes after the fill.

### Delta snapshot

Poll `/v2/wallet/balances` and `/v2/positions/margined` about every 10 s per strategy, with that strategy's environment keys from `quote-bot/.env`. Position base = contracts × `contract_value`; positive size is long. Bot size comes from fresh telemetry (`MM_METRICS.inventory`) and is null when unknown. A position that disappears gets a zero row so the UI does not show stale size. The venue number is what the UI shows as truth. The snapshot loop never places or cancels orders.

### TCA formulas (computed in Rust when the fill is stored)

`side` = +1 buy, −1 sell; bps = ratio × 10,000.
- Slippage = side × (fill − arrival_mid) / arrival_mid
- Quoted half-spread = distance from arrival mid to our limit price
- Effective spread = 2 × side × (fill − mid_at_fill) / mid_at_fill (uses the mid **at the fill**)
- Markout(τ) at 1 s / 5 s / 30 s = side × (mid_after − arrival_mid) / arrival_mid
- Net at 5 s = effective spread − fee bps − adverse part of the 5 s markout; null (not zero) when the 5 s mid is missing

Test a buy and a sell for each formula.

### Verify

```bash
cd cex-mm && export PATH="$HOME/.local/bin-wrappers:$PATH" && cargo test -p mm-oems
```

## Web (`cex-mm/web`)

- Vite + React + Tailwind, dev server 127.0.0.1:5179. Pages: Trade (candles via `lightweight-charts`, order book, tape, quote panel, position, blotter), Performance, Blotter, Risk, Strategy. Shell: `components/AppShell.tsx`; data via `hooks/usePoll.ts` and `context/AppContext.tsx`.
- Every control action goes through `components/ConfirmDialog.tsx` (typed confirmation for closing a position). Status is never color alone (dot + symbol + words).
- `lightweight-charts` cannot parse `oklch()`; resolve theme colors with `toRgb` in `CandleChart.tsx`.
- No PnL or TCA math in the browser beyond display; the OEMS computes it.
- Running `npm install` while the dev server runs can crash it; restart `npm run dev` afterwards.

```bash
cd cex-mm/web && npm run typecheck && npm run build
```

Then exercise the changed screen in a browser against the local OEMS.
