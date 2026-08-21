# A5 scoring engine and fixture Score Pack implementation plan

**Ticket:** A5 — Scoring engine + fixture Score Pack
**Ratification branch:** `agent/a5-contract-ratification`
**Ratification starting main:** `3d80e09549964251833b0d8a70093cfceb51a501`
**Implementation branch:** not created
**Status:** pre-implementation contract ratified in documentation only; A5
remains `todo`

This is the bounded plan for a future A5 implementation. It does not implement
scoring, create a runtime Score Pack, add tests, add dependencies, satisfy a
Definition-of-Done item, or authorize A6 or later work.

## Pre-implementation repository gate and maturity

- An independent GitHub repository/branch read and a fresh local fetch both
  resolved current `main` to exact commit
  `3d80e09549964251833b0d8a70093cfceb51a501`, the reviewed A4 closeout merge.
- GitHub reported no open pull request and no remote branch matching A5 or
  scoring work before the ratification branch was created.
- `.agent/WAVE.md` records A5 as `todo`; A6 and every later ticket are also
  `todo`. This plan does not change that board.
- `carbon/scoring/` contains only the A0 package marker. There is no canonical
  A5 engine, pack loader/model, `ScoreInput`, `InternalResult`, fixture Score
  Pack JSON, default-CPU A5 test, or prior A5 plan.
- Historical scorers under `carbon/common/`, `poc/`, and `neurons/` and tests
  under `tests/legacy/` or `poc/tests/` use superseded or incomplete semantics.
  Their existence is archaeology, not canonical A5 implementation or test
  evidence.
- Therefore A5's contract is **SPECIFIED / RATIFIED** only. A5 is **NOT
  IMPLEMENTED**, **NOT TESTED**, and **NOT PRODUCTION-QUALIFIED**.
- Future implementation may start only after the ratification PR is
  independently reviewed, human-authorized, merged, and followed by a fresh
  main/concurrency/authority/status check.

## Authoritative source map

| Source | Authority and A5 use |
|---|---|
| Root `AGENTS.md` | Governs no invented science, pinned evaluation, infra/science separation, fixture non-emission, maturity claims, dependency discipline, and reviewable scope. |
| `.agent/DECISIONS.md` A5-R1–A5-R13 | Ratifies the exact artifact, pin, input, gate, failure, aggregate, numerical-profile, readiness, fixture, result, supersession, and ticket contracts. |
| `.agent/INVARIANTS.md` | Requires pinned official evaluation, forbidden-input exclusion, infra/science separation, no placeholder LIVE values, and private-by-default internal results. |
| `Design_Specs/Scoring.md` | Sole mathematical and Score Pack/A5 runtime authority. |
| `Design_Specs/Scoring_Formulas.md` | Subordinate historical detail; named obsolete rules are explicitly superseded and cannot be implementation authority. |
| `Design_Specs/Implementation.md` | Historical scoring appendix only. Its runtime artifact/input/gate/math/result examples are superseded for A5 and are not implementation evidence. |
| `Design_Specs/Strategy_Schema.md` | Proposed/unratified legacy scoring tuple only; it cannot define the A5 input or aggregate. |
| `Design_Specs/Build_Out.md` C5 | Sequencing/ownership only. Its YAML and broad InternalResult shorthand is narrowed by the scoring-domain owner. |
| `Design_Specs/Build_Out_Protocol_Extension.md` A5 | Requires a stable private score result suitable for later receipt commitment without moving receipts into A5. |
| `Design_Specs/Evaluation_Evidence_and_Validator_Audit.md` §6 | Owns the structural rule that infra/reference results cannot construct authoritative `ScoreInput`. |
| Current `carbon/registry/` | A3 code authority for exact `ChallengeKey`, version validation, tagged SHA-256 form, securely hashed actual bytes, and fixture-origin registry semantics. A5 reuses rather than weakens these contracts. |
| Current `carbon/seeding/` | A4 code authority for compatible challenge/generator/scoring pins and fixture labeling. A5 accepts no seed, draw, evaluation-binding, or commitment material. |
| `docs/context/Implemented_vs_Specified` | Maturity ledger; must distinguish the ratified canonical A5 target from legacy scoring code. |

