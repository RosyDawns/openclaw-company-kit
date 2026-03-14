"""Regression checks for BK-11 XSS hardening in setup/dashboard rendering."""

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SETUP_HTML = ROOT / "web" / "setup.html"
DASHBOARD_HTML = ROOT / "dashboard" / "rd-dashboard" / "index.html"


def innerhtml_assignments(content: str) -> list[tuple[int, str]]:
    rows = []
    for match in re.finditer(r"\.innerHTML\s*=", content):
        line_no = content.count("\n", 0, match.start()) + 1
        line = content.splitlines()[line_no - 1].strip()
        rows.append((line_no, line))
    return rows


class XssHardeningTests(unittest.TestCase):
    def assert_only_template_innerhtml(self, path: pathlib.Path):
        content = path.read_text(encoding="utf-8")
        bad = []
        for line_no, line in innerhtml_assignments(content):
            if "template.innerHTML" in line:
                continue
            bad.append(f"{path}:{line_no}: {line}")
        self.assertFalse(bad, msg="unsafe innerHTML assignment found:\n" + "\n".join(bad))

    def test_setup_hardened_rendering(self):
        content = SETUP_HTML.read_text(encoding="utf-8")
        self.assertIn("function sanitizeFragment(fragment)", content)
        self.assertIn("function setSafeHTML(host, html)", content)
        self.assertIn('setSafeHTML(byId("panel"), panes[key] || "");', content)
        self.assertIn("stepsHost.replaceChildren();", content)
        self.assertIn("host.replaceChildren();", content)
        self.assertNotIn("insertAdjacentHTML", content)
        self.assert_only_template_innerhtml(SETUP_HTML)

    def test_dashboard_hardened_rendering(self):
        content = DASHBOARD_HTML.read_text(encoding="utf-8")
        self.assertIn("function sanitizeFragment(fragment)", content)
        self.assertIn("function setSafeHTML(host, html)", content)
        self.assertIn("setSafeHTML(host, html);", content)
        self.assertIn('const button = document.createElement("button");', content)
        self.assertIn("button.dataset.view = String(v.id || \"\");", content)
        self.assertIn("button.dataset.target = String(t.id || \"\");", content)
        self.assertNotIn("insertAdjacentHTML", content)
        self.assert_only_template_innerhtml(DASHBOARD_HTML)


if __name__ == "__main__":
    unittest.main()
