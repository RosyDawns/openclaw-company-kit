"""Lightweight HTTP router with path parameter support.

Pure standard-library implementation — no framework dependencies.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger("openclaw.router")


@dataclass
class Route:
    """A single registered route."""

    method: str
    path: str
    handler: Callable
    auth_required: bool = True
    group: str = ""


class Router:
    """Simple path-based HTTP router.

    Supports exact paths (``/api/config``) and path parameters
    (``/api/task/{id}``).  Parameter values are captured into the
    *path_params* dict returned by :meth:`match`.
    """

    def __init__(self) -> None:
        self._routes: list[Route] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add_route(
        self,
        method: str,
        path: str,
        handler: Callable,
        auth_required: bool = True,
        group: str = "",
    ) -> None:
        self._routes.append(
            Route(
                method=method.upper(),
                path=path,
                handler=handler,
                auth_required=auth_required,
                group=group,
            )
        )

    def route(self, method: str, path: str, auth_required: bool = True, group: str = ""):
        """Decorator form of :meth:`add_route`."""

        def decorator(func: Callable) -> Callable:
            self.add_route(method, path, func, auth_required, group)
            return func

        return decorator

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def match(self, method: str, path: str) -> tuple[Route, dict[str, str]] | None:
        """Return ``(route, path_params)`` for the first matching route, or *None*."""

        upper = method.upper()
        for route in self._routes:
            if route.method != upper:
                continue
            params = _match_path(route.path, path)
            if params is not None:
                return (route, params)
        return None

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def dispatch(
        self,
        handler_instance: Any,
        method: str,
        path: str,
        query_params: dict,
        body: dict | None,
    ) -> dict | None:
        """Match *method*/*path* and invoke the handler.

        *handler_instance* is the ``ControlHandler`` — used solely for
        ``_check_auth()``.

        Returns the handler's response dict (possibly containing a
        ``_status`` key for non-200 responses), or *None* when no route
        matched so the caller can fall through to legacy logic.

        Wraps every handler call in unified exception handling and logs
        request method, path, and elapsed time.
        """

        result = self.match(method, path)
        if result is None:
            return None

        route, path_params = result

        if route.auth_required and not handler_instance._check_auth():
            return {"ok": False, "error": "unauthorized", "_status": 401}

        merged: dict = dict(query_params or {})
        merged.update(path_params)

        t0 = time.monotonic()
        try:
            response = route.handler(merged, body)
        except Exception:
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.exception(
                "%s %s [%s] — unhandled exception (%.1fms)",
                method.upper(),
                path,
                route.group or "default",
                elapsed_ms,
            )
            return {"ok": False, "error": "internal server error", "_status": 500}

        elapsed_ms = (time.monotonic() - t0) * 1000
        status = response.get("_status", 200) if isinstance(response, dict) else 200
        logger.debug(
            "%s %s [%s] %d (%.1fms)",
            method.upper(),
            path,
            route.group or "default",
            status,
            elapsed_ms,
        )
        return response


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _match_path(pattern: str, path: str) -> dict[str, str] | None:
    """Match *path* against *pattern*, extracting ``{param}`` segments."""

    pat_parts = pattern.strip("/").split("/")
    path_parts = path.strip("/").split("/")

    if len(pat_parts) != len(path_parts):
        return None

    params: dict[str, str] = {}
    for pat_seg, path_seg in zip(pat_parts, path_parts):
        if pat_seg.startswith("{") and pat_seg.endswith("}"):
            params[pat_seg[1:-1]] = path_seg
        elif pat_seg != path_seg:
            return None

    return params
