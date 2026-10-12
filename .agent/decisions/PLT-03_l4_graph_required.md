# PLT-03: require graphs for Graphite Level 4 proposals

Authority: owner-assigned queue item L4-GRAPH-VARIANT-FIX-01 (2026-10-12),
OWNER-LEVEL4-GRAPH-ONLY-01, and the current delivery protocol.
Reviewer: Test Engineer. Maturity ceiling: DEVELOPMENT engineering.

Diagnosis: battery-l4-graph-v3 grants a graph slot, but development compilation
also accepts base recipes with no widened fields. Graphite applied that path
to proposals, so an ordinary MLP could be scored and bundled under an L4 binding.
The existing staged-graph worker already constructs and trains GraphModel.

REPAIR Graphite proposal admission to require a staged graph at Level 4.
KEEP plain baselines and single-field ablations as explicit comparison controls.
REPAIR delivery and clean rebuild to refuse graphless L4 winners and missing
envelopes, including internally consistent old defective bundles. Their stored
scores and files are not rewritten or rescored; they cannot establish an L4 build.
KEEP battery's variant document, registry, graph worker, pinned recipe/training
modules, and numpy-free level4 import unchanged. The brief now says a graph is
required. A superseding change would modify experiment.py and delivery.py;
automatic lowering of proposals was rejected because it hides a missing graph
instead of requiring the Constructor's submitted artifact.

Validation: canonical focused Graphite L4 staging/carry/session regressions,
battery L4 variant/rebuild/worker training regressions, phase-3 delivery and
development-variant regressions; required CI acceptance on the PR head.
No scientific thresholds, hidden material, security qualification, LIVE,
scoring policy, economic or deployment authority is introduced. The Development
Hub is retired by OWNER-WORKFLOW-SPEED-01; no Hub regeneration applies.
