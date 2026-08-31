# Research Resource Policy Contract

**Version:** 0.2<br>
**Status:** AGENT-SELECTED WORKING CONTRACT<br>
**Ticket:** B-02C<br>
**Authority class:** bounded engineering contract only<br>
**Depends on:** B-02B and B-07R<br>
**Maturity ceiling:** no scientific, security, operations, economics, LIVE,
network, launch, or production qualification

This contract defines an exact, immutable, fixture-capable resource-policy
boundary around the policy-agnostic construction output produced by B-02B. It
does not authorize production hardware, spending, prices, quotas, queues,
security acceptance, or execution.

Version 0.2 records an implementation-discovered fail-closed clarification:
derived content addresses prove byte identity rather than operation
provenance, so readiness also receives the exact plan/ref and downstream
services recompute supplied derived values before trusting them. No policy,
production, operations, economics, security, or scientific authority changed.

The normative ownership law is:

```text
exact immutable ResolvedConstructionPlan
+ exact unchanged StaticResourceRequirement values and impact tags
+ exact ResearchResourcePolicy
+ exact ResourceClass
+ exact nominal fixture authority context

-> one exact static policy assessment
-> one fixture-only readiness/admissibility result
-> optional pure enforcement/cancellation/accounting values

or

-> one typed fail-closed non-scientific outcome
```

A resource-policy change changes the policy result. It never changes Strategy
semantics, compiler semantics, the plan, the plan hash, or a static
construction requirement.

---

## 1. Authority reconciliation and ownership

### 1.1 Controlling owners

- B-02B owns `ResolvedConstructionPlan`, its content ref, exact
  `StaticResourceRequirement` values, resource impact tags, compiler identity,
  construction environment pins, and all construction semantics.
- B-02C consumes those values and owns resource-class identity, declared
  fixture ceilings, policy support/admissibility, pure enforcement outcomes,
  kill/cancellation provenance, non-scientific resource receipts, and typed
  resource deferral.
- B-05 owns `ReconstructionEvidencePolicy`, scientific evidence sufficiency,
  coverage-qualified stopping, `INDETERMINATE`, and scientific outcomes.
- B-07E owns calibrated forecasting algorithms, model/calibration identity,
  forecast support, and forecast uncertainty.
- B-07S owns future wire names, requests, results, canonical wire envelopes,
  service errors, bounds, and protocol lifecycle.
- Wave C operations/economics owns binding execution quotes, real capacity
  admission, prices, quotas, congestion, charging, and remote operational
  execution.
- A7 retains official submission `CANCELLED` and `FAILED_INFRA` lifecycle
  ownership. B-02C defines no alternate official lifecycle and performs no A7
  state transition.

### 1.2 KEEP / WRAP / NEW disposition

| Surface | Disposition | Consequence |
|---|---|---|
| B-02B plan/ref/compiler/environment/static-requirement types | KEEP + WRAP | Consume exact public types and defensively copy them; never duplicate or mutate them. |
| A3/B-02A Challenge, id, version, unit-ref, UInt64, finite Float64, canonical-value, and tagged-digest grammar | KEEP + WRAP | Reuse validators and canonical values under one B-02C domain frame. |
| A7 `SubmissionResourceLimits` | KEEP, not reused | It bounds hostile request capture/store accounting, not reconstruction resource policy. |
| A7 `ExecutionEnvironmentPin` | KEEP, not aliased | It is a different A7 attempt identity. B-02C binds B-02B `EnvironmentPin`. |
| A8 `FixtureRuntimePolicy` and resource-violation cause | KEEP, not reused | Private fixture retry semantics cannot become policy admission or receipts. |
| resource-policy package, refs, assessments, enforcement, receipts | NEW | Owned by B-02C in a one-way standard-library-only package. |
| persistence | DEFER | No existing generic store owns these types; B-02C produces exact bytes/refs only. |

### 1.3 Package and dependency direction

The implementation owner is `carbon.resource_policy`:

```text
carbon.resource_policy
  -> carbon.construction
  -> carbon.authoring canonical/primitives/refs
  -> carbon.registry ChallengeKey

carbon.construction -/> carbon.resource_policy
carbon.fees         -/> carbon.resource_policy
carbon.traineval    -/> carbon.resource_policy
carbon.mcp          -/> carbon.resource_policy
carbon.scoring      -/> carbon.resource_policy
```

The package is standard-library-only. It imports no backend, scheduler,
forecast service, fee/quote policy, scorer, official lifecycle, or optional
dependency. B-07E and later adapters may depend on this package; it must not
depend on them.

---

## 2. Canonical identity and reference law

### 2.1 Reused grammar and domain separation

B-02C reuses the exact A3/B-02A rules for `ChallengeKey`, canonical ids,
version tokens, strict text, exact Boolean, UInt64, finite binary64, tuple
bounds, owner refs, and `sha256:<64 lowercase hex>` digests. It reuses B-02A
canonical scalar/tuple/record/ref values rather than defining a second generic
identity system.

Resource-policy documents use:

```text
schema_version = "1.0"
canonicalization_profile = "carbon_resource_policy_canonical_v1"
header = "carbon.resource_policy.canonical.v1\0"
```

The B-02A and B-02B registries remain closed. B-02C owns one literal closed
object/ref/field registry and explicit adapters for nested B-02B refs and
models. Decoders reject unknown or reordered fields, unknown union tags,
subclasses, aliases, trailing bytes, noncanonical order, duplicate set-like
members, invalid values, and digest mismatch.

### 2.2 Long-lived authored refs

`ResearchResourcePolicyRef` is exact, frozen, slotted, and Challenge-bound:

```text
challenge_key
object_id
object_version
schema_version
canonicalization_profile
content_digest
```

`ResourceClassRef` is a distinct exact, frozen, slotted, Challenge-bound ref:

```text
challenge_key
object_id
object_version
schema_version
canonicalization_profile
content_digest
```

A class from another Challenge always rejects. V1 deliberately has no global
class variant: resource hardware/environment meaning may be reusable in a
future owner contract, but this fixture policy binds every class and all of its
provenance to one exact Challenge. There is no implicit latest, version
ordering, name alias, downgrade, or class substitution.

### 2.3 Resolved refs

`StaticResourceAssessmentRef`, `FixtureResourceDecisionRef`,
`ResourceCancellationRecordRef`, and `ObservedResourceReceiptRef` are distinct
exact digest-only refs:

```text
challenge_key
schema_version
canonicalization_profile
content_digest
```

The same fields do not make the ref types interchangeable. Exact type is part
of every check. Historical exact bytes remain valid when their dependencies
remain available; stale means a mismatch with an explicit expected ref or
binding, never merely “not latest.”

### 2.4 Acyclic content graph

