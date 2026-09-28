#!/usr/bin/env bash
# The Workbench's real-worker suites, run in the Workbench job itself.
#
# These exercise the private Workbench host and its study adapter against the
# pinned Julia worker. They also run in the isolated service job's Julia suite,
# but that job is selected only by C-03 and Julia paths, so a change to the
# Workbench host, its adapter or these tests would otherwise reach main without
# them. `workbench_scope.py` reads the test list below, so the selector cannot
# drift from what this script runs.
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
cd "${repo_root}"

export PYTHONPATH="${repo_root}/tests/cpu:${repo_root}${PYTHONPATH:+:${PYTHONPATH}}"
export CARBON_JULIA_WORKER_MANIFEST="${CARBON_JULIA_WORKER_MANIFEST:-${repo_root}/.carbon-artifacts/julia-worker-image.json}"
export CARBON_JULIA_TRACE_PATH="${CARBON_JULIA_TRACE_PATH:-${repo_root}/.carbon-artifacts/julia-service-traces.jsonl}"

echo "==> pinned C-03 worker image, then the Julia worker built on it"
./scripts/dev/c03_worker_image.sh
bash ./scripts/dev/julia_worker_image.sh
[[ -s "${CARBON_JULIA_WORKER_MANIFEST}" ]] || { echo "The Julia worker manifest was not written." >&2; exit 2; }

echo "==> Workbench host and study adapter against the real worker"
"${repo_root}/.venv/bin/python" -m pytest -q \
  tests/service/test_workbench_host.py \
  tests/service/test_julia_workbench.py \
  tests/service/test_workbench_host_process.py \
  tests/service/test_julia_envelope_worker.py \
  tests/cpu/test_workbench_science.py

echo "Workbench real-worker checks passed."
