#!/usr/bin/env bash
# One determinism session: N invocations of the real reconstruction, in one
# container, on one device.
#
# Sessions are the axis that matters. D3 found unpinned runs bit-identical
# *within* a process and divergent *across* processes, so repeats inside one
# process would find nothing and conclude wrongly. Run this script once per
# session and compare the digests it prints between sessions.
#
#   run_condition.sh <label> [extra docker args...]
#
# Pinned condition: pass the registered determinism configuration as extra args.
#   -e XLA_FLAGS="--xla_gpu_deterministic_ops=true \
#                 --xla_gpu_exclude_nondeterministic_ops=true \
#                 --xla_gpu_autotune_level=0" \
#   -e NVIDIA_TF32_OVERRIDE=0 -e CUBLAS_WORKSPACE_CONFIG=":4096:8"
#
# Unpinned condition: pass nothing extra.
#
# Environment:
#   STUDY_MATERIALS  staged materials directory (see prepare.py)   [required]
#   STUDY_RESULTS    directory for result records                  [required]
#   STUDY_RUNS       invocations per session                       [default 3]
#   STUDY_IMAGE      pinned worker image reference                 [required]
#   CARBON_REPO      repository root to mount read-only            [default: this checkout]
set -u
LABEL="${1:?usage: run_condition.sh <label> [docker args...]}"; shift

REPO="${CARBON_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)}"
: "${STUDY_MATERIALS:?set STUDY_MATERIALS to the staged materials directory}"
: "${STUDY_RESULTS:?set STUDY_RESULTS to a writable results directory}"
: "${STUDY_IMAGE:?set STUDY_IMAGE to the pinned worker image reference}"
RUNS="${STUDY_RUNS:-3}"

UUID="$(nvidia-smi --query-gpu=uuid --format=csv,noheader | head -1)"
KIND="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
[ -n "${UUID}" ] || { echo "no device reported by nvidia-smi" >&2; exit 2; }

# The results directory is bind-mounted and the container runs as a non-root
# user, so it must be writable by that user. The record is also printed before
# it is written, so an unwritable mount loses timing but never the result.
mkdir -p "${STUDY_RESULTS}"

timeout 2400 docker run --rm --gpus all --network none \
  --tmpfs /scratch:rw,size=1g,mode=1777 --tmpfs /work:rw,size=2g,mode=1777 \
  -v "${REPO}":/carbon:ro \
  -v "${STUDY_MATERIALS}":/materials:ro \
  -v "${STUDY_RESULTS}":/results \
  -e PYTHONPATH=/carbon -e TMPDIR=/work/tmp \
  -e D3_MATERIALS=/materials -e D3_RESULTS="/results/${LABEL}.json" \
  -e D3_LABEL="${LABEL}" -e D3_RUNS="${RUNS}" \
  -e D3_DEVICE_UUID="${UUID}" -e CARBON_ACCELERATOR_DEVICE_KIND="${KIND}" \
  -e JAX_PLATFORMS=cuda -e JAX_ENABLE_X64=false \
  -e JAX_DEFAULT_MATMUL_PRECISION=highest \
  -e JAX_ENABLE_COMPILATION_CACHE=false \
  -e XLA_PYTHON_CLIENT_PREALLOCATE=false -e XLA_PYTHON_CLIENT_ALLOCATOR=platform \
  -e CUDA_VISIBLE_DEVICES="${UUID}" \
  "$@" \
  --entrypoint /opt/carbon-worker/bin/python "${STUDY_IMAGE}" \
  /materials/repeat_gpu.py
