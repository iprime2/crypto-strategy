#!/usr/bin/env bash
# Start MM bots detached from SSH/Cursor — survives terminal close.
#
# Usage:
#   bash ~/scripts/mms/start-mm-daemon.sh              # testnet (default)
#   bash ~/scripts/mms/start-mm-devnet-daemon.sh       # devnet (parallel stack)
#   bash ~/scripts/mms/stop-mm-daemon.sh               # stop testnet only
#   tail -f ~/scripts/mms/artifacts/mm-daemon.log
set -euo pipefail

# shellcheck disable=SC1091
source "${HOME}/scripts/mms/mm-stack-env.sh"

DAEMON_PID_FILE="${LOG_DIR}/mm-daemon.pid"
DAEMON_LOG="${LOG_DIR}/mm-daemon.log"

mkdir -p "$LOG_DIR"
RUNS_DIR="${LOG_DIR}/runs"
mkdir -p "$RUNS_DIR"

RUN_NOTES="${MM_RUN_NOTES:-spread hierarchy + kappa bootstrap + horizon vol fix}"

if [[ -f "$DAEMON_PID_FILE" ]] && kill -0 "$(cat "$DAEMON_PID_FILE")" 2>/dev/null; then
  echo "MM daemon already running stack=${MM_STACK} pid=$(cat "$DAEMON_PID_FILE")"
  if [[ "$MM_STACK" == "devnet" ]]; then
    echo "  Stop first: bash ~/scripts/mms/stop-mm-devnet-daemon.sh"
  else
    echo "  Stop first: bash ~/scripts/mms/stop-mm-daemon.sh"
  fi
  exit 0
fi

# Archive prior run logs + runbook before rebuild/restart.
SHOULD_ARCHIVE=0
for _bot_log in "$LOG_DIR"/mm-bot-*.log; do
  if [[ -f "$_bot_log" ]] && [[ -s "$_bot_log" ]]; then
    SHOULD_ARCHIVE=1
    break
  fi
done
if [[ -f "$DAEMON_LOG" ]] && [[ -s "$DAEMON_LOG" ]]; then
  SHOULD_ARCHIVE=1
fi
if [[ "$SHOULD_ARCHIVE" -eq 1 ]]; then
  echo "Archiving previous run…"
  ARCHIVE_NOTES="${MM_ARCHIVE_NOTES:-archived on daemon restart}"
  MM_STACK="$MM_STACK" MM_ARTIFACTS_DIR="$LOG_DIR" \
    bash "${HOME}/scripts/mms/mm-archive-run.sh" --notes "$ARCHIVE_NOTES"
fi

echo "Building vanilla-mm-rust (release)…"
cd "${HOME}/scripts/mms/vanilla-mm-rust"
cargo build --release --bins

# Clean stop of stale processes for this stack only (not the other env).
MM_STACK="$MM_STACK" MM_ARTIFACTS_DIR="$LOG_DIR" bash "${HOME}/scripts/mms/stop-mm-daemon.sh" 2>/dev/null || true
sleep 1

# setsid + nohup fully detach from controlling terminal (survives SSH logout).
MM_STACK="$MM_STACK" MM_ARTIFACTS_DIR="$LOG_DIR" GODARK_ENV="$GODARK_ENV" \
  setsid nohup bash "${HOME}/scripts/mms/mm-tune-loop.sh" >>"$DAEMON_LOG" 2>&1 &
echo $! >"$DAEMON_PID_FILE"

CURRENT_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
CURRENT_RUN_DIR="${RUNS_DIR}/${CURRENT_RUN_ID}"
mkdir -p "$CURRENT_RUN_DIR"
cp -a "${MM_TUNING_ENV:-${LOG_DIR}/mm-tuning.env}" "${CURRENT_RUN_DIR}/mm-tuning.env.snapshot" 2>/dev/null || true
if [[ "${MM_STACK}" == "devnet" ]] && [[ -f "${HOME}/scripts/mms/mm-tuning-devnet.env" ]]; then
  cp -a "${HOME}/scripts/mms/mm-tuning-devnet.env" "${CURRENT_RUN_DIR}/mm-tuning-devnet.overlay.snapshot" 2>/dev/null || true
