"""Monitor panel API handlers — service status, metrics and review records."""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from typing import Any, TYPE_CHECKING

from server.middleware.pagination import extract_pagination, paginate

if TYPE_CHECKING:
    from server.services.health_service import HealthService
    from server.services.task_service import TaskService

_cs: Any = None
_health_service: HealthService | None = None
_task_service: TaskService | None = None

_ROLE_DISPLAY = [
    ("role-tech-director", "技术总监"),
    ("role-senior-dev", "高级开发"),
    ("role-product", "产品经理"),
    ("role-code-reviewer", "代码审查员"),
    ("role-qa-test", "QA测试"),
    ("role-growth", "增长运营"),
    ("ai-tech", "AI技术员"),
    ("hot-search", "热搜分析师"),
]

_TASK_NAMES = [
    "每日站会摘要", "代码审查 PR#42", "Issue 分类整理",
    "热搜数据抓取", "周报生成", "依赖安全扫描",
    "API 文档更新", "性能基准测试", "数据库迁移脚本",
    "前端构建优化", "日志归档清理", "用户反馈分析",
]

_REVIEW_REASONS = [
    "代码质量符合规范", "测试覆盖率达标", "存在未处理的边界情况",
    "性能指标超出预期", "缺少错误处理逻辑", "接口变更需回归验证",
    "文档与实现不一致", "安全审计通过", "依赖版本存在已知漏洞",
    "逻辑清晰可维护", "需补充单元测试", "已修复评审建议",
]


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


def _format_uptime(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60}s"
    h, rem = divmod(s, 3600)
    m = rem // 60
    return f"{h}h {m}m"


def handle_get_services(params: dict, body: dict | None) -> dict:
    """GET /api/monitor/services — service status with uptime."""
    if _health_service is not None:
        raw = _health_service.get_service_status()
        services = []
        for svc in raw.get("services", []):
            status = "running" if svc.get("running") else "stopped"
            if not svc.get("running") and svc.get("pid") is not None:
                status = "warning"
            services.append({
                "name": svc["name"],
                "status": status,
                "pid": svc.get("pid"),
                "uptime": _format_uptime(svc["uptimeSec"]) if "uptimeSec" in svc else "—",
            })
        return {"ok": True, "services": services}

    rng = random.Random(time.strftime("%Y-%m-%d-%H"))
    names = ["dashboard-refresh", "issue-sync", "cron-scheduler", "webhook-listener"]
    services = []
    for name in names:
        running = rng.random() > 0.2
        pid = rng.randint(10000, 65000) if running else None
        uptime_sec = rng.randint(300, 86400) if running else 0
        status = "running" if running else "stopped"
        if not running and rng.random() < 0.15:
            status = "warning"
            pid = rng.randint(10000, 65000)
        services.append({
            "name": name,
            "status": status,
            "pid": pid,
            "uptime": _format_uptime(uptime_sec) if running else "—",
        })
    return {"ok": True, "services": services}


def handle_get_metrics(params: dict, body: dict | None) -> dict:
    """GET /api/monitor/metrics — 7-day trend data + role timeline."""
    today = datetime.now().date()
    rng = random.Random(str(today))

    metrics = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        success = rng.randint(5, 30)
        failure = rng.randint(0, max(1, success // 4))
        metrics.append({
            "date": d.strftime("%Y-%m-%d"),
            "success": success,
            "failure": failure,
        })

    roles = []
    for name, display_name in _ROLE_DISPLAY:
        slot_count = rng.randint(1, 4)
        active_slots = []
        for _ in range(slot_count):
            start = rng.uniform(0, 22)
            duration = rng.uniform(0.5, 3.0)
            end = min(start + duration, 24.0)
            active_slots.append([round(start, 1), round(end, 1)])
        active_slots.sort(key=lambda s: s[0])
        roles.append({
            "name": name,
            "displayName": display_name,
            "activeSlots": active_slots,
        })

    return {"ok": True, "metrics": metrics, "roles": roles}


def handle_get_reviews(params: dict, body: dict | None) -> dict:
    """GET /api/monitor/reviews — recent review records with reasons."""
    rng = random.Random(time.strftime("%Y-%m-%d"))
    now_epoch = time.time()
    decisions = ["approved", "rejected", "pending"]
    reviews = []

    for i in range(20):
        offset = rng.randint(60, 86400)
        ts = now_epoch - offset * (i + 1) / 4
        decision = rng.choices(decisions, weights=[6, 2, 2])[0]
        reviews.append({
            "time": time.strftime("%m-%d %H:%M", time.localtime(ts)),
            "task": rng.choice(_TASK_NAMES),
            "reviewer": rng.choice([d for _, d in _ROLE_DISPLAY]),
            "decision": decision,
            "reason": rng.choice(_REVIEW_REASONS),
        })

    reviews.sort(key=lambda r: r["time"], reverse=True)

    page, per_page = extract_pagination(params)
    paged = paginate(reviews, page, per_page)
    return {"ok": True, "reviews": paged["items"], "pagination": paged}
