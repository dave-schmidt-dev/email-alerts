from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from email_alert.model import Message
from email_alert.state import append_jsonl, atomic_write_text, read_text


def message_id(message: Message) -> str:
    to_norm = message.to.strip().lower()
    from_norm = message.from_addr.strip().lower()
    subject_norm = message.subject.strip()
    body_norm = message.body.replace("\r\n", "\n")

    payload = "\0".join([to_norm, from_norm, subject_norm, body_norm]).encode(
        "utf-8", errors="replace"
    )
    return hashlib.sha256(payload).hexdigest()


def _iter_sent_entries(sent_file: Path) -> Iterable[tuple[float, str]]:
    raw = read_text(sent_file)
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            ts = float(obj.get("ts"))
            mid = str(obj.get("id"))
        except Exception:
            continue
        if not mid:
            continue
        yield (ts, mid)


def was_sent_recently(*, sent_file: Path, msg_id: str, now: float, window_seconds: int) -> bool:
    if window_seconds <= 0:
        return False
    cutoff = now - window_seconds
    for ts, mid in _iter_sent_entries(sent_file):
        if ts >= cutoff and mid == msg_id:
            return True
    return False


def record_sent(*, sent_file: Path, msg_id: str, now: float, window_seconds: int) -> None:
    append_jsonl(sent_file, {"ts": now, "id": msg_id})
    prune_sent_file(sent_file=sent_file, now=now, window_seconds=window_seconds)


def prune_sent_file(*, sent_file: Path, now: float, window_seconds: int) -> None:
    if window_seconds <= 0:
        atomic_write_text(sent_file, "")
        return
    cutoff = now - window_seconds
    keep: list[dict[str, object]] = []
    for ts, mid in _iter_sent_entries(sent_file):
        if ts >= cutoff:
            keep.append({"ts": ts, "id": mid})
    keep.sort(key=lambda x: float(x["ts"]))
    atomic_write_text(
        sent_file,
        "\n".join(json.dumps(x, separators=(",", ":"), ensure_ascii=False) for x in keep)
        + ("\n" if keep else ""),
    )

