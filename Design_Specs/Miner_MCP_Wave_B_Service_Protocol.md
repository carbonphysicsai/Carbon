# Miner MCP Wave B Service Protocol

**Status:** normative, ratified engineering protocol
**Version:** 2.0.0
**Owner:** B-07S
**Authority:** `Miner_MCP_Wave_B_Research_Contract.md`, with the exact domain
owners named below
**Maturity:** `SPECIFIED / RATIFIED`; not implemented or qualified

## 1. Scope and conformance

This document is the sole wire-visible contract for the local Wave B research
service. It closes the implementation choices delegated by B-07R without
implementing B-07A/B/C/D/E/F/G. An adapter conforms only when every request,
result, failure, bound, identity rule, transition, projection, and constructor
capability below is enforced. Unknown fields, union tags, enum values,
operations, and namespaces fail closed.

The two local service identities are exact and disjoint:

- `carbon_protocol_v1` is the unchanged Wave A service. Official `submit` and
  `get_submission_result` exist only there.
- `carbon_research_v2` contains exactly `get_challenge_info`,
  `get_interaction_manifest`, `get_prior`, `get_mock_scaffold`, `dry_validate`,
  `compile_strategy`, `inspect_prior_alignment`, `inspect_resources`,
  `forecast_resources`, `start_research_task`, `get_research_result`, and
  `cancel_research_task`.

There is no merged or unqualified alias. `submit` and
`get_submission_result` presented under v2, a v2 operation presented under v1,
or a request/result from one namespace used in the other is
`NAMESPACE_MISMATCH`. An otherwise unknown operation is
`OPERATION_UNSUPPORTED`.

The protocol is an in-process agent-adapter contract. Conformance requires no
listener, socket, remote transport, identity credential, or key.

## 2. Canonical wire profile

### 2.1 Envelope

Every call is the exact record, in this order:

```text
ServiceCall(namespace, operation, request)
namespace : exact UTF-8 enum
operation : exact UTF-8 enum
request   : the operation's exact nominal request union member
```

Success is `ServiceReply(OK, result)` and failure is
`ServiceReply(ERROR, ResearchServiceError)`. No call has both or neither.

### 2.2 Encoding

Canonical bytes use the B-02A closed scalar/tuple/record/union/ref grammar:
UTF-8 text with no normalization, exact booleans, signed/unsigned 64-bit
integers, finite binary64 values (`-0.0` normalized to `+0.0`), length-prefixed
bytes and tuples, records in the field order specified here, and explicitly
tagged unions/refs. Maps, sets, NaN, infinities, subclasses, implicit numeric
coercion, duplicate fields, unknown fields, and trailing bytes are invalid.

The v2 document header is the literal bytes
`carbon.research-service.canonical.v2\x00`. The schema version is `2.0`; the
canonicalization profile is `carbon_research_service_canonical_v2`. Ref
digests are lowercase `sha256:` plus exactly 64 lowercase hexadecimal digits.
All hashes in this document are SHA-256 over the stated canonical bytes; a
domain separator is the literal UTF-8 text plus NUL shown for that identity.

Decoders enforce the following before allocation:

| Limit | Exact value |
|---|---:|
| canonical call or reply bytes | 1,048,576 |
| canonical resource bytes returned by one call | 8,388,608 |
| nesting depth | 32 |
| tuple items unless narrowed below | 4,096 |
| UTF-8 field bytes unless narrowed below | 16,384 |
| identifier/version/enum UTF-8 bytes | 128 |
| challenge identifier UTF-8 bytes | 256 |
| error message UTF-8 bytes | 1,024 |
| error path components | 32 |
| error detail entries | 32 |
| manifest catalog entries | 256 |
| manifest parameter entries | 1,024 |
| PriorPack items | 256 |
| finding items per terminal receipt | 256 |
| compile/validation/alignment issues | 256 |
| resource line items | 128 |
| task polls per task and idempotency identity | 10,000 |

Lengths are byte lengths after canonical UTF-8 encoding. Empty identifiers,
versions, and digests are invalid. All collections are tuples, preserve their
declared order, and reject duplicate identity keys. Exceeding any limit is
`BOUND_EXCEEDED`; malformed canonical bytes take precedence.

### 2.3 Common primitive and ref bindings

`Option[T]` is the exact union `NONE | SOME(T)`. `ChallengeKey` and
`TrainingStrategy` are the existing A2/B-02A nominal values, not strings or
new v2 representations. The following refs preserve their current nominal
field order, schema/profile validation, and digest semantics:

| Ref family | Exact fields |
|---|---|
| `PhysicalSystemSpecRef`, `CandidateOutputContractRef`, `SamplingPlanRef`, `TrainingSupportContractRef` | `challenge_key, object_id, object_version, schema_version, canonicalization_profile, content_digest` |
| `InstanceDistributionContractRef` | preceding six fields, then `expected_population_role` |
| `CandidateAssemblyContractRef`, `ParameterCatalogRef`, `ResearchResourcePolicyRef`, `ResourceClassRef` | `challenge_key, object_id, object_version, schema_version, canonicalization_profile, content_digest` |
| `TrainingSamplingPolicyRef`, `ResolvedConstructionPlanRef`, `StaticResourceAssessmentRef`, `FixtureResourceDecisionRef`, `ResourceCancellationRecordRef`, `ObservedResourceReceiptRef` | `challenge_key, schema_version, canonicalization_profile, content_digest` |
| `MeasurementContractRef` | `challenge_key, content_digest, schema_version, canonicalization_profile` |

In particular, the public `TrainingSupportContractRef` is the exact B-02A
six-field top-level ref using schema `1.0` and profile
`carbon_scientific_authoring_canonical_v1`. The public
`TrainingSamplingPolicyRef` is the exact B-02B four-field resolved ref using
schema `1.0` and profile `carbon_construction_canonical_v1`. Neither can carry
payload data or control fields.

V2-only refs use this exact field order unless explicitly stated:

