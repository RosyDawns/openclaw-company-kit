"""Health-check and service status service.

Extracted from ``scripts/control_server.py`` — preflight checks, service
status collection and path resolution live here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.services.config_service import ConfigService

from server.services import profile_dir


class HealthService:
    """Pure-Python health / status service (no HTTP dependency)."""

    def __init__(
        self,
        root_dir: Path | None = None,
        config_service: ConfigService | None = None,
        console_ui_dist: Path | None = None,
    ) -> None:
        self._root_dir = root_dir or Path(__file__).resolve().parents[2]
        self._config_service = config_service  # TODO: decouple from global state
        self._console_ui_dist = console_ui_dist or (
            self._root_dir / "frontend" / "console-vue" / "dist"
        )

    def _get_merged_config(self) -> dict[str, str]:
        if self._config_service is not None:
            return self._config_service.get_merged_config()
        return {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def preflight_check(self, profile_dir_override: str | None = None) -> dict:
        """Run environment pre-flight checks and return the results."""
        _ = profile_dir_override
        config = self._get_merged_config()
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

        required_vars = ["GROUP_ID", "FEISHU_AI_APP_ID", "FEISHU_AI_APP_SECRET"]
        for var in required_vars:
            checks.append({"name": var, "ok": bool(config.get(var, "").strip()), "type": "env"})

        pdir = profile_dir(config)
        oc_config_path = pdir / "openclaw.json"
        source_path = config.get("SOURCE_OPENCLAW_CONFIG", "").strip()
        oc_ok = oc_config_path.exists()
        if not oc_ok and source_path:
            oc_ok = Path(source_path).expanduser().exists()
        checks.append({"name": "openclaw_config", "ok": oc_ok, "type": "config", "blocking": False})

        all_passed = all(c["ok"] for c in checks if c.get("blocking", True))
        return {"ok": True, "checks": checks, "allPassed": all_passed}

    def get_service_status(self) -> dict:
        """Collect running-service status (PID files, liveness probes)."""
        config = self._get_merged_config()
        pdir = profile_dir(config)
        run_dir = pdir / "run"
        service_names = ["dashboard-refresh-loop", "issue-sync-loop"]
        services: list[dict] = []

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
            "profileDir": str(pdir),
            "runDir": str(run_dir),
            "services": services,
        }

    def get_dashboard_dir(self) -> str:
        """Resolve the dashboard directory path."""
        config = self._get_merged_config()
        deployed = profile_dir(config) / "workspace" / "rd-dashboard"
        if deployed.is_dir():
            return str(deployed)
        return str(self._root_dir / "dashboard" / "rd-dashboard")

    def get_console_ui_dir(self) -> str | None:
        """Resolve the console UI dist directory, or *None* if not built."""
        if self._console_ui_dist.is_dir() and (self._console_ui_dist / "index.html").is_file():
            return str(self._console_ui_dist)
        return None
