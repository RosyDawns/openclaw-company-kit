from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from engine.models import Task, TaskState
from engine.pipeline import NodeType, Pipeline, PipelineNode
from engine.review_gate import ReviewDecision, ReviewGate
from engine.state_machine import StateMachine


class ExecutionState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class NodeExecution:
    node: PipelineNode
    state: ExecutionState = ExecutionState.PENDING
    task: Task | None = None
    started_at: float | None = None
    completed_at: float | None = None
    result: dict | None = None
    error: str | None = None


@dataclass
class ExecutionTrace:
    pipeline_name: str
    started_at: float
    completed_at: float | None = None
    node_executions: list[NodeExecution] = field(default_factory=list)
    status: ExecutionState = ExecutionState.PENDING


class Orchestrator:
    def __init__(self, state_machine: StateMachine, review_gate: ReviewGate):
        self._state_machine = state_machine
        self._review_gate = review_gate
        self._executions: dict[str, ExecutionTrace] = {}
        self._pipelines: dict[str, Pipeline] = {}
        self._node_exec_map: dict[str, dict[str, NodeExecution]] = {}

    def execute_pipeline(
        self, pipeline: Pipeline, context: dict | None = None
    ) -> ExecutionTrace:
        ctx = dict(context) if context else {}
        trace = ExecutionTrace(
            pipeline_name=pipeline.name,
            started_at=time.time(),
            status=ExecutionState.RUNNING,
        )
        self._executions[pipeline.name] = trace
        self._pipelines[pipeline.name] = pipeline
        self._node_exec_map[pipeline.name] = {}

        entry = pipeline.get_entry_node()
        self._walk(pipeline, entry, trace, ctx)
        return trace

    def _walk(
        self,
        pipeline: Pipeline,
        start: PipelineNode,
        trace: ExecutionTrace,
        ctx: dict,
    ) -> None:
        queue: list[PipelineNode] = [start]
        visited: set[str] = set()

        while queue:
            node = queue.pop(0)
            if node.id in visited:
                continue

            # JOIN nodes must wait for all predecessors to complete
            if node.node_type == NodeType.JOIN:
                preds = [
                    e.from_node for e in pipeline.edges if e.to_node == node.id
                ]
                nmap = self._node_exec_map[pipeline.name]
                if not all(
                    p in nmap and nmap[p].state == ExecutionState.COMPLETED
                    for p in preds
                ):
                    queue.append(node)
                    continue

            visited.add(node.id)

            ne = self.execute_node(node, ctx.get("_current_task"), ctx)
            trace.node_executions.append(ne)
            self._node_exec_map[pipeline.name][node.id] = ne

            if ne.task:
                ctx["_current_task"] = ne.task

            if ne.state == ExecutionState.WAITING_REVIEW:
                trace.status = ExecutionState.WAITING_REVIEW
                return

            if ne.state == ExecutionState.FAILED:
                trace.status = ExecutionState.FAILED
                trace.completed_at = time.time()
                return

            # Determine successor nodes based on node type / outcome
            if (
                node.node_type == NodeType.REVIEW_GATE
                and ne.state == ExecutionState.COMPLETED
            ):
                nxt = pipeline.get_next_nodes(node.id, "on_approved")
                if not nxt:
                    nxt = pipeline.get_next_nodes(node.id)
            else:
                nxt = pipeline.get_next_nodes(node.id)
            queue.extend(nxt)

        # Finalise status after all reachable nodes are processed
        if trace.node_executions and all(
            n.state == ExecutionState.COMPLETED for n in trace.node_executions
        ):
            trace.status = ExecutionState.COMPLETED
            trace.completed_at = time.time()

    def execute_node(
        self, node: PipelineNode, task: Task | None, context: dict
    ) -> NodeExecution:
        ne = NodeExecution(node=node, started_at=time.time())
        ne.state = ExecutionState.RUNNING

        try:
            if node.node_type == NodeType.TASK:
                t = Task(
                    id=f"task-{node.id}-{uuid.uuid4().hex[:8]}",
                    name=f"Task for {node.id}",
                    metadata={
                        "node_id": node.id,
                        "task_type": node.task_type,
                    },
                )
                self._state_machine.advance(t, TaskState.QUEUED)
                self._state_machine.advance(t, TaskState.RUNNING)
                ne.task = t
                ne.state = ExecutionState.COMPLETED
                ne.completed_at = time.time()
                ne.result = {"task_id": t.id, "task_state": t.state.value}

            elif node.node_type == NodeType.REVIEW_GATE:
                if task is None:
                    raise ValueError("REVIEW_GATE requires a preceding task")
                self._state_machine.advance(task, TaskState.REVIEW)
                task_type = node.config.get(
                    "task_type", node.task_type or "default"
                )
                reviewer = self._review_gate.auto_route(task_type)
                req = self._review_gate.submit_for_review_with_routing(
                    task, task_type
                )
                ne.task = task

                if req.decision == ReviewDecision.APPROVED:
                    self._state_machine.advance(
                        task, TaskState.DONE, reason="Auto-approved"
                    )
                    ne.state = ExecutionState.COMPLETED
                    ne.completed_at = time.time()
                    ne.result = {
                        "decision": "approved",
                        "auto": True,
                        "reviewer_role": reviewer,
                        "request_id": req.task.id,
                    }
                else:
                    ne.state = ExecutionState.WAITING_REVIEW
                    ne.result = {
                        "decision": "pending",
                        "reviewer_role": reviewer,
                        "request_id": req.task.id,
                    }

            elif node.node_type in (NodeType.FORK, NodeType.JOIN):
                ne.state = ExecutionState.COMPLETED
                ne.completed_at = time.time()
                ne.result = {"type": node.node_type.value}

        except Exception as exc:
            ne.state = ExecutionState.FAILED
            ne.error = str(exc)
            ne.completed_at = time.time()

        return ne

    def advance_after_review(
        self,
        pipeline_name: str,
        node_id: str,
        approved: bool,
        reason: str = "",
    ) -> ExecutionTrace:
        trace = self._executions.get(pipeline_name)
        if trace is None:
            raise ValueError(
                f"No execution found for pipeline: {pipeline_name}"
            )

        pipeline = self._pipelines[pipeline_name]
        ne = self._node_exec_map[pipeline_name].get(node_id)
        if ne is None:
            raise ValueError(f"No execution record for node: {node_id}")
        if ne.state != ExecutionState.WAITING_REVIEW:
            raise ValueError(f"Node {node_id} is not waiting for review")

        task = ne.task
        if task is None:
            raise ValueError(f"Node {node_id} has no associated task")

        if approved:
            self._review_gate.approve(
                task.id, reviewer="orchestrator", reason=reason
            )
            self._state_machine.advance(task, TaskState.DONE, reason=reason)
            ne.state = ExecutionState.COMPLETED
            ne.completed_at = time.time()
            ne.result = {"decision": "approved", "reason": reason}
            condition = "on_approved"
        else:
            self._review_gate.reject(
                task.id,
                reviewer="orchestrator",
                reason=reason or "Rejected",
            )
            ne.state = ExecutionState.COMPLETED
            ne.completed_at = time.time()
            ne.result = {"decision": "rejected", "reason": reason}
            condition = "on_rejected"

        nxt = pipeline.get_next_nodes(node_id, condition)
        if not nxt:
            nxt = pipeline.get_next_nodes(node_id)

        ctx: dict = {"_current_task": task}
        trace.status = ExecutionState.RUNNING

        if nxt:
            for n in nxt:
                self._walk(pipeline, n, trace, ctx)
        else:
            trace.status = ExecutionState.COMPLETED
            trace.completed_at = time.time()

        return trace

    def get_execution_status(self, pipeline_name: str) -> ExecutionTrace | None:
        return self._executions.get(pipeline_name)

    def cancel_execution(self, pipeline_name: str) -> bool:
        trace = self._executions.get(pipeline_name)
        if trace is None or trace.status in (
            ExecutionState.COMPLETED,
            ExecutionState.CANCELLED,
        ):
            return False

        trace.status = ExecutionState.CANCELLED
        trace.completed_at = time.time()
        for ne in trace.node_executions:
            if ne.state in (
                ExecutionState.RUNNING,
                ExecutionState.PENDING,
                ExecutionState.WAITING_REVIEW,
            ):
                ne.state = ExecutionState.CANCELLED
                ne.completed_at = ne.completed_at or time.time()
        return True

    def get_all_executions(self) -> list[ExecutionTrace]:
        return list(self._executions.values())
