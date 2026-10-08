# CHALLENGE-CUSTOMER-PACKETS-01 — Motor, Cooling and Battery customer briefs

**Start:** main `0e7308fe9e7f494ded0d80b2748b8afabb76ab8c`.
**Status:** candidate prepared for PR Lead; bounded DEVELOPMENT documentation/test ticket, not a runtime migration. Merge remains external.
**Authority:** owner's direct 2026-10-07 instruction, prospectively recorded in
OWNER-FIRST-THREE-CUSTOMER-ROUND-01; OWNER-PORTFOLIO-DEV-ROUND-01;
OWNER-LAUNCH-PORTFOLIO-02; Foundation Plan §3 and §4; current delivery protocol.
**Dependencies:** merged common packet #718 and five-family requirements #722.

## Working contract

Write independent mock-buyer packets in order Motor, Cooling, Battery, using
the common ten-section outline. Select concrete DEVELOPMENT requirements
from the buyer's job and cost of a wrong choice, not from TRAIN medians,
leaderboards or the capabilities of a current scoring implementation. Identify
exact gaps between that job and each existing reference/measurement contract.
Supply a separate machine-readable planning sheet with units and dimensional
checks. It is not a new registry, Score Pack, grant or runtime schema.

KEEP all current domain/reference/validator implementations and historical
contracts. WRAP the common design-packet format. Reuse public source facts
only as context, never as certification of mock requirements. Do not change
old thresholds, cases, weights, studies, readiness or customer rights.

## Definition of done

- Three ten-section packets contain persona/job, design action, buyer limits
  and reasons, wrong-choice costs, scenario strata, acceptance and abstention,
  deployment/speed/replacement story, and explicitly assumed value units.
- Motor's static mean/ripple requirements differ from 4 N·m / 0.30 TRAIN
  medians. Zero-current cogging is not divided by mean torque. Dynamic and
  thermal joint promises remain outside the 2D reference.
- Cooling's full-manifold requirements differ from periodic-cell 100 °C /
  0.25 W examples; full-assembly pressure/power is not a relabelled cell result.
- Battery keeps a 0-V model plating boundary and 45-°C buyer ceiling, retains
  the 30-cycle task, and exposes missing 10–80% timing measurements. No EV5,
  sealed journal sequence 14, live contract or existing exam limit changes.
- P_dev, diagnostic Q and evidence weights are distinguished from customer
  deployment frequencies. Public scenario recipes contain no protected draws.
- Focused canonical tests check ten-section structure, planning isolation,
  units/calculations and exact buyer/reference gaps; applicable quality passes.
- Record a lesson after each validation execution, notify #42 and #643, and
  hand one exact-head PR to PR Lead: `Codex is done; PR Lead may take over.`

## Manifest, maturity and continuation

Expected changes: this ticket; its one decision file; three new round1
packets; `first-three-requirements.json`; the round1 index; one CPU test file;
and execution lessons. No production Python module or frozen study changes.
The Development Hub is retired: its historical files remain untouched.

Requirements may earn SPECIFIED. Packet consistency and dimensional tests
may earn TESTED in that narrow scope. Empirical reference adequacy for these
new buyer decisions remains NOT_DEMONSTRATED. No physical model was trained,
no solver campaign dispatched and no actual customer acceptance occurred.
Completion is conditional on current scope-required exact-head CI and the
merge manager's normal merge; delivery evidence belongs in the PR, not an
evidence-only commit. Gate/quiz/tuning integration belongs to the Test Lead
and Carbon Validator in separate prospectively versioned tickets.

The previously authorized numeric/custody runner repair remains queued after
this owner-prioritized packet ticket. This ticket grants no spend and does
not increase or transfer the five new families' $160 feasibility allowances.

## Stable validation basis

Canonical focused validation includes the new packet tests plus the existing
portfolio screen and challenge-pipeline tests: **65 passed, 1 existing optional
NumPy skip**. Pipeline validation reports DEFINING, 7 valid records, 405 valid
lessons before recording the final execution, and zero awaiting a decision.
Ruff, Black and diff hygiene pass. The new test is stored with non-executable
Git mode 100644; the isolated canonical NTFS copy needed that intended mode
normalized before Ruff. Initial AST-reader and copy-mode failures are retained
in lessons rather than relabelled as passes. No reference solver ran.

These results establish packet structure, numeric consistency and prospective
boundary statements only. Exact-head CI, integration and merge remain the
merge manager's responsibility; this record asserts none of those outcomes.