`Scoring.md` governs scoring semantics. Historical YAML examples, PoC pack
files, legacy tests, Build Out shorthand, and archived documents do not
override it.

## KEEP / WRAP / REPAIR / REPLACE findings

| Area | Future A5 disposition |
|---|---|
| `carbon/scoring/__init__.py` | **KEEP / REPAIR narrowly.** Retain the canonical package boundary and later add only the explicit A5 public surface. |
| A3 `ChallengeKey` and validators | **KEEP / WRAP directly.** Reuse exact challenge identity, version grammar, and tagged-digest validation; do not duplicate weaker parsers. |
| A3 actual-byte digest behavior | **KEEP / WRAP.** Score Pack digest identity is exact regular-file bytes, but A5 additionally requires the digest to be supplied externally and checked before parsing. |
| A4 generator/scoring pin compatibility | **KEEP.** Match the exact public pins while excluding all A4 secret/private exam material from `ScoreInput` and `InternalResult`. |
| `carbon/common/scoring.py` | **REPLACE as canonical semantics; leave untouched as legacy.** It has embedded defaults and arithmetic aggregation. |
| `poc/eval/score.py` and `poc/configs/scoring_burgers1d.yaml` | **Do not promote.** They are historical PoC behavior/authoring data with unqualified values and non-current scoring semantics. |
| `neurons/scoring/` and legacy scorer/tracker tests | **Do not promote.** They are outside the canonical A5 package and do not prove the ratified contract. |
| Current Scoring soft-metric ideas | **WRAP only through scalars.** Preserve pack-authorized scalar transformations where specified; raw model/prediction/reference/percentile work belongs to A8 or later. |

No historical implementation file is deleted, rewritten, or declared
compliant by this ratification.

## Runtime artifact and digest flow

The future loader flow is fixed:

```text
trusted relative path + required external scoring digest
  → securely read exact regular-file bytes
  → SHA-256 exact bytes
  → exact tagged-digest comparison
  → strict UTF-8 decode (no BOM)
  → strict duplicate-detecting JSON parse
  → closed schema/type/value/readiness validation
  → complete exact pin cross-check
  → fixture-only loaded Score Pack
```

The digest comparison occurs before decoding or parsing. The expected digest
is not a field in the JSON, and no source-byte mutation, JSON
canonicalization, reserialization, or YAML conversion occurs inside the
runtime loader. The runtime accepts no YAML, internal/self-reported hash,
content-hash stub, fallback path, global pack, or default digest.

Strict JSON rejects at least:

- UTF-8 BOM and invalid UTF-8;
- duplicate keys at any object depth;
- `NaN`, `Infinity`, `-Infinity`, and other non-JSON constants;
- trailing documents/data and a non-object top level;
- missing, unknown, aliased, or type-invalid members;
- `null` where a required value or explicit unresolved state is expected.

YAML may remain in prose or a pre-publication human workflow, but the reviewed
JSON output bytes and external digest are the only A5 runtime artifact and
identity.

## Complete pack pin

The future immutable pin has exactly these semantic bindings:

| Binding | Contract |
|---|---|
| Challenge | Exact A3 `ChallengeKey`: `challenge_id` plus exact challenge `version`. |
| Scoring | Exact `scoring_version` plus the required external A5 Score Pack digest. |
| Generator | Exact `generator_version_required` plus exact tagged `generator_digest_required`. No allow-list or implicit active version. |
| Schema | Exact Score Pack `schema_version`. |
| Numeric profile | Exact identifier `python_binary64_v1`. |
| Origin | Exact Boolean `fixture_origin`; A5 accepts only `true`. |

