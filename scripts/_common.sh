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
  WORKFLOW_TEMPLATE="${WORKFLOW_TEMPLATE:-default}"

  # Accept either "owner/repo" or a GitHub URL and normalize to "owner/repo"
  # because downstream gh api calls require that slug form.
  if [[ "${PROJECT_REPO}" =~ ^https?://github\.com/([^/]+)/([^/?#]+)(\.git)?/?$ ]]; then
    PROJECT_REPO="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  elif [[ "${PROJECT_REPO}" =~ ^git@github\.com:([^/]+)/([^/?#]+)(\.git)?$ ]]; then
    PROJECT_REPO="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  elif [[ "${PROJECT_REPO}" =~ ^github\.com/([^/]+)/([^/?#]+)(\.git)?/?$ ]]; then
    PROJECT_REPO="${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  fi
  PROJECT_REPO="${PROJECT_REPO%.git}"

  GROUP_ID="${GROUP_ID:-}"

  FEISHU_HOT_ACCOUNT_ID="${FEISHU_HOT_ACCOUNT_ID:-}"
  FEISHU_HOT_BOT_NAME="${FEISHU_HOT_BOT_NAME:-}"
  FEISHU_HOT_APP_ID="${FEISHU_HOT_APP_ID:-}"
  FEISHU_HOT_APP_SECRET="${FEISHU_HOT_APP_SECRET:-}"
  FEISHU_ALLOW_FROM="${FEISHU_ALLOW_FROM:-}"

  FEISHU_AI_ACCOUNT_ID="${FEISHU_AI_ACCOUNT_ID:-}"
  FEISHU_AI_BOT_NAME="${FEISHU_AI_BOT_NAME:-}"
  FEISHU_AI_APP_ID="${FEISHU_AI_APP_ID:-}"
  FEISHU_AI_APP_SECRET="${FEISHU_AI_APP_SECRET:-}"

  # Single-bot default: ai-tech is the only required external bot account.
  # Backward-compatible fallback: if older setups only filled FEISHU_HOT_*,
  # copy those values into FEISHU_AI_*.
  [ -n "${FEISHU_AI_ACCOUNT_ID}" ] || FEISHU_AI_ACCOUNT_ID="${FEISHU_HOT_ACCOUNT_ID:-ai-tech}"
  [ -n "${FEISHU_AI_BOT_NAME}" ] || FEISHU_AI_BOT_NAME="${FEISHU_HOT_BOT_NAME:-小龙虾 2 号}"
  [ -n "${FEISHU_AI_APP_ID}" ] || FEISHU_AI_APP_ID="${FEISHU_HOT_APP_ID:-}"
  [ -n "${FEISHU_AI_APP_SECRET}" ] || FEISHU_AI_APP_SECRET="${FEISHU_HOT_APP_SECRET:-}"

  # Keep legacy FEISHU_HOT_* populated for templates/scripts that still read them.
  [ -n "${FEISHU_HOT_ACCOUNT_ID}" ] || FEISHU_HOT_ACCOUNT_ID="${FEISHU_AI_ACCOUNT_ID}"
  [ -n "${FEISHU_HOT_BOT_NAME}" ] || FEISHU_HOT_BOT_NAME="${FEISHU_AI_BOT_NAME}"
  [ -n "${FEISHU_HOT_APP_ID}" ] || FEISHU_HOT_APP_ID="${FEISHU_AI_APP_ID}"
  [ -n "${FEISHU_HOT_APP_SECRET}" ] || FEISHU_HOT_APP_SECRET="${FEISHU_AI_APP_SECRET}"

  GH_TOKEN="${GH_TOKEN:-}"
  MODEL_PRIMARY="${MODEL_PRIMARY:-}"
  CUSTOM_BASE_URL="${CUSTOM_BASE_URL:-}"
  CUSTOM_API_KEY="${CUSTOM_API_KEY:-}"
  CUSTOM_MODEL_ID="${CUSTOM_MODEL_ID:-}"
  CUSTOM_PROVIDER_ID="${CUSTOM_PROVIDER_ID:-}"
  CUSTOM_COMPATIBILITY="${CUSTOM_COMPATIBILITY:-}"

  MODEL_SUBAGENT="${MODEL_SUBAGENT:-}"
  DISCORD_BOT_TOKEN="${DISCORD_BOT_TOKEN:-}"
  DISCORD_GUILD_ID="${DISCORD_GUILD_ID:-}"
  DISCORD_CHANNEL_ID="${DISCORD_CHANNEL_ID:-}"

  DASHBOARD_PORT="${DASHBOARD_PORT:-8788}"
  OPENCLAW_NODE_MIN_MAJOR="${OPENCLAW_NODE_MIN_MAJOR:-22}"
  OPENCLAW_ALLOW_NO_GH="${OPENCLAW_ALLOW_NO_GH:-0}"
  SYNC_PROJECT_GH_BRIDGE="${SYNC_PROJECT_GH_BRIDGE:-1}"
  SYNC_PROJECT_GH_BRIDGE_STRICT="${SYNC_PROJECT_GH_BRIDGE_STRICT:-0}"
  SYNC_PROJECT_GH_BRIDGE_ON_LAUNCH="${SYNC_PROJECT_GH_BRIDGE_ON_LAUNCH:-0}"

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
  local raw
  local major
  local min_major="${OPENCLAW_NODE_MIN_MAJOR:-22}"
  local gh_optional="${OPENCLAW_ALLOW_NO_GH:-0}"

  for c in openclaw node jq python3 rsync; do
    if ! command -v "${c}" >/dev/null 2>&1; then
      echo "[ERROR] missing command: ${c}" >&2
      missing=1
    fi
  done

  if ! command -v gh >/dev/null 2>&1; then
    if [ "${gh_optional}" = "1" ]; then
      echo "[WARN] missing command: gh (OPENCLAW_ALLOW_NO_GH=1, GitHub sync features will be degraded)"
    else
      echo "[ERROR] missing command: gh" >&2
      echo "        install gh: brew install gh (macOS) / sudo apt install gh (Ubuntu)" >&2
      echo "        temp bypass: OPENCLAW_ALLOW_NO_GH=1 bash scripts/launch.sh" >&2
      missing=1
    fi
  fi

  if command -v node >/dev/null 2>&1; then
    raw="$(node -v 2>/dev/null | head -n1)"
    major="${raw#v}"
    major="${major%%.*}"
    if ! [[ "${major}" =~ ^[0-9]+$ ]]; then
      echo "[ERROR] failed to parse node version: ${raw}" >&2
      missing=1
    elif [ "${major}" -lt "${min_major}" ]; then
      echo "[ERROR] node version ${raw} is below required major ${min_major}" >&2
      missing=1
    fi
  fi

  if [ "${missing}" -ne 0 ]; then
    exit 1
  fi
}

ocp() {
  # Avoid inheriting low-scope gateway tokens from parent processes.
  env -u OPENCLAW_GATEWAY_TOKEN openclaw "${OPENCLAW_ARGS[@]}" "$@"
}

sed_inplace() {
  if sed --version 2>/dev/null | grep -q GNU; then
    sed -i "$@"
  else
    sed -i '' "$@"
  fi
}

expand_tilde_path() {
  local p="$1"
  case "${p}" in
    "~")
      printf '%s\n' "${HOME}"
      ;;
    "~/"*)
      printf '%s\n' "${HOME}/${p#\~/}"
      ;;
    *)
      printf '%s\n' "${p}"
      ;;
  esac
}

