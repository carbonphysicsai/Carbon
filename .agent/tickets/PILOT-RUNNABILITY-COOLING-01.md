# PILOT-RUNNABILITY-COOLING-01 (PKT-12)

Owner-assigned Packets3 queue, corrected by Test Lead 2026-10-13. One PR to
main; stop at the exact-green PR Head handoff. No merge, approval, release,
solver execution, spend or protected-material access in this ticket.

Starting base: `2d920d7ef9f820ae1321faa3a2667ca853dee9e1`.
Authority: CONSTITUTION.md, .agent/INVARIANTS.md, .agent/WAVE.md,
.agent/DELIVERY_PROTOCOL.md, .agent/DELEGATED_DECISION_PROTOCOL.md,
COOLING-CELL-READINESS-BUILD-01, committed cooling-cell PKT-09 runbook,
cooling-readiness registration/observer and RES-03 operating-points.json.
The Test Lead correction resolves the Elmer wording as DOCUMENTATION_LAG:
KEEP the current pinned OpenFOAM conjugate PG25 interior cell.

Implement a registration-bound plain-L0 kit, retained public-evidence worker,
explicit synthetic dry-run, and reference-generation plan. Reuse #1275's
load -> prepare -> train -> replay -> report worker pattern and main's
carbon_arm, tasks, evidence_pipeline and OPT-12 replay; no dependency on its
unmerged files. Do not edit carbon_arm.py/equal_budget.py, which #1275 owns.
Data acquisition, characterized post-spreader maps, TIM2/uncertainty, native
acceptance, objective/P/Q/w and grants remain explicit fail-closed inputs.

DoD: one-command retained-evidence replay; CPU seeds 0/1/2 with the registered
default MLP; whole-geometry TRAIN/held-out separation; co-located TIM2 observer
checks; complete-panel costs including preparation/failures/refinements;
NONE/UNRESOLVED preservation; no invented independent question clusters;
tiny fixture dry-run through OPT-12; batch-1 job counts and sourced CPU/RAM
hypotheses with the protected half explicitly outside this worker.

Validation: CARBON_UV_GROUPS=science-jax ./scripts/dev/canonical.sh --focused
tests/cpu/test_cooling_pilot.py tests/cpu/test_cooling_readiness_build.py
tests/cpu/test_winnability_pilot.py tests/cpu/test_carbon_arm_f02.py;
changed Python Ruff/Black, delivery hygiene, diff/UTF-8 checks, required CI.
Maturity ceiling: IMPLEMENTED/TESTED preparation and fixture wiring only.
No measured cooling winnability or qualification is earned by a stand-in.
Hub maintenance is retired by the current delivery protocol; no Hub changes.
