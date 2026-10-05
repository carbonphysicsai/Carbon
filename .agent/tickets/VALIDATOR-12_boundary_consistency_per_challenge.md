# VALIDATOR-12 — Construction-boundary consistency for every Challenge

**Status:** cooling implemented (test only), awaiting review. Motor follows
once its scorer lands.
**Authority:** the Test Lead, 2026-10-05, for the Graphite readiness gate's
item P7: battery's check (VALIDATOR-10, #624) is battery-only, so P7 was
NOT_BUILT for cooling and motor.

**Executor:** the Carbon Validator session. Branch
`claude/boundary-consistency-cooling`, from main `d8bd17bfe`.

## What

Each registered Challenge gets its own standing check. Its door
(`strict_json.parse_strategy`), its contract compile (`compile_submission`)
and its Graphite admission (`experiment.admit` under its scoring) must agree
on that Challenge's malformed-strategy set and valid controls.

Battery's test file is unchanged, byte for byte.

- **Cooling** (`tests/cpu/test_challenge_validator_boundary_consistency_cooling.py`):
  - 2 valid controls: the scaffold, and length_4 with ridge_1e_4;
  - 21 malformed strategies:
    - NaN and Inf, refused at the door;
    - unknown and numeric length tokens and nested `{"value": …}`, refused
      by the recipe;
    - an unknown parameter and an unknown field;
    - another backbone;
    - another Challenge's id, refused by name
      (`not_the_cold_plate_development_challenge`);
    - the 6 excluded surfaces, each as a field and as a parameter;
  - `null`, refused at the door and by the admission.
- **Motor:** the same pattern, once Codex's motor `ChallengeScoring` is
  registered.

## Validation

- **Cooling plus battery boundary tests:** 48 passed (cooling 26, battery 22,
  unchanged).
- `scripts/check_quality.py --base origin/main`: passed.
- **Canonical:** recorded in the PR.

## Maturity

TESTED (DEVELOPMENT). Not a security audit.