All values are required and non-defaultable. Generator/scoring version tokens
reuse A3 `validate_version`. Tagged digests reuse A3's only supported form,
`sha256:<64 lowercase hexadecimal characters>`. The scoring digest comes from
the external expectation and cannot be self-bound inside its own hashed bytes.
Hard-gate definitions require no separate `gate_version` because the exact
Score Pack bytes already bind them.

The loader constructs the complete pin from source-contained fields plus the
externally verified scoring digest. That constructed pin and the
registry/loader expectation must match exactly before readiness is assessed.
An unresolved required value may therefore return `PACK_NOT_READY` without
constructing input. Once the pack is ready, the input pin must match it exactly
before scientific-gate evaluation. No normalization, case-folding, alias,
latest-version lookup, or fallback is permitted.

## Closed schema and scalar operators

`Design_Specs/Scoring.md` §§2.4 and 6 fix the complete logical schema and
operation order. The future JSON contains exactly the pin fields,
`hard_gates`, `physics`, `robustness`, `accuracy`, exact top-level `weights`,
and `combination = "weighted_geometric_logspace"`.

The only A5 operators are:

| Context | Exact identifier and behavior |
|---|---|
| Threshold hard gate | `less_than`; complete binary64 actual passes iff strict `actual < threshold`. |
| Boolean hard gate | `boolean_true`; exact Boolean actual passes only on `True`. |
| Physics | `quadratic_barrier`; scalar ratio/multiply/subtract sequence and `math.fsum` component aggregation from `Scoring.md` §6.1. |
| Robustness | `tail_logistic`; A8 supplies finite non-negative scalar mean/tail summaries at the pack-bound quantile, while A5 applies the exact `math.fsum` blend, ordered `z`, stable two-branch `math.exp` logistic, and `math.fsum` category aggregation in §6.2. |
| Accuracy | `reciprocal_error`; A8 supplies finite non-negative scalar errors, while A5 applies the exact add/divide sequence and `math.fsum` component aggregation in §6.3. |
| Within-leg aggregate | `weighted_sum`, implemented only by the fixed formulas above. |
| Top level | `weighted_geometric_logspace`, implemented only by `python_binary64_v1`. |

The top-level leg set is exactly `physics`, `robustness`, and `accuracy` for
this schema version. No dynamic callable/import/plugin, unknown operator, or
additional leg is accepted. At least one hard gate is mandatory. Identifier
and input-key sets are unique and closed.

Every human-owned score-bearing numeric slot—mandatory hard-gate and leg
thresholds, top-level/within-leg/blend/category/component weights, tail
quantile, and sharpness—accepts at schema parse either a JSON number or one
explicit unresolved-state string. A `mandatory = false` gate is strictly
diagnostic/non-score-bearing.
Validation order is structure/types, then every concrete number's individual
token/finite/sign/range rules, then the mandatory-or-score-bearing sentinel
readiness scan, then cross-value unit-sum/formula checks for a score-ready
pack. A valid mandatory or score-bearing sentinel produces `PACK_NOT_READY`;
an invalid concrete sibling, omission, `null`, unknown state, or malformed
type rejects and is not masked as merely unready. An unresolved optional
diagnostic is unevaluated and omitted from results; it cannot affect status,
score, or eligibility.

## Closed `ScoreInput` boundary

The future `ScoreInput` is an immutable validator-owned value object, not a
generic mapping. Its semantic content is limited to:

- the complete exact pack pin;
- the complete closed set of scalar actuals for mandatory threshold gates and
  resolved optional diagnostic threshold gates;
- the complete closed set of exact Boolean predicate-gate actuals where the
  schema authorizes such a gate; and
- the complete closed set of bounded scalar score-bearing component inputs
  required by the pack's authorized scalar formulas.

An unresolved optional diagnostic contributes no expected input key and any
presented actual for it is extra input. Keys otherwise match the loaded pack
exactly. Unknown, duplicate, extra, missing, aliased, or dynamically dispatched
formula/operator keys reject. No dynamic callable, plugin import, miner-defined
operator, or open metrics bag is accepted.

The following cannot be represented in or converted by A5 into `ScoreInput`:

