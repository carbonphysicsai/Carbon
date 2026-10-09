## 2026-10-09 — TRAINING-BUDGET-02-S1: the cost calculator prices battery Levels 1-3 as the development rebuild trains them

**Authority.**
- **The ticket.** TRAINING-BUDGET-02 (#806), scheduled by the Test Lead
  after pool selection (#882), on which this is stacked.
- **What it blocks.** It blocks switching on TRAINING-BUDGET-01's
  compute-budget check.
- **The scope.** This is an engineering change. No contract declares a
  compute budget, so nothing is refused today.

**Decision.** This PR covers ticket slices 1-4 and their tests (slice 6 for
Levels 0-3).
- **Ladder-aware compile.**
  - `cost(..., level=L)` and the CLI's `--level` cost a recipe under level
    L's current development variant.
  - Battery's adapter compiles it with `compile_development` and builds the
    model the development rebuild builds (`development_rebuild`).
  - Level 0 is the calculator as before.
- **Level 1:** the loss expression's own trainer is captured, and F4 sees it.
- **Level 2:**
  - SpecMuon's per-step SVD and extra forward pass are inside the compiled
    step, so F4 counts them. A test pins that the spectral step costs more
    than base Muon's.
  - A pool selection prices at its drawn size: N cases train and N bound the
    update.
- **Level 3:** a polish prices at its worst case, through the new
  `Program.polish_factor`:
  - the line search's recorded evaluations per step, each a full-batch loss
    and gradient expressed in minibatch steps;
  - plus a dense routine's inverse-Hessian update, about 4 p² FLOPs per
    polish step (`polish_dense_flops_per_p2`; 0 for L-BFGS);
  - a measured `k_polish` still decides when supplied.
- **Level 4** is refused, typed, as `cost_level4_graph_pending`, until slice
  5 reads its FLOPs from the compiled graph (G5).
- **The budget check.**
  - `compile_development` checks the declared compute budget at its own
    level (`check_compute_budget(..., level=L)`). A recipe over it is refused
    `budget.over_compute_budget`.
  - The calculator compiles with `check_budget=False`, so the check never
    recurses.

**Tests.** `tests/cpu/test_training_budget_ladder.py`, 15 passed:
- Level 0 is unchanged;
- honest Level 1-3 recipes price;
- a development field at Level 0 is still refused;
- SpecMuon costs more per step than base Muon;
- a pool selection prices at its size;
- three Level 3 worst cases hold to the formula;
- Level 4 is refused, typed;
- over-budget refusal at a development level;
- the compile checks the budget at its level.

**Not claimed.**
- **Accuracy as a time proxy.** The calculator's accuracy as a proxy for
  rebuild time is still decided by R5 on each Challenge's study.
- **Level 4 graph FLOPs** are slice 5, not this PR.
- **The 4 p² dense-update figure** is an engineering constant for a worst
  case. It is not a measurement.
- **No switch.** No contract's compute budget is switched on here.