```text
ResourceClass
  -> exact Challenge + construction EnvironmentPin
  -> supported static dimensions + exact observation metrics

ResearchResourcePolicy
  -> Challenge + assembly/catalog/compiler
  -> exact ResourceClassRef bindings + ceilings/limits/readiness law + context

StaticResourceAssessment
  -> policy/class/plan refs + exact copied static requirements/tags

FixtureResourceDecision
  -> assessment ref + exact availability-input union

ResourceCancellationRecord
  -> policy/class/plan + exact actor/reason matrix
  -> optional matching enforcement event + observed facts

ObservedResourceReceipt
  -> policy/class/plan + assessment/decision
  -> truthful build/reuse/replicate/accounting unions
  -> stop-cause-dependent cancellation/event bindings
```

No object points to its own ref or includes its digest in its digest preimage.

---

## 3. Closed shared subordinate schemas

Every record below is exact, frozen, slotted, subclass-rejecting, bounded, and
defensively reconstructed. Set-like tuples sort by complete canonical member
bytes and reject duplicates. Ordered semantic tuples preserve declared order.
All UInt64 fields reject Boolean, negative values, floats, subclasses, and
overflow.

Unless a field explicitly says `PortableOwnerRef`, every B-02A owner ref in a
B-02C value is an exact `PinnedOwnerRef` whose `ChallengeScope` equals the
containing value's Challenge. Unit refs and exact upstream B-02B values retain
their already-authored portable/global-or-Challenge scope; B-02C never changes
that scope.

`PortableOwnerRef<K>` is specification shorthand for the same existing exact
B-02A kind-specific owner-ref class, with either `GlobalScope` or
`ChallengeScope` equal to the containing Challenge. It is not a wrapper,
protocol, base class, or runtime alias. A Challenge-scoped portable ref from a
different Challenge always rejects.

### 3.1 Nominal authority contexts

There is no caller-selected `practice | official` string or Boolean.

```text
FixtureResourceProvenance
  fixture_registration_ref: PinnedOwnerRef<fixture_registration>
  source_provenance_refs:
    nonempty canonical set tuple[PinnedOwnerRef<provenance>]
  authority_marker = FIXTURE_PROVENANCE_NOT_PRODUCTION

FixturePracticeResourceContext
  challenge_key
  context_id
  fixture_registration_ref: PinnedOwnerRef<fixture_registration>
  internal_service_scope_ref: PinnedOwnerRef<internal_service_scope>
  authority_marker = FIXTURE_PRACTICE_NOT_OFFICIAL

FixtureOfficialShapedResourceContext
  challenge_key
  context_id
  fixture_registration_ref: PinnedOwnerRef<fixture_registration>
  internal_service_scope_ref: PinnedOwnerRef<internal_service_scope>
  authority_marker = FIXTURE_OFFICIAL_SHAPED_NOT_OFFICIAL

ResourceAuthorityContext = exact nominal union[
  FixturePracticeResourceContext |
  FixtureOfficialShapedResourceContext
]
```

These are distinct exact nominal classes. Neither can be upgraded, serialized
as production authority, or substituted for the other. B-02C v1 has no real
official, production, or remote context variant.

Every owner ref inside a context or `FixtureResourceProvenance` is exactly
Challenge-scoped to the containing Challenge. The shorthand `PinnedOwnerRef<K>`
means the existing exact owner-kind-specific B-02A nominal ref, never a generic
runtime ref class.

### 3.2 Static ceilings and observed metrics

B-02C reuses exact B-02B `StaticResourceDimension` and
`StaticResourceRequirement` values. Runtime observations are class-owned
metrics and do not silently alias B-02B dimensions:

```text
DeclaredResourceCeiling
  dimension_id
  unit_ref: exact PortableOwnerRef<unit>
  maximum_quantity: UInt64

ResourceObservationMetric
  metric_id
  unit_ref: exact PortableOwnerRef<unit>
  observation_role:
    RESOURCE_CONSUMPTION | RESOURCE_COST_NOT_PRICE | OBSERVED_LATENCY

ObservedResourceQuantity
  metric_id
  unit_ref: exact PortableOwnerRef<unit>
  quantity: UInt64
  observation_role:
    RESOURCE_CONSUMPTION | RESOURCE_COST_NOT_PRICE | OBSERVED_LATENCY

ObservationUnavailableReason =
  NO_WORK_STARTED |
  CANCELLED_BEFORE_OBSERVATION |
  OBSERVATION_FAILED |
  INFRASTRUCTURE_FAILURE

ObservedMetricBinding = exact nominal union[
  OBSERVED(ObservedResourceQuantity) |
  UNAVAILABLE(ObservationUnavailableReason)
]
```

`RESOURCE_COST_NOT_PRICE` is consumed compute/storage/network-equivalent work,
not currency. There is no amount, currency, price, fee, exchange rate, quota,
invoice, or settlement field. A resource class defines exactly one latency
metric, exactly one resource-cost-not-price metric, and at least one
consumption metric. Every observation must exactly match one class metric by
id, unit, and role; metric ids are unique. Quantities are cumulative totals
for their exact receipt attempt, so later observations of the same metric can
never be lower than earlier stop-time observations.

### 3.3 Readiness and enforcement declarations

```text
OperationalRequirementDisposition = exact nominal union[
  REQUIRED |
  NOT_APPLICABLE(PinnedOwnerRef<applicability_reason>)
]

OperationalReadinessRequirements
  validator_capacity: OperationalRequirementDisposition
  reconstruction_funding: OperationalRequirementDisposition
  queue_availability: OperationalRequirementDisposition
  evidence_budget_availability: OperationalRequirementDisposition

EnforcementPoint =
  PRE_ALLOCATION_READINESS
  PRE_EXECUTION
  RUNTIME_OBSERVATION

EnforcementMode =
  PREVENT_START_ON_EXCESS |
  PREVENT_NEXT_UNIT_ON_EXCESS |
  STOP_ON_FIRST_OBSERVED_EXCESS

EnforcementObservationKind =
  CURRENT_TOTAL | ATTEMPTED_NEXT_TOTAL

RuntimeResourceLimit
  limit_id
  metric_id
  unit_ref: exact PortableOwnerRef<unit>
  maximum_quantity: UInt64
  enforcement_point: EnforcementPoint
  enforcement_mode: EnforcementMode

ResourceEnforcementObservation
  metric_quantity: ObservedResourceQuantity
  observation_kind: EnforcementObservationKind
```

An enforcement point is a resource-policy location only. It is not a
scientific gate, evidence stage, official lifecycle state, or permission to
launch a process. Point/mode compatibility is closed: pre-allocation uses
`PREVENT_START_ON_EXCESS` with `ATTEMPTED_NEXT_TOTAL`, pre-execution uses
`PREVENT_NEXT_UNIT_ON_EXCESS` with `ATTEMPTED_NEXT_TOTAL`, and runtime uses
`STOP_ON_FIRST_OBSERVED_EXCESS` with `CURRENT_TOTAL`. Post-stop accounting is
an observation/receipt activity, not an enforcement point. Every inclusive
limit continues at `quantity <= maximum_quantity` and breaches only at
`quantity > maximum_quantity`; B-02C never clamps or consumes the attempted
next unit.

### 3.4 Closed input failures and semantic issues

