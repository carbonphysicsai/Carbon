# Generator Runtime Contract

**Ticket:** B-03 — Generator API and fixed-viscosity Burgers fixture
**Contract version:** 0.1
**Status:** agent-selected working engineering contract candidate
**Maturity ceiling:** bounded fixture engineering only
**Implementation owner:** `carbon.generators`
**Fixture owner:** `carbon.generators.burgers`

This contract defines the smallest deterministic generator boundary needed to
construct exact B-02A `CanonicalChallengeCase` values and to exercise
authoring, conformance, censoring, replay, and A3 LIVE-rejection paths. It does
not select a scientific population, a proposal law, physical ranges,
conformance thresholds, reference truth, production entropy, or a LIVE
qualification policy.

The contract becomes bounded engineering authority only after its exact tree
passes exact-head CI, receives clean exact-head Greptile correctness review
with every valid finding repaired and zero unresolved threads, normally merges
with exact reviewed-tree preservation, and passes exact-main CI. Notification
is visibility, not ratification or a silence gate. A tree change requires CI
and Greptile rereview.

## 1. Authority and interpretation

The authority order is the repository constitution and agent constitution;
the active Wave-B board and B-03 ticket; the merged B-02A scientific-authoring
contract and implementation; A3 registry/LIVE and A4 seeding boundaries; then
the current owner specifications listed by the ticket. This contract
reconciles the current sources as follows:

| Source or question | Disposition in B-03 |
|---|---|
| B-02A authoring objects, refs, canonical bytes, graph validation, dispositions, censoring, replacement accounting, and disclosure | `KEEP + WRAP`; B-03 constructs and verifies exact owner values and defines no parallel case identity or projection authority |
| A3 fixture-origin and LIVE gate | `KEEP + WRAP`; every Burgers artifact remains structurally fixture-derived and therefore cannot pass LIVE |
| A4 seed context, domain, role, provider, derivation, and leakage boundary | `KEEP + WRAP`; A4 remains the sole entropy owner and B-03 never exposes a public raw-seed interface |
| `Generator_Creation.md` v5.1 and `Generator_Validation.md` v2.1 proposals | `DOCUMENTATION_LAG`; useful topology and test intent, but their unratified numerical ranges, constants, tolerances, and scientific claims are not selected |
| MQ-002 — challenge-instance distribution | `NEW_OWNER_DECISION_REQUIRED / EVIDENCE_REQUIRED`; preserve exact external primary/selection/plan refs (official P/Q/w when applicable) and fixture-only materialization; no target law, range, or adequacy claim |
| MQ-003 — generator qualification | `NEW_OWNER_DECISION_REQUIRED / EVIDENCE_REQUIRED`; expose fact-only conformance seams and fail closed; no threshold, qualification claim, or promotion |

`MQ-002` and `MQ-003` are `DEFERRED_FAIL_CLOSED`, not answered by this
contract. The missing human values stop only production or scientific
behavior. They do not prevent a nominal fixture-only generator from being
implemented and tested.

## 2. Ownership and dependency direction

The implementation is one standard-library-only package:

```text
carbon.registry identity/digest primitives ─┐
carbon.authoring case/ref/graph contracts ──┼─> carbon.generators
carbon.seeding fixture-only A4 APIs ────────┘       └─> carbon.generators.burgers
```

`carbon.generators` may import exact internal producer seams from
`carbon.authoring.cases` and `carbon.authoring.refs` because it is a trusted
case producer. That use must not widen `carbon.authoring.__init__`; protected
case identity and fixture capabilities remain absent from convenience exports.
The generator package may use registry `ChallengeKey` and digest validation,
but it must not import registry stores, lifecycle gates, qualification
manifests, `ChallengeRecord`, or LIVE activation.

No upstream package may reverse-import `carbon.generators`. The package may
not import scoring, construction, resource policy, reference runners,
measurement, dossier, evaluation, TrainEval, research service, MCP, chain,
network, filesystem, process, dynamic import, optional numerical, or legacy
runtime packages. It must not revive `carbon.challenges`, `carbon.data`,
`carbon.physics`, `poc`, or archived code. Future B-04/B-05/B-06/B-07S code
consumes this package prospectively; B-03 does not create placeholders for it.

## 3. Reused exact authoring identities

B-03 consumes the following exact B-02A values and their owner-issued refs:

- `ChallengeKey`;
- `PhysicalSystemSpec` / `PhysicalSystemSpecRef`;
- `CandidateOutputContract` / `CandidateOutputContractRef`;
- `InstanceDistributionContract` / `InstanceDistributionContractRef`;
- `SamplingPlan` / `SamplingPlanRef`;
- `SamplingRole` and the plan's exact allowed-consumer role;
- `CanonicalChallengeCase` / `CanonicalChallengeCaseRef`;
- `CaseSourceBinding(GENERATED, GeneratedCaseSource(...))`;
- B-02A replacement, disposition, censoring, graph-validation, fixture-origin,
  and public-projection values where applicable; and
- the existing B-02A owner-ref kinds `generator`, `generation_event`,
  `generation_failure`, `distribution_conformance`, `case_source`,
  `protected_case_payload`, `protected_intended_slot`,
  `protected_intended_evidence_unit`, `protected_attempt_commitment`,
  `protected_replacement_lineage`,
  `fixture_registration`, `provenance`, and audit/accounting kinds.

B-03 defines no new `GeneratorRef`, no generic ref, no second
`CanonicalChallengeCase`, no case canonicalizer, no authored-object history,
and no self-issued `CaseProjectionAuthority`. A generator identity is the
existing exact `generator` owner ref whose scope, object id, object version,
and digest are verified against the full B-03 generator descriptor. A
generation event is the existing exact `generation_event` owner ref computed
from the complete event record below.

A content-addressed ref proves bytes, not that an authorized operation emitted
those bytes. Every B-03 service verifies exact object/ref pairs and recomputes
the generator descriptor, payload, event, result, and case ref from their full
dependencies. A digest-valid caller fabrication is not provenance.

All canonical-record B-03 refs are distinct exact Challenge-bound dataclasses,
never one generic ref. Each carries its literal record type, schema version `1.0`,
canonical profile `carbon_generator_runtime_canonical_v1`, copied
`ChallengeKey`, and tagged content digest of the corresponding fully framed
canonical record. The closed set is:

| Exact ref | Record type |
|---|---|
| `GeneratorEnvironmentRef` | `generator_environment` |
| `BurgersFixtureConfigurationRef` | `burgers_fixture_configuration` |
| `GeneratorRequestRef` | `generator_request` |
| `IntendedUnitLinkDecisionRef` | `intended_unit_link_decision` |
| `SupportExclusionDecisionRef` | `support_exclusion_decision` |
| `CensoringVerdictRef` | `generator_censoring_verdict` |
| `CensoringDecisionRef` | `generator_censoring_decision` |
| `AttemptAccountingDirectiveRef` | `attempt_accounting_directive` |
| `AttemptAccountingDecisionRef` | `attempt_accounting_decision` |
| `GeneratorFailureReasonRef` | `generator_failure_reason` |
| `GeneratorFailureOccurrenceRef` | `generator_failure_occurrence` |
| `PendingGenerationAttemptRef` | `pending_generation_attempt` (protected; nonterminal orchestration record) |
| `GeneratorResultRef` | `generator_result` |
| `GenerationAttemptRecordRef` | `generation_attempt_record` |
| `IntendedUnitAccountingRef` | `intended_unit_accounting` |
| `GenerationAccountingSummaryRef` | `generation_accounting_summary` |
| `GeneratorConformanceFactsRef` | `generator_conformance_facts` |
| `PhysicalPayloadFingerprintRef` | `physical_payload_fingerprint` (protected; attempt-independent) |
| `FixtureReplayProbeRef` | `fixture_replay_probe` (protected; non-accounting) |
| `DeterministicReplayComparisonRef` | `deterministic_replay_comparison` (post-result fixture fact) |
| `ComparisonCorpusDecisionRef` | `comparison_corpus_decision` (post-result protected input) |
| `DuplicateConformanceFactsRef` | `duplicate_conformance_facts` (post-result fact) |
| `ExternalDistributionFactSetRef` | `external_distribution_fact_set` |

`GeneratorReplayCommitmentRef` is a deliberate protected exception, not a ref
to a B-03 canonical record. It is a distinct frozen/slotted nominal capability-
issued value containing exact Challenge scope, replay-scheme id/version, exact
B-02A `authority_evidence` issuer ref, and one opaque tagged commitment digest.
Before request construction, `FixtureGenerationAuthority.reserve_replay`
issues it without acquiring a provider/context, selecting a draw, or consuming
entropy. It is only a protected reservation identity at that point and does not
claim to precommit an A4 context. After admission, the grant operation
atomically binds that reservation in its private insert-only issuance record to
the acquired A4 projection/draw and exact execution commitments. B-03 validates
the ref's exact type, field grammar, Challenge, reservation issuer, and later
grant echo but cannot recompute the opaque commitment or private association.
It is not interchangeable
with attempt, slot, evidence-unit, lineage, or any B-02A owner ref.

Where B-02A requires one of its existing owner refs, B-03 calls the exact
B-02A `owner_ref` constructor with `ChallengeScope(challenge_key)`, the literal
mapping below, and the tagged digest of the complete named record. Object ids
and versions are identity fields, not caller-selected aliases:

| B-02A owner kind | Exact object id | Object version | Digest preimage |
|---|---|---|---|
| `generator` | descriptor `generator_id` | descriptor `generator_version` | full `GeneratorDescriptor` bytes |
| `generation_event` | exact protected `attempt_ref.object_id` | exact `attempt_ref.object_version` | full `GenerationSourceEvent` bytes |
| `case_source` | exact protected `attempt_ref.object_id` | exact `attempt_ref.object_version` | exact event ref + generator ref |
| `protected_case_payload` | exact protected `attempt_ref.object_id` | exact `attempt_ref.object_version` | full protected payload bytes |
| `generation_failure` | stable registered nonconformance `GeneratorFailureReason.reason_id` | stable reason version | full prospective nonconformance `GeneratorFailureReason` bytes |
| `replacement_eligible_generation_failure_reason` | exact alias pin of the preceding nonconformance `generation_failure` ref | exact alias version | exact same stable reason bytes/digest; nominal kind alone differs |
| `generation_failure_accounting` | exact protected `attempt_ref.object_id` | exact `attempt_ref.object_version` | exact `GenerationAttemptRecord` bytes for the failed attempt |
| `distribution_conformance` | exact protected `attempt_ref.object_id` | exact `attempt_ref.object_version` | exact `GeneratorConformanceFacts` bytes |

The externally issued protected attempt commitment therefore supplies the
unique logical id/version for every attempt-scoped owner pin except the
prospectively registered stable failure-reason aliases. Admission
requires its exact kind/scope and rejects reuse of a predecessor's exact
attempt ref. Different attempts cannot create varying digests under one
constant logical id/version; no process-local uniqueness store is invented.

Each stable `GENERATOR_NONCONFORMANCE` reason is supplied and verified with
both exact B-02A owner-ref aliases above. Their scope, object id, object version,
and content digest are pin-equal while their nominal owner kinds remain
distinct. A SamplingPlan replacement trigger can therefore prospectively pin
the `replacement_eligible_generation_failure_reason` alias, and the eventual
`GenerationFailurePayload.failure_evidence_ref` uses the pin-equal
`generation_failure` alias. Stable invalid-construction and infrastructure
reasons instead carry two exact NOT_APPLICABLE alias bindings with a pre-issued
B-02A `applicability_reason` ref because they create no B-02A generation-
failure state or successor. Per-attempt request/event/stage facts never enter
a future-independent alias pin. Exact nested `GeneratorFailureCatalogEntry`
contains, in fixed order, the reason/ref,
`generation_failure_alias_binding`,
`replacement_eligible_generation_failure_alias_binding`, and a pre-issued
occurrence-evidence fallback (`audit_evidence` for nonconformance/invalid and
`infrastructure_failure` for infrastructure), so an exception or non-echo path
can construct its occurrence without asking the failed authority for another
value. Both alias bindings are BOUND to the two pin-equal owner refs exactly
for nonconformance and are exact NOT_APPLICABLE with the entry's pre-issued
alias-inapplicability reason for invalid/infrastructure. The entry has no
standalone ref and canonicalizes only inside request identity.

External B-02A authorities remain responsible for membership,
applicability, exclusion, censoring, policy, replacement, denominator, audit,
and restriction owner refs. Every B-03 result returns each B-03-owned record
with its exact ref; no store or resolver is assumed.

## 4. Exact B-03 value set

All public data values are exact-type, frozen, slotted, immutable, and reject
subclasses. Strings use the existing canonical identifier/version grammar;
integers reject Boolean substitution and use explicit bounds; floating-point
facts are finite Float64 values and are never compared to a B-03-owned
scientific tolerance. Tuples are exact tuples with declared ordering and
duplicate rules.

### 4.1 `GeneratorDescriptor`

The descriptor is the canonical meaning behind the reused `generator` owner
ref:

