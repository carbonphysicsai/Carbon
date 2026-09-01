#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "Carbon delivery preflight failed: $*" >&2
  exit 2
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
comparison_base="${QUALITY_BASE_SHA:-}"
expected_head="${CARBON_CANDIDATE_SHA:-}"
github_output="${GITHUB_OUTPUT:-}"

[[ -n "${comparison_base}" ]] || fail "QUALITY_BASE_SHA is required."
[[ "${expected_head}" =~ ^[0-9a-f]{40}$ ]] \
  || fail "CARBON_CANDIDATE_SHA must be an exact lowercase commit SHA."

cd "${repo_root}"
actual_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ "${actual_root}" == "${repo_root}" ]] || fail "repository root mismatch."
actual_head="$(git rev-parse --verify HEAD^{commit})"
[[ "${actual_head}" == "${expected_head}" ]] \
  || fail "checkout is ${actual_head}; expected exact candidate ${expected_head}."

case "${CARBON_EVENT_NAME:-local}" in
  pull_request) ;;
  push)
    [[ "${CARBON_EVENT_REF:-}" == "refs/heads/main" ]] \
      || fail "push verification is supported only for exact main."
    [[ "${CARBON_EVENT_SHA:-}" == "${expected_head}" ]] \
      || fail "push event SHA does not equal the checked-out candidate."
    ;;
  local) ;;
  *) fail "unsupported CI event ${CARBON_EVENT_NAME}." ;;
esac

classifier_args=(
  --repository "${repo_root}"
  --base "${comparison_base}"
)
if [[ -n "${github_output}" ]]; then
  classifier_args+=(--github-output "${github_output}")
fi

echo "==> strict changed-path classification"
python3 scripts/dev/classify_changes.py "${classifier_args[@]}"

echo "==> introduced commit, identity, and tracked-text hygiene"
python3 scripts/dev/check_delivery_hygiene.py \
  --repository "${repo_root}" \
  --base "${comparison_base}"

echo "==> committed, staged, and unstaged diff hygiene"
python3 scripts/dev/check_diff_hygiene.py \
  --repository "${repo_root}" \
  --base "${comparison_base}"

echo "Carbon delivery preflight passed at exact candidate ${actual_head}."
