"""Skill manifest dataclass – describes a single installable Skill."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SkillManifest:
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    repo_url: str = ""
    entry_point: str = "SKILL.md"
    compatible_roles: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    installed_at: Optional[str] = None

    ALLOWED_EXTENSIONS = {".md", ".json", ".txt"}

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "repo_url": self.repo_url,
            "entry_point": self.entry_point,
            "compatible_roles": list(self.compatible_roles),
            "tags": list(self.tags),
            "installed_at": self.installed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SkillManifest":
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            repo_url=data.get("repo_url", ""),
            entry_point=data.get("entry_point", "SKILL.md"),
            compatible_roles=list(data.get("compatible_roles", [])),
            tags=list(data.get("tags", [])),
            installed_at=data.get("installed_at"),
        )

    @classmethod
    def from_json(cls, path: str) -> "SkillManifest":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)

    def validate(self) -> List[str]:
        """Return a list of validation errors (empty == valid)."""
        errors: List[str] = []
        if not self.name:
            errors.append("name is required")
        if not self.entry_point:
            errors.append("entry_point is required")
        else:
            ext = os.path.splitext(self.entry_point)[1].lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                errors.append(
                    f"entry_point must be {self.ALLOWED_EXTENSIONS}, got {ext}"
                )
        return errors
