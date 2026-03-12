#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"
load_env

TARGET_CONFIG="${PROFILE_DIR}/openclaw.json"

if [ -f "${TARGET_CONFIG}" ]; then
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
  --workspace "${PROFILE_DIR}/workspace"; then
  echo "[onboard] ERROR: openclaw onboard failed" >&2
  exit 1
fi

echo "[onboard] OK"
