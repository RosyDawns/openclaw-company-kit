import json
import os
import tempfile
import unittest

from engine.roles import RoleDefinition, RoleLayer, RoleRegistry


class TestRoleConfig(unittest.TestCase):
    """Tests against the real role_config.json shipped with the engine."""

    def setUp(self):
        self.registry = RoleRegistry()

    # -- loading / registration --

    def test_load_config(self):
        roles = self.registry.get_all_roles()
        self.assertEqual(len(roles), 9)

    def test_all_roles_registered(self):
        names = {r.name for r in self.registry.get_all_roles()}
        expected = {
            "rd-company",
            "role-tech-director",
            "role-code-reviewer",
            "role-product",
            "role-senior-dev",
            "role-qa-test",
            "role-growth",
            "hot-search",
            "ai-tech",
        }
        self.assertEqual(names, expected)

    # -- lookup --

    def test_get_role_by_name(self):
        role = self.registry.get_role("rd-company")
        self.assertIsNotNone(role)
        self.assertEqual(role.name, "rd-company")
        self.assertEqual(role.display_name, "研发主管")
        self.assertEqual(role.layer, RoleLayer.DISPATCHER)

    def test_get_role_not_found(self):
        self.assertIsNone(self.registry.get_role("nonexistent"))

    # -- layer queries --

    def test_get_layer_roles(self):
        self.assertEqual(len(self.registry.get_layer_roles(RoleLayer.DISPATCHER)), 1)
        self.assertEqual(len(self.registry.get_layer_roles(RoleLayer.REVIEWER)), 2)
        self.assertEqual(len(self.registry.get_layer_roles(RoleLayer.EXECUTOR)), 4)
        sub_total = len(
            self.registry.get_layer_roles(RoleLayer.DISPATCHER_SUB)
        ) + len(self.registry.get_layer_roles(RoleLayer.EXECUTOR_SUB))
        self.assertEqual(sub_total, 2)

    def test_dispatcher_layer(self):
        role = self.registry.get_role("rd-company")
        self.assertEqual(role.layer, RoleLayer.DISPATCHER)

    def test_reviewer_layer(self):
        cr = self.registry.get_role("role-code-reviewer")
        td = self.registry.get_role("role-tech-director")
        self.assertEqual(cr.layer, RoleLayer.REVIEWER)
        self.assertEqual(td.layer, RoleLayer.REVIEWER)

    def test_executor_layer(self):
        for name in ("role-product", "role-senior-dev", "role-qa-test", "role-growth"):
            role = self.registry.get_role(name)
            self.assertEqual(
                role.layer, RoleLayer.EXECUTOR, f"{name} should be EXECUTOR"
            )

    def test_sub_layers(self):
        ai = self.registry.get_role("ai-tech")
        hs = self.registry.get_role("hot-search")
        self.assertEqual(ai.layer, RoleLayer.DISPATCHER_SUB)
        self.assertEqual(hs.layer, RoleLayer.EXECUTOR_SUB)

    # -- validation --

    def test_validate_integrity(self):
        errors = self.registry.validate()
        self.assertEqual(errors, [])

    def test_validate_catches_invalid_callee(self):
        reg = RoleRegistry(config_path=None)
        for layer in RoleLayer:
            reg.register(
                RoleDefinition(
                    name=f"stub-{layer.value}",
                    display_name="stub",
                    layer=layer,
                )
            )
        reg.register(
            RoleDefinition(
                name="bad-role",
                display_name="Bad",
                layer=RoleLayer.EXECUTOR,
                allowed_callees=["ghost-role"],
            )
        )
        errors = reg.validate()
        self.assertTrue(any("ghost-role" in e for e in errors))

    def test_validate_catches_invalid_dependency(self):
        reg = RoleRegistry(config_path=None)
        for layer in RoleLayer:
            reg.register(
                RoleDefinition(
                    name=f"stub-{layer.value}",
                    display_name="stub",
                    layer=layer,
                )
            )
        reg.register(
            RoleDefinition(
                name="dep-role",
                display_name="Dep",
                layer=RoleLayer.EXECUTOR,
                dependencies=["missing-dep"],
            )
        )
        errors = reg.validate()
        self.assertTrue(any("missing-dep" in e for e in errors))

    # -- wip / review scope constraints --

    def test_wip_limits(self):
        for role in self.registry.get_all_roles():
            self.assertGreaterEqual(
                role.wip_limit, 1, f"{role.name} wip_limit < 1"
            )
            self.assertLessEqual(
                role.wip_limit, 10, f"{role.name} wip_limit unreasonably high"
            )

    def test_review_scope_only_for_reviewers(self):
        for role in self.registry.get_all_roles():
            if role.layer != RoleLayer.REVIEWER:
                self.assertEqual(
                    role.review_scope,
                    [],
                    f"Non-reviewer '{role.name}' has non-empty review_scope",
                )

    # -- convenience helpers --

    def test_can_call(self):
        self.assertTrue(self.registry.can_call("rd-company", "role-tech-director"))
        self.assertTrue(self.registry.can_call("rd-company", "role-senior-dev"))
        self.assertFalse(self.registry.can_call("role-product", "role-senior-dev"))
        self.assertFalse(self.registry.can_call("role-growth", "role-qa-test"))

    def test_get_reviewers_for_type(self):
        code_reviewers = self.registry.get_reviewers_for_type("code")
        names = {r.name for r in code_reviewers}
        self.assertIn("role-code-reviewer", names)
        self.assertNotIn("role-tech-director", names)

        arch_reviewers = self.registry.get_reviewers_for_type("architecture")
        arch_names = {r.name for r in arch_reviewers}
        self.assertIn("role-tech-director", arch_names)

    # -- register / to_dict round-trip --

    def test_register_manual(self):
        reg = RoleRegistry(config_path=None)
        role = RoleDefinition(
            name="custom-role",
            display_name="Custom",
            layer=RoleLayer.EXECUTOR,
            capabilities=["test"],
        )
        reg.register(role)
        self.assertIsNotNone(reg.get_role("custom-role"))
        self.assertEqual(reg.get_all_roles()[0].capabilities, ["test"])

    def test_to_dict_round_trip(self):
        d = self.registry.to_dict()
        self.assertEqual(len(d["roles"]), 9)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(d, tmp, ensure_ascii=False)
            tmp_path = tmp.name

        try:
            reg2 = RoleRegistry(config_path=tmp_path)
            self.assertEqual(len(reg2.get_all_roles()), 9)
            for orig in self.registry.get_all_roles():
                reloaded = reg2.get_role(orig.name)
                self.assertIsNotNone(reloaded, f"{orig.name} missing after round-trip")
                self.assertEqual(orig.layer, reloaded.layer)
                self.assertEqual(orig.wip_limit, reloaded.wip_limit)
        finally:
            os.unlink(tmp_path)

    # -- load_from_config with custom file --

    def test_load_from_config_custom(self):
        data = {
            "roles": [
                {
                    "name": "solo",
                    "display_name": "Solo",
                    "layer": "dispatcher",
                    "capabilities": [],
                    "review_scope": [],
                    "wip_limit": 1,
                    "allowed_callees": [],
                    "cron_jobs": [],
                    "dependencies": [],
                }
            ]
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False)
            tmp_path = tmp.name

        try:
            reg = RoleRegistry(config_path=tmp_path)
            self.assertEqual(len(reg.get_all_roles()), 1)
            self.assertEqual(reg.get_role("solo").display_name, "Solo")
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
