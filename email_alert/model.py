from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

OnFailMode = Literal["queue_ok", "queue_fail"]


@dataclass(frozen=True)
class Message:
    to: str
    from_addr: str
    subject: str
    body: str


@dataclass(frozen=True)
class Config:
    gmail_user: str | None
    gmail_app_password: str | None

    default_to: str
    default_from: str | None

    state_dir: Path

    on_fail: OnFailMode
    rate_limit_seconds: int
    dedupe_seconds: int

    log_level: str
    log_file: Path
    log_max_bytes: int
    log_backup_count: int

    test_mode: bool
    e2e_test: bool
    e2e_bypass_rate_limit: bool

    smtp_host: str
    smtp_ports: tuple[int, ...]
    smtp_timeout_seconds: int


@dataclass(frozen=True)
class SendResult:
    ok: bool
    queued: bool = False
    deduped: bool = False
    rate_limited: bool = False
    detail: str | None = None
