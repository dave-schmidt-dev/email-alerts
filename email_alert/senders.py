from __future__ import annotations

from datetime import datetime, timezone

from email_alert.model import Config, Message
from email_alert.state import append_jsonl
from email_alert.smtp_gmail import send_via_gmail_smtp


def send_test(config: Config, message: Message) -> tuple[bool, str | None]:
    outbox_file = config.state_dir / "outbox.jsonl"
    append_jsonl(
        outbox_file,
        {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "to": message.to,
            "from_addr": message.from_addr,
            "subject": message.subject,
            "body": message.body,
        },
    )
    return (True, "test-mode: wrote to outbox.jsonl")


def send_smtp(config: Config, message: Message) -> tuple[bool, str | None]:
    return send_via_gmail_smtp(config, message)
