from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from engine.models import Task
from engine.roles import RoleRegistry

logger = logging.getLogger(__name__)


class Priority(Enum):
    P0 = 0
    P1 = 1
    P2 = 2


@dataclass
class DispatchRule:
    task_type: str
    target_roles: list[str]
    requires_review: bool = True
    review_type: str = ""
    priority: Priority = Priority.P1


@dataclass
class DispatchRequest:
    task: Task
    task_type: str
    priority: Priority
    assigned_role: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    dispatched_at: Optional[float] = None


class PriorityQueue:
    def __init__(self) -> None:
        self._items: list[DispatchRequest] = []

    def push(self, request: DispatchRequest) -> None:
        self._items.append(request)
        self._items.sort(key=lambda r: r.priority.value)

    def pop(self) -> Optional[DispatchRequest]:
        if not self._items:
            return None
        return self._items.pop(0)

    def peek(self) -> Optional[DispatchRequest]:
        if not self._items:
            return None
        return self._items[0]

    def size(self) -> int:
        return len(self._items)

    def get_by_priority(self, priority: Priority) -> list[DispatchRequest]:
        return [r for r in self._items if r.priority == priority]


class WIPTracker:
    def __init__(self) -> None:
        self._wip_counts: dict[str, int] = {}

    def acquire(self, role: str, limit: int) -> bool:
        current = self._wip_counts.get(role, 0)
        if current >= limit:
            return False
        self._wip_counts[role] = current + 1
        return True

    def release(self, role: str) -> None:
        current = self._wip_counts.get(role, 0)
        if current > 0:
            self._wip_counts[role] = current - 1

    def get_count(self, role: str) -> int:
        return self._wip_counts.get(role, 0)

    def is_available(self, role: str, limit: int) -> bool:
        return self._wip_counts.get(role, 0) < limit


class Dispatcher:
    _DEFAULT_RULES: list[dict] = [
        {"task_type": "code", "target_roles": ["role-senior-dev"], "review_type": "code"},
        {"task_type": "test", "target_roles": ["role-qa-test"], "review_type": "code"},
        {"task_type": "product", "target_roles": ["role-product"], "requires_review": False, "review_type": ""},
        {"task_type": "design", "target_roles": ["role-tech-director"], "review_type": "design"},
        {"task_type": "ops", "target_roles": ["rd-company"], "review_type": "ops"},
        {"task_type": "growth", "target_roles": ["role-growth"], "requires_review": False, "review_type": ""},
    ]

    def __init__(self, role_registry: RoleRegistry) -> None:
        self._role_registry = role_registry
        self._rules: dict[str, DispatchRule] = {}
        self._queue = PriorityQueue()
        self._wip_tracker = WIPTracker()

    def register_rule(self, rule: DispatchRule) -> None:
        self._rules[rule.task_type] = rule

    def load_default_rules(self) -> None:
        for entry in self._DEFAULT_RULES:
            rule = DispatchRule(
                task_type=entry["task_type"],
                target_roles=entry["target_roles"],
                requires_review=entry.get("requires_review", True),
                review_type=entry.get("review_type", ""),
            )
            self.register_rule(rule)
        logger.info("Loaded %d default dispatch rules", len(self._DEFAULT_RULES))

    def dispatch(
        self,
        task: Task,
        task_type: str,
        priority: Priority = Priority.P1,
    ) -> DispatchRequest:
        rule = self._rules.get(task_type)
        if rule is None:
            raise ValueError(f"No dispatch rule for task type: {task_type}")

        request = DispatchRequest(
            task=task,
            task_type=task_type,
            priority=priority,
        )

        for role_name in rule.target_roles:
            role_def = self._role_registry.get_role(role_name)
            wip_limit = role_def.wip_limit if role_def else 1
            if self._wip_tracker.acquire(role_name, wip_limit):
                request.assigned_role = role_name
                request.dispatched_at = time.time()
                logger.info(
                    "Dispatched task %s (%s) to %s",
                    task.id, task_type, role_name,
                )
                return request

        self._queue.push(request)
        logger.info(
            "All target roles busy for task %s (%s), queued (priority=%s, queue_size=%d)",
            task.id, task_type, priority.name, self._queue.size(),
        )
        return request

    def try_dispatch_queued(self) -> list[DispatchRequest]:
        dispatched: list[DispatchRequest] = []
        remaining: list[DispatchRequest] = []

        while self._queue.size() > 0:
            request = self._queue.pop()
            if request is None:
                break

            rule = self._rules.get(request.task_type)
            if rule is None:
                remaining.append(request)
                continue

            assigned = False
            for role_name in rule.target_roles:
                role_def = self._role_registry.get_role(role_name)
                wip_limit = role_def.wip_limit if role_def else 1
                if self._wip_tracker.acquire(role_name, wip_limit):
                    request.assigned_role = role_name
                    request.dispatched_at = time.time()
                    dispatched.append(request)
                    assigned = True
                    logger.info(
                        "Dispatched queued task %s (%s) to %s",
                        request.task.id, request.task_type, role_name,
                    )
                    break

            if not assigned:
                remaining.append(request)

        for req in remaining:
            self._queue.push(req)

        return dispatched

    def complete_task(self, task: Task, role: str) -> list[DispatchRequest]:
        self._wip_tracker.release(role)
        logger.info("Released WIP for role %s (task %s)", role, task.id)
        return self.try_dispatch_queued()

    def get_queue_status(self) -> dict:
        return {
            "queue_size": self._queue.size(),
            "wip": dict(self._wip_tracker._wip_counts),
            "rules_count": len(self._rules),
            "queued_by_priority": {
                p.name: len(self._queue.get_by_priority(p))
                for p in Priority
            },
        }

    def get_rule(self, task_type: str) -> Optional[DispatchRule]:
        return self._rules.get(task_type)
