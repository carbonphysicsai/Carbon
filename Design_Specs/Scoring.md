# Scoring.md — Lean Emission Scoring & Challenge Score Bank

> **Sole scoring authority.** This document owns Score Pack runtime semantics,
> hard-gate decisions, scalar soft scoring, forbidden inputs, and top-level
> aggregation. `Scoring_Formulas.md` is subordinate.
>
> **Wave A A5 ratification:** strict UTF-8 JSON runtime packs; exact source
> bytes plus a required external tagged SHA-256; a complete exact pin; closed
> validator-authorized scalar `ScoreInput`; binary strict-`<` mandatory gates;
> dependency-free `python_binary64_v1`; log-space weighted geometric
> aggregation; explicit unresolved states; and fixture-only non-emission
> origin.
>
> **Maturity:** the contract is **SPECIFIED / RATIFIED ONLY**. A5 remains
> `todo`. It is **NOT IMPLEMENTED**, **NOT TESTED**, and **NOT
> PRODUCTION-QUALIFIED**.

**Carbon Subnet**
**Version:** 2.1 (August 2026)
**Status:** Protocol Appendix — Security & Incentive Critical
**Audience:** Simulation Engineers, Physics PhDs, Protocol Engineers, Auditors
**Related:** root `SPEC.md`; `Build_Out.md`; `Data_Management.md`;
`Evaluation_Evidence_and_Validator_Audit.md`; `Generator_Validation.md`;
`Evidence_and_Envelope_Standards.md`; `Launch_Bar.md`

---

## 0. Authority, scope, and ratification boundary

This document defines how already-authorized scalar scientific evidence is
converted into a private score result. It does not make scientific thresholds
or weights true, qualify a generator/backend, disclose hidden evidence, write
cards/receipts/logs, or write economic weights.

The A5 boundary is deliberately narrow:

| Owner | Responsibility |
|---|---|
| A3 registry | Exact challenge identity, version grammar, external artifact bindings/digests, and structural fixture-origin record. |
| A4 seeding | Compatible challenge/generator/scoring pins and fixture marking; no seed or draw value enters A5. |
| A5 scoring | Strict fixture pack load, closed scalar input, binary gates, pack-authorized scalar transforms, weighted-geometric aggregate, private fixture result. |
| A6 | Result persistence, Model Card/EvaluationCard, disclosure allow-list and budget. |
| A7 | Submission/strategy identity, fees, idempotency, FSM, retry/refund, and concrete evaluation binding. |
| A8 or later metric operators | Model execution, predictions, references, relative-error generation, raw percentile computation, and authoritative `ScoreInput` construction. |
| Later evidence/operations/economic owners | Receipts/signatures, transcripts, audit, logging, tie-breaking/decay, score-to-weight mapping, Bittensor writes. |

Any example elsewhere that gives `ScoreEngine` predictions, references,
arrays, raw percentiles, infrastructure status, or miner-supplied metrics is
superseded for A5. Any example that treats YAML as the runtime artifact, fp32
or JAX as the Wave A scoring profile, a sigmoid as an official hard gate,
arithmetic addition as the top-level aggregate, or missing/incomplete evidence
as a scientific zero is also superseded.

The P0 0.45/0.30/0.25 physics/robustness/accuracy values remain a permissible
explicit Score Pack baseline. They are not scientific universals, engine
constants, defaults, or fallback values. A dossier and human owners govern any
production threshold, category, transform parameter, or weight.

---

## 1. Why a Score Bank rather than one global pack

Different PDE families have different conserved quantities, risks, and stress
taxonomies. A Burgers challenge may care about conservation and shock
behavior; incompressible flow may care about divergence and momentum; coupled
multiphysics may care about interface continuity. One global set of thresholds
or categories cannot safely represent all of them.

Each challenge version therefore binds a separately versioned Score Pack and
required Generator Pack. A change to a score-bearing threshold, weight,
category, transform, or required generator binding is a reviewed scoring
contract change. It is never a silent validator tweak.

Historical results retain the exact pack pin used at evaluation time. New
bytes or a new scoring version apply prospectively; historical scientific
scores are not silently reinterpreted.

---

## 2. Canonical Score Pack runtime artifact

### 2.1 Strict UTF-8 JSON only

The canonical runtime Score Pack is one exact byte sequence containing one
strict UTF-8 JSON object.

The A5 runtime loader rejects:

- a UTF-8 BOM or invalid UTF-8;
- YAML or any non-JSON serialization;
- duplicate object keys at any depth;
- `NaN`, `Infinity`, `-Infinity`, or any other non-JSON constant;
- trailing data or multiple documents;
- a non-object top level;
- a missing, unknown, aliased, or type-invalid member; and
- `null` where a required value or explicit unresolved state is required.

