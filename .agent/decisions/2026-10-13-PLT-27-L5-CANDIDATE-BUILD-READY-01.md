# PLT-27 candidate-build decisions (2026-10-13)

## Decision

Reuse the registered development-only Level 1 loss-expression and Level 3 numerics implementations rather than duplicating them. Add only the absent monotone-fade construction as a sidecar next to pinned battery recipe code. Candidate builds stay outside the miner-facing contract and do not imply Level 5 execution, security acceptance, physical validity, scientific qualification, or adoption.

## Placement supersession after the canonical closure failure

The initial battery-package placement made the unregistered sidecar an entry
in Graphite's `DYNAMIC_PACKAGES` ship. Canonical CI on 4af59e920 measured
82,067 environment characters, 67 above the unchanged 82,000 CI line.
Move the identical construction implementation to
`carbon.development_comparison.monotone_capacity`, the existing DEVELOPMENT
comparison namespace. Update the prospective imports and CLI command and
assert that default registered Graphite jobs do not ship the candidate while
the pinned recipe implementation remains in the closure. A measurement worker
must deliberately include this candidate when preparing its separate arm;
it is not registered default runtime code. The cap, reserve, closure algorithm,
registered modules and existing environment assertion remain unchanged.

## Candidate boundaries

- Monotone fade uses the existing `[Q1, Q1-Qk]` target layout, converts adjacent positive drops to softplus logits, and cumulatively decodes them. Nonpositive observed drops are refused instead of silently adding a floor.
- The sidecar temporarily installs its layout for a single candidate fit call; run it only in a fresh single-arm worker process. Pinned `recipes.py` and `training.py` remain unchanged.
- The Level 1 loss policy does not identify a specific physics-aware expression or term values. Leave that candidate choice `HUMAN_INPUT`.
- Use the existing Level-3 `ssbfgs` plus `strong_wolfe` menu as the bounded comparison hypothesis against `lbfgs` plus `strong_wolfe`; this does not adopt or qualify either method. The policy has fixed search caps. Do not call equal step count equal cost; measurement must consume the recorded evaluation cost. Avoid PR #1309's overlapping training-budget file.

## Stop conditions

No training compute, host run, spend, hidden/sealed input, security acceptance, or base registration is authorized here. Candidate 1's public zero-cost check precedes any training and a zero count ends that candidate with a null result. Candidate 2 remains held until its exact expression is supplied. Candidate 3 remains held until an equal-budget adapter accounts for its line-search cost.


## Candidate-1 no-cost precheck

The public prediction artifact named in the queue input bundle is xperiment-predictions/mlp-s0.json.gz; public EV4 decision references are v4-decision-references.jsonl. From repository root, run python -m carbon.battery.monotone_capacity --count-increases <public-predictions.json.gz> with the supplied gzip path. This reports counts and a stop/continue disposition only; do not proceed if the prediction does not match the unconstrained base recipe.
