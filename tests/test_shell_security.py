"""Security-oriented tests for shell helper scripts."""

import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON_SH = ROOT / "scripts" / "_common.sh"
BOOTSTRAP_SH = ROOT / "scripts" / "bootstrap.sh"


class ShellSecurityTests(unittest.TestCase):
    def test_expand_tilde_path_expands_current_user_home(self):
        script = f"""
set -euo pipefail
source {shlex.quote(str(COMMON_SH))}
HOME='/tmp/openclaw-home-test'
expand_tilde_path '~/.openclaw'
"""
        res = subprocess.run(["bash", "-lc", script], capture_output=True, text=True, check=True)
        self.assertEqual(res.stdout.strip(), "/tmp/openclaw-home-test/.openclaw")

    def test_expand_tilde_path_does_not_execute_command_substitution(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            marker = Path(tmp_dir) / "marker.txt"
            script = f"""
set -euo pipefail
source {shlex.quote(str(COMMON_SH))}
marker={shlex.quote(str(marker))}
value='~$(touch "$marker")/payload'
expand_tilde_path "$value" >/dev/null
test ! -f "$marker"
"""
            subprocess.run(["bash", "-lc", script], check=True)
            self.assertFalse(marker.exists())

    def test_bootstrap_script_has_no_local_cfg_eval(self):
        content = BOOTSTRAP_SH.read_text(encoding="utf-8")
        self.assertNotIn('eval "local_cfg=', content)


if __name__ == "__main__":
    unittest.main()
