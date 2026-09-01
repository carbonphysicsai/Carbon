#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
python_bin="${repo_root}/.venv/bin/python"
quality_base_ref="${QUALITY_BASE_SHA:-origin/main}"

export VIRTUAL_ENV="${repo_root}/.venv"
export PATH="${VIRTUAL_ENV}/bin:${PATH}"

cd "${repo_root}"

echo "==> fast preflight"
./scripts/dev/preflight.sh

echo "==> invariant lane"
"${python_bin}" -m pytest tests/invariants -m invariant -q

echo "==> default CPU lane"
./scripts/dev/test.sh

echo "==> package, wheel, and outside-tree lane"
"${python_bin}" -m pytest \
  tests/cpu/test_package_installation.py \
  tests/cpu/test_optional_backends.py \
  tests/cpu/test_observability.py::test_fresh_zero_dependency_wheel_imports_exact_surface_outside_tree \
  -q -s

echo "==> canonical/legacy authority boundary"
"${python_bin}" -m pytest tests/cpu/test_code_authority.py -q

echo "==> terminal committed and local Git diff hygiene"
"${python_bin}" scripts/dev/check_diff_hygiene.py \
  --repository "${repo_root}" \
  --base "${quality_base_ref}"

echo "Carbon canonical CI gates passed."