```text
ChallengeInfoRef(challenge_key, schema_version, canonicalization_profile, content_digest)
InteractionManifestRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PublicScorePolicyRef(challenge_key, schema_version, canonicalization_profile, content_digest)
StrategySchemaRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PriorPolicyBundleRef(challenge_key, schema_version, canonicalization_profile, content_digest)
DisclosurePolicyRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PublicEstimandRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PublicSearchScopeRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PracticeScopeStatementRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PublicMethodResourceCodebookRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PracticePackRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PublicScaffoldCatalogRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PublicPracticeTestRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PublicMethodArtifactRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PublicAggregatePublicationRef(challenge_key, schema_version, canonicalization_profile, content_digest)
CompilerEnvironmentRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PriorChannelRef(challenge_key, channel, schema_version, canonicalization_profile, content_digest)
PriorPackRef(challenge_key, channel, publication_sequence, content_hash)
PriorIndexSnapshotRef(challenge_key, channel, index_sequence, content_digest)
PriorPublicationReceiptRef(challenge_key, channel, publication_sequence, content_digest)
MockScaffoldRef(challenge_key, schema_version, canonicalization_profile, content_digest)
ValidationResultRef(challenge_key, schema_version, canonicalization_profile, content_digest)
StrategyCompilationRef(challenge_key, schema_version, canonicalization_profile, content_digest)
PriorAlignmentRef(challenge_key, schema_version, canonicalization_profile, content_digest)
ResourceForecastRef(challenge_key, schema_version, canonicalization_profile, content_digest)
ResearchTaskId(value)
ResearchReceiptRef(task_id, receipt_digest)
TestOnlyPriorAuthorizationReceiptRef(challenge_key, authorization_id, content_digest)
```

Sequences are exact unsigned 64-bit integers. `channel` is one of `PUBLIC` or
`TEST_ONLY_FIXTURE`; the latter never appears from an external-public context.
All four-field v2 refs use schema `2.0` and the v2 profile.

## 3. Public resources

The exact discovery resources are:

```text
ChallengeInfo(
  schema_version, challenge_key, challenge_version,
  physical_system_ref, candidate_output_ref, instance_distribution_ref,
  sampling_plan_ref, training_support_ref, measurement_contract_ref,
  public_score_policy_ref, disclosure_class
)

InteractionManifest(
  schema_version, challenge_key, challenge_info_ref,
  physical_system_ref, candidate_output_ref, instance_distribution_ref,
  sampling_plan_ref, training_support_ref, measurement_contract_ref,
  public_score_policy_ref, candidate_assembly_ref, strategy_schema_ref,
  parameter_catalog_ref, compiler_identity, method_resource_codebook_refs,
  practice_scope_ref, practice_pack_refs, scaffold_catalog_ref,
  prior_availability, resource_policy_ref, disclosure_policy_ref,
  supported_operations, limits, capability_labels
)

CompilerIdentity(name, version, implementation_digest, environment_ref)
PriorAvailability(NO_PRIOR | AVAILABLE(prior_channel_ref, prior_policy_bundle_ref))
```

`disclosure_class` is exactly `PUBLIC_RESEARCH`. `supported_operations` is the
v2 list in section 1 in that order. `limits` contains every row of section 2.2
in that order. In an external-public context `capability_labels` is the empty
tuple. In a fixture context it is exactly `("TEST_ONLY_FIXTURE_PRIOR",)`.
All manifest refs carry the manifest Challenge. Codebook and practice-pack refs
are canonically sorted by content digest and each tuple has at most 256 items.
The compiler implementation digest is a tagged SHA-256; its environment ref is
public, immutable, and non-executable.

No public resource exposes raw/custom datasets, filesystem paths, arbitrary
URIs, miner-selected official seeds, official P/Q/w, stress-set membership,
reference/truth assets, gate configuration, scorer configuration, protected
case identity, private qualification evidence, credentials, or keys.

Additional exact resources are:

```text
CompileIssue(code, path, message)
ValidationIssue(code, path, message)
AlignmentIssue(code, path, message)
ResourceLineItem(resource_class_ref, quantity, unit, confidence_band)
ResourceForecast(resource_forecast_ref, static_assessment_ref,
                 line_items, total_wall_seconds_band, limitations)
PublicResearchFinding(kind, claim, evidence_class,
                      measurement_ref, uncertainty_band, limitations)
```

`quantity` and band endpoints are finite non-negative binary64 values; lower
is not greater than upper. `path` has at most 32 components. `claim` and each
limitation have at most 4,096 UTF-8 bytes; limitations contain at most 64
items. `evidence_class` is `PUBLIC_OBSERVATIONAL`, `PUBLIC_DERIVED`, or
`TEST_ONLY`. It is never a scientific qualification label.

## 4. Operation contracts

The table is exhaustive. `provider` is a constructor-injected nominal
capability; callers cannot select it. `lifecycle` states whether the operation
may read or mutate a research task.

