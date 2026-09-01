#!/usr/bin/env bash
set -euo pipefail

unsupported_windows() {
  cat >&2 <<'EOF'
Unsupported canonical environment:
Windows native Python is not a Carbon evidence platform.
Open the repository in the Carbon Dev Container / WSL2 environment.
EOF
  exit 2
}

fail() {
  echo "Carbon bootstrap failed: $*" >&2
  exit 2
}

canonical_marker="ubuntu-24.04-glibc-cpython-3.11.16-uv-0.12.7-amd64"
canonical_marker_path="/etc/carbon-canonical-environment"

python_identity() {
  "$1" -I -c \
    'import platform, sys; print(f"{sys.implementation.name}|{platform.python_version()}")'
}

is_trusted_root_executable() {
  local executable="$1"
  local identity permissions
  identity="$(/usr/bin/stat -Lc '%u:%g:%A' "${executable}" 2>/dev/null || true)"
  [[ "${identity}" == 0:0:* ]] || return 1
  permissions="${identity##*:}"
  [[ "${permissions:5:1}" != "w" && "${permissions:8:1}" != "w" ]]
}

is_exact_carbon_image() {
  [[ -f /.dockerenv ]] || return 1
  [[ "${CARBON_CANONICAL_DEV_ENV:-}" == "${canonical_marker}" ]] || return 1
  [[ -f "${canonical_marker_path}" ]] || return 1
  [[ "$(/usr/bin/stat -c '%u:%g:%a' "${canonical_marker_path}" 2>/dev/null || true)" == "0:0:444" ]] \
    || return 1
  [[ "$(/usr/bin/cat "${canonical_marker_path}" 2>/dev/null || true)" == "${canonical_marker}" ]]
}

kernel="$(uname -s 2>/dev/null || true)"
case "${kernel}" in
  MINGW*|MSYS*|CYGWIN*) unsupported_windows ;;
esac
if [[ "${OS:-}" == "Windows_NT" ]]; then
  unsupported_windows
fi
if [[ "${kernel}" != "Linux" ]]; then
  echo "Unsupported canonical environment: Linux is required (found ${kernel:-unknown})." >&2
  exit 2
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
git_root="$(git -C "${repo_root}" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${git_root}" ]] || [[ "$(CDPATH= cd -- "${git_root}" && pwd -P)" != "${repo_root}" ]]; then
  echo "Carbon bootstrap must run from a valid Carbon repository root." >&2
  exit 2
fi

if grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null; then
  case "${repo_root}" in
    /mnt/[a-zA-Z]/*)
      cat >&2 <<'EOF'
Unsupported canonical repository location:
The Carbon repository is on a Windows-mounted WSL path.
Clone it inside the WSL/Linux filesystem (for example, /home/<user>/src/Carbon).
EOF
      exit 2
      ;;
  esac
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv 0.12.7 is required. Open the repository in the Carbon Dev Container." >&2
  exit 2
fi
actual_uv="$(uv --version)"
uv_version="${actual_uv#uv }"
uv_version="${uv_version%% *}"
if [[ "${uv_version}" != "0.12.7" ]]; then
  echo "Unsupported uv version: expected the pinned 0.12.7 release." >&2
  echo "Found: ${actual_uv}" >&2
  exit 2
fi

python_version="$(tr -d '[:space:]' < "${repo_root}/.python-version")"
if [[ "${python_version}" != "3.11.16" ]]; then
  echo "Unexpected .python-version: expected 3.11.16, found ${python_version}." >&2
  exit 2
fi

sync_args=(--locked --group dev)
for group in ${CARBON_UV_GROUPS:-}; do
  case "${group}" in
    science-jax|science-torch|chain) sync_args+=(--group "${group}") ;;
    *)
      echo "Unsupported CARBON_UV_GROUPS entry: ${group}." >&2
      echo "Allowed optional groups: science-jax science-torch chain." >&2
      exit 2
      ;;
  esac
done

cd "${repo_root}"
python_path=""
if [[ -f /.dockerenv && -n "${CARBON_CANONICAL_DEV_ENV:-}" ]] && \
  ! is_exact_carbon_image; then
  fail "the container claims a Carbon canonical identity without its root-owned marker."
fi
if is_exact_carbon_image; then
  python_path="/usr/local/bin/python3"
  is_trusted_root_executable "${python_path}" \
    || fail "the canonical image interpreter is not root-owned and non-writable."
  [[ "$(python_identity "${python_path}" 2>/dev/null || true)" == "cpython|${python_version}" ]] \
    || fail "the canonical image interpreter is not exact CPython ${python_version}."
else
  python_path="$(
    uv python find --no-project --no-python-downloads "${python_version}" \
      2>/dev/null || true
  )"
  if [[ -n "${python_path}" ]] && \
    [[ "$(python_identity "${python_path}" 2>/dev/null || true)" != "cpython|${python_version}" ]]; then
    python_path=""
  fi
  if [[ -z "${python_path}" ]]; then
    uv python install "${python_version}"
    python_path="$(
      uv python find --no-project --no-python-downloads "${python_version}"
    )"
    [[ "$(python_identity "${python_path}" 2>/dev/null || true)" == "cpython|${python_version}" ]] \
      || fail "uv did not provide exact CPython ${python_version} after installation."
  fi
fi
uv sync --python "${python_path}" "${sync_args[@]}"

echo "Carbon locked environment synchronized:"
echo "  repository: ${repo_root}"
echo "  Python:     ${python_version}"
echo "  uv:         0.12.7"
echo "  groups:     dev${CARBON_UV_GROUPS:+ ${CARBON_UV_GROUPS}}"
