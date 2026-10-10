# SOLVER-PACKAGE-SPECS-01 — prospective packaging recommendations

Owner scope: build specifications only; no build/run/spend. Base main
`4578d20b27f3d88641a8fe06b3bdbbde8aca17f7`. Primary map_ref would be
challenge_pipeline/reference packaging; the Development Hub is retired and
its frozen map remains unchanged under OWNER-WORKFLOW-SPEED-01.

Engineering selection: recommend OpenCFD OpenFOAM v2506 (do not mix it with
Foundation OpenFOAM 13), Meep v1.32.0 and reuse the inspected ccx 2.23 serial
build pattern at acquisition commit `0f12834226f65cdb317e7407e1e83e68c135801b`.
Use that recipe's exact Debian base/snapshot as the compatibility candidate
for all three. This is a pinned proposal, not a successful new build. DC must
freeze complete source/dependency checksums and platform-specific image
digests after a separately authorised build. No floating tag is accepted as
a final run identity.

Science seams remain HUMAN_INPUT: f17 high-Pe transport adequacy; f06 2D/3D
decision equivalence and affordable fine-grid truth; warpage calibrated cure,
solder formation and state-continuous process history. A solver capability
list or analytical fixture resolves none of these. Full original task scopes
and selected DEVELOPMENT limits remain unchanged. The 2D f06 reframe stays
an inactive candidate; it supplies screening only unless adopted separately.

Reuse class: KEEP packet contracts/build evidence; WRAP ledger and smoke
proofs; specify missing observer/material code without implementing it.
Cost/memory forecasts are HUMAN_INPUT hypotheses, never measured C1. Warpage
node-hours are not relabelled CPU-hours. Meep's sourced bytes-per-cell bound
is not a total-memory guarantee. Permission flags in the planning sheet are
all false and all new built-image identities are null.

Alternatives: reusing Cooling's solver name alone cannot supply f17's scalar
feature/observer proof; treating 2D Meep or an elastic ccx cube as full task
truth would change scope. Floating vendor images and inferred dependency
versions would obscure identity. Those shortcuts are rejected. No existing
public/runtime interface changes. A lead can supersede these proposals by
editing the three spec documents and package-specs.json prospectively; no
stored evidence migration is needed because no package ran. Missing science,
material rights, build acceptance and execution grants remain owner/DC seams.
