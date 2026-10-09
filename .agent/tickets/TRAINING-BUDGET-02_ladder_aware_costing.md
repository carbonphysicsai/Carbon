# TRAINING-BUDGET-02: ladder-aware costing

**Authority:** OWNER-COMPUTE-BUDGET-01; TRAINING-BUDGET-01. The Test Lead
ticketed this on 2026-10-08, from the Level 4 session's finding in #805.

**Status:** slices 1-4 built, with their tests (slice 6 for Levels 0-3):
TRAINING-BUDGET-02-S1, stacked on pool selection (#882). Slice 5 (Level 4
graph FLOPs) is open; Level 4 is refused `cost_level4_graph_pending` until it
lands.
**It blocks** switching on TRAINING-BUDGET-01's compute-budget admission check
(#742). The check stays off until this ticket lands.

## The gap

TRAINING-BUDGET-01's cost calculator compiles a recipe through the Level-0
path. It therefore refuses every Level 1-4 recipe (`parameter.unknown`). A
compute budget switched on today would refuse every development-level recipe,
honest or not, and would price none of them.

## Scope

One reviewable slice per PR.

1. **Ladder-aware compile.** The calculator costs a recipe under the
   development variant it names. It uses
   `development_variants.compile_development` and the shared dispatch
   (`carbon/battery/development_rebuild.py`), and builds the program the
   rebuild would train.
2. **Level 1:** the loss expression's program as compiled (F4 sees it).
3. **Level 2:**
   - **`optimizer.muon_spectral`:** the per-step SVD at full matrix size, with
     the fixed k_r and the extra forward pass. Both sit inside the compiled
     step, so F4 counts them; a test pins that.
   - **`data.pool_selection`:** the effective data volume. N selected cases
     count as `train_cases`, after the strata weights are normalized.
4. **Level 3 (`numerics.*`):** the polish stage's worst case, using each line
   search's recorded cap (`evaluations_per_polish_step`), and the dense
   routines' inverse-Hessian update cost.
5. **Level 4:** the graph's FLOPs, read from its strict-JSON graph.
6. **Tests:** at each level, honest recipes price, and recipes over a declared
   budget are refused (`budget.over_compute_budget`). Nothing is refused as
   `parameter.unknown`.

## Non-claims

- **No live switch.** No contract declares `compute_budget` here. Switching a
  Challenge on stays a separate registry PR after the owner's decision.
- **Not a proxy for time.** The calculator's accuracy as a proxy for rebuild
  time is still decided by R5 on each Challenge's study.
