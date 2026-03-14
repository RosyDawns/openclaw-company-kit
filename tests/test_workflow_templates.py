"""Regression checks for workflow template packages."""

import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL_SERVER = ROOT / "scripts" / "control_server.py"
SETUP_HTML = ROOT / "web" / "setup.html"
INSTALL_SH = ROOT / "scripts" / "install.sh"
INSTALL_CRON_SH = ROOT / "scripts" / "install-cron.sh"

WORKFLOW_JSON_FILES = [
    ROOT / "templates" / "workflow-jobs.default.json",
    ROOT / "templates" / "workflow-jobs.requirement-review.json",
    ROOT / "templates" / "workflow-jobs.bugfix.json",
    ROOT / "templates" / "workflow-jobs.release-retro.json",
]


def load_control_server_module():
    spec = importlib.util.spec_from_file_location("control_server", CONTROL_SERVER)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load control_server module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class WorkflowTemplateTests(unittest.TestCase):
    def test_control_server_has_workflow_template_key(self):
        mod = load_control_server_module()
        self.assertIn("WORKFLOW_TEMPLATE", mod.DEFAULT_CONFIG)
        self.assertIn("WORKFLOW_TEMPLATE", mod.ENV_KEY_ORDER)
        self.assertEqual(mod.DEFAULT_CONFIG.get("WORKFLOW_TEMPLATE"), "default")

    def test_setup_contains_workflow_template_selector(self):
        content = SETUP_HTML.read_text(encoding="utf-8")
        self.assertIn("WORKFLOW_TEMPLATE", content)
        self.assertIn("需求评审流", content)
        self.assertIn("Bug 修复流", content)
        self.assertIn("发布复盘流", content)

    def test_install_scripts_apply_workflow_templates(self):
        install_content = INSTALL_SH.read_text(encoding="utf-8")
        cron_content = INSTALL_CRON_SH.read_text(encoding="utf-8")
        self.assertIn("WORKFLOW_TEMPLATE_ID", install_content)
        self.assertIn("workflow-prompt.requirement-review.txt", install_content)
        self.assertIn("WORKFLOW_TEMPLATE_ID", cron_content)
        self.assertIn("workflow-jobs.default.json", cron_content)
        self.assertIn('startswith("模板-")', cron_content)

    def test_workflow_job_templates_are_valid_json(self):
        for path in WORKFLOW_JSON_FILES:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsInstance(payload, dict, msg=f"{path} must be a JSON object")
            jobs = payload.get("jobs")
            self.assertIsInstance(jobs, list, msg=f"{path} must contain jobs[]")
            self.assertGreaterEqual(len(jobs), 1, msg=f"{path} jobs[] must not be empty")
            for item in jobs:
                self.assertIsInstance(item, dict, msg=f"{path} job item must be object")
                self.assertIn("name", item)
                self.assertIn("agent", item)
                self.assertIn("cron", item)
                self.assertIn("message", item)


if __name__ == "__main__":
    unittest.main()
