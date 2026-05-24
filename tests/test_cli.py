from __future__ import annotations

import json
import os
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


def test_flags_with_stdin_body_writes_outbox_in_test_mode(tmp_path: Path) -> None:
    state_dir = tmp_path
    env = {
        "EMAIL_ALERT_TEST_MODE": "true",
        "EMAIL_ALERT_STATE_DIR": str(state_dir),
        "GMAIL_USER": "sender@example.com",
        "EMAIL_ALERT_TO": "to@example.com",
        "EMAIL_ALERT_LOG_LEVEL": "ERROR",
        "EMAIL_ALERT_ENV_FILE": str(state_dir / "empty.env"),
    }
    (state_dir / "empty.env").write_text("", encoding="utf-8")

    with (
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch.object(cli.sys, "stdin", _FakeStdin("hello\n", isatty=False)),
    ):
        assert cli.main(["--subject", "subj"]) == 0

    outbox = state_dir / "outbox.jsonl"
    assert outbox.exists()
    lines = outbox.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["to"] == "to@example.com"
    assert obj["from_addr"] == "sender@example.com"
    assert obj["subject"] == "subj"
    assert obj["body"] == "hello\n"


def test_positional_two_args(tmp_path: Path) -> None:
    state_dir = tmp_path
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
        assert cli.main(["subj", "body"]) == 0


def test_missing_to_is_error(tmp_path: Path) -> None:
    state_dir = tmp_path
    env = {
        "EMAIL_ALERT_TEST_MODE": "true",
        "EMAIL_ALERT_STATE_DIR": str(state_dir),
        "GMAIL_USER": "sender@example.com",
        "EMAIL_ALERT_LOG_LEVEL": "ERROR",
        "EMAIL_ALERT_ENV_FILE": str(state_dir / "empty.env"),
    }
    (state_dir / "empty.env").write_text("", encoding="utf-8")
    with mock.patch.dict(os.environ, env, clear=True):
        assert cli.main(["subj", "body"]) == 2


def test_stdin_not_read_if_body_provided(tmp_path: Path) -> None:
    state_dir = tmp_path
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

    with (
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch.object(cli.sys, "stdin", fake_stdin),
    ):
        assert cli.main(["--subject", "subj", "--body", "explicit"]) == 0
        assert fake_stdin.read_calls == 0


def test_test_and_e2e_mutually_exclusive() -> None:
    assert cli.main(["--test", "--e2e-test"]) == 2


def test_e2e_skips_flush_and_uses_smtp_sender(tmp_path: Path) -> None:
    state_dir = tmp_path
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

    with (
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch.object(cli.sys, "stdin", _FakeStdin("", isatty=True)),
        mock.patch(
            "email_alert.app.flush_queue",
            side_effect=AssertionError("flush_queue should not be called in e2e"),
        ),
        mock.patch("email_alert.cli.send_smtp", return_value=(True, None)) as send_mock,
    ):
        assert cli.main([]) == 0
        assert send_mock.called


def test_e2e_failure_exits_nonzero_and_does_not_queue(tmp_path: Path) -> None:
    state_dir = tmp_path
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

    with (
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch.object(cli.sys, "stdin", _FakeStdin("", isatty=True)),
        mock.patch("email_alert.cli.send_smtp", return_value=(False, "nope")),
    ):
        assert cli.main([]) == 1

    assert not (state_dir / "queue.jsonl").exists()
