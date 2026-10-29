#!/usr/bin/env bash
set -euo pipefail

# The local tag of a C-03 parent build.
#
# Usage: worker_parent_tag.sh VARIANT SOURCE_TREE_DIGEST
#
# Every image built FROM the C-03 worker (the CPU Torch worker, the JAX
# accelerator worker, the PyTorch GPU worker) rebuilds that parent and names
# it in the local store by tag. One shared tag, carbon-c03-worker:<16 hex of
# the source digest>, let each rebuild retag the previous one's image: after a
# --gpu install only the last parent kept the tag, and under the containerd
# store the CPU parent (which the CPU Torch worker was built FROM) was gone, so
# every catalog entry was refused (installed_cpu_construction_worker_unavailable;
# val4090, 2026-10-29).
#
# The CPU parent keeps the original tag, which the install's identity records
# and fingerprints name. Every other variant gets its own tag, the first 16 hex
# of sha256("<variant>\n<source digest>"), so no build retags another's image.
# Both forms match carbon.reconstruction.worker.image_fingerprint.PARENT_TAG.

fail() {
  echo "worker_parent_tag: $*" >&2
  exit 2
}

[[ "$#" -eq 2 ]] || fail "usage: worker_parent_tag.sh VARIANT SOURCE_TREE_DIGEST"
variant="$1"
source_digest="$2"
[[ "${source_digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "SOURCE_TREE_DIGEST is sha256:<64 hex>"
case "${variant}" in
  cpu) printf 'carbon-c03-worker:%s\n' "${source_digest:7:16}" ;;
  accelerator | torch-gpu)
    hashed="$(printf '%s\n%s' "${variant}" "${source_digest}" | sha256sum | cut -c1-16)"
    printf 'carbon-c03-worker:%s\n' "${hashed}"
    ;;
  *) fail "variant must be cpu, accelerator or torch-gpu" ;;
esac
