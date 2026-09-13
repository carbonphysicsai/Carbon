#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
venv_path="${repo_root}/.venv-jax-macos"
cache_path="${repo_root}/.carbon-local/uv-cache-c02"
tool_path="${repo_root}/.carbon-local/uv-tools-c02"
lock_path="${repo_root}/requirements/jax-macos-arm64.lock"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "C-02 native setup requires macOS on Apple silicon." >&2
  exit 2
fi
if ! command -v python3.11 >/dev/null 2>&1; then
  echo "Python 3.11 is required; no global interpreter will be modified." >&2
  exit 2
fi

mkdir -p "${cache_path}" "${tool_path}"
export UV_CACHE_DIR="${cache_path}"
export UV_TOOL_DIR="${tool_path}"
uv_command=(uv)
if [[ "$(uv --version 2>/dev/null || true)" != "uv 0.12.7 "* ]]; then
  uv_command=(uvx --from uv==0.12.7 uv)
fi
if [[ ! -x "${venv_path}/bin/python" ]]; then
  "${uv_command[@]}" venv --python python3.11 "${venv_path}"
fi
"${uv_command[@]}" pip sync \
  --python "${venv_path}/bin/python" \
  --require-hashes \
  "${lock_path}"

"${venv_path}/bin/python" "${script_dir}/jax_macos_diagnostic.py" doctor
