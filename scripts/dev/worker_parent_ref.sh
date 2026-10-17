#!/usr/bin/env bash
set -euo pipefail

# The FROM reference of a C-03 child or CPU Torch analysis child.
#
# Usage: worker_parent_ref.sh PARENT_IMAGE_ID SOURCE_TREE_DIGEST [c03|torch]
#
# A local build names the parent in the local image store:
#   carbon-c03-worker:<first 16 hex of the source digest>@<image ID>.
# A release sets CARBON_WORKER_PARENT_REPOSITORY to the registry repository
# the parent was just pushed to, and the child is built FROM
#   <repository>@<image ID>.
# A builder that cannot see the local store (as on a GitHub runner, where the
# local form resolved to Docker Hub) then pulls exactly the pushed parent. The
# digest pins it either way.
# Existing two-argument callers select C-03. Only the analysis builder names
# `torch`, after checking the parent's exact CPU Torch lock.

fail() {
  echo "worker_parent_ref: $*" >&2
  exit 2
}

[[ "$#" -eq 2 || "$#" -eq 3 ]] || fail "usage: worker_parent_ref.sh PARENT_IMAGE_ID SOURCE_TREE_DIGEST [c03|torch]"
parent="$1"
source_digest="$2"
case "${3:-c03}" in
  c03) name=carbon-c03-worker ;;
  torch) name=carbon-torch-worker ;;
  *) fail "parent kind must be c03 or torch" ;;
esac
[[ "${parent}" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "PARENT_IMAGE_ID is sha256:<64 hex>"
[[ "${source_digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "SOURCE_TREE_DIGEST is sha256:<64 hex>"
repository="${CARBON_WORKER_PARENT_REPOSITORY:-}"
if [[ -z "${repository}" ]]; then
  printf '%s:%s@%s\n' "${name}" "${source_digest:7:16}" "${parent}"
  exit 0
fi
component='[a-z0-9]+([._-][a-z0-9]+)*'
[[ "${repository}" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:[0-9]{1,5})?(/${component})*/${name}$ ]] \
  || fail "CARBON_WORKER_PARENT_REPOSITORY is registry/path/${name}, lowercase, with no tag or digest"
printf '%s@%s\n' "${repository}" "${parent}"
