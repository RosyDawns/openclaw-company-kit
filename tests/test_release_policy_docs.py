"""Regression checks for release channel and upgrade-path documentation."""

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ROADMAP = ROOT / "ROADMAP.md"
CHANGELOG = ROOT / "CHANGELOG.md"


class ReleasePolicyDocsTests(unittest.TestCase):
    def test_readme_contains_lts_latest_and_upgrade_path(self):
        content = README.read_text(encoding="utf-8")
        self.assertIn("## Release Strategy", content)
        self.assertIn("LTS（稳定）", content)
        self.assertIn("Latest（最新）", content)
        self.assertIn("## Upgrade Path", content)
        self.assertIn("v0.5.x -> v0.6.x", content)
        self.assertIn("v0.6.x -> v0.7.x", content)

    def test_roadmap_contains_release_rules(self):
        content = ROADMAP.read_text(encoding="utf-8")
        self.assertIn("## Version Channels", content)
        self.assertIn("## Release Rules", content)
        self.assertIn("BREAKING", content)
        self.assertIn("## Upgrade Flow", content)

    def test_changelog_contains_060_upgrade_notes(self):
        content = CHANGELOG.read_text(encoding="utf-8")
        self.assertIn("## [0.6.0] - 2026-03-16", content)
        self.assertIn("### Compatibility & Upgrade Notes", content)
        self.assertIn("BREAKING: none.", content)


if __name__ == "__main__":
    unittest.main()
