#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "Carbon C-07 DEVELOPMENT vertical failed: $*" >&2
  exit 2
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
manifest="${repo_root}/.carbon-artifacts/c03-worker-image.json"
state_root="${repo_root}/.carbon-local/c07-development"

[[ "$#" -eq 0 ]] || fail "usage: ./scripts/dev/c07_development_vertical.sh"
command -v openssl >/dev/null 2>&1 || fail "OpenSSL is unavailable."
[[ -f "${manifest}" ]] || "${script_dir}/c03_worker_image.sh" "${manifest}"
mkdir -p "${state_root}"
run_root="$(mktemp -d "${state_root}/run.XXXXXXXX")"
development_key="$(openssl rand -hex 32)"

CARBON_C03_IMAGE_MANIFEST="${manifest}" \
CARBON_C03_TRACE_PATH="${run_root}/service-traces.jsonl" \
CARBON_C03_JUNIT_PATH="${run_root}/service-junit.xml" \
CARBON_C07_DEVELOPMENT_SIGNING_KEY_HEX="${development_key}" \
CARBON_C07_REPORT_ROOT="${run_root}/report" \
  "${script_dir}/c03_worker_service.sh" \
  tests/service/test_c07_orchestration_service.py \
  --basetemp "${run_root}/pytest"

unset development_key
echo "Retained C-07 non-official DEVELOPMENT report under ${run_root}"
