# TRAINING-BUDGET-01: a Challenge-neutral budget study and compute-budget limit

**Owner decisions:** OWNER-COMPUTE-BUDGET-01 (2026-10-06), under
OWNER-TRAINING-BUDGET-STUDY-01 and -02.
**Specs:** `docs/development/CHALLENGE_TRAINING_BUDGET_STUDY.md`;
`docs/development/training_budget_study/DECISION_RULES.md` (R1-R8) and
`DECISION_RULES_R9_R11.md` (R9-R11), both frozen;
`docs/development/training_budget_study/SHEET_TEMPLATE.md`.
**Status:** specified; not started.

## Standing rule

**Generalizable by construction** (owner, 2026-10-06: "Make them
generalizable so all challenges can run the same study"). Shared code takes
the Challenge as a parameter and reads its specifics from its sheet and
adapter. A battery-only literal in shared code is a defect. Each slice states
what is shared and what the battery adapter supplies. Battery is the first
instance, never the design.

## Scope

One reviewable slice per PR.

1. **Sheet and adapter types** (`carbon/training_budget/sheet.py`,
   `adapter.py`). The sheet schema of `SHEET_TEMPLATE.md`, loaded from a
   per-Challenge file; any missing value is `HUMAN_INPUT` and blocks the
   phases that need it. The adapter is a protocol over existing Challenge
   records (contract, worker, exam code, equivalence margin, finalist rule,
   generator, panel, TRAIN size). Battery adapter first.
2. **Cost calculator** (`carbon/training_budget/cost.py`). One function:
   recipe + contract + backend → calculated cost, for F0-F4.
   - F4: compile one training step on the pinned image and read the
     compiler's FLOP estimate; multiply by steps; sum over ensemble members;
     weight polish steps by their measured factor. JAX via the compiled
     step's cost analysis; PyTorch via PyTorch's FLOP counter on one traced
     step.
   - Also reports the compiler's peak-memory estimate for the sheet's
     memory ceiling.
   - Deterministic: the same recipe on the same image gives the same number
     on every validator. Tested on CPU against hand-counted small models for
     both backends.
3. **Study harness** (`carbon/training_budget/study.py`). The sweep driver
   for Phases A-H, the record schema of the study's measurements table, the
   work-ledger integration and study-set creation (nested study TRAIN sets
   for Phase G, overlap checks). CPU tests with the DirectBackend before any
   pod time (runbook step 2).
4. **Analysis** (`carbon/training_budget/analysis.py`). Applies R1-R11 as
   written to a records file and writes `analysis.json` and the report's
   numbers: L and its unit, D, s and k, G, plateau curves, formula accuracy.
   No rule is re-implemented with a different threshold; tests bind each rule
   to its frozen text by example.
5. **Capacity calculator** (`carbon/training_budget/capacity.py`). R11's G
   from measured times and the sheet; reused by validator operations to size
   hosts.
6. **Miner cost calculator.** The cost calculator offered in every
   Challenge's research environment as a `Provided` entry under "train"
   (`carbon/challenge_kit/standard.py`), so a miner sees a recipe's cost and
   the budget before submitting.
7. **Contract budget check, built but not switched on.** A Challenge
   contract may declare `compute_budget` in its envelope. When present,
   admission computes the recipe's cost with slice 2 and refuses a recipe
   over budget (a new typed refusal); per-setting ranges stay as sanity
   bounds. No live contract declares it in this ticket.

**Per Challenge, after this ticket:** run the study with its sheet; the owner
decides L, its unit, D and capacity; then a separate PR declares that
Challenge's `compute_budget` and TRAIN size, with tech-lead review.

## Definition of done

- Slices 1-7 merged with tests.
- A test runs the harness end to end on two Challenges' adapters (battery
  and one other with a contract) using fake rebuilds, and shared modules
  contain no Challenge-specific literal (a test greps for registered
  Challenge tokens).
- Every Challenge with a construction contract has an adapter, or a named gap
  in the same style as the research-environment standard.

## Non-claims and human input

- No production budget, TRAIN size, margin or ceiling is chosen here; they
  come from sheets and owner decisions on study results.
- The calculator's accuracy is not established by its tests; R5 on each
  Challenge's study decides whether a compute budget can be adopted.
- Running the study needs owner approval of pod spend per Challenge.
