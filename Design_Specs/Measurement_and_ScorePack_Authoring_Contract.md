# Measurement and Score Pack Authoring Contract

**Ticket:** B-05 — MeasurementContract and Score Pack authoring bindings
**Version:** 0.1 working engineering contract
**Status:** SPECIFIED working candidate; not ratified, qualified, production-ready, or LIVE
**Starting authority:** `origin/main` commit
`f1a429de37290b3c7615ca051661a1d727528f78`, tree
`3e25bd65508c5c11d8d67558f9bd699808fc57a9`
**Runtime namespace:** `carbon.measurement`
**Upstream owners:** B-02A authoring, B-02C resource policy, B-04
reference/truth, and A5 scoring
**Downstream owners:** B-06 qualification, B-07F official fixture
composition, B-07A/C discovery and practice, B-E1 coverage/failure harness,
and B-GATE closeout

This contract defines how an exact scientific measurement is authored,
qualified by evidence role, and bound to the scalar interface of the existing
A5 Score Pack. It does not define real measurements, approve scientific
values, run a solver, qualify a Challenge, construct official evaluations,
rank miners, disclose protected evidence, or make an A5 result emission-
capable.

## 1. Governing principles

The following boundaries are normative.

1. Measurement definition, qualification evidence, case/stratum
   applicability, admissibility, score use, and disclosure use are different
   decisions and different typed records.
2. Mandatory scientific admissibility is decided before any soft score
   aggregation. A soft score cannot compensate for a missing or failed
   mandatory measurement.
3. A5 remains the deterministic fixture-only scalar executor. B-05 authors
   exact bindings to its closed input keys and `ScorePackPin`; it does not
   alter A5 operators, thresholds, weights, numerical profile, or
   `ScoreInput` construction authority.
4. B-02C facts constrain resource use but confer no scientific sufficiency.
   B-05 owns reconstruction-evidence stages and outcomes; B-E1 later tests
   their coverage and false-elimination behavior.
5. B-04 owns reference and TruthAsset authority. B-05 may consume exact B-04
   refs and typed outcomes but cannot promote an artifact or successful run to
   truth.
6. Implementation verification is not physical validation. In particular,
   MMS or refinement evidence cannot establish customer-workload
   applicability, engineering context of use, or physical-model validity.
7. Every real physical threshold, tolerance, floor, transform, stratum,
   weight, dependence assumption, evidence minimum, stopping rule, stability
   rate, and qualification outcome remains human-owned. An unresolved value is
   explicit `HUMAN_INPUT` or `BLOCKED_FOR_LIVE_UNTIL_SET`; omission and `null`
   are invalid.
8. Fixture values are allowed only in explicitly fixture-origin records and
   cannot become production or LIVE evidence through copying, hashing, or
   successful execution.

## 2. Ownership and dependency direction

The implementation is a new standard-library-only `carbon.measurement`
package. It consumes public nominal identities from existing packages in this
one-way direction:

```text
carbon.authoring  carbon.evaluation  carbon.resource_policy  carbon.scoring
        \                 |                  |                  /
                         carbon.measurement
```

The package may import exact value and reference types, canonical primitives,
and `ScorePackPin`. It must not import an A5 engine or construct `ScoreInput`,
run B-04 providers, mutate B-02C policy state, inspect protected payloads, or
depend on later-ticket packages. Upstream packages must not import
`carbon.measurement`.

Disposition of current code:

| Surface | Disposition | Reason |
|---|---|---|
| B-02A Challenge-bound refs and canonical primitives | KEEP + WRAP | Preserve existing identities without widening B-02A's closed schema. |
| B-04 truth/reference refs and typed outcomes | KEEP | Reference authority remains B-04-owned. |
| B-02C build, replicate, reuse, stop, and receipt facts | KEEP as facts | They may satisfy structural resource predicates but never scientific sufficiency. |
| A5 `ScorePackPin` and closed scalar schema 1.0 | KEEP | B-05 binds measurements to declared keys; A5 is unchanged. |
| Generic metric dictionaries, implicit defaults, covariance guesses, and raw product/resource fields | REPLACE / EXCLUDE | They erase scientific authority and fail-open distinctions. |
| Solver execution, Dossier qualification, official-plan composition, and coverage harness | DEFER | Owned by B-04/B-E2, B-06, B-07F, and B-E1. |

