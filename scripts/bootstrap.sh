#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

PROVIDER_NAME=""
AUTH_CHOICE=""
AUTH_KEY_FLAG=""
AUTH_KEY_VALUE=""
USE_CUSTOM_PROVIDER=0
CUSTOM_COMPATIBILITY=""
CUSTOM_BASE_URL=""
CUSTOM_MODEL_ID=""
CUSTOM_PROVIDER_ID=""
CUSTOM_API_KEY=""
MODEL_PRIMARY_VALUE=""

prompt_default() {
  local msg="$1"
  local def="$2"
  local val
  read -r -p "${msg} [${def}]: " val
  if [ -z "${val}" ]; then
    printf '%s' "${def}"
  else
    printf '%s' "${val}"
  fi
}

prompt_required() {
  local msg="$1"
  local val
  while true; do
    read -r -p "${msg}: " val
    if [ -n "${val}" ]; then
      printf '%s' "${val}"
      return
    fi
    echo "This field is required."
  done
}

prompt_secret_required() {
  local msg="$1"
  local val
  while true; do
    read -r -s -p "${msg}: " val
    echo
    if [ -n "${val}" ]; then
      printf '%s' "${val}"
      return
    fi
    echo "This field is required."
  done
}

prompt_secret_optional() {
  local msg="$1"
  local val
  read -r -s -p "${msg} (leave blank if none): " val
  echo
  printf '%s' "${val}"
}

prompt_secret_with_default() {
  local msg="$1"
  local def="${2:-}"
  local val
  if [ -n "${def}" ]; then
    read -r -s -p "${msg} (press Enter to reuse current value): " val
    echo
    if [ -z "${val}" ]; then
      printf '%s' "${def}"
    else
      printf '%s' "${val}"
    fi
  else
    prompt_secret_required "${msg}"
  fi
}

confirm_yes() {
  local msg="$1"
  local ans
  read -r -p "${msg} [Y/n]: " ans
  case "${ans}" in
    ""|Y|y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

escape_sq() {
  printf '%s' "$1" | sed "s/'/'\"'\"'/g"
}

write_kv() {
  local key="$1"
  local val="$2"
  printf "%s='%s'\n" "${key}" "$(escape_sq "${val}")" >> "${ENV_FILE}"
}

ensure_cmd() {
  local cmd="$1"
  local install_name="${2:-$1}"
  if command -v "${cmd}" >/dev/null 2>&1; then
    return 0
  fi

  echo "[missing] ${cmd}"
  if command -v brew >/dev/null 2>&1; then
    if confirm_yes "Install ${install_name} via brew now?"; then
      brew install "${install_name}"
      return 0
    fi
  fi

  echo "Please install ${cmd} manually and rerun." >&2
  exit 1
}

slugify() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g; s/-\{2,\}/-/g; s/^-//; s/-$//'
}

set_standard_provider() {
  PROVIDER_NAME="$1"
  AUTH_CHOICE="$2"
  AUTH_KEY_FLAG="$3"
  USE_CUSTOM_PROVIDER=0
  CUSTOM_COMPATIBILITY=""
  CUSTOM_BASE_URL=""
  CUSTOM_MODEL_ID=""
  CUSTOM_PROVIDER_ID=""
  CUSTOM_API_KEY=""
  MODEL_PRIMARY_VALUE=""
}

set_custom_provider_preset() {
  PROVIDER_NAME="$1"
  AUTH_CHOICE="custom-api-key"
  AUTH_KEY_FLAG=""
  USE_CUSTOM_PROVIDER=1
  CUSTOM_COMPATIBILITY="$2"
  CUSTOM_BASE_URL="$3"
  CUSTOM_MODEL_ID="$4"
  CUSTOM_PROVIDER_ID="$5"
  CUSTOM_API_KEY=""
  MODEL_PRIMARY_VALUE="${CUSTOM_PROVIDER_ID}/${CUSTOM_MODEL_ID}"
}

