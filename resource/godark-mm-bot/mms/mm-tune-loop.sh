#!/usr/bin/env bash
# Monitor MM bot logs, auto-tune params, restart bots when eval recommends changes.
# Supports multiple symbols via MM_SYMBOLS (one process per symbol).
set -euo pipefail

# shellcheck disable=SC1091
source "${HOME}/scripts/mms/mm-stack-env.sh"

INTERVAL_SEC="${MM_TUNE_INTERVAL_SEC:-120}"
TUNE_LOG="${LOG_DIR}/mm-tune.log"
TUNE_PID_FILE="${LOG_DIR}/mm-tune.pid"
MM_SYMBOLS="${MM_SYMBOLS:-BTC-USDC-PERP,ETH-USDC-PERP,SOL-USDC-PERP}"

mkdir -p "$LOG_DIR"
echo $$ >"$TUNE_PID_FILE"

log() {
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" | tee -a "$TUNE_LOG"
}

symbol_slug() {
  echo "${1%%-*}"
}

default_order_qty() {
  case "$1" in
    BTC-USDC-PERP) echo "${MM_ORDER_QTY_BTC:-0.005}" ;;
    ETH-USDC-PERP) echo "${MM_ORDER_QTY_ETH:-0.05}" ;;
    SOL-USDC-PERP) echo "${MM_ORDER_QTY_SOL:-0.5}" ;;
    *) echo "${MM_ORDER_QTY:-0.01}" ;;
  esac
}

default_max_inventory() {
  case "$1" in
    BTC-USDC-PERP) echo "${MM_MAX_INVENTORY_BTC:-0.05}" ;;
    ETH-USDC-PERP) echo "${MM_MAX_INVENTORY_ETH:-0.5}" ;;
    SOL-USDC-PERP) echo "${MM_MAX_INVENTORY_SOL:-5.0}" ;;
    *) echo "${MM_MAX_INVENTORY:-0.05}" ;;
  esac
}

default_fair_fallback() {
  case "$1" in
    BTC-USDC-PERP) echo "${MM_FAIR_FALLBACK_BTC:-64000}" ;;
    ETH-USDC-PERP) echo "${MM_FAIR_FALLBACK_ETH:-3500}" ;;
    SOL-USDC-PERP) echo "${MM_FAIR_FALLBACK_SOL:-150}" ;;
    *) echo "${MM_FAIR_FALLBACK:-64000}" ;;
  esac
}

default_loop_offset() {
  case "$1" in
    BTC-USDC-PERP) echo "${MM_LOOP_OFFSET_BTC:-0}" ;;
    ETH-USDC-PERP) echo "${MM_LOOP_OFFSET_ETH:-3}" ;;
    SOL-USDC-PERP) echo "${MM_LOOP_OFFSET_SOL:-6}" ;;
    *) echo "0" ;;
  esac
}

read_symbols() {
  echo "$MM_SYMBOLS" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | grep -v '^$'
}

pid_file_for() {
  echo "${LOG_DIR}/mm-bot-$(symbol_slug "$1").pid"
}

log_file_for() {
  echo "${LOG_DIR}/mm-bot-$(symbol_slug "$1").log"
}

stop_symbol_bot() {
  local symbol="$1"
  local pid_file
  pid_file="$(pid_file_for "$symbol")"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
  fi
}

start_symbol_bot() {
  local symbol="$1"
  local slug pid_file bot_log qty max_inv fair_fb loop_offset
  slug="$(symbol_slug "$symbol")"
  pid_file="$(pid_file_for "$symbol")"
  bot_log="$(log_file_for "$symbol")"
  qty="$(default_order_qty "$symbol")"
  max_inv="$(default_max_inventory "$symbol")"
  fair_fb="$(default_fair_fallback "$symbol")"
  loop_offset="$(default_loop_offset "$symbol")"

  stop_symbol_bot "$symbol"

  MM_STACK="$MM_STACK" \
  MM_ARTIFACTS_DIR="$LOG_DIR" \
  GODARK_ENV="$GODARK_ENV" \
  GODARK_DEVNET_SYMBOL="$symbol" \
  GODARK_SYMBOL="$symbol" \
  MM_ORDER_QTY="$qty" \
  MM_MAX_INVENTORY="$max_inv" \
  MM_FAIR_FALLBACK="$fair_fb" \
  MM_LOOP_OFFSET_SEC="$loop_offset" \
  MM_BOT_LOG="$bot_log" \
  setsid nohup bash "${HOME}/scripts/mms/run-vanilla-mm.sh" >>"$bot_log" 2>&1 &

  echo $! >"$pid_file"
  log "bot started symbol=$symbol slug=$slug pid=$(cat "$pid_file") qty=$qty max_inv=$max_inv log=$bot_log"
}

restart_all_bots() {
  log "restarting all bots: $MM_SYMBOLS"
  local n=0
  while IFS= read -r symbol; do
    start_symbol_bot "$symbol"
    n=$((n + 1))
    # Stagger auth/connect (helps even with per-symbol API keys).
    if [[ "$n" -lt 3 ]]; then
      sleep 8
    fi
  done < <(read_symbols)
}

ensure_symbol_bot() {
  local symbol="$1"
  local pid_file
  pid_file="$(pid_file_for "$symbol")"
  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    return 0
  fi
  log "bot not running for $symbol — starting"
  start_symbol_bot "$symbol"
}

ensure_all_bots() {
  while IFS= read -r symbol; do
    ensure_symbol_bot "$symbol"
  done < <(read_symbols)
}

# Detect real auth token expiry only — NOT "loop":1401 in MM_METRICS or order_ids
# containing the digits 1401.
token_expired_in_logs() {
  local symbol bot_log
  for symbol in $(read_symbols); do
    bot_log="$(log_file_for "$symbol")"
    if [[ -f "$bot_log" ]] && tail -100 "$bot_log" | rg -v 'MM_METRICS' | rg -q \
      'REST code=1401|Invalid or expired token|auth token expired'; then
      log "token expiry detected in $bot_log"
      return 0
    fi
  done
  return 1
}

export MM_TUNING_ENV MM_REPORT_DIR
log "mm-tune-loop started stack=${MM_STACK} env=${GODARK_ENV} interval=${INTERVAL_SEC}s tuning=${MM_TUNING_ENV} symbols=$MM_SYMBOLS"
ensure_all_bots

while true; do
  sleep "$INTERVAL_SEC"
  ensure_all_bots

  if token_expired_in_logs; then
    log "restarting all bots after token expiry"
    restart_all_bots
    continue
  fi

  restart_needed=0

  while IFS= read -r symbol; do
    bot_log="$(log_file_for "$symbol")"
    set +e
    out="$(MM_STACK="$MM_STACK" MM_ARTIFACTS_DIR="$LOG_DIR" MM_BOT_LOG="$bot_log" MM_TUNING_ENV="$MM_TUNING_ENV" MM_REPORT_DIR="$MM_REPORT_DIR" python3 "${HOME}/scripts/mms/mm-eval.py" --symbol "$symbol" 2>&1)"
    rc=$?
    set -e
    log "[$symbol] $out"
    if [[ "$rc" -eq 2 ]]; then
      restart_needed=1
    fi
  done < <(read_symbols)

  set +e
  dash_out="$(python3 "${HOME}/scripts/mms/mm-dashboard.py" 2>&1)"
  set -e
  log "dashboard $dash_out"

  if [[ "$restart_needed" -eq 1 ]]; then
    restart_all_bots
  fi
done
