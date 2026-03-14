#!/usr/bin/env python3
"""OpenClaw Company Kit control server.

Runs a local web UI for step-by-step setup and service control.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

ROOT_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT_DIR / "web"
DASHBOARD_DIR = ROOT_DIR / "dashboard" / "rd-dashboard"
ENV_FILE = ROOT_DIR / ".env"

DEFAULT_CONFIG = {
    "OPENCLAW_PROFILE": "company",
    "SOURCE_OPENCLAW_CONFIG": "~/.openclaw/openclaw.json",
    "COMPANY_NAME": "OpenClaw Company",
    "PROJECT_PATH": "/path/to/your-project",
    "PROJECT_REPO": "your-org/your-repo",
    "WORKFLOW_TEMPLATE": "default",
    "GROUP_ID": "",
    "FEISHU_HOT_ACCOUNT_ID": "hot-search",
    "FEISHU_HOT_BOT_NAME": "小龙虾 1 号",
    "FEISHU_HOT_APP_ID": "",
    "FEISHU_HOT_APP_SECRET": "",
    "FEISHU_AI_ACCOUNT_ID": "ai-tech",
    "FEISHU_AI_BOT_NAME": "小龙虾 2 号",
    "FEISHU_AI_APP_ID": "",
    "FEISHU_AI_APP_SECRET": "",
    "GH_TOKEN": "",
    "MODEL_PRIMARY": "",
    "CUSTOM_BASE_URL": "",
    "CUSTOM_API_KEY": "",
    "CUSTOM_MODEL_ID": "",
    "CUSTOM_PROVIDER_ID": "",
    "CUSTOM_COMPATIBILITY": "",
    "DASHBOARD_PORT": "8788",
    "MODEL_SUBAGENT": "",
    "DISCORD_BOT_TOKEN": "",
    "DISCORD_GUILD_ID": "",
    "DISCORD_CHANNEL_ID": "",
}

ENV_KEY_ORDER = [
    "OPENCLAW_PROFILE",
    "SOURCE_OPENCLAW_CONFIG",
    "COMPANY_NAME",
    "PROJECT_PATH",
    "PROJECT_REPO",
    "WORKFLOW_TEMPLATE",
    "GROUP_ID",
    "FEISHU_HOT_ACCOUNT_ID",
    "FEISHU_HOT_BOT_NAME",
    "FEISHU_HOT_APP_ID",
    "FEISHU_HOT_APP_SECRET",
    "FEISHU_AI_ACCOUNT_ID",
    "FEISHU_AI_BOT_NAME",
    "FEISHU_AI_APP_ID",
    "FEISHU_AI_APP_SECRET",
    "GH_TOKEN",
    "MODEL_PRIMARY",
    "CUSTOM_BASE_URL",
    "CUSTOM_API_KEY",
    "CUSTOM_MODEL_ID",
    "CUSTOM_PROVIDER_ID",
    "CUSTOM_COMPATIBILITY",
    "DASHBOARD_PORT",
    "MODEL_SUBAGENT",
    "DISCORD_BOT_TOKEN",
    "DISCORD_GUILD_ID",
    "DISCORD_CHANNEL_ID",
]

TASK_MAX_LOG_LINES = 1200
TASKS: dict[str, dict] = {}
TASK_LOCK = threading.Lock()
TASK_HISTORY_LOCK = threading.Lock()
TASK_AUDIT_LOCK = threading.Lock()
SERVER_PORT = 8788
AUTH_TOKEN: str | None = None
AUTH_TOKEN_EPHEMERAL = False
AUTH_COOKIE_NAME = "openclaw_control_token"
TASK_HISTORY_FILE = "control-task-history.jsonl"
TASK_AUDIT_FILE = "control-audit-log.jsonl"


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def resolve_auth_token(cli_token: str | None, env_token: str | None) -> tuple[str, bool]:
    token = (cli_token or env_token or "").strip()
    if token:
        return token, False
    return secrets.token_urlsafe(32), True


def parse_env_file(path: Path) -> tuple[dict[str, str], list[str]]:
    data: dict[str, str] = {}
    order: list[str] = []
    if not path.exists():
        return data, order

    key_re = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue

        key, value = raw_line.split("=", 1)
        key = key.strip()
        if not key_re.match(key):
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == "'":
            value = value[1:-1].replace("'\"'\"'", "'")
        elif len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]

        data[key] = value
        order.append(key)

    return data, order


def shell_quote(value: str) -> str:
    return "'" + str(value).replace("'", "'\"'\"'") + "'"


def merged_config() -> dict[str, str]:
    cfg = dict(DEFAULT_CONFIG)
    cfg["DASHBOARD_PORT"] = str(SERVER_PORT)
    existing, _ = parse_env_file(ENV_FILE)
    cfg.update(existing)
    return cfg


def normalize_config(input_cfg: dict, current: dict[str, str] | None = None) -> dict[str, str]:
    base = dict(current or merged_config())
    for key, value in input_cfg.items():
        if key not in DEFAULT_CONFIG:
            continue
        if value is None:
            base[key] = ""
        else:
            base[key] = str(value).strip()

    port_text = base.get("DASHBOARD_PORT", "8788").strip()
    if not re.fullmatch(r"\d{1,5}", port_text):
        raise ValueError("DASHBOARD_PORT must be a number")

    port = int(port_text)
    if port < 1 or port > 65535:
        raise ValueError("DASHBOARD_PORT must be between 1 and 65535")

    base["DASHBOARD_PORT"] = str(port)
    return base


def write_env(config: dict[str, str], previous_order: list[str], previous_data: dict[str, str]) -> None:
    lines = [
        "# -------------------------------",
        "# OpenClaw Company Kit",
        "# Generated by scripts/control_server.py",
        "# -------------------------------",
        "",
    ]

    emitted: set[str] = set()

    def emit_key(key: str) -> None:
        lines.append(f"{key}={shell_quote(config.get(key, ''))}")
        emitted.add(key)

    for key in ENV_KEY_ORDER:
        emit_key(key)

    extra_keys = []
    seen_extras: set[str] = set()
    for key in previous_order:
        if key not in emitted and key in previous_data and key not in seen_extras:
            extra_keys.append(key)
            seen_extras.add(key)
    for key in previous_data:
        if key not in emitted and key not in seen_extras:
            extra_keys.append(key)
            seen_extras.add(key)

    if extra_keys:
        lines.append("")
        lines.append("# Extra keys preserved from existing .env")
        for key in extra_keys:
            lines.append(f"{key}={shell_quote(previous_data.get(key, ''))}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def profile_dir(config: dict[str, str]) -> Path:
    profile = config.get("OPENCLAW_PROFILE", "company").strip() or "company"
    if profile in {"default", "main"}:
        return Path.home() / ".openclaw"
    return Path.home() / f".openclaw-{profile}"


def task_history_path(config: dict[str, str] | None = None) -> Path:
    cfg = config or merged_config()
    run_dir = profile_dir(cfg) / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / TASK_HISTORY_FILE


def task_audit_path(config: dict[str, str] | None = None) -> Path:
    cfg = config or merged_config()
    run_dir = profile_dir(cfg) / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir / TASK_AUDIT_FILE


def extract_task_error(logs: list[str]) -> str | None:
    for line in reversed(logs):
        text = (line or "").strip()
        if not text:
            continue
        if "[ERROR]" in text:
            return text
        if "Traceback" in text or "Exception" in text or "ERROR" in text:
            return text
        if text.startswith("[") or text.startswith("$ "):
            continue
        return text
    return None


def append_task_history(row: dict) -> None:
    path = task_history_path()
    payload = json.dumps(row, ensure_ascii=False)
    with TASK_HISTORY_LOCK:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(payload + "\n")


def append_task_audit(row: dict) -> None:
    path = task_audit_path()
    payload = dict(row or {})
    payload.setdefault("eventAt", now_text())
    payload.setdefault("eventAtEpoch", round(time.time(), 3))
    payload.setdefault("pid", os.getpid())
    payload.setdefault("profile", merged_config().get("OPENCLAW_PROFILE", "company"))
    line = json.dumps(payload, ensure_ascii=False)
    with TASK_AUDIT_LOCK:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def resolved_dashboard_dir(config: dict[str, str]) -> Path:
    deployed = profile_dir(config) / "workspace" / "rd-dashboard"
    if deployed.is_dir():
        return deployed
    return ROOT_DIR / "dashboard" / "rd-dashboard"


def collect_service_status(config: dict[str, str]) -> dict:
    run_dir = profile_dir(config) / "run"
    service_names = ["dashboard-refresh-loop", "issue-sync-loop"]
    services = []

    for name in service_names:
        pid_file = run_dir / f"{name}.pid"
        pid = None
        running = False
        if pid_file.exists():
            raw = pid_file.read_text(encoding="utf-8").strip()
            if raw.isdigit():
                pid = int(raw)
                try:
                    os.kill(pid, 0)
                    running = True
                except OSError:
                    running = False
        services.append({"name": name, "pid": pid, "running": running, "pidFile": str(pid_file)})

    return {
        "profileDir": str(profile_dir(config)),
        "runDir": str(run_dir),
        "services": services,
    }


def preflight_check(config: dict[str, str]) -> dict:
    checks: list[dict] = []

    required_tools = ["node", "openclaw", "jq", "python3", "rsync", "gh"]
    for tool in required_tools:
        found = shutil.which(tool) is not None
        entry: dict = {"name": tool, "ok": found, "type": "tool"}
        if tool == "node" and found:
            try:
                raw = subprocess.check_output(["node", "-v"], text=True).strip()
                entry["version"] = raw
                major = int(raw.lstrip("v").split(".")[0])
                if major < 22:
                    entry["ok"] = False
            except Exception:
                entry["ok"] = False
        checks.append(entry)

    # gh-issues skill auth check (non-blocking)
    gh_token = config.get("GH_TOKEN", "").strip()
    gh_auth_ok = False
    if gh_token:
        gh_auth_ok = True
    elif shutil.which("gh"):
        try:
            r = subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=5)
            gh_auth_ok = r.returncode == 0
        except Exception:
            pass
    checks.append({
        "name": "gh_auth",
        "ok": gh_auth_ok,
        "type": "auth",
        "hint": "配置 GH_TOKEN 或运行 gh auth login",
        "blocking": False,
    })

    required_vars = ["GROUP_ID", "FEISHU_HOT_APP_ID", "FEISHU_HOT_APP_SECRET"]
    for var in required_vars:
        checks.append({"name": var, "ok": bool(config.get(var, "").strip()), "type": "env"})

    oc_config_path = profile_dir(config) / "openclaw.json"
    source_path = config.get("SOURCE_OPENCLAW_CONFIG", "").strip()
    oc_ok = oc_config_path.exists()
    if not oc_ok and source_path:
        oc_ok = Path(source_path).expanduser().exists()
    checks.append({"name": "openclaw_config", "ok": oc_ok, "type": "config", "blocking": False})

    all_passed = all(c["ok"] for c in checks if c.get("blocking", True))
    return {"ok": True, "checks": checks, "allPassed": all_passed}


def append_task_log(task_id: str, line: str) -> None:
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        task["logs"].append(line)
        if len(task["logs"]) > TASK_MAX_LOG_LINES:
            task["logs"] = task["logs"][-TASK_MAX_LOG_LINES:]


def set_task_status(task_id: str, status: str, *, failed_step: str | None = None, failed_code: int | None = None) -> None:
    history_row: dict | None = None
    audit_row: dict | None = None
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return
        task["status"] = status
        if status in {"success", "failed"}:
            finished_epoch = time.time()
            task["finishedAt"] = now_text()
            task["finishedAtEpoch"] = finished_epoch
            started_epoch = float(task.get("startedAtEpoch") or finished_epoch)
            duration = max(0.0, round(finished_epoch - started_epoch, 3))
            task["durationSec"] = duration
            task["failedStep"] = failed_step
            task["failedCode"] = failed_code
            history_row = {
                "id": task.get("id"),
                "name": task.get("name"),
                "status": status,
                "startedAt": task.get("startedAt"),
                "finishedAt": task.get("finishedAt"),
                "durationSec": duration,
                "failedStep": failed_step,
                "failedCode": failed_code,
                "error": extract_task_error(task.get("logs") or []),
            }
            audit_row = {
                "event": "task_finished",
                "taskId": task.get("id"),
                "taskName": task.get("name"),
                "status": status,
                "durationSec": duration,
                "failedStep": failed_step,
                "failedCode": failed_code,
                "error": history_row.get("error"),
            }

    if history_row is not None:
        append_task_history(history_row)
    if audit_row is not None:
        append_task_audit(audit_row)


def run_task(task_id: str, steps: list[tuple[str, list[str]]]) -> None:
    try:
        for step_name, cmd in steps:
            step_started_epoch = time.time()
            append_task_log(task_id, f"[{now_text()}] STEP {step_name}")
            append_task_log(task_id, "$ " + " ".join(cmd))
            append_task_audit(
                {
                    "event": "task_step_start",
                    "taskId": task_id,
                    "step": step_name,
                    "cmd": list(cmd),
                }
            )
            proc = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                append_task_log(task_id, line.rstrip())
            code = proc.wait()
            append_task_log(task_id, f"[{now_text()}] EXIT {step_name}: {code}")
            append_task_audit(
                {
                    "event": "task_step_exit",
                    "taskId": task_id,
                    "step": step_name,
                    "cmd": list(cmd),
                    "exitCode": code,
                    "durationSec": max(0.0, round(time.time() - step_started_epoch, 3)),
                }
            )
            if code != 0:
                set_task_status(task_id, "failed", failed_step=step_name, failed_code=code)
                return
        set_task_status(task_id, "success")
    except Exception as exc:  # pylint: disable=broad-except
        append_task_log(task_id, f"[ERROR] {exc}")
        append_task_audit(
            {
                "event": "task_exception",
                "taskId": task_id,
                "step": "runtime",
                "error": str(exc),
            }
        )
        set_task_status(task_id, "failed", failed_step="runtime", failed_code=-1)


def create_task(name: str, steps: list[tuple[str, list[str]]]) -> dict:
    task_id = uuid.uuid4().hex[:10]
    started_epoch = time.time()
    task = {
        "id": task_id,
        "name": name,
        "status": "running",
        "startedAt": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started_epoch)),
        "startedAtEpoch": started_epoch,
        "finishedAt": None,
        "finishedAtEpoch": None,
        "durationSec": None,
        "failedStep": None,
        "failedCode": None,
        "steps": [x[0] for x in steps],
        "logs": [],
    }
    with TASK_LOCK:
        TASKS[task_id] = task

    append_task_audit(
        {
            "event": "task_created",
            "taskId": task_id,
            "taskName": name,
            "status": "running",
            "steps": [x[0] for x in steps],
            "stepCount": len(steps),
        }
    )

    thread = threading.Thread(target=run_task, args=(task_id, steps), daemon=True)
    thread.start()
    return task


def get_task(task_id: str) -> dict | None:
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if not task:
            return None
        return {
            "id": task["id"],
            "name": task["name"],
            "status": task["status"],
            "startedAt": task["startedAt"],
            "finishedAt": task["finishedAt"],
            "durationSec": task.get("durationSec"),
            "failedStep": task.get("failedStep"),
            "failedCode": task.get("failedCode"),
            "logs": list(task["logs"]),
        }


class ControlHandler(BaseHTTPRequestHandler):
    server_version = "OpenClawControl/1.0"

    def log_message(self, fmt: str, *args) -> None:
        _ = fmt, args

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def _check_auth(self) -> bool:
        if AUTH_TOKEN is None:
            return True
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
            return hmac.compare_digest(token, AUTH_TOKEN)
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:].strip()).decode("utf-8")
                _, password = decoded.split(":", 1)
                return hmac.compare_digest(password, AUTH_TOKEN)
            except Exception:
                return False
        cookie_token = self._read_cookie_token()
        if cookie_token:
            return hmac.compare_digest(cookie_token, AUTH_TOKEN)
        return False

    def _read_cookie_token(self) -> str | None:
        raw = self.headers.get("Cookie", "")
        if not raw:
            return None
        for chunk in raw.split(";"):
            item = chunk.strip()
            if not item or "=" not in item:
                continue
            key, value = item.split("=", 1)
            if key.strip() == AUTH_COOKIE_NAME:
                return unquote(value.strip())
        return None

    def _maybe_set_auth_cookie(self) -> None:
        if not AUTH_TOKEN:
            return
        val = quote(AUTH_TOKEN, safe="")
        self.send_header("Set-Cookie", f"{AUTH_COOKIE_NAME}={val}; Path=/; SameSite=Strict")

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._maybe_set_auth_cookie()
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._maybe_set_auth_cookie()
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", location)
        self._maybe_set_auth_cookie()
        self.end_headers()

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _serve_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self._send_text("Not Found", HTTPStatus.NOT_FOUND)
            return

        ctype, _ = mimetypes.guess_type(str(file_path))
        content_type = ctype or "application/octet-stream"
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._maybe_set_auth_cookie()
        self.end_headers()
        self.wfile.write(body)

    def _serve_dashboard(self, path: str) -> None:
        dash_dir = resolved_dashboard_dir(merged_config())

        if path in {"/dashboard", "/dashboard/"}:
            file_path = dash_dir / "index.html"
            self._serve_file(file_path)
            return

        rel = path[len("/dashboard/") :]
        rel_path = Path(rel)
        file_path = (dash_dir / rel_path).resolve()

        dashboard_root = dash_dir.resolve()
        if dashboard_root not in file_path.parents and file_path != dashboard_root:
            self._send_text("Forbidden", HTTPStatus.FORBIDDEN)
            return

        self._serve_file(file_path)

    def do_GET(self) -> None:  # pylint: disable=invalid-name
        path = urlparse(self.path).path

        if path == "/":
            self._redirect("/setup")
            return

        if path.startswith("/api/") and not self._check_auth():
            self._send_json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return

        if path == "/setup":
            self._serve_file(WEB_DIR / "setup.html")
            return

        if path == "/dashboard":
            self._redirect("/dashboard/")
            return

        if path.startswith("/dashboard/"):
            self._serve_dashboard(path)
            return

        if path == "/api/config":
            cfg = merged_config()
            first_time = not ENV_FILE.exists() or not cfg.get("GROUP_ID", "").strip()
            self._send_json({
                "ok": True,
                "config": cfg,
                "firstTime": first_time,
                "service": collect_service_status(cfg),
                "server": {"rootDir": str(ROOT_DIR)},
                "auth": {
                    "enabled": AUTH_TOKEN is not None,
                    "ephemeral": AUTH_TOKEN_EPHEMERAL,
                    "cookieName": AUTH_COOKIE_NAME,
                },
            })
            return

        if path == "/api/preflight":
            cfg = merged_config()
            self._send_json(preflight_check(cfg))
            return

        if path == "/api/service/status":
            cfg = merged_config()
            self._send_json({"ok": True, "service": collect_service_status(cfg)})
            return

        if path.startswith("/api/task/"):
            task_id = path.rsplit("/", 1)[-1].strip()
            task = get_task(task_id)
            if not task:
                self._send_json({"ok": False, "error": "task not found"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json({"ok": True, "task": task})
            return

        self._send_text("Not Found", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # pylint: disable=invalid-name
        path = urlparse(self.path).path

        if not self._check_auth():
            self._send_json({"ok": False, "error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return

        try:
            payload = self._read_json()
        except json.JSONDecodeError:
            self._send_json({"ok": False, "error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/config/save":
            cfg_payload = payload.get("config", payload)
            if not isinstance(cfg_payload, dict):
                self._send_json({"ok": False, "error": "config must be object"}, HTTPStatus.BAD_REQUEST)
                return

            try:
                old_data, old_order = parse_env_file(ENV_FILE)
                cfg = normalize_config(cfg_payload)
                write_env(cfg, old_order, old_data)
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            self._send_json({"ok": True, "config": cfg})
            return

        if path == "/api/config/apply":
            cfg_payload = payload.get("config", payload)
            if not isinstance(cfg_payload, dict):
                self._send_json({"ok": False, "error": "config must be object"}, HTTPStatus.BAD_REQUEST)
                return

            try:
                old_data, old_order = parse_env_file(ENV_FILE)
                cfg = normalize_config(cfg_payload)
                write_env(cfg, old_order, old_data)
            except ValueError as exc:
                self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return

            task = create_task(
                "apply",
                [
                    ("stop", ["bash", "scripts/stop.sh"]),
                    ("onboard", ["bash", "scripts/onboard-wrapper.sh"]),
                    ("install", ["bash", "scripts/install.sh"]),
                    ("start", ["bash", "scripts/start.sh"]),
                    ("healthcheck", ["bash", "scripts/healthcheck.sh"]),
                ],
            )
            self._send_json({"ok": True, "taskId": task["id"]})
            return

        if path == "/api/service/restart":
            task = create_task(
                "restart",
                [
                    ("stop", ["bash", "scripts/stop.sh"]),
                    ("start", ["bash", "scripts/start.sh"]),
                    ("healthcheck", ["bash", "scripts/healthcheck.sh"]),
                ],
            )
            self._send_json({"ok": True, "taskId": task["id"]})
            return

        self._send_json({"ok": False, "error": "not found"}, HTTPStatus.NOT_FOUND)


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenClaw Company Kit control server")
    parser.add_argument("--port", type=int, default=8788, help="Server port")
    parser.add_argument("--token", type=str, default=None, help="Bearer token for API auth (omit to auto-generate)")
    args = parser.parse_args()

    if args.port < 1 or args.port > 65535:
        raise SystemExit("port must be in [1, 65535]")

    global SERVER_PORT, AUTH_TOKEN, AUTH_TOKEN_EPHEMERAL  # pylint: disable=global-statement
    SERVER_PORT = args.port
    AUTH_TOKEN, AUTH_TOKEN_EPHEMERAL = resolve_auth_token(args.token, os.environ.get("CONTROL_TOKEN"))

    WEB_DIR.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), ControlHandler)
    print(f"[control] root={ROOT_DIR}")
    print(f"[control] setup:     http://127.0.0.1:{args.port}/setup")
    print(f"[control] dashboard: http://127.0.0.1:{args.port}/dashboard/")
    print(f"[control] auth:      Bearer token enabled")
    if AUTH_TOKEN_EPHEMERAL:
        print(f"[control] token:     {AUTH_TOKEN}")
        print(f"[control] hint:      set CONTROL_TOKEN in .env (or --token) to keep token stable")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
