#!/usr/bin/env bash
# Testnet smoke: post-only buy far from market → amend → cancel-all
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="${HOME}/.local/bin-wrappers:${PATH}"
if [[ -f .env ]]; then set -a; source .env; set +a; fi
if [[ -z "${BYBIT_API_KEY:-}" || -z "${BYBIT_API_SECRET:-}" ]]; then
  echo "FAIL: set BYBIT_API_KEY and BYBIT_API_SECRET in cex-mm/.env (testnet keys)" >&2
  exit 1
fi
echo "Running Bybit testnet integration (place / amend / cancel)..."
cargo test -p mm-bybit --test integration post_only_amend_cancel_flow -- --ignored --nocapture
echo "PASS: smoke test completed"
