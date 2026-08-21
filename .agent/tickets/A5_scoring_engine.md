# Ticket A5 — Scoring engine + fixture Score Pack (C5)

**Wave:** A
**Status:** `in_progress` — bounded fixture-only implementation on
`agent/a5-scoring-engine` from exact main
`af43d68ec3b9dcfd8818a61ab219759b2c859d78`
**Build_Out:** C5; `Design_Specs/Scoring.md` is the sole scoring authority
**Depends on:** A0–A4; reuse A3 exact identity/digest validation and preserve
A4 pin compatibility without accepting seeds or draw identity

## Maturity gate

This ticket is **SPECIFIED / RATIFIED** and **IMPLEMENTED on the bounded draft
branch head**. It is **TESTED only for the exact fixture-only CPU scope recorded
below**, remains **NOT PRODUCTION-QUALIFIED**, and stays `in_progress` pending
draft-PR review and a separately authorized merge/closeout. Fresh remote/main,
concurrency, authority, dependency, and repository-scope checks passed before
branch creation. The clean Python 3.11.11 pre-edit regression baseline reported
`622 passed in 5.71s`; that baseline remains regression context, not A5
behavioral evidence.

## Goal for this implementation

Implement a deterministic, standard-library-only scoring engine that loads
one strict UTF-8 JSON fixture Score Pack by exact bytes plus a required
external tagged SHA-256; accepts only a closed validator-authorized scalar
`ScoreInput`; applies binary hard gates and the pack-bound weighted-geometric
top-level aggregate under `python_binary64_v1`; and returns a private,
fixture-origin, structurally non-emission-authoritative `InternalResult`.

## Ratified contract

- Strict UTF-8 JSON is the only runtime Score Pack artifact. YAML is
  authoring/documentation form only and is never parsed by A5.
- Pack identity is the exact source bytes plus a mandatory external
  `sha256:<64 lowercase hex>` digest. There is no internal content-hash field,
  content-hash stub, path-only identity, fallback pack, or missing-digest
  fallback.
- The exact pin binds challenge ID/version, scoring version/digest, required
  generator version/digest, schema version, numerical profile, and exact
  `fixture_origin`.
- Schema version is exact `"1.0"`. Every hard-gate and soft-leg record requires
  exact discriminator `"operator"`; `"type"`, `"kind"`, aliases, omission,
  duplicates, and unknown values reject. Within-leg `weighted_sum` is implicit,
  so nested `"aggregation"` is forbidden.
- `ScoreInput` is closed, complete, validator-authorized, and scalar-only.
  Unknown/extra fields and forbidden inputs are rejected, never ignored.
  Predictions, references, relative-error generation, and raw percentile
  computation belong to A8 or later metric operators.
- Mandatory hard gates are binary. A threshold gate passes only when the
  actual value is strictly `<` its threshold; equality fails. An actual
  mandatory failure requires **both** `combined_score = 0.0` and
  `eligible_for_emission = False`.
- `ScoreEngine.score(score_input: ScoreInput | None, pack)` accepts `None` only
  for a valid `PACK_NOT_READY` pack. Ready packs require the exact input;
  unready packs reject non-`None` input. Resolved gates are evaluated fully in
  declared order without short-circuiting; mandatory failure retains the full
  gate vector and returns no soft evidence.
- Missing/malformed/incomplete input and infrastructure/reference failures are
  non-scientific errors. They produce no invented failed gate and no
  scientific zero.
- Top-level aggregation is weighted geometric only. Weights are pack-bound,
  strictly positive, exact-decimal-sum-to-one, never normalized, and never
  defaulted. 0.45/0.30/0.25 may appear only as pack data, not engine
  constants.
- The exact Wave A numerical profile is `python_binary64_v1`: dependency-free
  Python binary64, exact type/range/finite validation, a zero-component branch,
  and standard-library log-space aggregation as ratified in
  `.agent/DECISIONS.md` and `Design_Specs/Scoring.md`.
- `HUMAN_INPUT` and `BLOCKED_FOR_LIVE_UNTIL_SET` are the only explicit
  unresolved scientific-value states. An unresolved mandatory threshold or
  score-bearing value yields `PACK_NOT_READY`, no combined score, and false
  eligibility. `null` is not an unresolved-state alias.
- A5 accepts only exact `fixture_origin = true`. Every A5 pass result remains
  non-emission-authoritative and has `eligible_for_emission = False`.
- `InternalResult` is private and does not contain seeds, seed roles, draw IDs,
  evaluation binding, strategy/submission/miner/validator identity, fees,
  weights, public-card behavior, receipts/signatures, persistence, logging,
  tie-breaking/decay fields, or weight-writing behavior.
