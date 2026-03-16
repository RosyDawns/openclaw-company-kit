"""End-to-end integration tests for the engine package.

Covers: Pipeline execution, review gate approve/reject flow,
concurrent FileLock, RoleRegistry completeness, StateMachine
boundary transitions, and Pipeline serialization round-trip.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest

from engine.file_lock import FileLock
from engine.models import Task, TaskState
from engine.orchestrator import ExecutionState, Orchestrator
from engine.pipeline import NodeType, Pipeline, PipelineEdge, PipelineNode
from engine.review_gate import ReviewGate
from engine.roles import RoleLayer, RoleRegistry
from engine.state_machine import InvalidTransitionError, StateMachine


def _build_happy_pipeline() -> Pipeline:
    """TaskNode(A) → ReviewGateNode → TaskNode(B)"""
    p = Pipeline(name="happy-path", description="integration test")
    p.add_node(PipelineNode(id="A", node_type=NodeType.TASK, role="role-senior-dev", task_type="code"))
    p.add_node(PipelineNode(id="gate", node_type=NodeType.REVIEW_GATE, task_type="code"))
    p.add_node(PipelineNode(id="B", node_type=NodeType.TASK, role="role-qa-test", task_type="test"))
    p.add_edge(PipelineEdge(from_node="A", to_node="gate"))
    p.add_edge(PipelineEdge(from_node="gate", to_node="B", condition="on_approved"))
    return p


def _build_review_pipeline() -> Pipeline:
    """TaskNode → ReviewGateNode (terminal after approve)."""
    p = Pipeline(name="review-pipeline", description="rejection test")
    p.add_node(PipelineNode(id="task", node_type=NodeType.TASK, role="role-senior-dev", task_type="code"))
    p.add_node(PipelineNode(id="gate", node_type=NodeType.REVIEW_GATE, task_type="code"))
    p.add_edge(PipelineEdge(from_node="task", to_node="gate"))
    return p


class TestFullPipelineHappyPath(unittest.TestCase):
    """Scenario 1: A → ReviewGate(approve) → B → Done."""

    def test_full_pipeline_happy_path(self) -> None:
        sm = StateMachine()
        rg = ReviewGate(sm)
        orch = Orchestrator(sm, rg)

        pipeline = _build_happy_pipeline()
        trace = orch.execute_pipeline(pipeline)

        self.assertEqual(trace.status, ExecutionState.WAITING_REVIEW)
        self.assertEqual(len(trace.node_executions), 2)

        ne_a = trace.node_executions[0]
        self.assertEqual(ne_a.node.id, "A")
        self.assertEqual(ne_a.state, ExecutionState.COMPLETED)
        self.assertIsNotNone(ne_a.task)
        self.assertEqual(ne_a.result["task_state"], "running")

        ne_gate = trace.node_executions[1]
        self.assertEqual(ne_gate.node.id, "gate")
        self.assertEqual(ne_gate.state, ExecutionState.WAITING_REVIEW)

        trace = orch.advance_after_review("happy-path", "gate", approved=True, reason="LGTM")

        self.assertGreaterEqual(len(trace.node_executions), 3)
        ne_b = trace.node_executions[2]
        self.assertEqual(ne_b.node.id, "B")
        self.assertEqual(ne_b.state, ExecutionState.COMPLETED)

        self.assertEqual(trace.status, ExecutionState.COMPLETED)
        self.assertIsNotNone(trace.completed_at)

        step_ids = [ne.node.id for ne in trace.node_executions]
        self.assertEqual(step_ids, ["A", "gate", "B"])


class TestReviewRejectionAndRetry(unittest.TestCase):
    """Scenario 2: task → gate → reject → re-run → gate → approve."""

    def test_review_rejection_and_retry(self) -> None:
        sm = StateMachine()
        rg = ReviewGate(sm)
        orch = Orchestrator(sm, rg)

        pipeline = _build_review_pipeline()
        trace = orch.execute_pipeline(pipeline)

        self.assertEqual(trace.status, ExecutionState.WAITING_REVIEW)

        gate_ne = trace.node_executions[1]
        task = gate_ne.task
        self.assertIsNotNone(task)

        trace = orch.advance_after_review(
            "review-pipeline", "gate", approved=False, reason="Needs rework",
        )

        self.assertEqual(task.state, TaskState.REJECTED)
        self.assertEqual(task.metadata.get("reject_count"), 1)

        sm.advance(task, TaskState.RUNNING, reason="Re-executing after rejection")
        sm.advance(task, TaskState.REVIEW, reason="Re-submit for review")

        rg.submit_for_review(task, "code")
        rg.approve(task.id, reviewer="lead", reason="Fixed")
        sm.advance(task, TaskState.DONE, reason="Final approval")

        self.assertEqual(task.state, TaskState.DONE)
        self.assertEqual(task.metadata["reject_count"], 1)


class TestFileLockConcurrentAccess(unittest.TestCase):
    """Scenario 3: two threads contending for the same FileLock."""

    def test_file_lock_concurrent_access(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_path = os.path.join(tmpdir, "test.lock")
            intervals: list[tuple[float, float]] = []
            lock = threading.Lock()

            def worker() -> None:
                fl = FileLock(lock_path, timeout=10.0)
                with fl:
                    start = time.monotonic()
                    time.sleep(0.15)
                    end = time.monotonic()
                    with lock:
                        intervals.append((start, end))

            t1 = threading.Thread(target=worker)
            t2 = threading.Thread(target=worker)
            t1.start()
            t2.start()
            t1.join(timeout=30)
            t2.join(timeout=30)

            self.assertEqual(len(intervals), 2)

            intervals.sort()
            a_start, a_end = intervals[0]
            b_start, b_end = intervals[1]
            self.assertGreaterEqual(
                b_start, a_end - 0.01,
                "Lock intervals overlap — mutual exclusion violated",
            )


class TestRoleRegistryCompleteness(unittest.TestCase):
    """Scenario 4: all 9 roles registered with correct layer distribution."""

    def test_role_registry_completeness(self) -> None:
        registry = RoleRegistry()

        all_roles = registry.get_all_roles()
        self.assertEqual(len(all_roles), 9)

        dispatchers = registry.get_layer_roles(RoleLayer.DISPATCHER)
        self.assertEqual(len(dispatchers), 1)

        reviewers = registry.get_layer_roles(RoleLayer.REVIEWER)
        self.assertEqual(len(reviewers), 2)

        executors = registry.get_layer_roles(RoleLayer.EXECUTOR)
        self.assertEqual(len(executors), 4)

        subs = (
            registry.get_layer_roles(RoleLayer.DISPATCHER_SUB)
            + registry.get_layer_roles(RoleLayer.EXECUTOR_SUB)
        )
        self.assertEqual(len(subs), 2)

        errors = registry.validate()
        self.assertEqual(errors, [])


class TestStateMachineBoundary(unittest.TestCase):
    """Scenario 5: every illegal transition raises InvalidTransitionError;
    terminal state DONE allows no further transitions."""

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

    def test_all_invalid_transitions_raise(self) -> None:
        sm = StateMachine()
        for source, valid_targets in self._VALID_TRANSITIONS.items():
            for candidate in TaskState:
                if candidate in valid_targets:
                    continue
                task = Task(id=f"boundary-{source.value}-{candidate.value}", name="b", state=source)
                with self.assertRaises(
                    InvalidTransitionError,
                    msg=f"{source.value} → {candidate.value} should be invalid",
                ):
                    sm.advance(task, candidate)

    def test_done_is_terminal(self) -> None:
        sm = StateMachine()
        task = Task(id="terminal", name="terminal", state=TaskState.DONE)
        for target in TaskState:
            with self.assertRaises(InvalidTransitionError):
                sm.advance(task, target)


class TestPipelineRoundTrip(unittest.TestCase):
    """Scenario 6: to_dict → from_dict preserves pipeline structure."""

    def test_pipeline_round_trip(self) -> None:
        original = _build_happy_pipeline()
        data = original.to_dict()
        restored = Pipeline.from_dict(data)

        self.assertEqual(restored.name, original.name)
        self.assertEqual(restored.description, original.description)
        self.assertEqual(len(restored.nodes), len(original.nodes))
        self.assertEqual(len(restored.edges), len(original.edges))

        for nid, orig_node in original.nodes.items():
            rest_node = restored.nodes.get(nid)
            self.assertIsNotNone(rest_node, f"Missing node {nid}")
            self.assertEqual(rest_node.node_type, orig_node.node_type)
            self.assertEqual(rest_node.role, orig_node.role)
            self.assertEqual(rest_node.task_type, orig_node.task_type)
            self.assertEqual(rest_node.config, orig_node.config)
            self.assertEqual(rest_node.timeout_seconds, orig_node.timeout_seconds)

        for i, orig_edge in enumerate(original.edges):
            rest_edge = restored.edges[i]
            self.assertEqual(rest_edge.from_node, orig_edge.from_node)
            self.assertEqual(rest_edge.to_node, orig_edge.to_node)
            self.assertEqual(rest_edge.condition, orig_edge.condition)

        self.assertEqual(original.to_dict(), restored.to_dict())


if __name__ == "__main__":
    unittest.main()
