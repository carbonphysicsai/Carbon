## 2026-10-08 — LAUNCHPAD-COMPUTE-BUDGET-STATUS-01: the Launchpad shows miners whether a recipe is inside its submission compute budget

**Authority.** The owner, 2026-10-08, in the Launchpad Acceptance session:
"please make sure the system is showing miners if they're inside their
submission compute budget in the MLP" (MLP: the Miner Launchpad). Recorded by
a Claude session. It builds on OWNER-COMPUTE-BUDGET-01 and changes none of its
rules. No budget, unit, factor or threshold is chosen here: each Challenge's
budget comes from its own training budget study and the owner's decision on
it. No live contract declares one yet, so every Challenge shows NOT_SET.

Everything below is an engineering choice within that authority.

**Decisions.**

1. **One rule, so the display and the grade cannot disagree.**
   `challenge_contracts.budget_status(challenge, strategy)` returns
   `{schema, status, unit, used, allowed, within}`. `status` is one of
   NOT_SET, SET, MALFORMED, UNMEASURABLE, NO_ADAPTER or UNIT_NOT_CALIBRATED.
   - `check_compute_budget` is refactored to use it, so admission refuses
     exactly what the doors show.
   - Its refusal codes are unchanged. `budget.over_compute_budget` is used
     for SET and over the budget. `budget.cost_unmeasurable` is used for
     UNMEASURABLE, NO_ADAPTER and UNIT_NOT_CALIBRATED. MALFORMED stays a
     repository defect (`RuntimeError`).
   - A refusal now carries `budget: {unit, used, allowed}`.
   - The ladder view reads the declaration through the same parse
     (`declared_compute_budget`).
2. **Fail closed in two places that were open.**
   - A declared budget on a Challenge with no cost adapter used to raise an
     uncaught `NoAdapter`. It is now refused `budget.cost_unmeasurable`.
   - A non-finite cost or ceiling used to be admitted, because a NaN compares
     false. It is now UNMEASURABLE or MALFORMED.
3. **NOT_SET shows no numbers and computes nothing.** That holds for every
   real Challenge today, and for any Challenge without a construction
   contract.
4. **Every door, from one place.**
   - `budget_status` is a free, read-only operation: browser
     `POST /api/v1/operations/budget_status`, MCP `carbon_budget_status`. Its
     gates are `request` and `profile`, as `ladder`'s are.
   - Each practice result in observe and the campaign view carries
     `budget_status` for its recipe. The page shows one line next to the
     training seconds. Practice is never refused by it.
   - `freeze_candidate`, `commit` and `submit` show the status in their
     answer. They refuse a recipe the submission compile would refuse
     before anything is signed or sent: `over_compute_budget` or
     `cost_unmeasurable` with the numbers and a next step, or
     `compute_budget_malformed`.
   - The doors reach the cost calculator only through the training budget
     adapter registry, so they import no Challenge's own modules.
5. **One calculation per recipe per process.** Each recipe's status is
   cached for the life of the process. The cost is deterministic on one
   image, and a declared budget can mean a compile or two short fits.

**Unchanged.**
- The cost calculator's math, every contract, and every readiness record.
- The validator's figure on its pinned image is the one that decides.
