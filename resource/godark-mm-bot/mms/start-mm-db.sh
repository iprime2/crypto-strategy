#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="${ROOT}/docker"

if [[ -f "${HOME}/scripts/source-secrets.sh" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/scripts/source-secrets.sh"
fi
# shellcheck disable=SC1091
source "${ROOT}/mm-db-env.sh"

if [[ "${MM_TSDB_PASSWORD}" == "mm_local_dev_only" ]]; then
  echo "note: using default MM_TSDB_PASSWORD (set in ~/.cursor/secrets.env for non-local use)"
fi

cd "${COMPOSE_DIR}"
docker compose up -d

echo "Waiting for Timescale health…"
for _ in $(seq 1 40); do
  if docker compose exec -T timescale pg_isready -U "${MM_TSDB_USER}" -d "${MM_TSDB_DB}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! docker compose exec -T timescale pg_isready -U "${MM_TSDB_USER}" -d "${MM_TSDB_DB}" >/dev/null 2>&1; then
  echo "MM TimescaleDB failed health check — see: docker logs mm-strategy-timescale"
  exit 1
fi

echo "MM strategy DB ready"
echo "  container: mm-strategy-timescale"
echo "  URL:       postgres://${MM_TSDB_USER}@${MM_TSDB_HOST}:${MM_TSDB_PORT}/${MM_TSDB_DB}"
echo "  verify:    bash ${ROOT}/mm-db-verify.sh"
