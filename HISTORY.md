# History

All meaningful changes, bugs, and remediations regardless of git state.

## 2026-05-24

### [BUG-runtime-union-py39] `import email_alert.app` crashes on Python 3.9 (`TypeError: unsupported operand type(s) for |`)

- **Symptom:** Every launchd-triggered Scarecrow weekly report since 2026-05-18 (`2026-W20`) failed at the email step. `email-alert` aborted on import with:
  ```
  File ".../email_alert/app.py", line 15, in <module>
      SendFn = Callable[[Config, Message], tuple[bool, str | None]]
  TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
  ```
- **Root cause:** Line 15 is a **module-level assignment**, not an annotation, so its right-hand side is evaluated at import time. The `str | None` (PEP 604) union is only a valid *runtime* expression on Python ≥3.10. `from __future__ import annotations` does not defer it — that future only stringifies annotations (things after a `:` in signatures/variables), never assignment RHS values. `bin/email-alert` uses `#!/usr/bin/env python3` with no pinned venv, so under launchd's minimal PATH (`/opt/homebrew/bin` absent) `python3` resolved to `/usr/bin/python3` = system **Python 3.9.6**, which raised. Interactive/manual runs picked up Homebrew 3.14 and worked, which is why the bug only showed up in scheduled runs.
- **Fix:** use runtime-safe typing for the alias — `from typing import Callable, Optional, Tuple` and `SendFn = Callable[[Config, Message], Tuple[bool, Optional[str]]]`. A `compileall` + import scan confirmed this was the only module-level runtime union in the package; the rest is already 3.9-compatible.
- **Regression check:** `cd email-alerts && /usr/bin/python3 -c "import sys; sys.path.insert(0,'.'); import email_alert.app"` now imports cleanly under 3.9.6 (previously raised). A unit test asserting `email_alert.app` imports under the system interpreter would lock this in.
- **Hardening note:** the deeper fragility is the unpinned `#!/usr/bin/env python3`. If this tool ever intentionally adopts 3.10+ syntax, callers must invoke it with an explicit ≥3.10 interpreter (or the project should ship its own venv), since launchd will keep handing it system 3.9.

### Modernization to project standards

- **Added `pyproject.toml`** (hatchling): metadata, `requires-python = ">=3.9"`, `[project.scripts] email-alert = email_alert.cli:main`, and centralized `[tool.ruff]` (`target-version = "py39"` so the 3.10-only syntax that caused the bug above is now a lint error), `[tool.pytest.ini_options]`, and `[tool.vulture]` config.
- **Pinned dev interpreter** via `.python-version` = 3.9 (prod/CI parity — catches 3.10 syntax in dev, not just at launchd runtime).
- **Migrated tests `unittest` → `pytest`** (plain functions + `assert`, `tmp_path` fixtures). 10 tests pass under 3.9.6. Fixed an e2e test that read real stdin (passed under unittest from a tty, failed under pytest's captured stdin) by mocking stdin as a tty.
- **Fixed all ruff findings** the new config surfaced: 3× E501 (long lines; the SMTP one uses a local var rather than 3.10+ parenthesized `with`-items), 4× SIM105 (`try/except/pass` → `contextlib.suppress`).
- **Replaced the hand-rolled `githooks/pre-commit`** with the pre-commit framework (`.pre-commit-config.yaml`: ruff lint+format + vulture on commit, full pytest on pre-push) and added **`.github/workflows/ci.yml`** running the same four commands on Python 3.9 (CI parity). `scripts/install-git-hooks.sh` now installs the framework hooks.
- **Renamed `tasks.md` → `TASKS.md`** (project doc convention).
- **Verified:** `ruff check` / `ruff format --check` clean, `vulture` clean, `pytest` 10/10, imports under `/usr/bin/python3` 3.9.6, `bin/email-alert --help` exits 0, `config/.env` still untracked. Runtime behavior unchanged (the modules were only reformatted + the two typing/lint fixes).