## 3. Identity and canonical profile

The B-05 schema version is exact string `"1.0"`. Its canonical profile is
exact string `carbon_measurement_canonical_v1` and its domain header is exact
bytes `carbon.measurement.canonical.v1\x00`.

Every top-level authoring object is immutable and Challenge-bound. Its nominal
reference contains:

```text
challenge_key
content_digest = sha256:<64 lowercase hexadecimal characters>
schema_version = "1.0"
canonicalization_profile = "carbon_measurement_canonical_v1"
record_type = closed class constant
```

Subordinate scientific definitions use one exact nominal
`MeasurementDefinitionRef` carrying the same Challenge, one closed
`MeasurementDefinitionKind`, canonical object ID/version, exact content
digest, schema, and profile. This B-05-owned ref wraps the meaning already
defined by reviewed authoring material without adding new kinds to B-02A's
closed owner-ref registry.

The digest is over domain header plus canonical object kind, schema version,
and the complete canonical payload. Exact type checks reject Boolean-as-
integer substitution, subclasses, unknown enum members, non-finite numbers,
unordered mappings, duplicate identities, unknown fields, cross-Challenge
refs, and non-canonical text. Set-like tuples sort by complete canonical bytes;
normative sequences preserve declared order. A top-level object's ref is
derived from its bytes and cannot be caller asserted.

V1 top-level object kinds are planned as:

```text
measurement_contract
measurement_qualification_evidence
uncertainty_policy
reconstruction_evidence_policy
score_pack_authoring_contract
```

The first implementation slice freezes and implements
`measurement_contract` and `measurement_qualification_evidence`. The
remaining kinds are contract-defined but intentionally absent until their own
coherent slices and tests land.

## 4. MeasurementContract

`MeasurementContract` defines one scientific quantity and its deterministic
measurement recipe. It contains no observed candidate value.

| Field | Contract |
|---|---|
| `challenge_key` | Exact A3 Challenge identity. |
| `measurement_id`, `measurement_version` | Canonical ID and reviewed version token; neither is an alias or “latest”. |
| `scientific_property_ref` | Challenge-scoped B-05 definition ref naming the claimed property. |
| `observable_refs` | Non-empty canonical set of Challenge-scoped B-05 observable definition refs. |
| `coordinate_system_ref`, `unit_ref` | Exact Challenge-scoped coordinate and unit definitions. |
| `numerical_operator_ref` | Exact executable-semantics description, not a callable or import path. |
| `discretization_ref`, `sampling_quadrature_ref` | Exact numerical interpretation and sampling/quadrature definition. |
| `normalization_ref`, `aggregation_ref` | Exact transformation and within-measurement aggregation definitions. |
| `precision_ref` | Exact precision/numerical-profile authority. |
| `reference_policy_ref` | Exact B-04 `ReferencePolicyRef`; no path-only or solver-reputation reference. |
| `numerical_floor_binding` | Exact resolved scientific-value ref or explicit unresolved state. Zero/epsilon is never implicit. |
| `applicability_policy_ref` | Challenge-scoped B-05 policy definition ref for case and context applicability. |
| `uncertainty_policy_ref` | Exact B-05 `UncertaintyPolicyRef` or explicit unresolved state. |
| `stratum_applicability` | Non-empty explicit bindings for applicable, not-applicable-with-reason, or human-input strata. |
| `known_limitation_refs` | Canonical set; an empty set is explicit, not omitted. |
| `implementation_refs` | Non-empty canonical set of immutable implementation/provenance refs. |
| `intended_role` | Exactly `MANDATORY`, `SOFT`, or `DIAGNOSTIC`. |
| `fixture_origin` | Exact Boolean. `true` can never support LIVE or scientific qualification. |

No field can be inferred from a unit name, Python type, case label, reference
method, Score Pack input key, or another measurement. A measurement version
changes whenever its scientific meaning, operator, floor, normalization,
aggregation, applicability, uncertainty, or intended role changes.

### 4.1 Scientific-value binding

`ScientificValueBinding` is a closed union:

```text
BOUND(ref: Challenge-scoped scientific-value authority ref)
HUMAN_INPUT
BLOCKED_FOR_LIVE_UNTIL_SET
NOT_APPLICABLE(reason_ref)
```

