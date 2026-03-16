#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=./_common.sh
source "${ROOT_DIR}/scripts/_common.sh"

load_env
DEFAULT_PORT="${DASHBOARD_PORT:-8788}"
LAUNCH_PORT="${LAUNCH_PORT:-}"
LAUNCH_PROMPT_PORT="${LAUNCH_PROMPT_PORT:-0}"
LAUNCH_PORT_SCAN_LIMIT="${LAUNCH_PORT_SCAN_LIMIT:-20}"
RUN_DIR="${PROFILE_DIR}/run"
CONTROL_SERVER_PORT_FILE="${CONTROL_SERVER_PORT_FILE:-${RUN_DIR}/control-server-port}"
IS_INTERACTIVE=0
if [ -t 0 ] && [ -t 1 ]; then
  IS_INTERACTIVE=1
fi
mkdir -p "${RUN_DIR}"

echo "环境检测："
check_cmds

if [ "${SYNC_PROJECT_GH_BRIDGE}" = "1" ] && [ "${SYNC_PROJECT_GH_BRIDGE_ON_LAUNCH}" = "1" ]; then
  bridge_args=(--target "${PROJECT_PATH}")
  if [ "${SYNC_PROJECT_GH_BRIDGE_STRICT}" = "1" ]; then
    bridge_args+=(--strict)
  fi
  "${ROOT_DIR}/scripts/install-gh-bridge.sh" "${bridge_args[@]}"
fi

# GH_TOKEN / gh auth 软检测（非阻塞）
if command -v gh >/dev/null 2>&1; then
  if [ -z "${GH_TOKEN:-}" ] && ! gh auth status >/dev/null 2>&1; then
    echo "[WARN] GitHub 认证未配置（gh-issues skill 将不可用）"
  fi
fi

echo ""

is_valid_port() {
  local candidate="${1:-}"
  [[ "${candidate}" =~ ^[0-9]+$ ]] && [ "${candidate}" -ge 1 ] && [ "${candidate}" -le 65535 ]
}

read_saved_control_server_port() {
  local saved=""
  if [ -f "${CONTROL_SERVER_PORT_FILE}" ]; then
    saved="$(head -n 1 "${CONTROL_SERVER_PORT_FILE}" | tr -d '[:space:]')"
  fi

  if is_valid_port "${saved}"; then
    printf '%s\n' "${saved}"
    return 0
  fi

  return 1
}

persist_control_server_port() {
  local selected_port="$1"
  local preferred_port="$2"

  if [ "${selected_port}" = "${preferred_port}" ]; then
    rm -f "${CONTROL_SERVER_PORT_FILE}" >/dev/null 2>&1 || true
    return 0
  fi

  mkdir -p "$(dirname "${CONTROL_SERVER_PORT_FILE}")"
  printf '%s\n' "${selected_port}" > "${CONTROL_SERVER_PORT_FILE}"
}

is_port_in_use() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi

  # Fallback: treat successful TCP connect as "occupied/listening".
  python3 - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.5)
try:
    s.connect(("127.0.0.1", port))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
raise SystemExit(0)
PY
}

is_control_server_running() {
  local port="$1"
  local code
  code="$(curl -sS -m 2 -o /dev/null -w '%{http_code}' "http://127.0.0.1:${port}/api/config" 2>/dev/null || true)"
  case "${code}" in
    200|401|403)
      return 0
      ;;
    *)
      ;;
  esac

  # Fallback: detect control_server.py listener by process args.
  if command -v lsof >/dev/null 2>&1 && command -v ps >/dev/null 2>&1; then
    local pid args
    pid="$(lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
    if [ -n "${pid}" ]; then
      args="$(ps -p "${pid}" -o args= 2>/dev/null || true)"
      if printf '%s' "${args}" | grep -q 'scripts/control_server.py'; then
        return 0
      fi
    fi
  fi

  return 1
}

print_port_listener() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local out
    out="$(lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "${out}" ]; then
      printf '%s\n' "${out}" | sed 's/^/  /'
    else
      echo "  [no LISTEN process found]"
    fi
  fi
}

list_port_listener_pids() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
  fi
}

find_next_available_port() {
  local current="$1"
  local limit="$2"
  local candidate
  local steps=0

  candidate="$current"
  while [ "$steps" -lt "$limit" ]; do
    if [ "$candidate" -lt 65535 ]; then
      candidate="$((candidate + 1))"
    else
      return 1
    fi

    if is_control_server_running "$candidate"; then
      echo "$candidate"
      return 0
    fi

    if ! is_port_in_use "$candidate"; then
      echo "$candidate"
      return 0
    fi

    steps="$((steps + 1))"
  done

  return 1
}

confirm_stop_occupied_port() {
  local port="$1"
  local answer
  while true; do
    read -r -p "Port ${port} is occupied. Stop occupying process and use this port? [y/N]: " answer || true
    answer="${answer:-N}"
    case "${answer}" in
      y|Y|yes|YES)
        return 0
        ;;
      n|N|no|NO)
        return 1
        ;;
      *)
        echo "[ERROR] please answer y or n"
        ;;
    esac
  done
}

