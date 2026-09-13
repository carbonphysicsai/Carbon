#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "Carbon C-03 service acceptance failed: $*" >&2
  exit 2
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
manifest="${CARBON_C03_IMAGE_MANIFEST:-${repo_root}/.carbon-artifacts/c03-worker-image.json}"

case "$(uname -s):$(uname -m)" in
  Linux:x86_64) ;;
  Darwin:arm64)
    echo "Docker Desktop smoke is diagnostic; required acceptance remains Linux x86-64."
    ;;
  *) fail "worker service tests require Linux x86-64 or diagnostic Docker Desktop on Apple silicon." ;;
esac
command -v docker >/dev/null 2>&1 || fail "Docker is unavailable."
[[ -f "${manifest}" ]] || fail "exact worker image manifest is missing."

cd "${repo_root}"
export PYTHONPATH="${repo_root}/tests/cpu:${repo_root}"
export CARBON_C03_IMAGE_MANIFEST="${manifest}"
export CARBON_C03_TRACE_PATH="${repo_root}/.carbon-artifacts/c03-service-traces.jsonl"
: >> "${CARBON_C03_TRACE_PATH}"
python_path="${repo_root}/.venv/bin/python"
if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  python_path="${repo_root}/.venv-jax-macos/bin/python"
fi
[[ -x "${python_path}" ]] || fail "run the existing platform setup first."
if [[ "$#" -eq 0 ]]; then
  set -- tests/service/test_c03_worker_service.py
fi
"${python_path}" -m pytest -q \
  --junitxml "${repo_root}/.carbon-artifacts/c03-service-junit.xml" "$@"