The schema is closed. A new field requires an intentional schema-version
change; implementations do not silently retain or ignore extensions.

YAML may be used only as a human authoring or documentation form before pack
publication. A separately reviewed process may convert it to JSON, but A5 does
not parse YAML and adds no YAML dependency. The reviewed JSON bytes—not the
YAML, parsed object, or reserialized representation—are the runtime artifact.

### 2.2 Exact bytes plus required external SHA-256

Pack identity is the exact source bytes plus a required external expected
digest in A3's only accepted form:

```text
sha256:<64 lowercase hexadecimal characters>
```

The loader hashes the untouched bytes and compares that value with the
external expectation before UTF-8 decoding or JSON parsing. Whitespace, line
endings, member order, and every other source byte affect the digest.

The scoring digest is not trusted from a field inside the hashed bytes. There
is no self-reported `content_hash`, content-hash stub, path-only identity,
semantic/canonical JSON hash, missing-digest fallback, default pack, global
pack, or fallback pack. A digest mismatch is configuration/integrity failure,
not a scientific hard-gate failure.

### 2.3 Complete exact pack pin

One immutable pin binds all of the following:

| Field | Exact contract |
|---|---|
| Challenge identity | A3 `ChallengeKey`: exact `challenge_id` and exact challenge `version`. |
| Scoring identity | Exact `scoring_version` and the required external scoring digest over the source bytes. |
| Generator identity | Exact `generator_version_required` and exact tagged `generator_digest_required`. |
| Schema | Exact Score Pack `schema_version`. |
| Numerical profile | Exact identifier `python_binary64_v1`. |
| Origin | Exact Boolean `fixture_origin`. A5 accepts only `true`. |

Every binding is required, exact-match, and non-defaultable. Generator and
scoring versions reuse A3's version validator. Generator/scoring digests reuse
A3's tagged SHA-256 contract. A5 does not add a separate `gate_version`:
hard-gate definitions and thresholds are already bound by the exact Score Pack
bytes.

The loader constructs the complete pack pin from the source-contained fields
and the externally verified scoring digest. That constructed pin and the
external loader/registry expectation must agree exactly before readiness is
assessed. An unresolved required pack value can therefore produce
`PACK_NOT_READY` without constructing `ScoreInput`. Once a pack is ready, its
pin and the `ScoreInput` pin must agree exactly before any scientific gate is
evaluated. No normalization, case-folding, alias, “latest,” allow-list
substitution, or implicit active version is permitted.

### 2.4 Required logical pack content

The closed runtime object has these exact logical top-level members. A future
implementation may choose a mechanically equivalent nested representation
only through a reviewed schema-version change; it may not omit, rename, or add
behavior at implementation time.

| Member | A5 contract |
|---|---|
| `schema_version` | Exact version token for this closed JSON schema. |
| `challenge_id`, `challenge_version` | Exact A3 challenge identity. |
| `scoring_version` | Exact scoring version. The external scoring digest is deliberately not a member. |
| `generator_version_required`, `generator_digest_required` | One exact required Generator Pack binding; no allow-list. |
| `numerical_profile` | Exact string `python_binary64_v1`. |
| `fixture_origin` | Exact Boolean `true`. |
| `hard_gates` | Non-empty ordered array of the closed gate records below, including at least one exact `mandatory = true` gate. |
| `physics` | Exact `quadratic_barrier` leg record below. |
| `robustness` | Exact `tail_logistic` leg record below. |
| `accuracy` | Exact `reciprocal_error` leg record below. |
| `weights` | Object with exactly `physics`, `robustness`, and `accuracy` weights. |
| `combination` | Exact string `weighted_geometric_logspace`. |

The closed A5 operator set is:

| Context | Exact operator identifier | Required scalar content |
|---|---|---|
| Threshold hard gate | `less_than` | `id`, `input_key`, exact `mandatory` Boolean, and `threshold` (positive number or an explicit unresolved state). Exact `mandatory = false` makes the record strictly diagnostic and non-score-bearing. |
| Boolean hard gate | `boolean_true` | `id`, `input_key`, and exact `mandatory` Boolean; a `threshold` member is forbidden. Exact `mandatory = false` makes the record strictly diagnostic and non-score-bearing. |
| Physics leg | `quadratic_barrier` | Non-empty ordered `components`; each has `id`, `input_key`, threshold/state, and `weight`/state. When resolved, thresholds and weights are positive and the component weight set sums exactly to decimal one. |
| Robustness leg | `tail_logistic` | `tail_quantile`/state; `blend_weights` with exactly `mean`/`tail` number-or-state values; threshold/state; `sharpness`/state; and non-empty ordered categories containing `id`, `mean_input_key`, `tail_input_key`, and `weight`/state. When resolved, all required values satisfy the range/positivity rules and each weight set sums exactly to decimal one. |
| Accuracy leg | `reciprocal_error` | Non-empty ordered `components`; each has `id`, `input_key`, threshold/state, and `weight`/state. When resolved, thresholds and weights are positive and the component weight set sums exactly to decimal one. |
| Within-leg aggregation | `weighted_sum` | Fixed by the three leg schemas; it is not a dynamic pack callable. |
| Top-level aggregation | `weighted_geometric_logspace` | Exact top-level weight map and `python_binary64_v1` behavior in §7. |

Identifiers and input keys use reviewed canonical identifier validation and
must be unique in their scope. Ordered arrays are the declared within-leg or
gate evaluation order. The top-level leg order is fixed independently of JSON
object member order as `(physics, robustness, accuracy)`. At schema parse,
every human-owned required score-bearing numeric slot
accepts either a JSON number or exactly one of the two §3 unresolved-state
strings. This includes mandatory hard-gate thresholds, all leg thresholds,
every top-level/within-leg/blend/category/component weight, `tail_quantile`,
and `sharpness`. A `mandatory = false` diagnostic-gate threshold is explicitly
not score-bearing.

Validation order is exact: first validate structure/types; next validate every
concrete numeric slot independently for token bound, finiteness after binary64
conversion, and its local sign/range rule; then, if any otherwise valid
mandatory or score-bearing slot is an explicit state, return
`PACK_NOT_READY`; finally, for a score-ready pack, validate cross-value
unit-sum and formula-readiness rules. A negative,
out-of-range, non-finite-after-conversion, missing, `null`, unknown, or
malformed sibling rejects even when another slot is unresolved; an invalid
pack is not masked as merely unready.

For a score-ready pack, every required unit-sum map is strictly positive and
exact-decimal-sum-to-one. `tail_quantile` is strictly between zero and one;
`sharpness`, every leg threshold, and every mandatory-gate threshold are
strictly positive. These and every weight/transform parameter are
score-bearing values for readiness purposes. A resolved optional diagnostic
threshold is also locally validated as strictly positive but remains
non-score-bearing.

No other hard-gate, transform, leg, combination, or parameter is authorized by
A5. A pack cannot name a dynamic Python callable, import path, plugin,
miner-defined operator, or unknown metric. A new operator or top-level leg
requires a reviewed schema/scoring version change; it is not an ignored
extension.

No runtime fixture JSON exists at ratification time. Documentation examples
and historical YAML files are not substitutes for the future exact-byte A5
fixture artifact and cannot count as implementation evidence.

---

## 3. Explicit unresolved scientific-value states

The only explicit unresolved scientific-value states are the exact JSON
strings:

```text
HUMAN_INPUT
BLOCKED_FOR_LIVE_UNTIL_SET
```

They are states, not numbers, passes, failures, zeroes, or defaults. Omission,
JSON `null`, malformed text, or an unknown string is not an alias for either
state.

If any mandatory-gate threshold or other required score-bearing pack value is
in either state, the otherwise valid pack is `PACK_NOT_READY`:

- no scientific gate is evaluated;
- `combined_score` is absent/`None`;
- `eligible_for_emission` is `False`; and
- the outcome is not a scientific gate failure.

An optional value may remain unresolved only when its gate record has exact
`mandatory = false`, which marks it strictly diagnostic and non-score-bearing.
That diagnostic is not evaluated, creates no `GateResult`, and is omitted from
the result while unresolved. Its `input_key` is not expected in `ScoreInput`.
It cannot affect a mandatory gate, component, aggregate, status, combined
score, or eligibility decision. A resolved optional diagnostic may be
evaluated and recorded but remains non-score-bearing and
non-emission-authoritative.

Fixture packs may use visibly synthetic concrete values to exercise structural
pass/fail paths, but those values remain non-LIVE and scientifically
unqualified. An explicit sentinel is never replaced by such a value at
runtime.

---

## 4. Closed validator-authorized scalar `ScoreInput`

A5 accepts only an immutable validator-authorized `ScoreInput`, not a generic
mapping named “metrics.” Its schema is closed and contains only:

- the complete exact pack pin;
- the complete set of scalar actuals for every mandatory threshold gate and
  every resolved optional diagnostic threshold gate;
