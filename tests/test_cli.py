from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from email_alert import cli


class _FakeStdin:
    def __init__(self, text: str, *, isatty: bool) -> None:
        self._text = text
        self._isatty = isatty
        self.read_calls = 0

    def isatty(self) -> bool:  # pragma: no cover
        return self._isatty

    def read(self) -> str:  # pragma: no cover
        self.read_calls += 1
        return self._text


class TestCli(unittest.TestCase):
    def test_flags_with_stdin_body_writes_outbox_in_test_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)

            env = {
                "EMAIL_ALERT_TEST_MODE": "true",
                "EMAIL_ALERT_STATE_DIR": str(state_dir),
                "GMAIL_USER": "sender@example.com",
                "EMAIL_ALERT_TO": "to@example.com",
                "EMAIL_ALERT_LOG_LEVEL": "ERROR",
                "EMAIL_ALERT_ENV_FILE": str(state_dir / "empty.env"),
            }
            (state_dir / "empty.env").write_text("", encoding="utf-8")

            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                cli.sys, "stdin", _FakeStdin("hello\n", isatty=False)
            ):
                rc = cli.main(["--subject", "subj"])
                self.assertEqual(rc, 0)

            outbox = state_dir / "outbox.jsonl"
            self.assertTrue(outbox.exists())
            lines = outbox.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            obj = json.loads(lines[0])
            self.assertEqual(obj["to"], "to@example.com")
            self.assertEqual(obj["from_addr"], "sender@example.com")
            self.assertEqual(obj["subject"], "subj")
            self.assertEqual(obj["body"], "hello\n")

    def test_positional_two_args(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
            env = {
                "EMAIL_ALERT_TEST_MODE": "true",
                "EMAIL_ALERT_STATE_DIR": str(state_dir),
                "GMAIL_USER": "sender@example.com",
                "EMAIL_ALERT_TO": "to@example.com",
                "EMAIL_ALERT_LOG_LEVEL": "ERROR",
                "EMAIL_ALERT_ENV_FILE": str(state_dir / "empty.env"),
            }
            (state_dir / "empty.env").write_text("", encoding="utf-8")
            with mock.patch.dict(os.environ, env, clear=True):
                rc = cli.main(["subj", "body"])
                self.assertEqual(rc, 0)

    def test_missing_to_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
            env = {
                "EMAIL_ALERT_TEST_MODE": "true",
                "EMAIL_ALERT_STATE_DIR": str(state_dir),
                "GMAIL_USER": "sender@example.com",
                "EMAIL_ALERT_LOG_LEVEL": "ERROR",
                "EMAIL_ALERT_ENV_FILE": str(state_dir / "empty.env"),
            }
            (state_dir / "empty.env").write_text("", encoding="utf-8")
            with mock.patch.dict(os.environ, env, clear=True):
                rc = cli.main(["subj", "body"])
                self.assertEqual(rc, 2)

    def test_stdin_not_read_if_body_provided(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
            env = {
                "EMAIL_ALERT_TEST_MODE": "true",
                "EMAIL_ALERT_STATE_DIR": str(state_dir),
                "GMAIL_USER": "sender@example.com",
                "EMAIL_ALERT_TO": "to@example.com",
                "EMAIL_ALERT_LOG_LEVEL": "ERROR",
                "EMAIL_ALERT_ENV_FILE": str(state_dir / "empty.env"),
            }
            (state_dir / "empty.env").write_text("", encoding="utf-8")
            fake_stdin = _FakeStdin("should-not-be-read\n", isatty=False)

            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
                cli.sys, "stdin", fake_stdin
            ):
                rc = cli.main(["--subject", "subj", "--body", "explicit"])
                self.assertEqual(rc, 0)
                self.assertEqual(fake_stdin.read_calls, 0)

    def test_test_and_e2e_mutually_exclusive(self) -> None:
        rc = cli.main(["--test", "--e2e-test"])
        self.assertEqual(rc, 2)

    def test_e2e_skips_flush_and_uses_smtp_sender(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
            env = {
                "EMAIL_ALERT_E2E_TEST": "true",
                "EMAIL_ALERT_STATE_DIR": str(state_dir),
                "EMAIL_ALERT_TO": "to@example.com",
                "GMAIL_USER": "sender@example.com",
                "GMAIL_APP_PASSWORD": "dummy",
                "EMAIL_ALERT_LOG_LEVEL": "ERROR",
                "EMAIL_ALERT_ENV_FILE": str(state_dir / "empty.env"),
            }
            (state_dir / "empty.env").write_text("", encoding="utf-8")

            with mock.patch.dict(os.environ, env, clear=True), mock.patch(
                "email_alert.app.flush_queue",
                side_effect=AssertionError("flush_queue should not be called in e2e"),
            ), mock.patch(
                "email_alert.cli.send_smtp", return_value=(True, None)
            ) as send_mock:
                rc = cli.main([])
                self.assertEqual(rc, 0)
                self.assertTrue(send_mock.called)

    def test_e2e_failure_exits_nonzero_and_does_not_queue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_dir = Path(td)
            env = {
                "EMAIL_ALERT_E2E_TEST": "true",
                "EMAIL_ALERT_STATE_DIR": str(state_dir),
                "EMAIL_ALERT_TO": "to@example.com",
                "GMAIL_USER": "sender@example.com",
                "GMAIL_APP_PASSWORD": "dummy",
                "EMAIL_ALERT_LOG_LEVEL": "ERROR",
                "EMAIL_ALERT_ENV_FILE": str(state_dir / "empty.env"),
            }
            (state_dir / "empty.env").write_text("", encoding="utf-8")

            with mock.patch.dict(os.environ, env, clear=True), mock.patch(
                "email_alert.cli.send_smtp", return_value=(False, "nope")
            ):
                rc = cli.main([])
                self.assertEqual(rc, 1)

            self.assertFalse((state_dir / "queue.jsonl").exists())
