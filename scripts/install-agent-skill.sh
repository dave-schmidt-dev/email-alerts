#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target_dir="${HOME}/.agent/skills/email-alerts"

mkdir -p "${target_dir}"
cp -f "${repo_root}/skills/email-alerts/SKILL.md" "${target_dir}/SKILL.md"

echo "Installed skill: ${target_dir}/SKILL.md"
