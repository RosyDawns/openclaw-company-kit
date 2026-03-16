"""Static file serving for dashboard and console UI."""

from __future__ import annotations

import mimetypes
from pathlib import Path


class StaticFileServer:
    """Serves files from the dashboard and console-UI build directories.

    ``serve()`` returns ``(body_bytes, content_type, status_code)`` so
    the caller can write the HTTP response without knowing about the
    filesystem layout.
    """

    def __init__(self, dashboard_dir: str, console_ui_dir: str) -> None:
        self._dashboard_dir = Path(dashboard_dir)
        self._console_ui_dir = Path(console_ui_dir)

    @property
    def console_ui_available(self) -> bool:
        dist = self._console_ui_dir
        return dist.is_dir() and (dist / "index.html").is_file()

    def serve(self, path: str) -> tuple[bytes, str, int]:
        """Route *path* to the correct static directory and return the file."""

        if path.startswith("/dashboard"):
            return self._serve_dashboard(path)
        if path.startswith("/ui"):
            return self._serve_console_ui(path)
        return b"Not Found", "text/plain; charset=utf-8", 404

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def _serve_dashboard(self, path: str) -> tuple[bytes, str, int]:
        base = self._dashboard_dir

        if path in {"/dashboard", "/dashboard/"}:
            return _read_file(base / "index.html")

        rel = path[len("/dashboard/"):]
        file_path = (base / Path(rel)).resolve()
        base_resolved = base.resolve()

        if base_resolved not in file_path.parents and file_path != base_resolved:
            return b"Forbidden", "text/plain; charset=utf-8", 403

        return _read_file(file_path)

    # ------------------------------------------------------------------
    # Console UI (Vue SPA)
    # ------------------------------------------------------------------

    def _serve_console_ui(self, path: str) -> tuple[bytes, str, int]:
        dist = self._console_ui_dir

        if not dist.is_dir() or not (dist / "index.html").is_file():
            msg = (
                "Console UI build not found. "
                "Run: cd frontend/console-vue && npm install && npm run build"
            )
            return msg.encode("utf-8"), "text/plain; charset=utf-8", 404

        if path in {"/ui", "/ui/"}:
            return _read_file(dist / "index.html")

        rel = path[len("/ui/"):] if path.startswith("/ui/") else ""
        rel_path = Path(rel)

        # History-mode fallback: extensionless paths serve index.html
        if rel and "." not in rel_path.name:
            return _read_file(dist / "index.html")

        file_path = (dist / rel_path).resolve()
        dist_resolved = dist.resolve()

        if dist_resolved not in file_path.parents and file_path != dist_resolved:
            return b"Forbidden", "text/plain; charset=utf-8", 403

        return _read_file(file_path)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _read_file(file_path: Path) -> tuple[bytes, str, int]:
    """Read *file_path* and return ``(bytes, content_type, status)``."""

    if not file_path.exists() or not file_path.is_file():
        return b"Not Found", "text/plain; charset=utf-8", 404

    ctype, _ = mimetypes.guess_type(str(file_path))
    content_type = ctype or "application/octet-stream"
    return file_path.read_bytes(), content_type, 200
