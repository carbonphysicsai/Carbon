#!/usr/bin/env bash
set -euo pipefail

# Build, push and record the released worker images (IMAGE-RELEASE-01).
#
# Run by the release workflow only, from a clean checkout of an exact release
# tag on main, after the workflow's own `docker login`. It builds with the
# existing scripts and nothing else:
#   - c03_worker_image.sh          the CPU C-03 worker (JAX);
#   - accelerator_worker_image.sh  the NVIDIA (CUDA 13) worker on it (JAX GPU);
#   - torch_worker_image.sh        the PyTorch CPU worker on it;
#   - torch_gpu_worker_image.sh    the PyTorch GPU (CUDA 13) worker on it, in
#                                  its own environment (TORCH-GPU-01).
# The accelerator and PyTorch scripts each rebuild the C-03 parent; the parent
# they name must be the same image as the released C-03 worker, or nothing is
# pushed. Each image is tagged `<registry>/<name>:<tag>`, pushed, and recorded
# by its registry digest (worker_image_release.py record). Hosts pull by that
# digest.
#
# Usage: release_worker_images.sh --registry REGISTRY --tag TAG --out DIR
#   REGISTRY  e.g. ghcr.io/carbonphysicsai (lowercase, no tag or digest)
#   TAG       the release tag HEAD must be, e.g. worker-images-v1
#   DIR       where the manifests and release records are written

fail() {
  echo "release_worker_images: $*" >&2
  exit 2
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
registry=""
tag=""
out=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --registry | --tag | --out)
      [[ "$#" -ge 2 ]] || fail "$1 needs a value"
      case "$1" in
        --registry) registry="$2" ;;
        --tag) tag="$2" ;;
        --out) out="$2" ;;
      esac
      shift 2
      ;;
    *) fail "unknown argument: $1" ;;
  esac
done
[[ -n "${registry}" && -n "${tag}" && -n "${out}" ]] \
  || fail "usage: release_worker_images.sh --registry REGISTRY --tag TAG --out DIR"
component='[a-z0-9]+([._-][a-z0-9]+)*'
[[ "${registry}" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:[0-9]{1,5})?(/${component})+$ ]] \
  || fail "REGISTRY is registry/path, lowercase, with no tag or digest"
[[ "${tag}" =~ ^worker-images-v[0-9]+(\.[0-9]+)*$ ]] || fail "TAG is worker-images-vN"
command -v docker >/dev/null 2>&1 || fail "Docker is unavailable"
# Released images are named by their registry digest, which is the image ID
# only under the containerd image store (worker_image_release.py IMAGE_STORE).
docker info --format '{{json .DriverStatus}}' | grep -q io.containerd.snapshotter \
  || fail "Docker must use the containerd image store"

[[ "$(git -C "${repo_root}" status --porcelain=v1 --untracked-files=all)" == "" ]] \
  || fail "the checkout must be clean"
commit="$(git -C "${repo_root}" rev-parse HEAD)"
[[ "$(git -C "${repo_root}" rev-parse "refs/tags/${tag}^{commit}")" == "${commit}" ]] \
  || fail "HEAD is not the release tag ${tag}"

artifacts="${repo_root}/.carbon-artifacts"
mkdir -p "${out}"
bash "${script_dir}/c03_worker_image.sh" "${artifacts}/c03-worker-image.json"
bash "${script_dir}/accelerator_worker_image.sh" "${artifacts}/accelerator-worker-image.json"
bash "${script_dir}/torch_worker_image.sh" "${artifacts}/torch-worker-image.json"
bash "${script_dir}/torch_gpu_worker_image.sh" "${artifacts}/torch-gpu-worker-image.json"

field() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$1" "$2"
}
c03="$(field "${artifacts}/c03-worker-image.json" image_id)"
for parent in accelerator-parent torch-parent torch-gpu-parent; do
  [[ "$(field "${artifacts}/${parent}-worker-image.json" image_id)" == "${c03}" ]] \
    || fail "the ${parent} C-03 image is not the released C-03 worker ${c03}"
done
for kind in accelerator torch torch-gpu; do
  [[ "$(field "${artifacts}/${kind}-worker-image.json" base_image_digest)" == "${c03}" ]] \
    || fail "the ${kind} worker is not built on the released C-03 worker"
done

for pair in c03:carbon-c03-worker accelerator:carbon-accelerator-worker torch:carbon-torch-worker \
  torch-gpu:carbon-torch-gpu-worker; do
  kind="${pair%%:*}"
  repository="${registry}/${pair#*:}"
  manifest="${artifacts}/${kind}-worker-image.json"
  image="$(field "${manifest}" image_id)"
  docker tag "${image}" "${repository}:${tag}"
  docker push --quiet "${repository}:${tag}" >/dev/null || fail "the push of ${kind} failed"
  python3 "${script_dir}/worker_image_release.py" record \
    --kind "${kind}" \
    --manifest "${manifest}" \
    --repository "${repository}" \
    --tag "${tag}" \
    --commit "${commit}" \
    --out "${out}/${kind}-worker-image.release.json"
  cp -- "${manifest}" "${out}/${kind}-worker-image.json"
done
echo "Released worker images recorded in ${out}."
