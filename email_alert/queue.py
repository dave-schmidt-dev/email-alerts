from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from email_alert.model import Message
from email_alert.state import append_jsonl, atomic_write_text, read_text


@dataclass
class QueueEntry:
    id: str
    to: str
    from_addr: str
    subject: str
    body: str
    enqueued_at: float
    attempts: int = 0
    last_attempt: float | None = None
    last_error: str | None = None

    @classmethod
    def from_message(cls, *, msg_id: str, message: Message, now: float) -> QueueEntry:
        return cls(
            id=msg_id,
            to=message.to,
            from_addr=message.from_addr,
            subject=message.subject,
            body=message.body,
            enqueued_at=now,
        )

    def to_message(self) -> Message:
        return Message(
            to=self.to,
            from_addr=self.from_addr,
            subject=self.subject,
            body=self.body,
        )


def load_queue(queue_file: Path) -> list[QueueEntry]:
    raw = read_text(queue_file)
    entries: list[QueueEntry] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            entries.append(
                QueueEntry(
                    id=str(obj.get("id") or ""),
                    to=str(obj.get("to") or ""),
                    from_addr=str(obj.get("from_addr") or ""),
                    subject=str(obj.get("subject") or ""),
                    body=str(obj.get("body") or ""),
                    enqueued_at=float(obj.get("enqueued_at") or 0.0),
                    attempts=int(obj.get("attempts") or 0),
                    last_attempt=(
                        float(obj["last_attempt"]) if obj.get("last_attempt") is not None else None
                    ),
                    last_error=(
                        str(obj["last_error"]) if obj.get("last_error") is not None else None
                    ),
                )
            )
        except Exception:
            continue
    return entries


def save_queue(queue_file: Path, entries: Iterable[QueueEntry]) -> None:
    lines = [json.dumps(asdict(e), separators=(",", ":"), ensure_ascii=False) for e in entries]
    atomic_write_text(queue_file, ("\n".join(lines) + ("\n" if lines else "")))


def enqueue(queue_file: Path, entry: QueueEntry) -> None:
    append_jsonl(queue_file, asdict(entry))