set_custom_provider_interactive() {
  local display_name="$1"
  local compatibility="$2"
  local default_base_url="$3"
  local default_model_id="$4"

  PROVIDER_NAME="${display_name}"
  AUTH_CHOICE="custom-api-key"
  AUTH_KEY_FLAG=""
  USE_CUSTOM_PROVIDER=1

  CUSTOM_COMPATIBILITY="${compatibility}"
  CUSTOM_BASE_URL="$(prompt_default "Custom base URL" "${default_base_url}")"
  CUSTOM_MODEL_ID="$(prompt_default "Custom model id" "${default_model_id}")"
  CUSTOM_PROVIDER_ID="$(prompt_default "Custom provider id" "$(slugify "${display_name}")")"
  CUSTOM_API_KEY=""
  MODEL_PRIMARY_VALUE="${CUSTOM_PROVIDER_ID}/${CUSTOM_MODEL_ID}"
}

provider_select() {
  echo
  echo "Choose model provider:"
  echo " 1) OpenAI"
  echo " 2) Anthropic"
  echo " 3) Gemini"
  echo " 4) Moonshot (Kimi)"
  echo " 5) ZAI"
  echo " 6) MiniMax"
  echo " 7) Qianfan (Baidu)"
  echo " 8) Volcengine"
  echo " 9) BytePlus"
  echo "10) Xiaomi"
  echo "11) DeepSeek (preset, OpenAI-compatible)"
  echo "12) Qwen / DashScope (preset, OpenAI-compatible)"
  echo "13) Custom self-hosted (OpenAI-compatible)"
  echo "14) Custom self-hosted (Anthropic-compatible)"

  local c
  while true; do
    read -r -p "Select [1-14]: " c
    case "${c}" in
      1) set_standard_provider "OpenAI" "openai-api-key" "--openai-api-key"; return ;;
      2) set_standard_provider "Anthropic" "anthropic-api-key" "--anthropic-api-key"; return ;;
      3) set_standard_provider "Gemini" "gemini-api-key" "--gemini-api-key"; return ;;
      4) set_standard_provider "Moonshot" "moonshot-api-key" "--moonshot-api-key"; return ;;
      5) set_standard_provider "ZAI" "zai-api-key" "--zai-api-key"; return ;;
      6) set_standard_provider "MiniMax" "minimax-api" "--minimax-api-key"; return ;;
      7) set_standard_provider "Qianfan" "qianfan-api-key" "--qianfan-api-key"; return ;;
      8) set_standard_provider "Volcengine" "volcengine-api-key" "--volcengine-api-key"; return ;;
      9) set_standard_provider "BytePlus" "byteplus-api-key" "--byteplus-api-key"; return ;;
      10) set_standard_provider "Xiaomi" "xiaomi-api-key" "--xiaomi-api-key"; return ;;
      11) set_custom_provider_preset "DeepSeek" "openai" "https://api.deepseek.com/v1" "deepseek-chat" "deepseek"; return ;;
      12) set_custom_provider_preset "Qwen" "openai" "https://dashscope.aliyuncs.com/compatible-mode/v1" "qwen-plus" "qwen"; return ;;
      13) set_custom_provider_interactive "custom-openai" "openai" "http://127.0.0.1:8000/v1" "gpt-4o-mini"; return ;;
      14) set_custom_provider_interactive "custom-anthropic" "anthropic" "http://127.0.0.1:8000" "claude-3-5-sonnet"; return ;;
      *) echo "Invalid choice." ;;
    esac
  done
}

