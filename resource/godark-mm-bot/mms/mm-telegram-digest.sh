#!/usr/bin/env bash
# Daily MM scorecard → Telegram. Cron-friendly.
set -euo pipefail
source ~/scripts/source-secrets.sh
exec python3 "$(dirname "$0")/mm-telegram-digest.py" "$@"
