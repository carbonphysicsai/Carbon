#!/usr/bin/env bash
set -euo pipefail

# Push the pinned GPU worker to a registry repository you control
# (OWNER-MINER-COMPUTE-LINK-ONLY-01, LINKONLY-D8).
#
# For a container-only rental that pulls its image (an `ssh-container` setup):
# this builds the pinned GPU worker from this exact clean checkout, or takes
# the manifest you name, then tags and pushes that image, by its image ID, to
# your repository. It prints the `repository@sha256:...` reference to start
# your container from.
#
# Carbon publishes no registry and holds no registry credential. The push
# uses your own `docker login` for that registry; this script never logs in
# and never reads a credential. Nothing is started, stopped or billed.
#
# Usage: scripts/dev/push_worker_image.sh [--manifest PATH] REPOSITORY
#   REPOSITORY  registry/path you control, lowercase, with no tag or digest,
#               for example ghcr.io/you/carbon-gpu-worker
#   --manifest  an already built GPU worker manifest (by default the worker
#               is built: scripts/dev/accelerator_worker_image.sh)

usage() {
  cat <<'USAGE'
Usage: scripts/dev/push_worker_image.sh [--manifest PATH] REPOSITORY
  REPOSITORY  registry/path you control, lowercase, with no tag or digest,
              for example ghcr.io/you/carbon-gpu-worker
  --manifest  an already built GPU worker manifest (by default the worker
              is built: scripts/dev/accelerator_worker_image.sh)
USAGE
}

fail() {
  echo "push_worker_image: $*" >&2
  exit 2
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
manifest=""
repository=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --manifest)
      [[ "$#" -ge 2 ]] || fail "--manifest needs a path"
      manifest="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    -*) fail "unknown option: $1" ;;
    *)
      [[ -z "${repository}" ]] || fail "name one repository"
      repository="$1"
      shift
      ;;
  esac
done
[[ -n "${repository}" ]] || { usage >&2; exit 2; }
# registry[:port]/path, lowercase: never a tag, a digest or an option.
component='[a-z0-9]+([._-][a-z0-9]+)*'
[[ "${repository}" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:[0-9]{1,5})?(/${component})+$ ]] \
  || fail "REPOSITORY is registry/path, lowercase, with no tag or digest"
command -v docker >/dev/null 2>&1 || fail "Docker is unavailable"

if [[ -z "${manifest}" ]]; then
  manifest="${repo_root}/.carbon-artifacts/accelerator-worker-image.json"
  bash "${script_dir}/accelerator_worker_image.sh" "${manifest}"
fi
[[ -f "${manifest}" && ! -L "${manifest}" ]] || fail "no GPU worker manifest at ${manifest}"

# The manifest's image ID and source digest, and only for the pinned GPU
# worker: its lock is this checkout's accelerator lock.
lock="${repo_root}/.devcontainer/accelerators/cuda13-py311.txt"
[[ -f "${lock}" ]] || fail "this checkout has no accelerator lock"
expected_lock="sha256:$(sha256sum "${lock}" | cut -d' ' -f1)"
read -r image_id source_digest < <(
  python3 - "${manifest}" "${expected_lock}" <<'PY'
import json
import re
import sys

value = json.load(open(sys.argv[1], encoding="utf-8"))
digest = re.compile(r"sha256:[0-9a-f]{64}")
fields = (
    "image_id",
    "config_digest",
    "source_tree_digest",
    "wheel_digest",
    "lock_digest",
    "base_image_digest",
    "build_recipe_digest",
    "entrypoint_digest",
)
if (
    type(value) is not dict
    or value.get("schema") != "carbon.c03.worker-image.v1"
    or set(value) != {"schema", *fields}
    or not all(type(value[f]) is str and digest.fullmatch(value[f]) for f in fields)
):
    sys.exit("not a pinned worker manifest")
if value["lock_digest"] != sys.argv[2]:
    sys.exit("not the pinned GPU worker: its lock is not this checkout's")
print(value["image_id"], value["source_tree_digest"])
PY
) || fail "the manifest is not this checkout's pinned GPU worker"
[[ "${image_id}" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "the manifest names no image ID"
[[ "$(docker image inspect --format '{{.Id}}' "${image_id}" 2>/dev/null)" == "${image_id}" ]] \
  || fail "the pinned GPU worker ${image_id} is not built here"

tag="${repository}:carbon-gpu-worker-${source_digest:7:16}"
docker tag "${image_id}" "${tag}"
# Your own login for this registry; Carbon never asks for it.
docker push "${tag}" >/dev/null || fail "the push failed: run \`docker login\` for that registry yourself, then retry"

pushed=""
while IFS= read -r reference; do
  if [[ "${reference}" == "${repository}@sha256:"* ]] \
    && [[ "${reference#"${repository}@"}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    pushed="${reference}"
  fi
done < <(docker image inspect --format '{{range .RepoDigests}}{{println .}}{{end}}' "${image_id}")
[[ -n "${pushed}" ]] || fail "the registry returned no digest for ${repository}"

echo "Pushed the pinned GPU worker ${image_id} as ${tag}."
echo "Start your container from: ${pushed}"
echo "Carbon checks the build identity it carries (/opt/carbon/worker-image-build.json) over SSH before every practice trial."