Malformed canonical bytes, wrong exact types, invalid bounds, digest tamper,
or an object/ref recomputation mismatch raises one typed, fixed, non-echoing
`ResourcePolicyInputRejected` and produces no content-addressed result. Its
closed codes are `WRONG_TYPE`, `INVALID_VALUE`, `INVALID_CANONICAL_BYTES`,
`TRAILING_BYTES`, `REF_DIGEST_MISMATCH`, `POLICY_BUNDLE_INCOMPLETE`, and
`LIMIT_NOT_BOUND`.
Their fixed messages are respectively “input has the wrong exact type”,
“input value is outside the closed contract”, “canonical bytes are invalid”,
“canonical bytes contain trailing data”, “object and ref digest do not match”,
“policy class bundle is incomplete or injected”, and “runtime limit is not
bound by policy”. The exception path is a bounded trusted schema path, never a
hostile value.

Content addressing proves byte identity, not semantic provenance. Every
downstream operation that receives a derived assessment, decision,
enforcement result, or cancellation record must recompute that value from the
exact authoritative inputs it also receives and require exact equality before
using it. A digest-valid value constructed directly by a caller is not trusted
as evidence that the corresponding upstream operation ran. Generic structural
encoding/decoding and ref verification never establish semantic provenance.
Because an observed receipt is B-02C's terminal artifact, its public builder
returns the exact receipt/ref pair only after all §10 checks, and its public
validator requires the complete semantic dependency set and recomputes that
pair. There is no public unguarded receipt-ref issuer.

`ResourcePolicyIssue` is reserved for verified, well-formed inputs. Its closed
code/message/path registry is:

| Code | Fixed public message | Path pattern |
|---|---|---|
| `STALE_POLICY_REF` | selected policy ref is stale | `/expected_active_policy_ref` |
| `STALE_RESOURCE_CLASS_REF` | selected resource class ref is stale | `/expected_active_resource_class_ref` |
| `CHALLENGE_MISMATCH` | resource input has the wrong Challenge | `/challenge_key` |
| `AUTHORITY_CONTEXT_MISMATCH` | resource authority context does not match | `/authority_context` |
| `PLAN_ASSEMBLY_MISMATCH` | construction plan assembly does not match policy | `/construction_plan_ref/candidate_assembly_ref` |
| `PLAN_CATALOG_MISMATCH` | construction plan catalog does not match policy | `/construction_plan_ref/parameter_catalog_ref` |
| `PLAN_COMPILER_MISMATCH` | construction plan compiler does not match policy | `/construction_plan_ref/compiler_identity` |
| `PLAN_ENVIRONMENT_MISMATCH` | construction plan environment is unsupported | `/resource_class/required_plan_environment_pins/<index>` |
| `RESOURCE_CLASS_NOT_BOUND` | resource class is not bound by policy | `/resource_class_ref` |
| `UNSUPPORTED_DIMENSION` | static resource dimension is unsupported | `/static_resource_requirements/<index>/dimension_id` |
| `UNSUPPORTED_UNIT` | resource unit is unsupported | `/static_resource_requirements/<index>/unit_ref` |
| `UNSUPPORTED_IMPACT_TAG` | resource impact tag is unsupported | `/resource_impact_tags/<index>` |
| `STATIC_REQUIREMENT_OVER_LIMIT` | static resource requirement exceeds its ceiling | `/static_resource_requirements/<index>/quantity` |
| `LIMIT_OBSERVATION_MISMATCH` | runtime observation does not match its limit | `/observation` |
| `ENFORCEMENT_EVALUATION_FAILURE` | resource enforcement failed closed | `/enforcement` |

`<index>` is the zero-based index in the already canonical tuple and therefore
does not disclose protected topology. Issues never echo hostile values. A
semantic operation may return several issues only within its selected outcome
category; those issues sort by path and code and reject duplicates.

---

## 4. ResourceClass

`ResourceClass` is an exact long-lived object:

```text
object_kind = "resource_class"
schema_version = "1.0"
canonicalization_profile = "carbon_resource_policy_canonical_v1"
challenge_key
object_id
object_version
execution_environment_pin: exact B-02B EnvironmentPin
required_plan_environment_pins:
  nonempty canonical set tuple[exact B-02B EnvironmentPin]
supported_dimensions:
  nonempty canonical set tuple[exact B-02B StaticResourceDimension]
observation_metrics:
  nonempty canonical set tuple[ResourceObservationMetric]
provenance: FixtureResourceProvenance
authority_marker = FIXTURE_RESOURCE_CLASS_NOT_PRODUCTION
```

V1 exposes no global, registered, or production class/provenance variant. All
nested `PinnedOwnerRef` provenance refs are Challenge-scoped to `challenge_key`;
portable unit refs retain their authored scope. A real or reusable
cross-Challenge hardware class requires a prospective schema, human-supplied
values, security/operations qualification, and its own exact reviewed identity.

Class identity says only which declared fixture environment and dimensions a
policy may reason about. It does not prove capacity, availability,
reproducibility, sandboxing, performance, security, or scientific suitability.
`execution_environment_pin` must occur exactly in
`required_plan_environment_pins`. During assessment, that complete required
set must be a subset of exact `ResolvedConstructionPlan.environment_pins`.
Additional plan pins are allowed because they remain B-02B construction
semantics; B-02C neither removes nor reinterprets them. Any missing required
pin produces `ENVIRONMENT_MISMATCH` / `PLAN_ENVIRONMENT_MISMATCH`.

---

## 5. ResearchResourcePolicy

### 5.1 Class binding

```text
ResourceClassPolicyBinding
  resource_class_ref: exact ResourceClassRef
  ceilings: nonempty canonical set tuple[DeclaredResourceCeiling]
  supported_impact_tags: canonical set tuple[canonical id]
  runtime_limits: canonical set tuple[RuntimeResourceLimit]
  readiness_requirements: OperationalReadinessRequirements
```

Ceilings must form an exact one-to-one cover of the referenced class'
`supported_dimensions`: every class dimension id/unit appears exactly once and
no other dimension appears. A missing dimension is a structurally invalid
policy bundle, never unlimited. A ceiling may be zero. Runtime-limit ids are
unique; every limit metric id/unit must exactly match one referenced-class
observation metric, and its point/mode must satisfy §3.3. A class observation
metric without a runtime limit is accounting-only, not implicitly unlimited
or enforceable.

Every plan impact tag must appear exactly in `supported_impact_tags`; an
unknown tag is unsupported, never ignored. A tag is a closed routing/support
label only; no numeric value is inferred from a tag, class name, environment
label, forecast, receipt, or host inspection.

### 5.2 Policy object

`ResearchResourcePolicy` is exact, frozen, slotted, immutable, and
Challenge-bound:

