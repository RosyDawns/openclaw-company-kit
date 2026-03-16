"""Task API handlers."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from server.services.task_service import TaskService

_cs: Any = None
_task_service: TaskService | None = None


def init(cs_module: Any, *, task_service: TaskService | None = None) -> None:
    """Bind the control-server module and optional service instances."""
    global _cs, _task_service
    _cs = cs_module
    if task_service is not None:
        _task_service = task_service


def handle_get_task(params: dict, body: dict | None) -> dict:
    """GET /api/task/{id}"""
    assert _task_service is not None
    task_id = params.get("id", "").strip()
    task = _task_service.get_task(task_id)
    if not task:
        return {"ok": False, "error": "task not found", "_status": 404}
    return {"ok": True, "task": task}


def handle_create_task(params: dict, body: dict | None) -> dict:
    """POST /api/task — placeholder for future generalised task creation."""
    return {"ok": False, "error": "not implemented", "_status": 501}