- predictions, references, datasets, arrays/tensors, raw draws, raw
  percentile samples, models, or training output;
- infrastructure/reference failure or partial/incomplete execution state;
- raw/derived seeds, seed roles, draw/sample/exam IDs, evaluation binding, or
  exam commitment;
- prior similarity, `estimate`, any `light_*`, exam fee/payment, mock-only
  metrics, product-battery values, or miner-supplied evaluation metrics;
- strategy, submission, miner, validator, receipt, block, or public-card
  identity.

A8 or later validator-owned metric operators own predictions, references,
relative-error generation, raw percentile computation, and conversion of a
valid scientific execution into these authorized scalars. A5 fixture tests may
use a separately obvious fixture-only constructor without creating an infra or
production path.

## Gate, readiness, and failure taxonomy

Mandatory gates are evaluated only after the pack is valid and ready and the
input is authoritative, complete, and pin-matched.

| Condition | Scientific gate failure | `combined_score` | `eligible_for_emission` | A5 disposition |
|---|---:|---:|---:|---|
| Resolved fixture pack + complete input + all mandatory gates pass | No | Computed score | `False` | Private `SCORED` fixture result. |
| Same, but one top-level component is exactly zero | No | `0.0` | `False` | Private `SCORED` fixture result; zero leg is not a gate failure. |
| Complete input + an actual mandatory threshold/predicate failure | Yes | `0.0` | `False` | Private `MANDATORY_GATE_FAILED` result; both fields are required atomically. |
| Required mandatory/score-bearing pack value is `HUMAN_INPUT` or `BLOCKED_FOR_LIVE_UNTIL_SET` | No | Absent/`None` | `False` | Private `PACK_NOT_READY`; no gate is evaluated. |
| Missing/malformed pack, missing/mismatched digest/pin, or schema error | No | None; no scientific result | Non-emitting orchestration status | Typed load/config rejection; never a gate result. |
| Missing/malformed/incomplete `ScoreInput` or unknown/forbidden field | No | None; no scientific result | Non-emitting orchestration status | Typed input rejection; never a gate result. |
| Infra/reference failure or partial infra-derived metrics | No | None; no scientific result | Non-emitting infra status | Cannot construct `ScoreInput` or call the scientific engine. |

A threshold gate passes if and only if its validated binary64 actual is
strictly less than its validated threshold. Equality is an actual failure. A
Boolean predicate gate requires exact `True`. The mandatory set must be
non-vacuously complete before aggregation. A sigmoid cannot determine hard
PASS/FAIL; it may exist only as a soft transform or non-emission diagnostic.

## Explicit unresolved states

The only explicit states for an unresolved scientific value are the exact JSON
strings:

```text
HUMAN_INPUT
BLOCKED_FOR_LIVE_UNTIL_SET
```

They are neither numbers nor passes nor zeroes. Omission, `null`, malformed
text, and an unknown state are not aliases. Either state in a mandatory
threshold or other required score-bearing value makes an otherwise valid pack
`PACK_NOT_READY`. A `mandatory = false` diagnostic is non-score-bearing; while
unresolved it is unevaluated, contributes no expected `ScoreInput` key, and is
omitted from results. It cannot affect any mandatory gate, leg, aggregate,
status, score, or eligibility decision.

## Weight validation and top-level aggregation

The pack supplies the only top-level weight map. Its key set is exactly
`physics`, `robustness`, and `accuracy`. After readiness succeeds, every JSON
weight is strictly positive, and the original JSON numeric values must sum
exactly to decimal `1` before binary64 conversion. Missing, extra, zero,
negative, non-finite-after-conversion, or non-unit-sum resolved maps reject. An
explicit unresolved state follows the readiness taxonomy instead. Every
unit-sum within-leg, category, component, and mean/tail blend map follows the
same rule.