```text
object_kind = "research_resource_policy"
schema_version = "1.0"
canonicalization_profile = "carbon_resource_policy_canonical_v1"
challenge_key
object_id
object_version
candidate_assembly_ref: exact CandidateAssemblyContractRef
parameter_catalog_ref: exact ParameterCatalogRef
compiler_identity: exact CompilerIdentity
authority_context:
  FixturePracticeResourceContext |
  FixtureOfficialShapedResourceContext
class_bindings:
  nonempty canonical set tuple[ResourceClassPolicyBinding]
policy_authority_ref: PinnedOwnerRef<policy_authority>
provenance: FixtureResourceProvenance
unknown_or_invalid_policy = REJECT
authority_marker = FIXTURE_RESOURCE_POLICY_NOT_PRODUCTION
```

The Challenge on every nested ref/context must equal the policy Challenge.
Class refs are unique. Assembly, catalog, compiler, and plan environment
meanings never come from the policy by inference.

No `ResearchResourcePolicyRef` may be issued, decoded as resolved, or used for
assessment until `validate_research_resource_policy_bundle(...)` receives the
policy plus a canonical nonempty tuple of every exact `(ResourceClass,
ResourceClassRef)` pair named by `class_bindings`. It recomputes each pair,
requires an exact one-to-one ref cover with no omitted/injected class, and
validates every ceiling, metric, limit, context, readiness law, provenance, and
Challenge binding. This prevents an invalid dormant class binding from hiding
inside an otherwise usable policy. Structural decoding without the full bundle
does not claim resolved validity.

Policy bytes contain no forecast model/calibration, probability of success,
price, quota, queue rank, requester reputation, stake, sponsor priority,
scientific threshold, evidence requirement, score, gate, frontier, settlement,
or protected evaluator allocation.

---

## 6. Exact plan consumption and static assessment

### 6.1 Ingress and immutability

The pure `assess_static_resources(...)` operation accepts exact:

```text
ResolvedConstructionPlan
ResolvedConstructionPlanRef
ResearchResourcePolicy
ResearchResourcePolicyRef
complete canonical tuple of every exact (ResourceClass, ResourceClassRef) pair
selected exact (ResourceClass, ResourceClassRef) pair
expected active ResearchResourcePolicyRef
expected active ResourceClassRef
exact matching ResourceAuthorityContext
```

It first applies §3.4 and produces no assessment if any object/ref pair is
malformed, tampered, mismatched, or if the full policy bundle is incomplete.
Persisted hostile plan bytes enter through B-02B
`decode_resolved_construction_plan(..., expected_ref=...)`; B-02C never
reimplements the plan codec. After full bundle verification, the evaluator
verifies the separately supplied selected class pair. When bound, that pair
must equal the corresponding complete-bundle member; when unbound, it can
produce `UNSUPPORTED_RESOURCE_CLASS` without trusting an unverified class. The
evaluator then defensively reconstructs exact plan
requirements/tags, and compares the plan's exact Challenge, assembly ref,
catalog ref, compiler identity, and required environment pins with policy/class
bindings.

It must prove before returning that the caller's plan and every nested value
remain byte-identical. It never adds, deletes, clamps, converts, normalizes,
or reorders a plan requirement and never writes policy state into the plan.

### 6.2 Static assessment

```text
StaticResourceAssessment
  object_kind = "static_resource_assessment"
  schema_version
  canonicalization_profile
  challenge_key
  policy_ref: exact verified ResearchResourcePolicyRef
  resource_class_ref: exact verified selected ResourceClassRef
  expected_active_policy_ref: exact ResearchResourcePolicyRef
  expected_active_resource_class_ref: exact ResourceClassRef
  construction_plan_ref
  authority_context
  static_resource_requirements:
    exact tuple[B-02B StaticResourceRequirement]
  resource_impact_tags: exact tuple[canonical id]
  outcome: StaticAssessmentOutcome
  issues: canonical tuple[ResourcePolicyIssue]
  epistemic_layer = STATIC_CONSTRUCTION_REQUIREMENT
  authority_marker = STATIC_POLICY_RESULT_NOT_EXECUTION_OR_SCIENCE
```

`ResourcePolicyIssue` carries only a closed code, safe canonical path, and a
fixed non-echoing message from §3.4. `ADMISSIBLE` requires an empty issue tuple;
every other result requires at least one deterministic issue. Issues sort by
path and code.

```text
StaticAssessmentOutcome =
  ADMISSIBLE
  UNSUPPORTED_RESOURCE_CLASS
  UNSUPPORTED_REQUIREMENT
  OVER_LIMIT
  STALE_POLICY
  STALE_REFERENCE
  CHALLENGE_MISMATCH
  AUTHORITY_CONTEXT_MISMATCH
  PLAN_BINDING_MISMATCH
  ENVIRONMENT_MISMATCH
```

`ADMISSIBLE` means only that exact static requirements are supported and at or
below declared ceilings for that exact fixture policy/class/context. It is not
capacity admission, a binding quote, permission to execute, scientific
evidence, or evidence-budget satisfaction.

Stale policy means the exact verified policy ref differs from the exact
`expected_active_policy_ref`. Stale reference means the exact verified selected
class ref differs from `expected_active_resource_class_ref`; it never means a
digest-invalid object. Opaque versions are never ordered.

The single outcome follows closed category precedence:

```text
STALE_POLICY
> STALE_REFERENCE
> CHALLENGE_MISMATCH
> AUTHORITY_CONTEXT_MISMATCH
> PLAN_BINDING_MISMATCH
> ENVIRONMENT_MISMATCH
> UNSUPPORTED_RESOURCE_CLASS
> UNSUPPORTED_REQUIREMENT
> OVER_LIMIT
> ADMISSIBLE
```

Evaluation collects every deterministic issue in the first nonempty category
only. Canonical/programmer failures remain `ResourcePolicyInputRejected`; no
opaque catch-all semantic assessment is issued.

---

## 7. Four epistemic resource layers

The exact layer order is descriptive, not a conversion pipeline:

| Layer | Exact owner/type in this contract | What it means | What it cannot mean |
|---|---|---|---|
| 1. Static construction requirement | B-02B `StaticResourceRequirement`, copied into B-02C `StaticResourceAssessment` | Deterministic plan-derived quantity and declared policy comparison | Runtime prediction, capacity, price, or observed use |
| 2. Calibrated forecast | Future B-07E-owned exact nominal type and authority marker | Prediction with model, calibration window, support, scope, uncertainty | Admission, quote, observed use, quality, or science |
| 3. Binding execution quote/admission | Future Wave-C-owned exact nominal type and authority marker | Capacity/economic commitment under later policy | Measurement, receipt, score, or science |
| 4. Observed resource receipt | B-02C exact `ObservedResourceReceipt` | Factual resource/accounting observations after/while work occurs | Forecast, authorization, price, or scientific evidence |

B-02C v1 implements no forecast algorithm, calibration claim, binding quote,
price, real admission, or quote issuer. Its exported concrete static assessment
and observed receipt are exact nominal classes with fixed layer markers.
Every API checks exact type, so a forecast/quote-shaped lookalike, subclass,
wrong layer tag, static assessment, or receipt is rejected rather than
converted. Future B-07E/Wave C types require prospective contracts and cannot
be added to B-02C's closed v1 unions in place.

