from __future__ import annotations

import unittest

from engine.models import Task, TaskState
from engine.review_gate import (
    ReviewCriteria,
    ReviewDecision,
    ReviewGate,
    ReviewMode,
)
from engine.state_machine import StateMachine


class TestReviewGate(unittest.TestCase):
    def setUp(self):
        self.sm = StateMachine()
        self.gate = ReviewGate(self.sm)

    def _make_review_task(self, task_id: str = "t1", name: str = "Test Task") -> Task:
        task = Task(id=task_id, name=name)
        self.sm.advance(task, TaskState.QUEUED)
        self.sm.advance(task, TaskState.RUNNING)
        self.sm.advance(task, TaskState.REVIEW)
        return task

    def test_submit_auto_review_all_pass(self):
        criteria = ReviewCriteria(
            task_type="code",
            mode=ReviewMode.AUTO,
            auto_rules=[lambda t: True, lambda t: True],
            reviewer_role="role-code-reviewer",
        )
        self.gate._criteria_map["code"] = criteria

        task = self._make_review_task()
        request = self.gate.submit_for_review(task, "code")

        self.assertEqual(request.decision, ReviewDecision.APPROVED)
        self.assertEqual(task.state, TaskState.APPROVED)

    def test_submit_auto_review_fail_fallback_manual(self):
        criteria = ReviewCriteria(
            task_type="code",
            mode=ReviewMode.AUTO,
            auto_rules=[lambda t: True, lambda t: False],
            reviewer_role="role-code-reviewer",
        )
        self.gate._criteria_map["code"] = criteria

        task = self._make_review_task()
        request = self.gate.submit_for_review(task, "code")

        self.assertEqual(request.decision, ReviewDecision.PENDING)
        self.assertEqual(task.state, TaskState.REVIEW)
        self.assertIn(task.id, [r.task.id for r in self.gate.get_pending_reviews()])

    def test_submit_manual_review_creates_pending(self):
        criteria = ReviewCriteria(
            task_type="design",
            mode=ReviewMode.MANUAL,
            reviewer_role="role-tech-director",
        )
        self.gate._criteria_map["design"] = criteria

        task = self._make_review_task()
        request = self.gate.submit_for_review(task, "design")

        self.assertEqual(request.decision, ReviewDecision.PENDING)
        self.assertEqual(task.state, TaskState.REVIEW)
        self.assertIsNotNone(self.gate.get_review_status(task.id))

    def test_approve_advances_to_approved(self):
        criteria = ReviewCriteria(
            task_type="code",
            mode=ReviewMode.MANUAL,
            reviewer_role="role-code-reviewer",
        )
        self.gate._criteria_map["code"] = criteria

        task = self._make_review_task()
        self.gate.submit_for_review(task, "code")
        result = self.gate.approve(task.id, reviewer="alice", reason="LGTM")

        self.assertEqual(result.state, TaskState.APPROVED)
        self.assertIsNone(self.gate.get_review_status(task.id))

    def test_reject_advances_to_rejected(self):
        criteria = ReviewCriteria(
            task_type="code",
            mode=ReviewMode.MANUAL,
            reviewer_role="role-code-reviewer",
        )
        self.gate._criteria_map["code"] = criteria

        task = self._make_review_task()
        self.gate.submit_for_review(task, "code")
        result = self.gate.reject(task.id, reviewer="bob", reason="needs rework")

        self.assertEqual(result.state, TaskState.REJECTED)
        self.assertEqual(result.metadata["reject_reason"], "needs rework")

    def test_reject_increments_count(self):
        criteria = ReviewCriteria(
            task_type="code",
            mode=ReviewMode.MANUAL,
            reviewer_role="role-code-reviewer",
        )
        self.gate._criteria_map["code"] = criteria

        task = self._make_review_task()
        self.gate.submit_for_review(task, "code")
        self.gate.reject(task.id, reviewer="bob", reason="issue 1")
        self.assertEqual(task.metadata["reject_count"], 1)

        self.sm.advance(task, TaskState.RUNNING)
        self.sm.advance(task, TaskState.REVIEW)
        self.gate.submit_for_review(task, "code")
        self.gate.reject(task.id, reviewer="bob", reason="issue 2")
        self.assertEqual(task.metadata["reject_count"], 2)

    def test_reject_reason_required(self):
        criteria = ReviewCriteria(
            task_type="code",
            mode=ReviewMode.MANUAL,
            reviewer_role="role-code-reviewer",
        )
        self.gate._criteria_map["code"] = criteria

        task = self._make_review_task()
        self.gate.submit_for_review(task, "code")
        with self.assertRaises(ValueError):
            self.gate.reject(task.id, reviewer="bob", reason="")

    def test_submit_wrong_state_raises(self):
        task = Task(id="t1", name="Draft Task")
        with self.assertRaises(ValueError):
            self.gate.submit_for_review(task, "code")

    def test_get_pending_reviews(self):
        task1 = self._make_review_task("t1", "Task 1")
        task2 = self._make_review_task("t2", "Task 2")
        self.gate.submit_for_review(task1, "unknown")
        self.gate.submit_for_review(task2, "unknown")

        pending = self.gate.get_pending_reviews()
        self.assertEqual(len(pending), 2)
        self.assertEqual({r.task.id for r in pending}, {"t1", "t2"})

    def test_hybrid_mode_auto_pass(self):
        criteria = ReviewCriteria(
            task_type="ops",
            mode=ReviewMode.HYBRID,
            auto_rules=[lambda t: True],
            reviewer_role="role-tech-director",
        )
        self.gate._criteria_map["ops"] = criteria

        task = self._make_review_task()
        request = self.gate.submit_for_review(task, "ops")

        self.assertEqual(request.decision, ReviewDecision.APPROVED)
        self.assertEqual(task.state, TaskState.APPROVED)

    def test_hybrid_mode_auto_fail_to_manual(self):
        criteria = ReviewCriteria(
            task_type="ops",
            mode=ReviewMode.HYBRID,
            auto_rules=[lambda t: False],
            reviewer_role="role-tech-director",
        )
        self.gate._criteria_map["ops"] = criteria

        task = self._make_review_task()
        request = self.gate.submit_for_review(task, "ops")

        self.assertEqual(request.decision, ReviewDecision.PENDING)
        self.assertEqual(task.state, TaskState.REVIEW)
        self.assertIn(task.id, [r.task.id for r in self.gate.get_pending_reviews()])

    def test_load_rules_from_config(self):
        config = {
            "rules": [
                {
                    "task_type": "code",
                    "mode": "manual",
                    "reviewer_role": "role-code-reviewer",
                    "timeout_hours": 24,
                },
                {
                    "task_type": "ops",
                    "mode": "hybrid",
                    "reviewer_role": "role-tech-director",
                    "timeout_hours": 12,
                },
            ]
        }
        self.gate.load_rules(config)

        self.assertIn("code", self.gate._criteria_map)
        self.assertIn("ops", self.gate._criteria_map)
        self.assertEqual(self.gate._criteria_map["code"].mode, ReviewMode.MANUAL)
        self.assertEqual(self.gate._criteria_map["ops"].mode, ReviewMode.HYBRID)
        self.assertEqual(self.gate._criteria_map["code"].timeout_hours, 24)
        self.assertEqual(self.gate._criteria_map["ops"].timeout_hours, 12)


if __name__ == "__main__":
    unittest.main()
