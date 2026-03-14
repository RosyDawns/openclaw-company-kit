#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=./_common.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

load_env

BACKUP_DIR="${ROOT_DIR}/backups"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
BACKUP_NAME="${OPENCLAW_PROFILE}_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"
BACKUP_INCLUDE_TASK_SUMMARY="${BACKUP_INCLUDE_TASK_SUMMARY:-0}"
BACKUP_TASK_SUMMARY_DAYS="${BACKUP_TASK_SUMMARY_DAYS:-7}"
TASK_HISTORY_PATH="${PROFILE_DIR}/run/control-task-history.jsonl"
TASK_AUDIT_PATH="${PROFILE_DIR}/run/control-audit-log.jsonl"

if ! [[ "${BACKUP_TASK_SUMMARY_DAYS}" =~ ^[0-9]+$ ]] || [ "${BACKUP_TASK_SUMMARY_DAYS}" -lt 1 ] || [ "${BACKUP_TASK_SUMMARY_DAYS}" -gt 30 ]; then
  BACKUP_TASK_SUMMARY_DAYS=7
fi

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

if [ "${BACKUP_INCLUDE_TASK_SUMMARY}" = "1" ]; then
  if [ -f "${TASK_HISTORY_PATH}" ]; then
    summary_path="${BACKUP_PATH}/control-task-summary-${BACKUP_TASK_SUMMARY_DAYS}d.json"
    history_export_path="${BACKUP_PATH}/control-task-history.jsonl"
    python3 - "${TASK_HISTORY_PATH}" "${summary_path}" "${history_export_path}" "${BACKUP_TASK_SUMMARY_DAYS}" <<'PY'
import json
import sys
from datetime import datetime, timedelta

history_path = sys.argv[1]
summary_path = sys.argv[2]
history_export_path = sys.argv[3]
window_days = int(sys.argv[4])

now = datetime.now()
cutoff = now - timedelta(days=window_days)


def parse_local_time(value: str):
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


rows = []
with open(history_path, "r", encoding="utf-8") as fh:
    for raw in fh:
        text = raw.strip()
        if not text:
            continue
        try:
            row = json.loads(text)
        except Exception:
            continue
        ts = None
        for key in ("finishedAt", "startedAt"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                ts = parse_local_time(value.strip())
                if ts is not None:
                    break
        if ts is None or ts >= cutoff:
            rows.append(row)

rows.sort(key=lambda x: str(x.get("finishedAt") or x.get("startedAt") or ""), reverse=True)

success = sum(1 for x in rows if str(x.get("status") or "") == "success")
failed = sum(1 for x in rows if str(x.get("status") or "") == "failed")
total = len(rows)
success_rate = round((success * 100.0 / total), 2) if total > 0 else 0.0

by_task = {}
latest_failures = []
for row in rows:
    name = str(row.get("name") or "unknown")
    bucket = by_task.setdefault(name, {"name": name, "total": 0, "success": 0, "failed": 0})
    bucket["total"] += 1
    if str(row.get("status") or "") == "success":
        bucket["success"] += 1
    elif str(row.get("status") or "") == "failed":
        bucket["failed"] += 1
        if len(latest_failures) < 10:
            latest_failures.append(
                {
                    "id": row.get("id"),
                    "name": row.get("name"),
                    "finishedAt": row.get("finishedAt"),
                    "failedStep": row.get("failedStep"),
                    "failedCode": row.get("failedCode"),
                    "error": row.get("error"),
                }
            )

summary = {
    "generatedAt": now.strftime("%Y-%m-%d %H:%M:%S"),
    "windowDays": window_days,
    "source": "control-task-history.jsonl",
    "summary": {
        "total": total,
        "success": success,
        "failed": failed,
        "successRate": success_rate,
    },
    "byTask": sorted(by_task.values(), key=lambda x: (-x["failed"], -x["total"], x["name"])),
    "latestFailures": latest_failures,
}

with open(summary_path, "w", encoding="utf-8") as fh:
    fh.write(json.dumps(summary, ensure_ascii=False, indent=2))
    fh.write("\n")
with open(history_export_path, "w", encoding="utf-8") as fh:
    for row in rows:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
PY
    echo "[backup] ✓ control task summary (${BACKUP_TASK_SUMMARY_DAYS}d)"
    echo "[backup] ✓ control task history (${BACKUP_TASK_SUMMARY_DAYS}d)"
  else
    echo "[backup] - skip control task summary (history not found)"
  fi

  if [ -f "${TASK_AUDIT_PATH}" ]; then
    cp "${TASK_AUDIT_PATH}" "${BACKUP_PATH}/control-audit-log.jsonl"
    echo "[backup] ✓ control audit log"
  else
    echo "[backup] - skip control audit log (not found)"
  fi
fi

ARCHIVE="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
tar -czf "${ARCHIVE}" -C "${BACKUP_DIR}" "${BACKUP_NAME}"
rm -rf "${BACKUP_PATH}"

echo "[backup] ✓ archived: ${ARCHIVE}"
echo "[OK] backup complete"
