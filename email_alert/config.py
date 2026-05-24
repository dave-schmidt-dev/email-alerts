from __future__ import annotations

import os
from pathlib import Path

from email_alert.model import Config, OnFailMode


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    v = value.strip().lower()
    if v in {"1", "true", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _parse_int(value: str | None, *, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _parse_int_list(value: str | None, *, default: list[int]) -> list[int]:
    if value is None:
        return default
    items: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            items.append(int(part))
        except ValueError:
            continue
    return items or default


def _load_dotenv_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
            value = value[1:-1]
        data[key] = value
    return data


def load_env(repo_root: Path, env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if env is None else env)

    env_file = env.get("EMAIL_ALERT_ENV_FILE")
    dotenv_path = Path(env_file).expanduser() if env_file else repo_root / "config" / ".env"

    dotenv_values = _load_dotenv_file(dotenv_path)
    for key, value in dotenv_values.items():
        env.setdefault(key, value)

    return env


def resolve_state_dir(env: dict[str, str]) -> Path:
    raw = env.get("EMAIL_ALERT_STATE_DIR")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".agent" / "state" / "email-alerts"


def load_config(
    *,
    repo_root: Path,
    env: dict[str, str] | None = None,
    log_level_override: str | None = None,
    log_file_override: str | None = None,
    test_mode_override: bool | None = None,
    e2e_test_override: bool | None = None,
) -> Config:
    merged_env = load_env(repo_root, env)

    gmail_user = merged_env.get("GMAIL_USER") or None
    gmail_app_password = merged_env.get("GMAIL_APP_PASSWORD") or None

    default_to = merged_env.get("EMAIL_ALERT_TO") or merged_env.get("EMAIL_TO") or ""
    default_from = merged_env.get("EMAIL_ALERT_FROM") or None

    state_dir = resolve_state_dir(merged_env)

    on_fail: OnFailMode = (
        "queue_fail"
        if (merged_env.get("EMAIL_ALERT_ON_FAIL") or "").strip() == "queue_fail"
        else "queue_ok"
    )

    rate_limit_seconds = _parse_int(merged_env.get("EMAIL_ALERT_RATE_LIMIT_SECONDS"), default=60)
    dedupe_seconds = _parse_int(merged_env.get("EMAIL_ALERT_DEDUPE_SECONDS"), default=60)

    log_level = (log_level_override or merged_env.get("EMAIL_ALERT_LOG_LEVEL") or "INFO").upper()
    log_file = Path(
        log_file_override
        or merged_env.get("EMAIL_ALERT_LOG_FILE")
        or (state_dir / "email-alert.log")
    ).expanduser()
    log_max_bytes = _parse_int(merged_env.get("EMAIL_ALERT_LOG_MAX_BYTES"), default=1_000_000)
    log_backup_count = _parse_int(merged_env.get("EMAIL_ALERT_LOG_BACKUP_COUNT"), default=3)

    test_mode = (
        test_mode_override
        if test_mode_override is not None
        else _parse_bool(merged_env.get("EMAIL_ALERT_TEST_MODE"), default=False)
    )
    e2e_test = (
        e2e_test_override
        if e2e_test_override is not None
        else _parse_bool(merged_env.get("EMAIL_ALERT_E2E_TEST"), default=False)
    )
    e2e_bypass_rate_limit = _parse_bool(
        merged_env.get("EMAIL_ALERT_E2E_BYPASS_RATE_LIMIT"), default=False
    )

    smtp_host = (merged_env.get("EMAIL_ALERT_SMTP_HOST") or "smtp.gmail.com").strip()
    smtp_ports = tuple(
        _parse_int_list(merged_env.get("EMAIL_ALERT_SMTP_PORTS"), default=[587, 465])
    )
    smtp_timeout_seconds = _parse_int(
        merged_env.get("EMAIL_ALERT_SMTP_TIMEOUT_SECONDS"), default=20
    )

    return Config(
        gmail_user=gmail_user,
        gmail_app_password=gmail_app_password,
        default_to=default_to,
        default_from=default_from,
        state_dir=state_dir,
        on_fail=on_fail,
        rate_limit_seconds=max(0, rate_limit_seconds),
        dedupe_seconds=max(0, dedupe_seconds),
        log_level=log_level,
        log_file=log_file,
        log_max_bytes=max(0, log_max_bytes),
        log_backup_count=max(0, log_backup_count),
        test_mode=test_mode,
        e2e_test=e2e_test,
        e2e_bypass_rate_limit=e2e_bypass_rate_limit,
        smtp_host=smtp_host,
        smtp_ports=smtp_ports,
        smtp_timeout_seconds=max(1, smtp_timeout_seconds),
    )