| Operation | Exact request -> result | Resources/disclosure | Provider | Lifecycle | Semantic owner |
|---|---|---|---|---|---|
| `get_challenge_info` | `GetChallengeInfoRequest(challenge_key) -> ChallengeInfo` | public discovery only | `ChallengeCatalogProvider` | none | B-07A |
| `get_interaction_manifest` | `GetInteractionManifestRequest(challenge_key) -> InteractionManifest` | public discovery and fixed capabilities | `ManifestProvider` | none | B-07A |
| `get_prior` | `GetPriorRequest(challenge_key, selector) -> PriorLookupResult(index_snapshot_ref, prior_pack, prior_pack_ref, lookup_status, authorization)` | approved public prior, or fixture-only TEST_ONLY result | context-specific `PublicPriorProvider` or `TestOnlyPriorProvider` | none | B-07D3 |
| `get_mock_scaffold` | `GetMockScaffoldRequest(challenge_key, training_support_ref, prior_pack_ref) -> MockScaffold(scaffold_ref, strategy_template, limitations)` | mock/practice only | `ScaffoldProvider` | none | B-07C |
| `dry_validate` | `DryValidateRequest(challenge_key, strategy) -> DryValidationResult(valid, issues, validation_result_ref)` | structural/public policy result only | `ValidationProvider` | none | A2 |
| `compile_strategy` | `CompileStrategyRequest(challenge_key, strategy, expected_training_support_ref) -> CompileStrategyResult(accepted, issues, strategy_hash, training_sampling_policy_ref, resolved_plan_ref, compilation_ref)` | no official evaluation | `CompilationProvider` | none | B-02B |
| `inspect_prior_alignment` | `InspectPriorAlignmentRequest(challenge_key, strategy, prior_pack_ref) -> PriorAlignmentResult(alignment_ref, status, issues)` | coarsened public/fixture result | context-specific `PriorAlignmentProvider` | none | B-07D3 |
| `inspect_resources` | `InspectResourcesRequest(challenge_key, strategy, resource_policy_ref) -> InspectResourcesResult(static_assessment_ref, line_items, limitations)` | static estimates, never a quote | `ResourceInspectionProvider` | none | B-07E |
| `forecast_resources` | `ForecastResourcesRequest(challenge_key, strategy, resource_policy_ref, forecast_horizon_seconds) -> ResourceForecast` | forecast, never reservation or quote | `ResourceForecastProvider` | none | B-07E |
| `start_research_task` | `StartResearchTaskRequest(challenge_key, idempotency_key, task_spec, training_support_ref, prior_selector, resource_policy_ref, requested_resource_class_ref, practice_scope_ref) -> StartResearchTaskResult(created, task)` | accepted research inputs and immutable bindings | `ResearchTaskProvider` | create only | B-07B |
| `get_research_result` | `GetResearchResultRequest(challenge_key, task_id, poll_sequence) -> GetResearchResultResult(task)` | public-safe task view/terminal receipt | `ResearchTaskProvider` | read only | B-07B |
| `cancel_research_task` | `CancelResearchTaskRequest(challenge_key, task_id, cancellation_id) -> CancelResearchTaskResult(task, disposition)` | cancellation acknowledgement only | `ResearchTaskProvider` | cancel only | B-07B |

`prior_selector` is exactly:

```text
EXACT(prior_pack_ref)
ACTIVE(channel)
NONE
```

`task_spec` is exactly:

```text
RECONSTRUCTION_REHEARSAL(strategy, parent_strategy_hash)
PRACTICE(strategy, parent_strategy_hash)
PAIRED_PRACTICE(baseline_strategy, intervention_strategy)
RESOURCE_CALIBRATION(strategy)
```

Parent hashes are optional and lineage-only. Paired strategies must compile to
different `StrategyHash` values and exactly one independently computed
resolved-plan difference; zero or multiple differences is a domain validation
issue, not a caller assertion. A practice-scope ref is required for the first
three kinds and must be `NONE` for resource calibration. The requested
resource class must belong to the policy and cannot change official resources.

`get_prior.selector` excludes `NONE`. `start_research_task` permits it.
External-public calls permit only `PUBLIC`; fixture calls permit
`PUBLIC` or `TEST_ONLY_FIXTURE`. `forecast_horizon_seconds` is an exact integer
in `1..604800`. `idempotency_key` and `cancellation_id` are 16..128 ASCII bytes
matching `[A-Za-z0-9._:-]+`. `poll_sequence` is an exact integer in
`0..9999`, starts at zero, and increases by one per successful poll.

`strategy_hash` is the existing A7 `StrategyHash`, calculated by the B-02B
compiler. `dry_validate` cannot run evaluation or acquire official authority.
Compilation uses the exact Challenge-owned training support and derives the
training sampling policy; the caller cannot submit that policy. Resource
inspection and forecasting do not reserve capacity, price execution, or imply
availability.

### 4.1 Result invariants

`PriorLookupResult.lookup_status` is `ACTIVE` or `SUPERSEDED`, and its
`authorization` follows section 8. `MockScaffold.limitations`
is nonempty and includes `MOCK_ONLY`; the template cannot be submitted as an
official result. `DryValidationResult.valid` is true exactly when `issues` is
empty. `CompileStrategyResult.accepted` is true exactly when `issues` is empty;
when true, all four refs/hash are present, and when false they are all `NONE`.
`PriorAlignmentResult.status` is exactly `ALIGNED`, `PARTIAL`,
`NOT_ALIGNED`, or `NOT_APPLICABLE`; it is guidance rather than a gate.

`InspectResourcesResult` and `ResourceForecast` use only public resource class
refs and coarsened bands. Exact host inventory, tenant activity, scheduling,
credentials, pricing, and internal capacity are protected and cannot appear.
The forecast horizon is included in the canonical forecast identity even
though it is not an authority control.

Task operation results are exact:

```text
StartResearchTaskResult(created, task)
GetResearchResultResult(task)
CancelResearchTaskResult(task, disposition)
```

`disposition` is exactly `ACCEPTED`, `ALREADY_ACCEPTED`, or `TOO_LATE`.
`created` is an exact boolean. Every returned task challenge must equal the
request challenge; mismatch is `REFERENCE_MISMATCH` before disclosure.

### 4.2 Validation order

Every operation applies these stages and returns the first failure:

1. canonical decoding;
2. namespace;
3. operation vocabulary;
4. exact nominal request type and unknown-field rejection;
5. scalar and collection bounds;
6. prohibited-field and capability checks;
7. challenge/ref consistency and object lookup;
8. state/idempotency transition checks;
9. provider execution;
10. public disclosure projection and canonical result encoding.

Within a stage, the earliest field in declared record order wins; within a
tuple, the lowest index wins. Providers cannot replace an earlier protocol
error with a domain error.

## 5. Closed failures

`ResearchServiceError(code, path, message, retry_disposition, details)` has an
exact code below, a canonical component path, bounded public-safe message,
`retry_disposition` of `NEVER`, `SAME_REQUEST`, or `NEW_REQUEST`, and a tuple
of at most 32 `ErrorDetail(key, value)` records. Details must pass the same
disclosure projection.