- the complete set of exact Boolean actuals for schema-authorized predicate
  gates; and
- the complete set of authorized bounded scalar score-bearing inputs needed
  by the pack's declared scalar transforms.

An unresolved optional diagnostic threshold contributes no expected input key;
presenting an actual for that unevaluated diagnostic is extra input and
rejects. The expected key sets otherwise come from the validated pack and must
match exactly. Missing, duplicate, extra, unknown, aliased, or dynamically
interpreted keys reject. A5 does not trim, normalize, ignore, or retain them.

The following are not members of `ScoreInput`:

- models, predictions, references, datasets, arrays/tensors, raw stress draws,
  or raw percentile samples;
- infrastructure/reference status or partial/incomplete execution output;
- raw/derived seeds, seed roles, draw/sample/exam IDs, evaluation binding, or
  exam commitment;
- strategy, submission, miner, validator, receipt, block, or public-card
  identity;
- prior similarity, `estimate`, any `light_*`, exam fee/payment, mock-only
  metrics, product-battery results, or miner-supplied evaluation metrics.

Forbidden and unknown inputs are rejected rather than ignored. A closed type
should make them structurally unrepresentable; runtime validation remains
required at trust boundaries.

A8 or later validator-owned metric operators own predictions/references,
relative-error generation, raw percentile computation, and construction of an
authoritative scalar `ScoreInput`. Only valid scientific/strategy execution
may construct that value. Infra/reference/partial states cannot enter the
scientific engine.

---

## 5. Hard gates and failure taxonomy

### 5.1 Binary hard gates

Hard-gate decisions are binary. A resolved threshold gate passes if and only
if its validated binary64 actual is strictly less than its validated binary64
threshold:

```text
PASS ⇔ actual < threshold
```

Equality fails. A schema-authorized Boolean predicate gate passes only on
exact `True`. The complete mandatory gate set and every required actual must
be present and validated before evaluation; an absent/empty/incomplete set
cannot vacuously pass.

If any actual mandatory gate fails, the private result must atomically contain
both:

```text
combined_score = 0.0
eligible_for_emission = False
```

A sigmoid may be used for a soft-leg transformation or a non-emission
diagnostic, but it never determines official hard-gate PASS/FAIL. A zero soft
leg can also yield a zero combined score and therefore must remain
distinguishable from `MANDATORY_GATE_FAILED`.

### 5.2 Non-scientific failures are not zeroes

| Condition | Scientific gate failure | Combined score | Emission disposition |
|---|---:|---:|---|
| Ready fixture pack, complete input, all mandatory gates pass | No | Computed (possibly zero from a zero soft leg) | `False` because fixture origin |
| Ready pack, complete input, actual mandatory gate fails | Yes | `0.0` | `False`; both fields required |
| Required score-bearing value unresolved | No | Absent/`None`; `PACK_NOT_READY` | `False` |
| Pack missing/malformed, external digest/pin absent or mismatched | No | No scientific result | Typed non-emitting config/integrity error |
| `ScoreInput` missing/malformed/incomplete, unknown, or forbidden | No | No scientific result | Typed non-emitting input error |
| Infrastructure/reference failure or partial infra-derived metrics | No | No scientific result | Typed infra/retry/refund/quarantine path |

The last three rows create no failed `GateResult` and no scientific zero.
Infra failure neither proves scientific incompetence nor grants scientific
success or emissions.

---

## 6. Scalar soft scoring

A5 applies exactly the three schema-authorized scalar transforms below to
validated scalar inputs. It never generates the underlying predictions,
references, relative errors, category samples, or raw percentiles.

All thresholds and transform parameters are pack-bound. Required unresolved
values make the pack `PACK_NOT_READY`; missing/malformed values reject. No
formula below supplies a default. Every additive blend or within-leg weighted
sum uses `math.fsum` in the declared array/map order; ordinary binary64
multiplication, division, and subtraction plus `math.exp` follow
`python_binary64_v1` in the operation order stated below.

### 6.1 Physics fidelity — quadratic barrier

For an exact built-in binary64 `float` error `e` that is finite and
non-negative, and a resolved strictly positive finite binary64 pack threshold
`tau`, the scalar margin is:

```text
when e < tau:
    ratio = e / tau
    m(e, tau) = 1.0 - (ratio × ratio)
when e >= tau:
    m(e, tau) = 0.0
```

The comparison and branch occur first. Only on the `e < tau` branch does the
division occur once; the ratio is then multiplied by itself and that product
is subtracted from binary64 `1.0`. The `e >= tau` branch does not evaluate the
division. Algebraically equivalent reorderings are not the
`python_binary64_v1` operation sequence.

