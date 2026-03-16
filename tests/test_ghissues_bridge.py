"""Regression checks for ghissues_op action compatibility."""

import json
import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BRIDGE_SRC = ROOT / "templates" / "bin" / "ghissues_op"


class GhIssuesBridgeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = pathlib.Path(self._tmp.name)
        self.bridge = self.tmpdir / "ghissues_op"
        self.request_file = self.tmpdir / ".ghissues_op_request.json"
        self.response_file = self.tmpdir / ".ghissues_op_response.json"
        self.gh_log = self.tmpdir / "gh.log"

        shutil.copy2(BRIDGE_SRC, self.bridge)
        self.bridge.chmod(self.bridge.stat().st_mode | stat.S_IXUSR)
        self._write_fake_gh()

    def tearDown(self):
        self._tmp.cleanup()

    def _write_fake_gh(self):
        fake_gh = self.tmpdir / "gh"
        fake_gh.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                printf '%s\\n' "$*" >> "${GH_FAKE_LOG}"
                if [ "${GH_FAKE_FAIL_LIST:-0}" = "1" ] && [ "$1" = "issue" ] && [ "$2" = "list" ]; then
                  echo "mock list failure" >&2
                  exit 2
                fi
                if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
                  number="$3"
                  jq -n --argjson n "$number" '{number:$n,title:"fake issue",url:("https://github.com/example/repo/issues/" + ($n|tostring))}'
                  exit 0
                fi
                if [ "$1" = "pr" ] && [ "$2" = "view" ]; then
                  number="$3"
                  jq -n --argjson n "$number" '{number:$n,title:"fake pr",url:("https://github.com/example/repo/pull/" + ($n|tostring))}'
                  exit 0
                fi
                if [ "$1" = "issue" ] && [ "$2" = "list" ]; then
                  echo '[]'
                  exit 0
                fi
                if [ "$1" = "pr" ] && [ "$2" = "list" ]; then
                  echo '[]'
                  exit 0
                fi
                echo "unsupported fake gh call: $*" >&2
                exit 2
                """
            ),
            encoding="utf-8",
        )
        fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)

    def _run_bridge(self, payload, with_token=True):
        self.request_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        env = os.environ.copy()
        env["PATH"] = f"{self.tmpdir}{os.pathsep}{env.get('PATH', '')}"
        env["GH_FAKE_LOG"] = str(self.gh_log)
        if with_token:
            env["GH_TOKEN"] = "dummy-token"
        else:
            env.pop("GH_TOKEN", None)

        subprocess.run(
            [str(self.bridge)],
            cwd=self.tmpdir,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(self.response_file.read_text(encoding="utf-8"))

    def _run_bridge_with_env(self, payload, env_overrides):
        self.request_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        env = os.environ.copy()
        env["PATH"] = f"{self.tmpdir}{os.pathsep}{env.get('PATH', '')}"
        env["GH_FAKE_LOG"] = str(self.gh_log)
        env["GH_TOKEN"] = "dummy-token"
        env.update(env_overrides)

        subprocess.run(
            [str(self.bridge)],
            cwd=self.tmpdir,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(self.response_file.read_text(encoding="utf-8"))

    def test_get_issue_alias_maps_to_issue_view(self):
        data = self._run_bridge({"action": "get_issue", "repo": "example/repo", "number": 22})
        self.assertTrue(data["ok"])
        self.assertEqual(data["data"]["number"], 22)
        gh_calls = self.gh_log.read_text(encoding="utf-8")
        self.assertIn("issue view 22", gh_calls)

    def test_get_pr_alias_maps_to_pr_view(self):
        data = self._run_bridge({"action": "get_pr", "repo": "example/repo", "number": 9})
        self.assertTrue(data["ok"])
        self.assertEqual(data["data"]["number"], 9)
        gh_calls = self.gh_log.read_text(encoding="utf-8")
        self.assertIn("pr view 9", gh_calls)

    def test_list_actions_does_not_require_repo_or_token(self):
        data = self._run_bridge({"action": "list_actions"}, with_token=False)
        self.assertTrue(data["ok"])
        self.assertIn("view_issue", data["data"]["canonical"])
        self.assertEqual(data["data"]["aliases"]["get_issue"], "view_issue")

    def test_command_failure_returns_original_stderr(self):
        data = self._run_bridge_with_env(
            {"action": "list_issues", "repo": "example/repo"},
            {"GH_FAKE_FAIL_LIST": "1"},
        )
        self.assertFalse(data["ok"])
        self.assertIn("mock list failure", data["error"])


if __name__ == "__main__":
    unittest.main()
