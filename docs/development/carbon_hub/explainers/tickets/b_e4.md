# B-E4: Agent utility, leakage, poisoning, and aligned-cheating gauntlet

**Wave:** B

**Map ref:** `WAVE-B/B-E4`

**Status:** IN_PROGRESS

**Target phase:** WB-5

## What and why

Test the autoresearch workflow for utility, hidden-exam leakage, poisoning, gaming, diversity collapse, and unsafe evidence use.

A research assistant can improve apparent performance by exploiting the evaluator, leaking protected structure, or narrowing search rather than producing transferable scientific improvement.

## What it adds

Three causal TEST_ONLY families, an exact four-arm non-qualifying lifecycle, factory-bound rehearsal evidence, a frozen 25-block/100-run calibration, corrected reserve eligibility, conditional headroom analysis, and a content-bound common-model pilot proposal with derived limits.

## Placement and handoff

- **Depends on:** B-07A, B-07B, B-07C, B-07D1, B-07D2, B-07D3, B-07E, B-07F, B-07G, B-07S, B-E1, A12
- **Feeds:** B-GATE
- **Driver:** Codex + research + security
- **Review route:** Research + security + science + statistics + protocol
- **Master questions:** MQ-005, MQ-015, MQ-016, MQ-024, MQ-025, MQ-026

## Explicit non-goals

The owner-unapproved pilot proposal has no provider/execution path and does not approve population, task, seed, evidence, resource, qualification, ratification, shadow, attack, or campaign decisions. No proposal, calibration, test, or rehearsal establishes utility, leakage clearance, security/privacy, science, production, qualification, or LIVE authority.

## Current stage

PR #111 merged B-E4's execution-correctness repair. The current candidate is a content-bound owner-unapproved autonomous-agent pilot proposal with no provider or execution path; v4 remains STILL_BLOCKED and no inference or campaign ran.

## Maturity ceiling

B-E4 is specified, implemented, and tested only for bounded fixture semantics, non-qualifying lifecycle/rehearsal/calibration evidence, execution correctness, and owner-unapproved pilot design. Utility, leakage, diversity, scientific, security/privacy, network, production, qualification, frontier, settlement, emission, and LIVE maturity remain unearned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/.agent/tickets/B-E4_agent_gauntlet.md)
- [Wave B controlling board](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/.agent/WAVE_B.md)
- [B-E4 implementation plan](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/.agent/plans/B-E4_agent_gauntlet.md)
- [B-E4 stable evidence](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/.agent/evidence/wave_b/b-e4.md)
- [B-E4 successor validation regressions](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/tests/cpu/test_be4_successor_validation_repair.py)
- [Historical v2 preregistration proposal](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/.agent/preregistrations/B-E4_recommended_design_v2.json)
- [Historical v2 owner decision pack](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/docs/context/B_E4_PREREGISTRATION_OWNER_DECISION_PACK_2026-09-08.md)
- [v3 STILL_BLOCKED execution-readiness proposal](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/.agent/preregistrations/B-E4_recommended_design_v3.json)
- [v4 STILL_BLOCKED post-calibration proposal](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/.agent/preregistrations/B-E4_recommended_design_v4.json)
- [Owner-unapproved autonomous-agent pilot proposal](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/.agent/preregistrations/B-E4_autonomous_agent_pilot_v1.json)
- [Execution-readiness owner decision pack](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/docs/context/B_E4_EXECUTION_READINESS_OWNER_DECISION_PACK_2026-09-08.md)
- [Non-qualifying preflight calibration manifest](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/.agent/evidence/wave_b/b-e4-preflight-calibration-v1.json)
- [Frozen full-lifecycle calibration manifest](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/.agent/evidence/wave_b/b-e4-full-lifecycle-calibration-v1.json)
- [Full-lifecycle calibration generator](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/scripts/dev/generate_be4_full_lifecycle_calibration.py)
- [Full-lifecycle calibration regressions](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/tests/cpu/test_be4_full_lifecycle_calibration.py)
- [Execution-readiness integration](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/carbon/gauntlet/execution.py)
- [Complete non-qualifying lifecycle](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/carbon/gauntlet/lifecycle.py)
- [Non-qualifying lifecycle integration regressions](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/tests/cpu/test_be4_nonqualifying_lifecycle.py)
- [Non-qualifying rehearsal evidence](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/carbon/gauntlet/evidence.py)
- [Rehearsal integrity regressions](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/tests/cpu/test_be4_rehearsal_evidence.py)
- [Fail-closed readiness carriers](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/carbon/gauntlet/readiness.py)
- [Execution-readiness integration regressions](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/tests/cpu/test_be4_execution_integration.py)
- [Preregistration design helpers](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/carbon/gauntlet/design.py)
- [Preregistration design regressions](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/tests/cpu/test_be4_preregistration_design.py)
- [B-E4 decision series](https://github.com/carbonphysicsai/Carbon/blob/cb04fc05e1a021f47fe109421f508f6635c9f939/.agent/DECISIONS.md)

> The 25-block/100-run calibration is permanently design-analysis-only. V4 remains STILL_BLOCKED with all eight values PROPOSED. Policy exhaustion and ambiguous timeout attribution are nonreplaceable, and conditional headroom is not a population or utility result. Pilot proposal digest sha256:8ca1a79a9cd9866d54f52c797baf0ea392087c4652a1439017339a66610469f3 binds a 300-run/$98.304 ceiling, but all four grouped pilot decisions remain PROPOSED and no approval, provider adapter, execution authorization, inference, pilot, qualifying, shadow, or attack campaign exists. B-GATE remains unstarted.
