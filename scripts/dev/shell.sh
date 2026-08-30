#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
venv_root="${repo_root}/.venv"

if [[ ! -x "${venv_root}/bin/python" ]]; then
  echo "Carbon environment is missing; run ./scripts/dev/bootstrap.sh." >&2
  exit 2
fi

echo "Entering Carbon environment at ${venv_root}."
cd "${repo_root}"
exec env \
  VIRTUAL_ENV="${venv_root}" \
  PATH="${venv_root}/bin:${PATH}" \
  bash -i
