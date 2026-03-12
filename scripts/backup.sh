#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env

BACKUP_DIR="${ROOT_DIR}/backups"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
BACKUP_NAME="${OPENCLAW_PROFILE}_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

mkdir -p "${BACKUP_PATH}"

echo "[backup] profile: ${OPENCLAW_PROFILE}"
echo "[backup] target:  ${BACKUP_PATH}"

if [ -f "${PROFILE_DIR}/openclaw.json" ]; then
  cp "${PROFILE_DIR}/openclaw.json" "${BACKUP_PATH}/"
  echo "[backup] ✓ openclaw.json"
fi

if [ -f "${PROFILE_DIR}/exec-approvals.json" ]; then
  cp "${PROFILE_DIR}/exec-approvals.json" "${BACKUP_PATH}/"
  echo "[backup] ✓ exec-approvals.json"
fi

if [ -d "${TARGET_AGENTS_DIR}" ]; then
  mkdir -p "${BACKUP_PATH}/agents"
  for agent_dir in "${TARGET_AGENTS_DIR}"/*/; do
    [ -d "${agent_dir}" ] || continue
    agent_name="$(basename "${agent_dir}")"
    mkdir -p "${BACKUP_PATH}/agents/${agent_name}"
    for f in SOUL.md AGENTS.md MEMORY.md HEARTBEAT.md IDENTITY.md TOOLS.md USER.md BOOTSTRAP.md; do
      [ -f "${agent_dir}/${f}" ] && cp "${agent_dir}/${f}" "${BACKUP_PATH}/agents/${agent_name}/"
    done
  done
  echo "[backup] ✓ agent configs"
fi

if [ -f "${ROOT_DIR}/.env" ]; then
  cp "${ROOT_DIR}/.env" "${BACKUP_PATH}/dot-env"
  echo "[backup] ✓ .env"
fi

ARCHIVE="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
tar -czf "${ARCHIVE}" -C "${BACKUP_DIR}" "${BACKUP_NAME}"
rm -rf "${BACKUP_PATH}"

echo "[backup] ✓ archived: ${ARCHIVE}"
echo "[OK] backup complete"
