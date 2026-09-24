#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export MM_LOG_PATH="${MM_LOG_PATH:-$(pwd)/artifacts/delta-mm-run.log}"
export MM_DASHBOARD_PORT="${MM_DASHBOARD_PORT:-8787}"
echo "Dashboard: http://127.0.0.1:${MM_DASHBOARD_PORT}/"
echo "Tailing: ${MM_LOG_PATH}"
exec python3 dashboard/server.py
