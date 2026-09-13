#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "Carbon C-03 worker command failed: $*" >&2
  exit 2
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
manifest="${repo_root}/.carbon-artifacts/c03-worker-image.json"
state_root="${repo_root}/.carbon-local/c03-smoke"

case "${1:-}" in
  doctor)
    [[ "$#" -eq 1 ]] || fail "usage: ./scripts/dev/c03_worker.sh doctor"
    ;;
  smoke)
    [[ "$#" -eq 1 ]] || fail "usage: ./scripts/dev/c03_worker.sh smoke"
    [[ -f "${manifest}" ]] || "${script_dir}/c03_worker_image.sh" "${manifest}"
    mkdir -p "${state_root}"
    smoke_root="$(mktemp -d "${state_root}/run.XXXXXXXX")"
    CARBON_C03_IMAGE_MANIFEST="${manifest}" \
      CARBON_C03_TRACE_PATH="${smoke_root}/c03-smoke-traces.jsonl" \
      CARBON_C03_JUNIT_PATH="${smoke_root}/c03-smoke-junit.xml" \
      "${script_dir}/c03_worker_service.sh" \
      'tests/service/test_c03_worker_service.py::test_real_jax_path_is_isolated_validated_and_numerically_identical[False-16]' \
      --basetemp "${smoke_root}/pytest"
    echo "Retained C-03 smoke evidence under ${smoke_root}"
    exit 0
    ;;
  status|reconcile)
    [[ "$#" -eq 1 ]] || fail "usage: ./scripts/dev/c03_worker.sh ${1:-status}"
    ;;
  *) fail "usage: ./scripts/dev/c03_worker.sh {doctor|smoke|status|reconcile}" ;;
esac

python_path="${repo_root}/.venv/bin/python"
if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  python_path="${repo_root}/.venv-jax-macos/bin/python"
fi
[[ -x "${python_path}" ]] \
  || fail "run the existing platform setup first; no environment was changed."

case "$1" in
  doctor)
    "${python_path}" -m carbon.reconstruction.worker.operator doctor "${manifest}"
    ;;
  status)
    "${python_path}" -m carbon.reconstruction.worker.operator status "${state_root}"
    ;;
  reconcile)
    "${python_path}" -m carbon.reconstruction.worker.operator status "${state_root}"
    "${python_path}" -m carbon.reconstruction.worker.operator reconcile "${state_root}"
    "${python_path}" -m carbon.reconstruction.worker.operator status "${state_root}"
    ;;
esac