```text
CANONICAL_ENCODING_INVALID  NAMESPACE_MISMATCH      OPERATION_UNSUPPORTED
REQUEST_TYPE_INVALID        UNKNOWN_FIELD            BOUND_EXCEEDED
FORBIDDEN_SCIENTIFIC_CONTROL CONTEXT_SELECTION_FORBIDDEN
CAPABILITY_UNAVAILABLE      CHALLENGE_NOT_FOUND      REFERENCE_NOT_FOUND
REFERENCE_MISMATCH          PRIOR_INDEX_CHANGED      PRIOR_IDENTITY_INVALID
TEST_ONLY_AUTHORITY_INVALID TASK_NOT_FOUND           IDEMPOTENCY_CONFLICT
INVALID_TASK_TRANSITION     POLL_SEQUENCE_INVALID    PROVIDER_UNAVAILABLE
INFRASTRUCTURE_FAILURE      DISCLOSURE_REJECTED      INTERNAL_FAILURE
```

Malformed wire data is `NEVER`. A provider outage and retryable infrastructure
failure are `SAME_REQUEST`; `PRIOR_INDEX_CHANGED` is `NEW_REQUEST`; all other
codes are `NEVER`. `INTERNAL_FAILURE` exposes no exception text. Domain-owned
validation/compiler/resource codes remain in their bounded issue tuples and
do not become service error codes unless the operation itself cannot execute.

The following request field names are forbidden at every depth, including
case variants and normalized spelling variants:

```text
raw_data custom_data dataset data_path filesystem_path path uri url
seed seeds official_seed P Q w stress_set reference truth gate scorer
execution_context context provider evidence_class qualification_label mode
credential credentials key private_key signing_key listener address port
```

An authoritative nominal ref field named in this specification is not the
forbidden bare `reference`; it is decoded only as that exact ref type. Generic
maps are impossible, so aliases cannot smuggle controls. A caller's selection
of a mode, context, provider, evidence class, or qualification label can never
grant evaluator authority.

## 6. Research task state machine

### 6.1 Identity and immutable start binding

The service creates
`ResearchTaskId("rtsk_" + lowercase_hex(SHA-256(preimage)))`, where `preimage`
is the domain `carbon.research-task-id.v2\x00` followed by the canonical bytes
of `(service_instance_id, local_requester_binding, challenge_key,
idempotency_key)`. Both the service instance and requester binding are
constructor-owned random 256-bit values and never wire-visible. They are
installed in the local agent adapter session, not selected or claimed by the
caller; this is local idempotency isolation, not real miner/network identity.
Thus task identifiers do not correlate across service instances or sessions.

The idempotency request digest is SHA-256 over
`carbon.research-start-request.v2\x00` plus the complete canonical
`StartResearchTaskRequest` with `idempotency_key` omitted. The service stores
the tuple `(local_requester_binding, challenge_key, idempotency_key)` atomically
with that digest and the task before returning.

- The first request creates one task and returns `created=true`.
- A byte-equivalent request with the same pair returns the same task and
  `created=false`; it does not enqueue work again.
- A different digest with the same pair returns `IDEMPOTENCY_CONFLICT`; neither
  stored request nor task changes.
- Concurrent duplicates are linearized at that atomic insert and observe one
  of the two preceding results.

At creation the task pins the exact `ChallengeInfoRef`,
`InteractionManifestRef`, `TrainingSupportContractRef`,
the ordered tuple of `StrategyHash`, `TrainingSamplingPolicyRef`, and
`ResolvedConstructionPlanRef` bindings for every strategy in the task spec,
`PriorIndexSnapshotRef` and `PriorPackRef` (when present),
`ResearchResourcePolicyRef`, `ResourceClassRef`, and optional
`PracticeScopeStatementRef`. Active prior resolution and
compilation complete inside the same start transaction. Failure returns an
error and creates no task. Later catalog/index movement never changes a task.

### 6.2 States and transitions

The closed task states are:

```text
QUEUED RUNNING CANCEL_REQUESTED SUCCEEDED FAILED_INFRA CANCELLED
```

Terminal states are exactly `SUCCEEDED`, `FAILED_INFRA`, and `CANCELLED`.
Allowed transitions are exactly:

```text
QUEUED -> RUNNING
QUEUED -> CANCELLED
QUEUED -> FAILED_INFRA
RUNNING -> CANCEL_REQUESTED
RUNNING -> SUCCEEDED
RUNNING -> FAILED_INFRA
CANCEL_REQUESTED -> CANCELLED
CANCEL_REQUESTED -> SUCCEEDED
CANCEL_REQUESTED -> FAILED_INFRA
```

No self-transition or transition out of a terminal state exists. An attempted
provider transition outside this set is `INVALID_TASK_TRANSITION` and cannot
mutate the task.

The immutable binding is exact:

```text
ResearchTaskBindings(
  task_kind, challenge_info_ref, interaction_manifest_ref,
  strategy_bindings, training_support_ref,
  prior_index_snapshot_ref, prior_pack_ref,
  resource_policy_ref, requested_resource_class_ref, practice_scope_ref
)
StrategyTaskBinding(
  role, strategy_hash, training_sampling_policy_ref, resolved_plan_ref
)
```

`role` is `PRIMARY`, or for paired practice exactly `BASELINE` and
`INTERVENTION` in that order. Optional refs use `Option`. The binding is
written once at start and is identical in every view and receipt.

`ResearchTaskView` is the exact record:

```text
ResearchTaskView(
  task_id, challenge_key, state, revision, created_at_micros,
  updated_at_micros, immutable_bindings, progress, terminal_receipt
)
```

`revision` begins at zero and increments exactly once for each state change.
Timestamps are provider-owned UTC microseconds since Unix epoch, exact int64,
nondecreasing, and informational rather than identity inputs. `progress` is
`NONE` or `SOME(Progress(completed_units, total_units))`, exact uint64 values
with completed not greater than total; it cannot imply scientific outcome.
`terminal_receipt` is `NONE` in nonterminal states and present in terminal
states.

### 6.3 Cancellation, polling, failure, and receipts

Cancellation is linearized against terminal commit:

- From `QUEUED`, the first cancellation atomically commits `CANCELLED`.
- From `RUNNING`, it commits `CANCEL_REQUESTED`; the worker owns the next
  transition. If terminal commit won the race, cancellation returns the
  unchanged terminal task and `TOO_LATE`. If cancellation won, it returns
  `ACCEPTED`; later `SUCCEEDED` is allowed only when the indivisible result
  commit had already crossed the provider's cancellation cutoff.
