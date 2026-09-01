#!/usr/bin/env bash
set -euo pipefail

canonical_marker="ubuntu-24.04-glibc-cpython-3.11.16-uv-0.12.7-amd64"
canonical_marker_path="/etc/carbon-canonical-environment"
trusted_system_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/dev/canonical.sh [--dry-run] <command> [args...]
  ./scripts/dev/canonical.sh [--dry-run] --focused <pytest target> [args...]
  ./scripts/dev/canonical.sh [--dry-run] --full
  ./scripts/dev/canonical.sh [--dry-run] --interactive

Validation commands run directly only inside the exact pinned Carbon container.
Every other host uses the pinned linux/amd64 image and an isolated writable copy
of the read-only host worktree. Interactive mode is the explicit guarded mode
that mounts the live worktree and shared Git metadata read/write.
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

is_trusted_root_executable() {
  local executable="$1"
  local identity
  identity="$(/usr/bin/stat -Lc '%u:%g:%A' "${executable}" 2>/dev/null || true)"
  [[ "${identity}" == 0:0:* ]] || return 1
  local permissions="${identity##*:}"
  [[ "${permissions:5:1}" != "w" && "${permissions:8:1}" != "w" ]]
}

report_identity_miss() {
  if [[ "${CARBON_CANONICAL_IDENTITY_DIAGNOSTICS:-}" == "1" ]]; then
    echo "Carbon canonical identity mismatch: $*" >&2
  fi
  return 0
}

is_exact_canonical_environment() {
  [[ -f /.dockerenv ]] \
    || { report_identity_miss "/.dockerenv is missing"; return 1; }
  [[ "${CARBON_CANONICAL_DEV_ENV:-}" == "${canonical_marker}" ]] \
    || { report_identity_miss "environment marker differs"; return 1; }
  [[ -f "${canonical_marker_path}" ]] \
    || { report_identity_miss "marker file is missing"; return 1; }
  [[ "$(/usr/bin/stat -c '%u:%g:%a' "${canonical_marker_path}" 2>/dev/null || true)" == "0:0:444" ]] \
    || { report_identity_miss "marker ownership or mode differs"; return 1; }
  [[ "$(/usr/bin/cat "${canonical_marker_path}" 2>/dev/null || true)" == "${canonical_marker}" ]] \
    || { report_identity_miss "marker content differs"; return 1; }
  [[ "$(/usr/bin/uname -s 2>/dev/null || true)" == "Linux" ]] \
    || { report_identity_miss "kernel differs"; return 1; }
  [[ "$(/usr/bin/uname -m 2>/dev/null || true)" == "x86_64" ]] \
    || { report_identity_miss "architecture differs"; return 1; }
  [[ "$(/usr/bin/id -u 2>/dev/null || true)" == "1000" ]] \
    || { report_identity_miss "UID differs"; return 1; }
  [[ "$(/usr/bin/id -g 2>/dev/null || true)" == "1000" ]] \
    || { report_identity_miss "GID differs"; return 1; }
  [[ "$(/usr/bin/id -un 2>/dev/null || true)" == "ubuntu" ]] \
    || { report_identity_miss "user name differs"; return 1; }
  [[ -r /etc/os-release ]] \
    || { report_identity_miss "OS release is unreadable"; return 1; }
  (
    # shellcheck disable=SC1091
    source /etc/os-release
    [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]]
  ) || { report_identity_miss "OS release differs"; return 1; }
  [[ "$(/usr/local/bin/uv --version 2>/dev/null || true)" == "uv 0.12.7" ]] \
    || { report_identity_miss "uv version differs"; return 1; }
  [[ "$(/usr/local/bin/python3 --version 2>/dev/null || true)" == "Python 3.11.16" ]] \
    || { report_identity_miss "Python version differs"; return 1; }
  local executable
  for executable in \
    /usr/bin/cat /usr/bin/git /usr/bin/id /usr/bin/stat /usr/bin/uname \
    /usr/local/bin/python3 /usr/local/bin/uv; do
    is_trusted_root_executable "${executable}" \
      || { report_identity_miss "untrusted executable ${executable}"; return 1; }
  done
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
  interactive) requested_command=(/usr/bin/bash --noprofile --norc -i) ;;
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
[[ "${git_root}" == "${repo_root}" ]] \
  || fail "wrapper must belong to the Carbon repository root."

