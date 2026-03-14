#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# shellcheck source=./_common.sh
source "${ROOT_DIR}/scripts/_common.sh"

load_env
DEFAULT_PORT="${DASHBOARD_PORT:-8788}"

echo "环境检测："
check_cmds

# GH_TOKEN / gh auth 软检测（非阻塞）
if command -v gh >/dev/null 2>&1; then
  if [ -z "${GH_TOKEN:-}" ] && ! gh auth status >/dev/null 2>&1; then
    echo "[WARN] GitHub 认证未配置（gh-issues skill 将不可用）"
  fi
fi

echo ""

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
      return 1
      ;;
  esac
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

port=""
read -r -p "Dashboard/Setup port [${DEFAULT_PORT}]: " port || true
port="${port:-$DEFAULT_PORT}"

if ! [[ "$port" =~ ^[0-9]+$ ]]; then
  echo "[ERROR] port must be a number" >&2
  exit 1
fi

if [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
  echo "[ERROR] port must be between 1 and 65535" >&2
  exit 1
fi

while is_port_in_use "$port"; do
  port_has_control_server=0
  if is_control_server_running "$port"; then
    port_has_control_server=1
    echo "[WARN] config server is already running on this port: http://127.0.0.1:${port}/setup"
  fi

  echo "[WARN] port ${port} is already in use."
  print_port_listener "$port"

  if confirm_stop_occupied_port "${port}"; then
    if stop_port_listener "${port}"; then
      continue
    fi
    echo "[WARN] unable to free port ${port}; choose another port."
  else
    if [ "${port_has_control_server}" -eq 1 ]; then
      echo "[launch] keeping existing config server: http://127.0.0.1:${port}/setup"
      exit 0
    fi
  fi

  suggest_port="${port}"
  if [ "${port}" -lt 65535 ]; then
    suggest_port="$((port + 1))"
  fi

  next_port=""
  read -r -p "Choose another port [${suggest_port}]: " next_port || true
  next_port="${next_port:-$suggest_port}"

  if ! [[ "$next_port" =~ ^[0-9]+$ ]]; then
    echo "[ERROR] port must be a number" >&2
    continue
  fi

  if [ "$next_port" -lt 1 ] || [ "$next_port" -gt 65535 ]; then
    echo "[ERROR] port must be between 1 and 65535" >&2
    continue
  fi

  port="$next_port"
done

echo "[launch] starting config server on http://127.0.0.1:${port}/setup"
exec python3 "${ROOT_DIR}/scripts/control_server.py" --port "${port}"