- From `CANCEL_REQUESTED`, the same `cancellation_id` returns `ALREADY_ACCEPTED`;
  a different id returns `INVALID_TASK_TRANSITION`.
- From a terminal state, cancellation returns the unchanged task and
  `TOO_LATE`. It never rewrites the receipt.

The cutoff is the provider-owned atomic beginning of terminal-result commit;
it is not a scientific gate. A worker must check cancellation immediately
before crossing it. Infrastructure timeout, queue loss, worker loss, resource
exhaustion, or dependency outage commits `FAILED_INFRA`, never scientific
failure. `InfrastructureFailureClass` is exactly `QUEUE_LOST`, `WORKER_LOST`,
`RESOURCE_LIMIT`, `EXECUTION_TIMEOUT`, `DEPENDENCY_UNAVAILABLE`, or `INTERNAL`.

The provider owns retry. It may retry internal attempts while the task remains
nonterminal, but must preserve the same pinned inputs, publish no intermediate
attempt as a result, perform at most three attempts, and never create a new
task/idempotency identity. After `FAILED_INFRA`, only the caller may send a new
start with a new idempotency key. Cancellation is not retried after terminal
commit.

Polling is read-only. `(task_id, poll_sequence)` is stored per task. The first
poll uses zero; the next new poll uses the previous value plus one. Repeating
the last successful sequence returns the byte-identical view (including its
revision); lower, skipped, or more than 10,000 sequences return
`POLL_SEQUENCE_INVALID`. Polling never advances work or extends a timeout.

The immutable terminal receipt is:

```text
ResearchReceipt(
  receipt_ref, task_id, terminal_state, immutable_bindings,
  public_findings, observed_resource_receipt_ref,
  infrastructure_failure_class, limitations, completed_at_micros
)
```

For `SUCCEEDED`, findings may be present and infrastructure failure is `NONE`.
For `FAILED_INFRA`, findings are empty and failure is present. For `CANCELLED`,
findings are empty and failure is `NONE`. The observed-resource ref is optional
in all states. `receipt_ref.receipt_digest` hashes the canonical receipt with
`receipt_ref` omitted under `carbon.research-receipt.v2\x00`. Repeated polls
return identical terminal bytes. Task success, failure, cancellation, timeout,
or receipt existence does not mean scientific validity, utility
qualification, security qualification, or official submission outcome.

## 7. Prior lookup and acyclic identity

### 7.1 PriorPack

`PriorPack` canonical bytes contain exactly, in order:

```text
PriorPack(
  schema_version, canonicalization_profile, challenge_key,
  prior_id, prior_version, channel, publication_sequence,
  publication_class, evidence_cutoff_epoch, publication_epoch,
  activation_epoch, interaction_manifest_ref, parameter_catalog_ref,
  prior_policy_bundle_ref, builder_version, predecessor_pack_ref,
  items, disclosure_policy_ref, limitations
)

PriorGuidanceItem(
  item_id, kind, intervention, scope, expected_outcomes, evidence,
  counterevidence_and_applicability, falsification, provenance
)

PriorIntervention(surface_id, action, baseline_ref, from_ref, to_ref)
PriorScope(backbone_refs, context_refs, resource_class_refs)
PriorExpectedOutcome(public_estimand_ref, direction, effect_magnitude_band)
PriorEvidence(
  evidence_origin, epistemic_type, evidence_strength, uncertainty,
  stability, replication, coarse_support, contributor_diversity,
  selection_bias_codes, caveat_codes
)
CounterevidenceEntry(
  public_estimand_ref, finding, scope, evidence_origin, epistemic_type,
  evidence_strength, uncertainty, replication,
  applicability_codes, limitation_codes, caveat_codes
)
Counterevidence(
  ENTRIES(entries) |
  NONE_FOUND(public_search_scope_ref, evidence_cutoff_epoch)
)
PriorFalsification(public_practice_test_refs, public_method_artifact_refs)
PriorProvenance(public_aggregate_publication_refs)
```

`publication_class` is exactly `TEST_ONLY`, `BOOTSTRAP_PUBLIC`, or
`LEARNED_PUBLIC`. The origin ceiling is exact: `TEST_ONLY` permits only
`synthetic_test_fixture`; `BOOTSTRAP_PUBLIC` permits only
`curated_public_science`; `LEARNED_PUBLIC` permits
`qualified_official_aggregate` and optionally `curated_public_science` while
retaining each item's origin. `channel=TEST_ONLY_FIXTURE` requires
`publication_class=TEST_ONLY`; `channel=PUBLIC` requires one of the two public
classes.

`kind` is `STEER`, `AVOID`, `EXPLORE`, or `INSUFFICIENT_EVIDENCE`. `action` is
`ENABLE`, `DISABLE`, `INCREASE_CATALOG_BAND`, `DECREASE_CATALOG_BAND`,
`SUBSTITUTE`, or `COMPARE`. ENABLE/DISABLE require only `baseline_ref`; band
changes require `from_ref` and `to_ref`; SUBSTITUTE requires the exact two
alternatives; COMPARE requires baseline and intervention. Nonapplicable option
fields are `NONE`. `surface_id` must exist in the pinned
`ParameterCatalogRef`; a method artifact is never executable by itself.

Outcome direction is `IMPROVE`, `DEGRADE`, `MIXED`, or `UNRESOLVED`.
Counterevidence finding is `NULL`, `NEGATIVE`, `MIXED`, or `OUT_OF_SCOPE`.
`evidence_origin` is `synthetic_test_fixture`, `curated_public_science`, or
`qualified_official_aggregate`. `epistemic_type` is `observed`, `predictive`,
`causal_candidate`, or `experimentally_supported`. Strength, uncertainty,
stability, replication, support, and diversity use the closed band enum
`VERY_LOW`, `LOW`, `MEDIUM`, `HIGH`, `VERY_HIGH`, or `UNKNOWN`; effect
magnitude is `NONE` or a catalog/public-estimand-owned closed band ref, never a
raw score. Each code tuple has at most 32 canonical identifiers.

