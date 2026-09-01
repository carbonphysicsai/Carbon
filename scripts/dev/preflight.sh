#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
python_bin="${repo_root}/.venv/bin/python"
quality_base_ref="${QUALITY_BASE_SHA:-origin/main}"
artifact_dir="${CARBON_ARTIFACT_DIR:-${repo_root}/.carbon-artifacts}"

export VIRTUAL_ENV="${repo_root}/.venv"
export PATH="${VIRTUAL_ENV}/bin:${PATH}"

cd "${repo_root}"
mkdir -p "${artifact_dir}"

if ! quality_base="$(git rev-parse --verify --end-of-options "${quality_base_ref}^{commit}" 2>/dev/null)"; then
  echo "Carbon preflight cannot resolve QUALITY_BASE_SHA '${quality_base_ref}' to a commit." >&2
  echo "Fetch the comparison history or set QUALITY_BASE_SHA to an available commit/ref." >&2
  exit 2
fi
if ! git merge-base "${quality_base}" HEAD >/dev/null 2>&1; then
  echo "Carbon preflight cannot find a merge base between '${quality_base_ref}' and HEAD." >&2
  echo "Fetch full comparison history and ensure the refs share ancestry." >&2
  exit 2
fi

echo "==> environment doctor"
./scripts/dev/doctor.sh

echo "==> quality ratchet"
"${python_bin}" scripts/check_quality.py \
  --baseline .ci/quality-baseline.json \
  --base "${quality_base}" \
  --report "${artifact_dir}/quality.json"

echo "==> committed and local Git diff hygiene"
"${python_bin}" scripts/dev/check_diff_hygiene.py \
  --repository "${repo_root}" \
  --base "${quality_base}"

echo "Carbon fast preflight gates passed."
