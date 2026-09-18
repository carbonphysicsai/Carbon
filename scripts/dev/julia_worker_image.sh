#!/usr/bin/env bash
set -euo pipefail

# Extend a current, clean-source C-03 build; never alter an accepted image/tag.
script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
[[ "$#" -le 1 ]] || { echo 'usage: julia_worker_image.sh [output-manifest]' >&2; exit 2; }
output="${1:-${repo_root}/.carbon-artifacts/julia-worker-image.json}"
parent_manifest="${repo_root}/.carbon-artifacts/julia-parent-worker-image.json"
bash "${script_dir}/c03_worker_image.sh" "${parent_manifest}"
parent="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image_id"])' "${parent_manifest}")"
[[ "${parent}" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
source_digest="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source_tree_digest"])' "${parent_manifest}")"
[[ "${source_digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
# A local image/config ID is not a registry manifest digest. BuildKit's classic
# store cannot resolve tag@config-ID and must not try to pull this private build.
parent_ref="carbon-julia-parent:${parent:7}"
recipe="${repo_root}/.devcontainer/Dockerfile.julia-worker"
recipe_digest="sha256:$(sha256sum "${recipe}" | cut -d' ' -f1)"
temporary="$(mktemp -d)"
container=""
cleanup() {
  if [[ -n "${container}" ]]; then docker rm --force "${container}" >/dev/null; fi
  rm -rf -- "${temporary}"
}
trap cleanup EXIT
docker tag "${parent}" "${parent_ref}"
docker image inspect "${parent_ref}" --format '{{json .}}' > "${temporary}/parent-before.json"
python3 "${script_dir}/verify_julia_build_parent.py" "${parent_manifest}" "${temporary}/parent-before.json"
docker build --pull=false --platform linux/amd64 --file "${recipe}" \
  --build-arg "WORKER_IMAGE_REF=${parent_ref}" \
  --build-arg "WORKER_IMAGE=${parent}" \
  --build-arg "JULIA_RECIPE_DIGEST=${recipe_digest}" \
  --iidfile "${temporary}/iid" "${repo_root}"
image="$(tr -d '[:space:]' < "${temporary}/iid")"
[[ "${image}" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
docker image inspect "${parent_ref}" --format '{{json .}}' > "${temporary}/parent-after.json"
python3 "${script_dir}/verify_julia_build_parent.py" "${parent_manifest}" "${temporary}/parent-after.json"
docker image inspect "${image}" --format '{{json .}}' > "${temporary}/child.json"
container="$(docker create "${image}")"
docker cp "${container}:/opt/carbon/worker-image-build.json" "${temporary}/build.json"
python3 "${script_dir}/verify_julia_build_parent.py" "${parent_manifest}" "${temporary}/parent-before.json" \
  "${temporary}/child.json" "${image}" "${temporary}/build.json" "${recipe_digest}"
mkdir -p "$(dirname -- "${output}")"
python3 - "${image}" "${temporary}/build.json" "${output}" <<'PY'
import json
import pathlib
import sys

build = json.loads(pathlib.Path(sys.argv[2]).read_text())
payload = {**build, "schema": "carbon.c03.worker-image.v1",
           "image_id": sys.argv[1], "config_digest": sys.argv[1]}
pathlib.Path(sys.argv[3]).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
PY
echo "Julia DEVELOPMENT worker: ${image}"
echo "Image manifest: ${output}"
