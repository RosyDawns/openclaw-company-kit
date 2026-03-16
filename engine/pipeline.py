from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class NodeType(Enum):
    TASK = "task"
    REVIEW_GATE = "review_gate"
    FORK = "fork"
    JOIN = "join"


@dataclass
class PipelineNode:
    id: str
    node_type: NodeType
    role: str = ""
    task_type: str = ""
    config: dict = field(default_factory=dict)
    timeout_seconds: int = 3600


@dataclass
class PipelineEdge:
    from_node: str
    to_node: str
    condition: str = "always"


class Pipeline:
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.nodes: dict[str, PipelineNode] = {}
        self.edges: list[PipelineEdge] = []
        self._entry_node: str | None = None

    def add_node(self, node: PipelineNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: PipelineEdge) -> None:
        self.edges.append(edge)

    def get_entry_node(self) -> PipelineNode:
        if self._entry_node and self._entry_node in self.nodes:
            return self.nodes[self._entry_node]

        nodes_with_incoming = {e.to_node for e in self.edges}
        candidates = [nid for nid in self.nodes if nid not in nodes_with_incoming]

        if not candidates:
            raise ValueError("Pipeline has no entry node")
        if len(candidates) > 1:
            raise ValueError(f"Pipeline has multiple entry nodes: {candidates}")

        self._entry_node = candidates[0]
        return self.nodes[self._entry_node]

    def get_next_nodes(
        self, node_id: str, condition: str = "always"
    ) -> list[PipelineNode]:
        return [
            self.nodes[e.to_node]
            for e in self.edges
            if e.from_node == node_id
            and e.condition == condition
            and e.to_node in self.nodes
        ]

    def get_fork_branches(self, fork_node_id: str) -> list[list[PipelineNode]]:
        node = self.nodes.get(fork_node_id)
        if node is None or node.node_type != NodeType.FORK:
            raise ValueError(f"Node {fork_node_id} is not a FORK node")

        branches: list[list[PipelineNode]] = []
        for start in self.get_next_nodes(fork_node_id):
            path = [start]
            current = start
            while current.node_type != NodeType.JOIN:
                successors = self.get_next_nodes(current.id)
                if not successors:
                    break
                current = successors[0]
                if current.node_type == NodeType.JOIN:
                    break
                path.append(current)
            branches.append(path)
        return branches

    def validate(self) -> list[str]:
        errors: list[str] = []

        if not self.nodes:
            errors.append("Pipeline has no nodes")
            return errors

        for edge in self.edges:
            if edge.from_node not in self.nodes:
                errors.append(
                    f"Edge references unknown source node: {edge.from_node}"
                )
            if edge.to_node not in self.nodes:
                errors.append(
                    f"Edge references unknown target node: {edge.to_node}"
                )

        nodes_with_incoming = {e.to_node for e in self.edges}
        entry_candidates = [
            nid for nid in self.nodes if nid not in nodes_with_incoming
        ]
        if not entry_candidates:
            errors.append("Pipeline has no entry node (possible cycle)")

        if len(self.nodes) > 1:
            connected: set[str] = set()
            for edge in self.edges:
                connected.add(edge.from_node)
                connected.add(edge.to_node)
            for nid in self.nodes:
                if nid not in connected:
                    errors.append(f"Orphan node detected: {nid}")

        forks = sum(1 for n in self.nodes.values() if n.node_type == NodeType.FORK)
        joins = sum(1 for n in self.nodes.values() if n.node_type == NodeType.JOIN)
        if forks != joins:
            errors.append(
                f"FORK/JOIN mismatch: {forks} FORK(s), {joins} JOIN(s)"
            )

        for node in self.nodes.values():
            if node.node_type == NodeType.TASK and not node.role:
                errors.append(f"TASK node '{node.id}' missing required role")

        return errors

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "nodes": [
                {
                    "id": n.id,
                    "node_type": n.node_type.value,
                    "role": n.role,
                    "task_type": n.task_type,
                    "config": n.config,
                    "timeout_seconds": n.timeout_seconds,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "from_node": e.from_node,
                    "to_node": e.to_node,
                    "condition": e.condition,
                }
                for e in self.edges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Pipeline:
        p = cls(name=data["name"], description=data.get("description", ""))
        for nd in data.get("nodes", []):
            p.add_node(
                PipelineNode(
                    id=nd["id"],
                    node_type=NodeType(nd["node_type"]),
                    role=nd.get("role", ""),
                    task_type=nd.get("task_type", ""),
                    config=nd.get("config", {}),
                    timeout_seconds=nd.get("timeout_seconds", 3600),
                )
            )
        for ed in data.get("edges", []):
            p.add_edge(
                PipelineEdge(
                    from_node=ed["from_node"],
                    to_node=ed["to_node"],
                    condition=ed.get("condition", "always"),
                )
            )
        return p

    @classmethod
    def from_json(cls, path: str) -> Pipeline:
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
