#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -d "${repo_root}/.git" ]]; then
  echo "No .git directory found. Run 'git init' first." >&2
  exit 1
fi

mkdir -p "${repo_root}/.git/hooks"
cp -f "${repo_root}/githooks/pre-commit" "${repo_root}/.git/hooks/pre-commit"
chmod +x "${repo_root}/.git/hooks/pre-commit"

echo "Installed git hook: .git/hooks/pre-commit"