Within-leg component weights are pack-bound and, when expressed as a
unit-sum map, follow the same strictly-positive exact-decimal-sum-to-one
rule as top-level weights. For ordered component margins `m_j` and weights
`alpha_j`, the physics leg is:

```text
physics_terms = (alpha_1 × m_1, ..., alpha_n × m_n) in declared order
S_physics = math.fsum(physics_terms)
```

Its output must be validated in `[0.0, 1.0]` before top-level aggregation.

A scalar margin reaching zero is not by itself a mandatory gate failure. Gate
status is determined only by a separately declared mandatory gate.

### 6.2 Robustness — authorized scalar category summaries

A8 or later owns category membership, raw errors, mean calculation, and raw
percentile calculation at the exact pack-bound `tail_quantile`. A5 receives
only the closed scalar `mean_c` and already-computed scalar `tail_c` for every
required category. Each must be an exact built-in binary64 `float`, finite,
and non-negative.

Let the exact positive `blend_weights` be `b_mean` and `b_tail`, with exact
decimal sum one. For each ordered category `c`, A5 computes:

```text
r_c = math.fsum((b_mean × mean_c, b_tail × tail_c))
z_c = sharpness × (r_c - threshold) / threshold
```

For `z_c`, subtraction is evaluated first, then multiplication by
`sharpness`, then division by `threshold`.

The `tail_logistic` category score is the mathematically exact value
`1 / (1 + exp(z_c))`, evaluated with `math.exp` and without
positive-exponential overflow:

```text
q_c = math.exp(-z_c); t_c = q_c / (1.0 + q_c)   when z_c >= 0
q_c = math.exp(z_c);  t_c = 1.0 / (1.0 + q_c)   when z_c < 0
```

This branch is part of the numerical contract, not optional implementation
advice. For ordered category weights `gamma_c`:

```text
robustness_terms = (gamma_1 × t_1, ..., gamma_n × t_n) in declared order
S_robustness = math.fsum(robustness_terms)
```

Every required category must be present. Missing category evidence is
incomplete input and does not “gracefully” become a scientific zero or a
renormalized subset. Category weights, mean/tail blend, tail quantile,
threshold, and sharpness are pack-bound score-bearing values. No category or
parameter is embedded in the engine.

The robustness leg must be a validated scalar in `[0.0, 1.0]` before top-level
aggregation. A soft sigmoid used here is a component transform, not a hard
gate.

### 6.3 Accuracy/generalization — authorized scalar errors

A8 or later owns inference and relative-error generation. A5 receives one
exact built-in binary64 `float` error `e_k` for every ordered accuracy
component in the pack; each error is finite and non-negative. With that
component's resolved strictly positive finite binary64 threshold `tau_k`, the
exact `reciprocal_error` score is evaluated as:

```text
denominator_k = tau_k + e_k
a_k = tau_k / denominator_k
```

The addition occurs before the division. A non-finite denominator is handled
as the typed computation error required by §7.2; it is not replaced by zero.

For ordered positive unit-sum component weights `delta_k`:

```text
accuracy_terms = (delta_1 × a_1, ..., delta_n × a_n) in declared order
S_accuracy = math.fsum(accuracy_terms)
```

The component set and its weights represent any in-distribution versus
edge/rare-regime blend. The familiar 50/50 split is permissible explicit pack
data, not an engine default. Every component threshold and weight is
pack-bound and non-defaultable.

True outside-envelope probes, when present, are non-score-bearing diagnostics
unless a separately qualified challenge version explicitly places them inside
its declared score-bearing envelope. The accuracy leg must be a validated
scalar in `[0.0, 1.0]` before top-level aggregation.

### 6.4 No double application of top-level weights

Within-leg weights produce a unit-interval leg score. Top-level physics,
robustness, and accuracy weights appear only in the weighted-geometric
aggregate. They are not multiplied into a leg and then applied again as an
exponent.

---

## 7. Pack-bound weights and weighted-geometric top level

The only normative top-level aggregate is the weighted geometric mean. An
arithmetic weighted sum, unweighted raw product, or normalized/defaulted
variant is not allowed.

### 7.1 Exact weight validation

After §3 readiness succeeds, the fully resolved top-level pack weight map must
satisfy all of the following:

- its key set exactly equals the score-bearing top-level leg set;
- every source JSON value is a number and is strictly positive;
- the original JSON numeric values sum exactly to decimal `1` under exact
  decimal arithmetic before binary64 conversion;