- `Design_Specs/Scoring_Formulas.md` is subordinate. Its historical
  0.40/0.35/0.25, sigmoid official-hard-gate, fp32/JAX, arithmetic aggregate,
  and missing-input fail-or-zero text is superseded by `Scoring.md`.

## Bounded implementation Definition of Done

- [x] `ScoreEngine.score(score_input: ScoreInput | None, pack) ->
      InternalResult` implements the exact ready/unready entry matrix after
      exact pack bytes/digest/pin validation.
- [x] Strict schema `"1.0"` requires exact `"operator"` discriminators, rejects
      aliases/unknowns/duplicates, and rejects nested `"aggregation"`.
- [x] Canonical fixture runtime JSON exists under
      `tests/fixtures/score_packs/`, is visibly synthetic, binds
      `fixture_origin = true`, and cannot become emission-authoritative.
- [x] Loader rejects BOM/non-UTF-8, duplicate/unknown/missing keys, non-JSON
      constants, trailing data, malformed values, digest mismatch, pin
      mismatch, missing external digest, YAML, and all fallback behavior.
- [x] Concrete fixture weights are strictly positive and sum exactly to
      decimal one before binary64 conversion; invalid maps reject without
      normalization or defaults.
- [x] Complete pass, strict-threshold equality failure, above-threshold
      failure, Boolean gate, zero soft leg, and ordinary non-zero log-space
      paths in fixed `(physics, robustness, accuracy)` order match the numeric
      profile independently of JSON object member order.
- [x] Golden/boundary tests cover `quadratic_barrier`, both stable
      `tail_logistic` sign branches and extremes, `reciprocal_error`, every
      within-leg ordered `math.fsum`, and required-category completeness.
- [x] Every actual mandatory-gate failure sets both required result fields;
      all resolved gates remain in declared-order evidence without
      short-circuiting, no soft leg is evaluated, and a later zero soft leg
      remains distinguishable from a gate failure.
- [x] `HUMAN_INPUT` and `BLOCKED_FOR_LIVE_UNTIL_SET` readiness cases return
      `PACK_NOT_READY`, no combined score, and false eligibility without
      constructing a gate failure.
- [x] An unresolved exact `mandatory = false` diagnostic gate is unevaluated
      and omitted, contributes no expected `ScoreInput` key, and does not
      affect readiness, score, status, or eligibility.
- [x] Missing/malformed/incomplete and infra/reference inputs reject as
      non-scientific, never as score zero.
- [x] Forbidden/unknown inputs cannot construct `ScoreInput` and are rejected,
      including prior similarity, `estimate`/`light_*`, exam fee, mock-only
      metrics, and product-battery results.
- [x] Every fixture pass remains `eligible_for_emission = False`.
- [x] `InternalResult` field/exclusion and import-isolation tests preserve the
      private bounded contract and do not pull in A6/A7/A8/A9+ owners.
- [x] The implementation and tests use only existing/standard-library
      dependencies; no dependency is added.

## Bounded branch evidence

- Python 3.11.11 focused A5 command
  `python -m pytest tests/cpu/test_scoring_engine.py -q` passed
  `279 passed in 0.45s`; all 38 authorized categories are represented.
- The related A3/package/leakage command passed `195 passed in 4.07s`; the
  complete default CPU command passed `923 passed in 5.04s`.
- Compilation passed for `carbon/scoring` and the focused test. Ruff reported
  all eight changed Python files clean; Black reported all eight unchanged.
- The repository quality ratchet passed with `Ruff 757/776`, `Black 62/68`,
  removed debt `Ruff 19, Black 6`, eight changed Python files, and no new debt.
- The sole fixture is exactly 2,126 bytes at
  `tests/fixtures/score_packs/a5_fixture_v1.json`; its independently computed
  external digest is
  `sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57`.
- A built-wheel, outside-tree, isolated import loaded `carbon.scoring` from the
  installed wheel, scored the fixture to binary64 `0.8945915647907036`, loaded
  or attempted no prohibited optional/later-owner module, and remained
  false-eligible. No dependency or production/LIVE path was added.
- Independent review reported no remaining P0/P1/P2 implementation finding.
  These are bounded draft-branch results, not merged-main, scientific
  qualification, security/operations qualification, or production evidence.

## Must not

- Do not hardcode production thresholds, scientific categories, or weights as
  truth.
- Do not parse runtime YAML, add a YAML dependency, add a fallback/global pack,
  normalize weights, or accept a content-hash stub.
- Do not accept free-form metrics, raw predictions/references/draws, infra
  status, forbidden inputs, or miner-controlled score fields.
- Do not mark fixture data LIVE-qualified or emission-authoritative.
- Do not implement A6 cards/disclosure, A7 submission/FSM/fees, A8
  TrainEval/metric operators, receipts, logging, emissions, or later work.

## Focused test command

`python -m pytest tests/cpu/test_scoring_engine.py -q`
