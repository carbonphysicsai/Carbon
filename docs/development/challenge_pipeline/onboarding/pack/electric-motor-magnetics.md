# Evidence page: electric-motor-magnetics

> DISCLAIMER: These pages are measurements read from repository artefacts. They are not traction, customer, qualification or LIVE claims, and not a statement that any Challenge is production-ready.

Generated from the brief-to-product ledger for `electric-motor-magnetics`.
Framing: Models never beat the solver on accuracy; the solver is the reference.

## Decision
- Current decision: Precision-joint magnetic shortlist [source: docs/development/challenge_pipeline/value-cost/analysis.md]
- Unresolved or adverse evidence: Old-space failure is not a result for 10p/12s/skew; complete refined receipt missing [source: docs/development/challenge_pipeline/value-cost/analysis.md]
- Scorecard disposition: Await revised-space S3 T1/T2; no additional reframe now [source: docs/development/challenge_pipeline/value-cost/analysis.md]

## Value
- A real buyer decision with at least two sources: UNMEASURED (measure: owner Codex; tool: The Challenge packet's engineering-job section and the buyer-volume evidence (PR 939, merged)) [required for PASSES VALUE]
- Value and volume ranges: UNMEASURED (measure: owner Codex; tool: The Challenge packet and the buyer-volume evidence (PR 939, merged)) [required for PASSES VALUE]

## Model against reference and cheap baseline
- Model agreement with the reference (accuracy): UNMEASURED (measure: owner Data Collection; tool: Reference-agreement panel returned through docs/development/challenge_pipeline/cheap-baselines/data-collection-return.md)
- Decision quality against the strongest cheap baseline (V4): UNMEASURED (measure: owner Data Collection; tool: Data Collection panels, PR 994 (CHEAP-BASELINE-COMPARATORS-01, open) and the evaluator PR 1003 (PASSES-VALUE-EVALUATOR-01, open)) [required for TESTED] [source: docs/development/challenge_pipeline/cheap-baselines/motor.md]
- Regret against the cheap baseline, paired bootstrap interval: UNMEASURED (measure: owner Data Collection; tool: Data Collection panels, PR 994 comparators (open) and the evaluator PR 1003 (open)) [required for PASSES VALUE]
- Score-value alignment: UNMEASURED (measure: owner Test Lead; tool: A readiness Q1 report (carbon/challenge_pipeline/readiness/q1.py))

## Required: equal-budget screen-then-verify
This page is required. Models never beat the solver on accuracy; the solver is the reference. A model beats the solver only by finding a better design at equal time and compute.
- Screen-then-verify against the solver alone: UNMEASURED (measure: owner Data Collection; tool: PR 998 (EQUAL-BUDGET-DESIGN-01, open) on the design_search track_b harness) [required for PASSES VALUE]

## Speed-up against the reference
- Speed-up per decision query: UNMEASURED (measure: owner Data Collection; tool: Data Collection reference timing plus the model inference cost, on the same hardware) [required for PASSES VALUE]
- Speed-up from the ledger outputs: UNMEASURED (measure: owner Data Collection; tool: Data Collection reference timing (value-cost C1) plus the model inference cost, on the same hardware)

## Onboarding cost and time
- Dated stage records: UNMEASURED (measure: owner Test Lead; tool: cycle_metrics.jsonl, hand-recorded until the A9 recorder exists)
- Cycle days per stage: UNMEASURED (decision owner: Test Lead; question: A first dated record is not the time spent. Which entry and exit records define each stage's cycle time?)
- Cost per stage: UNMEASURED (measure: owner Executor; tool: Stage report: each run's cap fraction; spend ledgers stay out of the repository)
- Readiness, first gate run: {"counts": {"FAIL": 5, "NOT_BUILT": 25, "PASS": 6, "REVIEW_REQUIRED": 5}, "level": 0, "utc": "2026-10-06T16:12:24Z"} [source: docs/development/challenge_pipeline/readiness/electric-motor-magnetics/history.jsonl]
- Readiness, latest by level: {"0": {"counts": {"FAIL": 5, "NOT_BUILT": 25, "PASS": 6, "REVIEW_REQUIRED": 5}, "green": false, "utc": "2026-10-06T16:12:24Z"}} [source: docs/development/challenge_pipeline/readiness/electric-motor-magnetics/history.jsonl]
- Lessons entries: {"by_stage": {"design": 9, "test_iterate": 53}, "count": 62, "first": "2026-10-04T16:05:26Z", "last": "2026-10-09T17:05:00+00:00"} [source: carbon/challenge_pipeline/lessons]
- Grant caps (caps only): UNMEASURED (measure: owner Test Lead; tool: A stage grant file under docs/development/graphite/grants once approved)

## Blockers
The taxonomy is pipeline-wide and seeded with battery stage A.
- B1 Wrong lane: fix FIXED_IN_CODE_NOT_YET_EXERCISED_LIVE; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]
- B2 Keys in the wrong distro: fix FIXED_IN_CODE_NOT_YET_EXERCISED_LIVE; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]
- B3 One controller per root: fix FIXED_IN_CODE_NOT_YET_EXERCISED_LIVE; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]
- B4 Pod ceiling below the offered price: fix FIX_IN_PR_969_NOT_MERGED_NOT_EXERCISED_LIVE; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]
- B5 Token share and pod split: fix VALUE_FIXED_IN_PR_969_CHECK_STILL_OPEN; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]
- B6 Reboot fragility: fix OPEN; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]
- B7 Auto-mode permission blocks: fix OPEN; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]
- B8 Silent failures: fix FIXED_IN_CODE_NOT_YET_EXERCISED_LIVE; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]
- B9 Lane install lagging the grant code: fix OWNER_ASSIGNED_CHECK_PROPOSED_NOT_BUILT; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]
- B10 One shared checkout for every lane: fix OWNER_ASSIGNED_NOT_YET_EXERCISED_LIVE; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]

## Network
- Graphite agents vs real miners: UNMEASURED (measure: owner Test Lead; tool: Validator-scored Launchpad confirmations from Graphite agents and from real miners on the same Challenge)
- Incentive canary payout correctness: UNMEASURED (measure: owner Test Lead; tool: INCENTIVE-CANARY-01 (PR 971, merged))
- Leaderboard improvement over time: UNMEASURED (measure: owner Test Lead; tool: Validator-scored Launchpad confirmations from stage A)

## PASSES VALUE
- Conditions measured: 0 of 5 [source: ledger outputs.passes_value for electric-motor-magnetics]
- Set by: Conditions a to d: Test Lead, delegated by the owner, 2026-10-10. Condition e: Test Lead, from the owner, 2026-10-10. [source: ledger outputs.passes_value for electric-motor-magnetics]