Every scope tuple is nonempty or uses the exact singleton
`ALL_REGISTERED_PUBLIC_CONTEXTS`; each has at most 64 refs. Expected outcomes
and counterevidence entries have 1..64 items. An actionable positive item must
use nonempty counterevidence `ENTRIES` or explicit `NONE_FOUND`. Practice tests
and method artifacts have at most 64 refs; aggregate provenance has 1..64
refs. Pack items are sorted by `item_id`, which is unique and carries no rank;
all nested ref tuples sort by canonical ref bytes. Epochs are exact uint64 and
must satisfy `evidence_cutoff_epoch <= publication_epoch <= activation_epoch`.
The later publication-policy owner may impose a positive lag; until that
human-reserved value exists, public activation is unavailable rather than
assuming a lag.

`PriorPack` contains neither an embedded self-hash nor a `PriorPackRef` for
itself. Its identity is exactly:

```text
PriorPackRef.content_hash =
  "sha256:" + lowercase_hex(SHA-256(canonical PriorPack bytes))
```

The content hash is outside its preimage. The ref's challenge, channel, and
sequence must equal the pack. `predecessor_pack_ref` is `NONE` for the first
pack and otherwise must have a lower sequence in the same challenge/channel.
Duplicate or recursive decoding, a content preimage containing its own ref or
hash, a reciprocal predecessor cycle, or a ref/pack mismatch is
`PRIOR_IDENTITY_INVALID`.

### 7.2 Index and transitions

The one canonical genesis previous-index sentinel is the exact tagged union
`PriorPreviousIndex::GENESIS`; it is not text, a null ref, or an all-zero
digest. A non-genesis transition uses
`PriorPreviousIndex::SNAPSHOT(previous_index_snapshot_ref)`.

`PriorIndexSnapshot` contains exactly
`(schema_version, challenge_key, channel, index_sequence,
previous_index, active_prior_pack_ref, index_authorization,
historical_prior_pack_refs, transition_digest)`. `index_authorization` is the
exact union `PUBLIC(PriorPublicationReceiptRef) |
FIXTURE(TestOnlyPriorAuthorizationReceiptRef)`. The historical tuple is
ordered by publication sequence,
contains every earlier pack exactly once, and includes the active pack as its
last item. Publication replaces the entire immutable snapshot atomically.

The proposed transition digest hashes
`carbon.prior-index-transition.v2\x00` plus canonical bytes of
`(challenge_key, channel, proposed_index_sequence, previous_index,
proposed_active_prior_pack_ref, proposed_historical_prior_pack_refs)`. Its
preimage explicitly excludes both `index_authorization` (the public
publication or test-only authorization receipt) and the resulting
`PriorIndexSnapshotRef`. The resulting snapshot digest hashes the complete
snapshot after the transition digest and authorization are inserted. An
authorization receipt binds the already-identified pack and proposed
transition but never the resulting snapshot, preventing a cycle.

### 7.3 Exact and active reads

`EXACT(ref)` resolves the immutable pack by content hash, verifies every ref
field against canonical bytes, and returns the atomic index snapshot that
authorized that pack. Active and superseded packs remain historically
retrievable. A withdrawn pack is not served again; missing or withdrawn exact
content is the public-safe `REFERENCE_NOT_FOUND`.

`ACTIVE(channel)` acquires one atomic snapshot, reads the active ref from it,
then fetches and verifies that pack. If the snapshot changes during the read,
the provider retries the entire read once; a second change is
`PRIOR_INDEX_CHANGED`. It never combines a ref from one snapshot with a pack
from another. A started task stores the exact observed snapshot ref and pack
ref, so subsequent active movement cannot change the run.

Public withdrawal, when later domain authority permits it, creates a new
snapshot with no active pack and prevents new byte service without deleting
historical storage or its receipt. `ACTIVE` with no active ref is
`REFERENCE_NOT_FOUND`. B-07S grants no publication or withdrawal operation to
callers.

## 8. Context and capability separation

The service has two nominal constructor graphs:

```text
ExternalPublicResearchContext(
  challenge_catalog_provider, manifest_provider, public_prior_provider,
  scaffold_provider, validation_provider, compilation_provider,
  prior_alignment_provider, resource_inspection_provider,
  resource_forecast_provider, research_task_provider
)

FixtureResearchContext(
  challenge_catalog_provider, manifest_provider, public_prior_provider,
  test_only_prior_provider, test_only_authorization_provider,
  scaffold_provider, validation_provider, compilation_provider,
  prior_alignment_provider, resource_inspection_provider,
  resource_forecast_provider, research_task_provider
)
```

These exact nominal types are not wire fields. Only
`FixtureResearchContext` can be constructed with `TestOnlyPriorProvider` or
advertise `TEST_ONLY_FIXTURE_PRIOR`. A provider implementing both interfaces,
a caller boolean/label, a generic provider registry, or dynamic context switch
is nonconforming.

An external-public prior result has
`authorization=PUBLIC(PriorPublicationReceiptRef)`, channel `PUBLIC`, and
class `BOOTSTRAP_PUBLIC` or `LEARNED_PUBLIC`; its prior must already possess
that domain-owned public publication authority. A fixture result has channel
`TEST_ONLY_FIXTURE`, class `TEST_ONLY`, every item's origin
`synthetic_test_fixture`, and
`authorization=FIXTURE(TestOnlyPriorAuthorizationReceiptRef)`. The authorization
receipt binds exactly `(challenge_key, prior_pack_ref, fixture_suite_id,
expires_at_micros, authority_ceiling="NOT_UTILITY_QUALIFIED")`; the ref digest
hashes those canonical bytes under
`carbon.test-only-prior-authorization.v2\x00`.

The fixture receipt is never a public `PriorPublicationReceipt` and cannot be
converted into one. Missing, expired, mismatched, public-channel, or
utility/scientific qualification use is `TEST_ONLY_AUTHORITY_INVALID`.
Fixture results and their descendants must display both `TEST_ONLY` and
`NOT_UTILITY_QUALIFIED`; projection may make them more restrictive, never less.

## 9. Composition ownership and conflict classification

