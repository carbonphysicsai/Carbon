# OWNER-CONTAINMENT-ACCEPT-TESTNET-JNO-01: jNO (JAX) python-cpu parent containment accepted for testnet and rehearsal

Date: 2026-10-23 (UTC)
Status: ACCEPTED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), in reply to the Lead's request for a testnet acceptance of the JAX worker containment: "Accept".
Scope: **testnet 567 and rehearsals only**, like the 2026-10-21 v7 acceptance (OWNER-CONTAINMENT-ACCEPT-TESTNET-01). **Not mainnet**: mainnet containment acceptance stays with the human security review (critical path #8).

## Evidence (Validator ruling: VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022.md, section "jNO python-cpu parent containment: the EVIDENCE IS COMPLETE")

- Run J3 at `claude/run-j-tests` @ `edf4debd85801c98d952b16ac57565a7c853449c`: every part rc 0, 0 skips. C-03 8/8 on both parents. Launch controls, escapes, resources, network, filesystem and process all held.
- Run J3b (Part 5 rerun) at `fd06ebc44`: the JAX (a)+(b) tests 4/4, 0 skips. The bounded `/scratch/control-ready` wait is confirmed in production.

## What is accepted

1. The **non-test containment source** at `fd06ebc44`.
2. The **pass rule**: every part passes, nothing skipped.

## Condition

The image that ships must be rebuilt from that source and must pass the same full J pass rule, all parts in one run, before it grades. The acceptance does not bind one test-built image digest.
