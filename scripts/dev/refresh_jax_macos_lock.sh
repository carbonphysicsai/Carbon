#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
cache_path="${UV_CACHE_DIR:-${repo_root}/.carbon-local/uv-cache-c02}"
tool_path="${UV_TOOL_DIR:-${repo_root}/.carbon-local/uv-tools-c02}"

cd "${repo_root}"
UV_CACHE_DIR="${cache_path}" UV_TOOL_DIR="${tool_path}" \
  uvx --from uv==0.12.7 uv pip compile \
  --python-platform aarch64-apple-darwin \
  --python-version 3.11 \
  --generate-hashes \
  --custom-compile-command './scripts/dev/refresh_jax_macos_lock.sh' \
  --output-file requirements/jax-macos-arm64.lock \
  requirements/jax-macos-arm64.in