extract_json_payload() {
  python3 -c '
import json
import sys

raw = sys.stdin.read()
decoder = json.JSONDecoder()
for idx, ch in enumerate(raw):
    if ch not in "{[":
        continue
    try:
        obj, _ = decoder.raw_decode(raw[idx:])
    except Exception:
        continue
    print(json.dumps(obj, ensure_ascii=False))
    raise SystemExit(0)
raise SystemExit(1)
'
}

gateway_error_has_auth_scope_issue() {
  local text
  text="$(printf '%s' "$*" | tr '[:upper:]' '[:lower:]')"
  if printf '%s' "${text}" | grep -Eq "missing scope: *operator\\.read|missing scope|device identity required"; then
    return 0
  fi
  return 1
}

detect_gateway_auth_scope_issue() {
  local status_raw status_json status_reachable status_error gateway_status_raw

  status_raw="$(ocp status --all --json 2>/dev/null || true)"
  status_json="$(printf '%s' "${status_raw}" | extract_json_payload 2>/dev/null || true)"
  if [ -n "${status_json}" ]; then
    status_reachable="$(printf '%s' "${status_json}" | jq -r '.gateway.reachable // false' 2>/dev/null || echo false)"
    status_error="$(printf '%s' "${status_json}" | jq -r '.gateway.error // ""' 2>/dev/null || true)"
    if [ "${status_reachable}" != "true" ] && gateway_error_has_auth_scope_issue "${status_error}"; then
      return 0
    fi
  fi

  gateway_status_raw="$(ocp gateway status 2>&1 || true)"
  if gateway_error_has_auth_scope_issue "${gateway_status_raw}"; then
    return 0
  fi

  return 1
}

