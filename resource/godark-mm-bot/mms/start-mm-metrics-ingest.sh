#!/usr/bin/env bash
# Optional sidecar: poll bot logs → MM TimescaleDB (mm_ops).
set -euo pipefail

# shellcheck disable=SC1091
source "${HOME}/scripts/source-secrets.sh" 2>/dev/null || true
# shellcheck disable=SC1091
source "${HOME}/scripts/mms/mm-db-env.sh"

INTERVAL="${MM_METRICS_INGEST_INTERVAL_SEC:-60}"
PID_FILE="${HOME}/scripts/mms/artifacts/mm-metrics-ingest.pid"
LOG_FILE="${HOME}/scripts/mms/artifacts/mm-metrics-ingest.log"

mkdir -p "$(dirname "$PID_FILE")"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "MM metrics ingest already running pid=$(cat "$PID_FILE")"
  exit 0
fi

if ! docker ps --format '{{.Names}}' | grep -qx 'mm-strategy-timescale'; then
  echo "Start Timescale first: bash ~/scripts/mms/start-mm-db.sh"
  exit 1
fi

(
  while true; do
    python3 "${HOME}/scripts/mms/mm-metrics-ingest.py" --once --stack both >>"$LOG_FILE" 2>&1 || true
    sleep "$INTERVAL"
  done
) &
echo $! >"$PID_FILE"
echo "MM metrics ingest started pid=$(cat "$PID_FILE") interval=${INTERVAL}s log=$LOG_FILE"