- each converted binary64 value remains finite and strictly positive; and
- no value is missing, extra, aliased, normalized, or defaulted.

The same rule applies to every unit-sum within-leg, category, component, and
mean/tail blend weight map. An explicit unresolved state follows §3 instead of
this resolved-map check.

Every JSON numeric token in this schema is at most 128 ASCII characters. It is
parsed directly from its source lexeme with `decimal.Decimal`; no intermediate
binary64 value is used for decimal validation. Exact unit-sum comparison is
independent of the ambient decimal context:

1. obtain each finite positive value's sign, integer coefficient, and base-10
   exponent from `Decimal.as_tuple()`;
2. reject a value greater than decimal one or whose later binary64 conversion
   is zero/non-finite before constructing a common scale;
3. choose the minimum exponent across the map and decimal one;
4. scale each coefficient to that common power of ten using Python arbitrary-
   precision integers; and
5. require the exact integer coefficient sum to equal the correspondingly
   scaled integer coefficient of decimal one.

No `decimal.Context` addition or comparison tolerance participates in the
unit-sum decision. Decimal validation also deliberately does not require the
converted binary64 weights themselves to sum to binary64 `1.0`.

The engine never rescales a non-unit map and never substitutes the P0 baseline
or another global value.

### 7.2 Exact `python_binary64_v1` numerical profile

The Wave A profile identifier is exactly `python_binary64_v1`.

1. Gate and score arithmetic uses exact built-in binary64 `float` values plus
   the named standard-library operations `math.isfinite`, `math.fsum`,
   `math.log`, and `math.exp`. NumPy, JAX, Torch, alternate dtypes, and
   dependency-specific math are outside this profile.
2. Source JSON numeric tokens are retained as exact `decimal.Decimal` values
   for schema, range, positivity, and the ambient-context-independent integer
   unit-sum procedure in §7.1 before explicit conversion to binary64. A
   non-finite conversion or loss of required strict positivity rejects.
3. Numeric `ScoreInput` slots require exact built-in `float`. Boolean,
   integer, string, subclassed, coerced, NaN, and infinite values reject where
   a number is required. Predicate slots separately require exact built-in
   `bool`.
4. Thresholds and sharpness are finite and strictly positive. Tail quantile is
   finite and strictly between zero and one. Numeric gate actuals and all
   physics/robustness/accuracy error summaries are finite and non-negative.
   Transformed components and leg scores are finite and within the closed
   interval `[0.0, 1.0]`.
5. No implicit epsilon floor, clipping, coercion, normalization, rounding, or
   silent range repair is permitted.
6. If all mandatory gates pass and any top-level component compares equal to
   binary64 zero (including signed zero), the engine takes the zero branch and
   returns canonical positive `0.0` without evaluating that component's log.
7. Otherwise, in the fixed top-level order `(physics, robustness, accuracy)`,
   compute each binary64 term as `weight × math.log(component)`, combine that
   three-term materialized tuple with `math.fsum`, and apply `math.exp` exactly
   once to that sum. JSON object source order has no arithmetic effect.
8. Do not round or clamp the result. A non-finite or out-of-range
   intermediate/output is a typed non-scientific scoring error, not a gate
   failure or invented zero.

Mathematically, for resolved positive component scores `S_i` and pack weights
`w_i`:

```text
log_terms = (
    w_physics × math.log(S_physics),
    w_robustness × math.log(S_robustness),
    w_accuracy × math.log(S_accuracy),
)
S_combined = math.exp(math.fsum(log_terms))
```

This execution contract does not itself prove bitwise equality across
arbitrary Python/libm/platform cohorts. Exact runtime/backend reproducibility
remains a later qualification claim bound to the required backend profile.

---

## 8. Private `InternalResult`

A5 returns a private stable result suitable for later controlled persistence
or receipt commitment. It is not a public card, receipt, log record, or
economic weight.

The bounded result contains only:

- status: `SCORED`, `MANDATORY_GATE_FAILED`, or `PACK_NOT_READY`;
- the complete exact Score Pack pin, including `fixture_origin`;
- evaluated gate decisions and authorized scalar component/leg scores when
  applicable;
- optional binary64 `combined_score`; and
- exact Boolean `eligible_for_emission`.

`PACK_NOT_READY` contains no evaluated scientific gates and no combined score.
An actual mandatory failure contains `combined_score = 0.0` and false
eligibility. An A5 `SCORED` result may contain a positive or zero combined
score but remains false-eligible because A5 is fixture-only.

`InternalResult` does not contain or own:

- Score Pack weights;
- raw or derived seeds, seed roles, draw/sample/exam IDs, evaluation binding,
  or exam commitment;
