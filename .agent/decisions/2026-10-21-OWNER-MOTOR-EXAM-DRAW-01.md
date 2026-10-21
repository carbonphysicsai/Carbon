# OWNER-MOTOR-EXAM-DRAW-01: Motor sealed exams are placed to straddle both limits

Date: 2026-10-21
Status: APPROVED by the owner, directly in the Carbon Validator's session ("Approve").

## Why

- **The first sealed batch failed QA:** Motor sealed batch 1 failed `straddle_short:ripple_fraction` (batch_digest `sha256:fbc06b960636b90a77402775feaa5553d8fd17927a08db3bafbcd19ae0e1f2dd`).
- **This was predicted:** a fully random draw meets the at-least-a-third-per-side straddle on both limits only about half the time.

## Decided

- **Placed draws:** each Motor sealed batch is still drawn fresh by seed from the registered Motor law, but placed using a closed-form or fitted estimate so that about a third falls on each side of both limits (mean torque ≥ 4.0 N·m and ripple fraction ≤ 0.30).
  - This is the same approach as the Cooling (OWNER-COOLING-EXAM-DRAW-01) and F08 (N1r strata) draws.
- **The estimate is placement only.** It's never stored or used as a label; labels come from the reference solver.
- **Unchanged:**
  - the batch size (30) and its disjointness from published cases;
  - the U record (0.0052 N·m, 0.026);
  - the record-declared 1/3 within-U stop;
  - the exam QA, which isn't relaxed.
- **The stop rule:** 2 consecutive failing batches still stop the family.
