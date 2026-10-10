# Evidence pack: across Challenges

> DISCLAIMER: These pages are measurements read from repository artefacts. They are not traction, customer, qualification or LIVE claims, and not a statement that any Challenge is production-ready.

Framing: Models never beat the solver on accuracy; the solver is the reference.

## Challenges covered
- battery-fastcharge-ageing-development-v1: Five ambient-indexed charge/cooling choices [source: docs/development/challenge_pipeline/value-cost/analysis.md]
- electric-motor-magnetics: Precision-joint magnetic shortlist [source: docs/development/challenge_pipeline/value-cost/analysis.md]
- f02: Thermal burst schedule [source: docs/development/challenge_pipeline/value-cost/analysis.md]

## Physics regimes covered
- Regime taxonomy: UNMEASURED (decision owner: Test Lead; question: which regime tags apply to each Challenge? No artefact records one.)

## PASSES VALUE across Challenges
| Challenge | a | b | c | d | e |
|---|---|---|---|---|---|
| battery-fastcharge-ageing-development-v1 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED |
| electric-motor-magnetics | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED |
| f02 | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED | UNMEASURED |

## Per-stage cost and time

### battery-fastcharge-ageing-development-v1
- Dated stage records: [{"date": "2026-10-06", "event": "first_dated_record", "stage": "S1_packet"}, {"date": "2026-10-06", "event": "first_gate_run", "stage": "S6_readiness"}, {"date": "2026-10-07", "event": "first_dated_record", "stage": "S3_feasibility_value_panel"}, {"date": "2026-10-08", "event": "value_cost_framework", "stage": "S3_feasibility_value_panel"}, {"date": "2026-10-08", "event": "first_dated_record", "stage": "S4_question_law"}, {"date": "2026-10-09", "event": "baseline_2", "stage": "S6_readiness"}, {"date": "2026-10-09", "event": "stage_a_grants_approved", "stage": "S7_stage_a"}, {"date": "2026-10-10", "event": "l0_launch_ready", "stage": "S6_readiness"}, {"date": "2026-10-10", "event": "launch_preflight_merged", "stage": "S7_stage_a"}] [source: docs/development/challenge_pipeline/onboarding/cycle_metrics.jsonl]
- Cycle days per stage: UNMEASURED (decision owner: Test Lead; question: A first dated record is not the time spent. Which entry and exit records define each stage's cycle time?)
- Cost per stage: UNMEASURED (measure: owner Executor; tool: Stage report: each run's cap fraction; spend ledgers stay out of the repository)

### electric-motor-magnetics
- Dated stage records: UNMEASURED (measure: owner Test Lead; tool: cycle_metrics.jsonl, hand-recorded until the A9 recorder exists)
- Cycle days per stage: UNMEASURED (decision owner: Test Lead; question: A first dated record is not the time spent. Which entry and exit records define each stage's cycle time?)
- Cost per stage: UNMEASURED (measure: owner Executor; tool: Stage report: each run's cap fraction; spend ledgers stay out of the repository)

### f02
- Dated stage records: UNMEASURED (measure: owner Test Lead; tool: cycle_metrics.jsonl, hand-recorded until the A9 recorder exists)
- Cycle days per stage: UNMEASURED (decision owner: Test Lead; question: A first dated record is not the time spent. Which entry and exit records define each stage's cycle time?)
- Cost per stage: UNMEASURED (measure: owner Executor; tool: Stage report: each run's cap fraction; spend ledgers stay out of the repository)

## Network evidence

### battery-fastcharge-ageing-development-v1
- Graphite agents vs real miners: UNMEASURED (measure: owner Test Lead; tool: Validator-scored Launchpad confirmations from Graphite agents and from real miners on the same Challenge)
- Incentive canary payout correctness: UNMEASURED (measure: owner Test Lead; tool: INCENTIVE-CANARY-01 (PR 971, merged))
- Leaderboard improvement over time: UNMEASURED (measure: owner Test Lead; tool: Validator-scored Launchpad confirmations from stage A)

### electric-motor-magnetics
- Graphite agents vs real miners: UNMEASURED (measure: owner Test Lead; tool: Validator-scored Launchpad confirmations from Graphite agents and from real miners on the same Challenge)
- Incentive canary payout correctness: UNMEASURED (measure: owner Test Lead; tool: INCENTIVE-CANARY-01 (PR 971, merged))
- Leaderboard improvement over time: UNMEASURED (measure: owner Test Lead; tool: Validator-scored Launchpad confirmations from stage A)

### f02
- Graphite agents vs real miners: UNMEASURED (measure: owner Test Lead; tool: Validator-scored Launchpad confirmations from Graphite agents and from real miners on the same Challenge)
- Incentive canary payout correctness: UNMEASURED (measure: owner Test Lead; tool: INCENTIVE-CANARY-01 (PR 971, merged))
- Leaderboard improvement over time: UNMEASURED (measure: owner Test Lead; tool: Validator-scored Launchpad confirmations from stage A)