| Domain owner | One semantic implementation |
|---|---|
| B-07A | shared nominal v2 wire primitives; challenge discovery and interaction manifest |
| B-07D3 | prior retrieval, immutable index reads, and prior alignment |
| B-07C | mock scaffold and practice execution semantics |
| A2 | strategy validation semantics |
| B-02B | compilation, strategy identity, and resolved training sampling policy |
| B-07E | resource inspection and forecasting |
| B-07B | task records, idempotency, transitions, cancellation, polling, receipts |
| B-07G | constructor composition, qualified dispatch, and conformance only |

B-07G must call the domain owners and cannot reproduce their semantic rules.
The A9 v1 `McpService`, `PriorRef`, and `ScaffoldRef` are `KEEP` in v1; using
them as unqualified v2 types would be `OWNER_CONFLICT`, resolved by distinct
v2 nominals and namespaces. B-02A/B/C, A2, and A7 types above are `KEEP` and
wrapped. The absent exact v2 service types are `IMPLEMENTATION_LAG`, resolved
by later implementation against this specification. No authoritative type is
replaced or duplicated.

## 10. Explicit unavailable seams

The following operations/capabilities return `CAPABILITY_UNAVAILABLE` before
provider execution: `quote_execution`, authenticated remote transport, real
miner/network identity linkage, production signing, production key custody,
production credentials, and a remote listener/network service. No request can
carry fields for them. Bittensor transport, treasury, settlement, weights,
pricing, or production deployment is outside this protocol.

Adding any of these, a wire field, operation, state, error, bound, context, or
identity rule requires a new version and the owning authority. A provider
cannot opt into an extension under `carbon_research_v2`.

## 11. Conformance and negative-boundary matrix

| Boundary | Required negative result |
|---|---|
| unknown operation | `OPERATION_UNSUPPORTED` |
| wrong/merged/unqualified namespace | `NAMESPACE_MISMATCH` |
| v1 official lifecycle request/result under v2 | `NAMESPACE_MISMATCH` |
| collection or bytes above a fixed limit | `BOUND_EXCEEDED` before allocation |
| noncanonical, unknown, duplicate, or trailing representation | `CANONICAL_ENCODING_INVALID` or `UNKNOWN_FIELD` by precedence |
| PriorPack embeds its hash/ref or transition hashes receipt/result ref | `PRIOR_IDENTITY_INVALID` |
| caller supplies context/provider/mode/capability | `CONTEXT_SELECTION_FORBIDDEN` |
| public context requests TEST_ONLY or fixture omits its receipt | `TEST_ONLY_AUTHORITY_INVALID` |
| scientific-control field or alias | `FORBIDDEN_SCIENTIFIC_CONTROL` |
| transition outside section 6.2 | `INVALID_TASK_TRANSITION`, no mutation |
| same idempotency pair, different request digest | `IDEMPOTENCY_CONFLICT`, original unchanged |
| cancellation loses terminal race | unchanged terminal receipt plus `TOO_LATE` disposition |
| reserved future capability | `CAPABILITY_UNAVAILABLE` |
| result contains protected evaluator state | `DISCLOSURE_REJECTED`, no partial result |

The machine-readable block below is normative and must agree with the tables.
Repository conformance validation parses it and tests the properties that can
be ratified without prematurely implementing runtime code.