collect_provider_auth() {
  if [ "${USE_CUSTOM_PROVIDER}" -eq 1 ]; then
    if [ -n "${CUSTOM_BASE_URL}" ] && [ -n "${CUSTOM_MODEL_ID}" ] && [ -n "${CUSTOM_PROVIDER_ID}" ]; then
      echo "Selected ${PROVIDER_NAME}: ${CUSTOM_BASE_URL} (${CUSTOM_MODEL_ID})"
      if confirm_yes "Override custom base/model/provider values?"; then
        CUSTOM_BASE_URL="$(prompt_default "Custom base URL" "${CUSTOM_BASE_URL}")"
        CUSTOM_MODEL_ID="$(prompt_default "Custom model id" "${CUSTOM_MODEL_ID}")"
        CUSTOM_PROVIDER_ID="$(prompt_default "Custom provider id" "${CUSTOM_PROVIDER_ID}")"
      fi
    else
      CUSTOM_BASE_URL="$(prompt_required "Custom base URL")"
      CUSTOM_MODEL_ID="$(prompt_required "Custom model id")"
      CUSTOM_PROVIDER_ID="$(prompt_default "Custom provider id" "custom-provider")"
    fi

    CUSTOM_API_KEY="$(prompt_secret_optional "Custom API key")"
    MODEL_PRIMARY_VALUE="${CUSTOM_PROVIDER_ID}/${CUSTOM_MODEL_ID}"
    AUTH_KEY_VALUE=""
  else
    AUTH_KEY_VALUE="$(prompt_secret_required "Enter ${PROVIDER_NAME} API key")"
  fi
}

run_onboard() {
  local profile="$1"
  local workspace_dir="$2"

  local -a cmd
  cmd=(
    openclaw --profile "${profile}" onboard
    --non-interactive --accept-risk
    --mode local --flow quickstart
    --auth-choice "${AUTH_CHOICE}"
  )

  if [ "${USE_CUSTOM_PROVIDER}" -eq 1 ]; then
    cmd+=(
      --custom-compatibility "${CUSTOM_COMPATIBILITY}"
      --custom-base-url "${CUSTOM_BASE_URL}"
      --custom-model-id "${CUSTOM_MODEL_ID}"
      --custom-provider-id "${CUSTOM_PROVIDER_ID}"
    )
    if [ -n "${CUSTOM_API_KEY}" ]; then
      cmd+=(--custom-api-key "${CUSTOM_API_KEY}")
    fi
  else
    cmd+=("${AUTH_KEY_FLAG}" "${AUTH_KEY_VALUE}")
  fi

  cmd+=(
    --skip-channels --skip-skills --skip-ui --skip-daemon --skip-health
    --workspace "${workspace_dir}"
  )

  "${cmd[@]}"
}

profile_state_dir() {
  local profile="$1"
  if [ "${profile}" = "default" ] || [ "${profile}" = "main" ]; then
    printf '%s' "${HOME}/.openclaw"
  else
    printf '%s' "${HOME}/.openclaw-${profile}"
  fi
}

