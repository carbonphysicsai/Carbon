#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "Carbon development image verification failed: $*" >&2
  exit 2
}

if [[ "$#" -ne 1 ]] || [[ -z "${1:-}" ]]; then
  fail "usage: ./scripts/dev/verify_image.sh <loaded-image-tag>"
fi

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
image="$1"
quality_base="${QUALITY_BASE_SHA:-origin/main}"
candidate_sha="$(git -C "${repo_root}" rev-parse --verify HEAD^{commit})"

command -v docker >/dev/null 2>&1 || fail "Docker is unavailable."
[[ -z "$(git -C "${repo_root}" status --porcelain=v1 --untracked-files=all)" ]] \
  || fail "the source checkout must be clean before image verification."

image_os="$(docker image inspect --format '{{.Os}}' "${image}")"
image_architecture="$(docker image inspect --format '{{.Architecture}}' "${image}")"
image_user="$(docker image inspect --format '{{.Config.User}}' "${image}")"
[[ "${image_os}" == "linux" ]] || fail "expected a Linux image; found ${image_os}."
[[ "${image_architecture}" == "amd64" ]] \
  || fail "expected a linux/amd64 image; found ${image_os}/${image_architecture}."
[[ "${image_user}" == "ubuntu" ]] \
  || fail "expected configured runtime user ubuntu; found ${image_user:-unset}."

container_id=""
cleanup() {
  if [[ -n "${container_id:-}" ]]; then
    docker rm --force "${container_id}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

container_id="$(docker create --platform linux/amd64 "${image}")"
docker cp "${repo_root}/." "${container_id}:/workspaces/Carbon"
docker start "${container_id}" >/dev/null
[[ "$(docker inspect --format '{{.State.Running}}' "${container_id}")" == "true" ]] \
  || fail "the candidate image did not remain running after startup."

docker exec --user 0:0 "${container_id}" \
  chown -R 1000:1000 /workspaces/Carbon

container_exec=(
  docker exec
  --workdir /workspaces/Carbon
  "${container_id}"
)

runtime_user="$("${container_exec[@]}" id -un)"
runtime_uid="$("${container_exec[@]}" id -u)"
runtime_gid="$("${container_exec[@]}" id -g)"
runtime_home="$("${container_exec[@]}" printenv HOME)"
runtime_marker="$("${container_exec[@]}" printenv CARBON_CANONICAL_DEV_ENV)"
runtime_architecture="$("${container_exec[@]}" uname -m)"
os_identity="$(
  "${container_exec[@]}" bash -c \
    'source /etc/os-release; printf "%s|%s" "$ID" "$VERSION_ID"'
)"
glibc_identity="$("${container_exec[@]}" getconf GNU_LIBC_VERSION)"
ldd_identity="$("${container_exec[@]}" bash -c 'ldd --version 2>&1')"
uv_identity="$("${container_exec[@]}" uv --version)"
uv_version="${uv_identity#uv }"
uv_version="${uv_version%% *}"
python_identity="$(
  "${container_exec[@]}" python -c \
    'import platform, sys; print(f"{sys.implementation.name}|{platform.python_version()}")'
)"
checkout_owner="$(
  "${container_exec[@]}" stat --format '%u:%g' /workspaces/Carbon
)"
unexpected_owner="$(
  "${container_exec[@]}" bash -c \
    'find . -xdev \( ! -uid 1000 -o ! -gid 1000 \) -print -quit'
)"
container_head="$("${container_exec[@]}" git rev-parse --verify HEAD^{commit})"
container_status="$(
  "${container_exec[@]}" git status --porcelain=v1 --untracked-files=all
)"

[[ "${runtime_user}" == "ubuntu" ]] || fail "runtime user is ${runtime_user}."
[[ "${runtime_uid}" == "1000" ]] || fail "runtime UID is ${runtime_uid}."
[[ "${runtime_gid}" == "1000" ]] || fail "runtime GID is ${runtime_gid}."
[[ "${runtime_home}" == "/home/ubuntu" ]] || fail "runtime HOME is ${runtime_home}."
[[ "${runtime_marker}" == "ubuntu-24.04-glibc-cpython-3.11.16-uv-0.12.7-amd64" ]] \
  || fail "canonical environment marker is invalid."
[[ "${runtime_architecture}" == "x86_64" ]] \
  || fail "runtime architecture is ${runtime_architecture}."
[[ "${os_identity}" == "ubuntu|24.04" ]] \
  || fail "runtime OS identity is ${os_identity}."
[[ "${glibc_identity}" == glibc\ * ]] \
  || fail "runtime userland does not report GNU glibc."
grep -Eqi 'glibc|GNU libc' <<< "${ldd_identity}" \
  || fail "runtime ldd does not report GNU glibc."
[[ "${uv_version}" == "0.12.7" ]] || fail "runtime ${uv_identity}."
[[ "${python_identity}" == "cpython|3.11.16" ]] \
  || fail "runtime Python identity is ${python_identity}."
[[ "${checkout_owner}" == "1000:1000" ]] \
  || fail "checkout root ownership is ${checkout_owner}."
[[ -z "${unexpected_owner}" ]] \
  || fail "checkout entry is not owned by UID/GID 1000: ${unexpected_owner}."
[[ "${container_head}" == "${candidate_sha}" ]] \
  || fail "container checkout is ${container_head}, expected ${candidate_sha}."
[[ -z "${container_status}" ]] || fail "container checkout is not clean."

echo "Carbon candidate image started with exact runtime identity:"
echo "  image:        ${image}"
echo "  user:         ${runtime_user} (${runtime_uid}:${runtime_gid})"
echo "  OS/userland:  Ubuntu 24.04 / ${glibc_identity}"
echo "  architecture: linux/amd64"
echo "  Python:       CPython 3.11.16"
echo "  uv:           0.12.7"
echo "  marker:       ${runtime_marker}"
echo "  candidate:    ${candidate_sha}"

"${container_exec[@]}" ./scripts/dev/bootstrap.sh
"${container_exec[@]}" ./scripts/dev/doctor.sh
docker exec \
  --workdir /workspaces/Carbon \
  --env "QUALITY_BASE_SHA=${quality_base}" \
  --env CARBON_ARTIFACT_DIR=/tmp/carbon-artifacts \
  "${container_id}" \
  ./scripts/dev/ci.sh

final_status="$(
  "${container_exec[@]}" git status --porcelain=v1 --untracked-files=all
)"
[[ -z "${final_status}" ]] \
  || fail "canonical image validation modified the tracked checkout."

echo "Carbon candidate image completed bootstrap, doctor, and canonical CI."
