from __future__ import annotations

import hashlib
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from email_alert.model import Config


class PrivateRotatingFileHandler(RotatingFileHandler):
    def _ensure_private(self) -> None:
        try:
            Path(self.baseFilename).chmod(0o600)
        except OSError:
            pass

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover
        self._ensure_private()
        return super().emit(record)

    def doRollover(self) -> None:  # pragma: no cover
        super().doRollover()
        self._ensure_private()


def body_fingerprint(body: str) -> tuple[int, str]:
    body_bytes = body.encode("utf-8", errors="replace")
    digest = hashlib.sha256(body_bytes).hexdigest()
    return (len(body_bytes), digest)


def configure_logging(
    *,
    config: Config,
    log_level_override: str | None = None,
    log_file_override: Path | None = None,
) -> logging.Logger:
    logger = logging.getLogger("email_alert")
    logger.setLevel(logging.DEBUG)
    for handler in list(logger.handlers):
        try:
            handler.close()
        finally:
            logger.removeHandler(handler)
    logger.propagate = False

    level_name = (log_level_override or config.log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    log_file = log_file_override or config.log_file
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)

        max_bytes = int(config.log_max_bytes) if config.log_max_bytes else 0
        backup_count = int(config.log_backup_count) if config.log_backup_count else 0

        file_handler = PrivateRotatingFileHandler(
            filename=str(log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        logger.warning("file logging disabled (log_file=%s): %s", log_file, e)

    return logger
