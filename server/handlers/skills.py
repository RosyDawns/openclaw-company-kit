"""Skills API handlers."""

from __future__ import annotations

import logging

from engine.skill_manager import SkillManager

logger = logging.getLogger(__name__)

_manager: SkillManager | None = None


def init(skills_dir: str | None = None) -> None:
    global _manager
    _manager = SkillManager(skills_dir=skills_dir)


def _mgr() -> SkillManager:
    assert _manager is not None, "skills handler not initialised — call init() first"
    return _manager


def handle_get_skills(params: dict, body: dict | None) -> dict:
    """GET /api/skills — list locally installed skills."""
    skills = _mgr().list_local()
    return {
        "ok": True,
        "skills": [s.to_dict() for s in skills],
    }


def handle_add_skill(params: dict, body: dict | None) -> dict:
    """POST /api/skills/add — install a remote skill from a git repo."""
    body = body or {}
    repo_url = (body.get("repoUrl") or "").strip()
    if not repo_url:
        return {"ok": False, "error": "missing 'repoUrl'", "_status": 400}

    name = (body.get("name") or "").strip() or None
    try:
        manifest = _mgr().add_remote(repo_url, name=name)
        return {"ok": True, "skill": manifest.to_dict()}
    except FileExistsError as exc:
        return {"ok": False, "error": str(exc), "_status": 409}
    except Exception as exc:
        logger.exception("Failed to install skill from %s", repo_url)
        return {"ok": False, "error": str(exc), "_status": 500}


def handle_update_skill(params: dict, body: dict | None) -> dict:
    """POST /api/skills/update/{name} — pull latest for an installed skill."""
    name = params.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "missing skill name", "_status": 400}

    try:
        manifest = _mgr().update_remote(name)
        return {"ok": True, "skill": manifest.to_dict()}
    except FileNotFoundError as exc:
        return {"ok": False, "error": str(exc), "_status": 404}
    except Exception as exc:
        logger.exception("Failed to update skill %s", name)
        return {"ok": False, "error": str(exc), "_status": 500}


def handle_remove_skill(params: dict, body: dict | None) -> dict:
    """POST /api/skills/remove/{name} — uninstall a skill."""
    name = params.get("name", "").strip()
    if not name:
        return {"ok": False, "error": "missing skill name", "_status": 400}

    removed = _mgr().remove(name)
    if not removed:
        return {"ok": False, "error": f"skill '{name}' not found", "_status": 404}
    return {"ok": True}
