#!/usr/bin/env bash
set -euo pipefail
# Never write bytecode into the checkout: a development candidate refuses
# an ignored runtime source such as carbon/**/__pycache__ (M1, 2026-10-21).
export PYTHONDONTWRITEBYTECODE=1

fail() {
  echo "Carbon C-03 worker image build failed: $*" >&2
  exit 2
}

[[ "$#" -le 1 ]] || fail "usage: ./scripts/dev/c03_worker_image.sh [output-manifest]"
command -v docker >/dev/null 2>&1 || fail "Docker is unavailable."

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# No script assumes a system python3 (resolve_python.sh): the checkout's venv python, else python3, else python.
PYTHON="$(bash "${script_dir}/resolve_python.sh")" || exit 2
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
output="${1:-${repo_root}/.carbon-artifacts/c03-worker-image.json}"
dockerfile="${repo_root}/.devcontainer/Dockerfile.reconstruction-worker"
base_digest="sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517"

[[ "$(git -C "${repo_root}" status --porcelain=v1 --untracked-files=all)" == "" ]] \
  || fail "the source checkout must be clean before image identity is assigned."

mkdir -p "$(dirname -- "${output}")"
temporary="$(mktemp -d)"
proxy_pid=""
stop_apt_proxy() {
  [[ -z "${proxy_pid}" ]] || kill "${proxy_pid}" >/dev/null 2>&1 || true
  proxy_pid=""
}
trap 'stop_apt_proxy; rm -rf "${temporary}"' EXIT

# The digest of the worker build inputs only (carbon/reconstruction/worker/build_inputs.txt), not the whole repository:
# a change outside them (scripts/, docs/, tests/ ...) no longer moves any image id. The checkout is still clean as a whole.
# A git-ignored file under the inputs would enter the build context and the wheel without being bound by the digest.
# These two programs live in carbon/reconstruction/worker/, beside that package's own `operator.py`. Run as a script,
# Python puts the script's directory first on sys.path, so `import ast` -> `enum` -> `from operator import or_` found
# THAT file instead of the standard library's and failed (reported as a stale list). `-I` (isolated mode: neither the
# script's directory, the working directory, PYTHON* variables nor the user site on sys.path; every Python 3 has it,
# unlike `-P`, 3.11+ only, and the interpreter here may be a host python3) keeps the shadow out; `-B` restores what the
# ignored PYTHONDONTWRITEBYTECODE export above would have done (isolated mode ignores the environment).
build_inputs_program="${repo_root}/carbon/reconstruction/worker/build_inputs.py"
# The carbon files the image carries are GENERATED from the container's own imports (image_modules.py); a stale list,
# build-inputs file or Dockerfile allow-list would build an image whose digest does not describe it.
image_modules_program="${repo_root}/carbon/reconstruction/worker/image_modules.py"
stale_generated="$("${PYTHON}" -I -B "${image_modules_program}" check "${repo_root}")" \
  || fail "the generated worker image files are stale or the check could not run (run: python -I -B carbon/reconstruction/worker/image_modules.py generate): ${stale_generated//$'\n'/ }"
ignored_inputs="$("${PYTHON}" -I -B "${build_inputs_program}" ignored "${repo_root}")" \
  || fail "git-ignored files under the worker build inputs would enter the image unbound by its digest: ${ignored_inputs//$'\n'/ }"
source_tree_digest="$("${PYTHON}" -I -B "${build_inputs_program}" digest "${repo_root}")" \
  || fail "could not compute the worker build-inputs digest."
