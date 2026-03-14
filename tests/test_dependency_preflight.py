"""Regression checks for unified dependency preflight."""

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMON_SH = ROOT / "scripts" / "_common.sh"
LAUNCH_SH = ROOT / "scripts" / "launch.sh"
INSTALL_SH = ROOT / "scripts" / "install.sh"
START_SH = ROOT / "scripts" / "start.sh"
INSTALL_CRON_SH = ROOT / "scripts" / "install-cron.sh"


class DependencyPreflightTests(unittest.TestCase):
    def test_common_check_cmds_covers_shared_dependencies(self):
        content = COMMON_SH.read_text(encoding="utf-8")
        self.assertIn("OPENCLAW_NODE_MIN_MAJOR", content)
        self.assertIn("for c in openclaw node jq python3 rsync; do", content)
        self.assertIn('OPENCLAW_ALLOW_NO_GH="${OPENCLAW_ALLOW_NO_GH:-0}"', content)
        self.assertIn('if ! command -v gh >/dev/null 2>&1; then', content)
        self.assertIn("install gh: brew install gh", content)
        self.assertIn("temp bypass: OPENCLAW_ALLOW_NO_GH=1 bash scripts/launch.sh", content)
        self.assertIn("node version ${raw} is below required major ${min_major}", content)

    def test_launch_reuses_common_preflight(self):
        content = LAUNCH_SH.read_text(encoding="utf-8")
        self.assertIn("source \"${ROOT_DIR}/scripts/_common.sh\"", content)
        self.assertIn("load_env", content)
        self.assertIn("check_cmds", content)
        self.assertNotIn("check_node()", content)

    def test_entry_scripts_share_check_cmds(self):
        for path in (INSTALL_SH, START_SH, INSTALL_CRON_SH):
            content = path.read_text(encoding="utf-8")
            self.assertIn("check_cmds", content, msg=f"{path} should use shared check_cmds")

    def test_start_repairs_gateway_token_mismatch(self):
        content = START_SH.read_text(encoding="utf-8")
        self.assertIn("repair_gateway_token_mismatch() {", content)
        self.assertIn('status_output="$(ocp gateway status 2>&1 || true)"', content)
        self.assertIn("gateway token mismatch", content)
        self.assertIn("ocp gateway stop >/dev/null 2>&1 || true", content)
        self.assertIn("ocp gateway install --force >/dev/null 2>&1 || true", content)


if __name__ == "__main__":
    unittest.main()
