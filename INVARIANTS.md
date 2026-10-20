# Invariants — email-alerts

This charter does not send email or run live SMTP verification. Queued bodies and local outbox entries are sensitive data.

Charter adoption records required behavior; it does not certify runtime compliance.

### INV-1 — Queue and send outcomes preserve the documented exit contract
area: ["email_alert/app.py", "email_alert/queue.py", "email_alert/cli.py"]
gate_test: tests/test_queue.py
threshold: 3
rationale: A successfully queued alert, a delivered alert and a failed send retain their documented meanings rather than reporting synthetic delivery.

### INV-2 — Deduplication and rate limiting remain independent enforced decisions
area: ["email_alert/dedupe.py", "email_alert/rate_limit.py"]
gate_test: tests/test_dedupe.py
threshold: 3
rationale: Duplicate suppression and rate policy prevent repeated notifications; tests/test_rate_limit.py separately locks rate accounting.

### INV-3 — SMTP credentials and queued message bodies stay private
area: ["email_alert/config.py", "email_alert/smtp_gmail.py", "email_alert/state.py"]
gate_test: manual: inspect credential consumption, logging and state-directory handling without reading secret values or sending mail; automated complete privacy coverage is not implemented
threshold: 3
rationale: Routine diagnostics must not expose credentials or full private queued message bodies.

### INV-4 — Flush and SMTP waits expose progress and terminal errors
area: ["email_alert/app.py", "email_alert/smtp_gmail.py", "email_alert/cli.py"]
gate_test: manual: verify visible flush/admission/connection progress and bounded terminal failure with fake transport; complete automated progress coverage is not implemented
threshold: 3
rationale: Automation callers must be able to distinguish active sending, queued work and failed SMTP operations.
