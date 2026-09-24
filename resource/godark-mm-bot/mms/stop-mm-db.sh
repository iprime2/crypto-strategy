#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}/docker"
docker compose down
echo "MM strategy TimescaleDB stopped (volume mm-strategy-timescale retained)"
