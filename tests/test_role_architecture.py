"""RB-14: Comprehensive 3-layer role architecture tests.

Validates layer completeness, dispatch correctness, review routing,
permission boundaries, manifest consistency, and registry validation.
"""

import json
import os
import unittest

from engine.dispatch import Dispatcher, Priority
from engine.models import Task
from engine.review_gate import ReviewGate
from engine.roles import RoleLayer, RoleRegistry
from engine.state_machine import StateMachine

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(PROJECT_ROOT, "templates", "agents")
ROLE_CONFIG_PATH = os.path.join(PROJECT_ROOT, "engine", "role_config.json")

ALL_ROLE_NAMES = {
    "rd-company",
    "role-code-reviewer",
    "role-tech-director",
    "role-product",
    "role-senior-dev",
    "role-qa-test",
    "role-growth",
    "ai-tech",
    "hot-search",
}

MANIFEST_REQUIRED_FIELDS = {"name", "displayName", "layer", "capabilities", "wipLimit"}

VALID_LAYERS = {layer.value for layer in RoleLayer}


class TestLayerCompleteness(unittest.TestCase):
    """Every role belongs to exactly one layer; layer counts match spec."""

    def setUp(self):
        self.registry = RoleRegistry()

    def test_all_roles_have_unique_layer(self):
        roles = self.registry.get_all_roles()
        self.assertEqual(len(roles), 9)
        seen = {}
        for role in roles:
            self.assertIsInstance(role.layer, RoleLayer)
            seen.setdefault(role.name, []).append(role.layer)
        for name, layers in seen.items():
            self.assertEqual(len(layers), 1, f"{name} mapped to multiple layers")

    def test_dispatcher_count(self):
        dispatchers = self.registry.get_layer_roles(RoleLayer.DISPATCHER)
        self.assertEqual(len(dispatchers), 1)
        self.assertEqual(dispatchers[0].name, "rd-company")

    def test_reviewer_count(self):
        reviewers = self.registry.get_layer_roles(RoleLayer.REVIEWER)
        self.assertEqual(len(reviewers), 2)
        names = {r.name for r in reviewers}
        self.assertEqual(names, {"role-code-reviewer", "role-tech-director"})

    def test_executor_count(self):
        executors = self.registry.get_layer_roles(RoleLayer.EXECUTOR)
        self.assertEqual(len(executors), 4)
        names = {r.name for r in executors}
        self.assertEqual(
            names,
            {"role-product", "role-senior-dev", "role-qa-test", "role-growth"},
        )

    def test_sub_roles_count(self):
        d_subs = self.registry.get_layer_roles(RoleLayer.DISPATCHER_SUB)
        e_subs = self.registry.get_layer_roles(RoleLayer.EXECUTOR_SUB)
        self.assertEqual(len(d_subs), 1)
        self.assertEqual(len(e_subs), 1)
        self.assertEqual(d_subs[0].name, "ai-tech")
        self.assertEqual(e_subs[0].name, "hot-search")

    def test_no_duplicate_roles(self):
        names = [r.name for r in self.registry.get_all_roles()]
        self.assertEqual(len(names), len(set(names)), f"Duplicate roles: {names}")


class TestDispatchCorrectness(unittest.TestCase):
    """Dispatch rules route task types to the correct executor roles."""

    def setUp(self):
        self.registry = RoleRegistry()
        self.dispatcher = Dispatcher(self.registry)
        self.dispatcher.load_default_rules()

    def _dispatch(self, task_type: str) -> str:
        task = Task(id=f"t-{task_type}", name=f"Test {task_type} task")
        req = self.dispatcher.dispatch(task, task_type)
        return req.assigned_role

    def test_code_task_dispatches_to_senior_dev(self):
        self.assertEqual(self._dispatch("code"), "role-senior-dev")

    def test_test_task_dispatches_to_qa_test(self):
        self.assertEqual(self._dispatch("test"), "role-qa-test")

    def test_product_task_dispatches_to_product(self):
        self.assertEqual(self._dispatch("product"), "role-product")

    def test_design_task_dispatches_to_tech_director(self):
        self.assertEqual(self._dispatch("design"), "role-tech-director")


class TestReviewTrigger(unittest.TestCase):
    """Review routing sends task types to the correct reviewer roles."""

    def setUp(self):
        self.sm = StateMachine()
        self.gate = ReviewGate(state_machine=self.sm)

    def test_code_review_routes_to_code_reviewer(self):
        reviewer = self.gate.auto_route("code")
        self.assertEqual(reviewer, "role-code-reviewer")

    def test_design_review_routes_to_tech_director(self):
        reviewer = self.gate.auto_route("design")
        self.assertEqual(reviewer, "role-tech-director")

    def test_ops_requires_dual_review(self):
        self.assertTrue(self.gate.requires_dual_review("ops"))


