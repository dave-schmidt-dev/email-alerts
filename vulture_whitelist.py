# vulture whitelist — false-positive suppression for email-alerts
#
# Entries here are items vulture flags as unused but are intentionally kept:
# dataclass fields accessed via named keyword args, module-level constants
# used only in string formatting, and public API surface.

from email_alert.logging_utils import PrivateRotatingFileHandler

# PrivateRotatingFileHandler.emit / doRollover are overrides; they are called
# by the logging framework, not from our own code.
PrivateRotatingFileHandler.emit
PrivateRotatingFileHandler.doRollover

from email_alert.model import SendResult

# SendResult.deduped / rate_limited are set and checked by callers; vulture
# may not see the cross-module usage.
SendResult.deduped
SendResult.rate_limited
