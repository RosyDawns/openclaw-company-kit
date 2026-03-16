from __future__ import annotations

import unittest
from datetime import datetime, timezone

from engine.models import Task, TaskState
from engine.state_machine import InvalidTransitionError, StateMachine


class TestStateMachine(unittest.TestCase):
    def setUp(self) -> None:
        self.sm = StateMachine()
        self.task = Task(id="t-001", name="Test Task")

    def _advance_through(self, *states: TaskState) -> None:
        for s in states:
            self.sm.advance(self.task, s)

    def test_valid_transition_draft_to_queued(self) -> None:
        result = self.sm.advance(self.task, TaskState.QUEUED)
        self.assertEqual(result.state, TaskState.QUEUED)
        self.assertEqual(len(self.task.transitions), 1)
        self.assertEqual(self.task.transitions[0].from_state, TaskState.DRAFT)
        self.assertEqual(self.task.transitions[0].to_state, TaskState.QUEUED)

    def test_valid_transition_full_happy_path(self) -> None:
        path = [
            TaskState.QUEUED,
            TaskState.RUNNING,
            TaskState.REVIEW,
            TaskState.APPROVED,
            TaskState.DONE,
        ]
        for target in path:
            self.sm.advance(self.task, target)
        self.assertEqual(self.task.state, TaskState.DONE)
        self.assertEqual(len(self.task.transitions), 5)

    def test_invalid_transition_raises_error(self) -> None:
        with self.assertRaises(InvalidTransitionError) as ctx:
            self.sm.advance(self.task, TaskState.RUNNING)
        self.assertEqual(ctx.exception.from_state, TaskState.DRAFT)
        self.assertEqual(ctx.exception.to_state, TaskState.RUNNING)

    def test_blocked_and_recovery(self) -> None:
        self._advance_through(TaskState.QUEUED, TaskState.RUNNING)
        self.sm.advance(self.task, TaskState.BLOCKED, reason="Waiting on dependency")
        self.assertEqual(self.task.state, TaskState.BLOCKED)
        self.sm.advance(self.task, TaskState.RUNNING)
        self.assertEqual(self.task.state, TaskState.RUNNING)
        self.assertEqual(len(self.task.transitions), 4)

    def test_rejected_and_retry(self) -> None:
        self._advance_through(
            TaskState.QUEUED, TaskState.RUNNING, TaskState.REVIEW,
        )
        self.sm.advance(self.task, TaskState.REJECTED, reason="Needs rework")
        self.sm.advance(self.task, TaskState.RUNNING)
        self.sm.advance(self.task, TaskState.REVIEW)
        self.sm.advance(self.task, TaskState.APPROVED)
        self.sm.advance(self.task, TaskState.DONE)
        self.assertEqual(self.task.state, TaskState.DONE)
        self.assertEqual(len(self.task.transitions), 8)

    def test_done_is_terminal(self) -> None:
        self._advance_through(
            TaskState.QUEUED, TaskState.RUNNING, TaskState.REVIEW,
            TaskState.APPROVED, TaskState.DONE,
        )
        for target in TaskState:
            with self.assertRaises(InvalidTransitionError):
                self.sm.advance(self.task, target)

    def test_can_advance_returns_bool(self) -> None:
        self.assertTrue(self.sm.can_advance(self.task, TaskState.QUEUED))
        self.assertFalse(self.sm.can_advance(self.task, TaskState.RUNNING))
        self.assertFalse(self.sm.can_advance(self.task, TaskState.DONE))

    def test_get_valid_targets(self) -> None:
        self.assertEqual(self.sm.get_valid_targets(self.task), [TaskState.QUEUED])
        self._advance_through(TaskState.QUEUED, TaskState.RUNNING)
        targets = self.sm.get_valid_targets(self.task)
        self.assertIn(TaskState.REVIEW, targets)
        self.assertIn(TaskState.BLOCKED, targets)
        self.assertEqual(len(targets), 2)

    def test_transition_history_recorded(self) -> None:
        self._advance_through(TaskState.QUEUED, TaskState.RUNNING)
        history = self.sm.get_transition_history(self.task)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].from_state, TaskState.DRAFT)
        self.assertEqual(history[0].to_state, TaskState.QUEUED)
        self.assertEqual(history[1].from_state, TaskState.QUEUED)
        self.assertEqual(history[1].to_state, TaskState.RUNNING)
        self.assertIsInstance(history[0].timestamp, datetime)

    def test_advance_records_actor(self) -> None:
        self.sm.advance(self.task, TaskState.QUEUED, actor="ci-bot")
        self.assertEqual(self.task.transitions[0].actor, "ci-bot")

    def test_advance_records_reason(self) -> None:
        self.sm.advance(self.task, TaskState.QUEUED, reason="Ready")
        self.assertEqual(self.task.transitions[0].reason, "Ready")

    def test_advance_updates_timestamp(self) -> None:
        before = datetime.now(timezone.utc)
        self.sm.advance(self.task, TaskState.QUEUED)
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(self.task.updated_at, before)
        self.assertLessEqual(self.task.updated_at, after)

    def test_history_is_independent_copy(self) -> None:
        self.sm.advance(self.task, TaskState.QUEUED)
        history = self.sm.get_transition_history(self.task)
        history.clear()
        self.assertEqual(len(self.sm.get_transition_history(self.task)), 1)


if __name__ == "__main__":
    unittest.main()
