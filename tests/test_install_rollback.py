"""Regression checks for install rollback safeguards."""

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class InstallRollbackTests(unittest.TestCase):
    def test_install_has_rollback_trap(self):
        content = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertIn("rollback_install()", content)
        self.assertIn("trap 'rollback_install $? $LINENO' ERR", content)
        self.assertIn("INSTALL_COMPLETED=1", content)

    def test_install_restores_key_paths(self):
        content = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertIn('restore_file_or_remove "${PROFILE_DIR}/openclaw.json"', content)
        self.assertIn('restore_file_or_remove "${PROFILE_DIR}/exec-approvals.json"', content)
        self.assertIn('restore_dir_or_remove "${TARGET_AGENTS_DIR}"', content)
        self.assertIn('restore_dir_or_remove "${TARGET_DASHBOARD_DIR}"', content)


if __name__ == "__main__":
    unittest.main()
