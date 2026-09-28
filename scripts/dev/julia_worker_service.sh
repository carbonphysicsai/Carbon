#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
cd "${repo_root}"
export CARBON_JULIA_WORKER_MANIFEST="${CARBON_JULIA_WORKER_MANIFEST:-${repo_root}/.carbon-artifacts/julia-worker-image.json}"
export CARBON_JULIA_TRACE_PATH="${CARBON_JULIA_TRACE_PATH:-${repo_root}/.carbon-artifacts/julia-service-traces.jsonl}"
export CARBON_AUTHORED_JULIA_IMAGE_ROOT="${CARBON_AUTHORED_JULIA_IMAGE_ROOT:-${repo_root}/.carbon-artifacts/authored-julia-images}"
[[ -s "${CARBON_JULIA_WORKER_MANIFEST}" ]] || { echo 'Build the exact Julia worker before service acceptance.' >&2; exit 2; }
# Reuse the published precompiled depot when it is for these Julia inputs. Its
# identity is Julia inputs only (julia_depot.depot_digest), so it survives
# commits that do not touch them. A read token, when given, reaches docker over
# stdin only. No lock for these inputs, a failed sign-in, a failed pull or a
# failed check records nothing, and the suite then builds the depot cold.
# The sign-in lasts only as long as the adopt: it is removed right after, and
# by the trap if adopt itself fails, so the service tests never run with it.
if [[ -n "${GHCR_READ_TOKEN:-}" ]]; then
  trap 'docker logout ghcr.io >/dev/null 2>&1 || true' EXIT
  printf '%s' "${GHCR_READ_TOKEN}" | docker login ghcr.io -u "${GITHUB_ACTOR:-carbon-ci}" --password-stdin >/dev/null 2>&1 \
    || echo 'Julia depot registry sign-in failed; the depot will be built if it cannot be pulled.'
fi
"${repo_root}/.venv/bin/python" "${repo_root}/scripts/dev/julia_depot.py" adopt \
  --root "${CARBON_AUTHORED_JULIA_IMAGE_ROOT}/depot"
if [[ -n "${GHCR_READ_TOKEN:-}" ]]; then
  docker logout ghcr.io >/dev/null 2>&1 || true
  trap - EXIT
fi
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_julia_science_service.py \
  -k 'registered_julia or existing_c04_controller' -q
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_julia_miner_research.py -q
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_authored_julia_service.py -q
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_julia_sciml_environments.py -q
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_mcp_tasks_native_julia.py -q
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_advection_science_service.py -q
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_julia_workbench.py -q
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_workbench_host_process.py -q
"${repo_root}/.venv/bin/python" -m pytest tests/service/test_julia_envelope_worker.py -q
