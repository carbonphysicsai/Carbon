#!/usr/bin/env bash
set -euo pipefail

# The C-03 parent manifest of an image built on the C-03 worker
# (IMAGE-RELEASE-01).
#
# Usage: worker_parent_manifest.sh OUT
#
# A local build rebuilds the C-03 worker (c03_worker_image.sh OUT). A release
# never does: it sets CARBON_WORKER_PARENT_MANIFEST to the manifest of the
# C-03 worker it has already pushed, and this copies it to OUT. A rebuild is
# not the same image. Its platform manifest matches, but its attestation, and
# so its image ID, differ (release run 37550120018), and that ID was never
# pushed. A release sets the parent manifest and the repository
# (CARBON_WORKER_PARENT_REPOSITORY, worker_parent_ref.sh) together, or
# neither.

fail() {
  echo "worker_parent_manifest: $*" >&2
  exit 2
}

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
[[ "$#" -eq 1 && -n "$1" ]] || fail "usage: worker_parent_manifest.sh OUT"
out="$1"
released="${CARBON_WORKER_PARENT_MANIFEST:-}"
repository="${CARBON_WORKER_PARENT_REPOSITORY:-}"
if [[ -z "${released}" && -z "${repository}" ]]; then
  exec bash "${script_dir}/c03_worker_image.sh" "${out}"
fi
[[ -n "${released}" && -n "${repository}" ]] \
  || fail "a release sets CARBON_WORKER_PARENT_MANIFEST and CARBON_WORKER_PARENT_REPOSITORY together"
[[ -f "${released}" && ! -L "${released}" ]] || fail "CARBON_WORKER_PARENT_MANIFEST is not a regular file"
python3 - "${released}" <<'PY' || fail "CARBON_WORKER_PARENT_MANIFEST is not a C-03 worker manifest"
import json
import re
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
digest = re.compile(r"sha256:[0-9a-f]{64}")
assert manifest["schema"] == "carbon.c03.worker-image.v1"
assert digest.fullmatch(manifest["image_id"])
assert digest.fullmatch(manifest["source_tree_digest"])
PY
mkdir -p "$(dirname -- "${out}")"
if [[ "$(realpath -- "${released}")" != "$(realpath -m -- "${out}")" ]]; then
  cp -- "${released}" "${out}"
fi
