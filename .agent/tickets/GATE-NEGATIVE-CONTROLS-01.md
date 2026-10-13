# PKT-14 GATE-NEGATIVE-CONTROLS-01

Authority: owner-delegated Test Lead assignment and codex-queue/packets.md,
2026-10-13. Base: bf2494ef478a96ea6403f86aea8d96e3e345482d.
Primary map_ref: CHALLENGE-READINESS (mapped implementation detail).

## Bounded contract

KEEP the 42-item roster, original checks, reviews, waivers and historical
reports. WRAP the current check result with separately reported executable
positive/negative-control coverage. Begin with public-code checks P1, P2 and
A4; do not build all missing reference/host checks. Each run of those items
also invokes the live registered checker on its pinned known-bad specimen.
Missing controls are UNCONTROLLED, never a controlled pass. An accepted bad
specimen, wrong refusal or exception is CONTROL_FAILED, never detection.
The report binds control specification, specimen and checker code identities.

Report original item status, checked count, positive/negative outcomes,
minimum/p01 margin, same-unit noise and unresolved fields together. Structural
checks have no physical scalar margin; leave these null with an explicit
definition-needed reason, never invent zero noise. Numerical report arithmetic
is tested only on synthetic/public aggregates and cannot grant qualification.
Keep legacy readiness distinct from controlled readiness; no score, scientific
threshold, runtime admission or launch authority changes.

## Acceptance and holds

Tests must fail when the checker always accepts, always rejects, raises,
refuses for the wrong reason, has no control, or loses its registered binding.
Exercise actual registered P1/P2/A4 paths and report per-challenge counts,
including an explicit subset denominator; no partial/full-ready conflation.
Use canonical wrapper/CI for acceptance; native Windows is diagnostic only.
No host probes, providers, spend, protected inputs or hidden-panel readers.

Delivery/Hub authority seam is NEW_OWNER_DECISION_REQUIRED, already escalated
by Test Lead. Safe implementation/testing continues; affected closeout/merge
and Hub disposition stay held until the owner rules. No DONE or launch claim.

Expected files: this ticket, one decision, readiness/control module, runner
report integration, focused tests, readiness docs and an execution lesson.
One main-based PR; Validator then Test Lead review; PR Head owns merge.
