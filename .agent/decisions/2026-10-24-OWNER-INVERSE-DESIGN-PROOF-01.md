# OWNER-INVERSE-DESIGN-PROOF-01: grading is fast, answers known in advance, hard and strict; inverse design must be proven tested

Date: 2026-10-24
Status: **DECIDED by the owner, directly in the Carbon Validator's session.** The owner's words: "It just has to be fast grading with answers known ahead of time and then I'm fine. It has to be hard and graded strictly. Inverse design is the goal of a perfect surrogate. We have to prove we are testing that thoroughly".
Builds on: OWNER-D-IS-OPTIMIZATION-01, OWNER-SCORE-SCALE-MEANING-01, OWNER-GEN-SCOPE-AND-HARD-D-01. It confirms REVISION 3a: a pre-solved candidate pool per target, and no solver at grade time.

## Decided

- **Fast grading with answers known ahead of time:** every target's truth (the pool's true outputs, feasibility within U, the reference optimum) is precomputed and sealed per exam version. Grading runs the model plus Carbon's optimizer only.
- **Hard and strict:** the owner's earlier bars stand (good ≤ 0.80 on sealed; 1.0 reserved for never wrong and generalising). The scales are strict and picked from curves.
- **Inverse design is the goal:** the design half is Carbon's optimizer doing inverse design with the model (finding designs that meet hidden targets, including the variants), scored on true feasibility and closeness to the reference optimum, plus prediction honesty.
- **Proof of thoroughness is REQUIRED before launch.** For each Challenge, this evidence is shown to the owner:
  1. **An oracle check:** the pool's own truth, used as the "model", scores 1.0 on D.
  2. **A strictness curve:** truth with injected error of increasing size (noise, bias near the limits, a wrong trend) gives a score that falls monotonically, and is clearly below 1 at errors the size of a good model's.
  3. **Gaming controls lose:** a model optimistic near the limits; a model accurate only in-distribution (it fails the variants); a model that's accurate everywhere except near the optimum.
  4. **Coverage:** the number of targets and variants, the pool density near the optimum and the limits, and the share of the extended region sampled.
  5. **Feedback-leak control:** repeated submissions with score feedback can't hill-climb to a target's optimum (the totals are combined and rounded, and the allowance limits them). This is shown by a simulated attack.
  6. **Separation:** the default is clearly below the good model, and the good model ≤ 0.80 (the proof run).

## Not covered

The numeric values (targets, pool size, scales, budget) are picked from curves later. Mainnet.
