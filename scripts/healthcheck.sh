#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env

RUNTIME_ENV_FILE="${TARGET_DASHBOARD_DIR}/.env.runtime"
if [ -f "${RUNTIME_ENV_FILE}" ]; then
  set -a
  # shellcheck source=/dev/null
  source "${RUNTIME_ENV_FILE}"
  set +a
fi

echo "=== OpenClaw Status (${OPENCLAW_PROFILE}) ==="
ocp status --all | sed -n '1,120p'

echo
echo "=== Cron Jobs (${OPENCLAW_PROFILE}) ==="
ocp cron list --all --json | jq -r '.jobs[] | [.name,.agentId,((.enabled|tostring)),((.schedule.expr//"-")),((.state.lastRunStatus//"-")),((.state.lastDeliveryStatus//"-"))] | @tsv' | sed -n '1,40p'

echo
echo "=== Dashboard Data Freshness ==="
if [ -f "${TARGET_DASHBOARD_DIR}/dashboard-data.json" ]; then
  jq -r '.generatedAt, .githubAuth, .github.issueStats' "${TARGET_DASHBOARD_DIR}/dashboard-data.json"
else
  echo "dashboard-data.json not found"
fi

echo
echo "=== Dashboard HTTP ==="
if curl -sS -m 3 "http://127.0.0.1:${DASHBOARD_PORT}/" >/dev/null; then
  echo "dashboard reachable: http://127.0.0.1:${DASHBOARD_PORT}"
else
  echo "dashboard not reachable on :${DASHBOARD_PORT}"
fi
