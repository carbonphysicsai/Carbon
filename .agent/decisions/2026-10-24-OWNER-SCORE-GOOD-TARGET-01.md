# OWNER-SCORE-GOOD-TARGET-01: the good reference model's ceiling on the sealed exam is 0.75

- **Received by:** the Lead session (the 10-24 team Lead, Claude Code desktop), directly from the owner in chat, 2026-10-24.
- **Question asked:** OWNER-SCORE-SCALE-MEANING-01 recorded "good ≤ 0.80 on the sealed exam" as the Lead's reading, pending the owner's confirmation. The owner was asked to reply "confirm 0.80" or give another number.
- **Owner's words:** "0.75".
- **Decision:** on the sealed exam, Carbon's good reference model must score **at most 0.75** (headroom H ≥ 0.25). This replaces the 0.80 reading in OWNER-SCORE-SCALE-MEANING-01.
- **Unchanged:** the default must score at least max(0.10, 5 × the KOTH margin) below the good model. T3 is the least strict acceptable. 1.0 means never wrong on remotely similar problems.
- **Use:** this is the `target` argument of the pool grader's proof suite (POOL_GRADER_AND_PROOF_SUITE_SPEC_20261024.md) and the separation check in the proof run. All other scales and the budget B are still owner picks from the curves.
