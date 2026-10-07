#!/usr/bin/env bash
set -euo pipefail

# Rehearse the release's C-03 parent chain against a throwaway registry
# (IMAGE-RELEASE-01). CI runs it on every change to the release path, so a
# parent the registry does not serve fails here, not in a release.
#
# Usage: release_parent_rehearsal.sh REGISTRY   e.g. localhost:5000/rehearsal
#
# The same scripts as release_worker_images.sh: build the C-03 worker, push it
# and name it by the registry's digest (release_c03_parent.sh), then build one
# real child, the PyTorch CPU worker, and the analysis image FROM that digest,
# with no C-03 rebuild. The CUDA children are left out for runner disk and
# time; they take their parent through the same two helpers.

fail() {
  echo "release_parent_rehearsal: $*" >&2
  exit 2
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(CDPATH= cd -- "${script_dir}/../.." && pwd -P)"
[[ "$#" -eq 1 ]] || fail "usage: release_parent_rehearsal.sh REGISTRY"
registry="$1"
docker info --format '{{json .DriverStatus}}' | grep -q io.containerd.snapshotter \
  || fail "Docker must use the containerd image store"

artifacts="${repo_root}/.carbon-artifacts"
c03_manifest="${artifacts}/rehearsal-c03-worker-image.json"
bash "${script_dir}/c03_worker_image.sh" "${c03_manifest}"
repository="${registry}/carbon-c03-worker"
reference="$(bash "${script_dir}/release_c03_parent.sh" "${repository}" rehearsal "${c03_manifest}")"
echo "C-03 parent: ${reference}"
export CARBON_WORKER_PARENT_REPOSITORY="${repository}"
export CARBON_WORKER_PARENT_MANIFEST="${c03_manifest}"
bash "${script_dir}/torch_worker_image.sh" "${artifacts}/rehearsal-torch-worker-image.json"
analysis_built="$("${repo_root}/.venv/bin/python" -m carbon.development_session.research_image \
  --parent-manifest "${c03_manifest}" \
  --parent-repository "${repository}" \
  --root "${artifacts}/rehearsal-research-images")"

field() {
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$1" "$2"
}
c03="$(field "${c03_manifest}" image_id)"
[[ "${reference}" == "${repository}@${c03}" ]] || fail "the parent reference is not the pushed C-03 image"
[[ "$(field "${artifacts}/torch-parent-worker-image.json" image_id)" == "${c03}" ]] \
  || fail "the PyTorch worker's parent is not the pushed C-03 image"
torch="$(field "${artifacts}/rehearsal-torch-worker-image.json" image_id)"
[[ "$(field "${artifacts}/rehearsal-torch-worker-image.json" base_image_digest)" == "${c03}" ]] \
  || fail "the PyTorch worker does not record the pushed C-03 image as its base"
analysis_manifest="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["manifest"])' "${analysis_built}")"
[[ "$(field "${analysis_manifest}" parent_image)" == "${c03}" ]] \
  || fail "the analysis image is not built on the pushed C-03 image"
analysis="$(field "${analysis_manifest}" image_id)"
# The children's filesystems start with the pushed parent's layers.
python3 - "$(docker image inspect --format '{{json .RootFS.Layers}}' "${c03}")" \
  "$(docker image inspect --format '{{json .RootFS.Layers}}' "${torch}")" \
  "$(docker image inspect --format '{{json .RootFS.Layers}}' "${analysis}")" <<'PY' \
  || fail "a child is not layered on the pushed C-03 image"
import json
import sys

parent, *children = (json.loads(value) for value in sys.argv[1:])
assert parent and all(child[: len(parent)] == parent for child in children)
PY
echo "Rehearsal passed: the PyTorch worker and the analysis image build on ${reference}."