fi
if [[ "${MM_STACK}" == "testnet" ]] && [[ -f "${HOME}/scripts/mms/mm-tuning-testnet.env" ]]; then
  cp -a "${HOME}/scripts/mms/mm-tuning-testnet.env" "${CURRENT_RUN_DIR}/mm-tuning-testnet.overlay.snapshot" 2>/dev/null || true
fi

GIT_REV="unknown"
if git -C "${HOME}/scripts/mms/vanilla-mm-rust" rev-parse --short HEAD >/dev/null 2>&1; then
  GIT_REV="$(git -C "${HOME}/scripts/mms/vanilla-mm-rust" rev-parse --short HEAD)"
fi

{
  echo "# MM Run ${CURRENT_RUN_ID} (active)"
  echo
  echo "| Field | Value |"
  echo "|-------|-------|"
  echo "| Started (UTC) | $(date -u +%Y-%m-%dT%H:%M:%SZ) |"
  echo "| Status | **running** |"
  echo "| Notes | ${RUN_NOTES} |"
  echo "| Git rev | ${GIT_REV} |"
  echo "| Daemon pid | $(cat "$DAEMON_PID_FILE") |"
  echo
  echo "## Live logs"
  echo
  echo "| Log | Path |"
  echo "|-----|------|"
  echo "| Supervisor | \`${DAEMON_LOG}\` |"
  echo "| Tune loop | \`${LOG_DIR}/mm-tune.log\` |"
  echo "| BTC bot | \`${LOG_DIR}/mm-bot-BTC.log\` |"
  echo "| ETH bot | \`${LOG_DIR}/mm-bot-ETH.log\` |"
  echo "| SOL bot | \`${LOG_DIR}/mm-bot-SOL.log\` |"
  echo
  echo "## Validation checklist"
  echo
  echo "- [ ] \`effective_kappa\` diverges from 1.5 after ≥3 fills"
  echo "- [ ] Calm \`spread_bps\` below legacy 30.8 bps floor"
  echo "- [ ] \`vol_horizon_bps\` scales down when horizon < lookback window"
  echo "- [ ] Inventory within cap; no cancel-failure stacking"
  echo
  echo "## Stop / archive"
  echo
  echo '```bash'
  echo "bash ~/scripts/mms/stop-mm-daemon.sh"
  echo "MM_RUN_NOTES='your notes' bash ~/scripts/mms/start-mm-daemon.sh  # archives on next start"
  echo '```'
} >"${CURRENT_RUN_DIR}/RUNBOOK.md"

python3 - <<PY
import json
from pathlib import Path
run_dir = Path("${CURRENT_RUN_DIR}")
manifest = {
    "run_id": "${CURRENT_RUN_ID}",
    "started_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "status": "running",
    "notes": """${RUN_NOTES}""",
    "git_rev": "${GIT_REV}",
    "daemon_pid": int("$(cat "$DAEMON_PID_FILE")"),
    "symbols": "${MM_SYMBOLS:-BTC-USDC-PERP,ETH-USDC-PERP,SOL-USDC-PERP}".split(","),
    "log_dir": "${LOG_DIR}",
}
(run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

ln -sfn "$CURRENT_RUN_DIR" "${RUNS_DIR}/current"

echo "MM daemon started stack=${MM_STACK} env=${GODARK_ENV} pid=$(cat "$DAEMON_PID_FILE")"
echo "  symbols: ${MM_SYMBOLS:-BTC-USDC-PERP,ETH-USDC-PERP,SOL-USDC-PERP}"
echo "  supervisor log: $DAEMON_LOG"
echo "  per-symbol logs: ${LOG_DIR}/mm-bot-{BTC,ETH,SOL}.log"
echo "  run dir: ${CURRENT_RUN_DIR}"
echo "  runbook: ${CURRENT_RUN_DIR}/RUNBOOK.md"
echo "  prior runs: ${RUNS_DIR}/latest (last archived)"
