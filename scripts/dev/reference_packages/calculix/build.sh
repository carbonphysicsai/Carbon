#!/bin/bash
# Build the CalculiX reference image from sources.lock.json. Downloads only what
# the lock names and refuses any checksum mismatch.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
CTX=${1:-$HOME/refpkg/calculix}
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
docker build -t carbon-ref-calculix:2.23 "$CTX"
docker image inspect carbon-ref-calculix:2.23 --format '{{.Id}}'
