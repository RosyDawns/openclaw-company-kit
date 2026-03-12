#!/usr/bin/env bash
set -euo pipefail

PORT="${DASHBOARD_PORT:-8788}"
APP_DIR="/app/dashboard/rd-dashboard"
DEMO_DIR="/app/docker/demo_data"

mkdir -p "${APP_DIR}/reports"
cp -f "${DEMO_DIR}/dashboard-data.json" "${APP_DIR}/dashboard-data.json"
cp -f "${DEMO_DIR}/business-metrics.json" "${APP_DIR}/business-metrics.json"

exec python3 -m http.server "${PORT}" --bind 0.0.0.0 --directory "${APP_DIR}"
