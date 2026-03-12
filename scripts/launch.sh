#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_PORT="8788"

GREEN='\033[32m'
RED='\033[31m'
YELLOW='\033[33m'
RESET='\033[0m'

pass=0
fail=0

check_cmd() {
  local label="$1" cmd="$2"
  local ver
  if ver="$(command -v "$cmd" >/dev/null 2>&1 && "$cmd" --version 2>/dev/null | head -n1)"; then
    printf "  %-24s ${GREEN}✓${RESET} %s\n" "$label" "$ver"
    pass=$((pass + 1))
  else
    printf "  %-24s ${RED}✗${RESET} 未安装\n" "$label"
    fail=$((fail + 1))
  fi
}

check_node() {
  local label="Node.js ≥ 22"
  local raw major
  if ! command -v node >/dev/null 2>&1; then
    printf "  %-24s ${RED}✗${RESET} 未安装\n" "$label"
    fail=$((fail + 1))
    return
  fi
  raw="$(node -v 2>/dev/null | head -n1)"
  major="${raw#v}"
  major="${major%%.*}"
  if [ -n "$major" ] && [ "$major" -ge 22 ] 2>/dev/null; then
    printf "  %-24s ${GREEN}✓${RESET} %s\n" "$label" "$raw"
    pass=$((pass + 1))
  else
    printf "  %-24s ${RED}✗${RESET} %s (需要 ≥ 22)\n" "$label" "$raw"
    fail=$((fail + 1))
  fi
}

echo "环境检测："

check_node
check_cmd "openclaw CLI"  openclaw
check_cmd "jq"            jq
check_cmd "python3"       python3
check_cmd "rsync"         rsync
check_cmd "GitHub CLI"    gh

if [ "$fail" -gt 0 ]; then
  echo ""
  echo "请先安装缺失工具后重试。"
  exit 1
fi

# GH_TOKEN / gh auth 软检测（非阻塞）
if command -v gh >/dev/null 2>&1; then
  if [ -z "${GH_TOKEN:-}" ] && ! gh auth status >/dev/null 2>&1; then
    printf "\n  %-24s ${YELLOW}⚠${RESET} 未配置（gh-issues skill 将不可用）\n" "GitHub 认证"
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
