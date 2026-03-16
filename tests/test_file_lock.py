from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from engine.file_lock import (
    DASHBOARD_DATA_LOCK,
    ENV_LOCK,
    LOCK_DIR,
    TASK_AUDIT_LOCK,
    TASK_HISTORY_LOCK,
    FileLock,
    LockTimeoutError,
    with_file_lock,
)


# ── LockTimeoutError ────────────────────────────────────────────────


class TestLockTimeoutError:
    def test_attributes(self) -> None:
        err = LockTimeoutError("/tmp/test.lock", 5.0)
        assert err.lock_path == Path("/tmp/test.lock")
        assert err.timeout == 5.0
        assert "test.lock" in str(err)

    def test_custom_message(self) -> None:
        err = LockTimeoutError("/tmp/test.lock", 5.0, message="custom")
        assert err.message == "custom"
        assert str(err) == "custom"


# ── Basic lock / release ─────────────────────────────────────────────


class TestBasicLockAndRelease:
    def test_basic_lock_and_release(self, tmp_path: Path) -> None:
        lock_file = str(tmp_path / "test.lock")
        lock = FileLock(lock_file)

        result = lock.acquire()
        assert result is True
        assert lock.is_locked
        assert lock.lock_path.exists()

        lock.release()
        assert not lock.is_locked

    def test_context_manager(self, tmp_path: Path) -> None:
        lock_file = str(tmp_path / "test.lock")
        with FileLock(lock_file) as fl:
            assert fl.is_locked
        assert not fl.is_locked

    def test_context_manager_releases_on_exception(self, tmp_path: Path) -> None:
        lock_file = str(tmp_path / "test.lock")
        fl = FileLock(lock_file)
        with pytest.raises(RuntimeError):
            with fl:
                raise RuntimeError("boom")
        assert not fl.is_locked

    def test_lock_path_property(self, tmp_path: Path) -> None:
        lock_file = str(tmp_path / "my.lock")
        lock = FileLock(lock_file)
        assert lock.lock_path == Path(lock_file)


# ── Timeout ──────────────────────────────────────────────────────────


class TestTimeout:
    def test_timeout_raises_error(self, tmp_path: Path) -> None:
        lock_file = str(tmp_path / "test.lock")

        lock_a = FileLock(lock_file, timeout=10.0)
        lock_a.acquire()
        try:
            lock_b = FileLock(lock_file, timeout=0.3)
            with pytest.raises(LockTimeoutError) as exc_info:
                lock_b.acquire()
            assert exc_info.value.timeout == 0.3
        finally:
            lock_a.release()

    def test_second_lock_succeeds_after_release(self, tmp_path: Path) -> None:
        lock_file = str(tmp_path / "test.lock")
        barrier = threading.Barrier(2, timeout=5)
        results: list[str] = []

        def hold_then_release() -> None:
            with FileLock(lock_file, timeout=5.0):
                results.append("first_acquired")
                barrier.wait()
                time.sleep(0.3)
            results.append("first_released")

        t = threading.Thread(target=hold_then_release)
        t.start()
        barrier.wait()
        with FileLock(lock_file, timeout=5.0):
            results.append("second_acquired")
        t.join(timeout=5)
        assert "first_acquired" in results
        assert "second_acquired" in results


# ── Stale lock cleanup ──────────────────────────────────────────────


class TestStaleLockCleanup:
    def test_stale_lock_cleanup(self, tmp_path: Path) -> None:
        """Lock file with a dead PID is detected as stale and cleaned up."""
        lock_file = str(tmp_path / "test.lock")
        lock_path = Path(lock_file)

        proc = subprocess.Popen(["true"])
        proc.wait()
        dead_pid = proc.pid

        lock_path.write_text(
            json.dumps({"pid": dead_pid, "thread": 0, "acquired_at": time.time()})
        )
        with FileLock(lock_file) as fl:
            assert fl.is_locked

    def test_stale_lock_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        lock_file = str(tmp_path / "test.lock")
        lock_path = Path(lock_file)

        proc = subprocess.Popen(["true"])
        proc.wait()
        dead_pid = proc.pid

        lock_path.write_text(
            json.dumps({"pid": dead_pid, "thread": 0, "acquired_at": time.time()})
        )
        with caplog.at_level("WARNING", logger="engine.file_lock"):
            with FileLock(lock_file):
                pass
        assert any("Stale lock" in r.message for r in caplog.records)

    def test_ttl_exceeded_cleanup(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Lock held past TTL by a live process is treated as stale."""
        lock_file = str(tmp_path / "test.lock")
        lock_path = Path(lock_file)

        lock_path.write_text(
            json.dumps(
                {"pid": os.getpid(), "thread": 0, "acquired_at": time.time() - 400}
            )
        )
        with caplog.at_level("WARNING", logger="engine.file_lock"):
            with FileLock(lock_file, ttl=300.0):
                pass
        assert any("TTL" in r.message for r in caplog.records)


# ── Reentrant ────────────────────────────────────────────────────────


class TestReentrant:
    def test_reentrant(self, tmp_path: Path) -> None:
        lock_file = str(tmp_path / "test.lock")
        lock = FileLock(lock_file)

        lock.acquire()
        lock.acquire()  # must not block
        assert lock.is_locked

        lock.release()  # depth 2 → 1
        assert lock.is_locked

        lock.release()  # depth 1 → 0
        assert not lock.is_locked

    def test_reentrant_context_managers(self, tmp_path: Path) -> None:
        lock_file = str(tmp_path / "test.lock")
        lock = FileLock(lock_file)
        with lock:
            with lock:
                assert lock.is_locked
            assert lock.is_locked
        assert not lock.is_locked


# ── Decorator ────────────────────────────────────────────────────────


class TestDecorator:
    def test_decorator(self, tmp_path: Path) -> None:
        lock_file = str(tmp_path / "test.lock")
        calls: list[int] = []

        @with_file_lock(lock_file)
        def write_data(value: int) -> int:
            calls.append(value)
            return value * 2

        result = write_data(42)
        assert result == 84
        assert calls == [42]

    def test_decorator_releases_on_exception(self, tmp_path: Path) -> None:
        lock_file = str(tmp_path / "test.lock")

        @with_file_lock(lock_file)
        def failing() -> None:
            raise ValueError("oops")

        with pytest.raises(ValueError):
            failing()

        with FileLock(lock_file, timeout=1.0):
            pass  # must not block — lock was released


# ── Lock dir auto-create ─────────────────────────────────────────────


class TestLockDirAutoCreate:
    def test_lock_dir_auto_create(self, tmp_path: Path) -> None:
        nested_dir = tmp_path / "nonexistent" / "sub" / "dir"
        lock_file = str(nested_dir / "test.lock")
        assert not nested_dir.exists()

        with FileLock(lock_file):
            assert nested_dir.exists()


# ── Constants ────────────────────────────────────────────────────────


class TestConstants:
    def test_lock_dir(self) -> None:
        assert LOCK_DIR == "/tmp/openclaw-company-kit"

    def test_lock_paths_under_lock_dir(self) -> None:
        for path in (TASK_HISTORY_LOCK, TASK_AUDIT_LOCK, DASHBOARD_DATA_LOCK, ENV_LOCK):
            assert path.startswith(LOCK_DIR)
            assert path.endswith(".lock")
