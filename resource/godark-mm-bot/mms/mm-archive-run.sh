#!/usr/bin/env bash
# Archive the current MM run: logs, tuning snapshot, manifest, and RUNBOOK.md.
#
# Usage:
#   bash ~/scripts/mms/mm-archive-run.sh [--notes "change description"] [--no-truncate]
#
# Called automatically by start-mm-daemon.sh before each restart.
set -euo pipefail

MMS_ROOT="${HOME}/scripts/mms"
if [[ -f "${MMS_ROOT}/mm-stack-env.sh" ]]; then
  # shellcheck disable=SC1091
  source "${MMS_ROOT}/mm-stack-env.sh"
else
  LOG_DIR="${HOME}/scripts/mms/artifacts"
fi
RUNS_DIR="${LOG_DIR}/runs"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_DIR="${RUNS_DIR}/${RUN_ID}"
NOTES="${MM_RUN_NOTES:-}"
TRUNCATE_LOGS=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --notes)
      NOTES="${2:-}"
      shift 2
      ;;
    --no-truncate)
      TRUNCATE_LOGS=0
      shift
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$RUN_DIR"

copy_if_nonempty() {
  local src="$1"
  local dest="$2"
  if [[ -f "$src" ]] && [[ -s "$src" ]]; then
    cp -a "$src" "$dest"
    return 0
  fi
  return 1
}

ARCHIVED=0
for name in mm-daemon.log mm-tune.log mm-bot-BTC.log mm-bot-ETH.log mm-bot-SOL.log; do
  if copy_if_nonempty "${LOG_DIR}/${name}" "${RUN_DIR}/${name}"; then
    ARCHIVED=1
  fi
done

if [[ -f "${MM_TUNING_ENV:-${LOG_DIR}/mm-tuning.env}" ]]; then
  cp -a "${MM_TUNING_ENV:-${LOG_DIR}/mm-tuning.env}" "${RUN_DIR}/mm-tuning.env.snapshot"
  ARCHIVED=1
fi
if [[ "${MM_STACK:-testnet}" == "devnet" ]] && [[ -f "${MMS_ROOT}/mm-tuning-devnet.env" ]]; then
  cp -a "${MMS_ROOT}/mm-tuning-devnet.env" "${RUN_DIR}/mm-tuning-devnet.overlay.snapshot"
fi

if [[ -f "${LOG_DIR}/mm-metrics/dashboard-latest.json" ]]; then
  cp -a "${LOG_DIR}/mm-metrics/dashboard-latest.json" "${RUN_DIR}/dashboard-latest.json"
fi

# Latest per-symbol eval reports
mkdir -p "${RUN_DIR}/mm-metrics"
for slug in BTC ETH SOL; do
  latest="$(ls -t "${LOG_DIR}/mm-metrics/eval-${slug}-"*.json 2>/dev/null | head -1 || true)"
  if [[ -n "$latest" ]]; then
    cp -a "$latest" "${RUN_DIR}/mm-metrics/"
    ARCHIVED=1
  fi
done

if [[ "$ARCHIVED" -eq 0 ]]; then
  echo "mm-archive-run: nothing to archive (fresh install)"
  rmdir "$RUN_DIR" 2>/dev/null || true
  exit 0
fi

BINARY="${MMS_ROOT}/vanilla-mm-rust/target/release/vanilla-mm-rust"
GIT_REV="unknown"
if git -C "${MMS_ROOT}/vanilla-mm-rust" rev-parse --short HEAD >/dev/null 2>&1; then
  GIT_REV="$(git -C "${MMS_ROOT}/vanilla-mm-rust" rev-parse --short HEAD)"
fi

BINARY_SHA="n/a"
if [[ -f "$BINARY" ]]; then
  BINARY_SHA="$(sha256sum "$BINARY" | awk '{print $1}' | cut -c1-12)"
fi

HOSTNAME="$(hostname 2>/dev/null || echo unknown)"
SYMBOLS="${MM_SYMBOLS:-BTC-USDC-PERP,ETH-USDC-PERP,SOL-USDC-PERP}"

python3 <<PY
import json, os, re, statistics as st
from pathlib import Path

