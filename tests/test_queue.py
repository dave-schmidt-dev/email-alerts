from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

from email_alert import cli


def test_flush_sends_one_then_rate_limits_current(tmp_path: Path) -> None:
    state_dir = tmp_path
    env = {
        "EMAIL_ALERT_TEST_MODE": "true",
        "EMAIL_ALERT_STATE_DIR": str(state_dir),
        "GMAIL_USER": "sender@example.com",
        "EMAIL_ALERT_TO": "to@example.com",
        "EMAIL_ALERT_DEDUPE_SECONDS": "0",
        "EMAIL_ALERT_RATE_LIMIT_SECONDS": "60",
        "EMAIL_ALERT_LOG_LEVEL": "ERROR",
        "EMAIL_ALERT_ENV_FILE": str(state_dir / "empty.env"),
    }
    (state_dir / "empty.env").write_text("", encoding="utf-8")

    # First: send, then queue another due to rate limit.
    with (
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch("email_alert.app.time.time", return_value=3_000.0),
    ):
        assert cli.main(["subj1", "body1"]) == 0
    with (
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch("email_alert.app.time.time", return_value=3_000.1),
    ):
        assert cli.main(["subj2", "body2"]) == 0

    # After a minute: invocation should flush one queued item, then queue current.
    with (
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch("email_alert.app.time.time", return_value=3_060.2),
    ):
        assert cli.main(["subj3", "body3"]) == 0

    outbox_lines = (state_dir / "outbox.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(outbox_lines) >= 2

    queue_lines = (state_dir / "test_queue.jsonl").read_text(encoding="utf-8").splitlines()
    # At least one should remain (subj3 queued after flush).
    assert len(queue_lines) >= 1
