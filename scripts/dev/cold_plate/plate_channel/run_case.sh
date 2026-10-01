#!/usr/bin/env bash
# Rung 4: one straight-channel plate cell (half channel, half fin), conjugate,
# offline, in the pinned OpenFOAM image. Usage:
#   run_case.sh OUTDIR [generate.py options, e.g. --resolution 2 --iterations 8000]
# Serial, and capped to two CPUs so the shared host keeps its headroom.
set -euo pipefail
IMAGE="opencfd/openfoam-default@sha256:33fb575aa9980d2bc42fd58c75ae698c489293ba30c991380fe3f899c622f319"
[[ $# -ge 1 ]] || { echo "usage: run_case.sh OUTDIR [generate options]" >&2; exit 64; }
out=$1; shift
here="$(cd "$(dirname "$0")" && pwd)"
python3 "$here/generate.py" "$out" "$@"
start=$(date +%s)
# The image entrypoint starts in the openfoam home directory; change to the case.
docker run --rm --network none --cpus 2 --user "$(id -u):$(id -g)" \
  -v "$(cd "$out" && pwd):/case" "$IMAGE" bash -lc '
    set -e
    cd /case
    blockMesh > log.blockMesh 2>&1
    checkMesh > log.checkMesh 2>&1
    splitMeshRegions -cellZones -overwrite > log.splitMeshRegions 2>&1
    rm -f 0/solid/U 0/solid/p_rgh
    for r in fluid solid; do changeDictionary -region $r > log.changeDictionary.$r 2>&1; done
    chtMultiRegionSimpleFoam > log.chtMultiRegionSimpleFoam 2>&1
    for r in fluid solid; do postProcess -region $r -func writeCellCentres > log.cellCentres.$r 2>&1; done
    for r in fluid solid; do postProcess -region $r -func writeCellVolumes > log.cellVolumes.$r 2>&1; done
    foamListTimes > times
  '
echo "{\"wall_s\": $(( $(date +%s) - start )), \"image\": \"$IMAGE\"}" > "$out/run.json"
