---
name: email-alerts
description: Send local email alerts from scripts via the `email-alert` CLI.
---

# Email Alerts Skill (Local CLI)

This skill uses the local `email-alert` command to send email alerts from scripts/automations.

## Install (recommended)

1) Install the stable command path:

```bash
bash /path/to/email-alerts/scripts/install-agent-bin.sh
```

2) Install this skill into `~/.agent/skills`:

```bash
bash /path/to/email-alerts/scripts/install-agent-skill.sh
```

After that, scripts and automations should call:
- `~/.agent/bin/email-alert`

## Configuration

By default, `email-alert` loads `/path/to/email-alerts/config/.env` (ignored by git).

Required for real sends (Gmail SMTP):
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`

Optional:
- `EMAIL_ALERT_TO` (default recipient)
- `EMAIL_ALERT_FROM` (default sender; defaults to `GMAIL_USER`)
- `EMAIL_ALERT_STATE_DIR` (default: `~/.agent/state/email-alerts`)

## Usage

Automation-friendly (body via stdin):

```bash
echo "Something happened" | ~/.agent/bin/email-alert --to "you@example.com" --subject "Alert"
```

Test mode (no SMTP; writes to outbox):

```bash
echo "Hello" | ~/.agent/bin/email-alert --test --subject "Test"
```

E2E smoke test (real SMTP send):

```bash
~/.agent/bin/email-alert --e2e-test
```
