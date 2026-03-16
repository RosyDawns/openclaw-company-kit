"""Smoke tests for control server API and minimal apply/restart chain."""

import json
import os
import threading
import tempfile
import unittest
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib import error, request

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import control_server as cs  # noqa: E402


class ControlApiSmokeTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.env_file = Path(self.tmpdir.name) / ".env"

        self._orig_env_file = cs.ENV_FILE
        self._orig_auth_token = cs.AUTH_TOKEN
        self._orig_auth_ephemeral = cs.AUTH_TOKEN_EPHEMERAL
        self._orig_create_task = cs.create_task

        cs.ENV_FILE = self.env_file
        cs.AUTH_TOKEN = "smoke-token"
        cs.AUTH_TOKEN_EPHEMERAL = False

        from server.handlers import config as _cfg_h
        self._config_svc = _cfg_h._config_service
        self._task_svc = _cfg_h._task_service

        if self._config_svc is not None:
            self._orig_svc_env_file = self._config_svc._env_file
            self._config_svc._env_file = self.env_file

        if self._task_svc is not None:
            self._orig_svc_create_task = self._task_svc.create_task

        try:
            self.server = ThreadingHTTPServer(("127.0.0.1", 0), cs.ControlHandler)
        except OSError as exc:
            self.tmpdir.cleanup()
            raise unittest.SkipTest(f"socket bind unavailable in current environment: {exc}") from exc

        self.port = int(self.server.server_address[1])
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        try:
            if hasattr(self, "server"):
                self.server.shutdown()
                self.server.server_close()
            if hasattr(self, "thread"):
                self.thread.join(timeout=2.0)
        finally:
            cs.ENV_FILE = self._orig_env_file
            cs.AUTH_TOKEN = self._orig_auth_token
            cs.AUTH_TOKEN_EPHEMERAL = self._orig_auth_ephemeral
            cs.create_task = self._orig_create_task
            if self._config_svc is not None:
                self._config_svc._env_file = self._orig_svc_env_file
            if self._task_svc is not None:
                self._task_svc.create_task = self._orig_svc_create_task
            self.tmpdir.cleanup()

    def _api(self, method: str, path: str, body: dict | None = None, token: str | None = "smoke-token"):
        url = f"http://127.0.0.1:{self.port}{path}"
        data = None
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        req = request.Request(url, method=method, data=data, headers=headers)
        try:
            with request.urlopen(req, timeout=5) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                return resp.status, payload
        except error.HTTPError as exc:
            payload = json.loads(exc.read().decode("utf-8"))
            return exc.code, payload

    def test_requires_auth_for_api(self):
        status, payload = self._api("GET", "/api/config", token=None)
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)
        self.assertFalse(payload.get("ok"))
        self.assertEqual(payload.get("error"), "unauthorized")

    def test_config_preflight_and_service_status_smoke(self):
        status_cfg, payload_cfg = self._api("GET", "/api/config")
        self.assertEqual(status_cfg, HTTPStatus.OK)
        self.assertTrue(payload_cfg.get("ok"))
        self.assertIn("config", payload_cfg)
        self.assertIn("service", payload_cfg)
        self.assertIn("auth", payload_cfg)

        status_pf, payload_pf = self._api("GET", "/api/preflight")
        self.assertEqual(status_pf, HTTPStatus.OK)
        self.assertTrue(payload_pf.get("ok"))
        self.assertIsInstance(payload_pf.get("checks"), list)
        self.assertIn("allPassed", payload_pf)

        status_svc, payload_svc = self._api("GET", "/api/service/status")
        self.assertEqual(status_svc, HTTPStatus.OK)
        self.assertTrue(payload_svc.get("ok"))
        services = ((payload_svc.get("service") or {}).get("services")) or []
        self.assertIsInstance(services, list)

    def test_apply_and_restart_step_chain_smoke(self):
        calls = []

        def fake_create_task(name, steps):
            calls.append((name, steps))
            return {"id": f"task-{name}"}

        cs.create_task = fake_create_task
        if self._task_svc is not None:
            self._task_svc.create_task = fake_create_task

        status_apply, payload_apply = self._api(
            "POST",
            "/api/config/apply",
            body={"config": {"DASHBOARD_PORT": "8788", "GROUP_ID": "oc_test"}},
        )
        self.assertEqual(status_apply, HTTPStatus.OK)
        self.assertTrue(payload_apply.get("ok"))
        self.assertEqual(payload_apply.get("taskId"), "task-apply")

        self.assertGreaterEqual(len(calls), 1)
        apply_name, apply_steps = calls[0]
        self.assertEqual(apply_name, "apply")
        self.assertEqual([x[0] for x in apply_steps], ["stop", "onboard", "install", "start", "healthcheck"])

        status_restart, payload_restart = self._api("POST", "/api/service/restart", body={})
        self.assertEqual(status_restart, HTTPStatus.OK)
        self.assertTrue(payload_restart.get("ok"))
        self.assertEqual(payload_restart.get("taskId"), "task-restart")

        self.assertGreaterEqual(len(calls), 2)
        restart_name, restart_steps = calls[1]
        self.assertEqual(restart_name, "restart")
        self.assertEqual([x[0] for x in restart_steps], ["stop", "start", "healthcheck"])

        self.assertTrue(self.env_file.exists(), "apply should persist .env via write_env")
        content = self.env_file.read_text(encoding="utf-8")
        self.assertIn("DASHBOARD_PORT=", content)
        self.assertIn("GROUP_ID=", content)


if __name__ == "__main__":
    unittest.main()
