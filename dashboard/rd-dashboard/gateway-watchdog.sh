#!/usr/bin/env bash
set -euo pipefail

LOG_PREFIX="[gateway-watchdog]"
OPENCLAW_BIN="${OPENCLAW_BIN:-}"
OPENCLAW_BIN="${OPENCLAW_BIN:-$(command -v openclaw || true)}"
OPENCLAW_STATE_DIR="${OPENCLAW_STATE_DIR:-${HOME}/.openclaw}"
OPENCLAW_PROFILE="${OPENCLAW_PROFILE:-}"
GATEWAY_PORT="${GATEWAY_PORT:-18789}"
STATE_PATH="${STATE_PATH:-$(cd "$(dirname "$0")" && pwd)/reports/gateway-watchdog-state.json}"
RESTART_WAIT_SEC=3

log() {
  echo "${LOG_PREFIX} $*" >&2
}

write_state() {
  local ok="$1"
  local action="$2"
  local detail="$3"
  local ts
  ts="$(TZ=Asia/Shanghai date '+%Y-%m-%d %H:%M:%S')"
  mkdir -p "$(dirname "${STATE_PATH}")"
  jq -n \
    --arg checkedAt "${ts}" \
    --arg action "${action}" \
    --arg detail "${detail}" \
    --argjson ok "${ok}" \
    '{checkedAt:$checkedAt,ok:$ok,action:$action,detail:$detail}' > "${STATE_PATH}"
}

probe_gateway_once() {
  local pid
  set +e
  pid="$(lsof -nP -iTCP:${GATEWAY_PORT} -sTCP:LISTEN -t 2>/dev/null | head -n1)"
  local rc=$?
  set -e
  [ "${rc}" -eq 0 ] && [ -n "${pid}" ]
}

check_gateway_health() {
  probe_gateway_once
}

if [ -z "${OPENCLAW_BIN}" ]; then
  log "openclaw not found in PATH"
  write_state false "failed" "openclaw not found"
  exit 1
fi

if check_gateway_health; then
  write_state true "noop" "gateway health ok"
  exit 0
fi

log "gateway health probe failed, trying restart"
if [ -n "${OPENCLAW_PROFILE}" ]; then
  "${OPENCLAW_BIN}" --profile "${OPENCLAW_PROFILE}" gateway restart >/dev/null 2>&1 || true
else
  "${OPENCLAW_BIN}" gateway restart >/dev/null 2>&1 || true
fi
sleep "${RESTART_WAIT_SEC}"

if check_gateway_health; then
  log "gateway recovered after restart"
  write_state true "restart" "gateway recovered"
  exit 0
fi

log "gateway still unhealthy after restart"
write_state false "restart-failed" "gateway health probe failed after restart"
exit 1
