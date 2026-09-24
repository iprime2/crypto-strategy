# cex-mm — CEX USDT-perp market maker (Rust)

Bybit-first testnet bot with GoDark-derived quote engine plus research extensions (OFI, regime, funding, Binance lead). See [../STRATEGY.md](../STRATEGY.md) and the build plan [../plans/cex_mm_rust_bot.plan.md](../plans/cex_mm_rust_bot.plan.md). Agent rules/skills: [../AGENTS.md](../AGENTS.md).

## Workspace

| Crate | Role |
|-------|------|
| `mm-core` | Quote engine, markout guard, OFI/regime/economics |
| `mm-bybit` | Bybit REST/WS adapter (testnet/mainnet) |
| `mm-delta` | Delta Exchange India REST/WS (demo + mainnet) |
| `mm-binance` | Public `bookTicker` reference fair |
| `mm-bot` | CLI: `record`, `dry-run`, `run`, `cancel-all` |

## Setup (WSL)

```bash
cd crypto-strategy/cex-mm
cp config/example.env .env   # fill BYBIT_* testnet keys
export PATH="$HOME/.local/bin-wrappers:$PATH"   # if no system gcc: zig cc wrappers
cargo test -p mm-core
cargo build -p mm-bot
```

### WSL HTTPS / VPN (Bybit curl times out)

If **Windows** reaches Bybit but **WSL** hangs on `curl https://…` (TCP `:443` OK, TLS Client Hello never answered), WSL’s default NAT stack is often incompatible with a host VPN (e.g. Surfshark).

**Fix (recommended):** mirrored networking — `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
networkingMode=mirrored
dnsTunneling=true
```

Then from **Windows** (not inside WSL): `wsl --shutdown`, reopen WSL, and retry:

```bash
curl -sS -m 15 "https://api-testnet.bybit.com/v5/market/time"
```

**Verify:** `./scripts/smoke_testnet_order.sh` (needs `.env` testnet keys).

**If still broken:** temporarily disconnect VPN to confirm; in the VPN app enable LAN/local bypass; or lower MTU in WSL (`sudo ip link set dev eth0 mtu 1350`) for classic VPN MTU black holes.

**Workaround only:** `/mnt/c/Windows/System32/curl.exe …` uses Windows networking; the Rust bot still needs WSL HTTPS fixed for `cargo run`.

## Commands

```bash
# Slice 1 — record public WS with local timestamps
cargo run -p mm-bot -- record --symbol BTCUSDT --duration 3600

# Top N liquid USDT perps (ranked by 24h turnover on Bybit at startup)
export MM_TOP_N=10
cargo run -p mm-bot -- universe --env testnet   # preview list
cargo run -p mm-bot -- run --env testnet

# Pin BTC, fill remaining 9 by liquidity:
# MM_SYMBOLS=BTCUSDT MM_TOP_N=10

# Multiple symbols (manual list)
export MM_SYMBOLS=BTCUSDT,ETHUSDT,SOLUSDT
cargo run -p mm-bot -- run --env testnet
cargo run -p mm-bot -- dry-run --symbols BTCUSDT,ETHUSDT --env testnet
cargo run -p mm-bot -- record --symbols BTCUSDT,ETHUSDT --duration 3600

# Dry-run quotes (no keys)
cargo run -p mm-bot -- dry-run --symbol BTCUSDT --env testnet

# Testnet live (keys required)
cargo run -p mm-bot -- run --symbol BTCUSDT --env testnet

# Delta India demo (same mm-core logic; keys from testnet.delta.exchange)
export MM_VENUE=delta
export DELTA_API_KEY=... DELTA_API_SECRET=...
cargo run -p mm-bot -- dry-run --venue delta --env testnet --symbols BTCUSDT,ETHUSDT,SOLUSDT
cargo run -p mm-bot -- run --venue delta --env testnet --symbols BTCUSDT
cargo run -p mm-bot -- cancel-all --venue delta --env testnet --symbol BTCUSDT
./scripts/smoke_delta_demo.sh

# Kill switch helper
cargo run -p mm-bot -- cancel-all --env testnet
cargo run -p mm-bot -- cancel-all --all --env testnet   # all MM_SYMBOLS
./scripts/fire_drill.sh
```

Each symbol runs its own book/Binance feed and quote loop in one process; one private execution WS routes fills by symbol. Economics persist under `artifacts/economics/{SYMBOL}.json`. Watch Bybit order rate limits when quoting many pairs (default ~7 ops/s per symbol).

Structured metrics: log lines with target `MM_METRICS` (JSON).

### Live dashboard (benchmark telemetry)

Tails the bot log and charts fair vs **Binance** mid, spread, inventory, markout, regime, and economics. Plain-language term definitions: [docs/DASHBOARD-GLOSSARY.md](docs/DASHBOARD-GLOSSARY.md).

```bash
# Bot should log with MM_METRICS enabled, e.g.:
# RUST_LOG=info,mm_bot=info,MM_METRICS=info
./scripts/run_dashboard.sh
# open http://127.0.0.1:8787/
```

Set `MM_LOG_PATH` if the bot writes elsewhere (default `artifacts/delta-mm-run.log`).

## Tests

```bash
cargo test -p mm-core -p mm-bot
cargo test -p mm-bybit -- --ignored   # with .env testnet keys
```

## Backtest / mainnet gate

- [artifacts/backtest/README.md](artifacts/backtest/README.md) — hftbacktest 2.4.4 pipeline (Slice 7/7b)
- [docs/MAINNET_GATE.md](docs/MAINNET_GATE.md) — promotion checklist (Slice 8)

## Secrets

Never commit `.env`. API keys: **Read + Trade** only; no withdraw.
