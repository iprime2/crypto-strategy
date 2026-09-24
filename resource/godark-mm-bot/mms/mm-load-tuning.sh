#!/usr/bin/env bash
# Load MM tuning for the active stack (testnet | devnet).
# Eval writes MM_TUNING_ENV; devnet overlay is runtime-only (not overwritten by eval).
set -euo pipefail

MMS_ROOT="${HOME}/scripts/mms"
: "${MM_TUNING_BASE:=${MMS_ROOT}/mm-tuning.env}"

if [[ -z "${MM_ARTIFACTS_DIR:-}" ]]; then
  # shellcheck disable=SC1091
  source "${MMS_ROOT}/mm-stack-env.sh"
fi

: "${MM_TUNING_ENV:=${MM_ARTIFACTS_DIR}/mm-tuning.env}"

if [[ ! -f "$MM_TUNING_ENV" ]] && [[ -f "$MM_TUNING_BASE" ]]; then
  cp -a "$MM_TUNING_BASE" "$MM_TUNING_ENV"
fi

set -a
if [[ -f "$MM_TUNING_ENV" ]]; then
  # shellcheck disable=SC1090
  source "$MM_TUNING_ENV"
fi
if [[ "${MM_STACK:-testnet}" == "devnet" ]]; then
  OVERLAY="${MM_TUNING_OVERLAY:-${MMS_ROOT}/mm-tuning-devnet.env}"
elif [[ "${MM_STACK:-testnet}" == "testnet" ]]; then
  OVERLAY="${MM_TUNING_OVERLAY:-${MMS_ROOT}/mm-tuning-testnet.env}"
else
  OVERLAY=""
fi
if [[ -n "${OVERLAY:-}" ]] && [[ -f "$OVERLAY" ]]; then
  # shellcheck disable=SC1090
  source "$OVERLAY"
fi
set +a

export MM_TUNING_ENV MM_TUNING_BASE