| Field | Exact meaning |
|---|---|
| `challenge_key` | exact Challenge scope |
| `generator_id` | canonical stable implementation family id |
| `generator_version` | exact prospective version token |
| `implementation_digest` | exact content digest of the non-self-referential `GeneratorImplementationManifest` below |
| `environment_ref` | exact B-03 `GeneratorEnvironmentRef`; fixture environment only in B-03 |
| `fixture_registration_ref` | exact B-02A owner ref of kind `fixture_registration`; mandatory in B-03 |
| `source_provenance_refs` | exact nonempty canonical tuple of B-02A owner refs of kind `provenance` |
| `fixture_configuration_ref` | exact B-03 `BurgersFixtureConfigurationRef`; no caller-selected configuration |
| `supported_physical_system_ref` | exact B-02A physical-system ref |
| `supported_candidate_output_ref` | exact B-02A candidate-output ref |
| `supported_primary_population_ref` | exact B-02A primary-population ref; a binding, not an adequacy claim |
| `supported_selection_population_ref` | exact B-02A executable selection-population ref; distinct when the plan says so |

`generator_ref(descriptor)` computes the reused B-02A `generator` owner ref.
The descriptor contains no mutable alias, latest lookup, production flag,
qualification flag, LIVE flag, or authority-by-name.

`GeneratorEnvironmentDescriptor` and `GeneratorEnvironmentRef` are distinct
B-03-owned, Challenge-bound exact types. The descriptor contains an exact
canonical environment id/version, Python implementation/version, platform
tag, dependency-lock digest, and structural `FIXTURE_ONLY` environment class.
Its ref is a domain-separated tagged content digest of those full fields. B-03
ships no production environment variant, performs no environment discovery at
request time, and never treats a caller string or the native host as a
qualified environment.

The exact service-owned `GeneratorImplementationManifest` contains only
`implementation_id="carbon_generators_burgers_fixture"`,
`implementation_version="1.0"`, `package="carbon.generators.burgers"`,
`runtime_contract_version="0.1"`,
`canonical_profile="carbon_generator_runtime_canonical_v1"`, the exact
`BurgersFixtureConfigurationRef`, and
`latent_codec_id="carbon.b03.burgers.fixture-latent.v1"`. Its canonical bytes
exclude every digest/ref derived from the manifest itself and are framed with
`carbon.generator.implementation-manifest.v1\0` before tagged SHA-256. The
result is `implementation_digest` and exactly equals A4
`SeedPin.generator_digest`. This is a semantic implementation identity, not a
source-code attestation or claim that arbitrary local files were reviewed.
Changing any listed semantic input requires a new manifest/version and cannot
mutate the old digest.

### 4.2 `ResolvedGeneratorAuthoringBundle`

The exact immutable bundle supplies the complete loaded B-02A graph needed by
the generator rather than collapsing primary and selection populations into
one distribution:

| Field | Exact meaning |
|---|---|
| `physical_system` / `physical_system_ref` | exact B-02A object/ref pair |
| `candidate_output` / `candidate_output_ref` | exact B-02A object/ref pair |
| `primary_population` / `primary_population_ref` | exact primary object/ref pair; this is the case's primary population |
| `selection_population` / `selection_population_ref` | exact selection object/ref pair from which the intended generation unit is selected |
| `sampling_plan` / `sampling_plan_ref` | exact B-02A object/ref pair |
| `resolved_dependencies` | exact canonically ordered ref/object pairs for every transitive target, official-proposal, evidence-weight, query, observation, related-population, training-support, and other B-02A top-level dependency required by the four anchors and plan |
| `loaded_dependencies` | the same exact dependencies as B-02A `LoadedAuthoringArtifact` values with independently verified bytes, refs, and origins, for later graph-origin composition |

Every pair exact-recomputes with `.to_ref()`. Each loaded artifact's
`expected_ref`, `recomputed_ref`, and `authored_object` must exact-equal the
corresponding resolved ref/object pair, and the loaded tuple must equal the
case's complete dependency-ref closure. The tuple rejects duplicate refs,
wrong nominal pairs, missing and extra unresolved dependencies, cross-
Challenge values, and entries unreachable from the anchor graph. Its
`objects_by_ref()` projection is passed unchanged to
`validate_loaded_authoring_graph`. The plan's `primary_population_ref` and
`selection_population_ref` must equal those exact objects. A generated case
binds the primary population; the protected intended-unit and material
derivation bind the selection population. For `OFFICIAL_EVALUATION` only,
B-02A additionally proves the exact P/Q/w design semantics. Equality of
primary and selection is allowed only when the exact SamplingPlan says they
are the same object.

### 4.3 `GenerationRoleBinding`

There is no new free-form role. The binding contains:

| Field | Exact meaning |
|---|---|
| `sampling_role` | exact B-02A `SamplingRole` |
| `seed_domain` | exact A4 `SeedDomain` selected by the closed table below |
| `role_key` | exact A4 `RoleKey`, fixed by implementation for that pair rather than supplied as an arbitrary caller label |
| `sampling_plan_ref` | exact B-02A plan ref whose resolved plan authorizes the sampling role |

The only B-03 fixture mappings are:

| B-02A `SamplingRole` | A4 fixture domain | B-03 role-key meaning |
|---|---|---|
| `OFFICIAL_EVALUATION` | `OFFICIAL_EVAL` | `RoleKey("generator_sampling")` |
| `STRESS` | `OFFICIAL_STRESS` | `RoleKey("generator_sampling")` |
| `PRACTICE` | `OFFICIAL_TRAIN` | `RoleKey("generator_sampling")` |

The last mapping does not equate authoring practice evidence with official
training evidence; it only selects A4's segregated non-evaluation entropy
domain for a fixture practice generator. The event records both nominal roles.
`PRODUCT_QUALIFICATION`, `VERIFICATION`, and `EVIDENCE_CAMPAIGN` remain typed
unavailable in B-03. Unknown combinations fail before entropy derivation. A
caller label, Boolean, or `TRAIN` alias cannot choose or upgrade a role.

### 4.4 `GeneratorRequest`

The internal service request has this exact field inventory:

| Field | Exact meaning |
|---|---|
| `challenge_key` | exact scope shared by every bound object |
| `authoring_bundle` | exact complete primary/selection/plan/dependency bundle from section 4.2 |
| `generator` / `generator_ref` | exact B-03 descriptor/reused owner-ref pair |
| `environment` / `environment_ref` | exact B-03 environment object/ref pair |
| `fixture_configuration` / `fixture_configuration_ref` | exact B-03 fixed fixture object/ref pair |
| `role_binding` | exact closed role/domain/plan binding |
| `replay_ref` | exact capability-issued B-03 `GeneratorReplayCommitmentRef`, not raw random material, a canonical-record ref, or a B-03-recomputed draw digest |
| `intended_slot_ref` | exact B-02A owner ref of kind `protected_intended_slot` for the case |
| `intended_evidence_unit_ref` | exact B-02A owner ref of kind `protected_intended_evidence_unit` for disposition/accounting |
| `intended_unit_link_decision` / `intended_unit_link_decision_ref` | exact echoing object/ref pair from `IntendedUnitLinkAuthority` |
| `attempt_ref` | exact B-02A owner ref of kind `protected_attempt_commitment` for this one invocation |
| `attempt_ordinal` | protected exact UInt64 ordinal for audit ordering; never public |
| `current_attempt_predecessor_binding` | exact optional prior `PendingGenerationAttempt`/`PendingGenerationAttemptRef` pair when this invocation is the authorized successor; a finalized attempt cannot authorize a later successor and no resolver/store is assumed |
| `current_attempt_lineage_binding` | exact optional B-02A owner ref of kind `protected_replacement_lineage`, required with a predecessor and absent otherwise |
| `attempt_accounting_fallback` | exact pre-issued B-02A owner refs of kinds `infrastructure_failure` and `applicability_reason` for accounting-authority failure and denominator-unavailability, sufficient to construct the closed unavailable decision without calling another authority |
| `attempt_accounting_applicability_reasons` | exact closed tuple of seven distinct pre-issued B-02A `applicability_reason` refs keyed only as `OUTCOME_REPLACEMENT_INAPPLICABLE`, `REPLACEMENT_TRIGGER_INAPPLICABLE`, `REPLACEMENT_LINEAGE_NOT_EXECUTED`, `SUCCESSOR_AUTHORIZATION_INAPPLICABLE`, `SUCCESSOR_EXECUTION_INAPPLICABLE`, `DENOMINATOR_EFFECT_INAPPLICABLE`, and `PENDING_ATTEMPT_INAPPLICABLE`; every direct/B-03-only/pending-record N/A binding uses its named ref |
| `result_applicability_reasons` | exact closed tuple of eight distinct pre-issued B-02A `applicability_reason` refs keyed only as `RESULT_CASE_INAPPLICABLE`, `CONSTRUCTED_CASE_INAPPLICABLE`, `SUPPORT_DECISION_INAPPLICABLE`, `CENSORING_VERDICT_INAPPLICABLE`, `CENSORING_DECISION_INAPPLICABLE`, `DISPOSITION_INAPPLICABLE`, `TERMINAL_REASON_INAPPLICABLE`, and `FAILURE_BINDING_INAPPLICABLE`; the last is used by pending and final attempt records and no result/attempt N/A value invents a ref |
| `conformance_fallbacks` | exact closed tuple of pre-issued B-02A `applicability_reason` refs keyed by every section 9 field/source-stage applicability pair plus exact `infrastructure_failure` refs for its authority-unavailable paths; no open strings/map/defaults |
| `source_payload_inapplicable_reason_ref` | exact pre-issued B-02A `applicability_reason` ref used only by the source event's payload binding for `NOT_ATTEMPTED` / `NO_PAYLOAD` |
| `failure_reason_catalog` | exact nonempty closed tuple of `GeneratorFailureCatalogEntry` values covering every permitted failure outcome/stage; each entry binds one stable `GeneratorFailureReason`/ref, each nonconformance reason has pin-equal B-02A `generation_failure` / `replacement_eligible_generation_failure_reason` aliases, invalid/infrastructure reasons have two exact NOT_APPLICABLE alias bindings with their `applicability_reason` ref, and every entry includes the exact pre-issued occurrence-evidence fallback defined in section 3 |
| `disposition_construction` | exact evidence-scope, policy-authority, audit, restriction, and disclosure bindings plus distinct B-02A `applicability_reason` owner refs for case-inapplicable and attempt-inapplicable bindings, sufficient to construct every mapped B-02A disposition without defaults |
| `case_construction` | exact complete `CaseConstructionBinding` from section 4.5 |
| `fixture_loading` | exact `FixtureLoadingBinding` for the B-02A loader/composition calls |

`GeneratorRequestIdentity` is the only canonical projection of the protected
request. It contains the Challenge; physical/candidate/primary/selection/plan
refs; canonical dependency refs; for each loaded dependency its expected and
recomputed refs, closed origin tag, origin-evidence/source-provenance/audit
refs, and qualification-applicability binding; generator/environment/
configuration refs; role; replay/slot/evidence-unit/link-decision/attempt refs
and ordinal; current pending-predecessor ref/lineage, accounting fallback,
closed accounting-applicability reasons, and closed result/attempt-
applicability reasons;
conformance-fallback, source-payload-inapplicability, and stable failure-catalog
bindings; and exact construction,
disposition, and fixture-loading values. It contains no authored-object bytes,
loaded object, provider, capability, origin object, context, draw, seed, or raw
protected value. `GeneratorRequestRef` hashes this exact projection. The
service reconstructs it from the complete request and rejects any mismatch;
there is no caller-supplied identity projection without the full dependencies.

The request is not a public wire envelope. Its protected commitments are
opaque owner refs whose underlying slot, draw, stratum, mixture, and replay
inputs remain held by their owning services. The request accepts neither raw
bytes nor `DerivedSeed`, Python callbacks, arbitrary predicates, ambient RNG,
filesystem state, time, process state, environment variables, or network
state.

The service call separately receives one noncanonical, nonserializable
`FixtureGenerationAuthority`. That nominal internal authority returns an exact
`FixtureGenerationGrant` containing the request echo, exact B-02A
`FixtureAuthoringCapability`, issued `FixtureOrigin`, exact A4
`FixtureOfficialContext`, and a protected UInt64 draw index. The authority's
post-admission private issuance record atomically binds the request's reserved
`replay_ref` to A4's
exact value-only `FixtureOfficialExamProjection` and `ExamCommitment`, role/
domain/`RoleKey`, protected draw index, generator/environment/configuration
refs, intended slot/evidence-unit refs, attempt ref/ordinal, and
current pending-predecessor/lineage refs. The same authority-private entry also
retains a noncanonical, nonserializable, single-probe
`FixtureReplayDerivationCapability` over the exact `FixtureOfficialContext`
and draw until the one probe consumes it or the private authority discards its
entry. There is no clock, caller retention setting, or durability claim; an
absent entry makes replay evidence unavailable without changing generation.
The capability is never a request/event/result/case field or
reachable from a returned graph; the value-only projection alone is not
claimed to reconstruct the context. The private replay issuance deliberately
omits `intended_unit_link_decision_ref`; that later decision echoes the already
issued replay commitment, and `GeneratorRequestRef` binds both without a
cycle. B-03 validates the replay ref's exact kind,
Challenge scope, and request echo but does not recompute its opaque externally
owned preimage or re-encode SeedPin, evaluation-binding, or draw material. Only
the trusted adapter may read the draw and call A4. The grant, context, raw draw,
and private issuance record are noncanonical,
nonserializable, redacted, and never request/event/result/case/public fields.
The authority must exact-echo the request and descriptor fixture registration/
source provenance. A stale, forged, subclassed, partial, exception, or
non-echoing grant becomes `INFRASTRUCTURE_FAILURE` after admission without
leaking inputs. Separating execution authority from immutable request meaning
prevents provider/context/draw objects from becoming persisted identity or
surviving in a returned graph.

