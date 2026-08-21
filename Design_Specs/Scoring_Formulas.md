# Scoring Formulas & Score Pack Detail

> **Subordinate historical companion.** [`Scoring.md`](./Scoring.md) is the
> sole mathematical and A5 runtime-contract authority. Nothing in this file
> overrides it.
>
> **Explicit supersession:** the former 0.40/0.35/0.25 top-level weights,
> sigmoid-as-official-hard-gate text, arithmetic top-level aggregate,
> fp32/JAX runtime implication, YAML runtime framing, and missing-input
> fail-or-zero language are superseded by `Scoring.md` and must not be
> implemented.
>
> **Maturity:** A5 is contract-ratified but remains `todo`, **NOT
> IMPLEMENTED**, **NOT TESTED**, and **NOT PRODUCTION-QUALIFIED**.

---

## 1. Authority and purpose

This file preserves a concise reconciliation record for the formerly split
formula appendix. It is not an alternate Score Pack schema and is not an
implementation source.

For current behavior, use `Scoring.md` for:

- strict UTF-8 JSON runtime artifact rules;
- exact source bytes plus required external tagged SHA-256;
- the complete challenge/scoring/generator/schema/profile/origin pin;
- closed validator-authorized scalar `ScoreInput`;
- binary hard gates and non-scientific failure separation;
- pack readiness and explicit unresolved states;
- scalar soft transforms;
- exact pack-bound weights and log-space weighted-geometric aggregation;
- the `python_binary64_v1` profile;
- fixture-only non-emission authority; and
- private `InternalResult` fields/exclusions.

---

## 2. Named historical rules that are superseded

| Historical text/rule | Current authority in `Scoring.md` | Disposition |
|---|---|---|
| Top-level weights `physics: 0.40`, `robustness: 0.35`, `accuracy: 0.25` | Weights are explicit pack data, strictly positive, exact-decimal-sum-to-one, never normalized/defaulted. 0.45/0.30/0.25 is only a permissible explicit P0 pack baseline. | **Superseded. Do not implement 0.40/0.35/0.25 or any engine default.** |
| “Hard Gates — Steep Sigmoid (Differentiable Binary)” and sigmoid-derived PASS/FAIL | Mandatory gates are binary. A threshold passes iff validated `actual < threshold`; equality fails. Any sigmoid is soft/non-emission diagnostic only. | **Superseded. A sigmoid cannot determine official hard-gate status.** |
| `S_combined = w_p*S_physics + w_r*S_robustness + w_a*S_accuracy` | Top-level aggregation is weighted geometric only, under the exact `python_binary64_v1` zero/log/accurate-sum/exp path. | **Superseded. Arithmetic top-level aggregation is forbidden.** |
| fp32/JAX runtime scoring | Dependency-free Python built-in binary64 under exact profile `python_binary64_v1`. | **Superseded for A5.** |
| Runtime Score Pack YAML | Strict UTF-8 JSON exact source bytes are canonical. YAML is authoring/documentation only. | **Superseded for runtime.** |
| Missing category coverage “fails or zeros” a leg | Missing/malformed/incomplete evidence is non-scientific input failure. Required unresolved pack values produce `PACK_NOT_READY`, no combined score, and false eligibility. | **Superseded. Do not manufacture a scientific zero.** |
| Pure functions of `(pred, ref, config)` inside A5 | A8 or later metric operators own predictions, references, relative-error generation, and raw percentile computation; A5 accepts closed authorized scalars only. | **Moved out of A5.** |
| Card/hash/vector writes inside scoring | A5 returns a private narrow `InternalResult`; A6/later owns persistence, cards/disclosure, receipts, logging, and economic behavior. | **Moved out of A5.** |

This table is an explicit semantic supersession, not a compatibility option.
Implementations and tests must not choose between the historical and current
columns.

---

## 3. YAML authoring/documentation boundary

Historical YAML snippets may remain useful to discuss challenge-specific
scientific design before publication. They are not runtime packs and have no
runtime identity.

Any authoring workflow must separately produce reviewed strict JSON bytes and
the required external tagged SHA-256. A5 then loads only those JSON bytes. The
runtime adds no YAML parser, does not transform YAML, does not hash authoring
YAML, and does not treat a parsed/reserialized object as equivalent to the
published bytes.

Historical threshold/category examples are illustrative and scientifically
unqualified. They do not resolve `HUMAN_INPUT` or
`BLOCKED_FOR_LIVE_UNTIL_SET`, do not create a fixture artifact, and cannot be
used for LIVE scoring.

---

## 4. Current formula pointers

Current scalar formula behavior is intentionally stated only once:

- Binary threshold gates and their atomic zero/false failure result:
  `Scoring.md` §5.
- Physics quadratic scalar margin and scalar robustness/accuracy ownership:
  `Scoring.md` §6.
- Exact decimal weight validation, weighted-geometric-only top level, and
  dependency-free binary64 log-space path: `Scoring.md` §7.
- Private result and fixture-only emission boundary: `Scoring.md` §§8–9.

Restoring formula text from a historical commit is not permitted without
reconciling it against current `Scoring.md` and obtaining a new reviewed
decision. A historical pre-split appendix is not latent authority.

---

## 5. Input and ownership reminder

The A5 engine does not accept:

- raw predictions or references;
- model functions, datasets, arrays/tensors, raw draws, or raw percentiles;
- infrastructure/reference failure or partial metrics;
- miner metrics, prior similarity, `estimate`/`light_*`, exam fee, mock-only
  metrics, or product-battery results; or
- seeds/draw identity, submission identity, cards, receipts, logging, or
  economic weights.

Those values cannot be “ignored” inside an open metrics mapping. They are not
members of the closed `ScoreInput`, and trust-boundary presentation rejects.

---

## 6. Implementation status

The future A5 implementation/test locations are planned in
`.agent/plans/A5_scoring_engine.md` and summarized by `Scoring.md` §12. At this
ratification point:

- `carbon/scoring/` still contains only its A0 marker;
- no strict JSON fixture Score Pack exists;
- no `ScoreEngine`, `ScoreInput`, or `InternalResult` implementation exists;
- no `tests/cpu/test_scoring_engine.py` exists; and
- no scoring behavior is tested or production-qualified by this document.

The historical PoC/legacy code and tests remain non-authoritative archaeology.

---

*For all current scoring mathematics and runtime behavior, implement
`Scoring.md`, not the superseded rules catalogued here.*
