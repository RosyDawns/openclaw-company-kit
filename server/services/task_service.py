"""Task management service.

Extracted from ``scripts/control_server.py`` — task lifecycle, logging,
history and audit logic lives here.

TODO(RB-07): Migrate append_history / append_audit / _task_*_path to
``server.data.task_store.TaskStore`` so this service no longer performs
direct JSONL file I/O.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.services.config_service import ConfigService

from server.services import profile_dir


class TaskService:
    """Pure-Python task management service (no HTTP dependency)."""

    TASK_MAX_LOG_LINES = 1200
    TASK_HISTORY_FILE = "control-task-history.jsonl"
    TASK_AUDIT_FILE = "control-audit-log.jsonl"

    def __init__(
        self,
        root_dir: Path | None = None,
        config_service: ConfigService | None = None,
    ) -> None:
        self._root_dir = root_dir or Path(__file__).resolve().parents[2]
        self._config_service = config_service  # TODO: decouple from global state
        self._tasks: dict[str, dict] = {}
        self._task_lock = threading.Lock()
        self._history_lock = threading.Lock()
        self._audit_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now_text() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def _get_merged_config(self) -> dict[str, str]:
        if self._config_service is not None:
            return self._config_service.get_merged_config()
        return {}

    def _task_history_path(self, config: dict[str, str] | None = None) -> Path:
        cfg = config or self._get_merged_config()
        run_dir = profile_dir(cfg) / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir / self.TASK_HISTORY_FILE

    def _task_audit_path(self, config: dict[str, str] | None = None) -> Path:
        cfg = config or self._get_merged_config()
        run_dir = profile_dir(cfg) / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir / self.TASK_AUDIT_FILE

    @staticmethod
    def _extract_task_error(logs: list[str]) -> str | None:
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

    def _append_log(self, task_id: str, line: str) -> None:
        with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task["logs"].append(line)
            if len(task["logs"]) > self.TASK_MAX_LOG_LINES:
                task["logs"] = task["logs"][-self.TASK_MAX_LOG_LINES:]

    def _run_task(self, task_id: str, steps: list[tuple]) -> None:
        """Execute *steps* sequentially in a background thread."""
        try:
            for step in steps:
                if len(step) == 2:
                    step_name, cmd = step
                    allowed_codes = {0}
                else:
                    step_name, cmd, allowed = step
                    allowed_codes = {int(code) for code in (allowed or [0])}
                    if not allowed_codes:
                        allowed_codes = {0}

                step_started_epoch = time.time()
                self._append_log(task_id, f"[{self._now_text()}] STEP {step_name}")
                self._append_log(task_id, "$ " + " ".join(cmd))
                self.append_audit({
                    "event": "task_step_start",
                    "taskId": task_id,
                    "step": step_name,
                    "cmd": list(cmd),
                })

                proc = subprocess.Popen(
                    cmd,
                    cwd=str(self._root_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    self._append_log(task_id, line.rstrip())
                code = proc.wait()

                self._append_log(task_id, f"[{self._now_text()}] EXIT {step_name}: {code}")
                if code != 0 and code in allowed_codes:
                    self._append_log(
                        task_id,
                        f"[WARN] {step_name} exited with {code} (tolerated for this workflow)",
                    )
                self.append_audit({
                    "event": "task_step_exit",
                    "taskId": task_id,
                    "step": step_name,
                    "cmd": list(cmd),
                    "exitCode": code,
                    "durationSec": max(0.0, round(time.time() - step_started_epoch, 3)),
                })

                if code not in allowed_codes:
                    self.set_task_status(task_id, "failed", failed_step=step_name, failed_code=code)
                    return

            self.set_task_status(task_id, "success")
        except Exception as exc:
            self._append_log(task_id, f"[ERROR] {exc}")
            self.append_audit({
                "event": "task_exception",
                "taskId": task_id,
                "step": "runtime",
                "error": str(exc),
            })
            self.set_task_status(task_id, "failed", failed_step="runtime", failed_code=-1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_task(self, name: str, steps: list[tuple]) -> dict:
        """Create a new background task that runs *steps* sequentially."""
        task_id = uuid.uuid4().hex[:10]
        started_epoch = time.time()
        task: dict = {
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
        with self._task_lock:
            self._tasks[task_id] = task

        self.append_audit({
            "event": "task_created",
            "taskId": task_id,
            "taskName": name,
            "status": "running",
            "steps": [x[0] for x in steps],
            "stepCount": len(steps),
        })

        thread = threading.Thread(target=self._run_task, args=(task_id, steps), daemon=True)
        thread.start()
        return task

    def get_task(self, task_id: str) -> dict | None:
        """Return a snapshot of the task, or *None* if not found."""
        with self._task_lock:
            task = self._tasks.get(task_id)
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

    def get_all_tasks(self) -> list[dict]:
        """Return snapshots of all tracked tasks."""
        with self._task_lock:
            return [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "status": t["status"],
                    "startedAt": t["startedAt"],
                    "finishedAt": t["finishedAt"],
                    "durationSec": t.get("durationSec"),
                    "failedStep": t.get("failedStep"),
                    "failedCode": t.get("failedCode"),
                }
                for t in self._tasks.values()
            ]

    def set_task_status(
        self,
        task_id: str,
        status: str,
        *,
        failed_step: str | None = None,
        failed_code: int | None = None,
    ) -> bool:
        """Update task status; returns *True* if the task was found."""
        history_row: dict | None = None
        audit_row: dict | None = None

        with self._task_lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            task["status"] = status
            if status in {"success", "failed"}:
                finished_epoch = time.time()
                task["finishedAt"] = self._now_text()
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
                    "error": self._extract_task_error(task.get("logs") or []),
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
            self.append_history(task_id, history_row)
        if audit_row is not None:
            self.append_audit(audit_row)
        return True

    def append_history(self, task_id: str, entry: dict) -> None:
        """Append an entry to the task history JSONL file."""
        _ = task_id  # kept in signature for API symmetry
        path = self._task_history_path()
        payload = json.dumps(entry, ensure_ascii=False)
        with self._history_lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(payload + "\n")

    def append_audit(self, detail: dict) -> None:
        """Append an entry to the audit log JSONL file."""
        path = self._task_audit_path()
        payload = dict(detail or {})
        payload.setdefault("eventAt", self._now_text())
        payload.setdefault("eventAtEpoch", round(time.time(), 3))
        payload.setdefault("pid", os.getpid())
        if self._config_service is not None:
            payload.setdefault(
                "profile",
                self._config_service.get_merged_config().get("OPENCLAW_PROFILE", "company"),
            )
        with self._audit_lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
