# Email Alerts (Local CLI) — Plan

## Summary
Create a simple, open-source, terminal-based email alerting system that other scripts/automations can call as:

`email-alert [to?] [from?] [subject] [body]`

Primary transport is Gmail SMTP using an app password. The system must be reliable for automation use (stable CLI, safe defaults, queue on failure, rate limiting to prevent spam).

## Goals
- Provide a single local CLI: `email-alert`
- Support both:
  - Positional usage for convenience
  - Flag-based + stdin usage for automation stability
- Send email via Gmail SMTP (`GMAIL_USER` + `GMAIL_APP_PASSWORD`)
- Provide:
  - Global rate limiting (default: 1 message/minute)
  - Short-window dedupe (default: 1 minute)
  - On-failure queue to disk (retry later)
- Keep state outside the repo (so it’s safe to open-source the repo without leaking data)

## Non-goals (for v1)
- Multiple recipients
- Attachments
- HTML emails
- Provider integrations beyond Gmail SMTP
- Cross-machine support (this is “personal machine” first)

## CLI Contract

### Recommended automation usage (most stable)
- Body from stdin (avoids shell quoting and length limits):
  - `echo "Body" | email-alert --subject "Subject"`

### Flags
`email-alert --subject <subject> [--to <to>] [--from <from>] [--body <body>] [--dry-run] [--test] [--e2e-test] [--log-level <level>]`

Rules:
- If `--body` is omitted and stdin is not a TTY, read body from stdin.
- If body is still empty, treat as an error (exit non-zero) unless explicitly allowed.

### Positional
`email-alert [to] [from] <subject> <body>`

Arg-count detection:
- 2 args: `<subject> <body>`
- 3 args: `<to> <subject> <body>`
- 4 args: `<to> <from> <subject> <body>`

## Defaults & Configuration

### Defaults (v1)
- Default recipient: `EMAIL_ALERT_TO` (recommended). If not set, pass `--to` explicitly.
- Default sender:
  - `EMAIL_ALERT_FROM` if set, else `GMAIL_USER` (recommended to set explicitly)
- Rate limit: `EMAIL_ALERT_RATE_LIMIT_SECONDS=60`
- Dedupe window: `EMAIL_ALERT_DEDUPE_SECONDS=60`
- Logging:
  - `EMAIL_ALERT_LOG_LEVEL=INFO`
  - `EMAIL_ALERT_LOG_FILE=${EMAIL_ALERT_STATE_DIR}/email-alert.log`
  - `EMAIL_ALERT_LOG_MAX_BYTES=1000000`
  - `EMAIL_ALERT_LOG_BACKUP_COUNT=3`

