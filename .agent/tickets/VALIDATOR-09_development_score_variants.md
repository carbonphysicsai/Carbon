# VALIDATOR-09: development score variants

**Status:** slice 1 implemented (the registry, re-scoring and invariant).
Slice 2 (Graphite `--score-variant`) follows.

**Authority:**
- the Test Lead's approval of the design, 2026-10-05, with these corrections:
  - variant winners are judged on development data the optimiser never saw,
    never on a sealed confirmation set;
  - phase-4 variant support belongs to the Test Engineer, and is refused until
    then;
  - gate overrides may tighten or loosen, and are recorded in the variant's
    identity;
- OWNER-GRAPHITE-TEST-WAVE-08 §3: candidate weightings are registered before
  they are computed, then re-scored from the tuning set's stored per-case rows
  with no retraining. Survivors become development score variants;
- OWNER-TESTNET-WEIGHTS-01 §2a: scores closest to 1 are best.

**Executor:** the Carbon Validator session. Branch
`claude/validator-09-score-variants`, from main `53fae92fc`.

## Slice 1 (this PR)

- **`carbon/scoring/development_score_variants.py`** and
  `development_score_variant_policies/`, a digest-pinned registry that ships
  empty.
  - A document `carbon.development-score-variant.v1` holds weights over
    declared components and an optional `tail_logistic` transform onto
    [0, 1] (`Scoring.md` §6.2), where 1 is best.
  - Its scope is `DEVELOPMENT_ONLY_NEVER_SERVED_TO_MINERS`, and its status is
    CANDIDATE or SURVIVOR.
  - Refused by name:
    - an unregistered, unreadable, altered or malformed document;
    - an undeclared component;
    - weights that are not strictly positive with an exact decimal sum of 1;
    - set-level terms, gate overrides, and comparison or important-region
      overrides (not yet served);
    - a fixture in the shipped registry.
- **`rescore`** works from a member's stored rows: weighted per-case error,
  important-region error, eligibility (any gate failure still makes the member
  ineligible), and the [0, 1] score when a transform is set. The operator CLI
  is `rescore --version V --rows <tuning work>/rows --out FILE`, owner-only.
- **`ChallengeScoring.declared_score_components`**, data only. Battery
  declares `exam.COMPONENTS`.
- **The invariant** `tests/invariants/test_score_variants_unreachable.py`:
  no miner surface, validator or intake reaches the module. It uses both
  walks, with a planted-import specimen.

## Slice 2 (next)

- **Graphite `--score-variant` in phase 3:**
  - the variant is resolved before any spend;
  - it is pinned in the brief and in the permission profile;
  - the frozen rule is the variant's;
  - the variant identity appears in feedback, in `summary()` and on every
    result's label.
- **Phase 4** refuses `--score-variant`
  (`attacker_score_variant_not_supported`).
- **Refusal tests on every miner door,** each with a mutation-off twin.
- **Gate-override and set-level-term paths,** through the adapters (battery's
  is ours; motor's follows Codex's scorer).

## Maturity

IMPLEMENTED and TESTED (DEVELOPMENT). No variant is registered. Registering
one is the tuning loop's step, before it is computed.
