# PKT-19 — Existing physics-law gate controls and observability

Authority: the owner-delegated Packets3 queue entry in `platform.md`, with
Test Lead's 2026-10-13 scope correction after the repository audit.
Starting main: `e627c260d`. One bounded item and one PR.

## Working contract

The queue's claim that no conservation/boundary/PDE checks exist is
`DOCUMENTATION_LAG`. KEEP the existing registered measurements, rules and
physics-contract versions. Do not change scores, adopted tolerances, B15,
B8/B9/B16 roles, deployment state, or pinned implementation modules.

Implement a synthetic-only control/sweep harness over:

- Burgers conserved mean and initial condition, using the existing derived
  measurement and DEVELOPMENT mandatory-gate operator;
- battery initial temperature and inventory-derived capacity bound, using
  the existing exam's gate operator and physics-contract B2 measurement.

Each control must pass through the actual operator. Include compliant,
known-bad and unresolved specimens, hard-failure versus score discrimination,
and hypothetical threshold admit/exclude curves. No threshold is selected by
the harness; new law/observable/applicability/tolerance adoption stays explicit
`HUMAN_INPUT` and fail closed. Synthetic control constants never become
registered Challenge parameters or production evidence.

Record the actual gate inventory and observable limitations. In particular,
battery's published outputs do not supply a full internal charge/thermal
balance; endpoint-excluded Fourier closure does not test independent physical
boundary traces; underresolved integrated-energy/PDE diagnostics do not become
adopted gates. Additional scientific scope needs the Validator's identified
law, observable, Challenge and adoption decision.

## Plan and manifest

1. Audit current authority and open-PR manifests; run focused baseline.
2. Add the existing-law control/sweep CLI, regression tests and generated
   synthetic curves; record `DOCUMENTATION_LAG` and its bounded correction.
3. Validate exact-case coverage, missing/nonfinite failure paths and known-bad
   controls canonically; inspect the unchanged registered source identities.
4. Submit the complete candidate to Carbon Validator/Test Lead, then require
   actual successful exact-head CI/Merge gate before the ready handoff.

Expected paths: this ticket, one decision, `scripts/dev/physics_law_gates.py`,
`tests/cpu/test_physics_law_gate_controls.py`, and
`docs/development/physics-law-gates/{README.md,synthetic-curves.json}`.
No open PR touched these proposed paths at ticket start.

Validation: `CARBON_UV_GROUPS='science-jax archive'
./scripts/dev/canonical.sh --focused tests/cpu/test_physics_law_gate_controls.py
tests/cpu/test_physics_contract.py tests/cpu/test_battery_physics_gate.py
tests/cpu/test_cw1_development_scoring.py`; canonical Ruff/Black, delivery
hygiene, exact generated-output check, encoding and diff checks.

Primary historical map_ref: `WAVE-C/C-W1-D3`; affected battery gate surface.
Hub maintenance is retired by the owner's 2026-10-13 decision. No Hub edits.
Maturity ceiling: implemented/tested synthetic control wiring and audit only;
no new scientific law, adoption, reference adequacy, LIVE, host/security,
production, payment or deployment authority. Completion requires the bounded
DoD, scope review and real exact-head automated acceptance.