---

## 8. Capacity, funding, queue, and evidence-budget readiness

### 8.1 Fixture-only availability facts

Real operational commitments are absent. Tests may use this exact structural
fixture carrier:

```text
FixtureAvailabilityState = AVAILABLE | UNAVAILABLE | NOT_APPLICABLE

FixtureResourceAvailability
  object_kind = "fixture_resource_availability"
  schema_version
  canonicalization_profile
  challenge_key
  policy_ref
  resource_class_ref
  authority_context
  validator_capacity: FixtureAvailabilityState
  reconstruction_funding: FixtureAvailabilityState
  queue_availability: FixtureAvailabilityState
  evidence_budget_availability: FixtureAvailabilityState
  fixture_registration_ref: PinnedOwnerRef<fixture_registration>
  authority_marker = FIXTURE_AVAILABILITY_NOT_OPERATIONAL_COMMITMENT

FixtureAvailabilityInput = exact nominal union[
  NO_AVAILABILITY_INPUT |
  PROVIDED(FixtureResourceAvailability)
]
```

The selected class binding's `OperationalReadinessRequirements` controls each
field. A `REQUIRED` requirement accepts only `AVAILABLE` or `UNAVAILABLE`; its
missing/no-input state is unavailable. A `NOT_APPLICABLE(reason)` requirement
accepts only `NOT_APPLICABLE` and cannot be made to claim a false commitment.
For a provided carrier, `fixture_registration_ref` must exactly equal the
registration ref inside its nominal `authority_context`.
For `NO_AVAILABILITY_INPUT`, every required field contributes its unavailable
cause while every not-applicable field contributes none. No default is
optimistic. Exact Boolean is not used, preventing bool/int or truthiness
confusion.

### 8.2 Fixture decision

`decide_fixture_readiness(...)` consumes the exact construction plan/ref, an
exact `ADMISSIBLE` static assessment/ref, its verified policy/ref and complete
class bundle, the selected exact class pair, and one exact availability-input
union. It first recomputes the assessment from the plan and exact active
policy/class/context inputs and requires exact equality. It then revalidates
the selected binding's readiness requirements and all repeated refs/context
before returning:

```text
FixtureResourceDecision
  object_kind = "fixture_resource_decision"
  schema_version
  canonicalization_profile
  challenge_key
  assessment_ref
  policy_ref
  resource_class_ref
  authority_context
  availability_input: exact FixtureAvailabilityInput
  outcome: FIXTURE_ADMISSIBLE | EVIDENCE_DEFERRED
  deferral_causes: canonical set tuple[
    CAPACITY_UNAVAILABLE |
    RECONSTRUCTION_FUNDING_UNAVAILABLE |
    QUEUE_UNAVAILABLE |
    EVIDENCE_BUDGET_UNAVAILABLE
  ]
  authority_marker = POLICY_ADMISSIBILITY_NOT_QUOTE_OR_EXECUTION
```

The complete exact input union is part of decision identity, so two fixture
registrations or an omitted carrier cannot collapse into the same unexplained
decision. Every `REQUIRED` field is evaluated; causes are not hidden by
precedence. `FIXTURE_ADMISSIBLE` requires every required fixture state
`AVAILABLE`, every not-applicable state `NOT_APPLICABLE`, and empty causes. It
cannot be produced for a registered/production context because v1 has no such
context or availability type.

`EVIDENCE_DEFERRED` is a non-scientific resource state. It does not lower or
change the registered scientific requirement, create `INDETERMINATE`, infer
candidate quality, create negative evidence, or authorize a later scientific
stop. B-05/B-E1 remain the only owners of scientific sufficiency and stopping.

---

## 9. Enforcement, kill, and cancellation

### 9.1 Pure enforcement result

B-02C performs no process launch or kill. `evaluate_enforcement(...)` accepts
the exact plan/ref, policy/ref, complete verified class bundle, selected class
pair, assessment/ref, `FIXTURE_ADMISSIBLE` decision/ref, one exact canonical
`limit_id`, and one exact `ResourceEnforcementObservation`. It resolves the
matching declared runtime limit before result construction. An unbound id is
`ResourcePolicyInputRejected(LIMIT_NOT_BOUND)` and produces no event/result;
no policy field is fabricated. The pure evaluator then returns:

```text
ResourceEnforcementAction =
  NO_STOP |
  PREVENT_FIXTURE_START |
  PREVENT_NEXT_UNIT |
  REQUEST_FIXTURE_STOP |
  FAIL_CLOSED

ResourceEnforcementEvent
  object_kind = "resource_enforcement_event"
  schema_version
  canonicalization_profile
  challenge_key
  policy_ref
  resource_class_ref
  construction_plan_ref
  assessment_ref
  decision_ref
  authority_context
  limit_id
  enforcement_point
  enforcement_mode
  maximum_quantity
  observation: exact ResourceEnforcementObservation
  action: ResourceEnforcementAction
  outcome:
    CONTINUE_FIXTURE |
    STOPPED_OVER_LIMIT |
    ENFORCEMENT_FAILURE
  issue: NO_ISSUE | exact ResourcePolicyIssue

ResourceEnforcementResult
  object_kind = "resource_enforcement_result"
  schema_version
  canonicalization_profile
  challenge_key
  policy_ref
  resource_class_ref
  construction_plan_ref
  assessment_ref
  decision_ref
  authority_context
  event: exact ResourceEnforcementEvent
  outcome:
    CONTINUE_FIXTURE |
    STOPPED_OVER_LIMIT |
    ENFORCEMENT_FAILURE
  authority_marker = RESOURCE_ENFORCEMENT_NOT_EXECUTION_OR_SCIENCE
```

At/below-limit produces `CONTINUE_FIXTURE` and `NO_STOP`. Above-limit produces
`STOPPED_OVER_LIMIT` and the mode's exact prevention/stop action. A
point/mode mismatch, metric/unit/role mismatch,
or evaluator failure produces `ENFORCEMENT_FAILURE`, `FAIL_CLOSED`, and the
single matching fixed issue. No exception fallback creates continuation.

Continue and ordinary over-limit events use `NO_ISSUE`; the limit id, maximum,
observation, and action are their complete factual explanation. Only
`ENFORCEMENT_FAILURE` carries one issue. Every event ref/context field must
equal its result field exactly, and result `outcome` must equal event `outcome`.
The only valid triples are `(CONTINUE_FIXTURE, NO_STOP, NO_ISSUE)`,
`(STOPPED_OVER_LIMIT, the mode-specific prevention/stop action, NO_ISSUE)`,
and `(ENFORCEMENT_FAILURE, FAIL_CLOSED, one exact issue)`.

`CONTINUE_FIXTURE` remains fixture-only. Cancellation, infrastructure failure,
and readiness withdrawal are not fabricated as limit comparisons; they use the
exact stop/cancellation record below. All resource failures remain distinct
from candidate failure.

### 9.2 Stop/cancellation actor and record

Cancellation authority is a closed exact union:

