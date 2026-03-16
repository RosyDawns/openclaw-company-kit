from __future__ import annotations

import unittest

from engine.dispatch import (
    DispatchRequest,
    DispatchRule,
    Dispatcher,
    Priority,
    PriorityQueue,
    WIPTracker,
)
from engine.models import Task
from engine.roles import RoleRegistry


def _make_registry() -> RoleRegistry:
    """Build a RoleRegistry from the project's role_config.json."""
    return RoleRegistry()


def _make_task(name: str = "t") -> Task:
    return Task(id=f"task-{name}", name=name)


class TestDispatchCodeTask(unittest.TestCase):
    def test_dispatch_code_task(self) -> None:
        reg = _make_registry()
        d = Dispatcher(reg)
        d.load_default_rules()

        req = d.dispatch(_make_task("code1"), "code")
        self.assertEqual(req.assigned_role, "role-senior-dev")
        self.assertIsNotNone(req.dispatched_at)


class TestDispatchTestTask(unittest.TestCase):
    def test_dispatch_test_task(self) -> None:
        reg = _make_registry()
        d = Dispatcher(reg)
        d.load_default_rules()

        req = d.dispatch(_make_task("test1"), "test")
        self.assertEqual(req.assigned_role, "role-qa-test")


class TestDispatchProductTask(unittest.TestCase):
    def test_dispatch_product_task(self) -> None:
        reg = _make_registry()
        d = Dispatcher(reg)
        d.load_default_rules()

        req = d.dispatch(_make_task("prod1"), "product")
        self.assertEqual(req.assigned_role, "role-product")


class TestWIPLimitExceeded(unittest.TestCase):
    def test_wip_limit_exceeded(self) -> None:
        """role-senior-dev has wip_limit=1; second dispatch should queue."""
        reg = _make_registry()
        d = Dispatcher(reg)
        d.load_default_rules()

        req1 = d.dispatch(_make_task("c1"), "code")
        self.assertEqual(req1.assigned_role, "role-senior-dev")

        req2 = d.dispatch(_make_task("c2"), "code")
        self.assertIsNone(req2.assigned_role)
        self.assertIsNone(req2.dispatched_at)
        self.assertEqual(d._queue.size(), 1)


class TestWIPReleaseTriggers(unittest.TestCase):
    def test_wip_release_triggers_dispatch(self) -> None:
        reg = _make_registry()
        d = Dispatcher(reg)
        d.load_default_rules()

        req1 = d.dispatch(_make_task("c1"), "code")
        req2 = d.dispatch(_make_task("c2"), "code")
        self.assertIsNone(req2.assigned_role)

        newly = d.complete_task(req1.task, "role-senior-dev")
        self.assertEqual(len(newly), 1)
        self.assertEqual(newly[0].assigned_role, "role-senior-dev")
        self.assertEqual(newly[0].task.id, "task-c2")


class TestPriorityOrdering(unittest.TestCase):
    def test_priority_ordering(self) -> None:
        q = PriorityQueue()
        r_p2 = DispatchRequest(task=_make_task("p2"), task_type="code", priority=Priority.P2)
        r_p0 = DispatchRequest(task=_make_task("p0"), task_type="code", priority=Priority.P0)
        r_p1 = DispatchRequest(task=_make_task("p1"), task_type="code", priority=Priority.P1)

        q.push(r_p2)
        q.push(r_p0)
        q.push(r_p1)

        self.assertEqual(q.pop().priority, Priority.P0)
        self.assertEqual(q.pop().priority, Priority.P1)
        self.assertEqual(q.pop().priority, Priority.P2)


class TestLoadDefaultRules(unittest.TestCase):
    def test_load_default_rules(self) -> None:
        reg = _make_registry()
        d = Dispatcher(reg)
        d.load_default_rules()

        expected = {"code", "test", "product", "design", "ops", "growth"}
        self.assertEqual(set(d._rules.keys()), expected)

        self.assertEqual(d.get_rule("code").target_roles, ["role-senior-dev"])
        self.assertEqual(d.get_rule("test").target_roles, ["role-qa-test"])
        self.assertEqual(d.get_rule("ops").target_roles, ["rd-company"])
        self.assertTrue(d.get_rule("code").requires_review)
        self.assertFalse(d.get_rule("product").requires_review)


class TestDispatchUnknownType(unittest.TestCase):
    def test_dispatch_unknown_type(self) -> None:
        reg = _make_registry()
        d = Dispatcher(reg)
        d.load_default_rules()

        with self.assertRaises(ValueError):
            d.dispatch(_make_task("x"), "nonexistent")


class TestCompleteTaskReleasesWIP(unittest.TestCase):
    def test_complete_task_releases_wip(self) -> None:
        reg = _make_registry()
        d = Dispatcher(reg)
        d.load_default_rules()

        req = d.dispatch(_make_task("c1"), "code")
        self.assertEqual(d._wip_tracker.get_count("role-senior-dev"), 1)

        d.complete_task(req.task, "role-senior-dev")
        self.assertEqual(d._wip_tracker.get_count("role-senior-dev"), 0)


class TestQueueStatus(unittest.TestCase):
    def test_queue_status(self) -> None:
        reg = _make_registry()
        d = Dispatcher(reg)
        d.load_default_rules()

        d.dispatch(_make_task("c1"), "code")
        d.dispatch(_make_task("c2"), "code", Priority.P0)

        status = d.get_queue_status()
        self.assertEqual(status["queue_size"], 1)
        self.assertEqual(status["wip"]["role-senior-dev"], 1)
        self.assertEqual(status["queued_by_priority"]["P0"], 1)
        self.assertEqual(status["rules_count"], 6)


if __name__ == "__main__":
    unittest.main()
