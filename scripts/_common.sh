#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

load_env() {
  local env_file="${ROOT_DIR}/.env"
  if [ -f "${env_file}" ]; then
    set -a
    # shellcheck source=/dev/null
    source "${env_file}"
    set +a
  fi

  OPENCLAW_PROFILE="${OPENCLAW_PROFILE:-company}"
  COMPANY_NAME="${COMPANY_NAME:-OpenClaw Company}"
  PROJECT_PATH="${PROJECT_PATH:-/path/to/your-project}"
  PROJECT_REPO="${PROJECT_REPO:-your-org/your-repo}"

  GROUP_ID="${GROUP_ID:-}"

  FEISHU_HOT_ACCOUNT_ID="${FEISHU_HOT_ACCOUNT_ID:-hot-search}"
  FEISHU_HOT_BOT_NAME="${FEISHU_HOT_BOT_NAME:-小龙虾 1 号}"
  FEISHU_HOT_APP_ID="${FEISHU_HOT_APP_ID:-}"
  FEISHU_HOT_APP_SECRET="${FEISHU_HOT_APP_SECRET:-}"

  FEISHU_AI_ACCOUNT_ID="${FEISHU_AI_ACCOUNT_ID:-ai-tech}"
  FEISHU_AI_BOT_NAME="${FEISHU_AI_BOT_NAME:-小龙虾 2 号}"
  FEISHU_AI_APP_ID="${FEISHU_AI_APP_ID:-}"
  FEISHU_AI_APP_SECRET="${FEISHU_AI_APP_SECRET:-}"

  GH_TOKEN="${GH_TOKEN:-}"
  MODEL_PRIMARY="${MODEL_PRIMARY:-}"

  DASHBOARD_PORT="${DASHBOARD_PORT:-8788}"

  if [ "${OPENCLAW_PROFILE}" = "default" ] || [ "${OPENCLAW_PROFILE}" = "main" ]; then
    PROFILE_DIR="${HOME}/.openclaw"
    OPENCLAW_ARGS=()
  else
    PROFILE_DIR="${HOME}/.openclaw-${OPENCLAW_PROFILE}"
    OPENCLAW_ARGS=(--profile "${OPENCLAW_PROFILE}")
  fi

  TARGET_WORKSPACE="${PROFILE_DIR}/workspace"
  TARGET_AGENTS_DIR="${PROFILE_DIR}/agents"
  TARGET_DASHBOARD_DIR="${TARGET_WORKSPACE}/rd-dashboard"
}

required_var() {
  local key="$1"
  local val="${!key:-}"
  if [ -z "${val}" ]; then
    echo "[ERROR] missing required env: ${key}" >&2
    exit 1
  fi
}

check_cmds() {
  local missing=0
  for c in openclaw jq python3 rsync; do
    if ! command -v "${c}" >/dev/null 2>&1; then
      echo "[ERROR] missing command: ${c}" >&2
      missing=1
    fi
  done
  if [ "${missing}" -ne 0 ]; then
    exit 1
  fi
}

ocp() {
  openclaw "${OPENCLAW_ARGS[@]}" "$@"
}

expand_tilde_path() {
  local p="$1"
  if [[ "${p}" == ~* ]]; then
    eval "echo ${p}"
  else
    echo "${p}"
  fi
}

now_local() {
  date '+%Y-%m-%d %H:%M:%S'
}
