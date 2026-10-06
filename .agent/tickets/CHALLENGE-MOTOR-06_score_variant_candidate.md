# CHALLENGE-MOTOR-06 — prospective unit-interval score candidate

**Status:** implementation and focused canonical validation complete;
applicable PR CI and PR Lead handoff pending. DEVELOPMENT candidate only.

**Authority:** SCORING-ARCH-01 (#643), OWNER-TESTNET-WEIGHTS-01 §2a,
OWNER-CHALLENGE-DESIGN-01, and Motor's registered DEVELOPMENT exam.
**Predecessor:** CHALLENGE-MOTOR-05, merged PR #638.
**Coordination:** Carbon Validator owns VALIDATOR-09's neutral registry,
VALIDATOR-13's hidden route, and winner weights. This ticket edits none of
those. PR Lead may take over after handoff.

## Outcome and boundary

Propose and measure one `[0,1]`, higher-is-better transform of Motor's existing
raw mean TRAIN-normalized public PRACTICE error. Keep its frozen 30 cases,
gates, components, scales, aggregate and historical result identities
unchanged. The candidate is not registered in the validator, miner practice,
Graphite or weights, and never reads protected cases or seeds.

This is not the physics/robustness/accuracy Score Pack. The soft-physics
estimand, a full 45/30/25 profile, and score adoption remain `HUMAN_INPUT`.

## Working contract

- Candidate formula: `u(e) = 1 / (1 + e / tau)` with proposed `tau = 0.17`,
  rounded from the learned public PRACTICE baseline raw mean
  `0.17300702981329621`. The scale places that scaffold near `0.5`; it is a
  measured proposal, not a production threshold.
- The transform is monotone and cannot change the frozen exam's ranking or
  repair its documented decision-value divergences. SR-M1's phase-invariant
  A2 is a separately registered DEVELOPMENT candidate, not silently combined
  with this transform or adopted here.
- A positive candidate score requires all 30 usable case outcomes and no
  mandatory gate failure. A complete confirmed gate failure gives an
  inadmissible zero. Missing/invalid reference, infrastructure or incomplete
  coverage yields no numeric score, while known gate failures remain visible.
- All results are public/adaptive DEVELOPMENT, nonpromotable and ineligible
  for official scoring. Prospective adoption requires the Motor science owner
  and neutral registry integration in a later ticket.

## Definition of done

- Pure typed candidate transform with stable Challenge/material/implementation
  identity and no official caller.
- Reproducible public-baseline report and honest interpretation alongside
  SR-M1's existing widened-panel finding.
- Focused tests for endpoints, ordering, gates, missing evidence, inconsistent
  aggregate and non-authority; affected Motor tests and quality checks.
- One lessons entry after execution; applicable PR CI before delivery closeout.

## Validation to date

- Candidate and affected Motor scorer/exam/SR-M1 matrix: 61 tests passed in
  the pinned canonical Linux environment with `science-jax` dependencies.
- Changed Python files passed pinned Ruff and Black checks.
- A first test run had one test-only exact floating-point equality failure;
  the assertion was corrected to numerical comparison. No scoring code or
  registered rule was changed to make the test pass.
- The exact-base temporary Linux checkout contains mechanical copies of the
  Motor source/test/evidence note because WSL Git cannot interpret a
  Windows-created worktree's `.git` path. GitHub CI is final PR acceptance.

## Out of scope

Motor's independently held paired fresh-case promotion policy is a separate
ticket. This one does not run GetDP, spend compute, produce fresh confirmation,
change the frozen 8×6 decision set, adopt A2, touch EV5/journal 14/Battery's
live contract, or claim scientific/production qualification.
