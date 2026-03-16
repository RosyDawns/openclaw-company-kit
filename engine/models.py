from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class TaskState(Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    REVIEW = "review"
    APPROVED = "approved"
    DONE = "done"
    BLOCKED = "blocked"
    REJECTED = "rejected"


@dataclass
class Transition:
    from_state: TaskState
    to_state: TaskState
    timestamp: datetime
    reason: Optional[str] = None
    actor: Optional[str] = None


@dataclass
class Task:
    id: str
    name: str
    state: TaskState = TaskState.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    transitions: list[Transition] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
