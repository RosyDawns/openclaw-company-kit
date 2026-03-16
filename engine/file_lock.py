from __future__ import annotations

import fcntl
import functools
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar, cast

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

LOCK_DIR = "/tmp/openclaw-company-kit"
TASK_HISTORY_LOCK = os.path.join(LOCK_DIR, "task-history.lock")
TASK_AUDIT_LOCK = os.path.join(LOCK_DIR, "task-audit.lock")
DASHBOARD_DATA_LOCK = os.path.join(LOCK_DIR, "dashboard-data.lock")
ENV_LOCK = os.path.join(LOCK_DIR, "env.lock")


class LockTimeoutError(Exception):
    """Raised when a lock cannot be acquired within the timeout period."""

    def __init__(
        self, lock_path: str | Path, timeout: float, message: str = ""
    ) -> None:
        self.lock_path = Path(lock_path)
        self.timeout = timeout
        self.message = message or (
            f"Failed to acquire lock {self.lock_path} within {self.timeout}s"
        )
        super().__init__(self.message)


class FileLock:
    """Process-level mutual-exclusion file lock using *fcntl.flock*.

    Supports context-manager protocol, reentrant acquisition from the same
    thread (reference-counted), and stale-lock detection via PID liveness
    checking and TTL expiry.
    """

    def __init__(
        self,
        lock_path: str,
        timeout: float = 10.0,
        ttl: float = 300.0,
    ) -> None:
        self._lock_path = Path(lock_path)
        self._timeout = timeout
        self._ttl = ttl

        self._fd: int | None = None
        self._owner_thread: int | None = None
        self._reentrant_depth: int = 0
        self._acquire_time: float | None = None

    @property
    def lock_path(self) -> Path:
        return self._lock_path

    @property
    def is_locked(self) -> bool:
        return self._fd is not None

    def _current_thread_id(self) -> int:
        return threading.current_thread().ident or 0

    # ------------------------------------------------------------------
    # Stale-lock detection
    # ------------------------------------------------------------------

    def _check_stale(self) -> bool:
        """Return *True* if a stale lock was detected and cleaned up.

        A lock is considered stale when either:
        * The recorded PID no longer refers to a running process.
        * The lock has been held longer than *ttl* seconds (wall-clock).
        """
        try:
            if not self._lock_path.exists():
                return False
            raw = self._lock_path.read_text()
            if not raw.strip():
                return False
            meta = json.loads(raw)
            pid = meta.get("pid")
            if pid is None:
                return False

            alive = True
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                alive = False
            except PermissionError:
                pass  # process exists but we lack signal permission

            if not alive:
                logger.warning(
                    "Stale lock detected on %s (pid=%s no longer alive). "
                    "Removing stale lock file.",
                    self._lock_path,
                    pid,
                )
                try:
                    self._lock_path.unlink()
                except OSError:
                    pass
                return True

            acquired_at = meta.get("acquired_at", 0.0)
            elapsed = time.time() - acquired_at
            if elapsed > self._ttl:
                logger.warning(
                    "Lock on %s held by pid=%s exceeded TTL (%.1fs > %.1fs). "
                    "Removing stale lock file.",
                    self._lock_path,
                    pid,
                    elapsed,
                    self._ttl,
                )
                try:
                    self._lock_path.unlink()
                except OSError:
                    pass
                return True

        except (json.JSONDecodeError, OSError):
            pass
        return False

    def _write_lock_meta(self) -> None:
        self._acquire_time = time.time()
        meta = {
            "pid": os.getpid(),
            "thread": self._current_thread_id(),
            "acquired_at": self._acquire_time,
        }
        try:
            self._lock_path.write_text(json.dumps(meta))
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Acquire / Release
    # ------------------------------------------------------------------

    def acquire(self) -> bool:
        """Acquire the exclusive lock.

        Returns *True* on success.  Raises :class:`LockTimeoutError` if the
        lock cannot be obtained within the configured *timeout*.
        """
        tid = self._current_thread_id()
        if self._owner_thread == tid and self._fd is not None:
            self._reentrant_depth += 1
            return True

        self._check_stale()

        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR)

        deadline = time.monotonic() + self._timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    os.close(fd)
                    raise LockTimeoutError(self._lock_path, self._timeout)
                time.sleep(0.1)

        self._fd = fd
        self._owner_thread = tid
        self._reentrant_depth = 1
        self._write_lock_meta()
        return True

    def release(self) -> None:
        """Release the lock.  Decrements reentrant depth; only truly releases
        when depth reaches zero."""
        if self._fd is None:
            return

        self._reentrant_depth -= 1
        if self._reentrant_depth > 0:
            return

        fd = self._fd
        self._fd = None
        self._owner_thread = None
        self._acquire_time = None

        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

        try:
            self._lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Context-manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


def with_file_lock(
    lock_path: str,
    timeout: float = 10.0,
) -> Callable[[F], F]:
    """Decorator that wraps the function body in a :class:`FileLock` context."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with FileLock(lock_path, timeout=timeout):
                return fn(*args, **kwargs)

        return cast(F, wrapper)

    return decorator
