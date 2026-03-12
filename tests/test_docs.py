import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class DocsTests(unittest.TestCase):
    def test_required_docs_exist(self):
        required = [
            ROOT / "README.md",
            ROOT / "docs" / "getting-started.md",
            ROOT / "docs" / "architecture.md",
            ROOT / "docs" / "deployment.md",
            ROOT / "docs" / "troubleshooting.md",
            ROOT / "docs" / "security.md",
            ROOT / "CONTRIBUTING.md",
            ROOT / "ROADMAP.md",
        ]
        for p in required:
            self.assertTrue(p.exists(), f"missing doc: {p}")


if __name__ == "__main__":
    unittest.main()
