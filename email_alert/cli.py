from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from email_alert.app import generate_e2e_message, paths_for_config, process_message
from email_alert.config import load_config
from email_alert.dedupe import message_id
from email_alert.logging_utils import body_fingerprint, configure_logging
from email_alert.model import Message
from email_alert.queue import QueueEntry, enqueue
from email_alert.senders import send_smtp, send_test
from email_alert.state import state_lock


def _read_stdin_if_piped() -> str | None:
    if sys.stdin is None:
        return None
    if sys.stdin.isatty():
        return None
    return sys.stdin.read()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="email-alert", add_help=True)

    parser.add_argument("--to", dest="to", default=None)
    parser.add_argument("--from", dest="from_addr", default=None)
    parser.add_argument("--subject", dest="subject", default=None)
    parser.add_argument("--body", dest="body", default=None)

    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--test", action="store_true", default=False)
    parser.add_argument("--e2e-test", action="store_true", default=False)

    parser.add_argument("--log-level", dest="log_level", default=None)
    parser.add_argument("--log-file", dest="log_file", default=None)

    parser.add_argument("positional", nargs="*")

    return parser


def _parse_positional(
    positional: list[str],
) -> tuple[str | None, str | None, str | None, str | None]:
    if not positional:
        return (None, None, None, None)

    if len(positional) == 2:
        subject, body = positional
        return (None, None, subject, body)
    if len(positional) == 3:
        to, subject, body = positional
        return (to, None, subject, body)
    if len(positional) == 4:
        to, from_addr, subject, body = positional
        return (to, from_addr, subject, body)

    raise ValueError("Invalid positional usage. Expected 2-4 args: [to] [from] subject body")


def _normalize_message(
    *,
    config_default_to: str,
    config_default_from: str | None,
    to: str | None,
    from_addr: str | None,
    subject: str | None,
    body: str | None,
) -> Message:
    resolved_to = (to or config_default_to or "").strip()
    resolved_from = (from_addr or config_default_from or "").strip()
    resolved_subject = (subject or "").strip()
    resolved_body = body if body is not None else ""

    if not resolved_to:
        raise ValueError("Missing recipient (--to or EMAIL_ALERT_TO).")
    if not resolved_from:
        raise ValueError("Missing sender (--from, EMAIL_ALERT_FROM, or GMAIL_USER).")
    if not resolved_subject:
        raise ValueError("Missing subject (--subject or positional).")
    if resolved_body == "":
        raise ValueError("Missing body (--body, positional, or stdin).")

    return Message(
        to=resolved_to,
        from_addr=resolved_from,
        subject=resolved_subject,
        body=resolved_body,
    )


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    repo_root = Path(__file__).resolve().parents[1]
    parser = build_parser()

    config = None
    logger = None
    message: Message | None = None

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2

    if args.test and args.e2e_test:
        print("input error: --test and --e2e-test are mutually exclusive", file=sys.stderr)
        return 2

    config = load_config(
        repo_root=repo_root,
        log_level_override=args.log_level,
        log_file_override=args.log_file,
        test_mode_override=bool(args.test) if args.test else None,
        e2e_test_override=bool(args.e2e_test) if args.e2e_test else None,
    )
    logger = configure_logging(config=config)

    if config.test_mode and config.e2e_test:
        logger.error("input error: test mode and e2e-test cannot both be enabled")
        return 2

    try:
        p_to, p_from, p_subject, p_body = _parse_positional(list(args.positional))
        to = args.to or p_to
        from_addr = args.from_addr or p_from or config.default_from or config.gmail_user
        subject = args.subject or p_subject

        stdin_body = _read_stdin_if_piped() if (args.body is None and p_body is None) else None
        body = args.body or p_body or stdin_body

        if config.e2e_test:
            partial = _normalize_message(
                config_default_to=config.default_to,
                config_default_from=(config.default_from or config.gmail_user),
                to=to,
                from_addr=from_addr,
                subject="e2e",  # placeholder; replaced below
                body="e2e",  # placeholder; replaced below
            )
            message = generate_e2e_message(
                config,
                to=partial.to,
                from_addr=partial.from_addr,
            )
        else:
            message = _normalize_message(
                config_default_to=config.default_to,
                config_default_from=(config.default_from or config.gmail_user),
                to=to,
                from_addr=from_addr,
                subject=subject,
                body=body,
            )

        body_len, body_hash = body_fingerprint(message.body)
        logger.info(
            "parsed to=%s from=%s subject=%s body_len=%s body_sha256=%s",
            message.to,
            message.from_addr,
            message.subject,
            body_len,
            body_hash,
        )

        if args.dry_run:
            logger.info("dry-run: no send/queue performed")
            return 0

        send_fn = send_test if (config.test_mode and not config.e2e_test) else send_smtp
        bypass_rate_limit = bool(config.e2e_test and config.e2e_bypass_rate_limit)

        result = process_message(
            config=config,
            message=message,
            send_fn=send_fn,
            bypass_rate_limit=bypass_rate_limit,
            log=lambda msg: logger.info("%s", msg),
        )

        if config.e2e_test and not result.ok:
            logger.error("e2e-test failed detail=%s", result.detail)
            return 1

        if result.ok:
            return 0
        if result.queued and config.on_fail == "queue_ok":
            logger.error("send failed (queued); on_fail=queue_ok detail=%s", result.detail)
            return 0

        logger.error("send failed detail=%s", result.detail)
        return 1
    except ValueError as e:
        logger.error("input error: %s", e)
        return 2
    except Exception as e:
        logger.exception("unexpected error")

        queued = False
        if config is not None and message is not None and not config.e2e_test:
            try:
                with state_lock(config.state_dir):
                    queue_file = paths_for_config(config)["queue"]
                    mid = message_id(message)
                    enqueue(
                        queue_file,
                        QueueEntry.from_message(msg_id=mid, message=message, now=time.time()),
                    )
                queued = True
                logger.error("queued message due to exception: %s", e)
            except Exception:
                logger.exception("failed to queue message after exception")

        if queued and config is not None and config.on_fail == "queue_ok":
            return 0
        return 1
