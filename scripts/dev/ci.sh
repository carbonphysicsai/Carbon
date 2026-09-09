#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
python_bin="${repo_root}/.venv/bin/python"
quality_base_ref="${QUALITY_BASE_SHA:-origin/main}"

export VIRTUAL_ENV="${repo_root}/.venv"
export PATH="${VIRTUAL_ENV}/bin:${PATH}"

cd "${repo_root}"

if ! quality_base="$(git rev-parse --verify --end-of-options "${quality_base_ref}^{commit}" 2>/dev/null)"; then
  echo "Carbon CI cannot resolve QUALITY_BASE_SHA '${quality_base_ref}' to a commit." >&2
  echo "Fetch the comparison history or set QUALITY_BASE_SHA to an available commit/ref." >&2
  exit 2
fi
if ! git merge-base "${quality_base}" HEAD >/dev/null 2>&1; then
  echo "Carbon CI cannot find a merge base between '${quality_base_ref}' and HEAD." >&2
  echo "Fetch full comparison history and ensure the refs share ancestry." >&2
  exit 2
fi

echo "==> delivery scope and repository hygiene"
"${python_bin}" scripts/dev/classify_changes.py \
  --repository "${repo_root}" \
  --base "${quality_base}"
"${python_bin}" scripts/dev/check_delivery_hygiene.py \
  --repository "${repo_root}" \
  --base "${quality_base}"

echo "==> fast preflight"
QUALITY_BASE_SHA="${quality_base}" ./scripts/dev/preflight.sh

echo "==> invariant lane"
"${python_bin}" -m pytest tests/invariants -m invariant -q

echo "==> default CPU lane"
cpu_profile="$("${python_bin}" scripts/dev/select_cpu_profile.py --base="${quality_base}")"
case "${cpu_profile}" in
  NETWORK_FOUNDATION)
    echo "==> bounded network and tooling regression; full invariant and package lanes retained"
    "${python_bin}" -m pytest --collect-only -q >/dev/null
    network_manifest="$("${python_bin}" scripts/dev/select_cpu_profile.py --base="${quality_base}" --network-tests)"
    mapfile -t network_tests <<< "${network_manifest}"
    [[ "${#network_tests[@]}" -gt 0 ]]
    "${python_bin}" -m pytest "${network_tests[@]}" -q
    ;;
  TOOLING_ONLY)
    echo "==> bounded tooling regression suite; all CPU tests must still collect"
    "${python_bin}" -m pytest --collect-only -q >/dev/null
    tooling_manifest="$("${python_bin}" scripts/dev/select_cpu_profile.py --base="${quality_base}" --tooling-tests)"
    mapfile -t tooling_tests <<< "${tooling_manifest}"
    [[ "${#tooling_tests[@]}" -gt 0 ]]
    "${python_bin}" -m pytest "${tooling_tests[@]}" -q
    ;;
  RUNTIME_FULL)
    ./scripts/dev/test.sh
    ;;
  *)
    echo "Invalid CPU acceptance profile: ${cpu_profile}" >&2
    exit 2
    ;;
esac

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
  --base "${quality_base}"

echo "Carbon canonical CI gates passed."
