import unittest

from engine.models import TaskState
from engine.orchestrator import ExecutionState, Orchestrator
from engine.pipeline import NodeType, Pipeline, PipelineEdge, PipelineNode
from engine.review_gate import ReviewGate
from engine.state_machine import StateMachine


class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self.sm = StateMachine()
        self.rg = ReviewGate(
            self.sm,
            {"rules": [{"task_type": "code", "mode": "manual"}]},
        )
        self.orch = Orchestrator(self.sm, self.rg)

    def _linear_pipeline(self) -> Pipeline:
        p = Pipeline("linear")
        for nid in ("a", "b", "c"):
            p.add_node(
                PipelineNode(nid, NodeType.TASK, role="dev", task_type="code")
            )
        p.add_edge(PipelineEdge("a", "b"))
        p.add_edge(PipelineEdge("b", "c"))
        return p

    # ------------------------------------------------------------------
    # 1. test_simple_linear_pipeline
    # ------------------------------------------------------------------
    def test_simple_linear_pipeline(self):
        trace = self.orch.execute_pipeline(self._linear_pipeline())

        self.assertEqual(trace.status, ExecutionState.COMPLETED)
        self.assertEqual(len(trace.node_executions), 3)
        for ne in trace.node_executions:
            self.assertEqual(ne.state, ExecutionState.COMPLETED)
            self.assertIsNotNone(ne.task)
            self.assertEqual(ne.task.state, TaskState.RUNNING)

    # ------------------------------------------------------------------
    # 2. test_pipeline_with_review_gate
    # ------------------------------------------------------------------
    def test_pipeline_with_review_gate(self):
        p = Pipeline("review-approve")
        p.add_node(
            PipelineNode("a", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_node(PipelineNode("rg", NodeType.REVIEW_GATE, task_type="code"))
        p.add_node(
            PipelineNode("b", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_edge(PipelineEdge("a", "rg"))
        p.add_edge(PipelineEdge("rg", "b", condition="on_approved"))

        trace = self.orch.execute_pipeline(p)
        self.assertEqual(trace.status, ExecutionState.WAITING_REVIEW)

        trace = self.orch.advance_after_review(
            "review-approve", "rg", approved=True, reason="LGTM"
        )
        self.assertEqual(trace.status, ExecutionState.COMPLETED)
        self.assertEqual(len(trace.node_executions), 3)

    # ------------------------------------------------------------------
    # 3. test_pipeline_review_rejection
    # ------------------------------------------------------------------
    def test_pipeline_review_rejection(self):
        p = Pipeline("review-reject")
        p.add_node(
            PipelineNode("a", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_node(PipelineNode("rg", NodeType.REVIEW_GATE, task_type="code"))
        p.add_node(
            PipelineNode("ok", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_node(
            PipelineNode("fix", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_edge(PipelineEdge("a", "rg"))
        p.add_edge(PipelineEdge("rg", "ok", condition="on_approved"))
        p.add_edge(PipelineEdge("rg", "fix", condition="on_rejected"))

        trace = self.orch.execute_pipeline(p)
        self.assertEqual(trace.status, ExecutionState.WAITING_REVIEW)

        trace = self.orch.advance_after_review(
            "review-reject", "rg", approved=False, reason="Needs work"
        )
        self.assertEqual(trace.status, ExecutionState.COMPLETED)

        executed_ids = [ne.node.id for ne in trace.node_executions]
        self.assertIn("fix", executed_ids)
        self.assertNotIn("ok", executed_ids)

    # ------------------------------------------------------------------
    # 4. test_fork_and_join
    # ------------------------------------------------------------------
    def test_fork_and_join(self):
        p = Pipeline("fork-join")
        p.add_node(
            PipelineNode("start", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_node(PipelineNode("fork", NodeType.FORK))
        p.add_node(
            PipelineNode("b1", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_node(
            PipelineNode("b2", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_node(PipelineNode("join", NodeType.JOIN))
        p.add_node(
            PipelineNode("end", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_edge(PipelineEdge("start", "fork"))
        p.add_edge(PipelineEdge("fork", "b1"))
        p.add_edge(PipelineEdge("fork", "b2"))
        p.add_edge(PipelineEdge("b1", "join"))
        p.add_edge(PipelineEdge("b2", "join"))
        p.add_edge(PipelineEdge("join", "end"))

        trace = self.orch.execute_pipeline(p)
        self.assertEqual(trace.status, ExecutionState.COMPLETED)

        executed_ids = [ne.node.id for ne in trace.node_executions]
        self.assertEqual(len(trace.node_executions), 6)
        for expected in ("start", "fork", "b1", "b2", "join", "end"):
            self.assertIn(expected, executed_ids)

    # ------------------------------------------------------------------
    # 5. test_pipeline_validation
    # ------------------------------------------------------------------
    def test_pipeline_validation(self):
        valid = self._linear_pipeline()
        self.assertEqual(valid.validate(), [])

        empty = Pipeline("empty")
        self.assertNotEqual(empty.validate(), [])

        orphan = Pipeline("orphan")
        orphan.add_node(
            PipelineNode("a", NodeType.TASK, role="dev", task_type="code")
        )
        orphan.add_node(
            PipelineNode("b", NodeType.TASK, role="dev", task_type="code")
        )
        orphan.add_node(
            PipelineNode("c", NodeType.TASK, role="dev", task_type="code")
        )
        orphan.add_edge(PipelineEdge("a", "b"))
        errors = orphan.validate()
        self.assertTrue(any("Orphan" in e for e in errors))

        bad_fork = Pipeline("bad-fork")
        bad_fork.add_node(PipelineNode("f", NodeType.FORK))
        bad_fork.add_node(
            PipelineNode("a", NodeType.TASK, role="dev", task_type="code")
        )
        bad_fork.add_edge(PipelineEdge("f", "a"))
        errors = bad_fork.validate()
        self.assertTrue(any("FORK/JOIN" in e for e in errors))

        no_role = Pipeline("no-role")
        no_role.add_node(PipelineNode("x", NodeType.TASK))
        errors = no_role.validate()
        self.assertTrue(any("role" in e.lower() for e in errors))

    # ------------------------------------------------------------------
    # 6. test_execution_trace_recorded
    # ------------------------------------------------------------------
    def test_execution_trace_recorded(self):
        trace = self.orch.execute_pipeline(self._linear_pipeline())

        self.assertEqual(trace.pipeline_name, "linear")
        self.assertIsNotNone(trace.started_at)
        self.assertIsNotNone(trace.completed_at)
        self.assertGreaterEqual(trace.completed_at, trace.started_at)

        for ne in trace.node_executions:
            self.assertIsNotNone(ne.started_at)
            self.assertIsNotNone(ne.completed_at)
            self.assertIsNotNone(ne.result)
            self.assertIsNone(ne.error)

    # ------------------------------------------------------------------
    # 7. test_pipeline_from_dict
    # ------------------------------------------------------------------
    def test_pipeline_from_dict(self):
        data = {
            "name": "dict-pipeline",
            "description": "Built from dict",
            "nodes": [
                {"id": "x", "node_type": "task", "role": "dev", "task_type": "code"},
                {"id": "y", "node_type": "task", "role": "qa", "task_type": "test"},
            ],
            "edges": [{"from_node": "x", "to_node": "y"}],
        }
        p = Pipeline.from_dict(data)
        self.assertEqual(p.name, "dict-pipeline")
        self.assertEqual(len(p.nodes), 2)
        self.assertEqual(len(p.edges), 1)
        self.assertEqual(p.nodes["x"].role, "dev")

        roundtrip = Pipeline.from_dict(p.to_dict())
        self.assertEqual(roundtrip.name, p.name)
        self.assertEqual(len(roundtrip.nodes), len(p.nodes))

        trace = self.orch.execute_pipeline(p)
        self.assertEqual(trace.status, ExecutionState.COMPLETED)

    # ------------------------------------------------------------------
    # 8. test_cancel_execution
    # ------------------------------------------------------------------
    def test_cancel_execution(self):
        p = Pipeline("cancel-test")
        p.add_node(
            PipelineNode("a", NodeType.TASK, role="dev", task_type="code")
        )
        p.add_node(PipelineNode("rg", NodeType.REVIEW_GATE, task_type="code"))
        p.add_edge(PipelineEdge("a", "rg"))

        self.orch.execute_pipeline(p)
        self.assertTrue(self.orch.cancel_execution("cancel-test"))

        trace = self.orch.get_execution_status("cancel-test")
        self.assertEqual(trace.status, ExecutionState.CANCELLED)
        self.assertIsNotNone(trace.completed_at)

        # Cancelling again returns False
        self.assertFalse(self.orch.cancel_execution("cancel-test"))
        # Non-existent pipeline returns False
        self.assertFalse(self.orch.cancel_execution("no-such-pipeline"))

    # ------------------------------------------------------------------
    # 9. test_get_execution_status
    # ------------------------------------------------------------------
    def test_get_execution_status(self):
        self.assertIsNone(self.orch.get_execution_status("nonexistent"))

        self.orch.execute_pipeline(self._linear_pipeline())
        trace = self.orch.get_execution_status("linear")
        self.assertIsNotNone(trace)
        self.assertEqual(trace.pipeline_name, "linear")
        self.assertEqual(trace.status, ExecutionState.COMPLETED)

        all_execs = self.orch.get_all_executions()
        self.assertEqual(len(all_execs), 1)


if __name__ == "__main__":
    unittest.main()
