"""Skill lifecycle manager – list / install / update / remove skills."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from engine.skill_manifest import SkillManifest

logger = logging.getLogger(__name__)


class SkillManager:
    """Manages the full lifecycle of Skills stored under a profile directory."""

    def __init__(self, skills_dir: Optional[str] = None) -> None:
        if skills_dir is None:
            profile = os.environ.get("OPENCLAW_PROFILE", "default")
            skills_dir = str(Path.home() / f".openclaw-{profile}" / "skills")
        self._skills_dir = skills_dir
        os.makedirs(self._skills_dir, exist_ok=True)

    @property
    def skills_dir(self) -> str:
        return self._skills_dir

    # ------------------------------------------------------------------
    # List / Get
    # ------------------------------------------------------------------

    def list_local(self) -> List[SkillManifest]:
        """Scan the skills directory and return installed manifests."""
        skills: List[SkillManifest] = []
        if not os.path.isdir(self._skills_dir):
            return skills
        for name in sorted(os.listdir(self._skills_dir)):
            skill_dir = os.path.join(self._skills_dir, name)
            if not os.path.isdir(skill_dir):
                continue
            manifest_path = os.path.join(skill_dir, "manifest.json")
            if os.path.isfile(manifest_path):
                try:
                    skills.append(SkillManifest.from_json(manifest_path))
                except Exception as exc:
                    logger.warning("Failed to load skill %s: %s", name, exc)
            else:
                entry = self._find_entry_point(skill_dir)
                if entry:
                    skills.append(SkillManifest(name=name, entry_point=entry))
        return skills

    def get_skill(self, name: str) -> Optional[SkillManifest]:
        """Return the manifest for a single installed skill, or *None*."""
        skill_dir = os.path.join(self._skills_dir, name)
        if not os.path.isdir(skill_dir):
            return None
        manifest_path = os.path.join(skill_dir, "manifest.json")
        if os.path.isfile(manifest_path):
            return SkillManifest.from_json(manifest_path)
        entry = self._find_entry_point(skill_dir)
        if entry:
            return SkillManifest(name=name, entry_point=entry)
        return None

    # ------------------------------------------------------------------
    # Install / Update / Remove
    # ------------------------------------------------------------------

    def add_remote(self, repo_url: str, name: Optional[str] = None) -> SkillManifest:
        """Clone a git repository as a new skill."""
        if name is None:
            name = self._name_from_url(repo_url)

        dest = os.path.join(self._skills_dir, name)
        if os.path.exists(dest):
            raise FileExistsError(f"Skill '{name}' already installed at {dest}")

        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, dest],
            check=True,
            capture_output=True,
            text=True,
        )

        warnings = self._validate_security(dest)
        if warnings:
            logger.warning("Security warnings for %s:\n  %s", name, "\n  ".join(warnings))

        manifest = self._load_or_create_manifest(dest, name, repo_url)
        manifest.installed_at = datetime.now(timezone.utc).isoformat()
        self._save_manifest(dest, manifest)
        return manifest

    def update_remote(self, name: str) -> SkillManifest:
        """Pull latest changes for an installed skill."""
        skill_dir = os.path.join(self._skills_dir, name)
        if not os.path.isdir(skill_dir):
            raise FileNotFoundError(f"Skill '{name}' is not installed")

        subprocess.run(
            ["git", "-C", skill_dir, "pull", "--ff-only"],
            check=True,
            capture_output=True,
            text=True,
        )

        manifest = self._load_or_create_manifest(skill_dir, name, "")
        return manifest

    def remove(self, name: str) -> bool:
        """Uninstall a skill by removing its directory."""
        skill_dir = os.path.join(self._skills_dir, name)
        if not os.path.isdir(skill_dir):
            return False
        shutil.rmtree(skill_dir)
        return True

    # ------------------------------------------------------------------
    # Official hub (placeholder)
    # ------------------------------------------------------------------

    def import_official_hub(
        self, agents: Optional[List[str]] = None
    ) -> List[SkillManifest]:
        """Batch-import from the official skill index (not yet available)."""
        return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_entry_point(skill_dir: str) -> Optional[str]:
        for candidate in ("SKILL.md", "README.md", "skill.json", "config.json"):
            if os.path.isfile(os.path.join(skill_dir, candidate)):
                return candidate
        return None

    @staticmethod
    def _validate_security(skill_dir: str) -> List[str]:
        dangerous_ext = {".py", ".sh", ".bash", ".js", ".rb", ".pl"}
        warnings: List[str] = []
        for root, _dirs, files in os.walk(skill_dir):
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext in dangerous_ext:
                    warnings.append(
                        f"Potentially dangerous file: {os.path.join(root, fname)}"
                    )
        return warnings

    @staticmethod
    def _name_from_url(url: str) -> str:
        """Derive a skill name from a git URL."""
        base = url.rstrip("/").rsplit("/", 1)[-1]
        if base.endswith(".git"):
            base = base[:-4]
        return base

    def _load_or_create_manifest(
        self, skill_dir: str, name: str, repo_url: str
    ) -> SkillManifest:
        manifest_path = os.path.join(skill_dir, "manifest.json")
        if os.path.isfile(manifest_path):
            manifest = SkillManifest.from_json(manifest_path)
        else:
            entry = self._find_entry_point(skill_dir) or "SKILL.md"
            manifest = SkillManifest(name=name, entry_point=entry)
        if repo_url:
            manifest.repo_url = repo_url
        return manifest

    @staticmethod
    def _save_manifest(skill_dir: str, manifest: SkillManifest) -> None:
        path = os.path.join(skill_dir, "manifest.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest.to_dict(), fh, indent=2, ensure_ascii=False)