Every JSON numeric token is at most 128 ASCII characters and is retained as an
exact `decimal.Decimal` source value. Unit-sum validation is independent of
ambient decimal context: derive sign/coefficient/exponent with
`Decimal.as_tuple()`, reject locally invalid or binary64-zero/non-finite
values, scale coefficients to a common base-10 exponent with arbitrary-
precision integers, and compare their exact integer sum with scaled decimal
one. Do not use `decimal.Context` addition or a binary64 tolerance.

The implementation never:

- embeds 0.45/0.30/0.25 or any other default weight;
- normalizes or renormalizes weights;
- substitutes a missing leg/weight;
- clips or repairs a component to fit `[0, 1]`; or
- switches to arithmetic aggregation.

The 0.45/0.30/0.25 P0 values remain a permissible explicit pack baseline,
subject to the same exact validation. They are not engine constants and no A5
fixture value is production science.

## Exact `python_binary64_v1` profile

The future implementation must record and test the following exact behavior:

1. Use only exact built-in binary64 `float` plus the named standard-library
   operations `math.isfinite`, `math.fsum`, `math.log`, and `math.exp` for gate
   and score arithmetic. NumPy, JAX, Torch, alternate dtypes, and
   dependency-specific math are not part of this profile.
2. Retain JSON numeric tokens as exact `decimal.Decimal` values for the
   ambient-context-independent validation above, then explicitly convert
   required scientific values to binary64. Reject a conversion that is
   non-finite or destroys required strict positivity.
3. Runtime numeric `ScoreInput` slots require exact built-in `float`; Boolean,
   integer, string, subclass, coercion, NaN, and infinity reject where a
   number is expected. Boolean predicate slots separately require exact
   built-in `bool`.
4. Thresholds and sharpness are finite and strictly positive; tail quantile is
   strictly between zero and one. Numeric gate actuals and every
   physics/robustness/accuracy error summary are finite and non-negative.
   Transformed components and leg scores are finite and in `[0.0, 1.0]`.
5. Apply no implicit epsilon, clipping, coercion, rounding, normalization, or
   silent repair.
6. After mandatory gates pass, if any top-level component is exactly binary64
   zero, return exact `0.0` without taking its logarithm.
7. Otherwise, in the fixed top-level order `(physics, robustness, accuracy)`,
   materialize the three binary64 `weight × math.log(component)` terms, pass
   that single tuple to `math.fsum`, and apply `math.exp` exactly once to the
   result. JSON object source order has no arithmetic effect. Do not calculate
   a direct product of powers.
8. Do not round or clamp the result. A non-finite or out-of-range
   intermediate/output is a typed non-scientific scoring error, never an
   invented hard-gate failure or zero.

This fixes the Wave A arithmetic path but is not evidence of bitwise equality
across arbitrary Python/libm/platform cohorts. Backend/profile reproducibility
qualification remains human/later owned.

## Private `InternalResult`

The future private result has only the minimum stable scoring contract:

- status: `SCORED`, `MANDATORY_GATE_FAILED`, or `PACK_NOT_READY`;
- complete exact pack pin, including fixture origin;
- evaluated binary gate decisions and authorized scalar component scores when
  applicable;
- optional binary64 combined score; and
- exact `eligible_for_emission` Boolean.

`PACK_NOT_READY` has no evaluated gates and no combined score. An actual
mandatory failure has score `0.0` and false eligibility. Every A5 `SCORED`
result also has false eligibility because A5 is fixture-only.

The result does not contain pack weights or any seed/role/draw/exam material,
evaluation binding, strategy/submission/miner/validator identity, fee,
receipt/signature, public-card/disclosure policy, persistence, logging,
block/decay/tie-break value, or weight-writing behavior. It is not itself a
Model Card, EvaluationCard, EvaluationReceipt, log event, or emission weight.

## Fixture-only structural boundary

A5 loads only packs whose exact pin contains `fixture_origin = true`. Missing,
false, coerced, or non-Boolean origin rejects. The origin survives in the pin
and result and cannot be defaulted or relabelled. It is structural marking,
not authenticated provenance.

