#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${HOME}/scripts/source-secrets.sh" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/scripts/source-secrets.sh"
fi
# shellcheck disable=SC1091
source "${ROOT}/mm-db-env.sh"

cd "${ROOT}/docker"
docker compose exec -T timescale psql -U "${MM_TSDB_USER}" -d "${MM_TSDB_DB}" -v ON_ERROR_STOP=1 <<'SQL'
SELECT extname FROM pg_extension WHERE extname = 'timescaledb';
\d mm_metric_samples
SELECT count(*) AS sample_rows FROM mm_metric_samples;
SQL

echo "OK — MM TimescaleDB schema present"