stop_port_listener() {
  local port="$1"
  local pids pid
  local remaining

  pids="$(list_port_listener_pids "${port}")"
  if [ -z "${pids}" ]; then
    return 0
  fi

  echo "[launch] stopping listener(s) on port ${port}: $(printf '%s' "${pids}" | tr '\n' ' ' | sed 's/[[:space:]]\+$//')"
  for pid in ${pids}; do
    kill "${pid}" >/dev/null 2>&1 || true
  done

  for _ in $(seq 1 12); do
    if ! is_port_in_use "${port}"; then
      return 0
    fi
    sleep 0.25
  done

  remaining="$(list_port_listener_pids "${port}")"
  if [ -n "${remaining}" ]; then
    echo "[launch] force-stopping listener(s) on port ${port}: $(printf '%s' "${remaining}" | tr '\n' ' ' | sed 's/[[:space:]]\+$//')"
    for pid in ${remaining}; do
      kill -9 "${pid}" >/dev/null 2>&1 || true
    done
  fi

  for _ in $(seq 1 12); do
    if ! is_port_in_use "${port}"; then
      return 0
    fi
    sleep 0.25
  done

  echo "[WARN] port ${port} is still in use after stop attempt."
  return 1
}

preferred_port="${LAUNCH_PORT:-$DEFAULT_PORT}"
port="${preferred_port}"
stable_fallback_port="$(read_saved_control_server_port || true)"
if [ "${stable_fallback_port}" = "${preferred_port}" ]; then
  stable_fallback_port=""
fi

if [ "${LAUNCH_PROMPT_PORT}" = "1" ] && [ "${IS_INTERACTIVE}" -eq 1 ]; then
  port_input=""
  read -r -p "Dashboard/Setup port [${port}]: " port_input || true
  if [ -n "${port_input}" ]; then
    port="${port_input}"
    preferred_port="${port_input}"
  fi
else
  echo "[launch] using port ${port} (set LAUNCH_PROMPT_PORT=1 to prompt)"
fi

if ! is_valid_port "${port}"; then
  echo "[ERROR] port must be between 1 and 65535" >&2
  exit 1
fi

if ! is_valid_port "${preferred_port}"; then
  echo "[ERROR] preferred port must be between 1 and 65535" >&2
  exit 1
fi

while is_port_in_use "$port"; do
  if is_control_server_running "$port"; then
    echo "[WARN] config server is already running on this port: http://127.0.0.1:${port}/setup"
    echo "[launch] keeping existing config server: http://127.0.0.1:${port}/setup"
    persist_control_server_port "${port}" "${preferred_port}"
    exit 0
  fi

  echo "[WARN] port ${port} is already in use."
  print_port_listener "$port"

  if [ "${IS_INTERACTIVE}" -eq 1 ]; then
    if confirm_stop_occupied_port "${port}"; then
      if stop_port_listener "${port}"; then
        continue
      fi
      echo "[WARN] unable to free port ${port}; choose another port."
    fi
  fi

  if [ "${IS_INTERACTIVE}" -ne 1 ]; then
    auto_port=""
    auto_port_source="scan"

    if [ "${port}" = "${preferred_port}" ] && [ -n "${stable_fallback_port}" ]; then
      if is_control_server_running "${stable_fallback_port}"; then
        echo "[WARN] config server is already running on stable fallback port: http://127.0.0.1:${stable_fallback_port}/setup"
        echo "[launch] keeping existing config server: http://127.0.0.1:${stable_fallback_port}/setup"
        persist_control_server_port "${stable_fallback_port}" "${preferred_port}"
        exit 0
      fi

      if ! is_port_in_use "${stable_fallback_port}"; then
        auto_port="${stable_fallback_port}"
        auto_port_source="stable"
      else
        echo "[WARN] stable fallback port ${stable_fallback_port} is occupied; scanning for a new fallback."
      fi
    fi

    if [ -z "${auto_port}" ]; then
      auto_port="$(find_next_available_port "${preferred_port}" "$LAUNCH_PORT_SCAN_LIMIT" || true)"
      auto_port_source="scan"
    fi

    if [ -n "${auto_port}" ]; then
      if is_control_server_running "${auto_port}"; then
        echo "[WARN] config server is already running on auto-selected port: http://127.0.0.1:${auto_port}/setup"
        echo "[launch] keeping existing config server: http://127.0.0.1:${auto_port}/setup"
        persist_control_server_port "${auto_port}" "${preferred_port}"
        exit 0
      fi

      if [ "${auto_port_source}" = "stable" ]; then
        echo "[launch] preferred port ${preferred_port} occupied; reusing stable fallback port ${auto_port}"
      else
        echo "[launch] preferred port ${preferred_port} occupied; selected fallback port ${auto_port}"
      fi
      port="${auto_port}"
      stable_fallback_port="${auto_port}"
      continue
    fi
    echo "[ERROR] no available port found after ${LAUNCH_PORT_SCAN_LIMIT} attempts from ${preferred_port}" >&2
    exit 1
  fi

  suggest_port="${port}"
  if [ "${port}" -lt 65535 ]; then
    suggest_port="$((port + 1))"
  fi

  next_port=""
  read -r -p "Choose another port [${suggest_port}]: " next_port || true
  next_port="${next_port:-$suggest_port}"

  if ! is_valid_port "${next_port}"; then
    echo "[ERROR] port must be between 1 and 65535" >&2
    continue
  fi

  port="$next_port"
done

persist_control_server_port "${port}" "${preferred_port}"
echo "[launch] starting config server on http://127.0.0.1:${port}/setup"
exec python3 "${ROOT_DIR}/scripts/control_server.py" --port "${port}"