Even a complete pass with a non-zero combined score is
`eligible_for_emission = False`. The future fixture file and every synthetic
threshold/value must be unmistakably non-LIVE and non-qualified. A
production-origin loader or emission-authoritative result is outside A5 and
requires later specification, implementation, scientific/security/operational
qualification, and human authorization.

## Cross-ticket ownership

| Owner | Boundary |
|---|---|
| A3 | Exact challenge identity, version grammar, external artifact binding/digest form, and registry fixture-origin record. A5 does not weaken or replace it. |
| A4 | Compatible generator/scoring pins and fixture marking. A5 does not accept or retain entropy, seeds, roles, draw IDs, evaluation binding, or exam commitment. |
| A5 | Strict fixture pack loading, closed scalar input validation, binary gates, scalar pack transforms, weighted-geometric aggregate, and private fixture result only. |
| A6 | Persistence, Model Card/EvaluationCard, disclosure allow-list/budget, and public projections. |
| A7 | Submission identity, strategy binding, fees, idempotency, FSM, retry/refund, and concrete evaluation binding. |
| A8 or later metric operators | TrainEval/backend status, predictions/references, relative-error generation, raw percentile computation, and construction of authoritative scalar `ScoreInput`. Stub remains non-emitting. |
| Later receipt/evidence owner | Receipt schema, commitment/signing, transcript/evidence persistence, and audit. |
| A10/A11/later economic owner | Leaderboard, logging/metrics, decay/tie-breaking, score-to-weight mapping, and Bittensor emission behavior. |

## Expected future files

The smallest anticipated A5 implementation surface is:

| Future path | Responsibility |
|---|---|
| `carbon/scoring/model.py` | Frozen pack pin, readiness/status, closed scalar input, gate result, and private result value types plus exact validation orchestration. |
| `carbon/scoring/pack.py` | Secure exact-byte read, mandatory external digest check, strict UTF-8 JSON parse, closed schema/readiness validation, and fixture-only load. |
| `carbon/scoring/engine.py` | Binary gates, authorized scalar transforms, and `python_binary64_v1` log-space aggregate. |
| `carbon/scoring/__init__.py` | Small explicit A5 public export surface only. |
| `tests/fixtures/score_packs/a5_fixture_v1.json` | Exact-byte, visibly synthetic, fixture-origin runtime artifact; no YAML runtime twin or embedded digest. |
| `tests/cpu/test_scoring_engine.py` | Focused contract, failure, numerical, exclusion, and import-isolation acceptance tests. |

Exact module names may be tightened during implementation review without
changing the ratified contract. No file in this table is created by the
ratification.

## Expected future CPU tests

At minimum, the focused test file must cover:

- exact known fixture bytes/digest and byte perturbations (whitespace, newline,
  order, and content);
- required external digest form/absence/mismatch and rejection of an internal
  hash or hash stub;
- BOM, invalid UTF-8, YAML, duplicate/unknown/missing keys, non-JSON constants,
  trailing data, null/type errors, and no fallback;
- every exact pin field and one-at-a-time pin mismatches;
- A3 version/digest validator reuse and exact `fixture_origin = true`;
- closed `ScoreInput` field-set/type/range/completeness behavior and explicit
  forbidden inputs;
- infra/reference/partial result rejection before gate construction;
- both explicit unresolved states and `PACK_NOT_READY` invariants;
- non-vacuous mandatory gate completeness, below/equal/above threshold,
  Boolean predicate behavior, resolved optional diagnostic isolation, and
  unresolved optional diagnostic omission without a readiness effect;
- the atomic `combined_score = 0.0` plus false-eligibility mandatory-failure
  invariant;
- `quadratic_barrier` branch/boundary/order goldens, both stable
  `tail_logistic` sign branches and extreme values, `reciprocal_error`
  add/divide order, every within-leg ordered `math.fsum`, and required-category
  completeness;
- zero soft-leg result distinguished from gate failure;
- positive exact-decimal unit-sum weights, including decimal representations
  whose binary64 sum is not exactly one; zero/negative/missing/extra/non-unit
  maps reject without normalization;
