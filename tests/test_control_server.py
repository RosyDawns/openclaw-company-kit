"""Unit tests for control_server.py pure functions."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import control_server as cs


class TestShellQuote(unittest.TestCase):
    def test_simple_value(self):
        self.assertEqual(cs.shell_quote("hello"), "'hello'")

    def test_value_with_spaces(self):
        self.assertEqual(cs.shell_quote("hello world"), "'hello world'")

    def test_value_with_single_quote(self):
        self.assertEqual(cs.shell_quote("it's"), """'it'\"'\"'s'""")

    def test_empty_string(self):
        self.assertEqual(cs.shell_quote(""), "''")

    def test_numeric_value(self):
        self.assertEqual(cs.shell_quote("8788"), "'8788'")


class TestParseEnvFile(unittest.TestCase):
    def _write_env(self, content: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False)
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    def test_basic_parsing(self):
        p = self._write_env("FOO=bar\nBAZ=qux\n")
        data, order = cs.parse_env_file(p)
        self.assertEqual(data, {"FOO": "bar", "BAZ": "qux"})
        self.assertEqual(order, ["FOO", "BAZ"])
        p.unlink()

    def test_comments_and_blanks(self):
        p = self._write_env("# comment\n\nKEY=val\n")
        data, order = cs.parse_env_file(p)
        self.assertEqual(data, {"KEY": "val"})
        self.assertEqual(order, ["KEY"])
        p.unlink()

    def test_quoted_values(self):
        p = self._write_env("A='hello world'\nB=\"double\"\n")
        data, _ = cs.parse_env_file(p)
        self.assertEqual(data["A"], "hello world")
        self.assertEqual(data["B"], "double")
        p.unlink()

    def test_empty_value(self):
        p = self._write_env("EMPTY=\n")
        data, _ = cs.parse_env_file(p)
        self.assertEqual(data["EMPTY"], "")
        p.unlink()

    def test_nonexistent_file(self):
        data, order = cs.parse_env_file(Path("/tmp/nonexistent_env_test_file"))
        self.assertEqual(data, {})
        self.assertEqual(order, [])

    def test_value_with_equals(self):
        p = self._write_env("URL=https://example.com?a=1&b=2\n")
        data, _ = cs.parse_env_file(p)
        self.assertEqual(data["URL"], "https://example.com?a=1&b=2")
        p.unlink()


class TestNormalizeConfig(unittest.TestCase):
    def test_valid_port(self):
        base = dict(cs.DEFAULT_CONFIG)
        base["DASHBOARD_PORT"] = "8788"
        result = cs.normalize_config({"DASHBOARD_PORT": "9000"}, base)
        self.assertEqual(result["DASHBOARD_PORT"], "9000")

    def test_invalid_port_string(self):
        base = dict(cs.DEFAULT_CONFIG)
        with self.assertRaises(ValueError):
            cs.normalize_config({"DASHBOARD_PORT": "abc"}, base)

    def test_port_out_of_range(self):
        base = dict(cs.DEFAULT_CONFIG)
        with self.assertRaises(ValueError):
            cs.normalize_config({"DASHBOARD_PORT": "99999"}, base)

    def test_unknown_keys_ignored(self):
        base = dict(cs.DEFAULT_CONFIG)
        base["DASHBOARD_PORT"] = "8788"
        result = cs.normalize_config({"UNKNOWN_KEY": "value"}, base)
        self.assertNotIn("UNKNOWN_KEY", result)

    def test_none_value_becomes_empty(self):
        base = dict(cs.DEFAULT_CONFIG)
        base["DASHBOARD_PORT"] = "8788"
        base["GH_TOKEN"] = "secret"
        result = cs.normalize_config({"GH_TOKEN": None}, base)
        self.assertEqual(result["GH_TOKEN"], "")


class TestProfileDir(unittest.TestCase):
    def test_default_profile(self):
        result = cs.profile_dir({"OPENCLAW_PROFILE": "default"})
        self.assertEqual(result, Path.home() / ".openclaw")

    def test_main_profile(self):
        result = cs.profile_dir({"OPENCLAW_PROFILE": "main"})
        self.assertEqual(result, Path.home() / ".openclaw")

    def test_custom_profile(self):
        result = cs.profile_dir({"OPENCLAW_PROFILE": "company"})
        self.assertEqual(result, Path.home() / ".openclaw-company")

    def test_empty_profile(self):
        result = cs.profile_dir({"OPENCLAW_PROFILE": ""})
        self.assertEqual(result, Path.home() / ".openclaw-company")


class TestResolveAuthToken(unittest.TestCase):
    def test_prefers_cli_token(self):
        token, ephemeral = cs.resolve_auth_token("cli-token", "env-token")
        self.assertEqual(token, "cli-token")
        self.assertFalse(ephemeral)

    def test_uses_env_token(self):
        token, ephemeral = cs.resolve_auth_token(None, "env-token")
        self.assertEqual(token, "env-token")
        self.assertFalse(ephemeral)

    def test_generates_ephemeral_token_when_missing(self):
        token, ephemeral = cs.resolve_auth_token(None, None)
        self.assertTrue(isinstance(token, str))
        self.assertGreaterEqual(len(token), 16)
        self.assertTrue(ephemeral)


class TestTaskHistoryHelpers(unittest.TestCase):
    def test_extract_task_error_prefers_explicit_error_line(self):
        logs = [
            "[2026-03-14 10:00:00] STEP install",
            "$ bash scripts/install.sh",
            "some regular output",
            "[ERROR] failed to install",
        ]
        self.assertEqual(cs.extract_task_error(logs), "[ERROR] failed to install")

    def test_extract_task_error_skips_metadata_lines(self):
        logs = [
            "[2026-03-14 10:00:00] STEP start",
            "$ bash scripts/start.sh",
            "service not ready",
        ]
        self.assertEqual(cs.extract_task_error(logs), "service not ready")


class TestTaskAuditHelpers(unittest.TestCase):
    def test_append_task_audit_writes_jsonl_row(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "control-audit-log.jsonl"
            original = cs.task_audit_path
            try:
                cs.task_audit_path = lambda config=None: path
                cs.append_task_audit({"event": "task_created", "taskId": "t123"})
            finally:
                cs.task_audit_path = original

            content = path.read_text(encoding="utf-8").strip()
            row = json.loads(content)
            self.assertEqual(row.get("event"), "task_created")
            self.assertEqual(row.get("taskId"), "t123")
            self.assertIn("eventAt", row)
            self.assertIn("eventAtEpoch", row)
            self.assertIn("profile", row)

    def test_task_audit_file_constant(self):
        self.assertEqual(cs.TASK_AUDIT_FILE, "control-audit-log.jsonl")


if __name__ == "__main__":
    unittest.main()
