"""Sessions panel API handlers — task history, stats and CSV export."""

from __future__ import annotations

import csv
import io
import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from server.middleware.pagination import extract_pagination, paginate

_cs: Any = None
_history_path: Path | None = None

_MOCK_ROLE_NAMES = [
    "技术总监", "高级开发", "产品经理", "代码审查员",
    "QA测试", "增长运营", "AI技术员", "热搜分析师",
]

_MOCK_TASK_NAMES = [
    "每日站会摘要", "代码审查 PR#42", "Issue 分类整理",
    "热搜数据抓取", "周报生成", "依赖安全扫描",
    "API 文档更新", "性能基准测试", "数据库迁移脚本",
    "前端构建优化", "日志归档清理", "用户反馈分析",
]


def init(cs_module: Any, *, history_file: Path | None = None) -> None:
    global _cs, _history_path
    _cs = cs_module
    if history_file is not None:
        _history_path = history_file


def _get_history_path() -> Path | None:
    if _history_path is not None:
        return _history_path
    if _cs is not None and hasattr(_cs, "task_history_path"):
        return _cs.task_history_path()
    return None


def _read_history() -> list[dict]:
    path = _get_history_path()
    if path is None or not path.exists():
        return []
    entries: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _generate_mock_history(count: int = 60) -> list[dict]:
    """Deterministic mock data when no real history exists."""
    rng = random.Random(42)
    now = time.time()
    items: list[dict] = []
    for i in range(count):
        offset = rng.randint(300, 86400 * 14)
        started_epoch = now - offset
        duration = rng.randint(10, 600)
        status = rng.choices(["success", "failed", "running"], weights=[7, 2, 1])[0]
        finished_epoch = started_epoch + duration if status != "running" else None
        error = None
        if status == "failed":
            error = rng.choice([
                "[ERROR] 连接超时",
                "[ERROR] 权限不足",
                "Traceback: IndexError",
                "[ERROR] 依赖缺失",
            ])
        items.append({
            "id": f"mock-{i:04d}",
            "name": rng.choice(_MOCK_TASK_NAMES),
            "status": status,
            "role": rng.choice(_MOCK_ROLE_NAMES),
            "startedAt": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started_epoch)),
            "finishedAt": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(finished_epoch)) if finished_epoch else None,
            "durationSec": duration if status != "running" else None,
            "error": error,
        })
    items.sort(key=lambda x: x["startedAt"], reverse=True)
    return items


def _filter_items(items: list[dict], params: dict) -> list[dict]:
    status = params.get("status")
    date_from = params.get("date_from")
    date_to = params.get("date_to")

    if not status and not date_from and not date_to:
        return items

    filtered = items
    if status:
        filtered = [x for x in filtered if x.get("status") == status]
    if date_from:
        filtered = [x for x in filtered if (x.get("startedAt") or "") >= date_from]
    if date_to:
        dt_end = date_to + " 23:59:59" if len(date_to) == 10 else date_to
        filtered = [x for x in filtered if (x.get("startedAt") or "") <= dt_end]
    return filtered


def _format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60}s"
    h, rem = divmod(s, 3600)
    return f"{h}h {rem // 60}m"


def _compute_stats(items: list[dict], period: str) -> dict:
    now = datetime.now()
    if period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    else:
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)

    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    window = [x for x in items if (x.get("startedAt") or "") >= cutoff_str]

    total = len(window)
    success_count = sum(1 for x in window if x.get("status") == "success")
    rate = round(success_count / total * 100) if total > 0 else 0

    durations = [x["durationSec"] for x in window if x.get("durationSec") is not None]
    avg_dur = sum(durations) / len(durations) if durations else 0

    longest = None
    if durations:
        longest_item = max(window, key=lambda x: x.get("durationSec") or 0)
        longest = {
            "name": longest_item.get("name", "—"),
            "duration": _format_duration(longest_item.get("durationSec")),
        }

    return {
        "total": total,
        "success": success_count,
        "successRate": f"{rate}%",
        "avgDuration": _format_duration(avg_dur),
        "longestTask": longest,
    }


# ------------------------------------------------------------------
# Handlers
# ------------------------------------------------------------------

def handle_get_sessions(params: dict, body: dict | None) -> dict:
    """GET /api/sessions — paginated history list."""
    items = _read_history()
    if not items:
        items = _generate_mock_history()

    for item in items:
        item.setdefault("role", "—")
    items.sort(key=lambda x: x.get("startedAt") or "", reverse=True)

    items = _filter_items(items, params)
    page, per_page = extract_pagination(params)
    result = paginate(items, page, per_page)
    return {"ok": True, "data": result}


def handle_get_session_detail(params: dict, body: dict | None) -> dict:
    """GET /api/sessions/{id} — single session detail with logs."""
    session_id = params.get("id", "")
    items = _read_history()
    if not items:
        items = _generate_mock_history()

    for item in items:
        if item.get("id") == session_id:
            item.setdefault("logs", [])
            item.setdefault("role", "—")
            return {"ok": True, "session": item}

    return {"ok": False, "error": "session not found", "_status": 404}


def handle_get_session_stats(params: dict, body: dict | None) -> dict:
    """GET /api/sessions/stats — aggregate statistics."""
    period = params.get("period", "day")
    if period not in ("day", "week", "month"):
        period = "day"

    items = _read_history()
    if not items:
        items = _generate_mock_history()

    stats = _compute_stats(items, period)
    return {"ok": True, "stats": stats}


def handle_export_sessions(params: dict, body: dict | None) -> dict:
    """GET /api/sessions/export — CSV export.

    Returns CSV as a string inside the JSON envelope.  The frontend
    triggers the actual file download via a Blob.
    """
    items = _read_history()
    if not items:
        items = _generate_mock_history()

    items.sort(key=lambda x: x.get("startedAt") or "", reverse=True)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ID", "任务名称", "状态", "角色", "开始时间", "结束时间", "耗时(秒)", "错误"])
    for row in items:
        writer.writerow([
            row.get("id", ""),
            row.get("name", ""),
            row.get("status", ""),
            row.get("role", ""),
            row.get("startedAt", ""),
            row.get("finishedAt", ""),
            row.get("durationSec", ""),
            row.get("error", ""),
        ])

    return {"ok": True, "csv": buf.getvalue(), "filename": "sessions-export.csv"}
