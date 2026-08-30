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
if [[ "${uv_version}" != "0.12.7" ]] || [[ "${actual_uv}" != *"61291a8ca"* ]]; then
  echo "Unsupported uv version: expected the 0.12.7 release at 61291a8ca." >&2
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
uv python install "${python_version}"
uv sync "${sync_args[@]}"

echo "Carbon locked environment synchronized:"
echo "  repository: ${repo_root}"
echo "  Python:     ${python_version}"
echo "  uv:         0.12.7"
echo "  groups:     dev${CARBON_UV_GROUPS:+ ${CARBON_UV_GROUPS}}"
