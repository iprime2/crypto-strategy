#!/usr/bin/env bash
# REAL-MONEY run of the DISM profile on Delta India MAINNET, next to the shadow test, so its real fills can be
# compared with the simulator over the same window (scripts/live_vs_shadow.py). It places real orders with the
# mainnet key in quote-bot/.env: same binary, profile (config/dism.env), flags and loop as the shadow dry-run,
# with `run` in place of `dry-run`. Without the OEMS; never run both on one account.
#
#   scripts/live.sh start --confirm "START REAL"   # refuses unless the shadow runs and the key check passes
#   scripts/live.sh status                         # bot, last quote, venue position and open orders (read-only)
#   scripts/live.sh stop                           # kill the bot, then cancel its orders; the position stays open
#   scripts/live.sh report [args]                  # real fills vs the simulator (scripts/live_vs_shadow.py)
#
# No auto-restart. mm-bot has no signal handler: if it dies or is killed, Delta's dead man's switch
# (MM_DMS_TTL_MS) cancels its resting orders, and the position stays open until the operator decides.
# The bot runs with artifacts/live/ as its working directory, so its economics file cannot reach the shadow
# dry-run (which reads artifacts/economics/) and its daily loss state (artifacts/live/artifacts/risk/) carries
# over between live runs.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
LIVE="$ROOT/artifacts/live"
CURRENT="$LIVE/current"
BIN="$ROOT/target/release/mm-bot"
PROFILE="$ROOT/config/dism.env"
ENV_FILE="${LIVE_ENV_FILE:-$ROOT/quote-bot/.env}"
SHADOW_CURRENT="$ROOT/artifacts/shadow/current"
CONFIRM="START REAL"
LIVE_RUST_LOG="warn,mm_bot=info,MM_METRICS=info,MM_ORDER=info"
SYMBOLS="$(grep -E '^MM_SYMBOLS=' "$PROFILE" | tail -1 | cut -d= -f2-)"

die() { echo "live.sh: $*" >&2; exit 1; }

