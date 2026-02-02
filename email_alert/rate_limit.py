from __future__ import annotations

from pathlib import Path

from email_alert.state import atomic_write_text, read_text


def read_last_sent_ts(rate_limit_file: Path) -> float | None:
    raw = read_text(rate_limit_file).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def is_rate_limited(
    *, rate_limit_file: Path, now: float, min_interval_seconds: int
) -> tuple[bool, float]:
    if min_interval_seconds <= 0:
        return (False, 0.0)
    last = read_last_sent_ts(rate_limit_file)
    if last is None:
        return (False, 0.0)
    remaining = (last + float(min_interval_seconds)) - now
    if remaining > 0:
        return (True, remaining)
    return (False, 0.0)


def record_sent_time(*, rate_limit_file: Path, now: float) -> None:
    atomic_write_text(rate_limit_file, f"{now:.6f}\n")

