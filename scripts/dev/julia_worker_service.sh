#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
cd "${repo_root}"
export CARBON_JULIA_WORKER_MANIFEST="${CARBON_JULIA_WORKER_MANIFEST:-${repo_root}/.carbon-artifacts/julia-worker-image.json}"
export CARBON_JULIA_TRACE_PATH="${CARBON_JULIA_TRACE_PATH:-${repo_root}/.carbon-artifacts/julia-service-traces.jsonl}"
[[ -s "${CARBON_JULIA_WORKER_MANIFEST}" ]] || { echo 'Build the exact Julia worker before service acceptance.' >&2; exit 2; }
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_julia_science_service.py \
  -k 'registered_julia or existing_c04_controller' -q
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_julia_miner_research.py -q
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_julia_workbench.py -q