`BOUND` records identity, not a free scalar. The referenced value is approved
outside this ticket and must carry the same Challenge. `NOT_APPLICABLE` is
legal only for a field whose surrounding schema admits it. Unresolved states
are neither zero nor a failed scientific predicate.

### 4.2 Stratum applicability

Every score-eligible measurement binds the complete authored scoring-stratum
inventory. Each `StratumApplicabilityBinding` names one exact stratum ref and
one status: `APPLICABLE`, `NOT_APPLICABLE`, or `HUMAN_INPUT`. Applicable
bindings name exact evidence; not-applicable bindings name an exact reason;
human-input bindings name neither. Duplicate, missing, extra, cross-Challenge,
or contradictory strata reject. B-06 later decides whether the evidence is
qualified; B-05 does not self-approve it.

## 5. MeasurementQualificationEvidence

This record binds evidence to a measurement without granting more authority
than the evidence role permits.

Each evidence item contains exact evidence identity, source/provenance ref,
one `MeasurementEvidenceRole`, a non-empty set of supported claim classes, a
non-empty explicit set of unsupported claim classes, case/stratum scope, and
fixture-origin status. The closed roles are:

- `ANALYTIC_OR_MANUFACTURED_VERIFICATION`
- `REFINEMENT_OR_CONVERGENCE`
- `INDEPENDENT_WITNESS`
- `LIMITING_CASE_OR_INVARIANCE`
- `EXPERIMENTAL_OR_INDUSTRIAL_VALIDATION`

The closed claim classes are:

- `IMPLEMENTATION_CORRECTNESS`
- `DISCRETIZATION_CONVERGENCE`
- `REFERENCE_AGREEMENT`
- `LIMITING_CASE_BEHAVIOR`
- `PHYSICAL_MODEL_VALIDITY`
- `TARGET_WORKLOAD_APPLICABILITY`
- `ENGINEERING_CONTEXT_OF_USE`
- `MEASUREMENT_UNCERTAINTY_ADEQUACY`

The following matrix is enforced structurally. A check mark means the role may
support the class; it does not mean the source is sufficient or qualified.

| Evidence role | Implementation | Convergence | Reference | Limiting case | Physical validity | Workload applicability | Context of use | Uncertainty adequacy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| analytic/manufactured verification | ✓ | — | ✓ | ✓ | — | — | — | — |
| refinement/convergence | ✓ | ✓ | — | ✓ | — | — | — | ✓ |
| independent witness | ✓ | ✓ | ✓ | ✓ | — | — | — | ✓ |
| limiting-case/invariance | ✓ | — | — | ✓ | — | — | — | — |
| experimental/industrial validation | — | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Every item must explicitly list all claim classes outside its supported set as
unsupported. An MMS, analytic solution, self-cross-check, manufactured case,
or refinement study attempting to support physical validity, target-workload
applicability, or engineering context of use rejects. Independent witness
means an exact B-04 witness identity and disclosed dependence; naming a second
solver is insufficient.

`MeasurementQualificationEvidence` is only an evidence inventory. B-06 owns
the positive qualification decision and its Dossier. Absence, an incomplete
role set, or fixture-only evidence therefore cannot silently yield a negative
scientific score; it yields an explicit unqualified or unresolved boundary.

## 6. UncertaintyPolicy

One immutable Challenge-bound `UncertaintyPolicy` binds all of:

- estimand identity and measurement-output identity;
- sampling, resampling, and independence units;
- common-case incumbent/challenger pairing;
- reconstruction-by-case and reconstruction-by-stratum interaction;
- joint reference uncertainty and reference/candidate covariance handling;
- representation and execution dependence;
- censoring, missingness, failure, and excluded-case accounting;
- minimum evidence and per-stratum minima;
- prospective stopping and scientific evidence-extension rules;
- interval/error-control method and multiplicity semantics; and
- Dossier applicability evidence required for any quadrature,
  independence, or zero-covariance shortcut.

Every listed policy component is an exact approved ref or explicit unresolved
state. A shortcut is a separate `DependenceShortcutBinding`; it binds the
exact incumbent evidence, exact challenger evidence, exact cases/strata,
assumption, applicability-test ref, and B-06 Dossier qualification ref. The
evidence being compared must exactly match the Dossier applicability scope.
Missing, broader, narrower, stale, or cross-version evidence yields
`UNCERTAINTY_UNRESOLVED`, never an assumed zero covariance.

