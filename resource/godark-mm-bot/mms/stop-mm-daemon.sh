#!/usr/bin/env bash
# Stop MM daemon, tune loop, and symbol bots for one stack (testnet or devnet).
# Does not touch the other stack's processes.
set -euo pipefail

# shellcheck disable=SC1091
source "${HOME}/scripts/mms/mm-stack-env.sh"

DAEMON_PID_FILE="${LOG_DIR}/mm-daemon.pid"
TUNE_PID_FILE="${LOG_DIR}/mm-tune.pid"

stop_pid_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$file"
  fi
}

stop_pid_file "$DAEMON_PID_FILE"
stop_pid_file "$TUNE_PID_FILE"

for f in "${LOG_DIR}"/mm-bot-*.pid; do
  [[ -e "$f" ]] || continue
  stop_pid_file "$f"
done
stop_pid_file "${LOG_DIR}/mm-bot.pid"

echo "MM daemon stopped (stack=${MM_STACK} artifacts=${LOG_DIR})"
