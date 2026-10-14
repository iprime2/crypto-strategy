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

# Quote settings under test: the DISM profile, the same file a live run uses.
PROFILE="$ROOT/config/dism.env"
mapfile -t PROFILE_ENV < <(grep -E '^[A-Z0-9_]+=' "$PROFILE")
SHADOW_ENV=(
  "${PROFILE_ENV[@]}"
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

  # env -i: no Delta API keys, no MM_OEMS_URL, nothing from the live bot's environment.
  setsid nohup env -i HOME="$HOME" PATH="/usr/bin:/bin" "${SHADOW_ENV[@]}" \
    "$BIN" dry-run --venue delta --env mainnet --symbols "$symbols" --loop-ms 400 \
    >"$run/dry-run.log" 2>&1 </dev/null &
  echo $! >"$run/dry-run.pid"
  setsid nohup env -i HOME="$HOME" PATH="/usr/bin:/bin" RUST_LOG=info NO_COLOR=1 \
    "$BIN" record-delta --symbols "$symbols" --env mainnet --out-dir "$run" --channels trades,ob_l2,mark_price \
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
  # Depth book (ob_l2): the last sample per symbol, and today's recorded book file.
  tail -n 400 "$CURRENT/dry-run.log" 2>/dev/null | grep MM_METRICS | python3 -c '
import json, sys
last = {}
for l in sys.stdin:
    try:
        m = json.loads(l[l.index("{"):])
    except ValueError:
        continue
    last[m.get("symbol")] = m
for s, m in sorted(last.items()):
    d, age, why = m.get("depth_mid"), m.get("depth_age_ms"), m.get("depth_none", "no depth fields")
    print("depth %s: %s" % (s, "mid %s age %s ms" % (d, age) if d is not None else "none (%s)" % why))
' 2>/dev/null || true
  local book
  book="$(ls -1 "$CURRENT"/delta_mainnet_book_*.jsonl 2>/dev/null | tail -1)"
  if [[ -n "$book" ]]; then
    echo "book file: $(basename "$book") $(du -h "$book" | cut -f1)"
  else
    echo "book file: none"
  fi
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
