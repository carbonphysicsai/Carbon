#!/bin/bash
# Smoke the pinned Elmer image on three upstream tests from the verified
# release archive, with no network and a read-only root:
#   heateq_bdf2               transient heat, BDF2 (f02's time integration)
#   HelmholtzPlaneWaves       plane wave, |p| ~ 1 analytically (f13's solver)
#   HelmholtzPlaneWavesScan   the same over a 5-frequency scanning loop (f13's sweep)
# Each passes when ElmerSolver's own Reference Norm check writes TEST.PASSED = 1.
set -uo pipefail
IMAGE=${1:?image digest or id}
CTX=${2:-$HOME/refpkg/elmer}
OUT=${3:-$CTX/smoke}
rm -rf "$OUT"; mkdir -p "$OUT"
declare -A GRD=([heateq_bdf2]="angle" [HelmholtzPlaneWaves]="rect.grd" [HelmholtzPlaneWavesScan]="rect.grd")
declare -A SIF=([heateq_bdf2]="TempDist.sif" [HelmholtzPlaneWaves]="case.sif" [HelmholtzPlaneWavesScan]="case.sif")
for t in heateq_bdf2 HelmholtzPlaneWaves HelmholtzPlaneWavesScan; do
  tar xzf "$CTX/elmerfem-release-26.2.1.tar.gz" -C "$OUT" --strip-components=3 --wildcards "*/fem/tests/$t/*"
  start=$(date +%s.%N)
  docker run --rm --network none --read-only --tmpfs /tmp --cpus 1 --user "$(id -u):$(id -g)" \
    -v "$OUT/$t:/case" "$IMAGE" bash -c "ElmerGrid 1 2 ${GRD[$t]} > grid.log 2>&1 && ElmerSolver ${SIF[$t]} > solver.log 2>&1"
  code=$?
  end=$(date +%s.%N)
  passed=$(cat "$OUT/$t/TEST.PASSED" 2>/dev/null | tr -d '[:space:]')
  norm=$(grep -h -E "ComputeNorm|Solver [0-9]+ norm|NRM" "$OUT/$t/solver.log" | tail -1)
  printf '{"test": "%s", "exit": %s, "test_passed": "%s", "wall_s": %.2f, "last_norm_line": "%s"}\n' \
    "$t" "$code" "${passed:-missing}" "$(echo "$end - $start" | bc)" "$(echo "$norm" | sed 's/"/\\"/g')"
done
