import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TemplateTests(unittest.TestCase):
    def test_jobs_template_valid_json(self):
        path = ROOT / "templates" / "jobs.template.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("jobs", data)
        self.assertGreaterEqual(len(data["jobs"]), 5)

    def test_company_template_valid_json(self):
        path = ROOT / "templates" / "company-project.template.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("companyName", data)
        self.assertIn("projectPath", data)
        self.assertIn("projectRepo", data)

    def test_demo_data_has_agent_panel(self):
        path = ROOT / "docker" / "demo_data" / "dashboard-data.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("agentPanel", data)
        self.assertGreaterEqual(len(data["agentPanel"]), 5)


if __name__ == "__main__":
    unittest.main()
