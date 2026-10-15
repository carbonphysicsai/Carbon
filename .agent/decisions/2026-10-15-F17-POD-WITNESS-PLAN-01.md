# F17-POD-WITNESS-PLAN-01 (2026-10-15)

**Decision.** The f17 refined-rung witnesses (D1 two-mesh, D2 maximum-Pe
scalar layer), the 8-design triage panel, the controls and the cold repeat
run as one RunPod pod plan,
`docs/development/evidence/reference-solvers-2026-10-15/plans/f17-witness-triage.json`
(kind `openfoam2506`), which the lead launches. A second step judges the
outputs in place with `scripts/dev/reference_packages/openfoam/f17_pod_judge.py`
against the bands in F17-SCIENCE-VALUES-01 and serves only compact JSON.

1. The frozen command is now relative (`bash Allrun > Allrun.log 2>&1`):
   `pod_phase.verify_decks` refuses `/case` paths. bulk_run already runs
   Docker with `-w /case` and the case dir as the native cwd, and `Allrun`
   changes to its own directory. The deck files are unchanged, so the file
   digests are the same as before.
2. The judge step installs `python3-numpy` and `python3-scipy` from the same
   pinned Ubuntu snapshot (20260930T000000Z) that the pod setup uses, and
   records them in `judge-packages.txt`. The alternative was to export the
   fields: a refined case holds about 120 MB of fields, which is too large to
   serve or commit.
3. `host_regenerated_files` lists the four Python-generated mesh inputs (STL,
   eMesh, blockMeshDict, snappyHexMeshDict), following
   REFERENCE-SOLVERS-HOST-MESH-01. snappyHexMesh builds the mesh in the case
   on the pod, and the mesh's digest is recorded in `mesh/mesh.sha256`.
4. Measured local costs (DEVELOPMENT profile `local-dev-4vcpu-15g-contended`)
   are recorded in `evidence/reference-packages-01/f17-local-costs.json`, and
   the manifest estimates are generated from that file.

**Reversibility.** Only plan files and tooling changed; no band changed.
**HUMAN_INPUT left.** The lead or owner decides when to launch the pod (worst
case $0.60 on cpu3c 8 vCPU, or $1.40 on cpu5c 16 vCPU so the run also serves
as D3 timing calibration).