- ordinary, all-one, zero-component, extreme-positive, and invalid numeric
  log-space paths in fixed `(physics, robustness, accuracy)` order against
  reviewed golden results, including permuted JSON object member order;
- every A5 pass remains false-eligible because of fixture origin;
- `InternalResult` allowed/excluded fields and absence of weights/secrets/
  downstream identity;
- import isolation: scoring import must not import YAML, NumPy/JAX/Torch,
  TrainEval, cards, fees/FSM, MCP, Bittensor/chain, logging, or receipts.

Future focused command:

```text
python -m pytest tests/cpu/test_scoring_engine.py -q
```

The later implementation must also run the repository's complete default CPU
suite and exact no-new-debt checks required by CI. Passing documentation checks
or historical tests is not A5 `TESTED` evidence.

## Dependency and import boundary

A5 adds no dependency. The expected implementation can use Python
standard-library facilities for dataclasses/enums, JSON, decimal validation,
SHA-256/digest comparison, finite/log/accurate-sum/exp arithmetic, and paths.
It must not import a YAML parser, NumPy, JAX, Torch, model/backend/scientific
execution, cards, fees/FSM, MCP, leaderboard, logging, chain/Bittensor, or
receipt/evidence modules.

The dependency direction remains narrow: A5 may reuse dependency-free A3
identity validators; it must not make registry or seeding import scoring, and
must not create a cycle with A6/A7/A8 or later packages.

## Bounded future implementation sequence

After a reviewed ratification merge and fresh start gate only:

1. Re-verify exact `main`, A5 `todo`, dependencies, and absence of competing
   A5 work; record exact base before creating a new implementation branch.
2. Run and record the supported default-CPU baseline without changing it.
3. Add only private models/validators needed for the exact pin, closed scalar
   input, statuses, gates, and result exclusions.
4. Add exact-byte/digest-first strict JSON fixture loader with no fallback.
5. Add the one structurally fixture-origin runtime JSON artifact and record its
   externally computed tagged digest in test/registry expectation, not inside
   the artifact.
6. Add binary gates, the closed exact scalar transforms/within-leg sums, and
   exact `python_binary64_v1` log-space aggregation.
7. Add the focused tests above, then run the focused/default CPU, import,
   formatting, lint, and no-new-debt gates.
8. Open a separate implementation PR for independent review. Do not mark A5
   `done` until exact-head review, acceptance evidence, authorized merge, and
   post-merge verification are complete.

This sequence is future guidance, not present implementation activity.

## Completion evidence required before A5 can be `done`

A later implementation closeout must identify:

- exact main base, implementation head, reviewed head, merge topology, and
  post-merge ancestry;
- exact fixture JSON bytes and externally expected tagged digest;
- focused/default CPU command results and exact-head CI;
- import/dependency isolation proof and clean changed-file quality gates;
- explicit evidence for every ticket checkbox and result-taxonomy row;
- confirmation that no A6/later behavior or production-origin/emission path was
  added; and
- an updated maturity ledger distinguishing bounded implementation/testing
  from scientific/security/operations/production qualification.

Until then, A5 must remain `todo`, **NOT IMPLEMENTED**, **NOT TESTED**, and
**NOT PRODUCTION-QUALIFIED**.

## Explicit non-goals of this ratification and A5

- No Python or dependency change in the ratification.
- No production Score Pack, production threshold, scientific category/weight,
  qualified generator/backend, LIVE activation, or emission authority.
- No raw metric generation, predictions/references, percentile operator,
  training/backend execution, or infra-to-science conversion.
- No seed/draw/evaluation identity, Strategy/submission/FSM/fee work, card or
  public disclosure, receipt/signature/evidence persistence, logging, decay,
  tie-breaking, score-to-weight mapping, Bittensor write, or A6+ work.
- No claim that a historical PoC/legacy scorer or test satisfies A5.
- No merge without human authorization.
