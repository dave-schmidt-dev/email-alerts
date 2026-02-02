from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from email_alert import cli


class TestRateLimit(unittest.TestCase):
    def test_second_message_queued_when_rate_limited(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
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

            with mock.patch.dict(os.environ, env, clear=True), mock.patch(
                "email_alert.app.time.time", return_value=2_000.0
            ):
                self.assertEqual(cli.main(["subj1", "body1"]), 0)

            with mock.patch.dict(os.environ, env, clear=True), mock.patch(
                "email_alert.app.time.time", return_value=2_000.1
            ):
                self.assertEqual(cli.main(["subj2", "body2"]), 0)

            queue_file = state_dir / "test_queue.jsonl"
            self.assertTrue(queue_file.exists())
            self.assertGreaterEqual(len(queue_file.read_text(encoding="utf-8").splitlines()), 1)

