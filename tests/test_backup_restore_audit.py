"""Regression checks for BK-13 backup/restore audit summary support."""

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKUP_SH = ROOT / "scripts" / "backup.sh"
RESTORE_SH = ROOT / "scripts" / "restore.sh"


class BackupRestoreAuditTests(unittest.TestCase):
    def test_backup_supports_optional_task_summary_bundle(self):
        content = BACKUP_SH.read_text(encoding="utf-8")
        self.assertIn('BACKUP_INCLUDE_TASK_SUMMARY="${BACKUP_INCLUDE_TASK_SUMMARY:-0}"', content)
        self.assertIn('BACKUP_TASK_SUMMARY_DAYS="${BACKUP_TASK_SUMMARY_DAYS:-7}"', content)
        self.assertIn("control-task-summary-", content)
        self.assertIn("control-task-history.jsonl", content)
        self.assertIn("control-audit-log.jsonl", content)

    def test_restore_supports_task_history_and_audit_logs(self):
        content = RESTORE_SH.read_text(encoding="utf-8")
        self.assertIn('mkdir -p "${PROFILE_DIR}/run"', content)
        self.assertIn('if [ -f "${RESTORE_DIR}/control-task-history.jsonl" ]; then', content)
        self.assertIn('if [ -f "${RESTORE_DIR}/control-audit-log.jsonl" ]; then', content)


if __name__ == "__main__":
    unittest.main()
