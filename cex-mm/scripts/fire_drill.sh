#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Load secrets from gitignored .env if present
if [[ -f .env ]]; then set -a; source .env; set +a; fi
start=$(date +%s%3N)
cargo run -p mm-bot -- cancel-all --env testnet --symbol "${MM_SYMBOL:-BTCUSDT}"
end=$(date +%s%3N)
echo "cancel-all latency_ms=$((end - start))"
if (( end - start > 2000 )); then
  echo "FAIL: exceeded 2s kill target" >&2
  exit 1
fi
echo "PASS: fire drill"