- strategy, submission, miner, validator, or receipt identity;
- fees/payments;
- public-card fields, disclosure policy/budget, or persistence behavior;
- receipt/signature/commitment behavior;
- logging/metrics behavior;
- block height, recency decay, tie-breaking, or weight-writing behavior; or
- predictions, references, raw errors/draws/percentiles, models, or training
  diagnostics.

A6 and later owners may consume only explicitly authorized result fields and
must preserve private-by-default disclosure.

---

## 9. Fixture-only A5 origin and emission authority

A5 accepts and implements only exact `fixture_origin = true`. Missing, false,
coerced, or non-Boolean origin rejects. The origin is part of the exact pin and
result, cannot be defaulted, and cannot be relabelled by the engine.

`fixture_origin` is a structural label, not authenticated provenance. It is
nevertheless sufficient to make every A5 result structurally
non-emission-authoritative:

```text
eligible_for_emission = False
```

This remains true even when all mandatory gates pass and the combined score is
non-zero. When a mandatory gate actually fails, the additional zero-score
invariant also applies.

A production-origin loader/result, LIVE Score Pack, emission-authoritative
score, score-to-weight mapping, or network write is outside A5. It requires
separate later specification/implementation, exact qualification evidence,
security/operations review, and human authorization.

---

## 10. Forbidden score inputs

The following never enter a scientific component, top-level aggregate,
eligibility decision, or later emission weight:

- prior similarity or Landscape similarity;
- `estimate` or any `light_*` result;
- mock/free-loop metrics;
- exam fee or payment amount;
- product-battery/commercial qualification results;
- miner-supplied evaluation metrics; or
- infrastructure/reference failure or partial infra-derived values.

The closed `ScoreInput` excludes them structurally, and boundary validation
rejects them if presented. “Ignored” is not an acceptable policy: accepting
and retaining unknown/forbidden input would expand the attack surface and make
the score contract ambiguous.

Fee is never score. Free/mock signal is never the official exam. Product
qualification never feeds lean competition scoring.

---

## 11. Versioning and governance

| Change | Required action |
|---|---|
| Threshold, unit-sum weight, category, transform, score-bearing key, or gate change | Human/scientific review as applicable and a new scoring contract/version; never a runtime tweak. |
| Required generator version/digest change | New exact generator/scoring binding and reviewed pack bytes. |
| Schema or numerical profile change | Explicit schema/profile version change and compatibility review. |
| Any source-byte change | New external exact-byte digest; no identity preservation through reserialization. |
| Metric-operator bug | New metric/scoring binding for future evaluations; no silent historical rescore. |
| Fixture to production origin | Not relabeling. Separate later implementation and complete qualification. |

Scores are attributable only to their complete exact pin. Historical results
are immutable at evaluation time and remain interpreted under that pin.

No agent autonomously supplies a production threshold/weight, approves a
Score Pack, flips a challenge LIVE, marks a fixture qualified, or authorizes
emissions.

---

## 12. Future A5 implementation and acceptance layout

The ratified future implementation is expected to remain small and
dependency-free:

```text
carbon/scoring/
  __init__.py
  model.py       # exact pin/input/status/private-result value types
  pack.py        # exact-byte digest-first strict JSON fixture loader
  engine.py      # binary gates, scalar transforms, log-space aggregate

tests/fixtures/score_packs/
  a5_fixture_v1.json

tests/cpu/
  test_scoring_engine.py
```

The future focused command is:

```text
python -m pytest tests/cpu/test_scoring_engine.py -q
```

At ratification time none of these implementation/test/fixture files exists
except the A0 `carbon/scoring/__init__.py` marker. The layout is a plan, not
implementation or test evidence.

Acceptance must cover exact bytes/digest/pin, strict JSON, no YAML/fallback,
closed input/forbidden fields, infra separation, explicit unresolved states,
strict threshold equality, the atomic gate-failure pair, exact decimal
weights, exact `quadratic_barrier` boundaries, both stable `tail_logistic`
branches and extremes, `reciprocal_error`, within-leg ordered sums and
category completeness, fixed-order binary64/log-space golden behavior,
zero-leg distinction, fixture-always-non-emitting, private-result exclusions,
no dependencies, and import isolation from A6/later owners.

---

## 13. Relationship to other scoring material

