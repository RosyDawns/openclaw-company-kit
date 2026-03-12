#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env

RUN_DIR="${PROFILE_DIR}/run"

stop_pid() {
  local name="$1"
  local pid_file="${RUN_DIR}/${name}.pid"
  if [ ! -f "${pid_file}" ]; then
    echo "[stop] ${name}: pid file not found"
    return 0
  fi

  local pid
  pid="$(cat "${pid_file}")"
  if [ -n "${pid}" ] && kill -0 "${pid}" >/dev/null 2>&1; then
    kill "${pid}" >/dev/null 2>&1 || true
    sleep 1
    if kill -0 "${pid}" >/dev/null 2>&1; then
      kill -9 "${pid}" >/dev/null 2>&1 || true
    fi
    echo "[stop] ${name}: stopped pid=${pid}"
  else
    echo "[stop] ${name}: not running"
  fi

  rm -f "${pid_file}"
}

stop_pid "dashboard-http"
stop_pid "dashboard-refresh-loop"
stop_pid "issue-sync-loop"

echo "[OK] local services stopped"
