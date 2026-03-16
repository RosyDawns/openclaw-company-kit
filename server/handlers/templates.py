"""Templates API handlers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from server.middleware.pagination import extract_pagination, paginate


_root_dir: Path | None = None


def init(root_dir: Path) -> None:
    global _root_dir
    _root_dir = root_dir


def _templates_dir() -> Path:
    assert _root_dir is not None
    return _root_dir / "templates"


def _scan_template_files() -> list[dict]:
    tpl_dir = _templates_dir()
    if not tpl_dir.is_dir():
        return []

    results: list[dict] = []
    pattern = re.compile(r"^workflow-jobs\.(.+)\.json$")
    for f in sorted(tpl_dir.iterdir()):
        m = pattern.match(f.name)
        if not m:
            continue
        name = m.group(1)
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            jobs = data.get("jobs", [])
            description = data.get("description", "")
            if not description and jobs:
                agents = sorted({j.get("agent", "") for j in jobs if j.get("agent")})
                description = f"包含 {len(jobs)} 个任务，涉及角色: {', '.join(agents)}"
            results.append({
                "name": name,
                "filename": f.name,
                "description": description,
                "jobCount": len(jobs),
            })
        except Exception:
            results.append({
                "name": name,
                "filename": f.name,
                "description": "无法解析",
                "jobCount": 0,
            })
    return results


def _read_template(name: str) -> dict | None:
    tpl_dir = _templates_dir()
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "", name)
    path = tpl_dir / f"workflow-jobs.{safe_name}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"name": safe_name, "filename": path.name, **data}
    except Exception:
        return None


def _read_env_template(env_path: Path) -> str:
    """Read current WORKFLOW_TEMPLATE from .env."""
    if not env_path.is_file():
        return "default"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("WORKFLOW_TEMPLATE="):
            val = line.split("=", 1)[1].strip().strip("'\"")
            return val or "default"
    return "default"


def handle_get_templates(params: dict, body: dict | None) -> dict:
    """GET /api/templates — template list with optional pagination."""
    templates = _scan_template_files()
    assert _root_dir is not None
    active = _read_env_template(_root_dir / ".env")

    page, per_page = extract_pagination(params)
    paged = paginate(templates, page, per_page)
    return {"ok": True, "templates": paged["items"], "active": active, "pagination": paged}


def handle_get_template_detail(params: dict, body: dict | None) -> dict:
    """GET /api/templates/{name} — single template detail."""
    name = params.get("name", "")
    if not name:
        return {"ok": False, "error": "missing template name", "_status": 400}
    detail = _read_template(name)
    if detail is None:
        return {"ok": False, "error": f"template '{name}' not found", "_status": 404}
    return {"ok": True, "template": detail}


def handle_activate_template(params: dict, body: dict | None) -> dict:
    """POST /api/templates/activate — switch active workflow template."""
    if not body or not body.get("name"):
        return {"ok": False, "error": "missing 'name' in body", "_status": 400}

    name = re.sub(r"[^a-zA-Z0-9_\-]", "", body["name"])
    assert _root_dir is not None
    tpl_path = _templates_dir() / f"workflow-jobs.{name}.json"
    if not tpl_path.is_file():
        return {"ok": False, "error": f"template '{name}' not found", "_status": 404}

    env_path = _root_dir / ".env"
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith("WORKFLOW_TEMPLATE="):
                lines[i] = f"WORKFLOW_TEMPLATE='{name}'"
                found = True
                break
        if not found:
            lines.append(f"WORKFLOW_TEMPLATE='{name}'")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        env_path.write_text(f"WORKFLOW_TEMPLATE='{name}'\n", encoding="utf-8")

    return {"ok": True, "active": name}
