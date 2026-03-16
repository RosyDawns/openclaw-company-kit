import json
import os
import tempfile
import unittest

from engine.cron_adapter import CronAdapter
from engine.dispatch import Dispatcher
from engine.orchestrator import ExecutionState, Orchestrator
from engine.pipeline import NodeType
from engine.review_gate import ReviewGate
from engine.roles import RoleDefinition, RoleLayer, RoleRegistry
from engine.state_machine import StateMachine


def _make_registry() -> RoleRegistry:
    reg = RoleRegistry(config_path=None)
    for name, layer in (
        ("role-senior-dev", RoleLayer.EXECUTOR),
        ("role-qa-test", RoleLayer.EXECUTOR),
        ("role-product", RoleLayer.DISPATCHER),
        ("role-tech-director", RoleLayer.REVIEWER),
        ("role-code-reviewer", RoleLayer.REVIEWER),
        ("role-growth", RoleLayer.DISPATCHER_SUB),
        ("rd-company", RoleLayer.DISPATCHER),
        ("ai-tech", RoleLayer.EXECUTOR_SUB),
        ("hot-search", RoleLayer.EXECUTOR_SUB),
    ):
        reg.register(
            RoleDefinition(name=name, display_name=name, layer=layer, wip_limit=3)
        )
    return reg


def _make_adapter(enabled: bool = True) -> CronAdapter:
    sm = StateMachine()
    rg = ReviewGate(sm, {"rules": [{"task_type": "code", "mode": "manual"}]})
    orch = Orchestrator(sm, rg)
    reg = _make_registry()
    disp = Dispatcher(reg)
    disp.load_default_rules()

    old = os.environ.get("ORCHESTRATOR_ENABLED")
    os.environ["ORCHESTRATOR_ENABLED"] = "1" if enabled else "0"
    try:
        adapter = CronAdapter(orch, disp)
    finally:
        if old is None:
            os.environ.pop("ORCHESTRATOR_ENABLED", None)
        else:
            os.environ["ORCHESTRATOR_ENABLED"] = old
    return adapter


