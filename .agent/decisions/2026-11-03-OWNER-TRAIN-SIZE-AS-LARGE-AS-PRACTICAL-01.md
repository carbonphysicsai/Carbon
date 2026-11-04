# OWNER-TRAIN-SIZE-AS-LARGE-AS-PRACTICAL-01: size every TRAIN set as large as is useful, cheap and practical to train

Date: 2026-11-03 (CST, ~10:53)
Status: DECIDED by the owner, directly in the Lead session (local_87151681-c66e-4949-a26c-23c4641b5722). A standing rule for every version ("throughout").
Owner's words: "I want to grow the training data to whatever size makes the most sense for us throughout and cost wise. If it's cheap. Bigger. But if too long to train. Cap it. Make sense? As much as I'd practical and best for learning."
Context: EQ's TRAIN_QUALIFICATION_TABLE_20261103.md (RB 2.0 120 → 240 ~$1–3; BT 3.0 118 → ~240 ~$2–4). Earlier he said "I really think that's an important check to get right" (the R38 TRAIN check).

## Decided (how the team applies it; the Lead's reading, stated to the owner)
Each version's TRAIN size is set from three MEASURED numbers:
1. **Useful:** the G6 learning curve (25 / 50 / 100 %). Grow while the curve still clearly improves; stop where it flattens.
2. **Cheap:** the solve cost per added design, within the owner's approved data spend (USD 135 G1–G9, inside the week's USD 250). Any larger figure goes to the owner first.
3. **Practical:** the rebuild training time. Every submission retrains from scratch, and crown averaging rebuilds N = 10. The cap is where the default catalog model's or a current king's training time on that TRAIN exceeds ~50 % of the registered 648 s build wall. The Lead's working cap is stated to the owner; the walls themselves are unchanged (OWNER-GRAPH-WALLS-KEEP-01).

**Applied now:**
- **RB 2.0 STAGE2 TRAIN = 240** (cheap, far inside the time cap); it grows again before the freeze only if G6 says so.
- **BT 3.0 TRAIN** grows to ≥ ~240 by the same check, before the freeze.
- **Motor 1.7 / Cooling 1.8:** G6 decides. Motor's missing saturation regime goes to the next version's hardness card.

**Who:** EQ (the R38 owner) sizes all 4 by this rule and posts each size with its three numbers. The Validator receipts each. A new TRAIN identity is only allowed before the freeze, and live versions keep theirs.
