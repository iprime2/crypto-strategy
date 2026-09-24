#!/usr/bin/env bash
# Shared GoDark env for MM launchers (testnet default; devnet when GODARK_ENV=devnet).
set -euo pipefail

_preserve_godark_env="${GODARK_ENV:-}"
_preserve_mm_stack="${MM_STACK:-}"
source ~/scripts/source-secrets.sh
if [[ "${_preserve_mm_stack}" == "devnet" ]]; then
  export GODARK_ENV=devnet
elif [[ "${_preserve_mm_stack}" == "testnet" ]]; then
  export GODARK_ENV=testnet
elif [[ "${_preserve_godark_env}" == "devnet" ]]; then
  export GODARK_ENV=devnet
else
  export GODARK_ENV="${GODARK_ENV:-testnet}"
fi
unset _preserve_godark_env _preserve_mm_stack

# Per-symbol keys: GODARK_*_<SLUG> or GODARK_DEVNET_*_<SLUG> when GODARK_ENV=devnet.
# shellcheck disable=SC1091
source ~/scripts/mms/mm-creds.sh

if [[ "${GODARK_ENV}" == "devnet" ]]; then
  export GODARK_DEVNET_REST_URL="${GODARK_DEVNET_REST_URL:-https://api.devnet.godark-dex.com}"
  export GODARK_DEVNET_EDGE_URL="${GODARK_DEVNET_EDGE_URL:-wss://api.devnet.godark-dex.com}"
  export GODARK_REST_URL="${GODARK_DEVNET_REST_URL}"
  export GDX_HPKE_STATIC_PUBLIC_KEY="${GDX_HPKE_STATIC_PUBLIC_KEY:-${GODARK_DEVNET_HPKE_STATIC_PUBLIC_KEY:-}}"
  export GODARK_EDGE_URL="${GDX_EDGE_URL:-${GODARK_DEVNET_EDGE_URL}}"
fi

mm_apply_symbol_credentials "$(mm_symbol_slug)" || true

if [[ "${GODARK_ENV}" == "devnet" ]]; then
  # Shared devnet key only when no per-symbol GODARK_DEVNET_API_*_<SLUG> was applied.
  if [[ "${MM_API_KEY_LABEL:-shared}" == "shared" ]]; then
    export GODARK_API_KEY_ID="${GODARK_DEVNET_API_KEY_ID:-${GODARK_API_KEY_ID:-}}"
    export GODARK_API_SECRET="${GODARK_DEVNET_API_SECRET:-${GODARK_API_SECRET:-}}"
    export GODARK_PASSPHRASE="${GODARK_DEVNET_PASSPHRASE:-${GODARK_PASSPHRASE:-}}"
  fi
  export GDX_API_KEY_ID="${GODARK_API_KEY_ID:-}"
  export GDX_API_SECRET="${GODARK_API_SECRET:-}"
  export GDX_PASSPHRASE="${GODARK_PASSPHRASE:-}"
  export GDX_HPKE_STATIC_PUBLIC_KEY="${GDX_HPKE_STATIC_PUBLIC_KEY:-${GODARK_DEVNET_HPKE_STATIC_PUBLIC_KEY:-}}"
  export GODARK_EDGE_URL="${GDX_EDGE_URL:-${GODARK_DEVNET_EDGE_URL}}"
else
  export GODARK_EDGE_URL="${GDX_EDGE_URL:-${GODARK_EDGE_URL:-wss://api.godark-dex.com}}"
  export GDX_API_KEY_ID="${GODARK_API_KEY_ID:-${GDX_API_KEY_ID:-}}"
  export GDX_API_SECRET="${GODARK_API_SECRET:-${GDX_API_SECRET:-}}"
  export GDX_PASSPHRASE="${GODARK_PASSPHRASE:-${GDX_PASSPHRASE:-}}"
  export GDX_HPKE_STATIC_PUBLIC_KEY="${GDX_HPKE_STATIC_PUBLIC_KEY:-${GODARK_HPKE_STATIC_PUBLIC_KEY:-}}"
fi

eval "$(python3 ~/scripts/mms/godark-resolve-auth.py --export)"

unset GODARK_USER_UUID GODARK_DEVNET_USER_UUID 2>/dev/null || true
