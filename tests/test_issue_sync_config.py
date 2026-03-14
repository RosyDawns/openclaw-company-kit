"""Regression checks for issue-sync parameterization."""

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ISSUE_SYNC_SH = ROOT / "dashboard" / "rd-dashboard" / "issue-sync.sh"


class IssueSyncConfigTests(unittest.TestCase):
    def test_issue_sync_has_no_w11_hardcode(self):
        content = ISSUE_SYNC_SH.read_text(encoding="utf-8")
        self.assertNotIn("sprint:w11", content)
        self.assertNotIn("MVP Sprint W11", content)

    def test_issue_sync_exposes_cron_job_ids_as_env_overrides(self):
        content = ISSUE_SYNC_SH.read_text(encoding="utf-8")
        self.assertIn('CRON_GUARD_TARGET_JOB_ID="${CRON_GUARD_TARGET_JOB_ID:-', content)
        self.assertIn('CRON_PIPELINE_TECH_JOB_ID="${CRON_PIPELINE_TECH_JOB_ID:-', content)
        self.assertIn('CRON_PIPELINE_PRODUCT_JOB_ID="${CRON_PIPELINE_PRODUCT_JOB_ID:-', content)
        self.assertIn('CRON_PIPELINE_REVIEWER_JOB_ID="${CRON_PIPELINE_REVIEWER_JOB_ID:-', content)
        self.assertIn('CRON_PIPELINE_QA_JOB_ID="${CRON_PIPELINE_QA_JOB_ID:-', content)

    def test_issue_sync_uses_dynamic_sprint_label(self):
        content = ISSUE_SYNC_SH.read_text(encoding="utf-8")
        self.assertIn('SPRINT_LABEL="${SPRINT_LABEL:-${ISSUE_SYNC_SPRINT_LABEL:-}}"', content)
        self.assertIn('labels_csv="${priority},${SPRINT_LABEL},${owners_csv}"', content)
        self.assertIn('ensure_label "${SPRINT_LABEL}" "1D76DB" "${SPRINT_NAME}"', content)

    def test_issue_sync_emits_structured_auto_evidence_fields(self):
        content = ISSUE_SYNC_SH.read_text(encoding="utf-8")
        self.assertIn("- EvidenceType:", content)
        self.assertIn("- EvidenceURL:", content)
        self.assertIn("- IssueURL:", content)
        self.assertIn("[AUTO-EVIDENCE]", content)


if __name__ == "__main__":
    unittest.main()