<!-- B07S-CONFORMANCE-MANIFEST-BEGIN -->
```json
{
  "schema_version": "2.0",
  "namespace": "carbon_research_v2",
  "official_v1_namespace": "carbon_protocol_v1",
  "operations": [
    "get_challenge_info", "get_interaction_manifest", "get_prior",
    "get_mock_scaffold", "dry_validate", "compile_strategy",
    "inspect_prior_alignment", "inspect_resources", "forecast_resources",
    "start_research_task", "get_research_result", "cancel_research_task"
  ],
  "official_v1_operations": ["submit", "get_submission_result"],
  "reserved_operations": ["quote_execution"],
  "operation_contracts": {
    "get_challenge_info": ["GetChallengeInfoRequest", "ChallengeInfo", "B-07A", "ChallengeCatalogProvider", "none"],
    "get_interaction_manifest": ["GetInteractionManifestRequest", "InteractionManifest", "B-07A", "ManifestProvider", "none"],
    "get_prior": ["GetPriorRequest", "PriorLookupResult", "B-07D3", "ContextPriorProvider", "none"],
    "get_mock_scaffold": ["GetMockScaffoldRequest", "MockScaffold", "B-07C", "ScaffoldProvider", "none"],
    "dry_validate": ["DryValidateRequest", "DryValidationResult", "A2", "ValidationProvider", "none"],
    "compile_strategy": ["CompileStrategyRequest", "CompileStrategyResult", "B-02B", "CompilationProvider", "none"],
    "inspect_prior_alignment": ["InspectPriorAlignmentRequest", "PriorAlignmentResult", "B-07D3", "PriorAlignmentProvider", "none"],
    "inspect_resources": ["InspectResourcesRequest", "InspectResourcesResult", "B-07E", "ResourceInspectionProvider", "none"],
    "forecast_resources": ["ForecastResourcesRequest", "ResourceForecast", "B-07E", "ResourceForecastProvider", "none"],
    "start_research_task": ["StartResearchTaskRequest", "StartResearchTaskResult", "B-07B", "ResearchTaskProvider", "create"],
    "get_research_result": ["GetResearchResultRequest", "GetResearchResultResult", "B-07B", "ResearchTaskProvider", "read"],
    "cancel_research_task": ["CancelResearchTaskRequest", "CancelResearchTaskResult", "B-07B", "ResearchTaskProvider", "cancel"]
  },
  "request_fields": {
    "get_challenge_info": ["challenge_key"],
    "get_interaction_manifest": ["challenge_key"],
    "get_prior": ["challenge_key", "selector"],
    "get_mock_scaffold": ["challenge_key", "training_support_ref", "prior_pack_ref"],
    "dry_validate": ["challenge_key", "strategy"],
    "compile_strategy": ["challenge_key", "strategy", "expected_training_support_ref"],
    "inspect_prior_alignment": ["challenge_key", "strategy", "prior_pack_ref"],
    "inspect_resources": ["challenge_key", "strategy", "resource_policy_ref"],
    "forecast_resources": ["challenge_key", "strategy", "resource_policy_ref", "forecast_horizon_seconds"],
    "start_research_task": ["challenge_key", "idempotency_key", "task_spec", "training_support_ref", "prior_selector", "resource_policy_ref", "requested_resource_class_ref", "practice_scope_ref"],
    "get_research_result": ["challenge_key", "task_id", "poll_sequence"],
    "cancel_research_task": ["challenge_key", "task_id", "cancellation_id"]
  },
  "task_states": ["QUEUED", "RUNNING", "CANCEL_REQUESTED", "SUCCEEDED", "FAILED_INFRA", "CANCELLED"],
  "task_kinds": ["RECONSTRUCTION_REHEARSAL", "PRACTICE", "PAIRED_PRACTICE", "RESOURCE_CALIBRATION"],
  "terminal_states": ["SUCCEEDED", "FAILED_INFRA", "CANCELLED"],
  "task_transitions": [
    ["QUEUED", "RUNNING"], ["QUEUED", "CANCELLED"], ["QUEUED", "FAILED_INFRA"],
    ["RUNNING", "CANCEL_REQUESTED"], ["RUNNING", "SUCCEEDED"], ["RUNNING", "FAILED_INFRA"],
    ["CANCEL_REQUESTED", "CANCELLED"], ["CANCEL_REQUESTED", "SUCCEEDED"],
    ["CANCEL_REQUESTED", "FAILED_INFRA"]
  ],
  "error_precedence": [
    "canonical", "namespace", "operation", "request_type", "bounds",
    "capability", "reference", "state", "provider", "disclosure"
  ],
  "errors": [
    "CANONICAL_ENCODING_INVALID", "NAMESPACE_MISMATCH", "OPERATION_UNSUPPORTED",
    "REQUEST_TYPE_INVALID", "UNKNOWN_FIELD", "BOUND_EXCEEDED",
    "FORBIDDEN_SCIENTIFIC_CONTROL", "CONTEXT_SELECTION_FORBIDDEN",
    "CAPABILITY_UNAVAILABLE", "CHALLENGE_NOT_FOUND", "REFERENCE_NOT_FOUND",
    "REFERENCE_MISMATCH", "PRIOR_INDEX_CHANGED", "PRIOR_IDENTITY_INVALID",
    "TEST_ONLY_AUTHORITY_INVALID", "TASK_NOT_FOUND", "IDEMPOTENCY_CONFLICT",
    "INVALID_TASK_TRANSITION", "POLL_SEQUENCE_INVALID", "PROVIDER_UNAVAILABLE",
    "INFRASTRUCTURE_FAILURE", "DISCLOSURE_REJECTED", "INTERNAL_FAILURE"
  ],
  "forbidden_control_fields": [
    "raw_data", "custom_data", "dataset", "data_path", "filesystem_path",
    "path", "uri", "url", "seed", "seeds", "official_seed", "P", "Q", "w",
    "stress_set", "reference", "truth", "gate", "scorer", "execution_context",
    "context", "provider", "evidence_class", "qualification_label", "mode",
    "credential", "credentials", "key", "private_key", "signing_key",
    "listener", "address", "port"
  ],
  "limits": {
    "canonical_call_reply_bytes": 1048576,
    "canonical_resource_bytes": 8388608,
    "nesting_depth": 32,
    "default_tuple_items": 4096,
    "prior_pack_items": 256,
    "finding_items": 256,
    "task_polls": 10000
  },
  "prior_identity": {
    "publication_classes": ["TEST_ONLY", "BOOTSTRAP_PUBLIC", "LEARNED_PUBLIC"],
    "genesis_previous_index": "PriorPreviousIndex::GENESIS",
    "pack_hash": "SHA-256(canonical PriorPack bytes without self-hash or PriorPackRef)",
    "transition_digest_excludes": ["publication_receipt", "resulting_index_ref"]
  },
  "contexts": {
    "external": "ExternalPublicResearchContext",
    "fixture": "FixtureResearchContext",
    "fixture_only_capability": "TEST_ONLY_FIXTURE_PRIOR",
    "fixture_ceiling": ["TEST_ONLY", "NOT_UTILITY_QUALIFIED"]
  },
  "maturity": {
    "specified": true,
    "ratified": true,
    "implemented": false,
    "scientifically_qualified": false,
    "security_qualified": false,
    "network_qualified": false,
    "production_qualified": false,
    "live": false
  }
}
```
<!-- B07S-CONFORMANCE-MANIFEST-END -->

## 12. Ratification decisions and change authority

- **B-07S-D1:** exact namespaces and the closed v2 vocabulary prevent official
  lifecycle mixing. Superseding it requires the A9 and B-07 service owners.
- **B-07S-D2:** existing domain refs and identities are kept; v2 adds only
  missing nominal wire wrappers with closed canonical bounds. Superseding a
  kept ref belongs to its original domain owner.
- **B-07S-D3:** the linearizable idempotency/state/cancellation/polling model
  separates infrastructure and task facts from scientific outcome. B-07B owns
  its later implementation; a state change requires B-07B plus protocol
  version authority.
- **B-07S-D4:** PriorPack hashes exclude their own ref/hash, transition hashes
  exclude publication receipt and resulting index ref, and genesis uses one
  tagged sentinel. B-07D3 owns implementation; publication authority remains
  separately reserved.
- **B-07S-D5:** constructor-nominal contexts structurally isolate fixture
  capability and bind TEST_ONLY results to a non-public authorization receipt
  with the `NOT_UTILITY_QUALIFIED` ceiling.
- **B-07S-D6:** semantic ownership is single-source; B-07G composes and checks
  but cannot become a second implementation layer.

No unresolved human input is needed to implement this local v2 protocol.
Human-reserved scientific values, security acceptance, public publication
policy, rights/legal determinations, economics, real identity, production
signing/custody, transport, qualification, launch, and LIVE authority remain
unavailable and must fail closed. This document may be superseded only by a
new normative version that names the owning authority, migration path, and
smallest affected interfaces; silent provider variation is forbidden.