main() {
  echo "=== OpenClaw Company Kit Bootstrap ==="
  echo "Note: 7 role agents map to 2 Feishu apps by default (hot-search + ai-tech), not 7 separate apps."

  ensure_cmd openclaw openclaw
  ensure_cmd jq jq
  ensure_cmd python3 python
  ensure_cmd rsync rsync

  local profile company_name project_path project_repo group_id
  local hot_account_id hot_bot_name hot_app_id hot_app_secret
  local ai_account_id ai_bot_name ai_app_id ai_app_secret
  local gh_token dashboard_port
  local with_ai_account
  local local_cfg
  local default_group_id default_hot_account_id default_hot_bot_name default_hot_app_id default_hot_app_secret
  local default_ai_account_id default_ai_bot_name default_ai_app_id default_ai_app_secret

  default_group_id="oc_replace_with_group_id"
  default_hot_account_id="hot-search"
  default_hot_bot_name="小龙虾 1 号"
  default_hot_app_id=""
  default_hot_app_secret=""
  default_ai_account_id="ai-tech"
  default_ai_bot_name="小龙虾 2 号"
  default_ai_app_id=""
  default_ai_app_secret=""

  local_cfg="$(openclaw config file 2>/dev/null || true)"
  if [ -n "${local_cfg}" ]; then
    eval "local_cfg=${local_cfg}"
  fi
  if [ -n "${local_cfg}" ] && [ -f "${local_cfg}" ]; then
    default_group_id="$(jq -r '.bindings[]? | select(.agentId=="rd-company" and .match.channel=="feishu") | .match.peer.id // empty' "${local_cfg}" | head -n1 || true)"
    default_hot_account_id="$(jq -r '.bindings[]? | select(.agentId=="rd-company" and .match.channel=="feishu") | .match.accountId // empty' "${local_cfg}" | head -n1 || true)"
    default_ai_account_id="$(jq -r '.bindings[]? | select(.agentId=="ai-tech" and .match.channel=="feishu") | .match.accountId // empty' "${local_cfg}" | head -n1 || true)"

    [ -n "${default_group_id}" ] || default_group_id="oc_replace_with_group_id"
    [ -n "${default_hot_account_id}" ] || default_hot_account_id="hot-search"
    [ -n "${default_ai_account_id}" ] || default_ai_account_id="ai-tech"

    default_hot_bot_name="$(jq -r --arg a "${default_hot_account_id}" '.channels.feishu.accounts[$a].botName // empty' "${local_cfg}" || true)"
    default_hot_app_id="$(jq -r --arg a "${default_hot_account_id}" '.channels.feishu.accounts[$a].appId // empty' "${local_cfg}" || true)"
    default_hot_app_secret="$(jq -r --arg a "${default_hot_account_id}" '.channels.feishu.accounts[$a].appSecret // empty' "${local_cfg}" || true)"

    default_ai_bot_name="$(jq -r --arg a "${default_ai_account_id}" '.channels.feishu.accounts[$a].botName // empty' "${local_cfg}" || true)"
    default_ai_app_id="$(jq -r --arg a "${default_ai_account_id}" '.channels.feishu.accounts[$a].appId // empty' "${local_cfg}" || true)"
    default_ai_app_secret="$(jq -r --arg a "${default_ai_account_id}" '.channels.feishu.accounts[$a].appSecret // empty' "${local_cfg}" || true)"

    [ -n "${default_hot_bot_name}" ] || default_hot_bot_name="小龙虾 1 号"
    [ -n "${default_ai_bot_name}" ] || default_ai_bot_name="小龙虾 2 号"
  fi

  profile="$(prompt_default "OpenClaw profile" "company")"
  company_name="$(prompt_default "Company name" "OpenClaw Company")"
  project_path="$(prompt_default "Project path" "/path/to/your-project")"
  project_repo="$(prompt_default "Project repo slug (owner/repo)" "your-org/your-repo")"

  provider_select
  collect_provider_auth

  group_id="$(prompt_default "Feishu group ID (oc_...)" "${default_group_id}")"
  while [ -z "${group_id}" ] || [ "${group_id}" = "oc_replace_with_group_id" ]; do
    echo "Feishu group ID cannot be empty."
    group_id="$(prompt_required "Feishu group ID (oc_...)")"
  done

  hot_account_id="$(prompt_default "Feishu hot account id" "${default_hot_account_id}")"
  hot_bot_name="$(prompt_default "Feishu hot bot name" "${default_hot_bot_name}")"
  hot_app_id="$(prompt_default "Feishu hot app id (cli_...)" "${default_hot_app_id}")"
  while [ -z "${hot_app_id}" ]; do
    echo "Feishu hot app id cannot be empty."
    hot_app_id="$(prompt_required "Feishu hot app id (cli_...)")"
  done

  hot_app_secret="$(prompt_secret_with_default "Feishu hot app secret" "${default_hot_app_secret}")"
  while [ -z "${hot_app_secret}" ]; do
    echo "Feishu hot app secret cannot be empty."
    hot_app_secret="$(prompt_secret_required "Feishu hot app secret")"
  done

  if confirm_yes "Configure second Feishu account (ai-tech, recommended for 7-role setup)?"; then
    with_ai_account=1
    ai_account_id="$(prompt_default "Feishu ai account id" "${default_ai_account_id}")"
    ai_bot_name="$(prompt_default "Feishu ai bot name" "${default_ai_bot_name}")"
    ai_app_id="$(prompt_default "Feishu ai app id (cli_...)" "${default_ai_app_id}")"
    while [ -z "${ai_app_id}" ]; do
      echo "Feishu ai app id cannot be empty."
      ai_app_id="$(prompt_required "Feishu ai app id (cli_...)")"
    done
    ai_app_secret="$(prompt_secret_with_default "Feishu ai app secret" "${default_ai_app_secret}")"
    while [ -z "${ai_app_secret}" ]; do
      echo "Feishu ai app secret cannot be empty."
      ai_app_secret="$(prompt_secret_required "Feishu ai app secret")"
    done
  else
    with_ai_account=0
    ai_account_id="ai-tech"
    ai_bot_name="小龙虾 2 号"
    ai_app_id=""
    ai_app_secret=""
  fi

  if confirm_yes "Set GH_TOKEN for GitHub issue sync now?"; then
    gh_token="$(prompt_secret_required "GH_TOKEN")"
  else
    gh_token=""
  fi

  dashboard_port="$(prompt_default "Dashboard port" "8788")"

  local state_dir workspace_dir profile_cfg
  state_dir="$(profile_state_dir "${profile}")"
  workspace_dir="${state_dir}/workspace"

  echo
  echo "[1/4] Initialize OpenClaw profile (${profile})"
  if [ -f "${state_dir}/openclaw.json" ]; then
    echo "profile config exists: ${state_dir}/openclaw.json"
    if confirm_yes "Re-run onboard to refresh model credentials?"; then
      run_onboard "${profile}" "${workspace_dir}"
    fi
  else
    run_onboard "${profile}" "${workspace_dir}"
  fi

  profile_cfg="$(openclaw --profile "${profile}" config file)"

  echo "[2/4] Write .env"
  if [ -f "${ENV_FILE}" ]; then
    cp "${ENV_FILE}" "${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"
  fi
  : > "${ENV_FILE}"

  write_kv OPENCLAW_PROFILE "${profile}"
  write_kv SOURCE_OPENCLAW_CONFIG "${profile_cfg}"
  write_kv COMPANY_NAME "${company_name}"
  write_kv PROJECT_PATH "${project_path}"
  write_kv PROJECT_REPO "${project_repo}"
  write_kv GROUP_ID "${group_id}"

  write_kv FEISHU_HOT_ACCOUNT_ID "${hot_account_id}"
  write_kv FEISHU_HOT_BOT_NAME "${hot_bot_name}"
  write_kv FEISHU_HOT_APP_ID "${hot_app_id}"
  write_kv FEISHU_HOT_APP_SECRET "${hot_app_secret}"

  write_kv FEISHU_AI_ACCOUNT_ID "${ai_account_id}"
  write_kv FEISHU_AI_BOT_NAME "${ai_bot_name}"
  if [ "${with_ai_account}" -eq 1 ]; then
    write_kv FEISHU_AI_APP_ID "${ai_app_id}"
    write_kv FEISHU_AI_APP_SECRET "${ai_app_secret}"
  else
    write_kv FEISHU_AI_APP_ID ""
    write_kv FEISHU_AI_APP_SECRET ""
  fi

  write_kv GH_TOKEN "${gh_token}"
  write_kv MODEL_PRIMARY "${MODEL_PRIMARY_VALUE}"
  write_kv DASHBOARD_PORT "${dashboard_port}"

  echo "[3/4] Run installer"
  (cd "${ROOT_DIR}" && bash scripts/install.sh)

  echo "[4/4] Start services"
  (cd "${ROOT_DIR}" && bash scripts/start.sh)

  if confirm_yes "Run healthcheck now?"; then
    (cd "${ROOT_DIR}" && bash scripts/healthcheck.sh)
  fi

  echo
  echo "Bootstrap done."
  echo "Provider: ${PROVIDER_NAME}"
  echo "Dashboard: http://127.0.0.1:${dashboard_port}"
  echo "Profile: ${profile}"
}

main "$@"
