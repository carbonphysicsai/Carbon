# READINESS-GAPS-01: S3, H2, and V3

**Status:** DEVELOPMENT implementation. The user's ticket authorizes the three waived readiness items. No hidden material, solver run, spend, LIVE change, or scientific threshold decision is in scope.

## Working contract

- **S3:** A producer-supplied, registered gate-margin panel identifies the complete gate set, margin units, source digest, and per-gate fragility boundary. The analyzer computes the minimum and empirical first percentile from reference margins and flags fragile gates. No default fragility boundary is invented. Missing or malformed data never passes readiness.
- **H2:** A producer-side overlap evidence input must name the registered tuning role and every sealed comparison role plus the rotating pool, TRAIN, PRACTICE, and practice decision set. The checker compares canonical case inputs in memory and emits aggregates only. An incomplete roster or any overlap fails. The registered role and existing confirmation-set overlap machinery are reused; a declaration without case evidence does not pass.
- **V3:** A multi-seed promotion policy is a proposal for the Test Lead. It records the evidence shape and leaves seed count, equivalence/noise band, promotion rule and action on inconclusive results HUMAN_INPUT. V3 remains a review item until an authorized review exists.

Wire the two automated checks through `python -m carbon.challenge_pipeline readiness` using explicit development evidence paths. Default runs with no evidence remain NOT_BUILT. The CLI must not print case inputs, case IDs, seeds, or overlap witnesses; it prints aggregate S3 measures and an H2 verdict. Tests use toy data only.

## Plan

1. Reuse readiness `Context`, `Result`, runner and existing registration. Add strict input schemas and pure S3/H2 analysis.
2. Wire explicit input paths to S3/H2 checks, preserve fail-closed default and report digest.
3. Add the V3 policy proposal, focused toy tests, and canonical validation. One PR to PR Lead at exact head.

**Maturity ceiling:** IMPLEMENTED and TESTED automated checks. No real-panel PASS or promotion-policy adoption is inferred from fixtures.
