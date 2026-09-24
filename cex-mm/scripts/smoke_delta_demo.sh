#!/usr/bin/env bash
# Delta India demo: dry-run quotes (public book + Binance lead), no orders.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="${HOME}/.local/bin-wrappers:${PATH}"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
export MM_VENUE="${MM_VENUE:-delta}"
export MM_SYMBOLS="${MM_SYMBOLS:-BTCUSDT}"
export RUST_LOG="${RUST_LOG:-info,mm_bot=info,MM_METRICS=info}"
echo "Delta demo dry-run (MM_VENUE=$MM_VENUE, env=testnet -> demo API)..."
timeout 45 cargo run -p mm-bot -- dry-run --venue delta --env testnet --symbols "${MM_SYMBOLS}" --loop-ms 500 2>&1 | head -40
echo "If you see MM_METRICS lines above, book + quote loop OK."
echo "Live demo orders: set DELTA_API_KEY/SECRET from testnet.delta.exchange demo account, then:"
echo "  cargo run -p mm-bot -- run --venue delta --env testnet --symbols BTCUSDT"
