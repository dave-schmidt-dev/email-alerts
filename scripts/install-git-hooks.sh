#!/usr/bin/env bash
# Install the pre-commit framework hooks (commit + pre-push) defined in
# .pre-commit-config.yaml. Idempotent.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

if [[ ! -d .git ]]; then
  echo "No .git directory found. Run 'git init' first." >&2
  exit 1
fi

if command -v pre-commit >/dev/null 2>&1; then
  PC=(pre-commit)
elif command -v uvx >/dev/null 2>&1; then
  PC=(uvx pre-commit)
else
  echo "pre-commit not found. Install it: 'brew install pre-commit' (or use 'uvx')." >&2
  exit 1
fi

# -f: do not preserve/run any pre-existing legacy hook (avoids migration mode
# running a stale hook alongside the framework).
"${PC[@]}" install -f --install-hooks
"${PC[@]}" install -f -t pre-push
echo "Installed pre-commit hooks (commit + pre-push)."
