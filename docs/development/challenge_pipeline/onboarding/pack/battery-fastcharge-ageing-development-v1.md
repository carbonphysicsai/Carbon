# Evidence page: battery-fastcharge-ageing-development-v1

> DISCLAIMER: These pages are measurements read from repository artefacts. They are not traction, customer, qualification or LIVE claims, and not a statement that any Challenge is production-ready.

Generated from the brief-to-product ledger for `battery-fastcharge-ageing-development-v1`.
Framing: Models never beat the solver on accuracy; the solver is the reference.

## Decision
- Current decision: Five ambient-indexed charge/cooling choices [source: docs/development/challenge_pipeline/value-cost/analysis.md]
- Unresolved or adverse evidence: T5/T40 each only 3 feasible actions; indexed ordering and cross-window T3/T4 unsettled [source: docs/development/challenge_pipeline/value-cost/analysis.md]
- Scorecard disposition: Retain v3 question; extend boundary coverage, power/refinement [source: docs/development/challenge_pipeline/value-cost/analysis.md]

## Value
- A real buyer decision with at least two sources: UNMEASURED (measure: owner Codex; tool: The Challenge packet's engineering-job section and the buyer-volume evidence (PR 939, merged)) [required for PASSES VALUE]
- Value and volume ranges: UNMEASURED (measure: owner Codex; tool: The Challenge packet and the buyer-volume evidence (PR 939, merged)) [required for PASSES VALUE]

## Model against reference and cheap baseline
- Model agreement with the reference (accuracy): UNMEASURED (measure: owner Data Collection; tool: Reference-agreement panel returned through docs/development/challenge_pipeline/cheap-baselines/data-collection-return.md)
- Decision quality against the strongest cheap baseline (V4): UNMEASURED (measure: owner Data Collection; tool: Data Collection panels, PR 994 (CHEAP-BASELINE-COMPARATORS-01, open) and the evaluator PR 1003 (PASSES-VALUE-EVALUATOR-01, open)) [required for TESTED] [source: docs/development/challenge_pipeline/cheap-baselines/battery.md]
- Regret against the cheap baseline, paired bootstrap interval: UNMEASURED (measure: owner Data Collection; tool: Data Collection panels, PR 994 comparators (open) and the evaluator PR 1003 (open)) [required for PASSES VALUE]
- Score-value alignment: {"kendall_tau_b": -0.47280542884465016, "level": 0, "members": 8, "note": "one seed per recipe; a measurement only", "reference_provenance": "EV4_REFERENCE", "spearman_rho": -0.5389318178609666} [source: carbon/challenge_pipeline/readiness/battery-fastcharge-ageing-development-v1/q1_report.json]

## Required: equal-budget screen-then-verify
This page is required. Models never beat the solver on accuracy; the solver is the reference. A model beats the solver only by finding a better design at equal time and compute.
- Screen-then-verify against the solver alone: UNMEASURED (measure: owner Data Collection; tool: PR 998 (EQUAL-BUDGET-DESIGN-01, open) on the design_search track_b harness) [required for PASSES VALUE]

## Speed-up against the reference
- Speed-up per decision query: UNMEASURED (measure: owner Data Collection; tool: Data Collection reference timing plus the model inference cost, on the same hardware) [required for PASSES VALUE]
- Speed-up from the ledger outputs: UNMEASURED (measure: owner Data Collection; tool: Data Collection reference timing (value-cost C1) plus the model inference cost, on the same hardware)

## Onboarding cost and time
- Dated stage records: [{"date": "2026-10-06", "event": "first_dated_record", "stage": "S1_packet"}, {"date": "2026-10-06", "event": "first_gate_run", "stage": "S6_readiness"}, {"date": "2026-10-07", "event": "first_dated_record", "stage": "S3_feasibility_value_panel"}, {"date": "2026-10-08", "event": "value_cost_framework", "stage": "S3_feasibility_value_panel"}, {"date": "2026-10-08", "event": "first_dated_record", "stage": "S4_question_law"}, {"date": "2026-10-09", "event": "baseline_2", "stage": "S6_readiness"}, {"date": "2026-10-09", "event": "stage_a_grants_approved", "stage": "S7_stage_a"}, {"date": "2026-10-10", "event": "l0_launch_ready", "stage": "S6_readiness"}, {"date": "2026-10-10", "event": "launch_preflight_merged", "stage": "S7_stage_a"}] [source: docs/development/challenge_pipeline/onboarding/cycle_metrics.jsonl]
- Cycle days per stage: UNMEASURED (decision owner: Test Lead; question: A first dated record is not the time spent. Which entry and exit records define each stage's cycle time?)
- Cost per stage: UNMEASURED (measure: owner Executor; tool: Stage report: each run's cap fraction; spend ledgers stay out of the repository)
- Readiness, first gate run: {"counts": {"FAIL": 3, "NOT_BUILT": 22, "PASS": 11, "REVIEW_REQUIRED": 5}, "level": 0, "utc": "2026-10-06T16:11:56Z"} [source: docs/development/challenge_pipeline/readiness/battery-fastcharge-ageing-development-v1/history.jsonl]
- Readiness, latest by level: {"0": {"counts": {"FAIL": 0, "NOT_BUILT": 0, "PASS": 22, "PASS_BY_REVIEW": 15, "REVIEW_REQUIRED": 0, "WAIVED": 4}, "green": false, "utc": "2026-10-10T12:17:01Z"}, "1": {"counts": {"FAIL": 2, "NOT_BUILT": 0, "PASS": 20, "PASS_BY_REVIEW": 15, "REVIEW_REQUIRED": 0, "WAIVED": 4}, "green": false, "utc": "2026-10-10T12:27:25Z"}} [source: docs/development/challenge_pipeline/readiness/battery-fastcharge-ageing-development-v1/history.jsonl]
- Lessons entries: {"by_stage": {"design": 2, "protocol": 2, "test_iterate": 59}, "count": 63, "first": "2026-10-02T20:01:18Z", "last": "2026-10-10T12:38:19Z"} [source: carbon/challenge_pipeline/lessons]
- Grant caps (caps only): [{"cap": "53.77", "grant_id": "GRAPHITE-GRANT-STAGE-A-ATTACKER", "permitted_runs": 4, "source": "docs/development/graphite/grants/GRAPHITE-GRANT-STAGE-A-ATTACKER.json"}, {"cap": "74.67", "grant_id": "GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR", "permitted_runs": 5, "source": "docs/development/graphite/grants/GRAPHITE-GRANT-STAGE-A-CONSTRUCTOR.json"}] [source: docs/development/graphite/grants]

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
- B11 Training kit does not cover the panel's action space: fix CRITERION_DECIDED_CHECK_NOT_BUILT; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]
- B12 Pinned solver image missing from the operator store: fix OPEN; time lost UNKNOWN [source: docs/development/challenge_pipeline/onboarding/blocker_taxonomy.json]

## Network
- Graphite agents vs real miners: UNMEASURED (measure: owner Test Lead; tool: Validator-scored Launchpad confirmations from Graphite agents and from real miners on the same Challenge)
- Incentive canary payout correctness: UNMEASURED (measure: owner Test Lead; tool: INCENTIVE-CANARY-01 (PR 971, merged))
- Leaderboard improvement over time: UNMEASURED (measure: owner Test Lead; tool: Validator-scored Launchpad confirmations from stage A)

## PASSES VALUE
- Conditions measured: 0 of 5 [source: ledger outputs.passes_value for battery-fastcharge-ageing-development-v1]
- Set by: Conditions a to d: Test Lead, delegated by the owner, 2026-10-10. Condition e: Test Lead, from the owner, 2026-10-10. [source: ledger outputs.passes_value for battery-fastcharge-ageing-development-v1]
