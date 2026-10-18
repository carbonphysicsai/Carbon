# ScoreLab dual-score experiment — prospective development slice

Ryan's 2026-10-18 direction: redesign the experiment with Research. One TOP
SCORE must reward both broad native-output accuracy/robustness (A) and
solver-verified design usefulness (D); keep both visible and mandatory gates
noncompensable. Optimize candidate content and ratio on independent problems.

This bounded slice adds a pure candidate reducer to `carbon.scoring` and one
`ScoreEngine` entry point. It does not alter existing v1/v3 scoring. The same
entry point is available to the workbench and validator; no validator caller,
physics predicate, model execution, reference solver or deployment is changed.
Measurement producers remain responsible for trusted reference applicability,
whole-problem splits, common masks, P/Q/w and cost measurement.

## Working decisions

- Scope is PUBLIC_DEVELOPMENT or SYNTHETIC_DEVELOPMENT only. No official score.
- All metric identities, units, normalization scales, within-leg weights,
  required leg minimums and value weight are explicit pack fields. No Challenge
  defaults. Missing measurements are not zero-filled.
- Research's first two candidate aggregators are weighted arithmetic mean
  (compensation control) and `min(A,D) * A**(1-wD) * D**wD` (joint candidate).
  The latter cannot exceed the weaker leg but may over-penalize weakness. No
  adoption is implied. Joint weights are strictly between zero and one;
  arithmetic endpoints are diagnostic controls.
- Reference uncertainty/infra and candidate faults stay separate. A reference
  gap in a comparison defers every compared model's total, rather than dropping
  a different case for each model. Q remains diagnostic, never mixed into P.
- Leg minimums may be explicitly null in exploratory packs; that is no claim
  of elite qualification. Existing mandatory gate outcomes remain compulsory.
- Gate names alone do not establish the Challenge's required physics/accuracy
  predicates. A reviewed Challenge measurement/pack contract must supply those
  predicates and any elite floors before authoritative use. This reducer is
  exploratory arithmetic, not a scientific or validator acceptance result.
- Each resolved decision outcome has an explicit registered eligibility and D
  cap. There is no automatic reward for NONE_FEASIBLE or missed opportunity.
  Raw measured D and outcome-adjusted D remain visible. Missing robustness or
  decision measurements cannot be silently imputed.
- For the arithmetic candidate, wD is a formula coefficient, not an empirical
  fraction of ranking influence. For the capped candidate it is a geometric
  emphasis parameter, not a literal value/accuracy percentage.
- Typed measurement digests canonicalize malformed candidate values to local
  invalidity. They are not original-prediction byte hashes; original artifacts
  and their provenance remain in the existing bank/producer evidence.
- The exposed Motor five-fit/one-bank results diagnose candidate rules. They
  do not establish independent robustness or the optimal ratio. Tuning and
  confirmation must split whole underlying problems/source-bank ancestry;
  A and D may be measured on the same registered question within either split.

## Scope and validation

Primary placement is the existing scoring core. The Development Hub is frozen
under the current delivery policy; no hub mutation is required. Owned files:
`carbon/scoring/dual_score.py`, the delegating method in
`carbon/scoring/engine.py`, and `tests/cpu/test_dual_score.py`.

Focused tests cover exact pack/input binding, units/scales, visible components,
both formulas, monotonicity and weak-leg cap, gates/minimums, reference-common
deferral, candidate failure typing, missing robustness, Q separation, and
entry-point parity. Product runs focused tests and existing scoring regression
through the canonical environment; source authors do not start competing jobs.
Entry-point delegation parity is not proof of an actual validator/ScoreLab
adapter integration; the current slice changes no validator caller. Full
caller adoption remains a separate integrated check, not an implied result.
Completion requires those results and Lead's normal integration/required checks.

Maturity ceiling: implemented/tested development candidate arithmetic only;
no production score, scientific qualification or selected policy values.
