#!/usr/bin/env bash
# Rung 3: conjugate heat transfer through two solid slabs into a channel,
# offline, in the pinned OpenFOAM image. Usage: run_case.sh NX NYF NYS OUTDIR
set -euo pipefail
IMAGE="opencfd/openfoam-default@sha256:33fb575aa9980d2bc42fd58c75ae698c489293ba30c991380fe3f899c622f319"
[[ $# -eq 4 ]] || { echo "usage: run_case.sh NX NYF NYS OUTDIR" >&2; exit 64; }
nx=$1; nyf=$2; nys=$3; out=$4
for v in "$nx" "$nyf" "$nys"; do [[ "$v" =~ ^[0-9]+$ ]] || { echo "resolutions must be integers" >&2; exit 64; }; done
[[ -e "$out" ]] && { echo "$out exists; refusing to overwrite" >&2; exit 65; }
here="$(cd "$(dirname "$0")" && pwd)"
install -d -m 0700 "$out"
cp -r "$here/0" "$here/constant" "$here/system" "$out/"
sed -i "s/(NX NYS 1)/($nx $nys 1)/; s/(NX NYF 1)/($nx $nyf 1)/" "$out/system/blockMeshDict"
start=$(date +%s)
# The image entrypoint starts in the openfoam home directory; change to the case.
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$(cd "$out" && pwd):/case" "$IMAGE" bash -lc '
    set -e
    cd /case
    blockMesh > log.blockMesh 2>&1
    splitMeshRegions -cellZones -overwrite > log.splitMeshRegions 2>&1
    for r in solidBottom solidTop; do rm -f 0/$r/U 0/$r/p_rgh; done
    for r in fluid solidBottom solidTop; do changeDictionary -region $r > log.changeDictionary.$r 2>&1; done
    chtMultiRegionSimpleFoam > log.chtMultiRegionSimpleFoam 2>&1
    for r in fluid solidBottom solidTop; do postProcess -region $r -func writeCellCentres -latestTime > log.cellCentres.$r 2>&1; done
    foamListTimes -latestTime > latestTime
  '
echo "{\"nx\": $nx, \"nyf\": $nyf, \"nys\": $nys, \"wall_s\": $(( $(date +%s) - start )), \"image\": \"$IMAGE\"}" > "$out/run.json"
