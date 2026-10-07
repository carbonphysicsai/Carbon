#!/usr/bin/env bash
set -euo pipefail

# Push the C-03 worker and name it by what the registry serves
# (IMAGE-RELEASE-01).
#
# Usage: release_c03_parent.sh REPOSITORY TAG MANIFEST
#   REPOSITORY  <registry>/<path>/carbon-c03-worker, lowercase, no tag
#   TAG         the release tag (or a rehearsal tag)
#   MANIFEST    the C-03 worker manifest (c03_worker_image.sh)
#
# It tags and pushes the manifest's image, reads the digest the registry
# reports for the tag (`docker buildx imagetools inspect`), requires it to be
# the manifest's image ID (the containerd image store), pulls that digest
# back, and prints `<REPOSITORY>@<digest>`. Every child is then built FROM
# that reference, on this manifest, with no rebuild (worker_parent_ref.sh,
# worker_parent_manifest.sh).

fail() {
  echo "release_c03_parent: $*" >&2
  exit 2
}

[[ "$#" -eq 3 ]] || fail "usage: release_c03_parent.sh REPOSITORY TAG MANIFEST"
repository="$1"
tag="$2"
manifest="$3"
component='[a-z0-9]+([._-][a-z0-9]+)*'
[[ "${repository}" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:[0-9]{1,5})?(/${component})*/carbon-c03-worker$ ]] \
  || fail "REPOSITORY is registry/path/carbon-c03-worker, lowercase, with no tag or digest"
[[ "${tag}" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]] || fail "TAG is not a valid tag"
image="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["image_id"])' "${manifest}")" \
  || fail "MANIFEST is unreadable"
[[ "${image}" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "MANIFEST has no image ID"

docker tag "${image}" "${repository}:${tag}"
docker push --quiet "${repository}:${tag}" >/dev/null || fail "the push failed"
served="$(docker buildx imagetools inspect "${repository}:${tag}" --format '{{json .Manifest}}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["digest"])')" \
  || fail "the registry did not report a digest for ${repository}:${tag}"
[[ "${served}" == "${image}" ]] \
  || fail "the registry serves ${served}, not the image ID ${image}: build with the containerd image store"
docker pull --quiet "${repository}@${served}" >/dev/null || fail "the pushed digest does not pull back"
printf '%s@%s\n' "${repository}" "${served}"
