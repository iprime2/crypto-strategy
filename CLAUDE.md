# crypto-strategy

Market making on crypto perpetuals: research and design (`STRATEGY.md`, `resource/`), build plans (`plans/`), and the Rust bot plus operator stack (`cex-mm/`). Current venue: **Delta Exchange India** (demo for live quoting, mainnet public data for the shadow test). Bybit code exists but is not the active venue.

<!-- AGENTS.md and .cursor/ are the Cursor setup. This file, .claude/rules/ and .claude/skills/ are the Claude Code setup. Keep facts in sync when either changes. -->

## Where things live

| Path | What |
|---|---|
| `STRATEGY.md`, `resource/01–06` | Design source of truth (the "why"). Code must not contradict it without updating it. |
| `plans/*.plan.md` | Build plans. Never put plans under `cex-mm/`. |
| `cex-mm/quote-bot/` | `mm-core` (pure quote/risk math), `mm-delta`, `mm-bybit`, `mm-binance` (venue I/O), `mm-bot` (CLI + loop) |
| `cex-mm/backend/mm-oems` | Axum + SQLx OEMS on 127.0.0.1:8791, TimescaleDB on 127.0.0.1:5462. Supervises the live bot. |
| `cex-mm/web` | Vite + React trader UI on 127.0.0.1:5179 (Trade, Performance, Blotter, Risk, Strategy) |
| `cex-mm/dashboard/` | Python dashboards: `server.py` (legacy, 8787), `shadow_server.py` (shadow test on 8788, trend paper trader at `/trend`) |
| `cex-mm/scripts/` | `shadow.sh`, `shadow_fill_sim.py`, `trend_backtest.py`, `trend_paper.py`, `flatten_delta.py`, `fire_drill.sh`, smoke scripts |
| `cex-mm/artifacts/research/` | Dated quant memos `YYYY-MM-DD-<slug>.md`. Read the newest before analysis. |

## Build and verify

WSL has no system `cc`; the zig wrapper is required for every cargo build:

```bash
cd cex-mm && export PATH="$HOME/.local/bin-wrappers:$PATH"
cargo test -p mm-core -p mm-bot -p mm-delta     # targeted
cargo test --workspace --locked                 # what CI runs
cd web && npm run typecheck && npm run build    # if cex-mm/web changed
```

- `target/debug/mm-bot` is the binary the OEMS runs live. A `cargo build` of the debug profile replaces it for the next restart; shadow and ad-hoc runs use `--release`.
- Paste command output as evidence before saying something works.

## Hard rules

- **Never** start, stop, restart, flatten, or cancel orders on the live bot, or run anything with `--env mainnet` that places orders, without the user's explicit go-ahead in this conversation. Read-only checks are fine.
- **Never** read aloud, log, or commit `cex-mm/.env`, `cex-mm/quote-bot/.env`, API keys, or signatures. Keys are Read + Trade only.
- Quotes are **post-only**. Taker orders only for an explicit reduce-only risk exit.
- The venue is the source of truth for position and PnL. `artifacts/economics/*.json` is not (its realized PnL is known to be wrong).
- Mainnet only through `cex-mm/docs/MAINNET_GATE.md` with markout evidence, never on demo PnL.
- Do not spawn subagents unless the user asks. The Cursor flow's "delegate to a Grok engineer" step does not apply to Claude Code.

## Git

- Never commit to `main`. Kept changes go on a `type/short-topic` branch, then a PR, green CI (Rust build and test, web typecheck and build, gitleaks + cargo-audit), a review of the diff, then merge.
- Commit, push, or open a PR only when the user asks. A question or "try it locally" is not a request to commit.
- Do not stage `artifacts/economics/*.json` (the running bot rewrites it) or anything under `artifacts/shadow/`.

## Environment gotchas

- `fstream.binance.com` and other exchange domains do not resolve on this network (ISP DNS block). The Binance reference feed silently returns nothing; use `MM_BINANCE_WS_BASE=wss://data-stream.binance.vision/ws` (public spot mirror). Check `binance_mid` in `MM_METRICS` before trusting any lead signal.
- The WSL clock runs about 1 s behind Delta. Join local data on local receive time, not exchange timestamps.
- Delta India public websocket channel names are `trades` and `ob_l1` (not the documented `all_trades` / `l1_orderbook`). In `trades`, `r="t"` means the buyer was the taker.
- Delta retail fees incl. GST: maker 2.12 bps, taker 5.31 bps. BTCUSD/ETHUSD mainnet spreads are one tick (0.06 / 0.18 bps), so passive quoting there cannot beat fees without a rebate.

## Skills (`.claude/skills/`)

| Skill | Use for |
|---|---|
| `quant-researcher` | PnL attribution, markouts, market selection, shadow-test evaluation, incident checks, memos |
| `lead-engineer` | Any non-trivial code change: plan with acceptance criteria, TDD, review, QA, ship via PR |
| `mm-bot-dev` | Changing the Rust bot (`mm-core` math, venue adapters, `mm-bot` loop) |
| `mm-ops` | Running things: live demo bot via OEMS, dry-run, shadow test, dashboards, cancel-all, flatten |
| `oems` | OEMS backend (API, schema, TCA, supervisor, Delta snapshot) and the web UI |

Path-scoped rules in `.claude/rules/` load automatically for `cex-mm/**` and for the research docs.
