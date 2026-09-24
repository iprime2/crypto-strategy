#!/usr/bin/env bash
set -euo pipefail
PID_FILE="${HOME}/scripts/mms/artifacts/mm-dashboard.pid"
if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
fi
pkill -f 'mm-dashboard-serve.py' 2>/dev/null || true
echo "MM dashboard stopped"
