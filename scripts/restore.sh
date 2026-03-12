#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env

BACKUP_DIR="${ROOT_DIR}/backups"

if [ $# -lt 1 ]; then
  echo "Usage: bash scripts/restore.sh <backup-archive>"
  echo ""
  echo "Available backups:"
  ls -1t "${BACKUP_DIR}"/*.tar.gz 2>/dev/null | head -10 || echo "  (none)"
  exit 1
fi

ARCHIVE="$1"
if [ ! -f "${ARCHIVE}" ]; then
  if [ -f "${BACKUP_DIR}/${ARCHIVE}" ]; then
    ARCHIVE="${BACKUP_DIR}/${ARCHIVE}"
  else
    echo "[ERROR] backup not found: ${ARCHIVE}"
    exit 1
  fi
fi

TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT

tar -xzf "${ARCHIVE}" -C "${TMPDIR}"
RESTORE_DIR="$(find "${TMPDIR}" -mindepth 1 -maxdepth 1 -type d | head -1)"

if [ -z "${RESTORE_DIR}" ]; then
  echo "[ERROR] invalid backup archive"
  exit 1
fi

echo "[restore] source: ${ARCHIVE}"
echo "[restore] profile: ${OPENCLAW_PROFILE}"

if [ -f "${RESTORE_DIR}/openclaw.json" ]; then
  cp "${RESTORE_DIR}/openclaw.json" "${PROFILE_DIR}/openclaw.json"
  echo "[restore] ✓ openclaw.json"
fi

if [ -f "${RESTORE_DIR}/exec-approvals.json" ]; then
  cp "${RESTORE_DIR}/exec-approvals.json" "${PROFILE_DIR}/exec-approvals.json"
  echo "[restore] ✓ exec-approvals.json"
fi

if [ -d "${RESTORE_DIR}/agents" ]; then
  for agent_dir in "${RESTORE_DIR}/agents"/*/; do
    [ -d "${agent_dir}" ] || continue
    agent_name="$(basename "${agent_dir}")"
    target="${TARGET_AGENTS_DIR}/${agent_name}"
    mkdir -p "${target}"
    cp "${agent_dir}"/*.md "${target}/" 2>/dev/null || true
  done
  echo "[restore] ✓ agent configs"
fi

if [ -f "${RESTORE_DIR}/dot-env" ]; then
  cp "${RESTORE_DIR}/dot-env" "${ROOT_DIR}/.env"
  echo "[restore] ✓ .env"
fi

echo "[OK] restore complete — run 'bash scripts/start.sh' to apply"
