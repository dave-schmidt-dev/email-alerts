# email-alerts

A simple, open-source, terminal-based email alerting CLI for local scripts and automations.

## Install (recommended)

Keep this repo anywhere (for development), and create a stable executable path for automations/skills:

```bash
bash scripts/install-agent-bin.sh
```

This creates/updates:
- `~/.agent/bin/email-alert` → `<repo>/bin/email-alert`

Then call from anywhere:

```bash
~/.agent/bin/email-alert --help
```

If you want `email-alert` on your shell `PATH`, add `~/.agent/bin` to your PATH (or create another symlink into a PATH directory you already use).

## Install skill (optional, for agents)

If you want a local skill entry under `~/.agent/skills/email-alerts` that documents how to use this repo:

```bash
bash scripts/install-agent-skill.sh
```

## Configuration

Copy the example env file and fill in secrets:

```bash
cp config/.env.example config/.env
```

Set at minimum:
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`

Optional defaults:
- `EMAIL_ALERT_TO` (recommended; otherwise pass `--to` each time)
- `EMAIL_ALERT_FROM` (defaults to `GMAIL_USER`)

Runtime state (queue/logs) defaults to `~/.agent/state/email-alerts`. Override with `EMAIL_ALERT_STATE_DIR`.

By default, `email-alert` loads `config/.env`. You can override with `EMAIL_ALERT_ENV_FILE=/absolute/path/to/.env`.

## Usage

### Automation-friendly (recommended)

```bash
echo "Body text" | ~/.agent/bin/email-alert --to "you@example.com" --subject "Subject line"
```

### Positional (convenience)

```bash
~/.agent/bin/email-alert "to@example.com" "Subject" "Body"
~/.agent/bin/email-alert "to@example.com" "from@example.com" "Subject" "Body"
```

## Modes

- `--test`: no SMTP; writes to `${EMAIL_ALERT_STATE_DIR}/outbox.jsonl`
- `--e2e-test`: sends a real email using SMTP with a timestamp+nonce payload (skips queue flush so it’s immediate)
- `--dry-run`: prints/logs what would happen without sending

`--test` and `--e2e-test` are mutually exclusive.

## Logging

Logs go to stderr and a rotating file:
- Default: `${EMAIL_ALERT_STATE_DIR}/email-alert.log`
- Control with: `--log-level`, `--log-file`, `EMAIL_ALERT_LOG_MAX_BYTES`, `EMAIL_ALERT_LOG_BACKUP_COUNT`

At the default `INFO` log level, the CLI prints progress-style steps (flush, rate limit decisions, and SMTP connection attempts).

## Exit codes

- `0`: sent successfully, queued successfully, deduped, or rate-limited (depending on config)
- `1`: send failed (and either not queued, or `EMAIL_ALERT_ON_FAIL=queue_fail`)
- `2`: input/usage error

`--e2e-test` always exits non-zero on failure.

## Privacy / local state

`${EMAIL_ALERT_STATE_DIR}` can contain queued messages and test outbox entries with full email bodies. Treat it as sensitive and keep it private.

## OS support

Designed for macOS/Linux. Windows support is untested (the lock implementation is Unix-oriented).

## Rate limiting & dedupe

- Global rate limit (default): 1 email per minute
- Dedupe window (default): 1 minute for identical `(to, from, subject, body)`

## Troubleshooting

- Gmail requires an app password (not your normal Gmail password).
- If sends fail, check `${EMAIL_ALERT_STATE_DIR}/email-alert.log`.
- If sends time out on port 587, your network may be blocking outbound SMTP. The tool will learn which port works and cache it in `${EMAIL_ALERT_STATE_DIR}/smtp_state.json`, but you can also force it by setting `EMAIL_ALERT_SMTP_PORTS=465` (or `465,587`) and retry.

## Development

Packaging: `pyproject.toml` (hatchling), `requires-python = ">=3.9"`. The project is
stdlib-only — no runtime dependencies. Pinned dev interpreter: `.python-version` = 3.9
(the launchd/system floor), so 3.10-only syntax is caught locally.

Tooling (run via `uvx`, no project venv needed):

```bash
uvx pytest -q            # tests (migrated to pytest)
uvx ruff check .         # lint
uvx ruff format .        # format
uvx vulture email_alert tests vulture_whitelist.py   # dead-code detection
```

Install the pre-commit framework hooks (lint + format + vulture on commit, full test
suite on push). Mirrors `.github/workflows/ci.yml` (CI parity):

```bash
bash scripts/install-git-hooks.sh
```

### Optional: install as a console script

The repo runs with **zero install** via `bin/email-alert` (see Install above). If you
prefer a packaged console script instead, `pipx install .` (or `uv tool install .`)
exposes an `email-alert` entry point (`email_alert.cli:main`).