```text
PolicyEnforcerActor
  policy_authority_ref: PinnedOwnerRef<policy_authority>

FixtureRequesterActor
  fixture_registration_ref: PinnedOwnerRef<fixture_registration>

InfrastructureActor
  infrastructure_failure_ref: PinnedOwnerRef<infrastructure_failure>

CancellationActor = exact nominal union[
  PolicyEnforcerActor |
  FixtureRequesterActor |
  InfrastructureActor
]

StopPointBinding = exact nominal union[
  NO_ENFORCEMENT_POINT |
  AT(EnforcementPoint)
]
```

There is no generic string actor or caller-supplied “authorized” flag.

`make_cancellation_record(...)` accepts the exact plan/ref, policy/ref,
complete verified class bundle, selected class pair, assessment/ref,
decision/ref, exact actor, reason, stop-point binding, work-started value,
canonical observed-quantity tuple, and either no enforcement result or the
exact `ResourceEnforcementResult` whose event will be embedded. It verifies all
repeated refs and the matrix below before issuing bytes/ref.

```text
ResourceCancellationRecord
  object_kind = "resource_cancellation_record"
  schema_version
  canonicalization_profile
  challenge_key
  policy_ref
  resource_class_ref
  construction_plan_ref
  assessment_ref
  fixture_decision_ref
  authority_context
  stop_point: exact StopPointBinding
  actor: exact CancellationActor
  reason:
    REQUESTER_CANCELLED |
    POLICY_LIMIT_REACHED |
    CAPACITY_WITHDRAWN |
    FUNDING_WITHDRAWN |
    QUEUE_WITHDRAWN |
    EVIDENCE_BUDGET_WITHDRAWN |
    ENFORCEMENT_FAILURE |
    INFRASTRUCTURE_FAILURE
  enforcement_event_binding:
    NO_ENFORCEMENT_EVENT | exact ResourceEnforcementEvent
  work_started: exact bool
  observed_resource_quantities_so_far:
    canonical set tuple[ObservedResourceQuantity]
  resulting_state:
    CANCELLED_NON_SCIENTIFIC |
    EVIDENCE_DEFERRED |
    INFRASTRUCTURE_UNAVAILABLE_NON_SCIENTIFIC
  authority_marker = RESOURCE_STOP_NOT_SCIENTIFIC_OUTCOME
```

The closed actor/reason/state/event matrix is:

| Actor | Allowed reason | Required event/point | Resulting state |
|---|---|---|---|
| `FixtureRequesterActor` | `REQUESTER_CANCELLED` only | no event; `NO_ENFORCEMENT_POINT` before work, otherwise `AT(PRE_EXECUTION | RUNTIME_OBSERVATION)` | `CANCELLED_NON_SCIENTIFIC` |
| `PolicyEnforcerActor` | `POLICY_LIMIT_REACHED` | exact matching `STOPPED_OVER_LIMIT` event and `AT(event.enforcement_point)` | `CANCELLED_NON_SCIENTIFIC` |
| `PolicyEnforcerActor` | capacity/funding/queue/evidence-budget withdrawal | no event; work started and `AT(PRE_EXECUTION | RUNTIME_OBSERVATION)` | `EVIDENCE_DEFERRED` |
| `PolicyEnforcerActor` | `ENFORCEMENT_FAILURE` | exact matching `ENFORCEMENT_FAILURE` event and `AT(event.enforcement_point)` | `CANCELLED_NON_SCIENTIFIC` |
| `InfrastructureActor` | `INFRASTRUCTURE_FAILURE` only | no event; `NO_ENFORCEMENT_POINT` before work, otherwise `AT(PRE_EXECUTION | RUNTIME_OBSERVATION)` | `INFRASTRUCTURE_UNAVAILABLE_NON_SCIENTIFIC` |

Every record builder receives and verifies the policy/class bundle and the
exact assessment/decision pairs named in the record. Every matching event must
repeat the record's policy/class/plan/assessment/decision/context refs and
equal the point inside `AT(...)`. A bound event with
`PREVENT_FIXTURE_START` requires `work_started = false`; `PREVENT_NEXT_UNIT` or
`REQUEST_FIXTURE_STOP` requires `work_started = true`. A fail-closed event at
pre-allocation requires work not started; a fail-closed event at pre-execution
or runtime requires work started. `work_started = false` requires an empty
`observed_resource_quantities_so_far`; any pre-allocation attempted total
remains in its exact enforcement event. Every observed quantity is unique by
metric id and exactly matches the
selected class' metric id/unit/role. A withdrawal reason is constructible only when the corresponding
selected-binding readiness requirement is `REQUIRED`; it requires the prior
decision `FIXTURE_ADMISSIBLE` and `work_started = true`. A not-applicable field
can never be withdrawn. Policy-limit and enforcement-failure records also
require a prior `FIXTURE_ADMISSIBLE` decision. No other combination is
constructible. The record is immutable and content-addressed. A cancel/kill
never changes the plan, lowers evidence requirements, creates a score/gate
result, or relabels resource absence as candidate physics evidence. Later
integration may map an authorized cancellation to its owner lifecycle, but
B-02C performs no mapping.

`PolicyEnforcerActor.policy_authority_ref` must exactly equal the selected
policy's `policy_authority_ref`. `FixtureRequesterActor.fixture_registration_ref`
must exactly equal the record context's fixture-registration ref.

---

## 10. Observed receipt and reconstruction seam

### 10.1 Resource-only reconstruction bindings

```text
IncompleteBuildIdentity
  challenge_key
  construction_plan_ref
  policy_ref
  resource_class_ref
  execution_environment_pin: exact B-02B EnvironmentPin
  build_attempt_id
  build_attempt_digest

CompleteBuildIdentity
  challenge_key
  construction_plan_ref
  policy_ref
  resource_class_ref
  execution_environment_pin: exact B-02B EnvironmentPin
  build_attempt_id
  complete_build_digest

BuildCompletionBinding = exact nominal union[
  NO_BUILD_STARTED |
  INCOMPLETE(IncompleteBuildIdentity) |
  COMPLETE(CompleteBuildIdentity)
]

FrozenArtifactReuseWindow
  window_id
  complete_build_identity: exact CompleteBuildIdentity
  reuse_policy_ref: PinnedOwnerRef<restriction>
  maximum_declared_uses: positive UInt64
  observed_use_ordinal: UInt64

ReconstructionReplicateIdentity
  challenge_key
  construction_plan_ref
  policy_ref
  resource_class_ref
  replicate_id
  replicate_digest

IncompleteReconstructionReplicateIdentity
  challenge_key
  construction_plan_ref
  policy_ref
  resource_class_ref
  replicate_attempt_id
  replicate_attempt_digest

ReplicateNotApplicableReason =
  NO_WORK_STARTED |
  NOT_A_RECONSTRUCTION_REPLICATE

ReconstructionReplicateBinding = exact nominal union[
  NOT_APPLICABLE(ReplicateNotApplicableReason) |
  INCOMPLETE(IncompleteReconstructionReplicateIdentity) |
  BOUND(ReconstructionReplicateIdentity)
]

DeclaredResourceEvidenceStage =
  NO_WORK_STARTED |
  DECLARED_PRACTICE_REHEARSAL |
  DECLARED_BUILD_ACCOUNTING |
  DECLARED_RECONSTRUCTION_REPLICATE_ACCOUNTING |
  DECLARED_RANDOM_REPEAT_ACCOUNTING
```