An exact nominal `IntendedUnitLinkAuthority` separately verifies that
`intended_slot_ref` and `intended_evidence_unit_ref` are the two distinct
owner-kind views authorized for the same exact plan selection. Its request
and `IntendedUnitLinkDecision` must exact-echo the Challenge, plan, selection
population, role, replay, slot, evidence unit, and attempt. The decision also
contains one exact externally owned B-02A `authority_evidence` link-evidence
ref. Its exact B-03 ref is
recomputed before admission. No equality or common digest is inferred across
the two nominal ref kinds.

`FixtureLoadingBinding` contains exact B-02A owner refs
`origin_evidence_ref` (`authoring_origin_evidence`), a nonempty canonical
`audit_evidence_refs` tuple (`audit_evidence`), and
`composition_audit_ref` (`origin_composition_audit`), plus exact
`fixture_unqualified_reason_ref` (`applicability_reason`). Its qualification
evidence is service-fixed
`ApplicabilityBinding.not_applicable(fixture_unqualified_reason_ref)` and
cannot be made bound for this fixture. The source-provenance tuple exact-echoes the
descriptor; the `FixtureOrigin` itself is issued only in the execution grant.
These values supply every required `load_authoring_bytes` and
`compose_authoring_graph_origin` argument without caller defaults or a
registered-origin authority.