if is_exact_canonical_environment; then
  cd "${repo_root}"
  export PATH="${trusted_system_path}"
  direct_git_dir="$(/usr/bin/git rev-parse --path-format=absolute --git-dir)"
  if [[ "${mode}" == "interactive" ]]; then
    [[ -w "${repo_root}" && -w "${direct_git_dir}" ]] \
      || fail "interactive mode requires an explicitly writable live worktree and Git metadata."
  else
    [[ "${CARBON_CANONICAL_VALIDATION_COPY:-}" == "1" ]] \
      || fail "validation direct mode requires the wrapper's isolated Docker checkout."
    [[ ! -w "${direct_git_dir}" ]] \
      || fail "validation direct mode refuses writable shared Git metadata."
    export GIT_OPTIONAL_LOCKS=0
  fi
  if [[ "${dry_run}" == true ]]; then
    printf 'DIRECT_AFTER_BOOTSTRAP_DOCTOR '
    print_command "${requested_command[@]}"
    exit 0
  fi
  ./scripts/dev/bootstrap.sh
  ./scripts/dev/doctor.sh
  export PATH="${repo_root}/.venv/bin:${trusted_system_path}"
  exec "${requested_command[@]}"
fi

docker_command="docker"
dockerfile_id="$(git -C "${repo_root}" hash-object .devcontainer/Dockerfile)"
image_tag="carbon-canonical:${dockerfile_id:0:16}"
git_common_dir="$(git -C "${repo_root}" rev-parse --path-format=absolute --git-common-dir)"
volume_identity="$(
  printf '%s\0%s' "${git_common_dir}" "${repo_root}" \
    | git -C "${repo_root}" hash-object --stdin
)"
venv_volume="carbon-canonical-venv-${volume_identity:0:16}"
uv_cache_volume="carbon-canonical-uv-cache-v1"

for mount_path in "${repo_root}" "${repo_root}/.git" "${git_common_dir}"; do
  case "${mount_path}" in
    *','*|*$'\n'*) fail "Docker bind-mount paths may not contain commas or newlines." ;;
  esac
done

build_command=(
  "${docker_command}" build
  --platform linux/amd64
  --pull
  --file "${repo_root}/.devcontainer/Dockerfile"
  --tag "${image_tag}"
  "${repo_root}"
)

