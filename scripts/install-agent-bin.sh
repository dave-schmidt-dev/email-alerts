#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target_dir="${HOME}/.agent/bin"
target_link="${target_dir}/email-alert"
source_path="${repo_root}/bin/email-alert"

mkdir -p "${target_dir}"
ln -sf "${source_path}" "${target_link}"

echo "Installed: ${target_link} -> ${source_path}"