[[ "${source_tree_digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "the worker build-inputs digest is malformed."
lock_digest="sha256:$(shasum -a 256 "${repo_root}/uv.lock" | cut -d' ' -f1)"
recipe_digest="sha256:$(shasum -a 256 "${dockerfile}" | cut -d' ' -f1)"
entrypoint_digest="sha256:$(shasum -a 256 "${repo_root}/carbon/reconstruction/worker/entrypoint.py" | cut -d' ' -f1)"
tag="$(bash "$(dirname -- "${BASH_SOURCE[0]}")/worker_parent_tag.sh" "${CARBON_WORKER_PARENT_VARIANT:-cpu}" "${source_tree_digest}")"

# The build context is STAGED: a directory holding exactly the build inputs, exported from HEAD (image_modules.py stage).
# BuildKit reads the Dockerfile-specific .dockerignore and a legacy builder (Docker without buildx) does not; a staged
# context needs neither, so every builder gives the same image and the source digest above describes its context.
context="${temporary}/context"
"${PYTHON}" -I -B "${image_modules_program}" stage "${repo_root}" "${context}" \
  || fail "could not stage the build context from the build inputs."

# Ubuntu's archive from ONE dated snapshot (scripts/dev/apt_snapshot_proxy.py). The native mesh lock pins exact package
# versions and bytes. When noble-updates replaces one (17 Nov 2026: mesa 25.2.8-0ubuntu0.24.04.4 -> .5) the live index
# no longer lists it, so the pinned install cannot resolve. The lock, the install script and the Dockerfile are build
# inputs and stay byte-identical. This script is not a build input, so the snapshot only changes where apt fetches the
# same signed index and sha256-checked packages, not the image identity. Docker passes the predefined `http_proxy` build
# argument to RUN steps without recording it in the image or its history. How the build reaches the proxy:
#   loopback (native Linux dockerd: CI, a Linux box, WSL docker): the proxy listens on 127.0.0.1 and the build uses the
#            host network.
#   gateway  (Docker Desktop on Mac/Windows, rootless dockerd: their "host" network is not this machine's loopback):
#            the proxy listens on every interface but answers only loopback/private clients, and the build reaches it
#            as `carbon-apt-proxy` through Docker's host-gateway.
# The mode is detected from `docker info`; CARBON_APT_PROXY_MODE=loopback|gateway overrides it. A remote DOCKER_HOST
# cannot reach this machine's proxy either way; apt then fails at `apt-get update` (closed: no image).
# CARBON_APT_SNAPSHOT=live builds against the live archive (no proxy), as before.
apt_snapshot="${CARBON_APT_SNAPSHOT:-20261116T000000Z}"
apt_build_args=()
if [[ "${apt_snapshot}" != "live" ]]; then
  [[ "${apt_snapshot}" =~ ^[0-9]{8}T[0-9]{6}Z$ ]] || fail "CARBON_APT_SNAPSHOT must be YYYYMMDDTHHMMSSZ or live."
  apt_proxy_mode="${CARBON_APT_PROXY_MODE:-}"
  if [[ -z "${apt_proxy_mode}" ]]; then
    docker_engine="$(docker info --format '{{.OperatingSystem}} {{json .SecurityOptions}}' 2>/dev/null || true)"
    case "${docker_engine}" in
      *"Docker Desktop"* | *rootless*) apt_proxy_mode="gateway" ;;
      *) apt_proxy_mode="loopback" ;;
    esac
  fi
  [[ "${apt_proxy_mode}" == "loopback" || "${apt_proxy_mode}" == "gateway" ]] \
    || fail "CARBON_APT_PROXY_MODE must be loopback or gateway."
  "${PYTHON}" -I "${script_dir}/apt_snapshot_proxy.py" "${apt_snapshot}" 0 "${apt_proxy_mode}" \
    > "${temporary}/apt-proxy-port" 2> "${temporary}/apt-proxy.log" &
  proxy_pid="$!"
  for _ in $(seq 1 100); do
    [[ -s "${temporary}/apt-proxy-port" ]] && break
    kill -0 "${proxy_pid}" 2>/dev/null || break
    sleep 0.1
  done
  apt_proxy_port="$(head -n 1 "${temporary}/apt-proxy-port" 2>/dev/null | tr -d '[:space:]')"
  [[ "${apt_proxy_port}" =~ ^[0-9]+$ ]] \
    || fail "the apt snapshot proxy did not start: $(tr '\n' ' ' < "${temporary}/apt-proxy.log")"
  if [[ "${apt_proxy_mode}" == "loopback" ]]; then
    apt_proxy="http://127.0.0.1:${apt_proxy_port}"
    apt_build_args=(--network host)
  else
    apt_proxy="http://carbon-apt-proxy:${apt_proxy_port}"
    apt_build_args=(--add-host "carbon-apt-proxy:host-gateway")
  fi
  apt_build_args+=(--build-arg "http_proxy=${apt_proxy}" --build-arg "HTTP_PROXY=${apt_proxy}")
  echo "Carbon C-03 worker image: apt from snapshot.ubuntu.com ${apt_snapshot} (${apt_proxy_mode})"
fi
docker build \
  --platform linux/amd64 \
  --pull \
  ${apt_build_args[@]+"${apt_build_args[@]}"} \
  --file "${context}/.devcontainer/Dockerfile.reconstruction-worker" \
  --build-arg "SOURCE_TREE_DIGEST=${source_tree_digest}" \
  --build-arg "LOCK_DIGEST=${lock_digest}" \
  --build-arg "BASE_IMAGE_DIGEST=${base_digest}" \
  --build-arg "BUILD_RECIPE_DIGEST=${recipe_digest}" \
  --build-arg "ENTRYPOINT_DIGEST=${entrypoint_digest}" \
  --iidfile "${temporary}/iid" \
  --tag "${tag}" \
  "${context}"
stop_apt_proxy

image_id="$(tr -d '[:space:]' < "${temporary}/iid")"
[[ "${image_id}" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "Docker returned an invalid image ID."
docker image inspect "${image_id}" --format '{{json .}}' > "${temporary}/inspect.json"
docker create --name "carbon-c03-manifest-${image_id:7:12}" "${image_id}" > "${temporary}/container-id"
manifest_container="$(tr -d '[:space:]' < "${temporary}/container-id")"
cleanup_manifest_container() {
  docker rm --force "${manifest_container}" >/dev/null 2>&1 || true
}
trap 'cleanup_manifest_container; rm -rf "${temporary}"' EXIT
docker cp "${manifest_container}:/opt/carbon/worker-image-build.json" "${temporary}/build.json"

"${PYTHON}" - "${temporary}/inspect.json" "${temporary}/build.json" "${output}" <<'PY'
import json
import pathlib
import sys

inspect = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
build = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
if inspect.get("Os") != "linux" or inspect.get("Architecture") != "amd64":
    raise SystemExit("worker image is not linux/amd64")
if inspect.get("Config", {}).get("User") != "65532:65532":
    raise SystemExit("worker image user is not exact numeric non-root")
payload = {
    "schema": "carbon.c03.worker-image.v1",
    "image_id": inspect["Id"],
    "config_digest": inspect["Id"],
    **{key: value for key, value in build.items() if key != "schema"},
}
path = pathlib.Path(sys.argv[3])
path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY

cleanup_manifest_container
trap 'rm -rf "${temporary}"' EXIT
echo "Carbon C-03 worker image built and pinned:"
echo "  image:    ${image_id}"
echo "  manifest: ${output}"
