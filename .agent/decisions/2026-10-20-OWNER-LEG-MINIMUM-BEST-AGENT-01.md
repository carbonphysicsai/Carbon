# OWNER-LEG-MINIMUM-BEST-AGENT-01: leg minimums come from Carbon's best agent-tested model

Date: 2026-10-20
Status: APPROVED by the owner, directly in the Carbon Validator's session.

## Question

Each Challenge's leg minimums (the A and D a model must reach before it can score) come from a registered baseline recipe. Battery and F02 had none. The Validator recommended simple baselines: Battery's `scaffold_mlp`, and kernel ridge for F02. The owner answered "Whichever is best" for both, and added, verbatim:

> There's no reason we shouldn't set the minimum during agent testing with our best results

Implementation (placeholders):
- **Battery's placeholder is `scaffold_mlp` against the direct graph interface,** recipe `sha256:2b9ccd38…e3`, graph `sha256:c3ff680d…d6`.
  - The Level 0 graph `530026ba` reproduces, but it has 245 outputs where the direct path needs 247, so the same architecture was re-lowered against the direct interface: dense [4, 64, 64, 64, 247], gelu, 2000 steps, batch 400.
- **F02's placeholder is KRR on TRAIN40-v2,** recipe `sha256:2ddb2f17…4e2c`, chosen by leave-one-out on TRAIN only.

## Decided

- **The baseline:** each Challenge's registered baseline is the best recipe from Carbon's own agent testing (the agent-miner rehearsal), chosen by total score on that Challenge's calibration pack. Its A and D are the leg minimums.
- **Shared rule:** the same rule applies to every Challenge, Motor, Cooling, F08, F02 and Battery, so one rule holds across Challenges.
- **Until agent testing produces a best recipe for a Challenge,** the current simple baseline stands in as the placeholder:
  - Motor, Cooling and F08: their KRR packets;
  - Battery: `scaffold_mlp`;
  - F02: KRR on TRAIN40-v2.
- **The baseline entry never contends** (`leg_minimum_source_not_a_contender`), so Carbon's own model never takes a crown.
- **Each new baseline is a recalibration.** It's a new leg-minimum source on the judge image, and it's prospective, so nothing is re-scored.

## Consequence (stated to the owner)

- **A miner must beat Carbon's best agent-built model on both legs to score at all.**
- **Until one does, the Challenge has no winner, and its share burns** under the KOTH rule.
