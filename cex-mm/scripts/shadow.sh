#!/usr/bin/env bash
# Shadow test: run the quote engine in dry-run on Delta India MAINNET data and record the
# public trade tape, so fills can be simulated later with scripts/shadow_fill_sim.py.
# No API keys are passed and no orders can be placed.
#
#   scripts/shadow.sh start [SYMBOLS]   # default ADAUSDT,NEARUSDT
#   scripts/shadow.sh status
#   scripts/shadow.sh report [sim args] # e.g. --sweep 3,4,5,6,8 --latencies 0,300,1000
#   scripts/shadow.sh stop
#   scripts/shadow.sh dashboard         # http://127.0.0.1:8788/ (dashboard/shadow_server.py)
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
SHADOW="$ROOT/artifacts/shadow"
CURRENT="$SHADOW/current"
BIN="$ROOT/target/release/mm-bot"

# Quote settings under test (see artifacts/research/2026-09-29-quant-review-edge-decomposition.md).
SHADOW_ENV=(
  MM_VENUE=delta
  MM_MIN_HALF_SPREAD_BPS=4
  MM_MAX_HALF_SPREAD_BPS=6
  MM_HALF_SPREAD_BPS=4
  MM_MAKER_FEE_BPS=2.12
  MM_ADVERSE_BUFFER_BPS=0
  MM_OFI_BETA=0.01
  MM_WARMUP_SAMPLES=32
  # L1 size imbalance is not a crash signal (same as the live demo config).
  MM_REGIME_L3_DEPTH_RATIO=0
  # fstream.binance.com does not resolve from this network; use the public market-data mirror.
  MM_BINANCE_WS_BASE=wss://data-stream.binance.vision/ws
  # Delta top of book from the public ob_l1 websocket (~100 ms) instead of 250 ms REST polling.
  MM_DELTA_BOOK_FEED=ws
  RUST_LOG=warn,mm_bot=info,MM_METRICS=info
  NO_COLOR=1
)

pid_alive() { [[ -f "$1" ]] && kill -0 "$(cat "$1")" 2>/dev/null; }

start() {
  local symbols="${1:-ADAUSDT,NEARUSDT}"
  if pid_alive "$CURRENT/dry-run.pid" || pid_alive "$CURRENT/recorder.pid"; then
    echo "shadow test already running in $(readlink -f "$CURRENT"); stop it first" >&2
    exit 1
  fi
  PATH="$HOME/.local/bin-wrappers:$PATH" cargo build --release -q -p mm-bot
  local run="$SHADOW/$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$run"
  ln -sfn "$run" "$CURRENT"
  {
    echo "symbols=$symbols"
    echo "started_utc=$(date -u +%FT%TZ)"
    echo "git=$(git rev-parse --short HEAD) $(git status --porcelain | wc -l) uncommitted"
    printf '%s\n' "${SHADOW_ENV[@]}"
  } >"$run/config.txt"

  # env -i: no DELTA_API_KEY, no MM_OEMS_URL, nothing from the live bot's environment.
  setsid nohup env -i HOME="$HOME" PATH="/usr/bin:/bin" "${SHADOW_ENV[@]}" \
    "$BIN" dry-run --venue delta --env mainnet --symbols "$symbols" --loop-ms 400 \
    >"$run/dry-run.log" 2>&1 </dev/null &
  echo $! >"$run/dry-run.pid"
  setsid nohup env -i HOME="$HOME" PATH="/usr/bin:/bin" RUST_LOG=info NO_COLOR=1 \
    "$BIN" record-delta --symbols "$symbols" --env mainnet --out-dir "$run" --channels trades \
    >"$run/recorder.log" 2>&1 </dev/null &
  echo $! >"$run/recorder.pid"
  sleep 3
  status
}

stop() {
  for name in dry-run recorder; do
    local pidf="$CURRENT/$name.pid"
    if pid_alive "$pidf"; then
      kill "$(cat "$pidf")" && echo "stopped $name ($(cat "$pidf"))"
    fi
  done
}

status() {
  if [[ ! -e "$CURRENT" ]]; then
    echo "no shadow run yet"
    return
  fi
  echo "run: $(readlink -f "$CURRENT")"
  sed -n '1,3p' "$CURRENT/config.txt"
  for name in dry-run recorder; do
    if pid_alive "$CURRENT/$name.pid"; then
      echo "$name: running (pid $(cat "$CURRENT/$name.pid"))"
    else
      echo "$name: NOT running"
    fi
  done
  local metrics trades
  metrics=$(grep -c MM_METRICS "$CURRENT/dry-run.log" 2>/dev/null || true)
  trades=$(cat "$CURRENT"/delta_mainnet_public_*.jsonl 2>/dev/null | grep -c '"type":"trades"' || true)
  echo "quote samples: ${metrics:-0}   recorded trades: ${trades:-0}"
  echo "disk: $(du -sh "$CURRENT/" | cut -f1)"
  echo "last quote: $(grep MM_METRICS "$CURRENT/dry-run.log" 2>/dev/null | tail -1 | cut -c1-27)"
  grep -E "WARN|ERROR" "$CURRENT/dry-run.log" "$CURRENT/recorder.log" 2>/dev/null | tail -3 || true
}

dashboard() {
  local pidf="$SHADOW/dashboard.pid"
  if pid_alive "$pidf"; then
    echo "dashboard already running (pid $(cat "$pidf")): http://127.0.0.1:8788/"
    return
  fi
  mkdir -p "$SHADOW"
  setsid nohup python3 "$ROOT/dashboard/shadow_server.py" --port 8788 \
    >"$SHADOW/dashboard.log" 2>&1 </dev/null &
  echo $! >"$pidf"
  echo "dashboard started (pid $!): http://127.0.0.1:8788/"
}

report() {
  python3 "$ROOT/scripts/shadow_fill_sim.py" --run-dir "$(readlink -f "$CURRENT")" "$@"
}

case "${1:-status}" in
  start) shift; start "$@" ;;
  stop) stop ;;
  status) status ;;
  report) shift; report "$@" ;;
  dashboard) dashboard ;;
  *) echo "usage: $0 start [SYMBOLS] | stop | status | report [sim args] | dashboard" >&2; exit 2 ;;
esac
