#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "Carbon C-03 service acceptance failed: $*" >&2
  exit 2
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
manifest="${CARBON_C03_IMAGE_MANIFEST:-${repo_root}/.carbon-artifacts/c03-worker-image.json}"
trace_path="${CARBON_C03_TRACE_PATH:-${repo_root}/.carbon-artifacts/c03-service-traces.jsonl}"
junit_path="${CARBON_C03_JUNIT_PATH:-${repo_root}/.carbon-artifacts/c03-service-junit.xml}"
report_parent="${repo_root}/.carbon-artifacts"

case "$(uname -s):$(uname -m)" in
  Linux:x86_64) ;;
  Darwin:arm64)
    echo "Docker Desktop smoke is diagnostic; required acceptance remains Linux x86-64."
    ;;
  *) fail "worker service tests require Linux x86-64 or diagnostic Docker Desktop on Apple silicon." ;;
esac
command -v docker >/dev/null 2>&1 || fail "Docker is unavailable."
command -v openssl >/dev/null 2>&1 || fail "OpenSSL is unavailable."
[[ -f "${manifest}" ]] || fail "exact worker image manifest is missing."
mkdir -p "${report_parent}"

cd "${repo_root}"
export PYTHONPATH="${repo_root}/tests/cpu:${repo_root}"
export CARBON_C03_IMAGE_MANIFEST="${manifest}"
export CARBON_C03_TRACE_PATH="${trace_path}"
export CARBON_C07_DEVELOPMENT_SIGNING_KEY_HEX="${CARBON_C07_DEVELOPMENT_SIGNING_KEY_HEX:-$(openssl rand -hex 32)}"
export CARBON_C07_REPORT_ROOT="${CARBON_C07_REPORT_ROOT:-$(mktemp -d "${report_parent}/c07-service-report.XXXXXXXX")}"
export CARBON_C10_DEVELOPMENT_SIGNING_KEY_HEX="${CARBON_C10_DEVELOPMENT_SIGNING_KEY_HEX:-$(openssl rand -hex 32)}"
export CARBON_C10_REPORT_ROOT="${CARBON_C10_REPORT_ROOT:-$(mktemp -d "${report_parent}/c10-service-report.XXXXXXXX")}"
: >> "${CARBON_C03_TRACE_PATH}"
python_path="${repo_root}/.venv/bin/python"
if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
  python_path="${repo_root}/.venv-jax-macos/bin/python"
fi
[[ -x "${python_path}" ]] || fail "run the existing platform setup first."
if [[ "$#" -eq 0 ]]; then
  set -- \
    tests/service/test_c03_worker_service.py \
    tests/service/test_c04_reference_service.py \
    tests/service/test_c05_measurement_service.py \
    tests/service/test_c07_orchestration_service.py \
    tests/service/test_c08_miner_mcp_service.py \
    tests/service/test_cw1_session_service.py \
    tests/service/test_cw1_research_carrier.py \
    tests/service/test_portable_research_state.py \
    tests/service/test_cw1_research_generation.py \
    tests/service/test_cw1_research_practice.py \
    tests/service/test_cw1_research_controls.py \
    tests/service/test_cw1_research_final_service.py \
    tests/service/test_c10_reexecution_service.py
fi
"${python_path}" -m pytest -q \
  --junitxml "${junit_path}" "$@"