| Source | Status at A5 ratification |
|---|---|
| `Design_Specs/Scoring.md` | Sole scoring mathematical/runtime authority. |
| `Design_Specs/Scoring_Formulas.md` | Subordinate. Its named obsolete rules are explicitly superseded. |
| `Design_Specs/Implementation.md` | Historical implementation appendix for scoring. Its prediction/reference-to-engine, YAML, fp32/JAX, 0.40/0.35/0.25, and sigmoid-hard-gate examples are superseded for A5 and are not implementation evidence. |
| `Design_Specs/Strategy_Schema.md` | Any proposed/unratified legacy scoring tuple is non-authoritative for A5. |
| `Design_Specs/Build_Out.md` | Sequencing authority only. “YAML schema” means authoring/schema work after this ratification; runtime is strict JSON. Its broad Model Card/InternalResult and EvaluationPin examples do not expand A5. |
| `poc/configs/scoring_burgers1d.yaml` | Historical PoC authoring/configuration; not the A5 runtime fixture and not qualified science. |
| `carbon/common/scoring.py`, `poc/eval/score.py`, `neurons/scoring/` | Legacy archaeology with non-current/defaulted/arithmetic behavior; not A5. |
| `tests/legacy/` and `poc/tests/` scoring tests | Historical evidence only; not default-CPU A5 acceptance. |

Specifically superseded and forbidden as A5 implementation targets:

- top-level weights 0.40/0.35/0.25 presented as authority;
- sigmoid-derived official hard-gate PASS/FAIL;
- arithmetic top-level aggregation;
- direct product-of-powers implementation instead of the fixed log-space
  profile;
- fp32/JAX runtime scoring in Wave A;
- YAML runtime loading;
- raw predictions/references/percentiles entering A5;
- missing/incomplete evidence “failing or zeroing” science;
- ignored miner/unknown metrics;
- fallback or content-hash-stub packs; and
- card/emission/receipt/logging/fee/seed identity inside `InternalResult`.

---

## 14. Engineering rationale

### Binary hard gates

Mandatory scientific constraints are pass/fail decisions. A differentiable
diagnostic can help research, but it cannot blur the emission-authoritative
decision boundary. Strict `<` also fixes the equality edge rather than leaving
it implementation-dependent.

### Quadratic physics margins

The scalar quadratic barrier rewards safety margin below a qualified
threshold while reaching zero at the threshold. It remains a soft component;
only a separately declared mandatory gate creates scientific gate-failure
status.

### Tail-focused robustness

Mean-only performance can hide catastrophic regimes. Raw percentile and
category construction require upstream scientific operators; A5 consumes
only their authorized scalar summaries so the scoring package does not become
a second evaluator.

### Weighted geometric aggregate

The weighted geometric mean preserves a series-system property: a weak or
zero leg cannot be compensated by a strong leg. Top-level weights occur once
in the log-space aggregate. Exact pack binding and no normalization prevent
validators from silently changing the exam.

### Fixture-only Wave A

The fixture path can prove artifact, type, failure, numerical, and isolation
contracts without pretending synthetic values are LIVE science. Structural
false eligibility prevents a successful fixture calculation from becoming an
emission claim.

---

## 15. A5 trustlessness checklist (not yet implementation evidence)

- [ ] Runtime artifact is strict UTF-8 JSON; YAML is authoring-only.
- [ ] Required external tagged digest matches exact source bytes before parse.
- [ ] Complete pin matches challenge, scoring, generator, schema, profile, and
      fixture origin exactly.
- [ ] No pack/hash/default/fallback path exists.
- [ ] Only a complete validator-authorized scalar `ScoreInput` reaches gates.
- [ ] Forbidden/unknown/infra input is rejected before scientific scoring.
- [ ] Unresolved required value produces `PACK_NOT_READY`, not a gate failure.
- [ ] Mandatory threshold comparison is strict `<`; equality fails.
- [ ] Actual mandatory failure sets both zero score and false eligibility.
- [ ] Weight maps are positive and exact-decimal-sum-to-one; no normalization.
- [ ] Closed scalar transforms and within-leg sums match their exact operation
      order, branches, boundaries, and completeness rules.
- [ ] Aggregation follows `python_binary64_v1` zero/log-space behavior.
- [ ] Every A5 result remains non-emission-authoritative because it is fixture
      origin.
- [ ] Private result excludes weights, hidden identity, and all later-owner
      behavior.
- [ ] Focused/default CPU and import-isolation acceptance tests pass.

Every box remains unchecked at ratification time. Documentation review does
not make A5 implemented, tested, or production-qualified.

---

*Lean scoring is a versioned, challenge-bound exam: binary gates decide,
pack-bound scalar margins rank, weighted-geometric aggregation combines, and
fixtures never emit. Validators execute exact reviewed bytes; they do not
improvise the exam.*
