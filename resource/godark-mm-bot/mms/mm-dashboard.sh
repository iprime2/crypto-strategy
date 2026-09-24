#!/usr/bin/env bash
# Refresh MM dashboard (single HTML with Testnet / Devnet tabs).
#   ~/scripts/mms/artifacts/mm-dashboard.html
set -euo pipefail
python3 "${HOME}/scripts/mms/mm-dashboard.py" "$@"
