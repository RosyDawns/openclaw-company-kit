from __future__ import annotations

from datetime import datetime, timezone

from engine.models import Task, TaskState, Transition


class InvalidTransitionError(Exception):
    def __init__(self, from_state: TaskState, to_state: TaskState, message: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        self.message = message or (
            f"Invalid transition from {from_state.value} to {to_state.value}"
        )
        super().__init__(self.message)


_VALID_TRANSITIONS: dict[TaskState, list[TaskState]] = {
    TaskState.DRAFT: [TaskState.QUEUED],
    TaskState.QUEUED: [TaskState.RUNNING],
    TaskState.RUNNING: [TaskState.REVIEW, TaskState.BLOCKED],
    TaskState.REVIEW: [TaskState.APPROVED, TaskState.REJECTED],
    TaskState.APPROVED: [TaskState.DONE],
    TaskState.REJECTED: [TaskState.RUNNING],
    TaskState.BLOCKED: [TaskState.RUNNING],
    TaskState.DONE: [],
}


class StateMachine:
    def advance(
        self,
        task: Task,
        target_state: TaskState,
        reason: str = "",
        actor: str = "",
    ) -> Task:
        if not self.can_advance(task, target_state):
            raise InvalidTransitionError(task.state, target_state)

        now = datetime.now(timezone.utc)
        transition = Transition(
            from_state=task.state,
            to_state=target_state,
            timestamp=now,
            reason=reason or None,
            actor=actor or None,
        )
        task.state = target_state
        task.updated_at = now
        task.transitions.append(transition)
        return task

    def can_advance(self, task: Task, target_state: TaskState) -> bool:
        return target_state in _VALID_TRANSITIONS.get(task.state, [])

    def get_valid_targets(self, task: Task) -> list[TaskState]:
        return list(_VALID_TRANSITIONS.get(task.state, []))

    def get_transition_history(self, task: Task) -> list[Transition]:
        return list(task.transitions)
