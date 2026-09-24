#!/usr/bin/env bash
# Connection vars for MM strategy TimescaleDB (source after source-secrets.sh).
set -euo pipefail

: "${MM_TSDB_HOST:=127.0.0.1}"
: "${MM_TSDB_PORT:=5462}"
: "${MM_TSDB_USER:=mm}"
: "${MM_TSDB_DB:=mm_ops}"
: "${MM_TSDB_PASSWORD:=mm_local_dev_only}"

export MM_TSDB_HOST MM_TSDB_PORT MM_TSDB_USER MM_TSDB_DB MM_TSDB_PASSWORD
export MM_TSDB_URL="postgres://${MM_TSDB_USER}:${MM_TSDB_PASSWORD}@${MM_TSDB_HOST}:${MM_TSDB_PORT}/${MM_TSDB_DB}"
