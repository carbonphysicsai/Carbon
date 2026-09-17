#!/usr/bin/env bash
set -euo pipefail

# Build images only; no GPU flag, installation on the host, or allocation.
script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
[[ "$#" -le 1 ]] || { echo 'usage: tpu_worker_image.sh [output-manifest]' >&2; exit 2; }
output="${1:-${repo_root}/.carbon-artifacts/tpu-worker-image.json}"
parent_manifest="${repo_root}/.carbon-artifacts/tpu-parent-worker-image.json"
bash "${script_dir}/c03_worker_image.sh" "${parent_manifest}"
parent="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image_id"])' "${parent_manifest}")"
source_digest="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source_tree_digest"])' "${parent_manifest}")"
[[ "${parent}" =~ ^sha256:[0-9a-f]{64}$ && "${source_digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
parent_ref="carbon-c03-worker:${source_digest:7:16}@${parent}"
recipe="${repo_root}/.devcontainer/accelerators/Dockerfile.tpu"
recipe_digest="sha256:$(sha256sum "${recipe}" | cut -d' ' -f1)"
lock_digest="sha256:$(sha256sum "${repo_root}/.devcontainer/accelerators/tpu-py311.txt" | cut -d' ' -f1)"
profile_digest="$(cd "${repo_root}" && python3 -c 'from carbon.reconstruction.accelerators import TPU_PROFILE; print(TPU_PROFILE.digest)')"
[[ "${profile_digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
temporary="$(mktemp -d)"
container=""
cleanup() {
  if [[ -n "${container}" ]]; then docker rm --force "${container}" >/dev/null; fi
  rm -rf -- "${temporary}"
}
trap cleanup EXIT
docker build --platform linux/amd64 --file "${recipe}" \
  --build-arg "WORKER_IMAGE_REF=${parent_ref}" \
  --build-arg "WORKER_IMAGE=${parent}" \
  --build-arg "ACCELERATOR_RECIPE_DIGEST=${recipe_digest}" \
  --build-arg "ACCELERATOR_PROFILE_DIGEST=${profile_digest}" \
  --build-arg "ACCELERATOR_LOCK_DIGEST=${lock_digest}" \
  --iidfile "${temporary}/iid" "${repo_root}"
image="$(tr -d '[:space:]' < "${temporary}/iid")"
[[ "${image}" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
container="$(docker create "${image}")"
docker cp "${container}:/opt/carbon/worker-image-build.json" "${temporary}/build.json"
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
echo "TPU PREPARATION worker: ${image}"
echo "Image manifest: ${output}"
