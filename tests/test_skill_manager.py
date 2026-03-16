"""Tests for engine.skill_manifest and engine.skill_manager."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from engine.skill_manifest import SkillManifest
from engine.skill_manager import SkillManager


class TestSkillManifest(unittest.TestCase):
    """SkillManifest dataclass round-trip and validation."""

    def test_to_dict_from_dict_roundtrip(self):
        m = SkillManifest(
            name="demo",
            version="2.0.0",
            description="A demo skill",
            author="tester",
            repo_url="https://github.com/x/demo.git",
            compatible_roles=["role-senior-dev"],
            tags=["test"],
        )
        d = m.to_dict()
        m2 = SkillManifest.from_dict(d)
        self.assertEqual(m.name, m2.name)
        self.assertEqual(m.version, m2.version)
        self.assertEqual(m.compatible_roles, m2.compatible_roles)

    def test_from_json(self):
        data = {"name": "json-skill", "version": "0.1.0", "entry_point": "README.md"}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fp:
            json.dump(data, fp)
            fp.flush()
            path = fp.name
        try:
            m = SkillManifest.from_json(path)
            self.assertEqual(m.name, "json-skill")
            self.assertEqual(m.entry_point, "README.md")
        finally:
            os.unlink(path)

    def test_validate_missing_name(self):
        m = SkillManifest(name="")
        errors = m.validate()
        self.assertIn("name is required", errors)

    def test_validate_missing_entry_point(self):
        m = SkillManifest(name="ok", entry_point="")
        errors = m.validate()
        self.assertIn("entry_point is required", errors)

    def test_validate_bad_extension(self):
        m = SkillManifest(name="ok", entry_point="run.py")
        errors = m.validate()
        self.assertTrue(any("entry_point must be" in e for e in errors))

    def test_validate_allowed_extensions(self):
        for ext in ("SKILL.md", "config.json", "notes.txt"):
            m = SkillManifest(name="ok", entry_point=ext)
            self.assertEqual(m.validate(), [], f"Expected no errors for {ext}")


class TestSkillManagerListLocal(unittest.TestCase):
    """list_local / get_skill against a temporary skills directory."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.mgr = SkillManager(skills_dir=self._tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_list_local_empty(self):
        self.assertEqual(self.mgr.list_local(), [])

    def test_list_local_with_manifest(self):
        skill_dir = os.path.join(self._tmpdir, "alpha")
        os.makedirs(skill_dir)
        manifest = {"name": "alpha", "version": "1.0.0", "entry_point": "SKILL.md"}
        with open(os.path.join(skill_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write("# Alpha")

        skills = self.mgr.list_local()
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].name, "alpha")

    def test_list_local_without_manifest_but_entry(self):
        skill_dir = os.path.join(self._tmpdir, "beta")
        os.makedirs(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write("# Beta")

        skills = self.mgr.list_local()
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].name, "beta")
        self.assertEqual(skills[0].entry_point, "SKILL.md")

    def test_list_local_empty_dir_no_entry(self):
        os.makedirs(os.path.join(self._tmpdir, "empty"))
        self.assertEqual(self.mgr.list_local(), [])

    def test_get_skill_exists(self):
        skill_dir = os.path.join(self._tmpdir, "gamma")
        os.makedirs(skill_dir)
        manifest = {"name": "gamma", "version": "3.0.0", "entry_point": "SKILL.md"}
        with open(os.path.join(skill_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f)

        s = self.mgr.get_skill("gamma")
        self.assertIsNotNone(s)
        self.assertEqual(s.name, "gamma")
        self.assertEqual(s.version, "3.0.0")

    def test_get_skill_not_found(self):
        self.assertIsNone(self.mgr.get_skill("nonexistent"))


class TestSkillManagerRemote(unittest.TestCase):
    """add_remote / update_remote / remove with mocked git."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.mgr = SkillManager(skills_dir=self._tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    @patch("engine.skill_manager.subprocess.run")
    def test_add_remote_creates_dir(self, mock_run: MagicMock):
        def fake_clone(cmd, **_kw):
            dest = cmd[-1]
            os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, "SKILL.md"), "w") as f:
                f.write("# Cloned")
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_clone

        m = self.mgr.add_remote("https://github.com/org/my-skill.git")
        self.assertEqual(m.name, "my-skill")
        self.assertTrue(os.path.isdir(os.path.join(self._tmpdir, "my-skill")))
        self.assertIsNotNone(m.installed_at)
        mock_run.assert_called_once()

    @patch("engine.skill_manager.subprocess.run")
    def test_add_remote_custom_name(self, mock_run: MagicMock):
        def fake_clone(cmd, **_kw):
            dest = cmd[-1]
            os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, "README.md"), "w") as f:
                f.write("# Custom")
            return MagicMock(returncode=0)

        mock_run.side_effect = fake_clone

        m = self.mgr.add_remote("https://github.com/org/repo.git", name="custom")
        self.assertEqual(m.name, "custom")

    @patch("engine.skill_manager.subprocess.run")
    def test_add_remote_duplicate_raises(self, mock_run: MagicMock):
        os.makedirs(os.path.join(self._tmpdir, "dup"))
        with self.assertRaises(FileExistsError):
            self.mgr.add_remote("https://github.com/org/dup.git")

    @patch("engine.skill_manager.subprocess.run")
    def test_update_remote(self, mock_run: MagicMock):
        skill_dir = os.path.join(self._tmpdir, "updatable")
        os.makedirs(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write("# v1")
        mock_run.return_value = MagicMock(returncode=0)

        m = self.mgr.update_remote("updatable")
        self.assertEqual(m.name, "updatable")
        mock_run.assert_called_once()

    def test_update_remote_not_installed(self):
        with self.assertRaises(FileNotFoundError):
            self.mgr.update_remote("ghost")

    def test_remove_skill(self):
        skill_dir = os.path.join(self._tmpdir, "removeme")
        os.makedirs(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write("bye")

        self.assertTrue(self.mgr.remove("removeme"))
        self.assertFalse(os.path.exists(skill_dir))

    def test_remove_nonexistent(self):
        self.assertFalse(self.mgr.remove("nope"))


class TestSkillManagerSecurity(unittest.TestCase):
    """Security validation and entry-point restrictions."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.mgr = SkillManager(skills_dir=self._tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_security_check_detects_dangerous(self):
        skill_dir = os.path.join(self._tmpdir, "risky")
        os.makedirs(skill_dir)
        for fname in ("SKILL.md", "helper.py", "setup.sh"):
            with open(os.path.join(skill_dir, fname), "w") as f:
                f.write("content")

        warnings = self.mgr._validate_security(skill_dir)
        self.assertEqual(len(warnings), 2)
        exts_found = {os.path.splitext(w.split(": ")[-1])[1] for w in warnings}
        self.assertIn(".py", exts_found)
        self.assertIn(".sh", exts_found)

    def test_security_check_clean(self):
        skill_dir = os.path.join(self._tmpdir, "safe")
        os.makedirs(skill_dir)
        with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
            f.write("safe")
        self.assertEqual(self.mgr._validate_security(skill_dir), [])

    def test_entry_point_restriction(self):
        m = SkillManifest(name="bad", entry_point="exploit.py")
        errors = m.validate()
        self.assertTrue(any(".py" in e for e in errors))

        m2 = SkillManifest(name="ok", entry_point="SKILL.md")
        self.assertEqual(m2.validate(), [])


class TestSkillManagerOfficialHub(unittest.TestCase):
    def test_import_official_hub_placeholder(self):
        mgr = SkillManager(skills_dir=tempfile.mkdtemp())
        result = mgr.import_official_hub()
        self.assertEqual(result, [])
        import shutil
        shutil.rmtree(mgr.skills_dir, ignore_errors=True)


class TestSkillManagerNameFromUrl(unittest.TestCase):
    def test_https_with_git_suffix(self):
        self.assertEqual(
            SkillManager._name_from_url("https://github.com/org/my-skill.git"),
            "my-skill",
        )

    def test_https_no_suffix(self):
        self.assertEqual(
            SkillManager._name_from_url("https://github.com/org/my-skill"),
            "my-skill",
        )

    def test_trailing_slash(self):
        self.assertEqual(
            SkillManager._name_from_url("https://github.com/org/my-skill/"),
            "my-skill",
        )


if __name__ == "__main__":
    unittest.main()