The reuse ordinal must satisfy
`1 <= observed_use_ordinal <= maximum_declared_uses`; zero is invalid. A reuse
window repeats one exact complete-build identity and must match the receipt's
Challenge/policy/class/plan. “Declared uses” is resource-accounting scope, not
scientific authorization. Every build/replicate identity is exact
Challenge/policy/class/plan-bound and independent of the receipt that later
contains it, keeping the graph acyclic.

These labels bind declared resource/accounting stages only. The evidence-stage
label does not prove that a scientific build/replicate requirement exists, is
eligible, is complete, or has coverage.

### 10.2 Receipt

`make_observed_resource_receipt(...)` accepts the exact plan/ref, policy/ref,
complete verified class bundle, selected class pair, assessment/ref,
decision/ref, optional exact stop-record/ref pair, optional exact enforcement
result, and every build/reuse/replicate/observation/stage/stop field below. It
recomputes all refs, revalidates the policy bundle, and proves the B-02B plan
bytes/ref unchanged before issuing receipt bytes/ref.

```text
ObservedResourceReceipt
  object_kind = "observed_resource_receipt"
  schema_version
  canonicalization_profile
  challenge_key
  policy_ref
  resource_class_ref
  construction_plan_ref
  assessment_ref
  fixture_decision_ref
  authority_context
  build_completion: exact BuildCompletionBinding
  frozen_artifact_reuse:
    NO_REUSE | FrozenArtifactReuseWindow
  reconstruction_replicate: exact ReconstructionReplicateBinding
  observed_consumption_quantities:
    canonical set tuple[ObservedResourceQuantity]
  observed_latency: exact ObservedMetricBinding
  observed_cost: exact ObservedMetricBinding
  evidence_stage_label: DeclaredResourceEvidenceStage
  stop_cause:
    COMPLETED_RESOURCE_ACCOUNTING |
    POLICY_LIMIT_REACHED |
    CANCELLED |
    ENFORCEMENT_FAILURE |
    INFRASTRUCTURE_FAILURE |
    EVIDENCE_DEFERRED
  stop_record_binding:
    NO_RESOURCE_STOP | exact ResourceCancellationRecordRef
  enforcement_event_binding:
    NO_ENFORCEMENT_EVENT | exact ResourceEnforcementEvent
  work_started: exact bool
  epistemic_layer = OBSERVED_RESOURCE_RECEIPT
  authority_marker = RESOURCE_FACTS_ONLY_NOT_EVIDENCE_OR_PRICE
```

Receipt construction receives and verifies every referenced assessment,
decision, class, optional stop-record pair, and nested event before issuance.
Every consumption quantity has role `RESOURCE_CONSUMPTION`, uses a unique exact
class metric, and matches its unit. The latency and cost bindings target the
class' one exact `OBSERVED_LATENCY` and `RESOURCE_COST_NOT_PRICE` metrics. A
receipt cannot carry currency, price, quote, estimated interval, score,
scientific measurement, gate, candidate-quality statement, `SUPERIOR`,
`NOT_SUPERIOR`, `INDETERMINATE`, frontier, entitlement, or settlement.

The closed cross-field law is:

- `work_started = false` if and only if the receipt has `NO_BUILD_STARTED`,
  `NO_REUSE`, replicate
  `NOT_APPLICABLE(NO_WORK_STARTED)`, stage `NO_WORK_STARTED`, empty consumption,
  and both metric bindings `UNAVAILABLE(NO_WORK_STARTED)`;
- `work_started = true` requires the referenced decision
  `FIXTURE_ADMISSIBLE`; it forbids `NO_BUILD_STARTED`, stage `NO_WORK_STARTED`,
  replicate reason `NO_WORK_STARTED`, and metric unavailability reason
  `NO_WORK_STARTED`; a partial build uses exact `INCOMPLETE`, never a fabricated
  complete identity;
- `COMPLETED_RESOURCE_ACCOUNTING` requires work started, exact `COMPLETE`,
  nonempty consumption, observed latency and cost, and no stop record/event;
- `POLICY_LIMIT_REACHED` requires a stop record with that exact reason and the
  same exact `STOPPED_OVER_LIMIT` event in both record and receipt;
- `CANCELLED` requires a `FixtureRequesterActor`/`REQUESTER_CANCELLED` stop
  record and no enforcement event;
- `ENFORCEMENT_FAILURE` requires the matching policy-enforcer stop record and
  exact `ENFORCEMENT_FAILURE` event;
- `INFRASTRUCTURE_FAILURE` requires the matching infrastructure stop record
  and no enforcement event; and
- pre-work `EVIDENCE_DEFERRED` requires a deferred fixture decision, no stop
  record, and the complete `work_started = false` law above;
- post-start `EVIDENCE_DEFERRED` requires the original
  `FIXTURE_ADMISSIBLE` decision plus the exact matching readiness-withdrawal
  stop record; it never binds an enforcement event.

A bound or exact incomplete replicate is required exactly for the two declared
replicate/repeat stages and is forbidden otherwise. `BOUND` requires completed
resource accounting; an incomplete stop uses `INCOMPLETE`. Reuse requires the exact complete build
named by its window. Every nested Challenge/policy/class/plan/context binding
must equal the receipt, and every build environment must equal the selected
`ResourceClass.execution_environment_pin`. Any other combination rejects
before ref issuance.

Whenever `stop_record_binding` is present, receipt `work_started` must exactly
equal stop-record `work_started`. Every stop-time quantity must have the same
metric id/unit/role in the final receipt: consumption maps to the corresponding
consumption tuple member, latency/cost maps to an `OBSERVED` binding and cannot
become `UNAVAILABLE`. The final cumulative quantity must be greater than or
equal to the stop-time quantity. A final receipt may add later accounting
observations, but it cannot erase or decrease an earlier exact fact.

A receipt cannot rank or screen candidates, permanently deny complete base
reconstruction, lower evidence requirements, or enter official score. B-05 and
B-E1 consume only the exact resource facts they explicitly register; absence
or success of a receipt has no implicit evidence effect.

---

## 11. Hidden-evaluation, hostile-input, and economics boundary

Policy, class, assessment, availability, enforcement, cancellation, and
receipt values may be participant-controlled at an ingress and are hostile.
Constructors and decoders use exact-type checks, bounded tuples/documents,
fixed non-echoing errors, defensive reconstruction, and no dynamic I/O.

The public model has no field for:

- official seed, draw, case, stratum, or protected reference identity;
- hidden case count or realized case/stress composition;
- evaluator topology, validator count/routing, protected concurrency, queue
  position, or official resource allocation;
