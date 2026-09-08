# B-E4: Agent utility, leakage, poisoning, and aligned-cheating gauntlet

**Wave:** B

**Map ref:** `WAVE-B/B-E4`

**Status:** IN_PROGRESS

**Target phase:** WB-5

## What and why

Test the autoresearch workflow for utility, hidden-exam leakage, poisoning, gaming, diversity collapse, and unsafe evidence use.

A research assistant can improve apparent performance by exploiting the evaluator, leaking protected structure, or narrowing search rather than producing transferable scientific improvement.

## What it adds

Three independently causal two-level toy-construction families, a private exploratory TEST_ONLY pack, five deterministic data-only fixture drivers, an exact four-arm non-qualifying lifecycle, complete-run metering, factory-bound rehearsal evidence, prospective typed reserves, and one frozen 25-block/100-run full-lifecycle calibration with a content-bound v4 proposal.

## Placement and handoff

- **Depends on:** B-07A, B-07B, B-07C, B-07D1, B-07D2, B-07D3, B-07E, B-07F, B-07G, B-07S, B-E1, A12
- **Feeds:** B-GATE
- **Driver:** Codex + research + security
- **Review route:** Research + security + science + statistics + protocol
- **Master questions:** MQ-005, MQ-015, MQ-016, MQ-024, MQ-025, MQ-026

## Explicit non-goals

The candidate does not establish representative autonomous-agent scope, stochastic variability, utility/diversity sufficiency, shadow/dependence or leakage evidence, trusted attacks, authenticated ratification, one-use execution authorization, or qualifying evidence. No proposal, calibration, dry run, synthetic result, or rehearsal record establishes utility, leakage clearance, security/privacy, science, production, qualification, or LIVE authority.

## Current stage

PR #109 merged B-E4's rehearsal integrity/evidence stage. This successor candidate records a frozen 25-block/100-run full-lifecycle calibration and v4 proposal; v4 remains STILL_BLOCKED and no qualifying, shadow, or attack campaign ran.

## Maturity ceiling

B-E4 is specified, implemented, and tested only for bounded fixture semantics, non-qualifying lifecycle/rehearsal evidence, frozen full-lifecycle calibration, and fail-closed design-analysis carriers. Utility, leakage, diversity, scientific, security/privacy, network, production, qualification, frontier, settlement, emission, and LIVE maturity remain unearned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/.agent/tickets/B-E4_agent_gauntlet.md)
- [Wave B controlling board](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/.agent/WAVE_B.md)
- [B-E4 implementation plan](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/.agent/plans/B-E4_agent_gauntlet.md)
- [B-E4 stable evidence](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/.agent/evidence/wave_b/b-e4.md)
- [B-E4 successor validation regressions](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/tests/cpu/test_be4_successor_validation_repair.py)
- [Historical v2 preregistration proposal](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/.agent/preregistrations/B-E4_recommended_design_v2.json)
- [Historical v2 owner decision pack](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/docs/context/B_E4_PREREGISTRATION_OWNER_DECISION_PACK_2026-09-08.md)
- [v3 STILL_BLOCKED execution-readiness proposal](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/.agent/preregistrations/B-E4_recommended_design_v3.json)
- [v4 STILL_BLOCKED post-calibration proposal](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/.agent/preregistrations/B-E4_recommended_design_v4.json)
- [Execution-readiness owner decision pack](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/docs/context/B_E4_EXECUTION_READINESS_OWNER_DECISION_PACK_2026-09-08.md)
- [Non-qualifying preflight calibration manifest](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/.agent/evidence/wave_b/b-e4-preflight-calibration-v1.json)
- [Frozen full-lifecycle calibration manifest](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/.agent/evidence/wave_b/b-e4-full-lifecycle-calibration-v1.json)
- [Full-lifecycle calibration generator](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/scripts/dev/generate_be4_full_lifecycle_calibration.py)
- [Full-lifecycle calibration regressions](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/tests/cpu/test_be4_full_lifecycle_calibration.py)
- [Execution-readiness integration](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/carbon/gauntlet/execution.py)
- [Complete non-qualifying lifecycle](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/carbon/gauntlet/lifecycle.py)
- [Non-qualifying lifecycle integration regressions](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/tests/cpu/test_be4_nonqualifying_lifecycle.py)
- [Non-qualifying rehearsal evidence](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/carbon/gauntlet/evidence.py)
- [Rehearsal integrity regressions](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/tests/cpu/test_be4_rehearsal_evidence.py)
- [Fail-closed readiness carriers](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/carbon/gauntlet/readiness.py)
- [Execution-readiness integration regressions](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/tests/cpu/test_be4_execution_integration.py)
- [Preregistration design helpers](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/carbon/gauntlet/design.py)
- [Preregistration design regressions](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/tests/cpu/test_be4_preregistration_design.py)
- [B-E4 decision series](https://github.com/carbonphysicsai/Carbon/blob/4b76bda3ee137cce42726ca61f1b0c01cdf0ba05/.agent/DECISIONS.md)

> The 25-block/100-run full-lifecycle calibration is permanently design-analysis-only. V4 changes work caps to 49/49/53/53/27, wall caps to 2/2/2/2/1, and transfer margin to 0.2797202700265491 Q while retaining primary floor 0.4017350715246475 Q. Its design digest is sha256:038eecfa8c17ae5bb309e9417f9397777168ddeaf281c9601ca35402b5caf836 and full proposal digest is sha256:faffff8e9d7f4c6748d76c84cfc0cd26f19eb996ece96d9705b89362d86d4f37. All eight values remain PROPOSED; deterministic policies are not an authorized autonomous-agent population; ratifications are empty; qualifying_execution_ready is false; and role verification/authorization remain unavailable. No qualifying, shadow, or attack campaign ran, no later ticket is selected, and B-GATE remains unstarted.
