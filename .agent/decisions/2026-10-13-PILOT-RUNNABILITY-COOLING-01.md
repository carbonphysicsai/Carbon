# PKT12-D1: cooling retained-evidence replay and reference holds

Ticket: PILOT-RUNNABILITY-COOLING-01 / PKT-12. Working engineering decision.
Test Lead corrected Elmer to the existing pinned OpenFOAM cell route on
2026-10-13; classification DOCUMENTATION_LAG. No solver substitution.

KEEP carbon_arm's default recipe, task assessment, co-located TIM2 observer,
cooling budget validator and OPT-12. WRAP them in cooling-owned kit/worker
files using #1275's load/prepare/train/replay pattern. A direct worker-local
kit avoids overlapping #1275's shared carbon_arm/equal_budget changes and
introduces no dependency on an unmerged PR or registered runtime identity.

Require retained faces for both TRAIN and held-out labels; never reinterpret
heated-face peaks. Learn case peak and pressure, derive hydraulic arithmetic.
Preserve all sibling-map geometry holdouts and propagate conservative supplied
uncertainty bands. Reused-bank requirement questions share one bootstrap
cluster. The synthetic trainer stand-in is confined to the separate dry-run;
public preparation refuses its scope and reduced inventory.

Rejected: copying native Elmer authority, scalar TIM offsets, inferred P/Q/w,
truth-driven recipe selection, treating question labels as independent data,
or generating a cold corpus under a top-up allowance. The 84-case corpus plus
controls/refinements needs a separate prospective big-machine authorization;
the protected half remains outside this public worker and plan.

Reversible through cooling_kit.py, cooling_pilot.py, cooling_pilot_fixture.py,
test_cooling_pilot.py and cooling-winnability-run docs; no migration of existing
public schemas is required. Native image/observer adequacy, characterized maps,
objective/P/Q/w, grants and pass/park thresholds remain human/producer inputs.
No scientific, security, product, production, LIVE or economic authority earned.
