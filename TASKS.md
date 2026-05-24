# Email Alerts — Tasks

Status key: `pending | in progress | done | blocked`. Historical build breakdown
lives in `PLAN.md`; this file tracks current state. Bugs/remediation: `HISTORY.md`.

## Done

- **v1.0.0 — full build shipped.** CLI surface, config/.env loading, rotating private
  logging, atomic state + cross-process lock, dedupe, rate limiting, JSONL queue,
  Gmail SMTP sender, test/e2e/dry-run modes, error handling, skill integration. (All
  Phase 0–12 items from `PLAN.md`.)
- **2026-05-24 — `[BUG-runtime-union-py39]` fixed.** `app.py` module-level `str | None`
  crashed on launchd's system Python 3.9; changed to `Tuple[bool, Optional[str]]`. See
  `HISTORY.md`.
- **2026-05-24 — modernized to project standards.** `pyproject.toml`
  (`requires-python>=3.9`, ruff `target py39`, console-script, pytest/vulture config);
  `.python-version` = 3.9; tests migrated `unittest`→`pytest` (10 pass on 3.9.6); all
  ruff findings fixed; pre-commit framework + GitHub Actions CI (parity); `tasks.md`→
  `TASKS.md`; removed hand-rolled `githooks/`.

## Next

- pending — Decide whether to ship a `.env.example` doc note about `EMAIL_ALERT_SMTP_PORTS`
  (the port-learning cache) so the troubleshooting path is discoverable from config alone.
- pending — Consider a tiny test asserting `import email_alert.app` under `/usr/bin/python3`
  (3.9) in CI, to lock the runtime-union regression even though CI already runs on 3.9.
- pending — If 3.10+ syntax is ever wanted, switch `bin/email-alert` to an explicit pinned
  interpreter / project venv (today it relies on staying 3.9-compatible under launchd).
