# OWNER-LEG-MINIMUM-BEST-AGENT-01: leg minimums come from Carbon's best agent-tested model

Date: 2026-10-20
Status: APPROVED by the owner, directly in the Carbon Validator's session.

## Question

Each Challenge's leg minimums (the A and D a model must reach before it can score) come from a registered baseline recipe. Battery and F02 had none. The Validator recommended simple baselines: Battery's `scaffold_mlp`, and kernel ridge for F02. The owner answered "Whichever is best" for both, and added, verbatim:

> There's no reason we shouldn't set the minimum during agent testing with our best results

Implementation (placeholders):
- **Each baseline's leg minimums bind to its graded submission on the judge image.** The full digests are recorded here because the code deliberately doesn't pin which recipe is the baseline.
- **Battery's placeholder is `scaffold_mlp` against the direct graph interface,** for Battery 2.0: recipe `sha256:08a9c190f4401464715af72e5608521de3569babb2b536ffd7fd14cdc855e0ea`, graph `sha256:cf8fdb067dc4318b1bcd8f4f58517f8aa256079e4b2c6cc3c5741a611715546b`, under served allowlist v6 with no step caps (packet `codex-queue/inputs/battery_baseline/scaffold_mlp_direct_v2_0/`, outside the repository). The graph is unchanged by the cap removal; the recipe binds the 2.0 kit. It supersedes the v6/1.0-kit recipe `sha256:00853517f170e2f6eab3e754cc1dfad2a347c057fdf9f31f93d6fa7fb30213b0`. It supersedes the v1-labelled recipe `sha256:2b9ccd38fa4f8018655f693041f3a206545d86b9a00582a305ed9d8314f325e3` and graph `sha256:c3ff680d66501fa9fab2a0b2d9c5f5aee2199aa4155a070d7d96af737b5e64d6`: the network is node-for-node identical, and only the allowlist label differs (packet `codex-queue/inputs/battery_baseline/scaffold_mlp_direct/`, outside the repository).
  - The Level 0 graph `530026baefc0ed15dc196ffb7631433d754e0bf77977ef4064d4c93945499022` reproduces, but it has 245 outputs where the direct path needs 247, so the same architecture was re-lowered against the direct interface: dense [4, 64, 64, 64, 247], gelu, 2000 steps, batch 400.
- **F02's placeholder is KRR on TRAIN40-v2,** recipe `sha256:2ddb2f17492f2cb78bc5695367d48ccc3698f9197eafd0d33dc00e732a744e2c` (packet `codex-queue/inputs/f02_step1/packets/krr_baseline/`, outside the repository), chosen by leave-one-out on TRAIN only.

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
