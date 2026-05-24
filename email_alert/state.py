from __future__ import annotations

import contextlib
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(path, 0o700)


def ensure_private_file(path: Path) -> None:
    try:
        if path.exists():
            os.chmod(path, 0o600)
    except OSError:
        pass


def atomic_write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with contextlib.suppress(OSError):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        ensure_private_file(path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_path)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def append_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    try:
        with contextlib.suppress(OSError):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
    finally:
        ensure_private_file(path)


def append_jsonl(path: Path, obj: object) -> None:
    append_text(path, json.dumps(obj, separators=(",", ":"), ensure_ascii=False) + "\n")


@contextmanager
def state_lock(state_dir: Path) -> Iterator[None]:
    ensure_dir(state_dir)
    lock_path = state_dir / ".lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
