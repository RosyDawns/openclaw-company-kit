from __future__ import annotations

import json
import logging
import os

from engine.dispatch import Dispatcher
from engine.orchestrator import Orchestrator
from engine.pipeline import NodeType, Pipeline, PipelineNode


class CronAdapter:
    """Adapts existing cron job configs to the orchestration engine."""

    _AGENT_TASK_TYPE: dict[str, str] = {
        "role-senior-dev": "code",
        "role-qa-test": "test",
        "role-product": "product",
        "role-tech-director": "design",
        "role-code-reviewer": "code",
        "role-growth": "growth",
        "rd-company": "ops",
        "ai-tech": "ops",
        "hot-search": "growth",
    }

    def __init__(self, orchestrator: Orchestrator, dispatcher: Dispatcher):
        self._orchestrator = orchestrator
        self._dispatcher = dispatcher
        self._task_map: dict[str, object] = {}
        self._enabled = os.environ.get("ORCHESTRATOR_ENABLED", "0") == "1"
        self._logger = logging.getLogger("cron_adapter")

    @property
    def enabled(self) -> bool:
        return self._enabled

    def adapt_job(self, job_config: dict) -> Pipeline | None:
        """Convert a single cron job config into a Pipeline.

        If the config contains a ``pipeline`` key (new template format), that
        definition is normalised and forwarded to ``Pipeline.from_dict``.
        Otherwise, a single-node TASK pipeline is synthesised from the
        ``agent`` field.
        """
        if not self._enabled:
            return None

        name = job_config.get("name", "unknown")
        agent = job_config.get("agent", "")

        if "pipeline" in job_config:
            return self._pipeline_from_template(name, job_config["pipeline"])

        pipeline = Pipeline(name=name)
        task_type = self._infer_task_type(agent)
        node = PipelineNode(
            id=f"job_{name}",
            node_type=NodeType.TASK,
            role=agent,
            task_type=task_type,
            timeout_seconds=job_config.get("timeout", 3600),
        )
        pipeline.add_node(node)
        return pipeline

    def adapt_all_jobs(self, jobs_config_path: str) -> list[Pipeline]:
        """Load and adapt every job from a jobs.template.json file."""
        if not self._enabled:
            return []

        try:
            with open(jobs_config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self._logger.error("Failed to load jobs config: %s", e)
            return []

        pipelines: list[Pipeline] = []
        for job in config.get("jobs", []):
            pipeline = self.adapt_job(job)
            if pipeline:
                pipelines.append(pipeline)
        return pipelines

    def on_cron_trigger(self, job_name: str, job_config: dict) -> dict:
        """Callback when a cron job fires.

        Returns ``{"managed": True, ...}`` when the orchestrator handles
        the job, or ``{"managed": False}`` to fall back to legacy direct
        execution.
        """
        if not self._enabled:
            return {"managed": False}

        pipeline = self.adapt_job(job_config)
        if not pipeline:
            return {"managed": False}

        try:
            trace = self._orchestrator.execute_pipeline(pipeline)
            return {
                "managed": True,
                "task_id": trace.pipeline_name,
                "state": trace.status.value,
                "trace": {
                    "started_at": trace.started_at,
                    "nodes_executed": len(trace.node_executions),
                },
            }
        except Exception as e:
            self._logger.error("Orchestrator failed for %s: %s", job_name, e)
            return {"managed": False, "error": str(e)}

    def get_status(self) -> dict:
        return {
            "enabled": self._enabled,
            "managed_tasks": len(self._task_map),
            "orchestrator_executions": len(
                self._orchestrator.get_all_executions()
            ),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _infer_task_type(self, agent: str) -> str:
        return self._AGENT_TASK_TYPE.get(agent, "ops")

    @staticmethod
    def _pipeline_from_template(name: str, raw: dict) -> Pipeline:
        """Normalise the template-format pipeline dict into the canonical
        ``Pipeline.from_dict`` schema (``node_type`` / ``task_type`` /
        ``from_node`` / ``to_node``)."""
        nodes = []
        for n in raw.get("nodes", []):
            nodes.append(
                {
                    "id": n["id"],
                    "node_type": n.get("node_type", n.get("type", "task")),
                    "role": n.get("role", ""),
                    "task_type": n.get("task_type", n.get("taskType", "")),
                    "config": n.get("config", {}),
                    "timeout_seconds": n.get("timeout_seconds", 3600),
                }
            )

        edges = []
        for e in raw.get("edges", []):
            to_node = e.get("to_node", e.get("to"))
            if to_node is None:
                continue
            edges.append(
                {
                    "from_node": e.get("from_node", e.get("from", "")),
                    "to_node": to_node,
                    "condition": e.get("condition", "always"),
                }
            )

        return Pipeline.from_dict(
            {"name": name, "nodes": nodes, "edges": edges}
        )
