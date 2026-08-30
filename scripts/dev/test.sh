#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
python_bin="${repo_root}/.venv/bin/python"

if [[ ! -x "${python_bin}" ]]; then
  echo "Carbon environment is missing; run ./scripts/dev/bootstrap.sh." >&2
  exit 2
fi

cd "${repo_root}"
exec "${python_bin}" -m pytest -q "$@"
