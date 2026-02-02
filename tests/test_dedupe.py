from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from email_alert import cli


class TestDedupe(unittest.TestCase):
    def test_duplicate_within_window_suppressed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
            env = {
                "EMAIL_ALERT_TEST_MODE": "true",
                "EMAIL_ALERT_STATE_DIR": str(state_dir),
                "GMAIL_USER": "sender@example.com",
                "EMAIL_ALERT_TO": "to@example.com",
                "EMAIL_ALERT_DEDUPE_SECONDS": "60",
                "EMAIL_ALERT_RATE_LIMIT_SECONDS": "0",
                "EMAIL_ALERT_LOG_LEVEL": "ERROR",
                "EMAIL_ALERT_ENV_FILE": str(state_dir / "empty.env"),
            }
            (state_dir / "empty.env").write_text("", encoding="utf-8")

            with mock.patch.dict(os.environ, env, clear=True), mock.patch(
                "email_alert.app.time.time", return_value=1_000.0
            ):
                self.assertEqual(cli.main(["subj", "body"]), 0)

            with mock.patch.dict(os.environ, env, clear=True), mock.patch(
                "email_alert.app.time.time", return_value=1_000.5
            ):
                self.assertEqual(cli.main(["subj", "body"]), 0)

            outbox = state_dir / "outbox.jsonl"
            lines = outbox.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            obj = json.loads(lines[0])
            self.assertEqual(obj["subject"], "subj")