class TestPermissionBoundary(unittest.TestCase):
    """Executor roles cannot bypass the dispatcher to reach reviewers."""

    def setUp(self):
        self.registry = RoleRegistry()

    def test_executor_cannot_call_reviewer_directly(self):
        reviewer_names = {
            r.name for r in self.registry.get_layer_roles(RoleLayer.REVIEWER)
        }
        for executor in self.registry.get_layer_roles(RoleLayer.EXECUTOR):
            overlap = reviewer_names & set(executor.allowed_callees)
            self.assertEqual(
                overlap,
                set(),
                f"Executor '{executor.name}' can directly call reviewers: {overlap}",
            )

    def test_executor_cannot_call_another_executor(self):
        executors = self.registry.get_layer_roles(RoleLayer.EXECUTOR)
        executor_names = {r.name for r in executors}
        for role in executors:
            illegal = (executor_names - {role.name}) & set(role.allowed_callees)
            self.assertEqual(
                illegal,
                set(),
                f"Executor '{role.name}' can call peer executors: {illegal}",
            )

    def test_dispatcher_can_call_all_main_roles(self):
        dispatcher = self.registry.get_role("rd-company")
        main_roles = (
            self.registry.get_layer_roles(RoleLayer.REVIEWER)
            + self.registry.get_layer_roles(RoleLayer.EXECUTOR)
        )
        for role in main_roles:
            self.assertIn(
                role.name,
                dispatcher.allowed_callees,
                f"Dispatcher cannot call main role '{role.name}'",
            )

    def test_wip_limit_positive(self):
        for role in self.registry.get_all_roles():
            self.assertGreater(
                role.wip_limit, 0, f"Role '{role.name}' has non-positive WIP limit"
            )


class TestManifestConsistency(unittest.TestCase):
    """Manifest files match the engine role_config and are well-formed."""

    def setUp(self):
        self.registry = RoleRegistry()
        with open(ROLE_CONFIG_PATH, encoding="utf-8") as f:
            self.role_config = json.load(f)
        self.config_by_name = {r["name"]: r for r in self.role_config["roles"]}

    def _load_manifest(self, role_name: str) -> dict:
        path = os.path.join(AGENTS_DIR, role_name, "manifest.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_all_manifests_exist(self):
        for name in ALL_ROLE_NAMES:
            path = os.path.join(AGENTS_DIR, name, "manifest.json")
            self.assertTrue(os.path.isfile(path), f"Missing manifest: {path}")

    def test_manifests_valid_json(self):
        for name in ALL_ROLE_NAMES:
            path = os.path.join(AGENTS_DIR, name, "manifest.json")
            with open(path, encoding="utf-8") as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as exc:
                    self.fail(f"Invalid JSON in {path}: {exc}")

    def test_manifest_required_fields(self):
        for name in ALL_ROLE_NAMES:
            manifest = self._load_manifest(name)
            missing = MANIFEST_REQUIRED_FIELDS - set(manifest.keys())
            self.assertEqual(
                missing, set(), f"{name}/manifest.json missing fields: {missing}"
            )

    def test_manifest_layer_in_valid_enum(self):
        for name in ALL_ROLE_NAMES:
            manifest = self._load_manifest(name)
            self.assertIn(
                manifest["layer"],
                VALID_LAYERS,
                f"{name}/manifest.json layer '{manifest['layer']}' not in {VALID_LAYERS}",
            )

    def test_manifest_name_matches_directory(self):
        for name in ALL_ROLE_NAMES:
            manifest = self._load_manifest(name)
            self.assertEqual(
                manifest["name"],
                name,
                f"Directory '{name}' vs manifest name '{manifest['name']}'",
            )

    def test_manifest_matches_role_config(self):
        field_map = {
            "displayName": "display_name",
            "layer": "layer",
            "capabilities": "capabilities",
            "reviewScope": "review_scope",
            "wipLimit": "wip_limit",
            "dependencies": "dependencies",
            "cronJobs": "cron_jobs",
        }
        for name in ALL_ROLE_NAMES:
            manifest = self._load_manifest(name)
            config = self.config_by_name[name]
            for m_key, c_key in field_map.items():
                if m_key not in manifest:
                    continue
                self.assertEqual(
                    manifest[m_key],
                    config[c_key],
                    f"{name}: manifest.{m_key} != config.{c_key}",
                )


class TestValidation(unittest.TestCase):
    """Registry-level validation catches no errors for the shipped config."""

    def test_registry_validates_clean(self):
        registry = RoleRegistry()
        errors = registry.validate()
        self.assertEqual(errors, [], f"Validation errors: {errors}")


if __name__ == "__main__":
    unittest.main()
