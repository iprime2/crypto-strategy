#!/usr/bin/env bash
# Cancel open Delta orders whose client_order_id starts with "smoke-" (smoke test only).
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then set -a; source .env; set +a; fi
export MM_ENV="${MM_ENV:-testnet}"
export MM_SYMBOL="${MM_SYMBOL:-BTCUSDT}"
exec cargo run -q -p mm-delta --example cancel_smoke_orders