Before any derivation, the service exact-recomputes every supplied ref; checks
Challenge equality; checks the full loaded B-02A graph using
`validate_loaded_authoring_graph`; proves primary/selection and, for official
evaluation, exact P/Q/w,
SamplingPlan, selection-law, role, query/observation/campaign, intended-slot,
and prospective-censoring bindings; verifies
`SeedPin.challenge_key == descriptor.challenge_key`,
`SeedPin.generator_version == descriptor.generator_version`, and
`SeedPin.generator_digest == descriptor.implementation_digest` (the full
descriptor's `generator_ref.content_digest` is a different digest); verifies
the descriptor's supported physical-system, candidate-output, primary-
population, and selection-population refs respectively equal the exact four
authoring-bundle refs; verifies the request environment and fixture-
configuration refs respectively equal the descriptor's environment and
fixture-configuration refs; verifies the intended-unit link decision; exact-
recomputes the optional pending-predecessor record/ref pair; requires its
`PENDING_SUCCESSOR` accounting directive to carry a bound
`SuccessorAuthorization` whose exact successor attempt ref is the current
`attempt_ref`, whose lineage ref equals the current lineage, and whose
successor ordinal equals the current `attempt_ordinal` before any provider/A4
work;
requires exact equality of predecessor and
current Challenge, plan, primary, selection, intended-slot, intended-evidence-
unit, role, generator, environment, and fixture-configuration identities;
requires the current ordinal to be greater; and rejects reuse of the
predecessor attempt ref; verifies every stable failure reason/ref/alias-
applicability binding and accepts pin-equal prospective generation-failure
triggers only for `GENERATOR_NONCONFORMANCE` reasons in the exact plan;
verifies the role table; and verifies structural fixture capability and origin. The
pre-materialization validation verifies the physical/candidate/distribution/
plan subgraph and every construction binding; the complete
`validate_loaded_authoring_graph` proof runs after the exact case exists.

### 4.5 `CaseConstructionBinding`

This immutable exact value supplies every variable B-02A case field that is not
the computed source or computed payload. The service fixes and exact-validates
`object_kind="canonical_challenge_case"`,
`schema_version=AUTHORING_SCHEMA_VERSION`, and
`canonicalization_profile=CANONICALIZATION_PROFILE`; those literals are not
caller fields or inferred defaults.

| Field | Exact meaning |
|---|---|
| `object_id`, `object_version`, `supersedes` | exact prospective B-02A case identity metadata |
| `related_population_bindings` | exact B-02A canonical tuple |
| `case_representation_ref` | exact B-02A owner ref of kind `representation` |
| `query_population_binding` / `observation_population_binding` | exact B-02A applicability bindings |
| `evidence_campaign_binding` | exact B-02A applicability binding |
| `intended_slot_binding` | exact B-02A applicability binding which must exact-echo the request's `intended_slot_ref` |
| `prospective_censoring_policy_binding` | exact B-02A applicability binding resolved from the SamplingPlan |
| `applicability_bindings` | exact canonical B-02A tuple |
| `disclosure_class` / `disclosure_contract` | exact B-02A protected disclosure values; no B-03 widening |
| `case_provenance_refs` | exact canonical tuple containing only B-02A owner refs of kind `provenance`; it must include all descriptor `source_provenance_refs` |

The service does not infer, default, or normalize any variable field. It checks
the binding against the full physical/candidate/primary/selection/plan graph and the
request's Challenge, role, intended slot, intended evidence unit, source
provenance, and censoring policy before materialization. `FixtureOrigin` and
its `fixture_registration_ref` are loader metadata, not case-provenance
entries. Production-unavailable fields cannot be replaced with sentinel
strings inside an otherwise complete case.

### 4.6 `GenerationSourceEvent`

The canonical source event is the acyclic protected identity behind the reused
`generation_event` owner ref. It is computed exactly once after admission: at
the construction-compatibility failure point with `NOT_ATTEMPTED`, or after
execution begins with `PAYLOAD_AVAILABLE`/`NO_PAYLOAD`. `NO_PAYLOAD` covers a
context, derivation, or materialization path that yielded no conforming payload
and does not assert that a materializer was invoked. The event is always
computed before support, case, censoring, duplicate, or terminal-result
decisions:

| Field | Exact meaning |
|---|---|
| `challenge_key` | exact scope |
| `request_ref` | exact B-03 `GeneratorRequestRef`, computed from all immutable request fields and protected commitments but no execution capability |
| authoring refs | physical system, candidate output, primary population, selection population, and SamplingPlan refs |
| `generator_ref` | exact descriptor identity |
| `environment_ref` | exact environment identity echoed from descriptor |
| `fixture_configuration_ref` | exact fixed configuration identity |
| `role_binding` | both B-02A role and A4 fixture domain/key |
| `fixture_registration_ref` / `source_provenance_refs` | exact structural non-production provenance echoes |
| `replay_ref` | protected replay commitment |
| `intended_slot_ref` / `intended_evidence_unit_ref` | distinct protected case-slot and accounting-unit identities |
| `attempt_ref` | protected attempt identity |
| `payload_ref_binding` | exact protected payload ref when materialization reaches a payload; otherwise exact NOT_APPLICABLE with the request's `source_payload_inapplicable_reason_ref` |
| `materialization_state` | exact `NOT_ATTEMPTED`, `PAYLOAD_AVAILABLE`, or `NO_PAYLOAD` source-stage fact; the latter means admitted execution yielded no conforming payload, not that any particular provider/materializer call occurred |

The source event contains no support, exclusion, censoring, duplicate,
terminal outcome, terminal reason, replacement decision, or result ref. It is
therefore constructible without a cycle. It is canonical even when no case
exists and binds the role, replay, attempt, distinct intended identities,
configuration, and fixture registration that `CanonicalChallengeCase` does
not carry explicitly. Its exact ref is used in `GeneratedCaseSource`;
protected event bytes and refs are never in the public projection. Terminal
decisions and replacement accounting live only in `GeneratorResult` and the
records in section 8.

### 4.7 Fixed Burgers fixture payload and artifact

`BurgersFixtureConfiguration` and
`BurgersFixtureConfigurationRef` are exact B-03-owned fixture-only types. The
only v1 configuration is service-constructed and has these exact, conspicuous
values:

| Field | Exact fixture value |
|---|---|
| `configuration_id` / `configuration_version` | `b03_burgers_structural_fixture` / `1.0` |
| `boundary_shape` | `PERIODIC_1D` |
| `period` / `grid_points` | finite Float64 `1.0` / UInt64 `8` |
| `viscosity` | finite Float64 `1.0`, mechanical fixture value only |
| `latent_codec_id` | `carbon.b03.burgers.fixture-latent.v1` |
| `basis_1` | exact integer tuple `(0, 1, 1, 0, -1, -1, 0, 0)` |
| `basis_2` | exact integer tuple `(1, 1, 0, -1, -1, 0, 1, 0)` |

The object/ref pair is bound into descriptor, request, and source event and
must equal the module's exact v1 value. It has no public constructor that can
change a field and no fixture-to-production flag.

The private sampler obtains one 32-byte copy through A4's exact
`DerivedSeed.as_backend_bytes()` API, reads the first two unsigned 64-bit
big-endian words `w1` and `w2`, computes exact integers
`n1=(w1 mod 2001)-1000` and `n2=(w2 mod 2001)-1000`, and emits the eight finite
Float64 values
`u[i]=(n1*basis_1[i] + n2*basis_2[i]) / 4096.0`. These power-of-two rational
values are exactly representable as Float64. The remaining material and the
ephemeral byte copy are dropped before return. The protected payload contains
only configuration ref, period, grid count, viscosity, and the eight initial
values; it contains no seed, word, coefficient, draw, slot, stratum, replay,
reference, or candidate output. The service exact-computes the B-02A owner ref
of kind `protected_case_payload` from that payload.

`BurgersProductionInputsUnavailable` is a frozen/slotted exact separate non-
case report with this fixed field order: `primary_population_law`,
`selection_population_law`, `selection_density_or_mass`,
`importance_weight`, `viscosity`, `parameter_ranges`, `forcing_law`,
`initial_condition_law`, `grid_specification`, `horizon_specification`,
`stratification`, `exclusions`, `conformance_estimands`,
`conformance_thresholds`, and `qualification_evidence`. Every field is the
closed nominal value `ProductionInputAvailability.HUMAN_INPUT_REQUIRED`.
There are no optional/extra fields, constructor overrides, dict aliases, or
grouped catch-all values; Boolean/string substitutions reject. The explicit
selection density and weight fields cover official Q/w only when an eventual
exact plan makes them applicable and do not claim that such a plan exists.
Those markers are not in
the configuration, descriptor digest, payload, case, or any apparently
complete production object.

The sampler neither solves the PDE nor produces a reference answer, score,
measurement, truth asset, or candidate output. The service computes and
verifies the exact payload/ref pair before constructing a case. It also
constructs an exact protected `PhysicalPayloadFingerprint`/ref from Challenge,
case-representation ref, fixture-configuration ref, and the tagged digest of
the full protected-payload canonical bytes. The fingerprint intentionally
omits attempt/event/replay identity, is never public, and is valid only under
those exact Challenge/representation/configuration bindings.

After support succeeds, the service may construct exactly one B-02A
`CanonicalChallengeCase` before censoring/accounting terminalization. When
complete graph validation succeeds, that immutable case remains a reached-
milestone protected artifact even if a later required censoring/accounting
authority fails. Its fields are:

- physical, candidate, primary-population, and SamplingPlan refs equal the
  request bundle; the selection population remains separately plan-bound and
  is not substituted for the case primary population;
- `case_source` is `GENERATED` with the recomputed source-event and generator
  refs;
- `physical_payload_ref` is the recomputed protected payload ref;
- intended-slot and prospective-censoring bindings echo the resolved plan and
  protected request commitments;
- `case_provenance_refs` contain only exact source-provenance refs; and
- canonical bytes and ref come only from B-02A `.canonical_bytes()` and
  `.to_ref()`.

The service then calls `load_authoring_bytes` on the exact case bytes with the
authority-issued `FixtureOrigin`, composes that exact loaded root with every
`loaded_dependencies` artifact through `compose_authoring_graph_origin`, and
requires `GraphOriginTag.FIXTURE_DERIVED`. A protected
`GeneratedFixtureArtifact` binds the exact case/ref, loaded case artifact,
complete dependency tuple, and composed graph-origin result. It is carried
internally by every result whose validated-case milestone was reached,
including post-case infrastructure failure, so A3 integration tests inspect
the actual structural origin rather than a caller Boolean. Only valid/censored
bind it as the disposition-facing case; post-case failure keeps it audit-only.
The artifact itself is omitted from the public projection.

The service validates the complete object mapping, including the exact case,
with `validate_loaded_authoring_graph`. It does not reimplement B-02A graph
laws. An admitted construction failure emits no case but does emit the exact
`INVALID_CONSTRUCTION` result/attempt record required by section 7.

## 5. A4 entropy and deterministic replay

A4 remains the only owner of entropy acquisition and derivation. After request
admission, the injected `FixtureGenerationAuthority` acquires the exact
`FixtureOfficialContext` through exact `DeterministicFixtureProvider`; provider
acquisition failure is therefore a reachable `INFRASTRUCTURE_FAILURE`. It also
creates A4's exact value-only `FixtureOfficialExamProjection` and
`ExamCommitment`. Its private issuance record verifies the external replay
commitment against that A4 projection, the closed domain/RoleKey, private draw,
and protected commitments; B-03 neither owns that opaque preimage nor invents
a second serialization of `SeedPin` or `EvaluationBinding` material.

Replay reservation is the sole pre-request authority step. It performs no A4
provider/context/draw work. Malformed, wrong-Challenge, or unissued reservations
fail request admission with zero provider call. Provider acquisition and the
atomic private reservation binding occur only after admission; their failure is
therefore the reachable `INFRASTRUCTURE_FAILURE` path above. A reservation is
never silently rebound to different context/draw commitments. Normal generation
reservations are single-consumption: after one admitted `generate` call marks
the private binding consumed, a second normal call with that reservation is
rejected at admission with no provider/derivation call and no second event,
result, or accounting row under the same attempt identity. The sole permitted
rederivation is the separately authorized audit-only replay probe below; it
uses the existing private binding without resetting or consuming a normal
attempt.

B-03 validates the SeedPin's exact Challenge, generator version, and generator
digest equalities defined in section 4.4. Its scoring and evaluation-binding
fields remain exact opaque A4 domain-separation inputs; B-03 neither knows nor
scientifically or operationally validates their expected values. The trusted
adapter calls `derive_fixture_official_seed` internally and drops all reachable
context/provider/material references before returning.
That reachability guarantee does not erase the separately encapsulated replay
capability held only in the authority's private issuance store. The probe may
consume it once; absence or prior consumption fails the probe closed and cannot
change the baseline result.

The fixture sampler is an internal capability, not a public function that
accepts bytes or a seed. Its material value:

- cannot be constructed through the public B-03 API;
- may be copied exactly once through `DerivedSeed.as_backend_bytes()` into the
  ephemeral private sampler defined in section 4.7, but cannot otherwise be
  serialized, pickled, stringified, represented, or copied by B-03;
- never appears in a request/result/event/case/public projection/error;
- cannot be retained by the returned object graph; and
- is never silently rederived after an attempt terminates.

Deterministic replay means that the same exact verified request commitments,
fixture context pin, role mapping, implementation/environment identity, and
fixture recipe produce byte-identical B-02A case bytes and the same case ref.
It is an engineering property only. It is not population conformance,
scientific validity, truth, independence, unpredictability, security
qualification, or LIVE authority.

## 6. Exact authority echoes

B-02A `SupportContract` and `ExclusionContract` bind rules and authority refs;
they do not execute predicates. B-03 therefore consumes nominal injected
authorities, never raw callbacks or caller Booleans.

### 6.1 Support/exclusion authority

`SupportExclusionRequest` contains the exact `GeneratorRequestRef`, preterminal
`GenerationSourceEvent`/ref, protected payload/ref, Challenge, physical,
candidate, primary population, selection population, SamplingPlan, generator, environment,
configuration, role, replay, intended-slot, intended-evidence-unit, and
attempt identities plus the fact-only fixture payload summary. It contains no
case or terminal result. It is a pre-case assessment after exactly one
materialization. `SupportExclusionDecision` and its exact ref echo that
complete request and use one closed top-level variant. `OWNER_UNAVAILABLE`
contains only that echo and the exact matching `SUPPORT_AUTHORITY` failure-
catalog entry's pre-issued B-02A `infrastructure_failure` fallback, with no
population assessment or pair-resolution claim. `ASSESSED` contains an exact ordered pair of
`PopulationSupportAssessment` values, one with
`SELECTION_MATERIALIZATION` and the exact selection population's own support/
exclusion contracts, and one with `PRIMARY_CASE` and the exact primary
population's own contracts. Even when the refs happen to be equal, the roles
remain nominally separate. Each assessment has one closed decision:

- `WITHIN_REGISTERED_SUPPORT` with the exact population's nested B-02A
  `SupportContract` echo and B-02A owner refs of kinds `membership_evidence`
  and `applicability_evidence`;
- `REGISTERED_EXCLUSION` with exact population, nested `SupportContract` and
  `ExclusionContract` echoes, and B-02A owner refs of kinds
  `exclusion_contract`, `exclusion_assessment`, `screening_design`, and
  `inclusion_probability_accounting`, plus the pin-equal
  `prospective_exclusion_contract` alias required by any B-02A replacement
  trigger;
- `OUTSIDE_REGISTERED_SUPPORT` with exact population/nested-support-contract
  echoes and B-02A `membership_evidence` / `applicability_evidence` failure
  refs, producing
  `GENERATOR_NONCONFORMANCE`; or
- `AUTHORITY_UNAVAILABLE` with the exact population/contracts and a B-02A
  `infrastructure_failure` ref fixed to the same admitted
  `SUPPORT_AUTHORITY` failure-catalog fallback.

The enclosing decision also contains one closed terminal resolution. If both
assessments are within, it must be `WITHIN_REGISTERED_SUPPORT`, with no
effective role or pair-resolution evidence. Otherwise it cannot be within and
must name exactly one non-within assessment as `effective_assessment_role` and
echo that assessment's exact decision kind as the terminal resolution. Every
such mixed or double-non-within pair additionally binds an externally issued
B-02A `policy_authority` resolution-policy ref and `membership_decision`
pair-resolution-evidence ref. Those refs make the external choice among
unavailable, outside, and exclusion assessments explicit; B-03 supplies no
hidden precedence. The selected unavailable assessment becomes infrastructure
failure, outside becomes nonconformance, and exclusion becomes registered
exclusion. For exclusion, the selected assessment's `exclusion_contract` and
pin-equal `prospective_exclusion_contract` aliases must match any replacement
trigger by owner-pin equality. `ValidCasePayload` receives the primary
assessment's applicability/membership refs because the case binds the primary
population. `ExcludedCasePayload` receives exactly the selected assessment's
four exclusion refs. Both population assessments and the pair resolution
remain in conformance facts regardless of terminal resolution.

The service accepts only the exact nominal authority interface and exact
request echo. Stale, cross-Challenge, forged, subclassed, partial, exception,
or non-echoing results deterministically become the top-level
`OWNER_UNAVAILABLE` decision using that admitted fallback, without re-calling
the authority or leaking inputs. A generator-owned
heuristic cannot impersonate registered support or exclusion. A valid
`REGISTERED_EXCLUSION` is prospective and B-03 always maps it to B-02A's
attempt-bound, no-case `EXCLUDED` shape; post-realization exclusion is outside
this ticket. `AUTHORITY_UNAVAILABLE` becomes infrastructure failure.

### 6.2 Near-duplicate authority

Duplicate comparison is a separate post-result operation and never feeds back
into `GeneratorResult`, `GenerationAttemptRecord`, or per-attempt conformance.
`PostResultDuplicateRequest` is an exact fixed-order nested request and contains an exact case-bearing
subject `GeneratorResultRecord`/ref pair, Challenge/representation/
configuration, and two distinct pre-issued B-02A `applicability_reason` refs:
`CORPUS_OWNER_UNAVAILABLE` and `NEAR_DUPLICATE_POLICY_UNAVAILABLE`. The
nonserializable subject wrapper is a transient verification attachment and is
never encoded into this request or any decision. `ComparisonCorpusAuthority`
accepts that exact request and returns exact
`ComparisonCorpusDecision`/`ComparisonCorpusDecisionRef`: either `BOUND` with a
canonical protected tuple of exact case-bearing comparison
`GeneratorResultRecord`/ref pairs and one B-02A `authority_evidence` corpus-
issuance ref, or `OWNER_UNAVAILABLE` with the request's exact
`CORPUS_OWNER_UNAVAILABLE` ref. Complete nonserializable wrappers may be
supplied transiently to verify protected artifacts, but never enter canonical
decision bytes. Stale, cross-Challenge,
non-echoing, exception, duplicate, subject-containing, wrong-representation,
or wrong-configuration corpora fail closed to the unavailable variant.

For a bound corpus, `DuplicateComparisonRequest` contains the exact subject
case ref and `PhysicalPayloadFingerprint`/ref plus each corpus member's exact
case ref and fingerprint/ref, and the exact corpus decision/ref. Complete result
wrappers may be supplied transiently to prove each case/fingerprint pairing,
but no protected payload object or wrapper enters canonical request bytes. B-03
exact-recomputes every nested result/ref and
emits two separate facts: `canonical_case_duplicate` means B-02A case-ref
equality, while `physical_instance_collision` means attempt-independent
`PhysicalPayloadFingerprintRef` equality. Comparing full attempt-scoped
payload owner refs would be incorrect because distinct attempts intentionally
have distinct logical id/version pins even when their canonical payload bytes
match. The fingerprint detects repeated physical material while distinct
replay/attempt source-event refs correctly make complete case refs differ.
Neither fact is semantic nearness or an acceptance verdict.

Near-duplicate meaning is externally owned. `NearDuplicateRequest` exact-
echoes the post-result request and corpus decision, adds exact B-02A owner refs
of kinds `duplicate_rule` and `semantic_equivalence`, and retains the exact
`NEAR_DUPLICATE_POLICY_UNAVAILABLE` fallback. A nominal authority returns an
exact echo plus `DISTINCT`
or `NEAR_DUPLICATE` with the exact `semantic_equivalence` policy ref, B-02A
`evidence_artifact` fact ref, and `audit_evidence` ref; or
`POLICY_UNAVAILABLE` with the requested policy refs and one exact B-02A
`applicability_reason` ref which must equal that admitted fallback. A stale,
cross-Challenge, partial, non-echoing, exception, or wrong-policy response is
converted deterministically to the same fallback without re-calling the failed
authority. The result is a post-case conformance fact only: it is not hashed into the
source event or case and cannot create, destroy, exclude, censor, qualify, or
promote a case. B-03 provides no distance, tolerance, embedding, threshold,
index, corpus, or rejection policy.

`NearDuplicateDecision` is an exact fixed-order nested record containing the
complete `NearDuplicateRequest` echo and exactly one closed variant:
`DISTINCT` or `NEAR_DUPLICATE` carries the exact requested
`semantic_equivalence` ref, one B-02A `evidence_artifact` fact ref, and one
`audit_evidence` ref; `POLICY_UNAVAILABLE` carries both requested policy refs
and exactly the request's `NEAR_DUPLICATE_POLICY_UNAVAILABLE` ref, with no fact
or audit ref. It has no standalone ref and canonicalizes only inside
`DuplicateConformanceFacts`; wrong field combinations reject.

The pure post-result builder returns the corpus decision, exact duplicate
comparison, near-duplicate decision/unavailable binding, and both mechanical
duplicate facts as `DuplicateConformanceFacts`/
`DuplicateConformanceFactsRef`. When the corpus is unavailable it returns the
exact unavailable facts record without a fabricated comparison. This record
is never embedded back into its subject result.

### 6.3 Censoring authority and record finalization

`GeneratorCensoringRequest` contains the exact case/ref pair, source-event/ref,
SamplingPlan object/ref, prospective censoring-policy ref, intended-evidence-
unit ref, B-02A `EvidenceScopeBinding`, and the exact Challenge/primary/
selection/generator/role identities. It deliberately contains no replacement
decision: replacement caused by this still-undecided outcome cannot exist yet.

The exact nominal authority returns a complete request echo plus an exact
`CensoringVerdict`/`CensoringVerdictRef` pair with one closed verdict:

- `NOT_CENSORED`, with no censoring basis;
- `CENSORED`, with an exact immutable `CensoringRecordBasis` containing every
  externally owned B-02A censoring-record field except `replacement_decision`;
  or
- `AUTHORITY_UNAVAILABLE`, with no basis and one exact non-scientific
  B-02A `infrastructure_failure` ref fixed to the admitted
  `CENSORING_AUTHORITY` failure-catalog entry's pre-issued fallback.

The censored basis therefore carries the intended evidence unit, evidence
scope, reason and typed trigger, actor, applicable population, plan,
campaign/query-observation provenance, censoring-accounting and missingness
bindings, audit refs, and downstream restrictions. It cannot carry a
replacement decision, a B-02A `CensoringRecord`, a disposition, or a result.
For B-03 v1 it may use only `EXPERIMENT_CORRUPTED` or
`EVIDENCE_ACQUISITION_INFRASTRUCTURE_TRIGGER`, with the exact primary population
and when the exact plan/scope permits the cause. Although B-02A separately
defines `OBSERVATION_MISSING` and `OBSERVATION_TIMEOUT`, its current complete-
graph law requires a censored disposition's record population to equal the
primary population while its censoring helper requires those two causes to
bind the observation population. B-03 therefore defers both until a prospective
B-02A supersession makes the conjunction implementable. Reference-family
causes remain B-04 and measurement-family causes remain B-05; an authority
returning any deferred family here fails closed.

After section 6.4 has produced a final exact outcome replacement decision,
either directly or by finalizing a pending predecessor after its successor
invocation exists, the pure trusted `finalize_censoring_decision` constructor
accepts the exact request, verdict/ref, and `AttemptAccountingDecision`/ref.
For `CENSORED` it inserts that decision's exact bound B-02A
`ReplacementDecision` into the basis, builds
and exact-recomputes the resulting B-02A `CensoringRecord`/ref, calls
`validate_censoring_against_plan`, and returns an exact
`CensoringDecision`/`CensoringDecisionRef` binding all four pairs. For
`NOT_CENSORED` it returns an exact decision with no record. An unavailable or
invalid verdict produces infrastructure-failure accounting and no censoring
record. The direct order is verdict -> accounting -> record finalization; the
successor path is verdict -> pending attempt -> admitted successor ->
accounting/record finalization. Both are acyclic. Stale, forged, subclassed,
partial, exception, or non-echoing
authority responses deterministically construct that exact unavailable verdict
without re-calling the authority, become `INFRASTRUCTURE_FAILURE`, and expose no case
publicly.

### 6.4 Outcome replacement and denominator authority

Replacement caused by the current terminal outcome is distinct from whether
the current attempt was itself a replacement. `AttemptAccountingRequest`
echoes the admitted request/source event, current predecessor/lineage,
provisional terminal outcome and its already available support-decision,
censoring-verdict, or stable failure-reason/per-attempt-occurrence refs,
optional case ref, exact plan and
replacement policy, and distinct intended identities. It never requires the
not-yet-constructible final censoring decision or record. The external nominal
authority returns an exact `AttemptAccountingDirective`/ref with exactly one
closed variant:

- `FINAL` contains an exact B-02A `ReplacementDecision` for valid, censored,
  excluded, or generator-failure mappings, or the request's exact not-
  applicable `OUTCOME_REPLACEMENT_INAPPLICABLE` reason for B-03-only invalid/
  infrastructure outcomes; an exact NOT_APPLICABLE successor binding using
  `SUCCESSOR_AUTHORIZATION_INAPPLICABLE`; and the closed denominator binding below.
  Its B-02A decision uses exact `REPLACEMENT_TRIGGER_INAPPLICABLE` whenever its
  trigger is unbound, exact `REPLACEMENT_LINEAGE_NOT_EXECUTED` for its unbound
  lineage, and is validated with `executed=False`.
- `PENDING_SUCCESSOR` contains no B-02A `ReplacementDecision` and therefore
  makes no false executed/unexecuted disposition claim. It instead contains
  one exact `SuccessorAuthorization` and the closed denominator binding. This
  variant is permitted only for an exact registered censored, excluded, or
  generation-failure trigger whose policy decision is `PERMITTED` or
  `REQUIRED_BY_POLICY`.
- `OWNER_UNAVAILABLE` contains the request's pre-issued exact accounting-
  authority-failure ref and denominator-unavailable-reason ref, not-applicable
  replacement/successor bindings fixed respectively to
  `OUTCOME_REPLACEMENT_INAPPLICABLE` and
  `SUCCESSOR_AUTHORIZATION_INAPPLICABLE`, the fallback's exact denominator-
  unavailable binding, records the provisional outcome,
  and fixes the final outcome to `INFRASTRUCTURE_FAILURE`.

`SuccessorAuthorization` is a nested exact external decision that echoes the
predecessor request/event/attempt, intended identities, plan, registered
policy ref, exact trigger, policy decision kind, and replacement-accounting
evidence ref. It binds a newly issued exact B-02A
`protected_attempt_commitment` for the successor, a strictly greater successor
ordinal, and one exact `protected_replacement_lineage` ref. It authorizes a
specific successor invocation but does not claim execution and is not itself a
B-02A replacement decision. It can appear only in `PENDING_SUCCESSOR`; all
other variants require the request's exact
`SUCCESSOR_AUTHORIZATION_INAPPLICABLE` reason.

`REQUIRED_BY_POLICY` is permitted only in `PENDING_SUCCESSOR` in B-03 v1; a
`FINAL` directive may contain only `PROHIBITED` or an owner-evidenced
unexecuted `PERMITTED` decision. B-03 does not invent a maximum-attempt or
policy-waiver interpretation that would make a required successor disappear.
If the owner cannot supply the required successor authorization, the exact
owner-unavailable path is used and no B-02A disposition is fabricated.

The denominator binding is not a free authority choice. It is BOUND exactly
when the current B-02A-mapped outcome has a bound trigger under
`ON_REGISTERED_TRIGGERS`, and its value must equal the exact
`RegisteredReplacementPolicy.denominator_effect_ref` embedded in the resolved
SamplingPlan. It is NOT_APPLICABLE, with the request's exact reason ref, for a
`NEVER` policy, a valid/no-trigger decision, and B-03-only invalid or
infrastructure outcomes; that ref is fixed to
`DENOMINATOR_EFFECT_INAPPLICABLE`. `OWNER_UNAVAILABLE` uses only the pre-issued
denominator-unavailable reason. B-03 never substitutes an unrelated owner ref
or invents a denominator Boolean.

The service constructs `OWNER_UNAVAILABLE` deterministically from the admitted
request's fallback binding when the authority raises, is absent after nominal
admission, or returns a stale/forged/non-echoing value. Thus terminalization
never calls the failed authority recursively. The failure reason stage is
`ATTEMPT_ACCOUNTING_AUTHORITY`; the pure fallback selects that exact stable
catalog reason, constructs its occurrence, and constructs conformance facts
with final `INFRASTRUCTURE_FAILURE`/`ATTEMPT_ACCOUNTING_AUTHORITY` while
retaining the actual payload/support/validated-case milestones already reached.
The directive preserves the provisional outcome, but it is not mislabeled as
the final result reason. No successor or B-02A disposition is created.

For `FINAL`, B-03 exact-checks the echo and calls
`validate_replacement_decision(..., executed=False)`. Valid requires a
prohibited/no-trigger decision. Censored, excluded, and generation-failure
triggers, when bound, must match the exact current state and reason. Invalid
construction and infrastructure failure cannot create a successor in v1
because they have no B-02A replacement-state mapping. The pure final path
constructs the exact `AttemptAccountingDecision`/ref, censoring decision when
applicable, final attempt record, B-02A disposition when applicable, and
`GeneratorResult`.

For `PENDING_SUCCESSOR`, the service instead constructs a canonical protected
`PendingGenerationAttemptRecord` and its `PendingGenerationAttemptRef`, then a
nonserializable exact `PendingGenerationAttempt` wrapper. The record contains
the exact Challenge, request ref, source-event/ref pair, provisional six-way outcome/stage,
support/constructed-case/censoring-verdict applicability bindings, a
failure-reason/occurrence binding which is BOUND exactly for pending
`GENERATOR_NONCONFORMANCE` and exact `FAILURE_BINDING_INAPPLICABLE` for pending
`REGISTERED_EXCLUSION`/`CENSORED_CASE`, and the conformance pair reached by this invocation,
and the exact directive/ref. The wrapper contains only that record/ref plus the
`GeneratedFixtureArtifact` exactly when the record's constructed-case binding
is BOUND, and forbids it otherwise; its case/ref must equal that binding. The
artifact is never canonicalized into
the pending ref. Neither record nor wrapper contains a B-02A
`ReplacementDecision`, `CensoringRecord`, final censoring decision,
disposition, `GenerationAttemptRecord`, or `GeneratorResult`. Pending is an
orchestration state around one already terminated invocation, not a seventh
`GeneratorOutcomeKind` and not an evidence/accounting row.

Every unbound pending constructed-case, support, censoring-verdict, and failure
field uses the same exact named request-bound result-applicability ref as the
final record; pending construction has no separate free-form reason namespace.

`AttemptAccountingDecision` / `AttemptAccountingDecisionRef` are final and
contain exactly the Challenge, request/event/attempt/intended identities,
provisional and final outcome/stage, source
`AttemptAccountingDirective`/ref, final outcome-replacement applicability
binding, exact denominator-effect applicability binding, and one closed
`successor_execution_binding`. The binding is either:

- `NOT_APPLICABLE` with the admitted request's exact reason ref for a direct
  final or owner-unavailable path, fixed to
  `SUCCESSOR_EXECUTION_INAPPLICABLE`; or
- `BOUND` with nested exact `SuccessorExecutionEvidence` containing the source
  `SuccessorAuthorization`, the successor's canonical
  `GeneratorRequestIdentity`/ref pair, and exactly one nominal successor output
  pair: its `PendingGenerationAttemptRecord`/ref or `GeneratorResultRecord`/ref.

The finalizer transiently accepts the complete noncanonical successor request,
reconstructs its canonical identity projection/ref, and requires its
predecessor binding to recompute to the pending predecessor. The BOUND variant
then requires exact attempt, ordinal, lineage, Challenge, plan, populations,
intended identities, generator, environment, configuration, and role equality.
The complete request is never a decision field; the final decision codec has
no open mapping, output union, or caller execution flag.

The authorized successor request must bind that exact pending object/ref as
its current predecessor and exact-echo the authorized attempt, ordinal, and
lineage. Once the successor invocation has itself returned either a final
`GeneratorResult`/ref or another exact `PendingGenerationAttempt`/ref, the pure
trusted `finalize_pending_generation_attempt` builder accepts those two exact
invocation outputs plus the complete predecessor and successor requests
transiently. It reconstructs both canonical request identities/refs, requires
the predecessor request/event and every retained pending binding to exact-echo
the pending record, recomputes all refs, and proves the successor request binds
the pending predecessor; proves exact Challenge/plan/population/slot/evidence-
unit/generator/environment/configuration/role continuity; and proves the
authorized attempt, ordinal, and lineage equal the actually admitted successor.
Only then does it construct the predecessor's exact B-02A
`ReplacementDecision` with that lineage BOUND, call
`validate_replacement_decision(..., executed=True)`, construct the final
`AttemptAccountingDecision`/ref and any censoring record/decision and
disposition, and return the predecessor's final `GeneratorResult`/ref. It
accepts no caller `executed` Boolean. A pending predecessor with no exact
admitted successor remains pending and is rejected by final accounting rather
than being relabeled or silently dropped.

A final valid attempt may itself have a pending predecessor: that current-
attempt lineage is recorded separately and is never placed in the valid
attempt's own outcome-caused B-02A replacement decision.

## 7. Closed terminal outcome taxonomy

`GeneratorOutcomeKind` is exactly:

1. `VALID_GENERATED` — exact case/case-ref pair exists and all validations
   passed;
2. `REGISTERED_EXCLUSION` — an exact external authority identified a
   registered prospective exclusion;
3. `GENERATOR_NONCONFORMANCE` — deterministic generator output or its bound
   facts violate the declared generator contract;
4. `INVALID_CONSTRUCTION` — an already admitted exact nominal request either
   failed the separately executed construction-compatibility check before
   source work (`NOT_ATTEMPTED`) or reached payload/case construction but the
   exact generated combination could not construct or graph-validate a B-02A
   case;
5. `CENSORED_CASE` — a prospective censoring policy produced an exact
   censoring record;
6. `INFRASTRUCTURE_FAILURE` — fixture provider, entropy acquisition,
   materialization, or required authority infrastructure failed without a
   registered exclusion or scientific conclusion.

Reference failure is not a B-03 outcome and remains B-04 scope. No outcome
value has an `UNKNOWN`, caller string, success Boolean, official flag,
production flag, qualified flag, or LIVE flag.

`GeneratorTerminalStage` is also closed. The exact outcome/stage/terminal-
reason matrix is:

| Outcome | Permitted terminal stage(s) | Terminal-reason shape |
|---|---|---|
| `VALID_GENERATED` | `CENSORING_COMPLETION` | exact NOT_APPLICABLE reason binding |
| `REGISTERED_EXCLUSION` | `SUPPORT_AUTHORITY` | exact effective support/exclusion assessment and decision/ref |
| `GENERATOR_NONCONFORMANCE` | `MATERIALIZATION`, `SUPPORT_AUTHORITY` | exact matching stable failure reason/ref and occurrence/ref |
| `INVALID_CONSTRUCTION` | `CONSTRUCTION_COMPATIBILITY`, `CASE_CONSTRUCTION`, `GRAPH_VALIDATION` | exact matching stable failure reason/ref and occurrence/ref |
| `CENSORED_CASE` | `CENSORING_COMPLETION` | exact censoring decision/ref plus B-02A censoring record/ref |
| `INFRASTRUCTURE_FAILURE` | `CONTEXT_ACQUISITION`, `DERIVATION`, `MATERIALIZATION`, `SUPPORT_AUTHORITY`, `CASE_CONSTRUCTION`, `CENSORING_AUTHORITY`, `ATTEMPT_ACCOUNTING_AUTHORITY`, `GRAPH_VALIDATION` | exact matching stable failure reason/ref and occurrence/ref |

No other combination canonicalizes. `CENSORING_COMPLETION` means the exact
nominal censoring verdict classified the otherwise valid constructed case; it
does not imply scientific acceptance. A pending-successor wrapper retains the
same provisional outcome/stage pair and does not add a terminal stage.

The service has one exact admission boundary. Wrong types/subclasses, malformed
identifiers/digests, stale object/ref pairs, cross-Challenge values, incomplete
primary/selection graphs, invalid role/configuration/environment/attempt-link
or fallback bindings, or a
missing nominal authority method raise a stable sanitized
`GeneratorValidationError`. They create no admitted request ref, source event,
result, or A4/provider call. After deterministic preflight succeeds, the
request is admitted and every invocation path returns exactly one closed
`GeneratorInvocationOutput`: either `FINAL(GeneratorResult)` or
`PENDING_SUCCESSOR(PendingGenerationAttempt)`. The latter wraps one of the same
six provisional outcomes and is not a seventh outcome or a disposition.
`GeneratorInvocationOutput` is an exact frozen/slotted nonserializable tagged
wrapper with no standalone ref or canonical bytes; wrong tag/payload pairs
reject:

1. an exact nominal request that passes boundary admission but fails the
   separately executed construction-compatibility check emits a
   `NOT_ATTEMPTED` source event and `INVALID_CONSTRUCTION` with zero provider/
   derivation calls;
2. grant/provider/acquisition/authority exceptions or unavailable required
   authority become `INFRASTRUCTURE_FAILURE`;
3. the trusted adapter performs at most one A4 derivation and one fixture
   materialization and emits an acyclic source event;
4. a sampler value/shape/nonfinite/configuration/replay violation becomes
   `GENERATOR_NONCONFORMANCE`;
5. registered prospective exclusion becomes `REGISTERED_EXCLUSION`, while
   outside registered support becomes `GENERATOR_NONCONFORMANCE`;
6. failure of exact payload-to-B-02A-case construction or complete graph
   validation, after all inputs were admitted, becomes
   `INVALID_CONSTRUCTION`;
7. an exact censored verdict produces provisional `CENSORED_CASE`; section
   6.4 either supplies its final unexecuted replacement decision or defers its
   B-02A record/result in a pending wrapper until the exact successor invocation
   exists; an exact not-censored verdict produces `VALID_GENERATED`; and
8. exact/near-duplicate and other conformance facts are computed post-case and
   cannot rewrite the terminal outcome.

`GeneratorFailureReason` / `GeneratorFailureReasonRef` are stable prospective
taxonomy values. Each contains exact Challenge, stable reason id/version, one
of `GENERATOR_NONCONFORMANCE`, `INVALID_CONSTRUCTION`, or
`INFRASTRUCTURE_FAILURE`, one exact stage from the matrix, a stable non-echoing
reason code, and exact occurrence-evidence category `AUDIT_EVIDENCE` or
`INFRASTRUCTURE_FAILURE`. It contains no request/event/attempt or future
occurrence input. Its exact registered B-02A aliases are defined in section 3.
The B-03 v1 catalog is exactly:

| Outcome | Stage | `reason_id` | `reason_code` | Occurrence evidence |
|---|---|---|---|---|
| `GENERATOR_NONCONFORMANCE` | `MATERIALIZATION` | `b03_sampler_contract_violation` | `sampler_contract_violation` | `AUDIT_EVIDENCE` |
| `GENERATOR_NONCONFORMANCE` | `SUPPORT_AUTHORITY` | `b03_outside_registered_support` | `outside_registered_support` | `AUDIT_EVIDENCE` |
| `INVALID_CONSTRUCTION` | `CONSTRUCTION_COMPATIBILITY` | `b03_construction_compatibility_failed` | `construction_compatibility_failed` | `AUDIT_EVIDENCE` |
| `INVALID_CONSTRUCTION` | `CASE_CONSTRUCTION` | `b03_case_construction_failed` | `case_construction_failed` | `AUDIT_EVIDENCE` |
| `INVALID_CONSTRUCTION` | `GRAPH_VALIDATION` | `b03_authoring_graph_invalid` | `authoring_graph_invalid` | `AUDIT_EVIDENCE` |
| `INFRASTRUCTURE_FAILURE` | `CONTEXT_ACQUISITION` | `b03_context_acquisition_unavailable` | `context_acquisition_unavailable` | `INFRASTRUCTURE_FAILURE` |
| `INFRASTRUCTURE_FAILURE` | `DERIVATION` | `b03_seed_derivation_unavailable` | `seed_derivation_unavailable` | `INFRASTRUCTURE_FAILURE` |
| `INFRASTRUCTURE_FAILURE` | `MATERIALIZATION` | `b03_materialization_infrastructure_failure` | `materialization_infrastructure_failure` | `INFRASTRUCTURE_FAILURE` |
| `INFRASTRUCTURE_FAILURE` | `SUPPORT_AUTHORITY` | `b03_support_authority_unavailable` | `support_authority_unavailable` | `INFRASTRUCTURE_FAILURE` |
| `INFRASTRUCTURE_FAILURE` | `CASE_CONSTRUCTION` | `b03_case_construction_infrastructure_failure` | `case_construction_infrastructure_failure` | `INFRASTRUCTURE_FAILURE` |
| `INFRASTRUCTURE_FAILURE` | `CENSORING_AUTHORITY` | `b03_censoring_authority_unavailable` | `censoring_authority_unavailable` | `INFRASTRUCTURE_FAILURE` |
| `INFRASTRUCTURE_FAILURE` | `ATTEMPT_ACCOUNTING_AUTHORITY` | `b03_attempt_accounting_authority_unavailable` | `attempt_accounting_authority_unavailable` | `INFRASTRUCTURE_FAILURE` |
| `INFRASTRUCTURE_FAILURE` | `GRAPH_VALIDATION` | `b03_graph_validation_infrastructure_failure` | `graph_validation_infrastructure_failure` | `INFRASTRUCTURE_FAILURE` |

Every row has `reason_version="1.0"`. The admitted request catalog must equal
this service-owned row schema in this canonical order with exactly one
Challenge-bound reason/ref, alias-applicability binding, and pre-issued
occurrence-evidence fallback for every row. Missing, extra, duplicate, wrong-
order, wrong-id/code/version/outcome/stage/category, stale-ref, or alias/fallback
mismatch fails admission. The service selects the unique reason only from the
actual outcome/stage pair; there is no caller reason selector or default.

The two shared construction stages have an exact failure boundary. A
`TypeError` or `ValueError` raised synchronously by the exact pure B-02A/B-03
case constructor or complete graph validator for the admitted candidate bytes
is `INVALID_CONSTRUCTION`; the service never reclassifies it by message text.
Failure of the required fixture capability, protected codec/loader/composition
adapter, origin attachment, or validator execution infrastructure before a
pure validation verdict is available is `INFRASTRUCTURE_FAILURE` at the same
stage and uses the catalog's pre-issued infrastructure fallback. Sampler
value/shape/nonfinite rejection versus materializer unavailability and outside-
support decision versus support-authority unavailability follow the analogous
closed splits already defined above. No arbitrary exception string selects a
reason.

`GeneratorFailureOccurrence` / `GeneratorFailureOccurrenceRef` contain the
exact request/source-event refs, stable reason/ref and its catalog entry's two
exact B-02A alias-applicability bindings, actual matching outcome/stage, and an exact applicability binding to
the matching catalog entry's pre-issued B-02A `audit_evidence` ref for
nonconformance/invalid occurrence evidence or `infrastructure_failure` ref for
infrastructure occurrence evidence. They contain no exception
text, input value, path, seed, draw, slot, stratum, or provider object. The
result and attempt retain both the stable reason and occurrence; only the
stable `generation_failure` alias enters B-02A
`GenerationFailurePayload.failure_evidence_ref`.

`GeneratorResultRecord` is the canonical protected result. `GeneratorResult`
is a nonserializable exact wrapper containing the record/ref plus the internal
`GeneratedFixtureArtifact` attachment whenever a validated case was actually
constructed, including a later post-case infrastructure failure. The canonical
record has:

| Field | Exact meaning |
|---|---|
| `challenge_key`, physical, candidate, primary, selection, SamplingPlan, generator, environment, configuration, role, fixture-registration, and source-provenance refs | exact request echoes |
| `request_ref` and `source_event` / `source_event_ref` | exact acyclic request/event identities |
| `outcome_kind` | one closed value above |
| `case_binding` | exact case/case-ref pair for `VALID_GENERATED` and `CENSORED_CASE`; exact `RESULT_CASE_INAPPLICABLE` otherwise |
| `constructed_case_binding` | protected audit-only exact case/case-ref pair whenever complete graph validation succeeded before terminalization; equals `case_binding` for valid/censored and may remain bound on later censoring/accounting infrastructure failure; otherwise exact `CONSTRUCTED_CASE_INAPPLICABLE`; never creates a disposition or public case identity |
| `support_decision` / `support_decision_ref` | exact object/ref pair when support authority ran; otherwise exact `SUPPORT_DECISION_INAPPLICABLE` |
| `censoring_verdict` / `censoring_verdict_ref` | exact object/ref pair when censoring authority ran, including when later accounting failed; otherwise exact `CENSORING_VERDICT_INAPPLICABLE` |
| `censoring_decision` / `censoring_decision_ref` | exact finalized object/ref pair only after bound attempt accounting permits finalization; otherwise exact `CENSORING_DECISION_INAPPLICABLE` |
| `disposition_binding` | exact B-02A disposition/ref pair only for the four rows mapped below; otherwise exact `DISPOSITION_INAPPLICABLE` |
| `terminal_reason_binding` | closed exact variant: exact `TERMINAL_REASON_INAPPLICABLE` for valid; support decision for exclusion; censoring decision + record for censored; stable B-03 failure-reason and per-attempt occurrence pairs for nonconformance/invalid/infrastructure, including accounting-authority failure |
| `attempt_accounting_decision` / `attempt_accounting_decision_ref` | exact section 6.4 bound or owner-unavailable object/ref pair; never a request echo |
| `attempt_record` / `attempt_record_ref` | exact object/ref pair covering this attempt |
| `conformance_facts` / `conformance_facts_ref` | exact object/ref pair on every admitted path; its individual fields carry closed applicability/unavailability variants |

The wrapper carries `GeneratedFixtureArtifact` exactly when
`constructed_case_binding` is bound and requires its case/ref to equal that
binding. A post-case infrastructure result retains the immutable protected
artifact for provenance/audit but has no `case_binding`, B-02A disposition, or
public case identity. The wrapper retains no A4 context, provider, grant, draw,
derived seed, or byte material.

The B-02A mapping is normative:

| B-03 outcome | B-02A mapping | Required case/attempt shape |
|---|---|---|
| `VALID_GENERATED` | `CaseState.VALID` + `ValidCasePayload` | exact case/ref bound; attempt-only binding absent |
| `CENSORED_CASE` | `CaseState.CENSORED` + exact `CensoringRecordRef` payload | exact case/ref bound; attempt-only binding absent; exact censoring record/ref and disposition required |
| `REGISTERED_EXCLUSION` | `CaseState.EXCLUDED` + `ExcludedCasePayload` | B-03 prospective form only: no case, exact attempt ref bound |
| `GENERATOR_NONCONFORMANCE` | `CaseState.GENERATION_FAILURE` + `GenerationFailurePayload` | no case, exact attempt ref bound; exact B-03 reason remains nominally preserved |
| `INVALID_CONSTRUCTION` | no B-02A `CaseState` | no case or fabricated disposition; exact B-03 reason/attempt record only |
| `INFRASTRUCTURE_FAILURE` | no B-02A `CaseState` | no disposition-facing case or fabricated disposition; exact B-03 reason/attempt record; a validated audit-only constructed case/artifact is retained only when failure occurred post-case |

For valid/censored, `case_ref_binding` is exact BOUND and
`attempt_commitment_binding` is exact NOT_APPLICABLE with the request's
attempt-inapplicable reason ref. For prospective exclusion/generation failure,
the case binding is exact NOT_APPLICABLE with the request's case-inapplicable
reason ref and the attempt binding is exact BOUND. Invalid/infrastructure
construct no disposition. The two reason refs are pre-issued, Challenge-bound,
retained in request identity, and never inferred or defaulted.

Every mapped disposition is exact-recomputed and graph-validated. None of the
six results is candidate scientific evidence merely by existing; censored and
excluded cases remain non-valid evidence under B-02A. No reason is collapsed
into another state.

## 8. Attempts, replacement, censoring, and population accounting

One normal service invocation owns exactly one protected attempt commitment
and makes at most one A4 derivation/provider-material consumption. It cannot
silently retry. B-03 selects no production retry ceiling. The audit-only replay
probe in section 9 is explicitly not an attempt, result, or accounting row.

`GenerationAttemptRecord` / `GenerationAttemptRecordRef` contain exactly:

- Challenge, request ref, source-event ref, generator/environment/configuration
  refs, primary/selection/plan refs, role, replay ref, distinct intended-slot
  and intended-evidence-unit refs, attempt ref, and a protected UInt64
  `attempt_ordinal`;
- materialization state, terminal `GeneratorOutcomeKind`, optional case ref,
  exact support-decision, censoring-verdict/final-decision, and conformance refs,
  and exact stable failure-reason plus per-attempt failure-occurrence refs with
  applicability fixed by the outcome matrix: BOUND exactly for the three
  failure outcomes and exact `FAILURE_BINDING_INAPPLICABLE` for valid,
  exclusion, and censored;
- the request's exact current pending-predecessor/lineage bindings, which say
  whether this attempt was itself a replacement;
- an exact applicability binding to this invocation's own
  `PendingGenerationAttemptRef`, BOUND only when it was later finalized after
  an admitted successor and otherwise the request's exact
  `PENDING_ATTEMPT_INAPPLICABLE` reason; and
- the final exact `AttemptAccountingDecision`/ref pair. It contains the source
  directive/ref, exact outcome-caused B-02A replacement binding when applicable,
  denominator binding, and an exact successor-execution binding. That last
  binding is BOUND only after the successor invocation exists and carries its
  exact request/ref plus either its pending-attempt/ref or final-result/ref;
  otherwise it is exact NOT_APPLICABLE.

The request carries `attempt_ordinal`; it is internal/protected, rejects
Boolean and overflow, and is absent from public/error surfaces. Attempt-record
construction exact-recomputes the directive and final accounting-decision refs.
For a direct final decision it validates the B-02A decision with
`executed=False` and requires no lineage/successor execution. For a finalized
pending predecessor it requires the exact same lineage in the authorization,
the actually admitted successor request, and the B-02A decision, validates with
`executed=True`, and requires the predecessor's own pending-attempt ref. It
rejects every other combination. A failed attempt cannot derive again or
mutate its ordinal/outcome. No replacement or denominator value is treated as
a request echo.

`IntendedUnitAccounting` / `IntendedUnitAccountingRef` contain the exact
Challenge, plan, primary/selection refs, distinct slot/evidence-unit refs, a
nonempty tuple of exact `IntendedUnitLinkDecision`/ref pairs, a nonempty tuple
of complete final `GenerationAttemptRecord`/ref pairs ordered by strictly
increasing unique ordinal, the exact pending-record/successor replacement-
lineage chain, the exact tuple of per-attempt denominator-effect applicability
bindings, one closed realized terminal outcome, and an exact optional realized
case ref. The realized case is present only for valid/censored; a censored case
remains non-valid evidence. Every finalized attempt is retained even when a
later replacement is realized. The external link/accounting decisions define
grouping and denominator effects; B-03 does not infer either from equal digests
or common labels.

The pure trusted `build_intended_unit_accounting` constructor accepts only the
nonempty exact final attempt-record/ref pairs and their exact link-decision/ref,
directive/ref, and accounting-decision/ref pairs. It recomputes all refs,
requires one Challenge/plan/population/slot/evidence-unit identity, and proves
strict ordinal order and exact predecessor/lineage continuity. Every non-final
record must bind its own pending-attempt ref; its final B-02A decision must have
BOUND lineage; its exact successor-execution binding must name the next
record's request and invocation output; and the next request must bind that
same pending predecessor and lineage. The final record must have no own pending
ref, no successor execution, and an unexecuted/prohibited B-02A decision when
that mapping applies. A top-level unmatched pending output, trailing
authorization, unfinalized successor transition, missing final record, or
orphan final record makes the unit incomplete and the builder rejects rather
than truncating it. Pending records embedded in a finalized predecessor's exact
successor-execution evidence are required and must match the next final record;
they are not rejected merely for being pending at the time they proved that
invocation executed. The builder
derives the realized outcome/case from the final attempt and returns the exact
accounting/ref pair. Owner-unavailable attempts retain their exact denominator-
unavailable binding and remain in both partitions. The builder has no retry
loop and accepts no caller counts, realized-outcome override, execution Boolean,
or denominator Boolean.

`GenerationAccountingSummary` / `GenerationAccountingSummaryRef` consume a
canonical tuple of complete intended-unit accounting pairs and contain exact
UInt64 `attempt_count`, six `attempt_outcome_counts`,
`intended_unit_count`, and six `realized_outcome_counts`, plus the exact tuple
of realized-valid case refs. Counts reject Boolean/overflow; the six attempt
counts must sum to `attempt_count`, the six realized counts must sum to
`intended_unit_count`, every nested ref must recompute, and no attempt or
intended unit may appear twice. Attempt and intended-unit partitions are
separate: a replacement chain may have several terminal attempts but only the
externally authorized intended-unit treatment. No unit disappears because a
case was difficult, invalid, excluded, censored, nonconforming, or
infrastructure-failed.

Each count tuple contains exactly six nested `GeneratorOutcomeCount` values,
each with one exact `GeneratorOutcomeKind` and UInt64 count, in the declaration
order of section 7 with every kind appearing once. Mappings, missing/extra/
duplicate kinds, alternate ordering, negative/Boolean counts, and caller-
supplied totals reject. `GeneratorOutcomeCount` has no standalone ref and
canonicalizes only in the summary.

The pure trusted `build_generation_accounting_summary` constructor accepts
only the canonical tuple of exact intended-unit-accounting/ref pairs,
recomputes every nested ref, rejects duplicate units or attempts, derives all
counts and realized-valid refs, and returns the exact summary/ref pair. It
accepts no caller-supplied count, denominator, or outcome override.

`GeneratorResult` covers exactly one finalized invocation and does not contain
an `IntendedUnitAccounting` or `GenerationAccountingSummary`; those aggregates
are constructed separately from complete final attempt records. It may be
returned directly or later by `finalize_pending_generation_attempt`, but the
latter performs no provider call, derivation, materialization, or mutation of
the invocation's immutable source/outcome facts.

If a fixture test exercises more than one attempt, a separate orchestrator
supplies each new protected attempt, ordinal, replay reservation/grant, current
pending predecessor/lineage, and intended-unit link decision, then explicitly
calls the pending finalizer after each authorized successor invocation exists.
The accounting authority supplies each directive and plan-pinned denominator
effect after the provisional outcome. B-03 has no loop that creates successors
and no built-in retry count. Censoring remains
prospective and exact-plan-bound through section 6.3; B-03 creates no
reference- or measurement-failure censoring rule.

## 9. Fact-only conformance hooks

The per-invocation fact schema uses two exact nested records rather than open
summaries:

- `FixturePayloadFacts` contains the exact protected-payload owner ref,
  `PhysicalPayloadFingerprint`/ref pair, configuration ref, exact UInt64
  `spatial_point_count`, `time_point_count`, and `initial_value_count`, and exact
  `FixtureDegeneracyFacts` below. It contains no raw value, range, moment,
  threshold, acceptance flag, or target-population claim. This is the exact
  fact-only payload summary consumed by the support/exclusion request; the
  protected payload attachment remains a separately typed internal authority
  input.
- `ValidatedCaseFacts` contains the exact B-02A case ref, representation ref,
  physical-payload ref, primary-population ref, SamplingPlan ref, literal
  `GraphOriginTag.FIXTURE_DERIVED`, and exact B-02A owner refs of kinds
  `authoring_origin_evidence` and `origin_composition_audit` from the validated
  `GeneratedFixtureArtifact`. It contains no case bytes, public handle,
  validity Boolean, qualification claim, or LIVE flag. Existence of this exact
  nested value proves only that the contract's validated-case milestone was
  reached.

Both have fixed field order and exact-type validation and canonicalize only as
nested fields of their owning request/fact record. They have no standalone
B-03 ref.

The payload-fact counts are derived, never caller supplied: `spatial_point_count ==
fixture_configuration.grid_points == 8`, `time_point_count == 1` for the sole
initial-condition slice (the fixture generates no trajectory), and
`initial_value_count == len(protected_payload.initial_values) == 8`. Any mismatch
rejects the facts and the containing authority request/conformance record.

`GeneratorConformanceFacts` / `GeneratorConformanceFactsRef` are an exact
object/ref pair, not a bare ref, and are constructible for every admitted
terminal path. The record always contains the Challenge, request/source-event,
generator/environment/configuration, primary/selection/plan, role, exact
terminal outcome/stage, and closed applicability bindings for exact
`FixturePayloadFacts`, the two-population support decision, and exact
`ValidatedCaseFacts`,
plus one always-bound exact `ReplayIdentityFacts` value for the current
invocation. External distribution facts are deliberately absent from this
per-attempt record. Every applicability binding is
exactly one of:

- `BOUND`, carrying the exact nominal value/ref pair required for that field;
  or
- `NOT_APPLICABLE`, carrying one exact pre-issued stage/reason ref from the
  admitted request's conformance fallbacks. Authority failure uses the field's
  exact `OWNER_UNAVAILABLE` value when that protocol defines one; it never
  fabricates a bound fact.

Applicability follows the actual reached milestone, not an optimistic outcome
label:

| Reached milestone | Payload/intrinsic degeneracy | Support pair | Validated case | Current replay identity |
|---|---|---|---|---|
| `NOT_ATTEMPTED` construction check | N/A | N/A | N/A | bound; payload/case applicability retained |
| context/derivation/materialization failure or no conforming payload | N/A | N/A | N/A | bound; no comparison claim |
| conforming payload before support completion | bound | N/A or exact owner-unavailable | N/A | bound |
| registered exclusion/outside support | bound | bound | N/A | bound |
| case construction/graph failure | bound | bound | N/A | bound |
| validated case reached | bound | bound | bound protected facts | bound |

Thus early `GENERATOR_NONCONFORMANCE` and every no-case result still obtain an
exact `GeneratorConformanceFactsRef`; their case components are
explicitly inapplicable. That ref always supplies B-02A
`GenerationFailurePayload.distribution_conformance_ref` when the terminal
mapping is `GENERATION_FAILURE`. The pure constructor derives applicability
from the source-event materialization state and terminal stage and accepts no
caller Boolean or forged reason.

`ReplayIdentityFacts` contains only the exact current request/ref,
source-event/ref, replay reservation ref, generator/environment/configuration/
role identities, materialization state, and exact payload/fingerprint and
constructed-case applicability bindings reached by this invocation. It has no
`expected`, `observed`, equality, success, or determinism Boolean and makes no
cross-run claim.

The nominal internal `FixtureReplayProbeAuthority` may use a case-bearing
baseline result's already-bound private replay reservation to perform one
separate fixture-only replay derivation/materialization. The call also accepts
the complete baseline request transiently, reconstructs its
`GeneratorRequestIdentity`/ref, and requires it and the result's request/event/
artifact bindings to match before consuming the probe capability; no resolver
is assumed. It then runs the same
pure protected-payload codec, source-event constructor, B-02A case constructor,
and canonical ref builders under the baseline's exact request/attempt/source
identities. This reconstructs audit-only objects; it does not issue a second
provenance event, disposition, attempt record, result, or accounting entry.
Ordinary second attempts instead require distinct replay/attempt identities and
are not expected to have equal complete case refs.

The authority returns a canonical protected `FixtureReplayProbeRecord` and
`FixtureReplayProbeRef` plus a nonserializable exact `FixtureReplayProbe`
wrapper. The record contains the exact baseline `GeneratorResultRecord`/ref and
`GeneratorRequestIdentity`/ref (never either nonserializable wrapper), replay
ref, generator/environment/configuration/role echoes, and newly observed
`PhysicalPayloadFingerprint`/ref, and the reconstructed protected-payload,
source-event, and B-02A case refs. The wrapper additionally retains those exact
protected reconstructed objects so their canonical bytes can be checked; they
are never exposed, stored as a generated case, or accepted by result/attempt/
accounting/public builders. The probe accepts no new draw/context, retains no
A4 material, and requires the baseline's exact construction bindings. A stale,
cross-Challenge, non-echoing, exception, or non-case baseline fails the probe
operation and does not alter the baseline terminal outcome.

The separate pure trusted `compare_fixture_replay` builder accepts one exact
case-bearing baseline `GeneratorResult`/ref pair plus one exact probe/ref,
recomputes every nested ref and canonical byte sequence, and requires all
identity echoes. It returns exact `DeterministicReplayComparison`/
`DeterministicReplayComparisonRef` containing the baseline result/event/
payload-fingerprint/case refs, probe and reconstructed refs, and three derived
Booleans: physical-payload-fingerprint equality, source-event byte/ref equality,
and B-02A case byte/ref equality. The attempt-independent fingerprint is itself
derived from the full protected-payload canonical bytes, so no unavailable
baseline payload object is needed or claimed. It
accepts no expected digest or caller Boolean. A fixture determinism proof
requires all three true. Because the probe is nominally non-accounting and its
reconstructed identities are barred from service/result/attempt/accounting
inputs, it cannot masquerade as a second execution. The comparison is an
engineering fact, not a scientific adequacy or independence verdict.

`FixtureDegeneracyFacts`, nested inside `FixturePayloadFacts`, contains only
payload-local mechanical observations: UInt64 `distinct_initial_value_count`
and exact Booleans `all_initial_values_zero` and
`all_initial_values_identical`. The distinct count cannot exceed the exact
initial-value count in its owning payload facts. Repeated
physical fingerprints and complete
case refs exist only in the separately applicable duplicate-comparison facts;
they are never defaulted to false before a comparison corpus/case exists.
These are not scientific degeneracy criteria and no Boolean is an acceptance
or qualification verdict.

Protected strata/tails and marginal/joint/conditional summaries cannot be
derived from opaque refs. The separate post-accounting
`ExternalDistributionFactRequest` therefore carries an already complete exact
protected canonical tuple of case-bearing `GeneratorResultRecord`/ref pairs
plus the exact nonempty canonical tuple of complete
`IntendedUnitAccounting`/ref pairs from which its
`GenerationAccountingSummary`/ref is recomputed, plan, population refs, one
exact requested fact kind (`REALIZED_STRATUM`, `TAIL_ALLOCATION`, `MARGINAL`,
`JOINT`, `CONDITIONAL`, `CENSORING_BY_CAUSE`, or
`CENSORING_BY_STRATUM`), one externally owned B-02A `statistics_objective`
estimand/spec ref, and one pre-issued
exact B-02A owner ref of kind `applicability_reason` for owner unavailability.
Complete result wrappers are transient verification attachments only and never
canonical request fields.
The request constructor recomputes every intended unit and the summary and
requires exactly one result-record/ref member for every and only final
`VALID_GENERATED` or `CENSORED_CASE` unit: its attempt-record ref, outcome, and
case ref must equal that unit's final attempt and realized binding. It rejects
missing, substituted, duplicate, extra, non-final, merely audit-constructed,
or cross-unit results. Thus censored cases cannot disappear merely because the
summary's separately useful realized-valid tuple excludes them, and corpus
completeness is proved without a store/resolver.
The fallback is bound into the request and
resulting fact-set identity and is used only when the nominal authority fails
to return a valid echo. The request never feeds
back into an attempt's `GeneratorConformanceFacts`. A nominal authority must
return one exact fixed-order nested `ExternalDistributionFactDecision`
containing the complete request echo and one `ExternalFactAvailability`
variant:

- `BOUND`, with one closed fact kind (`REALIZED_STRATUM`, `TAIL_ALLOCATION`,
  `MARGINAL`, `JOINT`, `CONDITIONAL`, `CENSORING_BY_CAUSE`, or
  `CENSORING_BY_STRATUM`) which must equal the request, and exact B-02A
  `evidence_artifact` fact ref plus `audit_evidence` ref; or
- `OWNER_UNAVAILABLE`, with the requested `statistics_objective` ref and the
  request's exact B-02A `applicability_reason` unavailable ref.

`ExternalFactAvailability` has no standalone ref and rejects every other field
combination. Stale, cross-Challenge, partial, non-echoing, subclassed, or
exception responses are deterministically converted to the exact
`OWNER_UNAVAILABLE` variant from the admitted request without re-calling the
failed authority.

The pure post-accounting builder accepts an exact nonempty canonical tuple of
request/decision pairs and returns a distinct
`ExternalDistributionFactSet`/`ExternalDistributionFactSetRef`. The set
contains exactly the common Challenge, case-corpus, intended-unit tuple,
accounting-summary, plan and population refs plus the canonical tuple of exact
decisions. Every pair must exact-echo and recompute; all common identities must
match; `(requested_fact_kind, statistics_objective_ref)` keys must be unique;
and canonical ordering is by those two encoded keys. No empty set, duplicate,
caller ordering override, omitted common input, or fact-kind substitution
canonicalizes.
B-03 never inspects or fabricates a protected
stratum/tail/estimand. Attempt, terminal, invalid-construction, rejection, and
censoring counts come only from the exact accounting summary in section 8 and
exact censoring records. This direction is acyclic: terminal conformance facts
precede attempt records; attempt records precede accounting; external fact sets
consume completed accounting and are never embedded back into those inputs.

The hooks contain no minimum sample count, confidence rule, p-value cutoff,
coverage target, range, viscosity tolerance, diversity threshold, collision
budget, near-duplicate distance, admissibility threshold, or qualification
decision. Human SciML/statistics owners and later B-06 evidence machinery
decide whether evidence is adequate.

## 10. Public disclosure boundary

`PublicGenerationProjection` is a separately constructed safe projection with
an exact closed allowlist:

- `challenge_key`;
- generator public id and version;
- structural `FIXTURE_ONLY` provenance marker;
- coarse terminal outcome kind; and
- already-authorized `PublicCaseIdentityProjection` only when an external
  B-02A `CaseProjectionAuthority` supplies it.

The factory accepts the exact protected `GeneratorResult` plus an optional
already-issued `PublicCaseIdentityProjection` and its external authority. It
requires the result wrapper's `GeneratedFixtureArtifact`, derives
`FIXTURE_ONLY` only from that artifact's exact composed
`GraphOriginTag.FIXTURE_DERIVED`, takes generator id/version from the exact
result generator owner pin, and takes the coarse outcome from the result. It
rejects the four early no-artifact outcomes rather than inventing a provenance
marker. A post-case infrastructure result may receive a projection with no
case identity, preserving fixture-attempt visibility without disclosing its
audit-only constructed case.

When a public case projection is present, the result's disposition-facing
`case_binding` must be bound (valid/censored), and the factory calls the
external `CaseProjectionAuthority.require_pairing(projection, case_ref)`. If
`case_binding` is absent, both case projection and authority must be absent.
Nothing returns unless all exact pairings and applicability rules hold. B-03
never constructs that authority, projects the audit-only constructed case, or
substitutes a digest-valid projection.

It must not contain or reveal a canonical case ref, payload ref or bytes,
generation-event ref, replay/attempt/intended-slot identity, seed/context/
provider/derived material, hidden stratum or mixture, distribution internals,
support/exclusion inputs, near-duplicate inputs, PDE/reference outputs,
reversible generator inputs, or exception internals. B-03 does not mint
`CaseProjectionAuthority` and cannot derive public case identity from a raw
case.

All protected types use redacted `repr`/`str`, reject generic serialization
and pickling where appropriate, and sanitize validation/provider/authority
errors. Public exceptions have stable reason codes and generic messages, no
cause/context chain, and no echoed values. Returned graphs retain no entropy
context, provider, derived seed, or raw protected input.

## 11. Canonical identity and validation

B-03 domain records use a closed domain-separated profile and header distinct
from B-02A while reusing B-02A primitive/value encoding and tagged SHA-256
grammar. The initial profile is
`carbon_generator_runtime_canonical_v1` and the framing header is
`carbon.generator.runtime.canonical.v1\0`. The closed canonical object kinds
are generator implementation manifest, descriptor, environment, fixture
configuration, request-identity projection, intended-unit-link decision,
source event, support/exclusion decision,
censoring verdict, censoring decision, attempt-accounting directive,
attempt-accounting decision, pending-generation-attempt record, failure reason,
failure occurrence, terminal-result record, generation-attempt record,
intended-unit accounting, generation-accounting summary, conformance facts,
protected fixture payload, protected physical-payload fingerprint,
fixture-replay-probe record, deterministic replay comparison, comparison-corpus
decision, duplicate-conformance facts, and the post-accounting external-
distribution fact set. `GenerationRoleBinding`, `CaseConstructionBinding`,
`FixtureLoadingBinding`, `PopulationSupportAssessment`,
`SupportExclusionRequest`, `PostResultDuplicateRequest`,
`DuplicateComparisonRequest`, `NearDuplicateRequest`,
`NearDuplicateDecision`,
`GeneratorCensoringRequest`, `CensoringRecordBasis`,
`AttemptAccountingRequest`, `SuccessorAuthorization`,
`SuccessorExecutionEvidence`, `FixturePayloadFacts`, `ValidatedCaseFacts`,
`FixtureDegeneracyFacts`, `ReplayIdentityFacts`, `GeneratorFailureCatalogEntry`,
`GeneratorOutcomeCount`,
`ExternalDistributionFactRequest`, `ExternalDistributionFactDecision`,
`ExternalFactAvailability`, and applicability/terminal-
reason bindings canonicalize only as fixed-order nested fields of their owning
records. The externally
issued `GeneratorReplayCommitmentRef` is likewise not a B-03 canonical object.
Protected random material, draw grants, loaded artifacts, graph-origin objects,
and capabilities are never B-03 canonical objects.

Decoders require exact profile, schema version, object kind, field set, field
order, value type, tuple order, and full byte consumption. They reject missing
or extra fields, duplicate keys, trailing bytes, unknown variants, malformed
UTF-8/identifiers/digests, subclass values, Boolean-as-integer, nonfinite
Float64, cross-Challenge refs, stale bindings, and digest mismatch. There are
no aliases or inferred version ordering. Historical bytes and refs never
change meaning.

The package root exposes only the curated safe descriptors/environment refs,
fixed fixture configuration/ref, role binding, `GeneratorOutcomeKind`,
production-input-unavailable value, and `PublicGenerationProjection` factory.
Protected request/construction/replay/source-event/result/accounting/
conformance values and the trusted service are available only by explicit
imports from their owning modules, mirroring B-02A's protected-case boundary;
they are not root convenience exports. Their representations remain redacted
and generic serialization is rejected. Fixture generation authority, draw
grant, material sampler, loaded-artifact wrapper, protected codec, and raw ref
issuance remain private. Only `PublicGenerationProjection` is externally
disclosable; no star-generated surface is allowed.

## 12. Required implementation proof

The B-03 implementation candidate must prove at least:

1. exact immutable fields, ref recomputation, stale/cross-Challenge and hostile
   input rejection;
2. canonical round trip, tamper/trailing/missing/extra-field rejection, and
   fresh-process/hash-seed independence;
3. exact B-02A graph validation before and after case construction;
4. byte-identical deterministic fixture replay and exact case-ref equality;
5. every closed terminal outcome and its strict no-case/case matrix;
6. raw callback/Boolean authority rejection and exact authority-echo checks;
7. one derivation per attempt, no silent retry, full replacement lineage, and
   intended-versus-realized denominator preservation;
8. exact-duplicate facts, externally owned near-duplicate seam, and fact-only
   degeneracy/conformance summaries without thresholds;
9. fixed-viscosity periodic Burgers fixture shape with explicit unavailable
   production inputs and no PDE/reference/score output;
10. no seed, material, context, provider, protected identity, hidden stratum,
    payload, or reversible-input leakage through values, serialization,
    `repr`, `str`, exceptions, or object reachability;
11. structural fixture-origin propagation through loaded authoring graphs and
    fail-closed A3 LIVE assessment with reason
    `scientific_authoring.fixture_derived`;
12. standard-library-only packaging, explicit exports, installed-wheel and
    outside-tree imports, one-way dependencies, code authority, and no retired
    namespace; and
13. no dependency, lock, workflow, environment, service transport, B-04,
    B-05, B-06, B-07S, or later-ticket implementation change.

The canonical local command remains `./scripts/dev/ci.sh`; canonical GitHub
Linux exact-head CI is authoritative when the native host is rejected.

## 13. Reserved inputs and maturity ceiling

SciML/statistics/protocol owners retain the real target and proposal
populations, density or sampling laws, ranges, strata, exclusions, mixture
weights, viscosity, forcing and initial-condition laws, sampling-plan values,
replacement/censoring policies, estimands, adequacy evidence, duplicate and
near-duplicate policy, conformance thresholds, and generator qualification.
A4/operations/security owners retain production entropy, provider,
environment, custody, deployment, and operational approval. B-04 retains
reference truth/failure. B-05 retains measurement and uncertainty policy.
A3/B-06 retain qualification and LIVE gates.

The contract and fixture implementation may support only:

```text
SPECIFIED: BOUNDED ENGINEERING CONTRACT ONLY
RATIFIED_ENGINEERING_CONTRACT: ONLY AFTER THE EXTERNAL CONTRACT GATE
IMPLEMENTED: FIXTURE CANDIDATE ONLY
TESTED: RECORDED ENGINEERING TESTS ONLY
SCIENTIFICALLY_QUALIFIED: NO
SECURITY_QUALIFIED: NO
OPERATIONS_APPROVED: NO
PRODUCTION_QUALIFIED: NO
LIVE: NO
```

## 14. Supersession and migration

Changing package ownership, dependency direction, public field inventory,
role/domain mapping, outcome taxonomy, canonical field order/profile, ref
scope, disclosure allowlist, authority protocol, or attempt-accounting meaning
requires a prospective B-03 contract/schema version, a normally merged
superseding decision, exact migrations or dual-version readers where persisted
bytes exist, invariant/import tests, exact-head review, and exact-main CI.
Existing event, result, payload, case, and accounting refs remain immutable.

Real population values, thresholds, production providers, qualification, and
LIVE cannot be added by revising a fixture constant or caller flag. Each
requires its owning contract, evidence, and prospective authority path.
