"""Kanban API handlers."""

from __future__ import annotations

import json
import time
from pathlib import Path
from engine.models import TaskState
from engine.state_machine import InvalidTransitionError, StateMachine


_root_dir: Path | None = None
_state_machine = StateMachine()

_KANBAN_STATE_MAP: dict[str, TaskState] = {s.value: s for s in TaskState}

_STATUS_MAP = {
    "draft": "draft",
    "queued": "queued",
    "running": "running",
    "review": "review",
    "approved": "done",
    "done": "done",
    "blocked": "blocked",
    "rejected": "blocked",
}


def init(root_dir: Path) -> None:
    global _root_dir
    _root_dir = root_dir


def _mock_kanban_data() -> dict[str, list[dict]]:
    """Return mock kanban data when no real task history exists."""

    def _h(hours: float) -> str:
        t = time.time() - hours * 3600
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))

    return {
        "draft": [
            {"id": "t-001", "name": "接入飞书消息推送模块", "status": "draft", "role": "执行-后端", "priority": 1, "updatedAt": _h(2), "description": "对接飞书 Open API，实现群消息推送能力"},
            {"id": "t-002", "name": "设计权限管理方案", "status": "draft", "role": "路由-架构", "priority": 0, "updatedAt": _h(5), "description": "多租户场景下的 RBAC 权限体系设计"},
        ],
        "queued": [
            {"id": "t-003", "name": "优化任务调度队列", "status": "queued", "role": "执行-引擎", "priority": 1, "updatedAt": _h(1), "description": "引入优先级队列，支持 P0 任务插队执行"},
            {"id": "t-004", "name": "编写 E2E 测试脚本", "status": "queued", "role": "审核-QA", "priority": 2, "updatedAt": _h(8), "description": "覆盖核心工作流的端到端集成测试"},
        ],
        "running": [
            {"id": "t-006", "name": "实现看板面板前端", "status": "running", "role": "执行-前端", "priority": 0, "updatedAt": _h(0.5), "description": "6 列卡片布局，支持任务状态可视化"},
        ],
        "review": [
            {"id": "t-008", "name": "API 鉴权中间件", "status": "review", "role": "审核-安全", "priority": 0, "updatedAt": _h(3), "description": "JWT + Cookie 双模式认证，已提交 PR 待审"},
        ],
        "done": [
            {"id": "t-010", "name": "面板框架搭建", "status": "done", "role": "执行-前端", "priority": 1, "updatedAt": _h(24), "description": "侧边栏导航 + 面板路由 + 布局组件"},
            {"id": "t-011", "name": "CI 流水线配置", "status": "done", "role": "执行-DevOps", "priority": 1, "updatedAt": _h(48), "description": "GitHub Actions 构建、测试、发布流程"},
        ],
        "blocked": [
            {"id": "t-013", "name": "Discord 机器人集成", "status": "blocked", "role": "路由-IM", "priority": 2, "updatedAt": _h(12), "description": "等待 Discord 开发者账号审批"},
        ],
    }


def _load_tasks_from_history() -> dict[str, list[dict]] | None:
    """Try to read real tasks from task-history.jsonl."""
    if _root_dir is None:
        return None

    history_candidates = [
        _root_dir / "task-history.jsonl",
        _root_dir / ".openclaw-company" / "run" / "control-task-history.jsonl",
    ]

    for path in history_candidates:
        if not path.is_file():
            continue
        columns: dict[str, list[dict]] = {
            "draft": [], "queued": [], "running": [], "review": [],
            "done": [], "blocked": [],
        }
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                status_raw = row.get("status", row.get("state", "draft"))
                col = _STATUS_MAP.get(status_raw, "draft")
                columns[col].append({
                    "id": row.get("id", ""),
                    "name": row.get("name", ""),
                    "status": status_raw,
                    "role": row.get("role", ""),
                    "priority": row.get("priority"),
                    "updatedAt": row.get("updatedAt", row.get("finishedAt", row.get("startedAt", ""))),
                    "description": row.get("description", row.get("error", "")),
                })
        except Exception:
            continue
        if any(columns[k] for k in columns):
            return columns

    return None


def _find_task_in_columns(columns: dict[str, list[dict]], task_id: str) -> dict | None:
    for col_tasks in columns.values():
        for task in col_tasks:
            if task.get("id") == task_id:
                return task
    return None


def handle_get_kanban(params: dict, body: dict | None) -> dict:
    """GET /api/kanban — return tasks grouped by status column."""
    columns = _load_tasks_from_history()
    if columns is None:
        columns = _mock_kanban_data()
    return {"ok": True, "columns": columns}


def handle_kanban_move(params: dict, body: dict | None) -> dict:
    """POST /api/kanban/move — validate and apply a task state transition."""
    if not body:
        return {"ok": False, "error": "缺少请求体", "_status": 400}

    task_id = body.get("taskId", "").strip()
    target_state_str = body.get("targetState", "").strip()

    if not task_id or not target_state_str:
        return {"ok": False, "error": "taskId 和 targetState 为必填项", "_status": 400}

    target_ts = _KANBAN_STATE_MAP.get(target_state_str)
    if target_ts is None:
        return {"ok": False, "error": f"未知状态: {target_state_str}", "_status": 400}

    columns = _load_tasks_from_history()
    if columns is None:
        columns = _mock_kanban_data()

    task_data = _find_task_in_columns(columns, task_id)
    if task_data is None:
        return {"ok": False, "error": f"找不到任务: {task_id}", "_status": 404}

    current_status = task_data.get("status", "draft")
    current_ts = _KANBAN_STATE_MAP.get(current_status)
    if current_ts is None:
        return {"ok": False, "error": f"任务当前状态无效: {current_status}", "_status": 400}

    from engine.models import Task
    dummy_task = Task(id=task_id, name=task_data.get("name", ""), state=current_ts)

    try:
        _state_machine.advance(dummy_task, target_ts, reason="kanban drag-and-drop", actor="console-ui")
    except InvalidTransitionError:
        valid = _state_machine.get_valid_targets(dummy_task)
        valid_names = [s.value for s in valid] or ["(无)"]
        return {
            "ok": False,
            "error": f"非法转换: {current_status} → {target_state_str}。允许的目标状态: {', '.join(valid_names)}",
        }

    return {
        "ok": True,
        "taskId": task_id,
        "from": current_status,
        "to": target_state_str,
    }
