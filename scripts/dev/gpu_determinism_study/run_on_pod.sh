#!/usr/bin/env bash
# One determinism session, run *inside* a rented pod.
#
# The sibling `run_condition.sh` spawns a container with `docker run`. That is
# correct on a host that owns a Docker daemon and impossible on a pod: RunPod's
# pods are themselves containers built from a custom image, and a pod cannot
# build or run containers. So on a rented pod the pod image *is* the worker
# image, and the reconstruction runs directly inside it - which is what this
# script does.
#
# What that costs, stated because the evidence has to say it: this path does not
# apply Carbon's containment. There is no `--network none`, no read-only root,
# no dropped capabilities, no seccomp profile, no cgroup ceiling and no bounded
# scratch, because there is no outer daemon to impose them; the provider's
# runtime supplies whatever isolation the pod has. Admission, the worker
# profile, the device lease and task-owned cleanup are likewise absent.
#
# What it preserves is what the study measures: the pinned numerics environment,
# the pinned image bytes, the plan, archive and seed identities, and the real
# `reconstruct()`. Record the path in these words - *direct execution inside the
# pinned image; not validator_launch; containment from the provider's runtime* -
# because a study that measured a different path than it claims is not an exact
# replay of anything.
#
#   run_on_pod.sh <label>
#
# Environment:
#   STUDY_MATERIALS   staged materials directory                  [required]
#   STUDY_RESULTS     directory for result records                [required]
#   STUDY_RUNS        invocations per session                     [default 3]
#   STUDY_PINNED      1 to apply and require the pinned config    [default 1]
#   CARBON_REPO       Carbon checkout to run from                 [required]
#   CARBON_REVISION   the revision CARBON_REPO is expected to be  [required]
#
# The revision is required and checked rather than inferred. The published image
# predates C-CORE-20 and does not contain the current code, so a run takes its
# Carbon from a checkout - which means the image digest alone does not pin what
# executed, and the execution class records both.
set -euo pipefail
LABEL="${1:?usage: run_on_pod.sh <label>}"

: "${STUDY_MATERIALS:?set STUDY_MATERIALS to the materials directory}"
: "${STUDY_RESULTS:?set STUDY_RESULTS to a writable results directory}"
: "${CARBON_REPO:?set CARBON_REPO to the Carbon checkout to run from}"
: "${CARBON_REVISION:?set CARBON_REVISION to the revision CARBON_REPO should be at}"
RUNS="${STUDY_RUNS:-3}"
PINNED="${STUDY_PINNED:-1}"

# The checkout must be the revision the execution class names. A silently
# different revision is the same class of error as a silently different image.
actual="$(git -C "${CARBON_REPO}" rev-parse HEAD)"
case "${actual}" in
  "${CARBON_REVISION}"*) ;;
  *) echo "checkout is ${actual}, expected ${CARBON_REVISION}" >&2; exit 2 ;;
esac
if ! git -C "${CARBON_REPO}" diff --quiet HEAD --; then
  echo "checkout has uncommitted changes; the revision would not describe it" >&2
  exit 2
fi

UUID="${STUDY_DEVICE_UUID:-$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -1)}"
KIND="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
[ -n "${UUID}" ] || { echo "no device reported by nvidia-smi" >&2; exit 2; }

SCRATCH="${STUDY_SCRATCH:-/work}"
mkdir -p "${SCRATCH}/tmp" "${STUDY_RESULTS}"

# Materials are derived here, in the pod, from the pinned revision - not shipped
# in. `prepare.py` reads no external data: it needs the repository and nothing
# else, and the repository is already required to be at CARBON_REVISION and
# clean.
#
# That is better than a transfer rather than merely easier. Copying materials in
# introduces a third thing to trust - the machine that staged them - whose state
# is not part of the execution class and is recorded nowhere. Deriving them in
# place means the execution class already describes them, and the plan digest is
# asserted, so a compilation that somehow differed is found rather than carried.
if [ ! -f "${STUDY_MATERIALS}/materials.json" ]; then
  echo "staging materials in-pod from ${CARBON_REVISION}"
  STUDY_OUT="${STUDY_MATERIALS}" \
    "${STUDY_PYTHON:-python3}" \
    "${CARBON_REPO}/scripts/dev/gpu_determinism_study/prepare.py"
fi
[ -f "${STUDY_MATERIALS}/materials.json" ] || {
  echo "materials were not produced at ${STUDY_MATERIALS}" >&2; exit 2; }

# Exported before python starts: XLA reads these at import, so setting them
# afterwards would be silently too late. `repeat_gpu.py` reads the numerics
# record back and refuses the run if they did not take effect, which is the only
# check that survives the absence of a daemon.
export PYTHONPATH="${CARBON_REPO}"
export TMPDIR="${SCRATCH}/tmp"
export JAX_PLATFORMS=cuda
export JAX_ENABLE_X64=false
export JAX_DEFAULT_MATMUL_PRECISION=highest
export JAX_ENABLE_COMPILATION_CACHE=false
export XLA_PYTHON_CLIENT_PREALLOCATE=false
export XLA_PYTHON_CLIENT_ALLOCATOR=platform
export CUDA_VISIBLE_DEVICES="${UUID}"
export CARBON_ACCELERATOR_DEVICE_KIND="${KIND}"
export D3_MATERIALS="${STUDY_MATERIALS}"
export D3_RESULTS="${STUDY_RESULTS}/${LABEL}.json"
export D3_LABEL="${LABEL}"
export D3_RUNS="${RUNS}"
export D3_DEVICE_UUID="${UUID}"

# Checked on both conditions. An unpinned contrast run on the wrong image would
# make the contrast meaningless, so this is not gated on PINNED.
export STUDY_REQUIRE_IMAGE=1

if [ "${PINNED}" = "1" ]; then
  export XLA_FLAGS="--xla_gpu_deterministic_ops=true --xla_gpu_exclude_nondeterministic_ops=true --xla_gpu_autotune_level=0"
  export NVIDIA_TF32_OVERRIDE=0
  export CUBLAS_WORKSPACE_CONFIG=":4096:8"
  export STUDY_REQUIRE_PINNED=1
else
  # The contrast condition. Unset rather than emptied, so the numerics record
  # shows their absence rather than an empty string that reads like a setting.
  unset XLA_FLAGS NVIDIA_TF32_OVERRIDE CUBLAS_WORKSPACE_CONFIG STUDY_REQUIRE_PINNED
fi

PYTHON="${STUDY_PYTHON:-/opt/carbon-worker/bin/python}"
[ -x "${PYTHON}" ] || PYTHON="$(command -v python3)"

exec "${PYTHON}" "${CARBON_REPO}/scripts/dev/gpu_determinism_study/repeat_gpu.py"
