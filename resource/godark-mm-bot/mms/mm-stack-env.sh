#!/usr/bin/env bash
# MM stack isolation: testnet and devnet daemons run in parallel (separate PIDs/logs).
#
#   MM_STACK=testnet  → ~/scripts/mms/artifacts/          (default)
#   MM_STACK=devnet   → ~/scripts/mms/artifacts/devnet/
#
# Start/stop:
#   bash ~/scripts/mms/start-mm-daemon.sh
#   MM_STACK=devnet bash ~/scripts/mms/start-mm-devnet-daemon.sh
set -euo pipefail

MM_STACK="${MM_STACK:-testnet}"
case "$MM_STACK" in
  devnet)
    export GODARK_ENV=devnet
    export MM_ARTIFACTS_DIR="${MM_ARTIFACTS_DIR:-${HOME}/scripts/mms/artifacts/devnet}"
    ;;
  testnet)
    export GODARK_ENV=testnet
    export MM_ARTIFACTS_DIR="${MM_ARTIFACTS_DIR:-${HOME}/scripts/mms/artifacts}"
    ;;
  *)
    echo "mm-stack-env: unknown MM_STACK=$MM_STACK (use testnet or devnet)" >&2
    return 1 2>/dev/null || exit 1
    ;;
esac

export MM_STACK
export LOG_DIR="$MM_ARTIFACTS_DIR"
mkdir -p "$LOG_DIR"

# Per-stack tuning (eval writes MM_TUNING_ENV; devnet also loads mm-tuning-devnet.env at bot start)
export MM_TUNING_BASE="${MM_TUNING_BASE:-${HOME}/scripts/mms/mm-tuning.env}"
export MM_TUNING_ENV="${MM_TUNING_ENV:-${MM_ARTIFACTS_DIR}/mm-tuning.env}"
export MM_REPORT_DIR="${MM_REPORT_DIR:-${MM_ARTIFACTS_DIR}/mm-metrics}"
if [[ "$MM_STACK" == "devnet" ]]; then
  export MM_TUNING_OVERLAY="${MM_TUNING_OVERLAY:-${HOME}/scripts/mms/mm-tuning-devnet.env}"
elif [[ "$MM_STACK" == "testnet" ]]; then
  export MM_TUNING_OVERLAY="${MM_TUNING_OVERLAY:-${HOME}/scripts/mms/mm-tuning-testnet.env}"
fi

if [[ ! -f "$MM_TUNING_ENV" ]] && [[ -f "$MM_TUNING_BASE" ]]; then
  cp -a "$MM_TUNING_BASE" "$MM_TUNING_ENV"
fi
mkdir -p "$MM_REPORT_DIR"
