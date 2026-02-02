from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Callable

from email_alert.dedupe import message_id, record_sent, was_sent_recently
from email_alert.model import Config, Message, SendResult
from email_alert.queue import QueueEntry, enqueue, load_queue, save_queue
from email_alert.rate_limit import is_rate_limited, record_sent_time
from email_alert.state import state_lock


SendFn = Callable[[Config, Message], tuple[bool, str | None]]


def _paths(state_dir: Path) -> dict[str, Path]:
    return {
        "queue": state_dir / "queue.jsonl",
        "sent": state_dir / "sent.log",
        "rate": state_dir / "rate_limit.log",
        "outbox": state_dir / "outbox.jsonl",
    }


def _paths_for_config(config: Config) -> dict[str, Path]:
    p = _paths(config.state_dir)
    if config.test_mode and not config.e2e_test:
        return {
            "queue": config.state_dir / "test_queue.jsonl",
            "sent": config.state_dir / "test_sent.log",
            "rate": config.state_dir / "test_rate_limit.log",
            "outbox": p["outbox"],
        }
    return p


def paths_for_config(config: Config) -> dict[str, Path]:
    return _paths_for_config(config)


def _is_fatal_send_error(detail: str | None) -> bool:
    if not detail:
        return False
    d = detail.lower()
    return (
        "smtp auth failed" in d
        or "missing gmail_user" in d
        or "missing gmail_app_password" in d
    )


def generate_e2e_message(config: Config, *, to: str, from_addr: str) -> Message:
    nonce = uuid.uuid4().hex[:12]
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    subject = f"email-alert e2e test {ts} {nonce}"
    body = f"email-alert e2e test\n\nTimestamp: {ts}\nNonce: {nonce}\n"
    return Message(to=to, from_addr=from_addr, subject=subject, body=body)


def _attempt_send_or_queue(
    *,
    config: Config,
    message: Message,
    now: float,
    send_fn: SendFn,
    bypass_rate_limit: bool,
    queue_file: Path,
    sent_file: Path,
    rate_file: Path,
    log: Callable[[str], None],
) -> SendResult:
    mid = message_id(message)

    if was_sent_recently(
        sent_file=sent_file, msg_id=mid, now=now, window_seconds=config.dedupe_seconds
    ):
        log("dedupe: suppressed (sent recently)")
        return SendResult(ok=True, deduped=True)

    if not bypass_rate_limit:
        limited, remaining = is_rate_limited(
            rate_limit_file=rate_file, now=now, min_interval_seconds=config.rate_limit_seconds
        )
        if limited:
            entry = QueueEntry.from_message(msg_id=mid, message=message, now=now)
            enqueue(queue_file, entry)
            log(f"rate-limit: queued (remaining={remaining:.1f}s)")
            return SendResult(ok=True, queued=True, rate_limited=True)

    ok, detail = send_fn(config, message)
    if ok:
        record_sent_time(rate_limit_file=rate_file, now=now)
        record_sent(
            sent_file=sent_file, msg_id=mid, now=now, window_seconds=config.dedupe_seconds
        )
        log(f"sent: ok{(' detail=' + detail) if detail else ''}")
        return SendResult(ok=True, detail=detail)

    if config.e2e_test:
        log(f"sent: failed (e2e-test; not queued) detail={detail}")
        return SendResult(ok=False, queued=False, detail=detail)

    entry = QueueEntry.from_message(msg_id=mid, message=message, now=now)
    entry.attempts = 1
    entry.last_attempt = now
    entry.last_error = detail
    enqueue(queue_file, entry)
    log(f"sent: failed -> queued detail={detail}")
    return SendResult(ok=False, queued=True, detail=detail)


def flush_queue(
    *,
    config: Config,
    now: float,
    send_fn: SendFn,
    bypass_rate_limit: bool,
    queue_file: Path,
    sent_file: Path,
    rate_file: Path,
    log: Callable[[str], None],
) -> None:
    entries = load_queue(queue_file)
    if not entries:
        return

    log(f"flush: found {len(entries)} queued item(s)")

    remaining: list[QueueEntry] = []

    for idx, entry in enumerate(entries):
        msg = entry.to_message()
        mid = entry.id or message_id(msg)
        tail = entries[idx + 1 :]

        if was_sent_recently(
            sent_file=sent_file, msg_id=mid, now=now, window_seconds=config.dedupe_seconds
        ):
            log("flush: dropped deduped queued item")
            save_queue(queue_file, remaining + tail)
            continue

        if not bypass_rate_limit:
            limited, remaining_seconds = is_rate_limited(
                rate_limit_file=rate_file, now=now, min_interval_seconds=config.rate_limit_seconds
            )
            if limited:
                remaining.append(entry)
                remaining.extend(tail)
                log(f"flush: stopped due to rate-limit (remaining={remaining_seconds:.1f}s)")
                save_queue(queue_file, remaining)
                break

        ok, detail = send_fn(config, msg)
        if ok:
            record_sent_time(rate_limit_file=rate_file, now=now)
            record_sent(
                sent_file=sent_file, msg_id=mid, now=now, window_seconds=config.dedupe_seconds
            )
            log("flush: sent one queued item")
            save_queue(queue_file, remaining + tail)
            continue

        entry.attempts = int(entry.attempts or 0) + 1
        entry.last_attempt = now
        entry.last_error = detail
        remaining.append(entry)
        log(f"flush: send failed; kept in queue detail={detail}")
        save_queue(queue_file, remaining + tail)

        if _is_fatal_send_error(detail):
            remaining.extend(tail)
            log("flush: aborting due to fatal error (auth/creds)")
            save_queue(queue_file, remaining)
            break


def process_message(
    *,
    config: Config,
    message: Message,
    send_fn: SendFn,
    bypass_rate_limit: bool,
    log: Callable[[str], None],
) -> SendResult:
    now = time.time()
    p = _paths_for_config(config)

    with state_lock(config.state_dir):
        if not config.e2e_test:
            flush_queue(
                config=config,
                now=now,
                send_fn=send_fn,
                bypass_rate_limit=bypass_rate_limit,
                queue_file=p["queue"],
                sent_file=p["sent"],
                rate_file=p["rate"],
                log=log,
            )
        else:
            log("flush: skipped for e2e-test")

        log("send: attempting current message")
        return _attempt_send_or_queue(
            config=config,
            message=message,
            now=now,
            send_fn=send_fn,
            bypass_rate_limit=bypass_rate_limit,
            queue_file=p["queue"],
            sent_file=p["sent"],
            rate_file=p["rate"],
            log=log,
        )
