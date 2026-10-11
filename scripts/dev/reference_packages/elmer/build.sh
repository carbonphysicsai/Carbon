#!/bin/bash
# Build the Elmer reference image from sources.lock.json. Downloads only what
# the lock names and refuses any checksum mismatch.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
CTX=${1:-$HOME/refpkg/elmer}
mkdir -p "$CTX"
python3 - "$HERE/sources.lock.json" "$CTX" <<'PY'
import hashlib, json, sys, urllib.request, pathlib
lock, ctx = json.load(open(sys.argv[1])), pathlib.Path(sys.argv[2])
for s in lock["sources"]:
    p = ctx / s["name"]
    if not p.exists():
        urllib.request.urlretrieve(s["url"], p)
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if h != s["sha256"] or p.stat().st_size != s["size"]:
        sys.exit(f"checksum mismatch: {s['name']}")
    print("verified", s["name"])
PY
cp "$HERE/Dockerfile" "$CTX/Dockerfile"
docker build -t carbon-ref-elmer:26.2.1 "$CTX"
docker image inspect carbon-ref-elmer:26.2.1 --format '{{.Id}}'
