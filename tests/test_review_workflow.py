from __future__ import annotations

import unittest

from engine.models import Task, TaskState
from engine.orchestrator import ExecutionState, Orchestrator
from engine.pipeline import NodeType, Pipeline, PipelineEdge, PipelineNode
from engine.review_gate import (
    ReviewCriteria,
    ReviewDecision,
    ReviewGate,
    ReviewMode,
)
from engine.state_machine import StateMachine


class TestReviewWorkflow(unittest.TestCase):
    def setUp(self):
        self.sm = StateMachine()
        self.gate = ReviewGate(self.sm)

    def _make_review_task(self, task_id: str = "t1") -> Task:
        task = Task(id=task_id, name=f"Task {task_id}")
        self.sm.advance(task, TaskState.QUEUED)
        self.sm.advance(task, TaskState.RUNNING)
        self.sm.advance(task, TaskState.REVIEW)
        return task

    # ------------------------------------------------------------------
    # 1. code type routes to role-code-reviewer
    # ------------------------------------------------------------------
    def test_auto_route_code_to_code_reviewer(self):
        self.assertEqual(
            self.gate.auto_route("code"), "role-code-reviewer"
        )
        self.assertEqual(
            self.gate.auto_route("security"), "role-code-reviewer"
        )

    # ------------------------------------------------------------------
    # 2. design type routes to role-tech-director
    # ------------------------------------------------------------------
    def test_auto_route_design_to_tech_director(self):
        self.assertEqual(
            self.gate.auto_route("design"), "role-tech-director"
        )
        self.assertEqual(
            self.gate.auto_route("architecture"), "role-tech-director"
        )

    # ------------------------------------------------------------------
    # 3. ops type requires dual review
    # ------------------------------------------------------------------
    def test_auto_route_ops_dual_review(self):
        self.assertTrue(self.gate.requires_dual_review("ops"))
        self.assertFalse(self.gate.requires_dual_review("code"))
        self.assertFalse(self.gate.requires_dual_review("design"))

    # ------------------------------------------------------------------
    # 4. submit_for_review_with_routing sets reviewer
    # ------------------------------------------------------------------
    def test_submit_with_routing(self):
        task = self._make_review_task()
        req = self.gate.submit_for_review_with_routing(task, "code")

        self.assertEqual(req.reviewer, "role-code-reviewer")
        self.assertEqual(req.decision, ReviewDecision.PENDING)

    # ------------------------------------------------------------------
    # 5. reject → RUNNING → resubmit
    # ------------------------------------------------------------------
    def test_reject_and_resubmit(self):
        task = self._make_review_task()
        self.gate.submit_for_review_with_routing(task, "code")

        self.gate.reject(task.id, reviewer="role-code-reviewer", reason="needs fix")
        self.assertEqual(task.state, TaskState.REJECTED)

        self.sm.advance(task, TaskState.RUNNING)
        self.assertEqual(task.state, TaskState.RUNNING)

        self.sm.advance(task, TaskState.REVIEW)
        req2 = self.gate.submit_for_review_with_routing(task, "code")
        self.assertEqual(req2.reviewer, "role-code-reviewer")
        self.assertEqual(req2.decision, ReviewDecision.PENDING)

    # ------------------------------------------------------------------
    # 6. dual review – both approve → overall pass
    # ------------------------------------------------------------------
    def test_dual_review_both_approve(self):
        task = self._make_review_task()
        requests = self.gate.create_dual_review(task, "ops")

        self.assertEqual(len(requests), 2)
        reviewers = {r.reviewer for r in requests}
        self.assertEqual(reviewers, {"role-code-reviewer", "role-tech-director"})

        all_approved = all(
            r.decision == ReviewDecision.PENDING for r in requests
        )
        self.assertTrue(all_approved)

        for req in requests:
            req.decision = ReviewDecision.APPROVED

        self.assertTrue(
            all(r.decision == ReviewDecision.APPROVED for r in requests)
        )

    # ------------------------------------------------------------------
    # 7. dual review – one rejects → overall rejected
    # ------------------------------------------------------------------
    def test_dual_review_one_reject(self):
        task = self._make_review_task()
        requests = self.gate.create_dual_review(task, "ops")

        requests[0].decision = ReviewDecision.APPROVED
        requests[1].decision = ReviewDecision.REJECTED

        overall = all(r.decision == ReviewDecision.APPROVED for r in requests)
        self.assertFalse(overall)

    # ------------------------------------------------------------------
    # 8. bind_reviewer for custom type
    # ------------------------------------------------------------------
    def test_bind_custom_reviewer(self):
        self.gate.bind_reviewer("ml-model", "role-ml-reviewer")
        self.assertEqual(self.gate.auto_route("ml-model"), "role-ml-reviewer")

        task = self._make_review_task()
        req = self.gate.submit_for_review_with_routing(task, "ml-model")
        self.assertEqual(req.reviewer, "role-ml-reviewer")

    # ------------------------------------------------------------------
    # 9. orchestrator routes review node correctly
    # ------------------------------------------------------------------
    def test_orchestrator_review_node_routes_correctly(self):
        gate = ReviewGate(
            self.sm,
            {"rules": [{"task_type": "code", "mode": "manual"}]},
        )
        orch = Orchestrator(self.sm, gate)

        p = Pipeline("route-test")
        p.add_node(
            PipelineNode("task1", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_node(
            PipelineNode(
                "rg",
                NodeType.REVIEW_GATE,
                task_type="code",
                config={"task_type": "code"},
            )
        )
        p.add_node(
            PipelineNode("done", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_edge(PipelineEdge("task1", "rg"))
        p.add_edge(PipelineEdge("rg", "done", condition="on_approved"))

        trace = orch.execute_pipeline(p)
        self.assertEqual(trace.status, ExecutionState.WAITING_REVIEW)

        rg_ne = trace.node_executions[-1]
        self.assertEqual(rg_ne.result["reviewer_role"], "role-code-reviewer")
        self.assertIn("request_id", rg_ne.result)


if __name__ == "__main__":
    unittest.main()
