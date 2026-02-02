# Email Alerts — Detailed Task List

This is the execution checklist derived from `PLAN.md`. Tasks are grouped into phases and written to be as atomic as practical. When a task says “Done when”, it has clear acceptance criteria.

## Phase 0 — Repo Bootstrap

- [ ] Decide repo location + stable install path
  - Recommendation: keep repo in `~/Documents/Projects/...` and create a stable symlink at `~/.agent/bin/email-alert`.
  - Done when: `~/.agent/bin/email-alert` exists and runs `--help` successfully.
- [ ] Add an install helper script for the stable symlink
  - Recommendation: `scripts/install-agent-bin.sh`
  - Done when: script creates/updates `~/.agent/bin/email-alert` symlink correctly.
- [ ] Create `README.md` skeleton (install, config, examples, troubleshooting)
  - Done when: `README.md` exists with placeholder sections matching the plan.
- [ ] Create `config/.env.example` with all planned variables
  - Done when: includes `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `EMAIL_ALERT_TO`, `EMAIL_ALERT_FROM`, `EMAIL_ALERT_STATE_DIR`, `EMAIL_ALERT_ON_FAIL`, logging vars, and rate/dedupe vars.
- [ ] Create `.gitignore` for secrets/state
  - Done when: ignores `config/.env`, any `*.log`, and anything under `${EMAIL_ALERT_STATE_DIR}` if it’s ever placed inside the repo accidentally.
- [ ] Choose and add `LICENSE` (MIT or Apache-2.0)
  - Done when: `LICENSE` exists and `README.md` references it.

## Phase 1 — CLI Surface (`bin/email-alert`)

- [ ] Create `bin/email-alert` executable wrapper
  - Done when: `bin/email-alert --help` works and exits `0`.
- [ ] Implement CLI flags parsing
  - Flags: `--to`, `--from`, `--subject`, `--body`, `--dry-run`, `--test`, `--e2e-test`, `--log-level`, `--log-file`
  - Done when: parsing is covered by unit tests in `tests/test_cli.py`.
- [ ] Implement positional parsing with arg-count detection
  - 2 args: subject, body
  - 3 args: to, subject, body
  - 4 args: to, from, subject, body
  - Done when: all three forms pass unit tests.
- [ ] Implement stdin body rules
  - If `--body` absent and stdin is not a TTY, read body from stdin.
  - If body is empty after parsing, treat as input error (non-zero exit).
  - Done when: stdin behavior is tested.

## Phase 2 — Core Package Skeleton (`email_alert/`)

- [ ] Create `email_alert/__init__.py`
  - Done when: package imports without side effects.
- [ ] Create `email_alert/model.py` with `Message` (and any small result types)
  - Done when: message normalization fields exist for dedupe hashing.
- [ ] Create `email_alert/config.py`
  - Load from environment + optional `.env` (per plan)
  - Resolve default `to` and default `from`
  - Resolve `EMAIL_ALERT_STATE_DIR` default to `~/.agent/state/email-alerts`
  - Done when: config resolution covered by tests or small targeted assertions.

## Phase 3 — Logging (stderr + rotating file)

- [ ] Create `email_alert/logging_utils.py`
  - Parse levels; redact body by default (log length + hash)
  - Done when: helper functions have unit tests.
- [ ] Implement logging setup (Rotating file + stderr)
  - Default file: `${EMAIL_ALERT_STATE_DIR}/email-alert.log`
  - Rotation: `EMAIL_ALERT_LOG_MAX_BYTES` (default `1000000`) and `EMAIL_ALERT_LOG_BACKUP_COUNT` (default `3`)
  - Done when: running `--test` creates/updates the log file and also emits to stderr.

## Phase 4 — State & Atomic File Ops

- [ ] Create `email_alert/state.py`
  - Ensure state dir exists
  - Provide atomic append/write primitives
  - Done when: file operations are safe against partial writes.
- [ ] Add a cross-process lock for state mutations (best-effort)
  - Use an advisory lock (e.g., lock file in state dir)
  - Done when: queue operations acquire the lock in a single place (not scattered).

## Phase 5 — Dedupe

- [ ] Create `email_alert/dedupe.py`
  - Compute stable hash from `(to, from, subject, body)` with normalization
  - Read/write `sent.log` and enforce `EMAIL_ALERT_DEDUPE_SECONDS` (default `60`)
  - Done when: `tests/test_dedupe.py` passes and duplicate sends within 60s are suppressed.

## Phase 6 — Rate Limiting

- [ ] Create `email_alert/rate_limit.py`
  - Global throttle: allow one send per `EMAIL_ALERT_RATE_LIMIT_SECONDS` (default `60`)
  - Record last successful send time in `rate_limit.log`
  - Done when: `tests/test_rate_limit.py` passes.

## Phase 7 — Queue

- [ ] Create `email_alert/queue.py`
  - JSONL queue format: one message per line with metadata (id hash, timestamps, attempt count)
  - Enqueue on failure / rate-limit
  - Flush “due” items first on each invocation
  - Done when: `tests/test_queue.py` passes (append/read/remove/flush selection).
- [ ] Define queue behaviors for dedupe + rate limit interactions
  - Example: flushing should skip items still rate-limited and leave them queued.
  - Done when: integration tests (or expanded unit tests) cover at least 2 queued items.

## Phase 8 — Gmail SMTP Sender

- [ ] Create `email_alert/smtp_gmail.py`
  - Use stdlib `smtplib` + `email.message`
  - TLS + auth using `GMAIL_USER` and `GMAIL_APP_PASSWORD`
  - Reasonable timeouts and clear exception mapping
  - Done when: module can be exercised in `--e2e-test` without code changes.

## Phase 9 — End-to-End Flow + Modes

- [ ] Implement “send flow” orchestration (flush → send current → record)
  - Done when: `--test` sends to `outbox.jsonl` and updates `sent.log`/`rate_limit.log`.
- [ ] Implement `--dry-run`
  - Done when: prints/logs what would happen and does not mutate state (or only mutates logs, per decision).
- [ ] Implement test mode (`--test` / `EMAIL_ALERT_TEST_MODE=true`)
  - Write rendered message to `outbox.jsonl`
  - Done when: `outbox.jsonl` contains the message and no SMTP is used.
- [ ] Implement E2E mode (`--e2e-test` / `EMAIL_ALERT_E2E_TEST=true`)
  - Force real SMTP send even if `--test` is set
  - Generate nonce + timestamp to avoid dedupe collisions
  - Done when: one command sends an actual email end-to-end.
- [ ] Implement failure-mode config (`EMAIL_ALERT_ON_FAIL=queue_ok|queue_fail`)
  - Default: `queue_ok` (automation-friendly)
  - Done when: simulated send failures choose correct exit code and queue behavior.

## Phase 10 — Error Handling

- [ ] Wrap CLI entrypoint in top-level try/except
  - Log error (stack trace only at `DEBUG`)
  - Best-effort queue if a message exists
  - Done when: forced exceptions yield a clear error and predictable exit code.

## Phase 11 — Tests & Developer Workflow

- [ ] Add test harness (stdlib `unittest`) and minimal config
  - Done when: `python -m unittest` runs locally and discovers tests.
- [ ] Ensure tests use a temp state dir
  - Done when: tests never write to the real `~/.agent/state/email-alerts`.
- [ ] Add a quick “smoke test” doc snippet to `README.md`
  - Includes `--test` example and `--e2e-test` example
  - Done when: copy/paste commands work.

## Phase 12 — Skill Integration (required)

- [ ] Update your local skill to call the stable install path
  - Recommendation: call `~/.agent/bin/email-alert` (symlink to the repo’s `bin/email-alert`).
  - Done when: skill uses the stable path and no duplicated implementation exists in the skill folder.
- [ ] Provide an install script for the skill
  - Recommendation: `scripts/install-agent-skill.sh` copies `skills/email-alerts/SKILL.md` to `~/.agent/skills/email-alerts/SKILL.md`.
  - Done when: running the script installs/updates the skill successfully.
