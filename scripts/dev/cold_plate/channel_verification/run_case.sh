#!/usr/bin/env bash
# Run the parallel-plate verification case at one resolution, offline, in
# the pinned OpenFOAM image. Usage: run_case.sh NX NY OUTDIR
set -euo pipefail
IMAGE="opencfd/openfoam-default@sha256:33fb575aa9980d2bc42fd58c75ae698c489293ba30c991380fe3f899c622f319"
[[ $# -eq 3 ]] || { echo "usage: run_case.sh NX NY OUTDIR" >&2; exit 64; }
nx=$1; ny=$2; out=$3
[[ "$nx" =~ ^[0-9]+$ && "$ny" =~ ^[0-9]+$ ]] || { echo "NX and NY must be integers" >&2; exit 64; }
[[ -e "$out" ]] && { echo "$out exists; refusing to overwrite" >&2; exit 65; }
here="$(cd "$(dirname "$0")" && pwd)"
install -d -m 0700 "$out"
cp -r "$here/0" "$here/constant" "$here/system" "$out/"
sed -i "s/(NX NY 1)/($nx $ny 1)/" "$out/system/blockMeshDict"
start=$(date +%s)
# The image entrypoint starts the shell in the openfoam home directory, so
# the script changes to the mounted case explicitly.
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$(cd "$out" && pwd):/case" "$IMAGE" bash -lc '
    set -e
    cd /case
    blockMesh > log.blockMesh 2>&1
    simpleFoam > log.simpleFoam 2>&1
    postProcess -func writeCellCentres -latestTime > log.cellCentres 2>&1
    foamListTimes -latestTime > latestTime
  '
echo "{\"nx\": $nx, \"ny\": $ny, \"wall_s\": $(( $(date +%s) - start )), \"image\": \"$IMAGE\"}" > "$out/run.json"
