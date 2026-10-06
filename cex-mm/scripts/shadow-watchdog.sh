#!/usr/bin/env bash
# Restart the shadow test when its dry-run or recorder has died (run by a systemd timer).
# Only acts while cex-mm-shadow.service is active: `systemctl --user stop cex-mm-shadow` stops the
# test for good, and a start that is still building is left alone.
set -euo pipefail
cd "$(dirname "$0")/.."

[[ "$(systemctl --user is-active cex-mm-shadow.service || true)" == "active" ]] || exit 0

alive() { [[ -f "artifacts/shadow/current/$1.pid" ]] && kill -0 "$(cat "artifacts/shadow/current/$1.pid")" 2>/dev/null; }
if alive dry-run && alive recorder; then
  exit 0
fi
echo "shadow watchdog: dry-run or recorder is down; restarting the shadow test"
exec systemctl --user restart cex-mm-shadow.service
