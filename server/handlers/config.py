"""Configuration API handlers.

These handlers delegate business logic to :class:`ConfigService`.  The
``_cs`` module reference is kept for fields that still live on the
control-server module (auth globals, ROOT_DIR).
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from server.services.config_service import ConfigService
    from server.services.health_service import HealthService
    from server.services.task_service import TaskService

_cs: Any = None
_config_service: ConfigService | None = None
_health_service: HealthService | None = None
_task_service: TaskService | None = None


def init(
    cs_module: Any,
    *,
    config_service: ConfigService | None = None,
    health_service: HealthService | None = None,
    task_service: TaskService | None = None,
) -> None:
    """Bind the control-server module and optional service instances."""
    global _cs, _config_service, _health_service, _task_service
    _cs = cs_module
    if config_service is not None:
        _config_service = config_service
    if health_service is not None:
        _health_service = health_service
    if task_service is not None:
        _task_service = task_service


def handle_get_config(params: dict, body: dict | None) -> dict:
    """GET /api/config"""
    assert _config_service is not None
    cfg = _config_service.get_config()
    first_time = not _config_service.env_file.exists() or not cfg.get("GROUP_ID", "").strip()

    service_status = (
        _health_service.get_service_status()
        if _health_service is not None
        else _cs.collect_service_status(cfg)
    )

    return {
        "ok": True,
        "config": cfg,
        "firstTime": first_time,
        "service": service_status,
        "server": {"rootDir": str(_config_service.root_dir)},
        "auth": {  # TODO: decouple from global state
            "enabled": _cs.AUTH_TOKEN is not None,
            "ephemeral": _cs.AUTH_TOKEN_EPHEMERAL,
            "cookieName": _cs.AUTH_COOKIE_NAME,
        },
    }


def handle_save_config(params: dict, body: dict | None) -> dict:
    """POST /api/config/save"""
    assert _config_service is not None
    payload = body or {}

    try:
        result = _config_service.save_config(payload)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "_status": 400}

    return result


def handle_apply_config(params: dict, body: dict | None) -> dict:
    """POST /api/config/apply"""
    assert _config_service is not None and _task_service is not None
    payload = body or {}

    try:
        _config_service.apply_config(payload)
    except ValueError as exc:
        return {"ok": False, "error": str(exc), "_status": 400}

    task = _task_service.create_task(
        "apply",
        [
            ("stop", ["bash", "scripts/stop.sh"]),
            ("onboard", ["bash", "scripts/onboard-wrapper.sh"]),
            ("install", ["bash", "scripts/install.sh"]),
            ("start", ["bash", "scripts/start.sh"]),
            ("healthcheck", ["bash", "scripts/healthcheck.sh"], [0, 1]),
        ],
    )
    return {"ok": True, "taskId": task["id"]}