### Secrets / Credentials
Environment variables (primary):
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`

Optional local config file (secondary):
- `EMAIL_ALERT_ENV_FILE` (explicit path) OR load `.env` from config directory

### State directory (outside repo)
- `EMAIL_ALERT_STATE_DIR` overrides location.
- Default: `~/.agent/state/email-alerts`

State files (names may change, but intent is fixed):
- `queue.jsonl` (pending messages)
- `sent.log` (recently sent message IDs for dedupe window)
- `rate_limit.log` (timestamp of last successful send)
- `outbox.jsonl` (test-mode “sent” messages for inspection)
- `email-alert.log` (running log file; rotated backups may exist)
- `test_queue.jsonl` (test-mode queue)
- `test_sent.log` (test-mode dedupe)
- `test_rate_limit.log` (test-mode rate limit)

## Behavior

### Send flow (each invocation)
1) Load config/env (env vars + optional `.env`)
2) Flush any queued messages that are now eligible (rate limit + dedupe)
3) Attempt to send the current message:
   - If rate-limited → queue it
   - If deduped → drop it (or optionally no-op success)
   - If SMTP send succeeds → record send time + dedupe ID
   - If SMTP send fails → queue it

### Test mode
- Add a test mode to make the system safe to run in CI/local validation without sending real email.
- Enable via `--test` or `EMAIL_ALERT_TEST_MODE=true`.
- In test mode:
  - Do not connect to Gmail SMTP.
  - Treat “send” as success and write the rendered message to a local outbox file for inspection:
    - `outbox.jsonl` in `EMAIL_ALERT_STATE_DIR`
  - Still apply rate limiting + dedupe by default (so test runs reflect real behavior), but keep test state separate so it doesn’t affect real sends:
    - `test_queue.jsonl`, `test_sent.log`, `test_rate_limit.log`

### E2E test email (smoke test)
- Provide an explicit way to send a real email end-to-end to validate Gmail credentials and SMTP connectivity.
- Enable via `--e2e-test` or `EMAIL_ALERT_E2E_TEST=true`.
- Behavior:
  - Always uses the real SMTP sender (even if `--test` is also set).
  - Uses a generated subject/body with a timestamp and random nonce to avoid dedupe collisions.
  - Uses configured defaults for `to`/`from` unless overridden by flags.
  - Skips queue flushing so the smoke test is immediate.
  - Still respects the global rate limit by default; add an escape hatch if needed:
    - Optional `EMAIL_ALERT_E2E_BYPASS_RATE_LIMIT=true` (or a later CLI flag) for “I really want one test email right now”.

### Rate limiting
- Global rate limit: allow at most 1 successful send per `EMAIL_ALERT_RATE_LIMIT_SECONDS`.
- When rate limited, message is queued and will be sent on a later invocation.

### Dedupe
- Compute a message ID hash from `(to, from, subject, body)` (stable normalization).
- If the same ID was successfully sent in the last `EMAIL_ALERT_DEDUPE_SECONDS`, do not send again.
- Default window is 60 seconds (can be lowered/raised).

### Failure mode (exit codes)
Make behavior configurable for automation:
- `EMAIL_ALERT_ON_FAIL=queue_ok|queue_fail`
  - `queue_ok` (default): queue on failure and exit `0` (best for “don’t break automations”)
  - `queue_fail`: queue on failure and exit non-zero (best for “fail fast / surface breakage”)

For hard input errors (missing subject/body, invalid args), always exit non-zero.

## Logging & Error Handling

### Logging
- Default logging to **both** stderr and a running log file (best for automation capture + postmortem debugging).
- Configure via:
  - `--log-level` or `EMAIL_ALERT_LOG_LEVEL` (`ERROR`, `WARNING`, `INFO` default, `DEBUG`)
- Log file (default): `${EMAIL_ALERT_STATE_DIR}/email-alert.log`
  - Override via `--log-file <path>` or `EMAIL_ALERT_LOG_FILE=/path/to/email-alert.log`
- Log rotation (built-in):
  - Default rotate at `1_000_000` bytes with `3` backups
  - Configurable via `EMAIL_ALERT_LOG_MAX_BYTES` and `EMAIL_ALERT_LOG_BACKUP_COUNT`
- Log events (at minimum):
  - Parsed destination/from/subject (redact body by default; show length + hash)
  - Send attempt outcome (sent, queued, rate-limited, deduped, flush results)
  - State directory and config source (env vs file)

### Error catching
- Wrap the CLI `main()` in a top-level try/except to prevent uncaught exceptions from crashing without context.
- On exceptions:
  - Log a clear error message (and stack trace only at `DEBUG`).
  - If the current message is available, attempt to queue it (best-effort).
  - Exit non-zero unless configured `EMAIL_ALERT_ON_FAIL=queue_ok` and queuing succeeded.

## Implementation Approach

### Language/runtime
- Prefer a single, dependency-light implementation:
  - Option A (recommended): Python 3 script in `bin/email-alert` using stdlib `smtplib` + `email.message`
  - Option B: Bash + `python3` helper (harder to test/maintain)

### Repo layout (proposed)
- `bin/email-alert` (entrypoint)
- `email_alert/` (Python package: config, smtp, queue, rate limit, dedupe)
- `config/.env.example`
- `README.md` (install + usage)
- `LICENSE` (MIT or Apache-2.0; choose before release)
- `skills/email-alerts/SKILL.md` (skill template that points to this repo)
- `scripts/install-agent-skill.sh` (installs skill to `~/.agent/skills/email-alerts`)

## Install & Skill Integration

### Recommended local install
- Keep the repo anywhere convenient for development (e.g., `~/Documents/Projects/email-alerts`).
- Provide a stable executable path for automations/skills by symlinking:
  - `~/.agent/bin/email-alert` → `<repo>/bin/email-alert`
  - (Optionally also) `~/.local/bin/email-alert` if you prefer that on `PATH`.

Rationale:
- Keeps the repo in a normal “projects” location (easy to git/publish).
- Gives all automations and skills a consistent path that doesn’t change if you move/rename the repo.

### Skill behavior (required)
- Update the local skill to call the stable symlink path (recommended) or a configurable env var.
- Prefer: call `~/.agent/bin/email-alert` (and document how to create that symlink).

## Files To Create (v1)

### Runtime/CLI
- `bin/email-alert`
  - Executable entrypoint users/automations call.
  - Handles CLI parsing (positional + flags), stdin reading, logging setup, and top-level error handling.
  - Calls into the Python package for the actual behavior (queue/flush/send).

### Python package
- `email_alert/__init__.py`
  - Package marker; exports version and high-level entry points if useful.
- `email_alert/cli.py`
  - Argument parsing + normalization into a message object.
  - Implements `--test` and `--e2e-test` behavior flags.
- `email_alert/config.py`
  - Loads env vars and optional `.env` file; resolves defaults for `to`/`from`.
  - Resolves `EMAIL_ALERT_STATE_DIR` default path.
- `email_alert/model.py`
  - Small dataclasses for `Message`, `SendResult`, etc.
  - Central place for normalization used by dedupe hashing.
- `email_alert/smtp_gmail.py`
  - Gmail SMTP sender using stdlib `smtplib` + `email.message`.
  - Timeouts, TLS, authentication, and friendly error mapping.
- `email_alert/state.py`
  - State directory management and atomic file operations.
  - Helpers to read/write queue/sent/rate-limit/outbox files safely.
- `email_alert/dedupe.py`
  - Message ID hashing + “sent recently” checks for the dedupe window.
- `email_alert/rate_limit.py`
  - Global rate limit checks and recording last-send time.
- `email_alert/queue.py`
  - Queue format (JSONL) and operations: enqueue, list, remove, flush-due.
- `email_alert/logging_utils.py`
  - Minimal logging helpers (level parsing, redaction utilities).

### Docs & configuration
- `config/.env.example`
  - Template env file showing required/optional vars and defaults (no secrets).
- `README.md`
  - Installation (symlink PATH, or call `bin/email-alert` directly), configuration, examples.
  - Troubleshooting (Gmail app password, common SMTP errors).
- `LICENSE`
  - Open-source license text (choose MIT vs Apache-2.0).

### Tests (minimal)
- `tests/test_cli.py`
  - Positional/flag parsing cases; stdin handling; required fields validation.
- `tests/test_dedupe.py`
  - Hash stability; 1-minute window behavior.
- `tests/test_rate_limit.py`
  - 1/minute global throttle behavior.
- `tests/test_queue.py`
  - JSONL queue append/read/remove; flush selection logic.

## Task Breakdown (do before coding each step)
1) Decide implementation language (Python 3 recommended)
2) Define exact exit code semantics and logging format
3) Implement CLI parsing (positional + flags + stdin)
4) Implement Gmail SMTP sender
5) Implement state dir selection + atomic file writes
6) Implement rate limiting + dedupe
7) Implement queue + flush behavior
8) Add `--dry-run`, `--test`, and `--e2e-test`
9) Add basic logging + top-level error handling
10) Add minimal tests (stdlib `unittest` for parser/dedupe/rate-limit/queue)
11) Add `README.md`, `.env.example`, and choose license
