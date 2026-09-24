#!/usr/bin/env bash
# Serve MM fill-rate / markout dashboard over HTTP (browser access).
set -euo pipefail

LOG_DIR="${HOME}/scripts/mms/artifacts"
PID_FILE="${LOG_DIR}/mm-dashboard.pid"
PORT="${MM_DASHBOARD_PORT:-8799}"
HOST="${MM_DASHBOARD_HOST:-0.0.0.0}"

mkdir -p "$LOG_DIR"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "MM dashboard already running pid=$(cat "$PID_FILE") port=$PORT"
  exit 0
fi

setsid nohup python3 "${HOME}/scripts/mms/mm-dashboard-serve.py" \
  --host "$HOST" --port "$PORT" >>"${LOG_DIR}/mm-dashboard-serve.log" 2>&1 &
echo $! >"$PID_FILE"

echo "MM dashboard started pid=$(cat "$PID_FILE")"
echo "  URL: http://127.0.0.1:${PORT}/  (tabs: Testnet | Devnet)"
echo "  devnet deep-link: http://127.0.0.1:${PORT}/#devnet"
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
if [[ -n "$LAN_IP" ]]; then
  echo "  LAN: http://${LAN_IP}:${PORT}/"
fi
echo "  log: ${LOG_DIR}/mm-dashboard-serve.log"
