#!/usr/bin/env bash
# Start vanilla GoDark MM bot (Rust / HPKE) — one symbol per process.
# Default: testnet (GODARK_ENV=testnet). Set GODARK_ENV=devnet for devnet.
set -euo pipefail

LAUNCH_SYMBOL="${GODARK_SYMBOL:-${GODARK_DEVNET_SYMBOL:-}}"
LAUNCH_ORDER_QTY="${MM_ORDER_QTY:-}"
LAUNCH_MAX_INVENTORY="${MM_MAX_INVENTORY:-}"
LAUNCH_FAIR_FALLBACK="${MM_FAIR_FALLBACK:-}"

# Symbol must be set before mm-env (selects GODARK_API_KEY_ID_<SLUG>).
if [[ -n "$LAUNCH_SYMBOL" ]]; then
  export GODARK_SYMBOL="$LAUNCH_SYMBOL"
  export GODARK_DEVNET_SYMBOL="$LAUNCH_SYMBOL"
fi

# shellcheck disable=SC1091
source ~/scripts/mms/mm-env.sh

if [[ -z "${MM_ARTIFACTS_DIR:-}" ]]; then
  # shellcheck disable=SC1091
  source ~/scripts/mms/mm-stack-env.sh
fi
# shellcheck disable=SC1091
source ~/scripts/mms/mm-load-tuning.sh

if [[ -n "$LAUNCH_SYMBOL" ]]; then
  export GODARK_SYMBOL="$LAUNCH_SYMBOL"
  export GODARK_DEVNET_SYMBOL="$LAUNCH_SYMBOL"
fi
if [[ -n "$LAUNCH_ORDER_QTY" ]]; then
  export MM_ORDER_QTY="$LAUNCH_ORDER_QTY"
fi
if [[ -n "$LAUNCH_MAX_INVENTORY" ]]; then
  export MM_MAX_INVENTORY="$LAUNCH_MAX_INVENTORY"
fi
if [[ -n "$LAUNCH_FAIR_FALLBACK" ]]; then
  export MM_FAIR_FALLBACK="$LAUNCH_FAIR_FALLBACK"
fi

export MM_ORDER_QTY="${MM_ORDER_QTY:-0.01}"
export MM_LOOP_INTERVAL_SEC="${MM_LOOP_INTERVAL_SEC:-10}"
export RUST_LOG="${RUST_LOG:-vanilla_mm_rust=info,godark=warn}"

SYMBOL="${GODARK_SYMBOL:-${GODARK_DEVNET_SYMBOL:-BTC-USDC-PERP}}"
export GODARK_SYMBOL="$SYMBOL"
export GODARK_DEVNET_SYMBOL="$SYMBOL"

BIN="${HOME}/scripts/mms/vanilla-mm-rust/target/release/vanilla-mm-rust"
cd ~/scripts/mms/vanilla-mm-rust
if [[ -x "$BIN" ]]; then
  exec "$BIN"
else
  exec cargo run --release
fi
