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

echo "==> constitutional invariant acceptance"
"${python_bin}" -m pytest tests/invariants -m invariant -q

authority_tests=(tests/cpu/test_code_authority.py)
if [[ -f tests/cpu/test_github_ruleset.py ]]; then
  authority_tests+=(tests/cpu/test_github_ruleset.py)
fi

echo "==> code, repository, and merge-authority acceptance"
"${python_bin}" -m pytest "${authority_tests[@]}" -q

echo "Carbon contract-authority gates passed."
