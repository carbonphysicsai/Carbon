# REFERENCE-SOLVERS-HOST-MESH-01 — solve the mesh the host generates, record both digests

**Finding.** The same Gmsh 4.15.2 SDK binary and script give byte-identical f08
meshes on the Intel development box and the pinned manifest (small-light
primary and the beam control both match), but the beam control differed on a
RunPod AMD EPYC 9754 pod (calculix smoke pod 2, 2026-10-15). Gmsh/OpenCASCADE
floating-point paths differ by CPU, so "regenerate on the pod and refuse any
digest mismatch" cannot work across hosts.

**Decision.** A pod plan step may name `host_regenerated_files` (mesh and the
files derived from it). A selected case that differs only in those files, with
a command matching the freeze, runs on the regenerated files. Before any solve
the step records, per file, the pinned and the solved digest
(`deck-verification.json`, `host_regenerated`) and keeps the solved files in
`decks-solved/`. The reference is the mesh actually solved, by its digest; the
generator code and parameters stay pinned. Any other difference still refuses.

**Alternatives rejected.** Shipping every dev-box mesh in git (witness meshes
exceed the 2 MB file rule); disabling the digest check (loses identity).

**Reversible** by removing the opt-in from plans. Convergence and control
judgements are made on the solved meshes, so they remain valid per host.
