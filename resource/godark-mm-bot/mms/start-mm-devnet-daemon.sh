#!/usr/bin/env bash
# Start devnet MM daemon (parallel to testnet — separate logs/PIDs under artifacts/devnet/).
#
# Usage:
#   bash ~/scripts/mms/start-mm-devnet-daemon.sh
#   bash ~/scripts/mms/stop-mm-devnet-daemon.sh
export MM_STACK=devnet
export GODARK_ENV=devnet
exec bash "${HOME}/scripts/mms/start-mm-daemon.sh"
