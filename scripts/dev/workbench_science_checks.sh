#!/usr/bin/env bash
# Run inside the canonical development environment; never regenerate tracked builds.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python="${repo_root}/.venv/bin/python"
if [[ ! -x "${python}" ]]; then
  echo "Workbench checks require the repository's canonical .venv." >&2
  exit 1
fi
if ! command -v node >/dev/null || [[ "$(node --version)" != "v24.19.0" ]]; then
  echo "Workbench checks require pinned Node.js v24.19.0 from the canonical job." >&2
  exit 1
fi
export PATH="${repo_root}/.venv/bin:${PATH}"
export PYTHONPATH="${repo_root}${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONUTF8=1

mkdir -p "${repo_root}/.carbon-local"
scratch="$(mktemp -d "${repo_root}/.carbon-local/workbench-science-checks.XXXXXX")"
echo "Workbench diagnostic copy and artifacts: ${scratch}"
mkdir -p "${scratch}/Business/Carbon_Fit" "${scratch}/.agent"
# Source tests intentionally rebuild release/schema files. Preserve fixture bytes
# and run them only in this disposable copy; no newline or fixture normalization.
cp -a "${repo_root}/Business/Carbon_Fit/workbench" "${scratch}/Business/Carbon_Fit/"
cp "${repo_root}/.agent/WAVE_C.md" "${scratch}/.agent/WAVE_C.md"
# The existing operational rehearsal resolves Carbon from its own source root.
ln -s "${repo_root}/carbon" "${scratch}/carbon"
workbench="${scratch}/Business/Carbon_Fit/workbench"

node --test "${workbench}"/tests/test_*.cjs
"${python}" -m pytest -q \
  "${workbench}/tests/test_sources.py" \
  "${workbench}/tests/test_authoring_bridge.py" \
  "${repo_root}/tests/cpu/test_workbench_science.py" \
  "${repo_root}/tests/cpu/test_workbench_science_http.py"
"${python}" "${workbench}/tools/build.py" \
  --output-directory "${scratch}/artifacts/offline"
"${python}" "${workbench}/tools/build.py" --private-science \
  --output-directory "${scratch}/artifacts/private"
echo "Workbench checks passed; retained artifacts: ${scratch}/artifacts"
