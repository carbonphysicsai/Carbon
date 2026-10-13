# PLT-27 construction candidates: build readiness

**Ticket:** PLT-27 L5-CANDIDATE-BUILD-READY-01
**Base:** main `c6e41ec3e5348b699815b62ea2a22d3425b4ffe4`
**Scope:** DEVELOPMENT candidate construction only. No base registration, miner admission, Challenge promotion, Level-5 execution, training run, spend, sealed data, or qualification.

## Candidate 1 — monotone capacity fade

`carbon/battery/monotone_capacity.py` wraps an existing JAX MLP/DeepONet battery recipe. Its Layout sidecar leaves `recipes.py` and `training.py` byte-identical. For the existing fade representation `[Q1, Q1-Q10, Q1-Q20, ...]`, training targets become `[Q1, softplus_inverse(d1), softplus_inverse(d2), ...]`, where each `di` is the adjacent checkpoint loss. Decoding applies softplus and cumulative sums before the existing `Layout.split`, so reconstructed capacity cannot rise. Non-finite or non-positive observed decrements, non-fade recipes, unsupported families, and non-JAX backends refuse by name. Positive observed decrements are required because the inverse is finite only on positive inputs; no zero-floor is invented.

Use `carbon.battery.monotone_capacity.build(family, settings)` for the candidate arm and `carbon.battery.recipes.build(family, settings)` for its baseline, with identical registered recipe settings, seeds, steps, training rows, and worker limits. Run each fit in its own fresh, single-arm worker process: the wrapper temporarily installs the candidate Layout while the fixed Carbon model creates its Layout, then restores the process binding in `finally`. This module is not an arbitrary-code interface. The unspent public zero-cost check remains a prerequisite before any training: count capacity increases in public development predictions; if the count is zero, stop with no-measurable-help and do not train.

## Candidate 2 — physics-aware loss expressions

Reuse the registered development-only `battery-l1-loss-expressions-v1` policy, its `carbon.reconstruction.loss_expressions` implementation and `carbon.battery.level1` reconstruction. It is explicitly not miner-facing. The review packet states the miner contract still excludes `objective.loss_expressions`. The queue does not name a concrete expression or provide its term weights/feature selection. Those values are `HUMAN_INPUT`; this ticket does not invent an objective and the candidate cannot start until its exact expression is recorded. No base contract or registry is widened here.

## Candidate 3 — quasi-Newton polish

Reuse `battery-l3-numerics-v1`, `carbon.battery.level3_numerics`, `level3_training`, and `level3_worker`. The proposed DEVELOPMENT arm is `ssbfgs` with `strong_wolfe`, compared with existing `lbfgs` plus `strong_wolfe` under the same recipe and `polish_steps` on the CPU-only development lane. This is a reversible menu selection for measurement, not adoption; the gain remains UNMEASURED. The Level-3 reconstruction already records worst-case evaluations per polish step and line-search caps, but the decision record says that wiring into the training-budget adapter is follow-up work. Exact-budget measurement is not ready until that adapter consumes the recorded cost. PR #1309 currently edits `carbon/battery/training_budget.py`; this ticket leaves it untouched to avoid overlap.

## Measurement handoff constraints

Use the existing equal-budget construction comparison once OPT-17 supplies its interface, or its documented public-data fallback. Match compute and tokens, steps, width, depth, seeds, data, and wall-clock cap. Report actual budgets for both arms rather than inferring equality from step count. Evaluate the target and every registered near variant; an exact-task-only gain is not a win. Preserve paired intervals and allow `UNRESOLVED` / “no measurable help” as valid outcomes. Use public data only. The hunt-recovery caveat in `codex-queue/inputs/L5_MEASUREMENT_BRIEF_01.md` must accompany every result.

## Readiness and maturity

- Candidate 1: DEVELOPMENT implementation and focused CPU unit tests only; public zero-cost monotonicity count not run; no training or measured effect.
- Candidate 2: existing DEVELOPMENT implementation reused; exact candidate expression requires HUMAN_INPUT; no result.
- Candidate 3: existing DEVELOPMENT CPU-only implementation reused; exact arm and true-cost adapter are unresolved; no result.
- All candidates remain unqualified and unadopted. Level 5 execution, hostile-code isolation, GPU determinism, image pinning, and any security acceptance remain outside this ticket.
