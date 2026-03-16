from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from engine.models import Task, TaskState
from engine.state_machine import StateMachine

logger = logging.getLogger(__name__)


class ReviewMode(Enum):
    AUTO = "auto"
    MANUAL = "manual"
    HYBRID = "hybrid"


class ReviewDecision(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


@dataclass
class ReviewCriteria:
    task_type: str
    mode: ReviewMode
    auto_rules: list[Callable[[Task], bool]] = field(default_factory=list)
    reviewer_role: str = ""
    timeout_hours: float = 24.0


@dataclass
class ReviewRequest:
    task: Task
    criteria: ReviewCriteria
    decision: ReviewDecision = ReviewDecision.PENDING
    reviewer: str = ""
    reason: str = ""
    created_at: float = field(default_factory=time.time)
    decided_at: Optional[float] = None


class ReviewGate:

    _ROUTE_TABLE: dict[str, str] = {
        "code": "role-code-reviewer",
        "security": "role-code-reviewer",
        "design": "role-tech-director",
        "architecture": "role-tech-director",
    }

    _DUAL_REVIEW_TYPES: frozenset[str] = frozenset({"ops"})

    def __init__(
        self,
        state_machine: StateMachine,
        rules_config: dict | None = None,
    ):
        self._state_machine = state_machine
        self._criteria_map: dict[str, ReviewCriteria] = {}
        self._pending_reviews: dict[str, ReviewRequest] = {}
        self._reviewer_bindings: dict[str, str] = {}
        if rules_config:
            self.load_rules(rules_config)

    def load_rules(self, config: dict) -> None:
        for entry in config.get("rules", []):
            criteria = ReviewCriteria(
                task_type=entry["task_type"],
                mode=ReviewMode(entry["mode"]),
                reviewer_role=entry.get("reviewer_role", ""),
                timeout_hours=entry.get("timeout_hours", 24.0),
            )
            self._criteria_map[criteria.task_type] = criteria

    def submit_for_review(self, task: Task, task_type: str) -> ReviewRequest:
        if task.state != TaskState.REVIEW:
            raise ValueError(
                f"Task must be in REVIEW state, got {task.state.value}"
            )

        criteria = self._criteria_map.get(task_type)
        if criteria is None:
            criteria = ReviewCriteria(task_type=task_type, mode=ReviewMode.MANUAL)

        if criteria.mode == ReviewMode.AUTO:
            return self._process_auto(task, criteria)
        if criteria.mode == ReviewMode.HYBRID:
            return self._process_hybrid(task, criteria)
        return self._create_pending(task, criteria)

    def _process_auto(self, task: Task, criteria: ReviewCriteria) -> ReviewRequest:
        if all(rule(task) for rule in criteria.auto_rules):
            return self._auto_approve(task, criteria)
        return self._create_pending(task, criteria)

    def _process_hybrid(self, task: Task, criteria: ReviewCriteria) -> ReviewRequest:
        if all(rule(task) for rule in criteria.auto_rules):
            return self._auto_approve(task, criteria)
        return self._create_pending(task, criteria)

    def _auto_approve(self, task: Task, criteria: ReviewCriteria) -> ReviewRequest:
        self._state_machine.advance(
            task, TaskState.APPROVED, reason="Auto-approved: all criteria passed"
        )
        logger.info("Task %s auto-approved", task.id)
        return ReviewRequest(
            task=task,
            criteria=criteria,
            decision=ReviewDecision.APPROVED,
            reviewer="system",
            reason="Auto-approved: all criteria passed",
            decided_at=time.time(),
        )

    def _create_pending(self, task: Task, criteria: ReviewCriteria) -> ReviewRequest:
        request = ReviewRequest(task=task, criteria=criteria)
        self._pending_reviews[task.id] = request
        logger.info("Task %s pending review (%s)", task.id, criteria.reviewer_role)
        return request

    def approve(self, task_id: str, reviewer: str, reason: str = "") -> Task:
        request = self._pending_reviews.pop(task_id)
        request.decision = ReviewDecision.APPROVED
        request.reviewer = reviewer
        request.reason = reason
        request.decided_at = time.time()

        self._state_machine.advance(
            request.task, TaskState.APPROVED, reason=reason, actor=reviewer
        )
        logger.info("Task %s approved by %s", task_id, reviewer)
        return request.task

    def reject(self, task_id: str, reviewer: str, reason: str) -> Task:
        if not reason:
            raise ValueError("Reject reason is required")

        request = self._pending_reviews.pop(task_id)
        request.decision = ReviewDecision.REJECTED
        request.reviewer = reviewer
        request.reason = reason
        request.decided_at = time.time()

        task = request.task
        task.metadata["reject_reason"] = reason
        task.metadata["reject_count"] = task.metadata.get("reject_count", 0) + 1

        self._state_machine.advance(
            task, TaskState.REJECTED, reason=reason, actor=reviewer
        )
        logger.info("Task %s rejected by %s: %s", task_id, reviewer, reason)
        return task

    # -- routing & dual-review helpers --

    def bind_reviewer(self, task_type: str, reviewer_role: str) -> None:
        self._reviewer_bindings[task_type] = reviewer_role

    def auto_route(self, task_type: str) -> str:
        if task_type in self._ROUTE_TABLE:
            return self._ROUTE_TABLE[task_type]

        bound = self._reviewer_bindings.get(task_type)
        if bound:
            return bound

        criteria = self._criteria_map.get(task_type)
        if criteria and criteria.reviewer_role:
            return criteria.reviewer_role

        return ""

    def submit_for_review_with_routing(
        self, task: Task, task_type: str
    ) -> ReviewRequest:
        reviewer = self.auto_route(task_type)
        request = self.submit_for_review(task, task_type)
        if reviewer:
            request.reviewer = reviewer
        return request

    def requires_dual_review(self, task_type: str) -> bool:
        return task_type in self._DUAL_REVIEW_TYPES

    def create_dual_review(
        self, task: Task, task_type: str
    ) -> list[ReviewRequest]:
        if task.state != TaskState.REVIEW:
            raise ValueError(
                f"Task must be in REVIEW state, got {task.state.value}"
            )

        reviewers = ["role-code-reviewer", "role-tech-director"]
        requests: list[ReviewRequest] = []
        for reviewer in reviewers:
            criteria = self._criteria_map.get(task_type)
            if criteria is None:
                criteria = ReviewCriteria(
                    task_type=task_type, mode=ReviewMode.MANUAL
                )
            req = ReviewRequest(task=task, criteria=criteria, reviewer=reviewer)
            requests.append(req)

        self._pending_reviews[task.id] = requests[0]
        return requests

    def get_pending_reviews(self) -> list[ReviewRequest]:
        return list(self._pending_reviews.values())

    def get_review_status(self, task_id: str) -> ReviewRequest | None:
        return self._pending_reviews.get(task_id)
