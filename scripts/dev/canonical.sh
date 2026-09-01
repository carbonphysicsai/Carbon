#!/usr/bin/env bash
set -euo pipefail

canonical_marker="ubuntu-24.04-glibc-cpython-3.11.16-uv-0.12.7-amd64"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/dev/canonical.sh [--dry-run] <command> [args...]
  ./scripts/dev/canonical.sh [--dry-run] --focused <pytest target> [args...]
  ./scripts/dev/canonical.sh [--dry-run] --full
  ./scripts/dev/canonical.sh [--dry-run] --interactive

The command runs directly only inside the exact pinned Carbon environment.
Every other host uses the pinned linux/amd64 development image.
EOF
}

fail() {
  echo "Carbon canonical wrapper failed: $*" >&2
  exit 2
}

print_command() {
  printf '%q' "$1"
  shift
  if [[ "$#" -gt 0 ]]; then
    printf ' %q' "$@"
  fi
  printf '\n'
}

is_exact_canonical_environment() {
  [[ "${CARBON_CANONICAL_DEV_ENV:-}" == "${canonical_marker}" ]] || return 1
  [[ "$(uname -s 2>/dev/null || true)" == "Linux" ]] || return 1
  [[ "$(uname -m 2>/dev/null || true)" == "x86_64" ]] || return 1
  [[ "$(id -u 2>/dev/null || true)" == "1000" ]] || return 1
  [[ "$(id -g 2>/dev/null || true)" == "1000" ]] || return 1
  [[ "$(id -un 2>/dev/null || true)" == "ubuntu" ]] || return 1
  [[ -r /etc/os-release ]] || return 1
  (
    # shellcheck disable=SC1091
    source /etc/os-release
    [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]]
  ) || return 1
  [[ "$(uv --version 2>/dev/null || true)" == "uv 0.12.7" ]] || return 1
  [[ "$(python3 --version 2>/dev/null || true)" == "Python 3.11.16" ]] || return 1
}

dry_run=false
mode="command"
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --dry-run)
      dry_run=true
      shift
      ;;
    --focused)
      mode="focused"
      shift
      break
      ;;
    --full)
      mode="full"
      shift
      [[ "$#" -eq 0 ]] || fail "--full does not accept another command."
      break
      ;;
    --interactive)
      mode="interactive"
      shift
      [[ "$#" -eq 0 ]] || fail "--interactive does not accept another command."
      break
      ;;
    --)
      shift
      break
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *) break ;;
  esac
done

case "${mode}" in
  focused)
    [[ "$#" -gt 0 ]] || fail "--focused requires at least one pytest target."
    requested_command=(./scripts/dev/test.sh "$@")
    ;;
  full) requested_command=(./scripts/dev/ci.sh) ;;
  interactive) requested_command=(bash -l) ;;
  command)
    [[ "$#" -gt 0 ]] || {
      usage >&2
      exit 2
    }
    requested_command=("$@")
    ;;
  *) fail "unsupported wrapper mode ${mode}." ;;
esac

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
git_root="$(git -C "${repo_root}" rev-parse --show-toplevel 2>/dev/null || true)"
[[ "${git_root}" == "${repo_root}" ]] || fail "wrapper must belong to the Carbon repository root."

if is_exact_canonical_environment; then
  if [[ "${dry_run}" == true ]]; then
    printf 'DIRECT '
    print_command "${requested_command[@]}"
    exit 0
  fi
  cd "${repo_root}"
  exec "${requested_command[@]}"
fi

docker_command="docker"
dockerfile_id="$(git -C "${repo_root}" hash-object .devcontainer/Dockerfile)"
image="carbon-canonical:${dockerfile_id:0:16}"
git_common_dir="$(git -C "${repo_root}" rev-parse --path-format=absolute --git-common-dir)"
volume_identity="$(
  printf '%s\0%s' "${git_common_dir}" "${repo_root}" \
    | git -C "${repo_root}" hash-object --stdin
)"
venv_volume="carbon-canonical-venv-${volume_identity:0:16}"
uv_cache_volume="carbon-canonical-uv-cache-v1"

for mount_path in "${repo_root}" "${git_common_dir}"; do
  case "${mount_path}" in
    *','*|*$'\n'*) fail "Docker bind-mount paths may not contain commas or newlines." ;;
  esac
done

build_command=(
  "${docker_command}" build
  --platform linux/amd64
  --pull
  --file "${repo_root}/.devcontainer/Dockerfile"
  --tag "${image}"
  "${repo_root}"
)

run_command=(
  "${docker_command}" run --rm
  --platform linux/amd64
  --user 1000:1000
  --workdir /workspaces/Carbon
  --env HOME=/home/ubuntu
  --env "CARBON_CANONICAL_DEV_ENV=${canonical_marker}"
  --env GIT_CONFIG_COUNT=1
  --env GIT_CONFIG_KEY_0=safe.directory
  --env GIT_CONFIG_VALUE_0=/workspaces/Carbon
  --mount "type=bind,source=${repo_root},target=/workspaces/Carbon"
  --mount "type=volume,source=${venv_volume},target=/workspaces/Carbon/.venv"
  --mount "type=volume,source=${uv_cache_volume},target=/home/ubuntu/.cache/uv"
)

if [[ "${mode}" == "interactive" ]]; then
  run_command+=(--interactive --tty)
fi
if [[ -f "${repo_root}/.git" ]]; then
  run_command+=(
    --mount "type=bind,source=${git_common_dir},target=${git_common_dir}"
    --mount "type=bind,source=${repo_root}/.git,target=${repo_root}/.git,readonly"
  )
fi
if [[ -n "${QUALITY_BASE_SHA:-}" ]]; then
  run_command+=(--env "QUALITY_BASE_SHA=${QUALITY_BASE_SHA}")
fi
if [[ -n "${CARBON_UV_GROUPS:-}" ]]; then
  run_command+=(--env "CARBON_UV_GROUPS=${CARBON_UV_GROUPS}")
fi
run_command+=(
  "${image}"
  bash -lc 'set -euo pipefail; ./scripts/dev/bootstrap.sh; exec "$@"'
  carbon-canonical
  "${requested_command[@]}"
)

if [[ "${dry_run}" == true ]]; then
  printf 'BUILD_IF_MISSING '
  print_command "${build_command[@]}"
  printf 'RUN '
  print_command "${run_command[@]}"
  exit 0
fi

command -v "${docker_command}" >/dev/null 2>&1 \
  || fail "Docker is unavailable; install/start Docker or enter the Carbon Dev Container."
"${docker_command}" info >/dev/null 2>&1 \
  || fail "Docker is installed but unavailable; start the daemon or enter the Carbon Dev Container."

if ! "${docker_command}" image inspect "${image}" >/dev/null 2>&1; then
  echo "==> building pinned Carbon development image ${image}"
  "${build_command[@]}"
fi

echo "==> running ${mode} command in pinned Carbon linux/amd64 environment"
exec "${run_command[@]}"
