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
  DEVELOPMENT_COMPETITION)
    echo "==> bounded DEVELOPMENT measurement/source/scoring/reward regression; no public transaction"
    "${python_bin}" -m pytest --collect-only -q >/dev/null
    development_manifest="$("${python_bin}" scripts/dev/select_cpu_profile.py --base="${quality_base}" --development-tests)"
    mapfile -t development_tests <<< "${development_manifest}"
    [[ "${#development_tests[@]}" -gt 0 ]]
    "${python_bin}" -m pytest "${development_tests[@]}" -q
    ;;
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

if [[ " ${CARBON_UV_GROUPS:-} " == *" science-jax "* ]]; then
  echo "==> required C-02 JAX development lane"
  "${python_bin}" -m pytest tests/science -q
fi

if [[ " ${CARBON_UV_GROUPS:-} " == *" mcp "* ]]; then
  echo "==> pinned standard MCP external-client interoperability"
  "${python_bin}" -m pytest tests/service/test_standard_mcp_stdio.py \
    tests/service/test_standard_mcp_cli.py tests/service/test_standard_mcp_http.py \
    tests/service/test_standard_mcp_apps.py tests/service/test_mcp_app_composition.py \
    tests/service/test_standard_mcp_extensions.py \
    tests/service/test_mcp_task_supervisor.py -q
  if [[ "${CARBON_REQUIRE_TYPESCRIPT_INTEROP:-}" == "1" ]]; then
    "${python_bin}" -m pytest tests/service/test_standard_mcp_typescript.py -q
    # The MCP conformance suite is not collected by the default testpaths, so it
    # runs here beside the interoperability client it was promoted from. Its
    # controls are required rather than skipped: a conformance suite that is
    # shipped but never executed manufactures the confidence it exists to test.
    pnpm --dir tests/conformance/mcp install --frozen-lockfile --ignore-scripts
    CARBON_REQUIRE_MCP_CONFORMANCE=1 \
      "${python_bin}" -m pytest tests/conformance/mcp -q
    bash ./scripts/dev/workbench_science_checks.sh
  fi
fi

# The Launchpad browser surface had no execution home: no browser on the
# development host and no CI step ran it, so assertions added to that smoke
# would have been coverage that never executes. It runs here rather than as a
# workflow step because the workflow delegates all of its semantics to these
# scripts, and adding a step there would have widened what that invariant pins
# instead of respecting it. Skipped, loudly, where no browser exists.
if "${python_bin}" -c "import sys; sys.path.insert(0, 'docs/development/carbon_hub/tools'); import browser_smoke_test as cdp; cdp.discover_browser()" >/dev/null 2>&1; then
  echo "==> Launchpad real-browser smoke"
  "${python_bin}" scripts/dev/miner_launchpad/browser_smoke.py
else
  echo "==> Launchpad real-browser smoke SKIPPED: no Chromium-family browser found"
fi

echo "==> canonical/legacy authority boundary"
"${python_bin}" -m pytest tests/cpu/test_code_authority.py -q

echo "==> terminal committed and local Git diff hygiene"
"${python_bin}" scripts/dev/check_diff_hygiene.py \
  --repository "${repo_root}" \
  --base "${quality_base}"

echo "Carbon canonical CI gates passed."
