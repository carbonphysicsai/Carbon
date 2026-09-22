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
# STUDY_RUNS repeats inside *one process*, and that is not the same experiment
# as repeating the script. Unpinned, the autotuner chooses kernels once per
# process and reuses them, so in-session repeats reproduce bit-identically even
# where fresh processes do not - measured here, and the reason C-CORE-21's
# 'three distinct digests' came from three separate invocations. A session is
# one invocation of this script; run it once per session.
#
# The revision is required and checked rather than inferred. The published image
# predates C-CORE-20 and does not contain the current code, so a run takes its
# Carbon from a checkout - which means the image digest alone does not pin what
# executed, and the execution class records both.
#
# How the checkout arrives matters, because this image cannot fetch it. There is
# no `git`, no `curl`, no `wget`, and no CA bundle - so an HTTPS download could
# only complete with certificate verification disabled, which would mean taking
# the revision over a channel it cannot authenticate, in a study whose purpose is
# provenance. The checkout therefore arrives on a mounted volume, staged by a
# separate pod that has `git` and runs no part of the study, and `stage_manifest`
# verifies it here by recomputing a digest of the tree.
set -euo pipefail
LABEL="${1:?usage: run_on_pod.sh <label>}"

: "${STUDY_MATERIALS:?set STUDY_MATERIALS to the materials directory}"
: "${STUDY_RESULTS:?set STUDY_RESULTS to a writable results directory}"
: "${CARBON_REPO:?set CARBON_REPO to the Carbon checkout to run from}"
: "${CARBON_REVISION:?set CARBON_REVISION to the revision CARBON_REPO should be at}"
RUNS="${STUDY_RUNS:-3}"
PINNED="${STUDY_PINNED:-1}"

PYTHON="${STUDY_PYTHON:-/opt/carbon-worker/bin/python}"
[ -x "${PYTHON}" ] || PYTHON="$(command -v python3)"
HERE="${CARBON_REPO}/scripts/dev/gpu_determinism_study"

# The checkout must be the revision the execution class names. This image has no
# git, so the check is a staged manifest written by whichever pod cloned the
# repository, verified here by recomputing a digest of the tree. That is stronger
# than the `git rev-parse` it replaces: a recorded revision is a claim, and
# recomputing the digest reads the bytes that are actually present.
"${PYTHON}" "${HERE}/stage_manifest.py" verify "${CARBON_REPO}" "${CARBON_REVISION}" || exit 2

# Device identity, which nothing else in this image can supply. nvidia-smi is
# absent and JAX exposes no UUID, PCI address or serial - only an index and a
# model name - so a study recording "device 0" would be recording an index whose
# mapping to hardware is preserved nowhere. Read through libnvidia-ml instead.
DEVICE_INDEX="${STUDY_DEVICE_INDEX:-0}"
identity="$("${PYTHON}" "${HERE}/device_identity.py" "${DEVICE_INDEX}")" || {
  echo "refusing: the device could not be named, so a per-device result could not be attributed" >&2
  exit 2; }
UUID="$(printf '%s' "${identity}" | "${PYTHON}" -c 'import json,sys; print(json.load(sys.stdin)[0]["uuid"] or "")')"
KIND="$(printf '%s' "${identity}" | "${PYTHON}" -c 'import json,sys; print(json.load(sys.stdin)[0]["name"] or "")')"
[ -n "${UUID}" ] || { echo "refusing: device UUID is unreadable; absent is not a name" >&2; exit 2; }
echo "device ${DEVICE_INDEX}: ${UUID} (${KIND})"

# /tmp, not /work. In the pinned image only /tmp is writable by the nonroot user
# the image runs as - another assumption that held on the development host and
# does not hold where this actually runs.
SCRATCH="${STUDY_SCRATCH:-/tmp/carbon-study}"
mkdir -p "${SCRATCH}/tmp" "${SCRATCH}/artifacts" "${STUDY_RESULTS}"

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
  STUDY_OUT="${STUDY_MATERIALS}" "${PYTHON}" "${HERE}/prepare.py"
fi
[ -f "${STUDY_MATERIALS}/materials.json" ] || {
  echo "materials were not produced at ${STUDY_MATERIALS}" >&2; exit 2; }

# Exported before python starts: XLA reads these at import, so setting them
# afterwards would be silently too late. `repeat_gpu.py` reads the numerics
# record back and refuses the run if they did not take effect, which is the only
# check that survives the absence of a daemon.
# Prepended, not assigned. An inherited PYTHONPATH is how the interpreter finds
# packages that are not in the image's own site-packages - `pytest`, which the
# material derivation reaches through the fixture chain, and `pynvml`. Replacing
# it outright dropped them, which worked only because the checkout happened to be
# staged beside them on the same volume.
export PYTHONPATH="${CARBON_REPO}${PYTHONPATH:+:${PYTHONPATH}}"
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
# The container path mounts /work as a tmpfs; here there is no daemon to mount
# anything, so reconstruction writes under the same scratch as everything else.
# Defaulted, not assigned. A caller that needs the reconstruction artifacts to
# survive - the divergence measurement does, because a digest says *different*
# and not *how different* - points this somewhere durable, and an unconditional
# assignment silently sent them to the scratch tmpfs instead.
export D3_ARTIFACTS="${D3_ARTIFACTS:-${SCRATCH}/artifacts}"
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

exec "${PYTHON}" "${HERE}/repeat_gpu.py"
