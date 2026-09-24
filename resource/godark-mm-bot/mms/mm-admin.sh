#!/usr/bin/env bash
# GoDark MM admin — snapshot account PnL or cancel all working orders.
#
# Usage:
#   bash ~/scripts/mms/mm-admin.sh snapshot
#   GODARK_SYMBOL=ETH-USDC-PERP bash ~/scripts/mms/mm-admin.sh snapshot
#   bash ~/scripts/mms/mm-admin.sh cancel-all
set -euo pipefail

CMD="${1:-snapshot}"
LAUNCH_SYMBOL="${GODARK_SYMBOL:-${GODARK_DEVNET_SYMBOL:-BTC-USDC-PERP}}"
LAUNCH_ORDER_QTY="${MM_ORDER_QTY:-}"
LAUNCH_MAX_INVENTORY="${MM_MAX_INVENTORY:-}"
LAUNCH_FAIR_FALLBACK="${MM_FAIR_FALLBACK:-}"

if [[ -n "$LAUNCH_SYMBOL" ]]; then
  export GODARK_SYMBOL="$LAUNCH_SYMBOL"
  export GODARK_DEVNET_SYMBOL="$LAUNCH_SYMBOL"
fi

# shellcheck disable=SC1091
source ~/scripts/mms/mm-env.sh
if [[ -n "$LAUNCH_ORDER_QTY" ]]; then export MM_ORDER_QTY="$LAUNCH_ORDER_QTY"; fi
if [[ -n "$LAUNCH_MAX_INVENTORY" ]]; then export MM_MAX_INVENTORY="$LAUNCH_MAX_INVENTORY"; fi
if [[ -n "$LAUNCH_FAIR_FALLBACK" ]]; then export MM_FAIR_FALLBACK="$LAUNCH_FAIR_FALLBACK"; fi

BIN="${HOME}/scripts/mms/vanilla-mm-rust/target/release/mm-admin"
cd ~/scripts/mms/vanilla-mm-rust
if [[ ! -x "$BIN" ]]; then
  cargo build --release --bin mm-admin
fi
exec "$BIN" "$CMD"
