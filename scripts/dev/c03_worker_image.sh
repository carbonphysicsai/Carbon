#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "Carbon C-03 worker image build failed: $*" >&2
  exit 2
}

[[ "$#" -le 1 ]] || fail "usage: ./scripts/dev/c03_worker_image.sh [output-manifest]"
command -v docker >/dev/null 2>&1 || fail "Docker is unavailable."

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
output="${1:-${repo_root}/.carbon-artifacts/c03-worker-image.json}"
dockerfile="${repo_root}/.devcontainer/Dockerfile.reconstruction-worker"
base_digest="sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517"

[[ "$(git -C "${repo_root}" status --porcelain=v1 --untracked-files=all)" == "" ]] \
  || fail "the source checkout must be clean before image identity is assigned."

mkdir -p "$(dirname -- "${output}")"
temporary="$(mktemp -d)"
trap 'rm -rf "${temporary}"' EXIT

source_tree_digest="sha256:$(git -C "${repo_root}" archive --format=tar HEAD | shasum -a 256 | cut -d' ' -f1)"
lock_digest="sha256:$(shasum -a 256 "${repo_root}/uv.lock" | cut -d' ' -f1)"
recipe_digest="sha256:$(shasum -a 256 "${dockerfile}" | cut -d' ' -f1)"
entrypoint_digest="sha256:$(shasum -a 256 "${repo_root}/carbon/reconstruction/worker/entrypoint.py" | cut -d' ' -f1)"
tag="carbon-c03-worker:${source_tree_digest:7:16}"

docker build \
  --platform linux/amd64 \
  --pull \
  --file "${dockerfile}" \
  --build-arg "SOURCE_TREE_DIGEST=${source_tree_digest}" \
  --build-arg "LOCK_DIGEST=${lock_digest}" \
  --build-arg "BASE_IMAGE_DIGEST=${base_digest}" \
  --build-arg "BUILD_RECIPE_DIGEST=${recipe_digest}" \
  --build-arg "ENTRYPOINT_DIGEST=${entrypoint_digest}" \
  --iidfile "${temporary}/iid" \
  --tag "${tag}" \
  "${repo_root}"

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

python3 - "${temporary}/inspect.json" "${temporary}/build.json" "${output}" <<'PY'
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