B-05 performs no mechanical combination of uncertainty components unless an
exact approved policy explicitly defines the combination. It does not infer
independence from separate processes, separate seeds, separate solvers, or
different machines.

## 7. ReconstructionEvidencePolicy

`ReconstructionEvidencePolicy` owns scientific sufficiency for evidence from
producer-independent reconstruction. It binds:

- exact Challenge/family and reconstruction-policy identity;
- a complete-base minimum of one or more builds;
- build completeness criteria and permitted frozen-artifact reuse;
- nomination and promotion stages as distinct states;
- case and stratum coverage requirements;
- scientific extension and stopping rules;
- a stability-audit rate and audit selection policy;
- typed `EVIDENCE_DEFERRED` conditions;
- heuristic-futility advice as non-authoritative scheduling input; and
- fail-closed outcomes for incomplete, failed, contested, or insufficient
  evidence.

The v1 stage order is:

```text
BASE_REQUIRED -> BASE_COMPLETE -> NOMINATED -> EXTENDED -> PROMOTION_ELIGIBLE
```

`NOMINATED` is not promoted, score-eligible, or qualified. A heuristic may
recommend delaying or ceasing further resource expenditure, but it cannot
convert insufficient evidence to a scientific failure or pass. Scientific
stopping/extension is coverage-qualified under the exact authored policy.

`EXTENDED` is the single registered transition showing that the separately
realized, producer-independent reconstruction evidence required for a
promotion decision exists. It requires the exact extension-evidence ref and a
`BoundReconstructionReplicate`; a generic evidence ref or resource receipt
cannot establish it. It does not impose an arbitrary second extension or make
all later sequential repeats mandatory. Any repeats after that registered
transition occur only under the prospective scientific stopping/extension
rule. `PROMOTION_ELIGIBLE` additionally requires the exact promotion-evidence
ref and means downstream evidence readiness only; it creates no ranking win,
frontier event, entitlement, weight, settlement, production, or LIVE authority.

B-02C's `CompleteBuild`, `BoundReconstructionReplicate`, frozen-reuse window,
resource stop, and `ObservedResourceReceiptRef` are accepted only as exact
resource facts. Forecasts, budgets, receipts, timeouts, or resource ceilings
cannot satisfy complete-base minimums or coverage predicates on their own.
Where the resource policy stops before scientific sufficiency, the outcome is
`EVIDENCE_DEFERRED` with exact provenance and remaining requirement refs.

The exact minimum build count, strata, coverage thresholds, stopping/error
control, and stability-audit rate are human-reserved. This ticket supplies
typed unresolved states and fixture-only examples, not real values.

## 8. Score Pack authoring binding

`ScorePackAuthoringContract` binds one exact B-05 measurement policy set to one
exact A5 `ScorePackPin`. It is an authoring/projection contract, not another
score engine.

For every A5 input key it records:

- the exact measurement contract and qualified output identity;
- numeric or Boolean scalar kind;
- `MANDATORY_GATE`, `SOFT_COMPONENT`, or `DIAGNOSTIC` use;
- estimand and stratum refs;
- uncertainty-policy ref;
- admissibility-policy ref;
- aggregation and ranking role;
- disclosure class/ref; and
- the exact A5 gate/component/category identifier consuming the scalar.

The binding must cover exactly the ready pack's expected keys with no
duplicates or aliases. One measurement output may feed multiple declared A5
uses only when each use is explicit. Unknown, missing, extra, cross-Challenge,
fixture/live-mismatched, or role-confused bindings reject.

The only admissible source is a complete typed measurement result matching the
exact contract, case/stratum scope, reference identity, uncertainty policy,
qualification evidence, and pack authoring binding. These sources are
forbidden regardless of shape:

- candidate/miner self-reported metrics;
- mock, practice, prior, resource forecast, cost, product, commercial,
  reputation, fee, stake, rank, chain, frontier, weight, or emission fields;
- raw predictions, arrays, reference payloads, case secrets, seeds, or
  protected evidence; and
- a diagnostic result relabeled as mandatory or soft.