attempt_gateway_auth_scope_repair() {
  local context="${1:-gateway}"

  echo "[${context}] detected gateway auth scope issue, running doctor --fix"
  if ! ocp doctor --fix --non-interactive --yes >/dev/null 2>&1; then
    echo "[WARN] ${context}: openclaw doctor --fix failed"
    return 1
  fi

  ocp gateway install --force >/dev/null 2>&1 || true
  if ocp gateway start >/dev/null 2>&1; then
    echo "[${context}] gateway auth scope repaired"
    return 0
  fi

  echo "[WARN] ${context}: gateway restart failed after doctor --fix"
  return 1
}

ensure_gateway_local_mode() {
  local cfg_path="${1:-${PROFILE_DIR}/openclaw.json}"
  local context="${2:-config}"
  local tmp_cfg

  [ -f "${cfg_path}" ] || return 0
  command -v jq >/dev/null 2>&1 || return 0

  tmp_cfg="$(mktemp)"
  if jq '
      (.gateway //= {}) |
      (if ((.gateway.mode? | type) != "string") or ((.gateway.mode? // "") == "") then
         .gateway.mode = "local"
       else
         .
       end)
    ' "${cfg_path}" > "${tmp_cfg}"; then
    if ! cmp -s "${cfg_path}" "${tmp_cfg}"; then
      mv "${tmp_cfg}" "${cfg_path}"
      echo "[${context}] ensured gateway.mode=local"
    else
      rm -f "${tmp_cfg}" >/dev/null 2>&1 || true
    fi
  else
    rm -f "${tmp_cfg}" >/dev/null 2>&1 || true
  fi
}

# Wait until gateway RPC probe reports ok (for use after gateway start).
wait_gateway_rpc_ready() {
  local timeout_sec="${1:-15}"
  local probe
  local i

  for ((i=0; i<timeout_sec; i++)); do
    probe="$(ocp gateway status 2>&1 || true)"
    if printf '%s' "${probe}" | grep -q 'RPC probe: ok'; then
      return 0
    fi
    sleep 1
  done
  return 1
}

warn_model_base_url() {
  local raw="${1:-}"
  local provider_id="${2:-unknown}"
  local source="${3:-config}"
  local trimmed

  trimmed="${raw#"${raw%%[![:space:]]*}"}"
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
  [ -n "${trimmed}" ] || return 0

  if [[ ! "${trimmed}" =~ ^https?:// ]]; then
    echo "[WARN] ${source}: provider=${provider_id} baseUrl may be invalid (expected http(s) URL): ${trimmed}" >&2
    return 0
  fi

  # Known pitfall: vendor docs may require /v1 suffix while users only configure domain root.
  if [[ "${trimmed%/}" =~ ^https?://([^/]+\.)?heiyucode\.com$ ]]; then
    echo "[WARN] ${source}: provider=${provider_id} baseUrl may be incomplete: ${trimmed}" >&2
    echo "[WARN] hint: try https://www.heiyucode.com/v1" >&2
  fi
}

now_local() {
  date '+%Y-%m-%d %H:%M:%S'
}
