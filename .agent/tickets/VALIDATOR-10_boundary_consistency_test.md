# VALIDATOR-10 — A standing construction-boundary consistency test

**Status:** implemented (test only), awaiting review.
**Authority:** the Test Lead, 2026-10-05, after the Carbon Validator's
independent review of battery phase-4 session 1.

**Executor:** the Carbon Validator session. Branch
`claude/validator-boundary-consistency`, from main `61c63925e`.

## Why

Battery phase-4 session 1 recorded 35 FAILING_TRIGGER findings. The
independent review found 0 genuine breaches of the construction boundary. All
35 were oracle defects: advisory tools (check_design, dry_validate, practice)
were read as the boundary. The Test Engineer's oracle fix makes the
Attacker's authoritative class call the real boundary.

This test keeps that boundary visible on its own, so a change to it shows up
even if the oracle changes too.

## What it checks

The authoritative boundary is three layers on the same input:

1. the validator door's strict parse (`strict_json.parse_strategy`);
2. the Challenge contract's compile (`compile_submission`);
3. Graphite's admission (`experiment.admit`).

For every attack category the session tried, the layers must agree:
- **door refusals:** NaN, Inf and `null`;
- **refused after the door** (well-formed JSON outside the contract):
  - knn neighbours −5;
  - nested `{"value": …}` parameters;
  - unknown parameters and fields;
  - six excluded surfaces, each as a field and as a parameter.
- **accepted by all three:** the two valid controls (the scaffold MLP and a
  valid knn).

## Validation

- `tests/cpu/test_challenge_validator_boundary_consistency.py`: 22 passed.
- `scripts/check_quality.py --base origin/main`: passed.
- Canonical: recorded in the PR.

## Maturity

TESTED (DEVELOPMENT). Not a security audit (AGENTS.md §13). The carrier
containment claims from the same session belong to the Test Engineer's
containment check and the security review.
