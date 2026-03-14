#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"
load_env

TARGET_CONFIG="${PROFILE_DIR}/openclaw.json"

sanitize_legacy_config() {
  local cfg_path="$1"
  [ -f "${cfg_path}" ] || return 0
  command -v jq >/dev/null 2>&1 || return 0

  local tmp_cfg
  tmp_cfg="$(mktemp)"
  if jq '
      if (.agents.list | type) == "array" then
        .agents.list |= map(
          if (.subagents | type) == "object" then
            .subagents |= del(.maxSpawnDepth)
          else
            .
          end
        )
      else
        .
      end
    ' "${cfg_path}" > "${tmp_cfg}"; then
    if ! cmp -s "${cfg_path}" "${tmp_cfg}"; then
      mv "${tmp_cfg}" "${cfg_path}"
      echo "[onboard] removed deprecated subagents.maxSpawnDepth from existing config"
    else
      rm -f "${tmp_cfg}" >/dev/null 2>&1 || true
    fi
  else
    rm -f "${tmp_cfg}" >/dev/null 2>&1 || true
  fi
}

ONBOARD_FLAGS=()
CUSTOM_BASE_URL_INPUT="${CUSTOM_BASE_URL:-}"
if [ -n "${CUSTOM_BASE_URL_INPUT}" ]; then
  warn_model_base_url "${CUSTOM_BASE_URL_INPUT}" "${CUSTOM_PROVIDER_ID:-custom}" "onboard"
  ONBOARD_FLAGS+=(--custom-base-url "${CUSTOM_BASE_URL_INPUT}")
  ONBOARD_FLAGS+=(--custom-model-id "${CUSTOM_MODEL_ID}")
  ONBOARD_FLAGS+=(--custom-provider-id "${CUSTOM_PROVIDER_ID}")
  [ -n "${CUSTOM_COMPATIBILITY:-}" ] && ONBOARD_FLAGS+=(--custom-compatibility "${CUSTOM_COMPATIBILITY}")
  if [ -n "${CUSTOM_API_KEY:-}" ]; then
    ONBOARD_FLAGS+=(--custom-api-key "${CUSTOM_API_KEY}")
  fi
fi

if [ -f "${TARGET_CONFIG}" ]; then
  sanitize_legacy_config "${TARGET_CONFIG}"
  if [ -n "${CUSTOM_API_KEY:-}" ] && [ -n "${CUSTOM_BASE_URL:-}" ]; then
    echo "[onboard] config exists, updating custom provider credentials..."
    ocp onboard \
      --non-interactive --accept-risk \
      --mode local --flow quickstart \
      --skip-channels --skip-skills --skip-ui --skip-daemon --skip-health \
      --workspace "${PROFILE_DIR}/workspace" \
      "${ONBOARD_FLAGS[@]}" || {
        echo "[onboard] WARN: credential update failed, continuing with existing config" >&2
      }
    echo "[onboard] OK"
    exit 0
  fi
  echo "[onboard] config exists: ${TARGET_CONFIG}, skipping"
  exit 0
fi

if [ -n "${SOURCE_OPENCLAW_CONFIG:-}" ]; then
  SRC_PATH="$(expand_tilde_path "${SOURCE_OPENCLAW_CONFIG}")"
  if [ -f "${SRC_PATH}" ]; then
    mkdir -p "${PROFILE_DIR}"
    cp "${SRC_PATH}" "${TARGET_CONFIG}"
    echo "[onboard] copied config from ${SRC_PATH}"
    echo "[onboard] OK"
    exit 0
  fi
fi

if ! ocp onboard \
  --non-interactive --accept-risk \
  --mode local --flow quickstart \
  --skip-channels --skip-skills --skip-ui --skip-daemon --skip-health \
  --workspace "${PROFILE_DIR}/workspace" \
  ${ONBOARD_FLAGS[@]+"${ONBOARD_FLAGS[@]}"}; then
  echo "[onboard] ERROR: openclaw onboard failed" >&2
  exit 1
fi

echo "[onboard] OK"
