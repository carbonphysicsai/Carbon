#!/bin/bash
# Pull the pinned OpenFOAM v2506 image by digest (no build) and verify its build identity.
# The Docker daemon's registry mirror (mirror.gcr.io) serves the same digest if Docker Hub limits.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REF=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['run_reference'])" "$HERE/image.lock.json")
docker pull -q "$REF"
docker run --rm --network none "$REF" bash -c 'cat $WM_PROJECT_DIR/META-INFO/api-info $WM_PROJECT_DIR/META-INFO/build-info' \
  | grep -qx 'build=_615aae61-20250627' || { echo "build identity mismatch" >&2; exit 1; }
echo "pinned: $REF"
