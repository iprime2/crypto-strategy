#!/usr/bin/env bash
# Place one far-off post-only limit on Delta India demo, then cancel (IP whitelist + keys check).
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="${HOME}/.local/bin-wrappers:${PATH}"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
export MM_ENV="${MM_ENV:-testnet}"
export MM_SYMBOL="${MM_SYMBOL:-BTCUSDT}"
echo "Delta demo order smoke (MM_SYMBOL=$MM_SYMBOL, MM_ENV=$MM_ENV)..."
cargo run -q -p mm-delta --example smoke_order
