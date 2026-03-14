"""Security regression checks for install flow defaults."""

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class InstallSecurityTests(unittest.TestCase):
    def test_install_uses_allow_from_json_variable(self):
        content = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertIn("--argjson allowFrom", content)
        self.assertNotIn('"allowFrom": ["*"]', content)
        self.assertIn('"allowFrom": $allowFrom', content)
        self.assertIn('"groupAllowFrom": $allowFrom', content)
        self.assertIn('"dmPolicy": "allowlist"', content)
        self.assertIn('"groupPolicy": "allowlist"', content)

    def test_env_example_documents_feishu_allow_from(self):
        content = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("FEISHU_ALLOW_FROM=", content)
        self.assertIn("GROUP_ID", content)

    def test_install_does_not_emit_deprecated_max_spawn_depth(self):
        content = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("maxSpawnDepth", content)
        self.assertIn('"subagents":{"allowAgents"', content)

    def test_onboard_wrapper_sanitizes_legacy_max_spawn_depth(self):
        content = (ROOT / "scripts" / "onboard-wrapper.sh").read_text(encoding="utf-8")
        self.assertIn("sanitize_legacy_config()", content)
        self.assertIn("del(.maxSpawnDepth)", content)
        self.assertIn("restore_gateway_auth_token_if_changed()", content)
        self.assertIn("restored existing gateway auth token", content)

    def test_install_removes_stale_ai_feishu_account_when_disabled(self):
        content = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        self.assertIn('if $aiAppId != "" and $aiAppSecret != "" then', content)
        self.assertIn("del(.[$aiAccount])", content)


if __name__ == "__main__":
    unittest.main()