- exact margin, candidate score, winner probability, rank, or unresolved
  frontier ordering;
- path, URI, import, command, callable, environment variable, credential,
  arbitrary metadata, or participant code;
- price, currency, fee, quota, sponsor priority, stake, reputation, invoice,
  payment, refund, settlement, weight, or emission.

Error code, issue count, ordering, timing, and output size must not depend on a
protected topology or case volume. Resource dimensions/classes/ceilings used in
public fixtures are explicit declared public contract values, never reverse
projections of protected allocation.

Static dimensions do not imply prices. A future economic seam must introduce
its own exact nominal quote/price types and human-owned policy. Any monetary
test canary is rejected; B-02C ships no fixture monetary field.

---

## 12. Fixture policy

Tests may construct a small closed fixture with:

- one exact Challenge;
- one practice resource policy and one distinct official-shaped fixture policy;
- exact Challenge-scoped fixture resource classes only;
- exact B-02B plan environments and dimensions;
- finite UInt64 static ceilings and exact runtime metric limits including
  exact-at-limit and one-over-limit cases;
- per-context required/not-applicable readiness laws plus missing, available,
  and unavailable capacity/funding/queue/evidence-budget variants;
- every enforcement, cancellation, withdrawal, and infrastructure outcome;
- exact observed/unavailable latency and cost, consumption, truthful
  unstarted/incomplete/complete build, reuse, replicate, and receipt variants.

Fixture registrations and authority markers are structural. No fixture object
can authorize production execution, become a production default, be upgraded
in place, supply a price/quota, satisfy security acceptance, or create
scientific evidence. The package ships no default policy or class; fixture
builders live under tests.

---

## 13. Public implementation boundary

The bounded implementation supplies:

- exact immutable models and nominal refs;
- closed canonical encoding/decoding and constant-time ref verification;
- structural `ResourceClass` validation and complete resolved
  `ResearchResourcePolicy`-bundle validation before ref issuance/use;
- typed hard rejection for malformed/tampered inputs and content-addressed
  semantic outcomes only for verified inputs;
- exact pure static assessment;
- exact fixture-only readiness/admissibility with typed
  `EVIDENCE_DEFERRED` causes;
- pure enforcement outcomes and immutable cancellation records;
- immutable observed resource receipts and reconstruction-accounting seams;
- fixed safe issue codes/messages;
- no persistence, scheduler, forecast algorithm, quote, price, payment,
  backend execution, process control, official lifecycle integration, or
  science/evidence engine.

The minimum exported operations are conceptually:

```text
encode/decode ResourceClass and ResearchResourcePolicy
encode/decode resolved assessment/decision/enforcement/cancellation/receipt values
make/verify exact nominal refs
validate_research_resource_policy_bundle(...)
assess_static_resources(...)
decide_fixture_readiness(...)
evaluate_enforcement(...)
make_cancellation_record(...)
make_observed_resource_receipt(...)
validate_observed_resource_receipt(...)
```

Exact Python names may be chosen within this contract without changing
semantics; the final public export inventory is evidence-owned. B-07S later
owns wire-visible projections and operation names.

---

## 14. Required verification

At minimum tests cover:

- exact policy/class canonical identity, ref type separation, digest tamper,
  trailing data, Challenge scope, hard ref-pair rejection, stale valid ref,
  expected-ref identity binding, and stale expected-policy behavior;
- complete policy-bundle cover, omitted/injected/dormant-invalid class,
  duplicate binding, static-dimension/ceiling bijection, observation-metric,
  runtime-limit, readiness-law, and provenance validation;
- exact cross-Challenge, assembly, catalog, compiler, environment, context,
  plan, and class binding;
- exact immutable consumption of plan requirements/tags and byte-identical
  plan/ref before and after every operation;
- unsupported class/requirement, structurally missing-ceiling hard rejection,
  exact-at-limit, over-limit,
  hostile quantity, bool/int confusion, float/non-finite rejection, UInt64
  overflow, unit mismatch, duplicate dimensions, and no clamping/conversion;
- fixture readiness with required/not-applicable laws, no-input identity, each
  unavailable capacity/funding/queue/evidence-budget cause, and deterministic
  combined causes, including rejection of digest-valid assessments whose
  copied requirements/tags do not equal the exact supplied plan;
- point/mode compatibility, exact inclusive limit law, attempted-next versus
  observed totals, continue/prevent-start/prevent-next/stop/fail-closed events;
- cancellation actor/reason/result/event matrix, work-started,
  observations-so-far, withdrawal, and infrastructure states;
- observed receipt with unstarted/incomplete/complete build, reuse-window
  bounds and exact build binding, replicate applicability, stage, class-bound
  consumption, required observed/unavailable latency and cost, and every
  stop-cause cross-law, including rejection of a structurally self-addressed
  receipt whose class-bound environment or metrics were not produced by the
  exact semantic builder;
- exact-type rejection between static assessment, forecast-shaped canary,
  quote-shaped canary, and observed receipt;
- no scientific threshold lowering, outcome inference, score input, price,
  quota, or production authorization;
- protected topology/case-volume non-disclosure and fixed non-echoing issues;
- fixture inability to construct production authority;
- installed wheel, outside-tree import, code authority, public export
  inventory, standard-library dependency set, and one-way package direction;
- affected B-02B construction/canonical/ref, A12 invariant, packaging, and
  quality regressions.

---

## 15. Decision crosswalk and maturity

The durable decision record is `.agent/DECISIONS.md`:

| Decision | Selected law |
|---|---|
| B-02C-D1 | `carbon.resource_policy` ownership, one-way dependencies, and no store |
| B-02C-D2 | domain-separated canonical graph and exact scoped nominal refs |
| B-02C-D3 | exact immutable B-02B plan/static-requirement consumption |
| B-02C-D4 | four nominal epistemic layers with later forecast/quote owners |
| B-02C-D5 | fixture resource classes, ceilings, contexts, and pure static admissibility |
| B-02C-D6 | capacity/funding/queue/evidence-budget fail-closed readiness |
| B-02C-D7 | pure enforcement, kill/cancellation provenance, and resource-only receipts |
| B-02C-D8 | fixture, hidden-evaluation, economics, and maturity ceiling |

These are agent-authorized engineering decisions. Notification does not grant
human-owned operational values or qualification.

Normal merge of the exact independently reviewed contract tree followed by
successful exact-main CI may establish only:

```text
SPECIFIED = YES
RATIFIED_ENGINEERING_CONTRACT = YES
```

Implementation and testing require the separate B-02C implementation branch.
`OPERATIONS_APPROVED`, `ECONOMICS_APPROVED`, `SECURITY_QUALIFIED`,
`SCIENTIFICALLY_QUALIFIED`, `PRODUCTION_QUALIFIED`, and `LIVE` remain `NO`.
Any semantic change to identities, fields, outcomes, or authority requires a
prospective version and a normally merged superseding decision; historical
bytes and evidence are never reinterpreted.
