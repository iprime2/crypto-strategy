#!/usr/bin/env bash
set -euo pipefail
PID_FILE="${HOME}/scripts/mms/artifacts/mm-metrics-ingest.pid"
if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    echo "stopped MM metrics ingest pid=$pid"
  fi
  rm -f "$PID_FILE"
else
  echo "MM metrics ingest not running"
fi
