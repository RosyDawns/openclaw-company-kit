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
HEALTH_SUMMARY_FILE="${HEALTH_STATE_DIR}/healthcheck-summary.json"
ALERT_THROTTLE_SEC="${WATCHDOG_ALERT_THROTTLE_SEC:-600}"
ALERT_STAMP_DIR="${HEALTH_STATE_DIR}/watchdog-alerts"
mkdir -p "${HEALTH_STATE_DIR}" "${LOG_DIR}"
mkdir -p "${ALERT_STAMP_DIR}"

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

sanitize_key() {
  printf '%s' "$1" | tr -c 'A-Za-z0-9_.-' '_'
}

should_notify_alert() {
  local key="$1"
  local safe_key
  local now_ts
  local stamp_file
  local last_ts

  safe_key="$(sanitize_key "${key}")"
  stamp_file="${ALERT_STAMP_DIR}/${safe_key}.ts"
  now_ts="$(date +%s)"
  last_ts="$(cat "${stamp_file}" 2>/dev/null || echo 0)"

  if [[ "${last_ts}" =~ ^[0-9]+$ ]] && [ $((now_ts - last_ts)) -lt "${ALERT_THROTTLE_SEC}" ]; then
    return 1
  fi

  printf '%s\n' "${now_ts}" > "${stamp_file}"
  return 0
}

refresh_dashboard_data_once() {
  if [ ! -x "${TARGET_DASHBOARD_DIR}/refresh.sh" ]; then
    return 1
  fi
  (cd "${TARGET_DASHBOARD_DIR}" && ./refresh.sh >/dev/null 2>&1)
}

detect_gateway_token_mismatch() {
  local status_output
  status_output="$(ocp gateway status 2>&1 || true)"
  if printf '%s' "${status_output}" | tr '[:upper:]' '[:lower:]' | grep -Eq "gateway token mismatch|openclaw_gateway_token does not match"; then
    return 0
  fi
  return 1
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

  if detect_gateway_token_mismatch; then
    log "gateway token mismatch detected, applying stop/install --force/start repair"
    ocp gateway stop >/dev/null 2>&1 || true
  fi
  ocp gateway install --force >/dev/null 2>&1 || true
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
    categories=""
    should_restart_gateway="false"
    gateway_action=""
    data_lag_action=""
    rate_limit_action=""

    if [ -f "${HEALTH_SUMMARY_FILE}" ]; then
      categories="$(jq -r '[.classifications[].category] | unique | join(",")' "${HEALTH_SUMMARY_FILE}" 2>/dev/null || echo "")"
      should_restart_gateway="$(jq -r '.shouldRestartGateway // false' "${HEALTH_SUMMARY_FILE}" 2>/dev/null || echo "false")"
      gateway_action="$(jq -r '.classifications[] | select(.category == "gateway_fault") | .action' "${HEALTH_SUMMARY_FILE}" 2>/dev/null | head -n1 || true)"
      data_lag_action="$(jq -r '.classifications[] | select(.category == "data_lag") | .action' "${HEALTH_SUMMARY_FILE}" 2>/dev/null | head -n1 || true)"
      rate_limit_action="$(jq -r '.classifications[] | select(.category == "github_rate_limit") | .action' "${HEALTH_SUMMARY_FILE}" 2>/dev/null | head -n1 || true)"
    fi

    log "health check failed (exit=${exit_code}, consecutive_fails=${fail_count}, categories=${categories:-unknown})"

    if [ "${should_restart_gateway}" = "true" ]; then
      log "gateway critical failure detected"
      if should_notify_alert "gateway_fault"; then
        notify_feishu "⚠️ Gateway 故障（连续 ${fail_count} 次），正在自动重启... 建议：${gateway_action:-检查 openclaw gateway 进程状态}"
      fi
      restart_gateway || true
      continue
    fi

    if printf '%s' "${categories}" | grep -q "data_lag"; then
      if refresh_dashboard_data_once; then
        log "data lag detected, triggered one-shot dashboard refresh"
      fi
      if should_notify_alert "data_lag"; then
        notify_feishu "⚠️ Dashboard 数据滞后，建议：${data_lag_action:-执行 refresh.sh 并检查 dashboard-refresh-loop}"
      fi
      continue
    fi

    if printf '%s' "${categories}" | grep -q "github_rate_limit"; then
      if should_notify_alert "github_rate_limit"; then
        notify_feishu "⚠️ GitHub 接口限流/预算降级，建议：${rate_limit_action:-提高缓存 TTL 或 API 预算并稍后重试}"
      fi
      continue
    fi

    if [ "${exit_code}" -gt 0 ] && should_notify_alert "health_generic"; then
      notify_feishu "⚠️ 健康检查异常（exit=${exit_code}），请执行 bash scripts/healthcheck.sh 查看分类详情"
    fi
  fi
  sleep "${CHECK_INTERVAL}"
done
