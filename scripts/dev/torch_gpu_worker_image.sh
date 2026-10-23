#!/usr/bin/env bash
set -euo pipefail
# Never write bytecode into the checkout: a development candidate refuses
# an ignored runtime source such as carbon/**/__pycache__ (M1, 2026-10-21).
export PYTHONDONTWRITEBYTECODE=1
# Dockerfile.gpu stamps the image's identity in heredoc RUN steps, which only
# BuildKit runs; the legacy builder skips them silently and the image keeps
# its parent's identity (M1 12g: the PyTorch GPU worker read as no
# registered GPU worker). Ask for BuildKit, and refuse a manifest whose
# identity was not stamped (below).
export DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-1}"

# The PyTorch GPU (CUDA 13) reconstruction worker image (TORCH-GPU-01),
# layered on the exact C-03 JAX worker image this checkout builds, in its own
# environment (never the JAX accelerator image's). Build only: nothing is
# installed on the host, no GPU is used and no deployment is changed.
script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
[[ "$#" -le 1 ]] || { echo 'usage: torch_gpu_worker_image.sh [output-manifest]' >&2; exit 2; }
command -v docker >/dev/null 2>&1 || { echo 'Docker is unavailable.' >&2; exit 2; }
output="${1:-${repo_root}/.carbon-artifacts/torch-gpu-worker-image.json}"
parent_manifest="${repo_root}/.carbon-artifacts/torch-gpu-parent-worker-image.json"
bash "${script_dir}/worker_parent_manifest.sh" "${parent_manifest}"
parent="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image_id"])' "${parent_manifest}")"
source_digest="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source_tree_digest"])' "${parent_manifest}")"
[[ "${parent}" =~ ^sha256:[0-9a-f]{64}$ && "${source_digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
parent_ref="$(bash "${script_dir}/worker_parent_ref.sh" "${parent}" "${source_digest}")"
# A local parent is named by tag: point the tag at the exact parent image
# first, so the child is built on that image and nothing is pulled (G-B1).
if [[ "${parent_ref}" != *@* ]]; then
  docker tag "${parent}" "${parent_ref}"
  [[ "$(docker image inspect --format '{{.Id}}' "${parent_ref}")" == "${parent}" ]]     || { echo 'The local parent tag does not name the exact parent image.' >&2; exit 2; }
fi
recipe="${repo_root}/.devcontainer/torch/Dockerfile.gpu"
recipe_digest="sha256:$(sha256sum "${recipe}" | cut -d' ' -f1)"
lock_digest="sha256:$(sha256sum "${repo_root}/.devcontainer/torch/torch-cu130-py311.txt" | cut -d' ' -f1)"
profile_digest="$(cd "${repo_root}" && python3 -c 'from carbon.reconstruction.torch_profile import GPU_PROFILE_DIGEST; print(GPU_PROFILE_DIGEST)')"
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
  --build-arg "TORCH_GPU_RECIPE_DIGEST=${recipe_digest}" \
  --build-arg "TORCH_GPU_LOCK_DIGEST=${lock_digest}" \
  --build-arg "TORCH_GPU_PROFILE_DIGEST=${profile_digest}" \
  --iidfile "${temporary}/iid" \
  --tag "carbon-torch-gpu-worker:${source_digest:7:16}" "${repo_root}"
image="$(tr -d '[:space:]' < "${temporary}/iid")"
[[ "${image}" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
container="$(docker create "${image}")"
docker cp "${container}:/opt/carbon/worker-image-build.json" "${temporary}/build.json"
mkdir -p "$(dirname -- "${output}")"
python3 - "${image}" "${temporary}/build.json" "${output}" \
  "${parent}" "${recipe_digest}" "${lock_digest}" <<'PY'
import json
import pathlib
import sys
build = json.loads(pathlib.Path(sys.argv[2]).read_text())
# Written only when the image's identity names this build's parent, recipe
# and PyTorch GPU lock, as the JAX GPU worker's build checks it.
expected = {"base_image_digest": sys.argv[4], "build_recipe_digest": sys.argv[5],
            "lock_digest": sys.argv[6]}
differs = sorted(key for key, value in expected.items() if build.get(key) != value)
if differs:
    raise SystemExit(
        "The PyTorch GPU worker image's build identity differs from this build ("
        + ", ".join(differs) + "): its identity step did not run. No manifest "
        "was written. Build again with Docker BuildKit (docker buildx, or "
        "DOCKER_BUILDKIT=1), or report this."
    )
payload = {**build, "schema": "carbon.c03.worker-image.v1",
           "image_id": sys.argv[1], "config_digest": sys.argv[1]}
pathlib.Path(sys.argv[3]).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
PY
echo "Carbon PyTorch GPU DEVELOPMENT worker: ${image}"
echo "JAX parent image: ${parent} (manifest ${parent_manifest})"
echo "Image manifest: ${output}"
