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

echo "[launch] starting config server on http://127.0.0.1:${port}/setup"
exec python3 "${ROOT_DIR}/scripts/control_server.py" --port "${port}"