build_run_command() {
  local image_reference="$1"
  run_command=(
    "${docker_command}" run --rm
    --platform linux/amd64
    --user 1000:1000
    --workdir /workspaces/Carbon
    --env HOME=/home/ubuntu
    --env "PATH=${trusted_system_path}"
    --env "CARBON_CANONICAL_DEV_ENV=${canonical_marker}"
    --env GIT_CONFIG_COUNT=1
    --env GIT_CONFIG_KEY_0=safe.directory
    --env GIT_CONFIG_VALUE_0=/workspaces/Carbon
    --mount "type=volume,source=${uv_cache_volume},target=/home/ubuntu/.cache/uv"
  )

  if [[ "${mode}" == "interactive" ]]; then
    run_command+=(
      --interactive --tty
      --mount "type=bind,source=${repo_root},target=/workspaces/Carbon"
      --mount "type=volume,source=${venv_volume},target=/workspaces/Carbon/.venv"
    )
    if [[ -f "${repo_root}/.git" ]]; then
      run_command+=(--mount "type=bind,source=${git_common_dir},target=${git_common_dir}")
    fi
  else
    run_command+=(
      --env GIT_OPTIONAL_LOCKS=0
      --env CARBON_CANONICAL_VALIDATION_COPY=1
      --mount "type=bind,source=${repo_root},target=/carbon-source,readonly"
      --mount "type=bind,source=${repo_root}/.git,target=/workspaces/Carbon/.git,readonly"
    )
    if [[ -f "${repo_root}/.git" ]]; then
      run_command+=(
        --mount "type=bind,source=${git_common_dir},target=${git_common_dir},readonly"
      )
    fi
  fi
  if [[ -n "${QUALITY_BASE_SHA:-}" ]]; then
    run_command+=(--env "QUALITY_BASE_SHA=${QUALITY_BASE_SHA}")
  fi
  if [[ -n "${CARBON_UV_GROUPS:-}" ]]; then
    run_command+=(--env "CARBON_UV_GROUPS=${CARBON_UV_GROUPS}")
  fi

  if [[ "${mode}" == "interactive" ]]; then
    run_command+=(
      "${image_reference}"
      /usr/bin/bash -lc 'set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
marker=/etc/carbon-canonical-environment
[[ -f /.dockerenv ]]
[[ "$(/usr/bin/stat -c "%u:%g:%a" "${marker}")" == "0:0:444" ]]
[[ "$(/usr/bin/cat "${marker}")" == "${CARBON_CANONICAL_DEV_ENV}" ]]
[[ -w /workspaces/Carbon ]] || { echo "Live worktree is not writable by canonical UID/GID 1000:1000." >&2; exit 2; }
git_dir="$(git rev-parse --path-format=absolute --git-dir)"
[[ -w "${git_dir}" ]] || { echo "Live Git metadata is not writable by canonical UID/GID 1000:1000." >&2; exit 2; }
./scripts/dev/bootstrap.sh
./scripts/dev/doctor.sh
export PATH="/workspaces/Carbon/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
exec "$@"'
      carbon-canonical
      "${requested_command[@]}"
    )
  else
    run_command+=(
      "${image_reference}"
      /usr/bin/bash -lc 'set -euo pipefail
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
marker=/etc/carbon-canonical-environment
[[ -f /.dockerenv ]]
[[ "$(/usr/bin/stat -c "%u:%g:%a" "${marker}")" == "0:0:444" ]]
[[ "$(/usr/bin/cat "${marker}")" == "${CARBON_CANONICAL_DEV_ENV}" ]]
shopt -s dotglob nullglob
for entry in /carbon-source/*; do
  name="${entry##*/}"
  case "${name}" in
    .git|.venv) continue ;;
  esac
  cp -R --no-dereference --preserve=mode,timestamps,links -- "${entry}" /workspaces/Carbon/
done
cd /workspaces/Carbon
./scripts/dev/bootstrap.sh
./scripts/dev/doctor.sh
export PATH="/workspaces/Carbon/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
exec "$@"'
      carbon-canonical
      "${requested_command[@]}"
    )
  fi
}

if [[ "${dry_run}" == true ]]; then
  build_run_command 'sha256:<immutable-image-id-from-build>'
  printf 'BUILD '
  print_command "${build_command[@]}"
  printf 'RUN_AFTER_BUILD_BY_IMMUTABLE_ID '
  print_command "${run_command[@]}"
  exit 0
fi

command -v "${docker_command}" >/dev/null 2>&1 \
  || fail "Docker is unavailable; install/start Docker or enter the Carbon Dev Container."
"${docker_command}" info >/dev/null 2>&1 \
  || fail "Docker is installed but unavailable; start the daemon or enter the Carbon Dev Container."

echo "==> building/revalidating pinned Carbon image ${image_tag} with Docker cache"
"${build_command[@]}"
image_id="$("${docker_command}" image inspect --format '{{.Id}}' "${image_tag}")"
[[ "${image_id}" =~ ^sha256:[0-9a-f]{64}$ ]] \
  || fail "Docker returned an invalid immutable image ID for ${image_tag}."
image_contract="$(
  "${docker_command}" image inspect \
    --format '{{.Os}}|{{.Architecture}}|{{.Config.User}}|{{index .Config.Labels "org.opencontainers.image.carbon.canonical-marker"}}' \
    "${image_id}"
)"
[[ "${image_contract}" == "linux|amd64|ubuntu|${canonical_marker}" ]] \
  || fail "built image identity is not the pinned Carbon contract: ${image_contract}."

build_run_command "${image_id}"
echo "==> running ${mode} command in pinned Carbon linux/amd64 environment ${image_id}"
exec "${run_command[@]}"
