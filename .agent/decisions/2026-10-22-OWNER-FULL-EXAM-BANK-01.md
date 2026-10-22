# OWNER-FULL-EXAM-BANK-01: every graded submission faces the full active sealed bank, with guardrails

Date: 2026-10-22
Status: APPROVED by the owner.
- First said to the Test Lead ("yes, full bank with those guardrails, send it to the validator. We will rotate the bank as needed with targeted cases").
- Then confirmed directly in the Carbon Validator's session ("Yes, record it").

Scope: all five Challenges (one exam architecture). DEVELOPMENT and testnet now; mainnet follows the same rule unless the owner changes it.
Not covered: whether validators receive the sealed exams. The owner asked to hold that question (2026-10-22).

## Decided

- **The full bank:** each graded submission is scored on the Challenge version's **full active sealed bank**: every QA-passed batch currently active for that version. There is no per-epoch random subset, so all miners and the king face identical hidden cases, and KOTH compares like with like.
- **Guardrails:**
  1. **One graded submission per hotkey per epoch** (the existing epoch limit).
  2. **Coarse miner feedback:** the miner sees a **rounded total only**, with no per-case or per-leg detail. This narrows OWNER-GRADE-FEEDBACK-LADDER-01's private-exam feedback (which showed a rounded total, A and D) to the total alone.
  3. **The weekly overfit check** (OWNER-CADENCE-AND-ROTATION-02): a fresh draw against the king, with early rotation if the gap exceeds the registered margin.
  4. **Rotation** as needed, at most every 90 days, with **targeted** replacement cases (placed by the exam's own law, never labels). Retired batches stay as recorded.

## What implements it

The Validator checks the graders and the Ladder against this record:
- the graders score the full active bank, not a subset;
- the Ladder/readback shows a rounded total only;
- the epoch limit is enforced;
- the rotation tooling replaces batches by the exam law.

Any gap is fixed once, in the common path.
