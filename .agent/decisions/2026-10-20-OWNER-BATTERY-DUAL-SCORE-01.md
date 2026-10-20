# OWNER-BATTERY-DUAL-SCORE-01: Battery's dual-pack score is 0.5·A + 0.5·D, like the other Challenges

Date: 2026-10-20
Status: APPROVED by the owner, directly in the Carbon Validator's session ("Yes").
Implementation: the Battery dual adapter registers `weighted_arithmetic_mean` 0.5/0.5 (`claude/battery-dual-producer`).

## Question

Battery's active candidate for rule `v3-bank-sched` (OWNER-BATTERY-SCORE-CANDIDATE-01) combines its legs geometrically, a^0.5 · q^0.5. The dual packs for Motor, Cooling, F08 and F02 use the arithmetic 0.5·A + 0.5·D. Should Battery's dual-pack score use the same combination as the others? The Validator recommended yes, for one rule across Challenges.

## Decided

- **Battery's dual-pack evaluation:** TOP = 0.5·A + 0.5·D, with A = registry leg `a` and D = registry leg `q`.
- **Gates first:** G-FEAS@0.05 with plating-v2 truth, `exam_gates`, B15, and the exact paired repeat (`BATTERY_DUAL_PACKET_20261020.md`).
- **OWNER-BATTERY-SCORE-CANDIDATE-01 stays active, unchanged, for rule `v3-bank-sched`.** Nothing is re-scored.
