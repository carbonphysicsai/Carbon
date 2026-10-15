#!/bin/bash
# Container smoke for the pinned OpenFOAM v2506 image: two upstream tutorials run
# with the runner's isolation (no network, read-only root, caller uid, 1 CPU).
# Usage: smoke.sh WORK_DIR   (WORK_DIR must not exist)
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=$1; mkdir "$WORK"; WORK=$(cd "$WORK" && pwd)
REF=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['run_reference'])" "$HERE/image.lock.json")
docker run --rm --network none --user "$(id -u):$(id -g)" -v "$WORK:/out" "$REF" bash -c '
  T=$WM_PROJECT_DIR/tutorials
  cp -r $T/incompressible/icoFoam/cavity/cavity /out/cavity
  cp -r $T/basic/scalarTransportFoam/pitzDaily /out/pitzDailyScalar
  cat $WM_PROJECT_DIR/META-INFO/api-info $WM_PROJECT_DIR/META-INFO/build-info > /out/meta-info.txt
  dpkg-query -W -f "\${Package}=\${Version}\n" > /out/packages.txt
  for b in simpleFoam scalarTransportFoam blockMesh snappyHexMesh checkMesh surfaceCheck postProcess foamDictionary; do
    sha256sum $(command -v $b); done > /out/binaries.sha256'
python3 "$HERE/foam_run.py" "$WORK/cavity" "blockMesh > log.blockMesh 2>&1 && checkMesh > log.checkMesh 2>&1 && icoFoam > log.icoFoam 2>&1" --memory 1g
python3 "$HERE/foam_run.py" "$WORK/pitzDailyScalar" "blockMesh > log.blockMesh 2>&1 && scalarTransportFoam > log.scalarTransportFoam 2>&1" --memory 1g
grep -q "^End" "$WORK/cavity/log.icoFoam" && grep -q "^End" "$WORK/pitzDailyScalar/log.scalarTransportFoam"
grep -q "Mesh OK" "$WORK/cavity/log.checkMesh"
echo SMOKE_PASS
