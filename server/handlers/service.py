"""Service management API handlers."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from server.services.health_service import HealthService
    from server.services.task_service import TaskService

_cs: Any = None
_health_service: HealthService | None = None
_task_service: TaskService | None = None


def init(
    cs_module: Any,
    *,
    health_service: HealthService | None = None,
    task_service: TaskService | None = None,
) -> None:
    """Bind the control-server module and optional service instances."""
    global _cs, _health_service, _task_service
    _cs = cs_module
    if health_service is not None:
        _health_service = health_service
    if task_service is not None:
        _task_service = task_service


def handle_service_status(params: dict, body: dict | None) -> dict:
    """GET /api/service/status"""
    assert _health_service is not None
    return {"ok": True, "service": _health_service.get_service_status()}


def handle_service_restart(params: dict, body: dict | None) -> dict:
    """POST /api/service/restart"""
    assert _task_service is not None
    task = _task_service.create_task(
        "restart",
        [
            ("stop", ["bash", "scripts/stop.sh"]),
            ("start", ["bash", "scripts/start.sh"]),
            ("healthcheck", ["bash", "scripts/healthcheck.sh"], [0, 1]),
        ],
    )
    return {"ok": True, "taskId": task["id"]}


def handle_preflight(params: dict, body: dict | None) -> dict:
    """GET /api/preflight"""
    assert _health_service is not None
    return _health_service.preflight_check()
