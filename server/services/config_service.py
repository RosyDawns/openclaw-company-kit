"""Configuration management service.

Extracted from ``scripts/control_server.py`` — all .env reading, writing,
normalisation and merging logic lives here.

TODO(RB-07): Migrate raw .env I/O (parse_env / write_env) to
``server.data.env_store.EnvStore`` so this service becomes a pure
business-logic layer with no direct file-system access.
"""

from __future__ import annotations

import re
from pathlib import Path


class ConfigService:
    """Pure-Python configuration service (no HTTP dependency)."""

    DEFAULT_CONFIG: dict[str, str] = {
        "OPENCLAW_PROFILE": "company",
        "SOURCE_OPENCLAW_CONFIG": "~/.openclaw/openclaw.json",
        "COMPANY_NAME": "OpenClaw Company",
        "PROJECT_PATH": "/path/to/your-project",
        "PROJECT_REPO": "your-org/your-repo",
        "WORKFLOW_TEMPLATE": "default",
        "GROUP_ID": "",
        "FEISHU_HOT_ACCOUNT_ID": "",
        "FEISHU_HOT_BOT_NAME": "",
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

    ENV_KEY_ORDER: list[str] = [
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

    _KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

    def __init__(
        self,
        root_dir: Path | None = None,
        env_file: Path | None = None,
        server_port: int = 8788,
    ) -> None:
        self._root_dir = root_dir or Path(__file__).resolve().parents[2]
        self._env_file = env_file or (self._root_dir / ".env")
        self._server_port = server_port

    @property
    def env_file(self) -> Path:
        return self._env_file

    @property
    def root_dir(self) -> Path:
        return self._root_dir

    @property
    def server_port(self) -> int:
        return self._server_port

    @server_port.setter
    def server_port(self, value: int) -> None:
        self._server_port = value

    # ------------------------------------------------------------------
    # Low-level helpers (extracted from control_server.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _shell_quote(value: str) -> str:
        return "'" + str(value).replace("'", "'\"'\"'") + "'"

    @classmethod
    def parse_env(cls, path: Path) -> tuple[dict[str, str], list[str]]:
        """Parse a ``.env`` file into ``(data, key_order)``."""
        data: dict[str, str] = {}
        order: list[str] = []
        if not path.exists():
            return data, order

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in raw_line:
                continue

            key, value = raw_line.split("=", 1)
            key = key.strip()
            if not cls._KEY_RE.match(key):
                continue

            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] == "'":
                value = value[1:-1].replace("'\"'\"'", "'")
            elif len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]

            data[key] = value
            order.append(key)

        return data, order

    def normalize(self, input_cfg: dict, current: dict[str, str] | None = None) -> dict[str, str]:
        """Normalise *input_cfg* against current (or merged) config."""
        base = dict(current or self.get_merged_config())
        for key, value in input_cfg.items():
            if key not in self.DEFAULT_CONFIG:
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

    def write_env(self, config: dict[str, str], previous_order: list[str], previous_data: dict[str, str]) -> None:
        """Write a full ``.env`` file from *config*, preserving extra keys."""
        lines = [
            "# -------------------------------",
            "# OpenClaw Company Kit",
            "# Generated by scripts/control_server.py",
            "# -------------------------------",
            "",
        ]

        emitted: set[str] = set()

        def emit_key(key: str) -> None:
            lines.append(f"{key}={self._shell_quote(config.get(key, ''))}")
            emitted.add(key)

        for key in self.ENV_KEY_ORDER:
            emit_key(key)

        extra_keys: list[str] = []
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
                lines.append(f"{key}={self._shell_quote(previous_data.get(key, ''))}")

        self._env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def get_merged_config(self) -> dict[str, str]:
        """Return the full merged config (defaults → .env overrides)."""
        cfg = dict(self.DEFAULT_CONFIG)
        cfg["DASHBOARD_PORT"] = str(self._server_port)
        existing, _ = self.parse_env(self._env_file)
        cfg.update(existing)
        return cfg

    # ------------------------------------------------------------------
    # High-level public API
    # ------------------------------------------------------------------

    def get_config(self, profile_dir: str | None = None) -> dict:
        """Read ``.env`` and return the merged configuration dict."""
        _ = profile_dir  # reserved for future per-profile support
        return self.get_merged_config()

    def save_config(self, payload: dict, profile_dir: str | None = None) -> dict:
        """Save *payload* to ``.env`` and return ``{"ok": True, "config": …}``."""
        _ = profile_dir
        cfg_payload = payload.get("config", payload)
        if not isinstance(cfg_payload, dict):
            raise ValueError("config must be object")
        old_data, old_order = self.parse_env(self._env_file)
        cfg = self.normalize(cfg_payload)
        self.write_env(cfg, old_order, old_data)
        return {"ok": True, "config": cfg}

    def apply_config(self, payload: dict, profile_dir: str | None = None) -> dict:
        """Save config (same as :meth:`save_config`).

        The caller is responsible for creating a task to perform the
        actual service reload (stop → onboard → install → start → healthcheck).
        """
        return self.save_config(payload, profile_dir=profile_dir)