The future B-07F adapter may construct A5 `ScoreInput` only after all mandatory
bindings are admissible. B-05 will expose a closed scalar projection for that
adapter; it will not call `ScoreEngine`, grant eligibility for emission, or
write a score result.

## 9. Typed measurement material and fail-closed precedence

The planned closed material outcomes are:

```text
COMPLETE
PARTIAL
NON_FINITE
INAPPLICABLE
REFERENCE_FAILED
NUMERICAL_FLOOR_UNRESOLVED
UNCERTAINTY_UNRESOLVED
QUALIFICATION_UNRESOLVED
EVIDENCE_DEFERRED
```

Only `COMPLETE` can carry a scalar projection. A complete material record must
still pass exact identity, applicability, qualification, uncertainty, and
authoring-binding checks. All other states carry a typed reason/ref and no
score scalar. They cannot be coerced to zero, infinity, threshold failure, or
missing input.

Fail-closed evaluation order is:

```text
identity and origin
-> case/stratum applicability
-> reference status
-> measurement completeness and finiteness
-> numerical-floor resolution
-> uncertainty resolution
-> qualification/admissibility
-> mandatory scalar projection
-> optional soft/diagnostic projection
-> A5 deterministic execution (later B-07F owner)
```

A resource or infrastructure failure is not a scientific failure. A reference
failure is not a candidate score. An inapplicable measurement is not a pass or
failure. A missing soft component is not silently renormalized.

## 10. Fixture, qualification, and maturity limits

The first B-05 implementation may include only synthetic, visibly nonphysical
fixture identities. No fixture value may be advertised as a scientific
default. All fixture constructors and artifacts carry exact
`fixture_origin=true`; any production-shaped boundary rejects them.

B-06 owns qualification records and Dossier completeness. Until that ticket
supplies a positive exact qualification:

```text
SPECIFIED: WORKING ENGINEERING CANDIDATE
IMPLEMENTED: ONLY FOR LANDED B-05 SLICES
TESTED: ONLY FOR RECORDED FIXTURE/STRUCTURAL SCOPE
SCIENTIFICALLY_QUALIFIED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
LIVE: NO
```

Hash validity, canonical round-trip, test success, a lead notification, code
review, merge, or A5 execution cannot raise those ceilings.

## 11. Implementation slices and acceptance evidence

The planned vertical slices are:

1. exact enums, scientific-value/applicability bindings,
   `MeasurementContract`, evidence-role matrix,
   `MeasurementQualificationEvidence`, nominal refs, canonical bytes/hash,
   bounded store/load, root allow-list, and hostile-input tests;
2. `UncertaintyPolicy`, exact Dossier shortcut applicability binding, and
   unresolved/dependence tests;
3. `ReconstructionEvidencePolicy`, exact B-02C fact adapters, stage/outcome
   transitions, and deferred/futility/stability tests;
4. `ScorePackAuthoringContract`, A5-pack exact coverage validator, typed
   material/admissibility projection, and forbidden-input/role-confusion tests;
5. complete fixture composition, cross-package boundary tests, package/wheel
   tests, invariants, canonical CI, and independent complete-diff review.

Every slice updates this contract if implementation discovers an ambiguity.
Any semantic or byte-shape change requires a versioned decision and fresh
tests. Real scientific values or qualification outcomes are never a condition
for completing the bounded engineering ticket; affected behavior remains
explicitly unresolved and fail closed.

Slice 4 implements item 4 as an outward validation seam against A5's unchanged
`LoadedScorePack` schema. The content-addressed authoring record owns no
runtime formula and the projection result remains role-separated; it cannot
construct `ScoreInput` or invoke `ScoreEngine`. Threshold, transform, and
weight authority is an exact typed ref or an explicit unresolved state.

## 12. Explicit exclusions

B-05 does not implement:

- real measurement formulas or authoritative thresholds;
- physical validation, scientific qualification, or Dossier issuance;
- a solver, reference runner, candidate execution, or failure-injection lab;
- official evaluation-plan composition or `ScoreInput` construction;
- Challenge ranking, frontier promotion, settlement, chain intents, or
  emissions;
- customer rights, product readiness, commercial evidence, or disclosure of
  protected evidence; or
- cross-Challenge score comparison or aggregation.

Those exclusions are ownership boundaries, not missing implementation details.