class TestCronAdapter(unittest.TestCase):
    # ------------------------------------------------------------------
    # 1. disabled by default
    # ------------------------------------------------------------------
    def test_disabled_by_default(self):
        old = os.environ.pop("ORCHESTRATOR_ENABLED", None)
        try:
            sm = StateMachine()
            rg = ReviewGate(sm)
            orch = Orchestrator(sm, rg)
            reg = _make_registry()
            disp = Dispatcher(reg)
            adapter = CronAdapter(orch, disp)
            self.assertFalse(adapter.enabled)
        finally:
            if old is not None:
                os.environ["ORCHESTRATOR_ENABLED"] = old

    # ------------------------------------------------------------------
    # 2. enabled when env set
    # ------------------------------------------------------------------
    def test_enabled_when_env_set(self):
        adapter = _make_adapter(enabled=True)
        self.assertTrue(adapter.enabled)

    # ------------------------------------------------------------------
    # 3. adapt single job
    # ------------------------------------------------------------------
    def test_adapt_single_job(self):
        adapter = _make_adapter()
        job = {
            "name": "研发晨会",
            "agent": "rd-company",
            "cron": "30 9 * * *",
            "timeout": 420,
        }
        pipeline = adapter.adapt_job(job)
        self.assertIsNotNone(pipeline)
        self.assertEqual(pipeline.name, "研发晨会")
        self.assertEqual(len(pipeline.nodes), 1)

        node = list(pipeline.nodes.values())[0]
        self.assertEqual(node.node_type, NodeType.TASK)
        self.assertEqual(node.role, "rd-company")
        self.assertEqual(node.task_type, "ops")
        self.assertEqual(node.timeout_seconds, 420)

    # ------------------------------------------------------------------
    # 4. adapt job with pipeline definition
    # ------------------------------------------------------------------
    def test_adapt_job_with_pipeline(self):
        adapter = _make_adapter()
        job = {
            "name": "code-sprint",
            "agent": "role-product",
            "pipeline": {
                "nodes": [
                    {"id": "n1", "type": "task", "role": "role-product", "taskType": "product"},
                    {"id": "g1", "type": "review_gate", "taskType": "design"},
                    {"id": "n2", "type": "task", "role": "role-senior-dev", "taskType": "code"},
                ],
                "edges": [
                    {"from": "n1", "to": "g1", "condition": "always"},
                    {"from": "g1", "to": "n2", "condition": "on_approved"},
                ],
            },
        }
        pipeline = adapter.adapt_job(job)
        self.assertIsNotNone(pipeline)
        self.assertEqual(pipeline.name, "code-sprint")
        self.assertEqual(len(pipeline.nodes), 3)
        self.assertEqual(len(pipeline.edges), 2)
        self.assertEqual(pipeline.nodes["n1"].role, "role-product")
        self.assertEqual(pipeline.nodes["g1"].node_type, NodeType.REVIEW_GATE)

    # ------------------------------------------------------------------
    # 5. adapt all jobs from file
    # ------------------------------------------------------------------
    def test_adapt_all_jobs(self):
        adapter = _make_adapter()
        config = {
            "jobs": [
                {"name": "job-a", "agent": "role-senior-dev"},
                {"name": "job-b", "agent": "role-qa-test"},
                {"name": "job-c", "agent": "role-growth"},
            ]
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(config, f)
            path = f.name

        try:
            pipelines = adapter.adapt_all_jobs(path)
            self.assertEqual(len(pipelines), 3)
            names = {p.name for p in pipelines}
            self.assertEqual(names, {"job-a", "job-b", "job-c"})
        finally:
            os.unlink(path)

    # ------------------------------------------------------------------
    # 6. on_cron_trigger disabled
    # ------------------------------------------------------------------
    def test_on_cron_trigger_disabled(self):
        adapter = _make_adapter(enabled=False)
        result = adapter.on_cron_trigger("any", {"name": "any", "agent": "rd-company"})
        self.assertFalse(result["managed"])

    # ------------------------------------------------------------------
    # 7. on_cron_trigger enabled
    # ------------------------------------------------------------------
    def test_on_cron_trigger_enabled(self):
        adapter = _make_adapter()
        job = {"name": "test-job", "agent": "role-senior-dev"}
        result = adapter.on_cron_trigger("test-job", job)

        self.assertTrue(result["managed"])
        self.assertEqual(result["task_id"], "test-job")
        self.assertIn(result["state"], [s.value for s in ExecutionState])
        self.assertIn("trace", result)
        self.assertGreater(result["trace"]["nodes_executed"], 0)

    # ------------------------------------------------------------------
    # 8. infer task type
    # ------------------------------------------------------------------
    def test_infer_task_type(self):
        adapter = _make_adapter()
        cases = {
            "role-senior-dev": "code",
            "role-qa-test": "test",
            "role-product": "product",
            "role-tech-director": "design",
            "role-code-reviewer": "code",
            "role-growth": "growth",
            "rd-company": "ops",
            "ai-tech": "ops",
            "hot-search": "growth",
            "unknown-agent": "ops",
        }
        for agent, expected in cases.items():
            self.assertEqual(
                adapter._infer_task_type(agent),
                expected,
                f"agent={agent}",
            )

    # ------------------------------------------------------------------
    # 9. invalid config handled
    # ------------------------------------------------------------------
    def test_invalid_config_handled(self):
        adapter = _make_adapter()
        pipelines = adapter.adapt_all_jobs("/nonexistent/path.json")
        self.assertEqual(pipelines, [])

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write("{bad json")
            bad_path = f.name
        try:
            pipelines = adapter.adapt_all_jobs(bad_path)
            self.assertEqual(pipelines, [])
        finally:
            os.unlink(bad_path)

    # ------------------------------------------------------------------
    # 10. get_status
    # ------------------------------------------------------------------
    def test_get_status(self):
        adapter = _make_adapter()
        status = adapter.get_status()
        self.assertIn("enabled", status)
        self.assertTrue(status["enabled"])
        self.assertEqual(status["managed_tasks"], 0)
        self.assertEqual(status["orchestrator_executions"], 0)

        adapter.on_cron_trigger("j", {"name": "j", "agent": "rd-company"})
        status = adapter.get_status()
        self.assertEqual(status["orchestrator_executions"], 1)

    # ------------------------------------------------------------------
    # 11. disabled adapter returns None / empty everywhere
    # ------------------------------------------------------------------
    def test_disabled_adapt_returns_none(self):
        adapter = _make_adapter(enabled=False)
        self.assertIsNone(adapter.adapt_job({"name": "x", "agent": "rd-company"}))
        self.assertEqual(adapter.adapt_all_jobs("/whatever"), [])

    # ------------------------------------------------------------------
    # 12. pipeline template with null to-node edges (terminal nodes)
    # ------------------------------------------------------------------
    def test_pipeline_template_null_edge_skipped(self):
        adapter = _make_adapter()
        job = {
            "name": "terminal",
            "agent": "role-qa-test",
            "pipeline": {
                "nodes": [
                    {"id": "n1", "type": "task", "role": "role-qa-test", "taskType": "test"},
                ],
                "edges": [
                    {"from": "n1", "to": None, "condition": "always"},
                ],
            },
        }
        pipeline = adapter.adapt_job(job)
        self.assertIsNotNone(pipeline)
        self.assertEqual(len(pipeline.edges), 0)


if __name__ == "__main__":
    unittest.main()
