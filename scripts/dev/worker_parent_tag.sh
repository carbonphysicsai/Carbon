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
# The tag also carries the install ROLE (CARBON_INSTALL_ROLE, worker_tag.sh): a miner and a validator install of the
# same tree never share a name.

fail() {
  echo "worker_parent_tag: $*" >&2
  exit 2
}

[[ "$#" -eq 2 ]] || fail "usage: worker_parent_tag.sh VARIANT SOURCE_TREE_DIGEST"
exec bash "$(dirname -- "${BASH_SOURCE[0]}")/worker_tag.sh" carbon-c03-worker "$1" "$2"
