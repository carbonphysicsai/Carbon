#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "Carbon environment check failed: $*" >&2
  exit 2
}

unsupported_windows() {
  cat >&2 <<'EOF'
Unsupported canonical environment:
Windows native Python is not a Carbon evidence platform.
Open the repository in the Carbon Dev Container / WSL2 environment.
EOF
  exit 2
}

kernel="$(uname -s 2>/dev/null || true)"
case "${kernel}" in
  MINGW*|MSYS*|CYGWIN*) unsupported_windows ;;
esac
if [[ "${OS:-}" == "Windows_NT" ]]; then
  unsupported_windows
fi
[[ "${kernel}" == "Linux" ]] || fail "Linux is required (found ${kernel:-unknown})."

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
cd "${repo_root}"

command -v bash >/dev/null 2>&1 || fail "bash is unavailable."
command -v git >/dev/null 2>&1 || fail "Git is unavailable."
command -v uv >/dev/null 2>&1 || fail "uv 0.12.7 is unavailable."
command -v ldd >/dev/null 2>&1 || fail "ldd is unavailable; glibc cannot be verified."
command -v getconf >/dev/null 2>&1 || fail "getconf is unavailable; glibc cannot be verified."

[[ -r /etc/os-release ]] || fail "/etc/os-release is unavailable."
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || fail "Ubuntu 24.04 is required (found ${ID:-unknown})."
[[ "${VERSION_ID:-}" == "24.04" ]] || fail "Ubuntu 24.04 is required (found ${VERSION_ID:-unknown})."

glibc_version="$(getconf GNU_LIBC_VERSION 2>/dev/null || true)"
[[ "${glibc_version}" == glibc\ * ]] || fail "GNU glibc is required; musl is unsupported."
ldd --version 2>&1 | head -n 1 | grep -Eqi 'glibc|GNU libc' \
  || fail "ldd does not report GNU glibc; musl is unsupported."

architecture="$(uname -m)"
[[ "${architecture}" == "x86_64" ]] \
  || fail "linux/amd64 is the only currently qualified development architecture (found ${architecture})."

git_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "${git_root}" ]] || fail "the current directory is not inside a Git repository."
git_root="$(CDPATH= cd -- "${git_root}" && pwd -P)"
[[ "${git_root}" == "${repo_root}" ]] || fail "repository root mismatch: ${git_root}."

if grep -qi microsoft /proc/sys/kernel/osrelease 2>/dev/null; then
  case "${repo_root}" in
    /mnt/[a-zA-Z]/*)
      fail "WSL repositories must live in the Linux filesystem, not under /mnt/<drive>."
      ;;
  esac
fi

[[ -f .devcontainer/Dockerfile ]] || fail "canonical dev-container Dockerfile is missing."
[[ -f .devcontainer/devcontainer.json ]] || fail "canonical dev-container metadata is missing."
if [[ -e /.dockerenv ]]; then
  [[ "${CARBON_CANONICAL_DEV_ENV:-}" == "ubuntu-24.04-glibc-cpython-3.11.16-uv-0.12.7-amd64" ]] \
    || fail "this container is not the pinned Carbon development image."
  [[ "$(id -un)" == "ubuntu" ]] \
    || fail "the pinned Carbon image must run as the non-root ubuntu user."
  [[ "$(id -u)" == "1000" ]] \
    || fail "the pinned Carbon image must run with UID 1000."
  [[ "$(id -g)" == "1000" ]] \
    || fail "the pinned Carbon image must run with GID 1000."
  [[ "${HOME:-}" == "/home/ubuntu" ]] \
    || fail "the pinned Carbon image must use /home/ubuntu as HOME."
elif [[ -n "${CARBON_CANONICAL_DEV_ENV:-}" ]]; then
  [[ "${CARBON_CANONICAL_DEV_ENV}" == "ubuntu-24.04-glibc-cpython-3.11.16-uv-0.12.7-amd64" ]] \
    || fail "the Carbon environment marker is invalid."
fi

actual_uv="$(uv --version)"
uv_version="${actual_uv#uv }"
uv_version="${uv_version%% *}"
if [[ "${uv_version}" != "0.12.7" ]]; then
  fail "expected the pinned uv 0.12.7 release; found ${actual_uv}."
fi

expected_python="$(tr -d '[:space:]' < .python-version)"
[[ "${expected_python}" == "3.11.16" ]] \
  || fail "expected .python-version 3.11.16; found ${expected_python}."
python_bin="${repo_root}/.venv/bin/python"
[[ -x "${python_bin}" ]] || fail "${python_bin} is missing; run ./scripts/dev/bootstrap.sh."

python_identity="$("${python_bin}" -c 'import platform, sys; print(f"{sys.implementation.name}|{platform.python_version()}|{sys.prefix}")')"
IFS='|' read -r implementation actual_python python_prefix <<< "${python_identity}"
[[ "${implementation}" == "cpython" ]] || fail "CPython is required (found ${implementation})."
[[ "${actual_python}" == "${expected_python}" ]] \
  || fail "expected CPython ${expected_python}; found ${actual_python}."
venv_root="$(CDPATH= cd -- "${repo_root}/.venv" && pwd -P)"
python_prefix="$(CDPATH= cd -- "${python_prefix}" && pwd -P)"
[[ "${python_prefix}" == "${venv_root}" ]] \
  || fail "the project interpreter does not belong to ${venv_root}."
if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  active_venv="$(CDPATH= cd -- "${VIRTUAL_ENV}" 2>/dev/null && pwd -P || true)"
  [[ "${active_venv}" == "${venv_root}" ]] \
    || fail "VIRTUAL_ENV points outside the Carbon project environment."
fi

uv lock --check >/dev/null
sync_args=(--locked --check --group dev)
for group in ${CARBON_UV_GROUPS:-}; do
  case "${group}" in
    science-jax|science-torch|chain) sync_args+=(--group "${group}") ;;
    *) fail "unsupported CARBON_UV_GROUPS entry: ${group}." ;;
  esac
done
uv sync "${sync_args[@]}" >/dev/null
uv pip check --python "${python_bin}" >/dev/null

outside_tree="$(mktemp -d)"
trap 'rm -rf -- "${outside_tree}"' EXIT
(
  cd "${outside_tree}"
  "${python_bin}" -I -c '
import importlib.metadata
import carbon

assert carbon.__version__ == "0.9.0"
distribution = importlib.metadata.distribution("carbon")
assert distribution.metadata["Name"] == "carbon"
assert distribution.version == "0.9.0"
'
)

echo "Carbon canonical environment is valid:"
echo "  OS:           Ubuntu ${VERSION_ID} / ${glibc_version}"
echo "  architecture: linux/amd64"
echo "  Python:       CPython ${actual_python}"
echo "  uv:           0.12.7"
echo "  environment:  ${venv_root}"
echo "  repository:   ${repo_root}"
echo "  lock/groups:  current (dev${CARBON_UV_GROUPS:+ ${CARBON_UV_GROUPS}})"
echo "  package:      carbon 0.9.0 import/distribution verified outside tree"
