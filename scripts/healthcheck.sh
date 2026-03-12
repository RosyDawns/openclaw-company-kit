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

HEALTH_STATE_DIR="${PROFILE_DIR}/run"
mkdir -p "${HEALTH_STATE_DIR}"
FAIL_COUNT_FILE="${HEALTH_STATE_DIR}/gateway_fail_count"

EXIT_CODE=0

echo "=== Gateway Status (${OPENCLAW_PROFILE}) ==="
if ocp status --all --json 2>/dev/null | jq -e '.gateway' >/dev/null 2>&1; then
  echo "gateway: responsive"
  echo 0 > "${FAIL_COUNT_FILE}"
else
  echo "gateway: UNRESPONSIVE"
  prev_count=$(cat "${FAIL_COUNT_FILE}" 2>/dev/null || echo 0)
  echo $((prev_count + 1)) > "${FAIL_COUNT_FILE}"
  EXIT_CODE=2
fi

echo
echo "=== Cron Health ==="
cron_json="$(ocp cron list --all --json 2>/dev/null || echo '{"jobs":[]}')"
cron_failures="$(echo "${cron_json}" | jq -r '[.jobs[] | select(.state.lastRunStatus == "error")] | length' 2>/dev/null || echo 0)"
if [ "${cron_failures}" -gt 0 ]; then
  echo "cron failures: ${cron_failures} job(s) in error state"
  echo "${cron_json}" | jq -r '.jobs[] | select(.state.lastRunStatus == "error") | "  FAILED: \(.name) (\(.agentId))"' 2>/dev/null || true
  EXIT_CODE=$((EXIT_CODE > 1 ? EXIT_CODE : 1))
else
  echo "cron: all healthy"
fi

echo
echo "=== Dashboard Data Freshness ==="
if [ -f "${TARGET_DASHBOARD_DIR}/dashboard-data.json" ]; then
  jq -r '"  generated: \(.generatedAt) | gh_auth: \(.githubAuth)"' "${TARGET_DASHBOARD_DIR}/dashboard-data.json" 2>/dev/null || echo "  (parse error)"
else
  echo "  dashboard-data.json not found"
fi

echo
echo "=== Dashboard HTTP ==="
if curl -sS -m 3 "http://127.0.0.1:${DASHBOARD_PORT}/" >/dev/null 2>&1; then
  echo "  reachable: http://127.0.0.1:${DASHBOARD_PORT}"
else
  echo "  NOT reachable on :${DASHBOARD_PORT}"
  EXIT_CODE=$((EXIT_CODE > 1 ? EXIT_CODE : 1))
fi

echo
fail_count=$(cat "${FAIL_COUNT_FILE}" 2>/dev/null || echo 0)
echo "=== Summary ==="
echo "  consecutive_gateway_failures=${fail_count}"
echo "  exit_code=${EXIT_CODE}"
exit ${EXIT_CODE}
