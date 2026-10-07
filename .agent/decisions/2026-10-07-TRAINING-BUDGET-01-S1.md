## 2026-10-07 — TRAINING-BUDGET-01 slice 1: sheet and adapter types, and the cost calculator

**Authority.** OWNER-COMPUTE-BUDGET-01 and its ticket, TRAINING-BUDGET-01 (scope
items 1 and 2). The Test Lead set the build order (2026-10-07). Everything below
is an engineering choice within that ticket. No budget, factor, rate, ceiling
or margin is chosen.

**Decisions.**

1. **One sheet file per Challenge** (`carbon/training_budget/sheets/<id>.json`,
   schema `carbon.training-budget.sheet.v1`).
   - **Missing values:** a value that is missing, null or `HUMAN_INPUT` blocks
     exactly the phases the template's "Used by" column names.
   - **No sheet:** a Challenge with no sheet blocks every phase. No battery
     sheet is committed: it is owner input.
   - **Malformed values:** a set value of the wrong form is refused, never read
     as unset.
2. **The study seed root is never in a sheet.** A sheet records only where the
   root is held and its sha256 commitment. A raw value is refused. The root
   and its one-shot confirmation set live only on the producer host (the
   Test Lead's S11 lesson).
3. **The sheet's image is a released worker image by registry digest**
   (`ghcr.io/carbonphysicsai/<repository>@sha256:…`). The study runs on
   released digests only. The harness (slice 3) checks the release record.
4. **Adapters are found through `carbon/training_budget/adapters.json`**, so the
   shared modules name no Challenge. A test greps them for registered
   Challenge tokens.
   - **Battery:** its adapter is `carbon.battery.training_budget`.
   - **Named gaps:** burgers, cold plate and motor are named gaps, each with
     its reason. A test requires every construction contract to have an
     adapter or a gap.
5. **The cost calculator measures the program the Challenge's own code
   compiles**, with no change to any pinned implementation.
   - **JAX:** the adapter's fit runs with `jax.jit` captured. The first
     jitted program holding a loop is compiled, never run.
     - **Loop counting:** XLA's cost analysis counts a loop body once whatever
       its trip count (measured: a 1-, 10- and 100-step scan all report one
       body). Each `scan` body is therefore compiled alone and counted
       `length` times.
     - **Refusals:** a `while` loop is refused (`cost_unbounded_loop`).
     - **Peak memory:** the compiler's peak-memory estimate comes from the
       same compile.
   - **PyTorch:** PyTorch's FLOP counter over a member's 16- and 32-step fits.
     The difference is the cost of 16 steps, and a non-linear difference is
     refused. No compiler memory estimate exists on CPU, so it is reported as
     none.
   - **Backend conventions:** the two backends count by their own
     conventions. XLA counts element-wise operations; PyTorch counts matrix
     products. The study fits each backend's conversion to seconds
     separately.
6. **F0-F4 as the study specification defines them.**
   - **F0 and F1** are exact: steps, and parameters × cases per update ×
     steps, summed over members.
   - **F2 and F4 factors:** F2 needs the study's measured `k_opt` and
     `k_polish`, and F4 needs `k_polish` when a recipe polishes. F3 and F4 in
     seconds need the study's fitted conversion. Each is `HUMAN_INPUT` until
     supplied.
   - **No training program:** a recipe with none (a nearest-neighbour recipe)
     costs 0.
7. **The battery adapter keeps the recipe's own path.**
   - **Settings:** the measurement fit changes only the main step count.
     `polish_steps` stays, so a recipe never switches between the classic and
     general training paths.
   - **Ensembles:** an ensemble is one program of identical members, each with
     `steps // members` steps, as `recipes.Ensemble` trains them.
   - **Data:** costs are measured on pinned TRAIN v1. A study TRAIN size is
     drawn from it by position, because cost depends on shapes only.

**Tests.**
- `tests/cpu/test_training_budget_sheet.py` covers the sheet and the adapter
  registry.
- `tests/cpu/test_training_budget_cost.py` covers the cost calculator.
- **Hand-counted:** a JAX scan of one product is counted per step. A PyTorch
  step is counted as its forward and weight-gradient products.
- **Battery, both backends:** F1 is P·B·S; F4 is linear in steps; members are
  counted; KNN costs 0; a study TRAIN size changes cases per update.
- **Fail closed:** unbounded loops and fits with no loop are refused; `jit` is
  restored after capture.
- **Skips:** the PyTorch tests skip where torch is not installed.

**Maturity.** Implemented and tested on CPU. The calculator's accuracy as a
proxy for rebuild time is not established here: R5 on each Challenge's study
decides it.
