"""Service layer for the control server.

Business logic extracted from ``scripts/control_server.py`` so that
handlers (and future callers) operate through a clean, HTTP-agnostic API.
"""

from __future__ import annotations

from pathlib import Path

from server.data.path_resolver import PathResolver


def profile_dir(config: dict[str, str]) -> Path:
    """Resolve the OpenClaw profile directory from a config dict.

    Delegates to :meth:`PathResolver.profile_dir_from_config`.
    Kept here for backward compatibility.
    """
    return PathResolver.profile_dir_from_config(config)
