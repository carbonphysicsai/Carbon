## 2026-10-07 — BATTERY-L3-NUMERICS-BUILD-01: battery's Level-3 development variant, training-time numerics (JAX)

**Authority.**
- **Review.** BATTERY-CLIMB-1-REVIEW (#757): the Test Lead's F1 review of
  level-climb-1 accepted `numerics.quasi_newton_family` and
  `numerics.line_search` for a development-only Level 3.
- **Guards.** The Test Lead's attack review (2026-10-07) and its ruling on the
  memory guard (p² × dtype ≤ the memory ceiling only, no invented parameter
  threshold).
- **Bounds.** OWNER-GRAPHITE-DEV-LEVELS-01 F2: Level 3 is a declarative menu.

Everything below is an engineering choice within that authority. It changes
no Level-0 behaviour, and the variant is never served to miners.

**Decisions.**
1. **The pattern of #611.**
   - **The variant:** `carbon/battery/level3.py` builds the variant document
     and registers Carbon's reconstructions. The variant is
     `battery-l3-numerics-v1`, pinned in the registry, current at Level 3 and
     recorded as development record 0002.
   - **The trainer:** `level3_training.py` is `training.train` with exactly two
     edits (its signature and the polish call), checked by a drift test.
   - **Staging:** `level3_worker.py` stages the trainer and replaces only the
     program's build line.
   - **Pinned files:** `recipes.py` and `training.py` are untouched.
   - **Dimension:** `Dimension` gains `NUMERICS` for Admission §3's Level 3. No
     contract document changes.
2. **The default is Level 0.** lbfgs with strong_wolfe, or no Level-3 field,
   leaves no numerics record. The rebuild is Level 0's program, files and
   trainer, byte for byte (tested), and `level3_numerics.polish` calls
   `training.polish` itself for that menu.
3. **The dense routines** (`level3_numerics.scale_by_broyden`) use one inverse
   Broyden-class update for bfgs (φ = 1, τ = 1), ssbfgs (φ = 1, τ =
   Oren-Luenberger) and ssbroyden (φ = ½, τ = Oren-Luenberger).
   - φ = ½, the midpoint of the restricted class, is an engineering choice
     that Phase F and the Level-3 data can revisit.
   - An update with non-positive curvature is skipped, so H stays positive
     definite.
4. **Line searches.**
   - **strong_wolfe** is optax's zoom search, capped at 20 steps (optax's
     default).
   - **backtracking** is optax's Armijo search, capped at 15 (optax's
     default).
   - **none** is the unit step, at the miner's risk.
5. **Guards.** Each has a test, and the first three have mutation tests.
   1. **Dense memory.** A dense routine is refused at compile
      (`development.inverse_hessian_too_large`) when p² × the float size
      exceeds the rebuild worker's memory bound (`worker_memory_bytes`, 4 GiB
      today). That bound is tighter than the sheet's 40 GiB, and it is the
      one a CPU rebuild runs under. p is the trained network's parameter count
      (`NumericsMLP.parameter_count`, shaped without training).
   2. **Evaluations.** Each line search's cap is a recorded constant. The
      reconstruction records `line_search_steps_cap` and
      `evaluations_per_polish_step` (1 + the cap) for the cost calculator's
      worst case. Wiring them into the TRAINING-BUDGET-01 adapter is a
      follow-up, once that stack is on main.
   3. **Lane.** Level 3 is CPU_ONLY_DEV. On any other device the staged
      program raises `ImportError`, which the worker records as an
      environment failure, never the candidate's. The in-process path raises
      `WorkerFailure(candidate=False)`. Built records carry
      "rebuild: CPU-verified only".
   4. **Attribution.** A diverged or non-finite polish trains to non-finite
      predictions, which the exam's finite-shape gate fails: the candidate's
      own fault, never FAILED_INFRA.
   5. **No-op choices.** A non-default choice on a recipe without a polish
      stage is refused (`development.no_polish_stage`).
6. **Scope.** JAX only, for the mlp and deeponet families. The PyTorch
   implementation follows in its own PR. Level 3 has no attack adapter yet,
   so the Attacker refuses Level 3 (`no_attack_adapter_for_challenge_level`)
   until one ships.

**Tests.** `tests/cpu/test_battery_level3.py`:
- the registered variant and its record, built from the code;
- miner surfaces refuse Level 3;
- the trainer drift test;
- default equivalence (staged files and program);
- two rebuilds give the same parameters;
- each routine lowers the loss from a fixed checkpoint;
- every guard, and the mutations.

`test_graphite_development_levels.py` now expects only Level 2 to be
unregistered.

**Maturity.** Implemented and tested on CPU, development only. Not GPU
verified, not security qualified, and never served to miners.
