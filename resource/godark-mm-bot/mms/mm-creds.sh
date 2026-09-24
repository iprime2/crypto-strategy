#!/usr/bin/env bash
# Resolve per-symbol GoDark API credentials into GODARK_API_* / GDX_API_*.
# One bot process per key — set GODARK_API_KEY_ID_BTC, _ETH, _SOL in secrets.env.
set -euo pipefail

mm_symbol_slug() {
  local sym="${1:-${GODARK_SYMBOL:-${GODARK_DEVNET_SYMBOL:-}}}"
  sym="${sym%%-*}"
  echo "${sym^^}"
}

# Apply symbol-specific credentials when GODARK_API_KEY_ID_<SLUG> is set.
# Falls back to shared GODARK_API_KEY_ID (logs a warning).
mm_apply_symbol_credentials() {
  local slug="${1:-$(mm_symbol_slug)}"
  unset MM_API_KEY_LABEL 2>/dev/null || true
  local prefix="GODARK"
  if [[ "${GODARK_ENV:-testnet}" == "devnet" ]]; then
    prefix="GODARK_DEVNET"
  fi

  if [[ -z "$slug" ]]; then
    return 0
  fi

  local id_var="${prefix}_API_KEY_ID_${slug}"
  local sec_var="${prefix}_API_SECRET_${slug}"
  local pp_var="${prefix}_PASSPHRASE_${slug}"

  local sym_id sym_sec sym_pp
  sym_id="${!id_var:-}"
  sym_sec="${!sec_var:-}"
  sym_pp="${!pp_var:-}"

  if [[ -n "$sym_id" && -n "$sym_sec" && -n "$sym_pp" ]]; then
    export GODARK_API_KEY_ID="$sym_id"
    export GODARK_API_SECRET="$sym_sec"
    export GODARK_PASSPHRASE="$sym_pp"
    export GDX_API_KEY_ID="$sym_id"
    export GDX_API_SECRET="$sym_sec"
    export GDX_PASSPHRASE="$sym_pp"
    export MM_API_KEY_LABEL="$slug"
    return 0
  fi

  # Partial symbol-specific config is an error (avoid silent half-config).
  if [[ -n "$sym_id" || -n "$sym_sec" || -n "$sym_pp" ]]; then
    echo "mm-creds: incomplete ${prefix}_API_*_${slug} — set id, secret, and passphrase" >&2
    return 1
  fi

  if [[ "$prefix" == "GODARK_DEVNET" ]]; then
    local shared_id shared_sec shared_pp
    shared_id="${GODARK_DEVNET_API_KEY_ID:-}"
    shared_sec="${GODARK_DEVNET_API_SECRET:-}"
    shared_pp="${GODARK_DEVNET_PASSPHRASE:-}"
    if [[ -n "$shared_id" && -n "$shared_sec" && -n "$shared_pp" ]]; then
      export GODARK_API_KEY_ID="$shared_id"
      export GODARK_API_SECRET="$shared_sec"
      export GODARK_PASSPHRASE="$shared_pp"
      export GDX_API_KEY_ID="$shared_id"
      export GDX_API_SECRET="$shared_sec"
      export GDX_PASSPHRASE="$shared_pp"
      export MM_API_KEY_LABEL="shared-devnet"
      return 0
    fi
  elif [[ -n "${GODARK_API_KEY_ID:-}" && -n "${GODARK_API_SECRET:-}" && -n "${GODARK_PASSPHRASE:-}" ]]; then
    echo "mm-creds: no ${prefix}_API_*_${slug}; using shared GODARK_API_KEY_ID" >&2
    export GDX_API_KEY_ID="${GODARK_API_KEY_ID}"
    export GDX_API_SECRET="${GODARK_API_SECRET}"
    export GDX_PASSPHRASE="${GODARK_PASSPHRASE}"
    export MM_API_KEY_LABEL="shared"
    return 0
  fi

  export MM_API_KEY_LABEL="${MM_API_KEY_LABEL:-shared}"
}
