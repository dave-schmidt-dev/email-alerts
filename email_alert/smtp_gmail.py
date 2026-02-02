from __future__ import annotations

import json
import logging
import smtplib
import ssl
import time
from email.message import EmailMessage
from pathlib import Path

from email_alert.model import Config, Message
from email_alert.state import atomic_write_text, read_text


_SMTP_STATE_FILENAME = "smtp_state.json"
_AVOID_TIMEOUT_SECONDS = 3600


def _smtp_state_path(config: Config) -> Path:
    return config.state_dir / _SMTP_STATE_FILENAME


def _load_smtp_state(config: Config) -> dict[str, object]:
    try:
        raw = read_text(_smtp_state_path(config)).strip()
        if not raw:
            return {}
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _save_smtp_state(config: Config, state: dict[str, object]) -> None:
    atomic_write_text(
        _smtp_state_path(config),
        json.dumps(state, separators=(",", ":"), ensure_ascii=False) + "\n",
    )


def _is_timeout_error(err: BaseException) -> bool:
    if isinstance(err, TimeoutError):
        return True
    msg = str(err).lower()
    return "timed out" in msg or "timeout" in msg


def _compute_ports_to_try(config: Config, now: float) -> list[int]:
    ports = [int(p) for p in config.smtp_ports]
    state = _load_smtp_state(config)

    preferred = state.get("preferred_port")
    if isinstance(preferred, int) and preferred in ports:
        ports = [preferred] + [p for p in ports if p != preferred]

    avoid = state.get("avoid_ports") if isinstance(state.get("avoid_ports"), dict) else {}
    if isinstance(avoid, dict):
        filtered: list[int] = []
        for p in ports:
            ts = avoid.get(str(p))
            try:
                tsf = float(ts)
            except Exception:
                tsf = None
            if tsf is not None and (now - tsf) < _AVOID_TIMEOUT_SECONDS:
                continue
            filtered.append(p)
        if filtered:
            ports = filtered

    return ports


def _record_success(config: Config, *, port: int) -> None:
    state = _load_smtp_state(config)
    state["preferred_port"] = int(port)
    avoid = state.get("avoid_ports") if isinstance(state.get("avoid_ports"), dict) else {}
    if isinstance(avoid, dict):
        avoid.pop(str(port), None)
        state["avoid_ports"] = avoid
    _save_smtp_state(config, state)


def _record_timeout(config: Config, *, port: int, now: float) -> None:
    state = _load_smtp_state(config)
    avoid = state.get("avoid_ports") if isinstance(state.get("avoid_ports"), dict) else {}
    if not isinstance(avoid, dict):
        avoid = {}
    avoid[str(int(port))] = float(now)
    state["avoid_ports"] = avoid
    _save_smtp_state(config, state)


def send_via_gmail_smtp(config: Config, message: Message) -> tuple[bool, str | None]:
    if not config.gmail_user:
        return (False, "Missing GMAIL_USER")
    if not config.gmail_app_password:
        return (False, "Missing GMAIL_APP_PASSWORD")

    email = EmailMessage()
    email["To"] = message.to
    email["From"] = message.from_addr
    email["Subject"] = message.subject
    email.set_content(message.body)

    context = ssl.create_default_context()
    logger = logging.getLogger("email_alert")

    try:
        last_error: str | None = None
        ports_to_try = _compute_ports_to_try(config, time.time())
        logger.info("smtp: ports_to_try=%s", ",".join(str(p) for p in ports_to_try))
        for port in ports_to_try:
            started = time.monotonic()
            try:
                if port == 465:
                    logger.info(
                        "smtp: connecting host=%s port=%s mode=ssl timeout=%ss",
                        config.smtp_host,
                        port,
                        config.smtp_timeout_seconds,
                    )
                    with smtplib.SMTP_SSL(
                        config.smtp_host, port, timeout=config.smtp_timeout_seconds, context=context
                    ) as smtp:
                        smtp.login(config.gmail_user, config.gmail_app_password)
                        smtp.send_message(email)
                    logger.info(
                        "smtp: sent via host=%s port=%s in %.1fs",
                        config.smtp_host,
                        port,
                        time.monotonic() - started,
                    )
                    _record_success(config, port=port)
                    return (True, None)

                logger.info(
                    "smtp: connecting host=%s port=%s mode=starttls timeout=%ss",
                    config.smtp_host,
                    port,
                    config.smtp_timeout_seconds,
                )
                with smtplib.SMTP(config.smtp_host, port, timeout=config.smtp_timeout_seconds) as smtp:
                    smtp.ehlo()
                    smtp.starttls(context=context)
                    smtp.ehlo()
                    smtp.login(config.gmail_user, config.gmail_app_password)
                    smtp.send_message(email)
                logger.info(
                    "smtp: sent via host=%s port=%s in %.1fs",
                    config.smtp_host,
                    port,
                    time.monotonic() - started,
                )
                _record_success(config, port=port)
                return (True, None)
            except smtplib.SMTPAuthenticationError:
                return (False, "SMTP auth failed (check Gmail app password)")
            except smtplib.SMTPConnectError as e:
                last_error = f"SMTP connect failed on {config.smtp_host}:{port}: {e}"
                logger.info("smtp: failed host=%s port=%s (%s)", config.smtp_host, port, e)
            except smtplib.SMTPException as e:
                last_error = f"SMTP error on {config.smtp_host}:{port}: {e}"
                logger.info("smtp: failed host=%s port=%s (%s)", config.smtp_host, port, e)
            except OSError as e:
                last_error = f"Network/OS error on {config.smtp_host}:{port}: {e}"
                logger.info("smtp: failed host=%s port=%s (%s)", config.smtp_host, port, e)
                if _is_timeout_error(e):
                    _record_timeout(config, port=port, now=time.time())

        return (False, last_error or "SMTP send failed")
    except smtplib.SMTPAuthenticationError:
        return (False, "SMTP auth failed (check Gmail app password)")
    except smtplib.SMTPConnectError as e:
        return (False, f"SMTP connect failed: {e}")
    except smtplib.SMTPException as e:
        return (False, f"SMTP error: {e}")
    except OSError as e:
        return (False, f"Network/OS error: {e}")
