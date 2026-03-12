#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env
check_cmds

RUNTIME_ENV_FILE="${TARGET_DASHBOARD_DIR}/.env.runtime"
if [ -f "${RUNTIME_ENV_FILE}" ]; then
  set -a
  # shellcheck source=/dev/null
  source "${RUNTIME_ENV_FILE}"
  set +a
fi

if [ ! -f "${PROFILE_DIR}/openclaw.json" ]; then
  echo "[ERROR] profile config not found: ${PROFILE_DIR}/openclaw.json"
  echo "Run: bash scripts/install.sh"
  exit 1
fi

if [ ! -f "${TARGET_DASHBOARD_DIR}/index.html" ]; then
  echo "[ERROR] dashboard not found: ${TARGET_DASHBOARD_DIR}"
  echo "Run: bash scripts/install.sh"
  exit 1
fi

RUN_DIR="${PROFILE_DIR}/run"
LOG_DIR="${PROFILE_DIR}/logs"
mkdir -p "${RUN_DIR}" "${LOG_DIR}"

start_bg() {
  local name="$1"
  local cmd="$2"
  local pid_file="${RUN_DIR}/${name}.pid"
  local log_file="${LOG_DIR}/${name}.log"

  if [ -f "${pid_file}" ]; then
    local pid
    pid="$(cat "${pid_file}")"
    if [ -n "${pid}" ] && kill -0 "${pid}" >/dev/null 2>&1; then
      echo "[start] ${name} already running (pid=${pid})"
      return 0
    fi
  fi

  nohup /bin/bash -lc "${cmd}" >> "${log_file}" 2>&1 &
  echo $! > "${pid_file}"
  echo "[start] ${name} started (pid=$(cat "${pid_file}"))"
}

# Ensure OpenClaw gateway LaunchAgent is installed, then start (for one-click deploy)
# install is idempotent; start may fail if launchd not loaded (e.g. first boot)
ocp gateway install >/dev/null 2>&1 || true
if ! ocp gateway start 2>/dev/null; then
  echo "[WARN] gateway may not be running. If healthcheck fails, run: openclaw --profile ${OPENCLAW_PROFILE} gateway install && openclaw --profile ${OPENCLAW_PROFILE} gateway start"
fi

cd "${TARGET_DASHBOARD_DIR}"
./refresh.sh >/dev/null 2>&1 || true

start_bg "dashboard-refresh-loop" "cd '${TARGET_DASHBOARD_DIR}' && set -a && [ -f .env.runtime ] && source .env.runtime || true; set +a; while true; do ./refresh.sh; sleep 300; done"
start_bg "issue-sync-loop" "cd '${TARGET_DASHBOARD_DIR}' && set -a && [ -f .env.runtime ] && source .env.runtime || true; set +a; while true; do ./issue-sync.sh; sleep 300; done"

echo "[OK] services started"
echo "Profile: ${OPENCLAW_PROFILE}"
