#!/usr/bin/env bash
set -euo pipefail

# The local tag of a source-tree-derived worker image, per install ROLE and variant.
#
# Usage: worker_tag.sh REPOSITORY VARIANT SOURCE_TREE_DIGEST
#   REPOSITORY  carbon-c03-worker | carbon-torch-worker | carbon-torch-gpu-worker
#   VARIANT     cpu | accelerator | torch-gpu   (the C-03 parent a build is for)
#   CARBON_INSTALL_ROLE  miner (default) | validator
#
# These tags are derived from the source tree alone, so a miner install and a validator install of the SAME tree on
# one Docker daemon named the same images, and the second install retagged the first's (val4090, 2026-10-29: a scratch
# miner install moved the validator's parent and worker tags). A tag now carries its role:
#
# - validator: the names a validator install has always used, unchanged on upgrade: <repository>:<hex 16 of the source
#   digest> (c03 parent: cpu variant) and <repository>:<hex 16 of sha256("<variant>\n<source digest>")> for the
#   accelerator and torch-gpu parent variants;
# - miner: <repository>:<hex 16 of sha256("miner\n<variant>\n<repository>\n<source digest>")>, which can match no
#   validator name.
# Both forms match carbon.reconstruction.worker.image_fingerprint.PARENT_TAG's shape.

fail() {
  echo "worker_tag: $*" >&2
  exit 2
}

[[ "$#" -eq 3 ]] || fail "usage: worker_tag.sh REPOSITORY VARIANT SOURCE_TREE_DIGEST"
repository="$1"
variant="$2"
source_digest="$3"
role="${CARBON_INSTALL_ROLE:-miner}"
case "${repository}" in
  carbon-c03-worker | carbon-torch-worker | carbon-torch-gpu-worker) ;;
  *) fail "REPOSITORY is carbon-c03-worker, carbon-torch-worker or carbon-torch-gpu-worker" ;;
esac
case "${variant}" in cpu | accelerator | torch-gpu) ;; *) fail "variant must be cpu, accelerator or torch-gpu" ;; esac
case "${role}" in miner | validator) ;; *) fail "CARBON_INSTALL_ROLE is miner or validator" ;; esac
[[ "${source_digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "SOURCE_TREE_DIGEST is sha256:<64 hex>"
hash16() { printf '%s' "$1" | sha256sum | cut -c1-16; }
if [[ "${role}" == validator ]]; then
  if [[ "${repository}" != carbon-c03-worker || "${variant}" == cpu ]]; then
    printf '%s:%s\n' "${repository}" "${source_digest:7:16}"
  else
    printf '%s:%s\n' "${repository}" "$(hash16 "${variant}"$'\n'"${source_digest}")"
  fi
else
  printf '%s:%s\n' "${repository}" "$(hash16 "miner"$'\n'"${variant}"$'\n'"${repository}"$'\n'"${source_digest}")"
fi
