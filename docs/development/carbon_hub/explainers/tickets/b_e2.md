# B-E2: Julia and reference failure contract

**Wave:** B

**Map ref:** `WAVE-B/B-E2`

**Status:** DONE

**Target phase:** WB-2

## What and why

Implement the complete typed reference outcome and failure contract for Julia and other registered reference paths.

A required truth service can diverge, time out, disagree, or become unavailable. Carbon must preserve those failures instead of silently substituting a score or a different reference.

## What it adds

An exact primary/witness registered-service seam over B-04, one-use invocation, typed hostile-response and infrastructure failures, immutable retry traces, and deterministic TEST_ONLY supported/failure/disagreement/MMS fixtures.

## Placement and handoff

- **Depends on:** B-04
- **Feeds:** B-GATE
- **Driver:** Codex + SciML
- **Review route:** SciML
- **Master questions:** MQ-004

## Explicit non-goals

It does not restore Julia, select or qualify a solver, permit an unregistered fallback, collapse disagreement, relabel MMS, manufacture truth, or turn infrastructure failure into candidate science.

## Current stage

Implemented and tested in the shipping candidate; bounded completion awaits applicable acceptance and normal merge. B-E4 remains next, todo, and unstarted.

## Maturity ceiling

SPECIFIED, IMPLEMENTED, and TESTED are prepared only for the exact service seam and deterministic TEST_ONLY fixtures. Julia runtime, numerical methods, scientific/security qualification, production, ranking, frontier, and LIVE remain unearned.

## Repository detail

- [Repo ticket](https://github.com/carbonphysicsai/Carbon/blob/fad2c000c60a9da31d60af3c21f2b20ff1d347ed/.agent/tickets/B-E2_reference_failure.md)
- [Wave B controlling board](https://github.com/carbonphysicsai/Carbon/blob/fad2c000c60a9da31d60af3c21f2b20ff1d347ed/.agent/WAVE_B.md)
- [B-E2 implementation plan](https://github.com/carbonphysicsai/Carbon/blob/fad2c000c60a9da31d60af3c21f2b20ff1d347ed/.agent/plans/B-E2_reference_failure.md)
- [B-E2 stable evidence](https://github.com/carbonphysicsai/Carbon/blob/fad2c000c60a9da31d60af3c21f2b20ff1d347ed/.agent/evidence/wave_b/b-e2.md)
- [Registered service boundary](https://github.com/carbonphysicsai/Carbon/blob/fad2c000c60a9da31d60af3c21f2b20ff1d347ed/carbon/evaluation/service_boundary.py)
- [Reference failure fixtures](https://github.com/carbonphysicsai/Carbon/blob/fad2c000c60a9da31d60af3c21f2b20ff1d347ed/carbon/evaluation/service_fixtures.py)

> The boundary accepts only exact B-04 identities and emits only B-04 run records. Failure never yields an artifact or fallback; supported fixtures remain FIXTURE_ONLY and MMS remains verification-only.
