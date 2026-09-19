#!/usr/bin/env bash
# Required Workbench product checks for changes to its own sources, generators,
# tests or release artifacts.
#
# The change classifier files the Workbench under CONTRACT_AUTHORITY, whose
# acceptance lane covers constitutional invariants and repository authority but
# never runs the application. These checks close that gap and are required
# whenever the Workbench's actual inputs change, independent of scope.
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
cd "${repo_root}"

workbench="${repo_root}/Business/Carbon_Fit/workbench"
python_bin="${repo_root}/.venv/bin/python"
required_node="v24.19.0"

if [[ ! -x "${python_bin}" ]]; then
  echo "Workbench release checks require the repository's canonical .venv; run ./scripts/dev/bootstrap.sh." >&2
  exit 2
fi

if ! command -v node >/dev/null || [[ "$(node --version)" != "${required_node}" ]]; then
  echo "Workbench release checks require pinned Node.js ${required_node}." >&2
  exit 2
fi

export PYTHONPATH="${repo_root}${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONUTF8=1

# This must run before any suite that regenerates the artifacts in place.
# test_sources.py rebuilds the bundle to prove determinism, which overwrites
# the tracked bytes; checking freshness afterwards would only ever compare a
# fresh build against itself.
echo "==> tracked Workbench release artifacts match their tracked sources"
"${python_bin}" "${workbench}/tools/check_release_freshness.py"

echo "==> Workbench application, workflow and team-review suites"
node --test "${workbench}"/tests/test_*.cjs

echo "==> Workbench source, packaging, freshness and authoring suites"
"${python_bin}" -m pytest -q \
  "${workbench}/tests/test_sources.py" \
  "${workbench}/tests/test_release_freshness.py" \
  "${workbench}/tests/test_authoring_bridge.py"

echo "Workbench release checks passed."
