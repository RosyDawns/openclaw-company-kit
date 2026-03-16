"""Officials (roles) API handlers."""

from __future__ import annotations

import json
import time
from pathlib import Path

_root_dir: Path | None = None

_LAYER_META = {
    "dispatcher": {"label": "路由层", "order": 0},
    "dispatcher_sub": {"label": "路由层", "order": 0},
    "reviewer": {"label": "审核层", "order": 1},
    "executor": {"label": "执行层", "order": 2},
    "executor_sub": {"label": "执行层", "order": 2},
}


def init(root_dir: Path) -> None:
    global _root_dir
    _root_dir = root_dir


def _load_role_config() -> list[dict]:
    if _root_dir is None:
        return []
    config_path = _root_dir / "engine" / "role_config.json"
    if not config_path.is_file():
        return []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return data.get("roles", [])
    except Exception:
        return []


def _enrich_role(role: dict) -> dict:
    """Add computed fields useful for the frontend."""
    layer_raw = role.get("layer", "executor")
    meta = _LAYER_META.get(layer_raw, {"label": layer_raw, "order": 9})
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "name": role.get("name", ""),
        "displayName": role.get("display_name", role.get("name", "")),
        "layer": layer_raw,
        "layerLabel": meta["label"],
        "layerOrder": meta["order"],
        "capabilities": role.get("capabilities", []),
        "reviewScope": role.get("review_scope", []),
        "wipLimit": role.get("wip_limit", 1),
        "wipCurrent": 0,
        "allowedCallees": role.get("allowed_callees", []),
        "cronJobs": role.get("cron_jobs", []),
        "dependencies": role.get("dependencies", []),
        "lastActive": now_iso,
    }


def handle_get_officials(params: dict, body: dict | None) -> dict:
    """GET /api/officials — role list with layer metadata."""
    roles = _load_role_config()
    enriched = [_enrich_role(r) for r in roles]
    enriched.sort(key=lambda r: (r["layerOrder"], r["name"]))

    layers = [
        {"key": "dispatcher", "label": "路由层", "color": "blue", "order": 0},
        {"key": "reviewer", "label": "审核层", "color": "orange", "order": 1},
        {"key": "executor", "label": "执行层", "color": "green", "order": 2},
    ]

    return {"ok": True, "roles": enriched, "layers": layers}
