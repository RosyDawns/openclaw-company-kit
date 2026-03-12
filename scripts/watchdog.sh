#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env

CHECK_INTERVAL="${WATCHDOG_INTERVAL:-60}"
MAX_RESTARTS="${WATCHDOG_MAX_RESTARTS:-5}"
BACKOFF_BASE=60
BACKOFF_MAX=1800

HEALTH_STATE_DIR="${PROFILE_DIR}/run"
LOG_DIR="${PROFILE_DIR}/logs"
LOG_FILE="${LOG_DIR}/watchdog.log"
RESTART_COUNT_FILE="${HEALTH_STATE_DIR}/watchdog_restart_count"
mkdir -p "${HEALTH_STATE_DIR}" "${LOG_DIR}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"; }

notify_feishu() {
  local msg="$1"
  local runtime_env="${TARGET_DASHBOARD_DIR}/.env.runtime"
  if [ -f "${runtime_env}" ]; then
    set -a; source "${runtime_env}"; set +a
  fi
  if [ -n "${CRON_GUARD_FEISHU_ACCOUNT:-}" ] && [ -n "${CRON_GUARD_FEISHU_TARGET:-}" ]; then
    ocp send \
      --channel feishu \
      --account "${CRON_GUARD_FEISHU_ACCOUNT}" \
      --to "${CRON_GUARD_FEISHU_TARGET}" \
      --text "[Watchdog] ${msg}" 2>/dev/null || log "feishu notify failed (non-fatal)"
  fi
}

restart_gateway() {
  local count
  count=$(cat "${RESTART_COUNT_FILE}" 2>/dev/null || echo 0)

  if [ "${count}" -ge "${MAX_RESTARTS}" ]; then
    log "CRITICAL: max restarts (${MAX_RESTARTS}) reached, suspending auto-restart"
    notify_feishu "🚨 Gateway 连续重启 ${MAX_RESTARTS} 次仍失败，需人工介入"
    echo "${count}" > "${RESTART_COUNT_FILE}"
    sleep "${BACKOFF_MAX}"
    return 1
  fi

  local backoff=$(( BACKOFF_BASE * (2 ** count) ))
  [ "${backoff}" -gt "${BACKOFF_MAX}" ] && backoff="${BACKOFF_MAX}"

  log "attempting restart #$((count + 1)) (backoff=${backoff}s)"

  ocp gateway install >/dev/null 2>&1 || true
  ocp gateway start >/dev/null 2>&1 || true

  echo $((count + 1)) > "${RESTART_COUNT_FILE}"
  sleep "${backoff}"
}

cleanup() {
  log "watchdog received shutdown signal, exiting gracefully"
  exit 0
}
trap cleanup SIGTERM SIGINT SIGHUP

log "watchdog started (interval=${CHECK_INTERVAL}s, max_restarts=${MAX_RESTARTS})"

while true; do
  if bash "${ROOT_DIR}/scripts/healthcheck.sh" >/dev/null 2>&1; then
    echo 0 > "${RESTART_COUNT_FILE}"
  else
    exit_code=$?
    fail_count=$(cat "${HEALTH_STATE_DIR}/gateway_fail_count" 2>/dev/null || echo 0)
    log "health check failed (exit=${exit_code}, consecutive_fails=${fail_count})"

    if [ "${exit_code}" -ge 2 ]; then
      log "gateway critical failure detected"
      notify_feishu "⚠️ Gateway 故障（连续 ${fail_count} 次），正在自动重启..."
      restart_gateway || true
    fi
  fi
  sleep "${CHECK_INTERVAL}"
done