run_dir = Path("${RUN_DIR}")
manifest = {
    "run_id": "${RUN_ID}",
    "archived_at_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "notes": """${NOTES}""",
    "hostname": "${HOSTNAME}",
    "symbols": "${SYMBOLS}".split(","),
    "git_rev": "${GIT_REV}",
    "binary_sha256_prefix": "${BINARY_SHA}",
    "files": sorted(p.name for p in run_dir.iterdir() if p.is_file()),
}
metrics_summary = {}
for slug in ("BTC", "ETH", "SOL"):
    log = run_dir / f"mm-bot-{slug}.log"
    if not log.exists():
        continue
    spreads, as_half, kappas, markout_pos = [], [], [], 0
    n = 0
    for line in log.read_text(errors="ignore").splitlines():
        if "MM_METRICS" not in line:
            continue
        try:
            d = json.loads(line.split("MM_METRICS ", 1)[1])
        except Exception:
            continue
        spreads.append(float(d.get("spread_bps", 0)))
        as_half.append(float(d.get("as_half_bps", 0)))
        kappas.append(float(d.get("effective_kappa", 0)))
        if float(d.get("markout_extra_bps", 0)) > 0:
            markout_pos += 1
        n += 1
    if n:
        metrics_summary[slug] = {
            "samples": n,
            "spread_bps_median": round(st.median(spreads), 2),
            "as_half_bps_median": round(st.median(as_half), 2),
            "kappa_unique": sorted(set(round(k, 2) for k in kappas)),
            "markout_widen_pct": round(100.0 * markout_pos / n, 1),
        }
manifest["metrics_summary"] = metrics_summary
(run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

# RUNBOOK.md
{
  echo "# MM Run ${RUN_ID}"
  echo
  echo "| Field | Value |"
  echo "|-------|-------|"
  echo "| Archived (UTC) | $(date -u +%Y-%m-%dT%H:%M:%SZ) |"
  echo "| Host | ${HOSTNAME} |"
  echo "| Symbols | ${SYMBOLS} |"
  echo "| Binary git | ${GIT_REV} |"
  echo "| Binary sha256 (prefix) | ${BINARY_SHA} |"
  echo "| Notes | ${NOTES:-—} |"
  echo
  echo "## Archived files"
  echo
  ls -lh "$RUN_DIR" | tail -n +2 | awk '{print "- `" $9 "` (" $5 ")"}'
  echo
  if [[ -f "${RUN_DIR}/manifest.json" ]]; then
    echo "## Metrics summary (from manifest.json)"
    echo
    echo '```json'
    python3 -c "import json; print(json.dumps(json.load(open('${RUN_DIR}/manifest.json')).get('metrics_summary',{}), indent=2))"
    echo '```'
    echo
  fi
  echo "## Tuning snapshot (key spread/skew vars)"
  echo
  echo '```'
  grep -E '^MM_(HALF_SPREAD|MIN_HALF|MAX_HALF|KAPPA|AS_|VOL_|MARKOUT|INVENTORY_SKEW|SPREAD)' \
    "${RUN_DIR}/mm-tuning.env.snapshot" 2>/dev/null || echo "(no tuning snapshot)"
  echo '```'
  echo
  echo "## Validation checklist (next run)"
  echo
  echo "- [ ] \`effective_kappa\` diverges from 1.5 after ≥3 fills per symbol"
  echo "- [ ] \`spread_bps\` tracks \`as_half_bps\` in calm markets (not stuck at 30.8)"
  echo "- [ ] \`markout_extra_bps\` widens spread under adverse fills"
  echo "- [ ] Max \|inventory\| stays within cap"
  echo "- [ ] No stacked-order / cancel-failure inventory spikes"
  echo
  echo "## Commands"
  echo
  echo '```bash'
  echo "# Inspect this run"
  echo "cat ${RUN_DIR}/manifest.json"
  echo "less ${RUN_DIR}/mm-bot-BTC.log"
  echo
  echo "# Compare spread before/after"
  echo "grep MM_METRICS ${RUN_DIR}/mm-bot-BTC.log | tail -5"
  echo '```'
} >"${RUN_DIR}/RUNBOOK.md"

# Symlink latest archived run
ln -sfn "$RUN_DIR" "${RUNS_DIR}/latest"

echo "Archived run ${RUN_ID} → ${RUN_DIR}"
echo "  RUNBOOK: ${RUN_DIR}/RUNBOOK.md"
echo "  manifest: ${RUN_DIR}/manifest.json"

if [[ "$TRUNCATE_LOGS" -eq 1 ]]; then
  : >"${LOG_DIR}/mm-daemon.log" 2>/dev/null || true
  : >"${LOG_DIR}/mm-tune.log" 2>/dev/null || true
  for slug in BTC ETH SOL; do
    : >"${LOG_DIR}/mm-bot-${slug}.log" 2>/dev/null || true
  done
  echo "  Truncated active logs for new run"
fi
