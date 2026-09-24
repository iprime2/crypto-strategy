#!/usr/bin/env bash
# Verify per-symbol API keys (auth/token only — no secrets printed).
#
# Usage:
#   bash ~/scripts/mms/mm-verify-keys.sh
#   GODARK_ENV=devnet bash ~/scripts/mms/mm-verify-keys.sh BTC ETH
set -euo pipefail

source ~/scripts/source-secrets.sh
export GODARK_ENV="${GODARK_ENV:-testnet}"

SLUGS=("$@")
if [[ ${#SLUGS[@]} -eq 0 ]]; then
  SLUGS=(BTC ETH SOL)
fi

ok=0
fail=0
for slug in "${SLUGS[@]}"; do
  slug="${slug^^}"
  sym="${slug}-USDC-PERP"
  export GODARK_SYMBOL="$sym"
  export GODARK_DEVNET_SYMBOL="$sym"
  # shellcheck disable=SC1091
  source ~/scripts/mms/mm-env.sh
  if [[ -z "${GODARK_API_KEY_ID:-}" || -z "${GODARK_API_SECRET:-}" || -z "${GODARK_PASSPHRASE:-}" ]]; then
    echo "[$slug] FAIL — incomplete credentials"
    fail=$((fail + 1))
    continue
  fi
  if python3 ~/scripts/mms/godark-resolve-auth.py 2>/dev/null | grep -q 'token:     ok=true'; then
    uuid="$(python3 ~/scripts/mms/godark-resolve-auth.py --uuid 2>/dev/null || true)"
    label="${MM_API_KEY_LABEL:-$slug}"
    echo "[$slug] OK  symbol=$sym key_label=$label user_uuid=${uuid:-?}"
    ok=$((ok + 1))
  else
    if [[ "${GODARK_ENV}" == "devnet" ]]; then
      echo "[$slug] FAIL — auth/token failed (check GODARK_DEVNET_API_*_${slug})"
    else
      echo "[$slug] FAIL — auth/token failed (check GODARK_API_*_${slug})"
    fi
    fail=$((fail + 1))
  fi
done

echo "---"
echo "verified ok=$ok fail=$fail"
[[ "$fail" -eq 0 ]]