# Value of KEY in an env file, parsed like the OEMS (supervisor.rs load_env_file): trimmed, surrounding double
# quotes stripped, last assignment wins. Printed only into a variable, never to the terminal or a log.
env_value() {
  local file="$1" want="$2" line k v out=""
  [[ -r "$file" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
    k="${line%%=*}"; k="${k%"${k##*[![:space:]]}"}"
    [[ "$k" == "$want" ]] || continue
    v="${line#*=}"; v="${v#"${v%%[![:space:]]*}"}"; v="${v%"${v##*[![:space:]]}"}"
    while [[ "$v" == \"* ]]; do v="${v#\"}"; done
    while [[ "$v" == *\" ]]; do v="${v%\"}"; done
    out="$v"
  done <"$file"
  printf '%s' "$out"
}

# True if PID is a live `mm-bot run` process (guards against a dead pid being reused by something else).
is_bot() {
  local pid="$1" argv i
  [[ "$pid" =~ ^[0-9]+$ ]] && [[ -r "/proc/$pid/cmdline" ]] || return 1
  { mapfile -d '' -t argv <"/proc/$pid/cmdline"; } 2>/dev/null || return 1
  for ((i = 0; i + 1 < ${#argv[@]}; i++)); do
    [[ "$(basename -- "${argv[i]}")" == mm-bot && "${argv[i + 1]}" == run ]] && return 0
  done
  return 1
}

bot_pid() { [[ -f "$CURRENT/bot.pid" ]] && cat "$CURRENT/bot.pid" || true; }
# Alive and not a zombie (an orphan's zombie can linger until its new parent reaps it).
alive() { [[ "$1" =~ ^[0-9]+$ ]] && [[ -r "/proc/$1/stat" ]] && [[ "$(cut -d' ' -f3 "/proc/$1/stat" 2>/dev/null)" != Z ]]; }
pid_alive() { [[ -f "$1" ]] && alive "$(cat "$1")"; }

# Every `mm-bot run` process on the machine: ours, the OEMS's or a stray one.
all_bots() {
  local d
  for d in /proc/[0-9]*; do
    is_bot "${d#/proc/}" && echo "${d#/proc/}"
  done
  return 0
}

# Runs inside `env -i` (see start/stop): load only the mainnet keys (and, for `run`, the profile), then exec
# mm-bot. Nothing here is echoed, and the secret never appears in an argv.
exec_bot() {
  local key secret line sym
  key="$(env_value "$ENV_FILE" DELTA_MAINNET_API_KEY)"
  secret="$(env_value "$ENV_FILE" DELTA_MAINNET_API_SECRET)"
  [[ -n "$key" && -n "$secret" ]] || die "DELTA_MAINNET_API_KEY / DELTA_MAINNET_API_SECRET missing in $ENV_FILE"
  export DELTA_MAINNET_API_KEY="$key" DELTA_MAINNET_API_SECRET="$secret" RUST_LOG="$LIVE_RUST_LOG" NO_COLOR=1
  unset key secret
  case "$1" in
    run)
      while IFS= read -r line; do export "$line"; done < <(grep -E '^[A-Z0-9_]+=' "$PROFILE")
      mkdir -p "$LIVE"
      cd "$LIVE"
      exec "$BIN" run --venue delta --env mainnet --symbols "$SYMBOLS" --loop-ms 400
      ;;
    cancel)
      # No profile here: MM_SYMBOLS in the env would send cancel-all down its universe path.
      for sym in ${SYMBOLS//,/ }; do
        "$BIN" cancel-all --venue delta --env mainnet --symbol "$sym" || exit 1
      done
      ;;
    *) die "unknown exec mode $1" ;;
  esac
}

clean_env() {
  env -i HOME="$HOME" PATH="/usr/bin:/bin" LIVE_ENV_FILE="$ENV_FILE" "$ROOT/scripts/live.sh" _exec "$@"
}

venue() {
  python3 "$ROOT/scripts/live_vs_shadow.py" venue --env-file "$ENV_FILE" --live-dir "$1" 2>&1 || true
}

start() {
  [[ $# -eq 2 && "$1" == --confirm && "$2" == "$CONFIRM" ]] \
    || die "this places REAL orders on Delta mainnet. Run: scripts/live.sh start --confirm \"$CONFIRM\""
  [[ -x "$BIN" ]] || die "no $BIN (build it with cargo build --release -p mm-bot, or restart the shadow test)"
  [[ "$SYMBOLS" =~ ^[A-Z0-9]+(,[A-Z0-9]+)*$ ]] || die "no usable MM_SYMBOLS in $PROFILE"
  local pid others spid
  pid="$(bot_pid)"
  if is_bot "$pid"; then die "the live bot is already running (pid $pid)"; fi
  others="$(all_bots | tr '\n' ' ')"
  [[ -z "${others// /}" ]] || die "another mm-bot run process is alive (pid ${others% }): the OEMS or a stray bot. Two bots on one account fight; stop it first"
  pid_alive "$SHADOW_CURRENT/dry-run.pid" || die "the shadow test is not running (start it: systemctl --user start cex-mm-shadow); the comparison needs it"
  spid="$(cat "$SHADOW_CURRENT/dry-run.pid")"
  if ! cmp -s "/proc/$spid/exe" "$BIN"; then
    [[ "${LIVE_ALLOW_BINARY_MISMATCH:-}" == 1 ]] \
      || die "the shadow dry-run runs a different mm-bot build than $BIN; restart the shadow first (systemctl --user restart cex-mm-shadow) or set LIVE_ALLOW_BINARY_MISMATCH=1"
    echo "warning: the shadow dry-run runs a different mm-bot build (LIVE_ALLOW_BINARY_MISMATCH=1)"
  fi
  [[ -n "$(env_value "$ENV_FILE" DELTA_MAINNET_API_KEY)" ]] || die "DELTA_MAINNET_API_KEY missing in $ENV_FILE"
  [[ -n "$(env_value "$ENV_FILE" DELTA_MAINNET_API_SECRET)" ]] || die "DELTA_MAINNET_API_SECRET missing in $ENV_FILE"
  local sym
  for sym in ${SYMBOLS//,/ }; do
    python3 "$ROOT/scripts/delta_key_check.py" "$ENV_FILE" "${sym%T}" \
      || die "key check failed for ${sym%T} (key, IP whitelist, or order leverage above 5x): not starting"
  done

  local run
  run="$LIVE/$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$run"
  ln -sfn "$run" "$CURRENT"
  {
    echo "symbols=$SYMBOLS"
    echo "started_utc=$(date -u +%FT%TZ)"
    echo "git=$(git rev-parse --short HEAD 2>/dev/null || echo unknown) $(git status --porcelain 2>/dev/null | wc -l) uncommitted"
    echo "binary_sha256=$(sha256sum "$BIN" | cut -d' ' -f1)"
    echo "shadow_run=$(basename "$(readlink -f "$SHADOW_CURRENT")")"
    echo "env=mainnet"
    grep -E '^[A-Z0-9_]+=' "$PROFILE"
    echo "RUST_LOG=$LIVE_RUST_LOG"
  } >"$run/config.txt"

  setsid nohup env -i HOME="$HOME" PATH="/usr/bin:/bin" LIVE_ENV_FILE="$ENV_FILE" \
    "$ROOT/scripts/live.sh" _exec run >"$run/bot.log" 2>&1 </dev/null &
  echo $! >"$run/bot.pid"
  echo "REAL-MONEY bot starting: $SYMBOLS on Delta mainnet, run $run"

  # The pid is the launcher until it execs mm-bot, so wait on the pid itself, not on is_bot.
  local i wait_s="${LIVE_START_WAIT_S:-30}" lpid
  lpid="$(bot_pid)"
  for ((i = 0; i < wait_s * 5; i++)); do
    grep -q "account guards on" "$run/bot.log" && break
    alive "$lpid" || break
    sleep 0.2
  done
  if ! is_bot "$lpid"; then
    echo "live.sh: the bot exited during startup; last log lines:" >&2
    tail -20 "$run/bot.log" >&2
    exit 1
  fi
  grep -q "account guards on" "$run/bot.log" || echo "warning: no 'account guards on' line after ${wait_s} s; check the log"
  status
}

stop() {
  local pid i
  pid="$(bot_pid)"
  if is_bot "$pid"; then
    kill -TERM "$pid" 2>/dev/null || true
    for ((i = 0; i < 50; i++)); do is_bot "$pid" || break; sleep 0.1; done
    if is_bot "$pid"; then kill -KILL "$pid" 2>/dev/null || true; sleep 0.5; fi
    echo "stopped the live bot (pid $pid)"
  else
    echo "the live bot is not running"
  fi
  [[ -d "$CURRENT" ]] && date -u +%FT%TZ >"$CURRENT/stopped"
  # mm-bot has no signal handler, so its orders are still resting: cancel them now rather than wait for the DMS.
  local ok=0
  for ((i = 1; i <= 3; i++)); do
    if clean_env cancel; then ok=1; break; fi
    sleep 1
  done
  if [[ $ok == 1 ]]; then
    echo "cancelled open orders on $SYMBOLS (mainnet)"
  else
    echo "live.sh: CANCEL FAILED 3 times; Delta's dead man's switch cancels them within MM_DMS_TTL_MS. Check the venue." >&2
  fi
  [[ -d "$CURRENT" ]] && venue "$(readlink -f "$CURRENT")"
  echo "The position is left open: flattening is a separate decision."
  [[ $ok == 1 ]]
}

status() {
  if [[ ! -e "$CURRENT" ]]; then
    echo "no live run yet"
    return
  fi
  local run pid
  run="$(readlink -f "$CURRENT")"
  pid="$(bot_pid)"
  echo "run: $run"
  sed -n '1,5p' "$run/config.txt"
  if is_bot "$pid"; then
    echo "bot: running (pid $pid, up $(ps -o etime= -p "$pid" | tr -d ' '))"
  elif [[ -f "$run/stopped" ]]; then
    echo "bot: stopped by live.sh stop at $(cat "$run/stopped")"
  else
    echo "bot: DOWN - it exited on its own (log last written $(date -u -r "$run/bot.log" +%FT%TZ))."
    echo "  Delta's dead man's switch cancels resting orders within MM_DMS_TTL_MS; the position stays open."
    echo "  Not restarted automatically. Last errors:"
    grep -E "ERROR|WARN|panicked" "$run/bot.log" | tail -5 | sed 's/^/    /' || true
  fi
  local last
  last="$(tail -c 400000 "$run/bot.log" | grep MM_METRICS | tail -1 || true)"
  if [[ -n "$last" ]]; then
    echo "last quote: ${last:0:27} $(grep -oE '"(bid|ask|inventory)":[^,]*' <<<"$last" | tr '\n' ' ')"
  fi
  echo "orders placed/edited: $(grep -c 'MM_ORDER' "$run/bot.log" || true)   rejects: $(grep -c 'MM_REJECT' "$run/bot.log" || true)"
  grep -E "ERROR|halt|daily loss|stale book" "$run/bot.log" | tail -3 || true
  venue "$run"
}

report() {
  nice -n 19 python3 "$ROOT/scripts/live_vs_shadow.py" --live-dir "$(readlink -f "$CURRENT")" --env-file "$ENV_FILE" "$@"
}

case "${1:-status}" in
  start) shift; start "$@" ;;
  stop) stop ;;
  status) status ;;
  report) shift; report "$@" ;;
  _exec) shift; exec_bot "$@" ;;
  *) echo "usage: $0 start --confirm \"$CONFIRM\" | stop | status | report [args]" >&2; exit 2 ;;
esac
