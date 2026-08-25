# Miner MCP Specification — bounded Wave-A contract and deferred full loop

Status: **A9 bounded Wave-A contract ratified; exact in-process implementation merged on current `main`**<br>
Version: **2.3**<br>
Authority: `CONSTITUTION.md`, `.agent/INVARIANTS.md`, `.agent/DECISIONS.md`, and the governing A2, A3, A6, A7, and A8 contracts<br>
Implementation maturity: **implemented and tested only for the recorded bounded engineering scope; not scientifically qualified, security qualified, network qualified, commercially validated, or production qualified**

This specification replaced the earlier aspirational MCP sketch with the
ratified bounded Wave-A contract. The exact seven-tool in-process implementation
is merged on current `main`. Full transport, authentication, production
providers and policy, mock/light execution, adaptive-query qualification, and
the end-to-end research loop remain deferred. The merged implementation adds no
network protocol, ranking, or scientific-quality claim.

## 1. Scope and wave boundary

Miner MCP is split into two deliberately separate lanes.

### Wave A — control and disclosure

Wave A exposes exactly seven in-process service tools:

| Tool | Request | Successful result | Canonical authority |
|---|---|---|---|
| `get_challenge_info` | `GetChallengeInfoRequest` | `ChallengeInfo` | A3 registry |
| `get_prior` | `GetPriorRequest` | `PublishedPrior` | injected prior provider |
| `get_mock_scaffold` | `GetMockScaffoldRequest` | `PublishedScaffold` | injected scaffold provider plus A2 validation |
| `dry_validate` | `DryValidateRequest` | `DryValidateResponse` | A2 `dry_validate` |
| `estimate` | `EstimateRequest` | `StructuralEstimate` | A2 validation; injected estimate provider only for exact `ok=True` |
| `submit` | `SubmitRequest` | `SubmitReceipt` | A7 `SubmissionService` |
| `get_submission_result` | `GetSubmissionResultRequest` | `SubmissionResult` | A7 `SubmissionService` plus query budget gate |

There are no aliases. In particular, `light_compare`, `light_train`, and
`list_my_submissions` are unavailable. Unknown tool names fail closed as
`mcp.tool_unavailable`.

Wave A is an application/service boundary, not a network protocol. Transport,
serialization, process hosting, discovery, and authentication are outside this
contract.

### Wave B — explicitly deferred

Wave B may define `MockExecutionRequest`, `MockRunOutcome`,
`MockTrainEvalService.run_mock`, mock packs and resources, execution disclosure,
adaptive-loop evidence, and any light comparison or light training surface.
None of those names or behaviors exists in Wave A.

A8-R15 remains binding for every execution-dependent claim. Wave A's
`estimate` tool is a pure structural prior operation; it does not execute a
strategy, call A4/A5/A8, produce an `EvaluationCard`, or predict scientific
quality. That separation is a **NO_CONFLICT** with A8-R15, not a waiver of it.

## 2. Module and service surface

The merged bounded Wave-A implementation is confined to:

- `carbon/mcp/__init__.py`
- `carbon/mcp/model.py`
- `carbon/mcp/providers.py`
- `carbon/mcp/service.py`
- `tests/cpu/test_mcp_skeleton.py`

The service contract is:

```python
McpService(
    registry: ChallengeRegistry,
    submission_service: SubmissionService,
    resource_limits: McpResourceLimits,
    query_budget_gate: QueryBudgetGate,
    prior_provider: PriorProvider | None,
    scaffold_provider: ScaffoldProvider | None,
    estimate_provider: EstimateProvider | None,
)

McpService.call(
    call: McpCall,
    requester_identity: RequesterIdentity,
) -> (
    ChallengeInfo | PublishedPrior | PublishedScaffold |
    DryValidateResponse | StructuralEstimate | SubmitReceipt |
    SubmissionResult
)
```

`ChallengeRegistry`, `SubmissionService`, and `RequesterIdentity` are the exact
canonical types already owned by their source layers. MCP does not shadow or
wrap them. `RequesterIdentity` is supplied out of band and never appears in a
caller-controlled request payload.

Trusted composition must supply the same exact `ChallengeRegistry` instance
used to construct the injected `SubmissionService`. MCP cannot inspect A7's
private registry or repair a mismatched composition. A successful call returns
only the closed union above; a failed call raises exactly one fixed public A9
error.

`McpCall` has schema version `"1.0"`, a raw exact-string `tool` field, and an
ordered tuple of `McpField` entries. Every successful top-level result has
schema version `"1.0"`; failures use one of the closed typed errors below.
Duplicate, unknown, or missing request fields are invalid, and inputs are not
coerced. Retaining field order makes duplicates observable before any unique
field mapping is constructed.

Every data-bearing A9 nominal model, request, response, and reference named in
this specification is exact, frozen, and slotted; both enum domains are exact
and closed. Each error is an exact nominal, slot-declared exception with a
frozen public contract payload: zero-argument construction, literal-backed
read-only `code` and fixed message/arguments, and no supported diagnostic
fields. This does not claim that Python removes inherited `BaseException`
runtime metadata such as traceback, context, cause, or its implementation
dictionary. Public boundaries require the exact type and reject subclasses.
Outputs are fresh bounded positive projections; MCP never releases a caller or
provider alias.

`McpField` and `McpCall` are deliberately storage-only raw-envelope nominals.
Their constructors freeze and retain the supplied references without eager
type, schema, field-name, duplicate, resource, or semantic validation. This is
what lets an exact top-level `McpCall` containing malformed framing reach
`McpService.call`, acquire its permit, and follow the single ordering below;
callers need no object-forging path. `McpService.call` alone exact-type checks
the outer classes and owns every framing/capture check.

The tool-to-result mapping is closed and exhaustive:

| Exact tool | Exact request fields | Exact result |
|---|---|---|
| `get_challenge_info` | `challenge_id`, `challenge_version` | `ChallengeInfo` |
| `get_prior` | `challenge_id`, `challenge_version` | `PublishedPrior` |
| `get_mock_scaffold` | `challenge_id`, `challenge_version`, optional `scaffold_id` | `PublishedScaffold` |
| `dry_validate` | `strategy` | `DryValidateResponse` |
| `estimate` | `challenge_id`, `challenge_version`, `strategy` | `StructuralEstimate` |
| `submit` | `challenge_id`, `challenge_version`, `strategy` | `SubmitReceipt` |
| `get_submission_result` | `submission_id` | `SubmissionResult` |

An optional `scaffold_id` is either absent or a canonical token; an explicit
null is not an alias for absence.

## 3. Capture and resource limits

Wave A accepts only an already-decoded, bounded value graph. Capture recognizes
the exact built-ins `None`, `bool`, `int`, finite `float`, `str`, `list`, and
`dict`. It rejects subclasses, tuples, sets, custom mappings, custom iterables,
non-finite floats, and other host objects without calling their `repr`, `str`,
iteration, equality, hashing, descriptors, or user code.

Dictionary keys may be only exact scalar built-ins during capture. Their
domain-specific validity remains owned by A2/A7; MCP must not silently convert
non-string strategy keys. Capture creates a fresh detached graph while
preserving list/dict topology, including shared aliases and cycles. A visited
identity table and iterative accounting make cyclic and aliased graphs bounded
and deterministic.

`McpResourceLimits` contains exactly these required positive unsigned-64-bit
integer fields, with no contract defaults:

1. `max_call_fields`
2. `max_total_request_value_nodes`
3. `max_request_object_members`
4. `max_request_list_items`
5. `max_request_string_utf8_bytes`
6. `max_request_object_key_utf8_bytes`
7. `max_request_integer_bits`
8. `max_total_request_utf8_bytes`
9. `max_total_response_value_nodes`
10. `max_response_sequence_items`
11. `max_response_string_utf8_bytes`
12. `max_response_integer_bits`
13. `max_total_response_utf8_bytes`
14. `max_concurrent_calls`

Request bounds are checked before any domain service or provider is invoked.
Response bounds are checked before a result is released. Concurrent admission
is fail-closed. Any breached resource bound maps to the fixed
`mcp.resource_limit_exceeded` error.

After exact top-level `McpCall` and requester type checks, every call acquires
one concurrency permit before any other framing, tool, field, value, provider,
or owner work; this includes malformed and unknown-tool calls. The permit is
held through response projection or error translation and released in
`finally`.

Inside the permit, structural framing first validates the schema/tool types and
the exact fields-tuple type. It then checks `len(fields)` against
`max_call_fields` before scanning any entry. Schema/tool framing strings are
metered before use, and only then is the schema value required to equal exact
`"1.0"`. Each now-bounded entry is checked in tuple order: exact `McpField`
type, exact string name, that name's framing UTF-8 meters, then duplicate
detection. This bounds every scan and every string hash/equality operation. An
exact-string unknown/deferred tool is then unavailable without a semantic
field schema or value capture. Only known tools are checked for missing/unknown
semantic fields before their values are captured.

Each call-field value root is one request node. On first expansion of a
distinct list/dict, every list item or dict member value adds one node. Alias
and cycle edges are charged by container cardinality, while a seen container's
children are not expanded twice; dict keys are not nodes. Object/list limits
apply per first-seen container. Exact `int.bit_length` meters every exact int
occurrence, including scalar keys and excluding bool.

Request per-string width covers schema version, tool, field names, graph
strings, and string dict keys; the key width also applies to every string dict
key; total request UTF-8 is their logical-occurrence sum. A strict code-point
scan charges a surrogate one byte solely to stay bounded and marks the request
invalid. A resource breach encountered first remains a resource error.

Response accounting starts with one top-level node, then one for every nominal
field, sequence item, and dict member value on first container expansion.
Only exact closed A9/owner nominals/enums and exact permitted
`None`/bool/int/finite-float/string/tuple/list/dict field values are
traversable; another type/subclass is integration failure. Sequence limits
apply per tuple/list. Response string and total UTF-8 meters
cover string values and dict keys; response integer width is exact
`int.bit_length` for every exact int value or scalar dict key, excluding bool.
An exact string enum is one value node and its exact `.value` is charged as a
response string. The same bounded one-byte surrogate handling marks response
text invalid. Response dict cardinality must fit the remaining total-node
meter before copy.

Valid-shape response-meter breach is `mcp.resource_limit_exceeded`. Within
those meters, malformed, subclassed, unstable, invalid-UTF-8, or cross-bound
provider output is `mcp.integration_failure`. Traversal uses exact
call-field-tuple, list/tuple-index, built-in-dict-insertion, declared
nominal-field, and provider-sequence order; the first condition encountered
controls. Positive projection detaches provider ownership while preserving
valid internal graph topology.

`DryValidateRequest`, `EstimateRequest`, and `SubmitRequest` preserve the same
freshly owned resource-admissible supported exact-built-in graph as
`strategy`, because A2 and A7 own rejection of invalid root types. Transport
capture may reject out-of-domain or over-limit values, but A9 does not require
an estimate Strategy dictionary root. Exact A2 validation, not transport,
controls whether the estimate provider may receive the graph.

## 4. Challenge information

`get_challenge_info` performs an exact `ChallengeKey` lookup through
`ChallengeRegistry.load`. It does not scan or list the registry and adds no
second challenge-admission policy.

The minimal successful `ChallengeInfo` projection contains only:

- schema version `"1.0"`;
- exact `challenge_key`;
- exact `lifecycle_status`;
- exact `fixture_origin`;
- exact `effectively_live`; and
- exact `allowed_backbones`.

An exact loaded `draft` record is unavailable and maps to
`mcp.challenge_unavailable`. An exact loaded `fixture` record is visible only
when it has exact lifecycle status `fixture`, `fixture_origin is True`, and
exact A3 `ChallengeRegistry.assess_live_eligibility(challenge_id, version,
fixture_mode=True).eligible is True`; its `effectively_live` is exact `False`.
A false fixture assessment is unavailable without exposing its reasons. An
exact loaded `live` record is visible and its `effectively_live` is supplied
only by the exact A3 `is_effectively_live` result; it may be false. Successful
`lifecycle_status` is therefore `fixture` or `live`. MCP discloses no artifact
path or digest, qualification reference,
qualification evidence or private reason, backend-profile evidence, receipt
evidence, fee value, Score Pack or generator hash, active mock-pack ID, mock
range, tag or disclosure catalog, seed, context, challenge payload, hidden
fixture content, leaderboard, or submission history.

Missing keys, canonical A3 load failures, malformed or unknown-lifecycle
records, inconsistent fixtures, and other internally inconsistent records map
to the fixed
`mcp.challenge_unavailable` response. Unexpected integration failures map to
`mcp.integration_failure` without disclosing exception text.

## 5. Prior publication

`get_prior` first checks that the injected `PriorProvider` is configured, then
establishes exact-key public Challenge visibility and calls that provider
exactly once. If no provider is configured, the tool is unavailable.

The closed prior types are:

```python
PriorRef(
    challenge_key: ChallengeKey,
    prior_id: str,       # exact bounded canonical token
    prior_version: str,  # exact version token
    content_hash: str,   # exact tagged lowercase SHA-256
)

PriorDirectiveKind = {
    STRUCTURAL_STEER: "structural_steer",
    AVOID: "avoid",
    EXPLORE: "explore",
    NOT_INCLUDED: "not_included",
}

PriorDirective(
    kind: PriorDirectiveKind,
    subject: str,              # exact bounded canonical token
    tokens: tuple[str, ...],   # exact bounded canonical tokens
)

PublishedPrior(
    schema_version: Literal["1.0"],
    prior_ref: PriorRef,
    directives: tuple[PriorDirective, ...],
)
```

Directives retain provider order and are duplicate-free. MCP validates the
closed syntax, exact challenge binding, canonical identifiers, and tagged
SHA-256 form. The content hash is provider-owned prior identity; Wave A does
not invent canonical prior bytes or a second prior store.

Every `canonical token` is an exact built-in `str` accepted without
normalization by public A3
`validate_canonical_identifier(value, field_name)`; MCP string and aggregate
UTF-8 limits supply its size bound. Every `version token` is an exact built-in
`str` accepted without normalization by A3 `validate_version`.

The directive vocabulary is structural and non-numeric. A prior contains no
Strategy, free text, numeric weight vector, hyperparameter recipe, champion
identity, champion weights, official score, rank, fee, seed, pack identity, or
emission field. It also carries no hidden outcome, `EvaluationCard` field,
gate decision, training label, or execution claim. `not_included` is an
explicit disclosure statement, not an implicit zero score.

Provider presence is checked before Challenge lookup. Absence is
`mcp.tool_unavailable`; malformed, subclassed, unstable, or cross-bound
provider output within response meters and provider exceptions are
`mcp.integration_failure`; a response-meter breach is
`mcp.resource_limit_exceeded`.

## 6. Mock scaffold publication

The name `get_mock_scaffold` publishes a static starter strategy; it does not
run a mock. It checks provider presence, establishes exact-key public Challenge
visibility, then calls the injected scaffold provider exactly once.

```python
ScaffoldRef(
    challenge_key: ChallengeKey,
    scaffold_id: str,       # exact bounded canonical token
    scaffold_version: str,  # exact version token
    content_hash: str,      # exact tagged lowercase SHA-256
)

PublishedScaffold(
    schema_version: Literal["1.0"],
    scaffold_ref: ScaffoldRef,
    strategy: dict,
    informed_by_prior: PriorRef | None,
    execution_deferred: Literal[True],
)
```

The strategy is a fresh detached exact built-in dictionary, passes canonical
A2 `dry_validate`, and binds to the requested challenge ID. MCP verifies this
by calling canonical `carbon.schema.dry_validate` exactly once on the detached
returned Strategy and requiring exact `ok=True`; it never trusts a provider
claim or recreates validation, and non-`ok` is provider integration failure.
If present, the prior reference binds to the same challenge key. Provider
output order and identity are preserved; caller-supplied or provider aliases
never escape.

When the request supplies `scaffold_id`, the returned
`scaffold_ref.scaffold_id` must equal it exactly. When the selector is absent,
the provider owns selection of the returned canonical ID.

The scaffold is not executed. It carries no claim that it is scientific,
representative, mediocre, competitive, safe, or a non-champion. Its hash is
provider-owned identity, not an MCP-defined byte encoding.

MCP does not fill a prior omission, derive the scaffold from a prior, make an
inert A2 parameter executable, or call A8. The optional prior reference is
metadata only.

Provider absence is `mcp.tool_unavailable`; invalid provider output within
response meters and provider exceptions are `mcp.integration_failure`; a
response-meter breach is `mcp.resource_limit_exceeded`.

## 7. Dry validation and structural estimate

`dry_validate` calls canonical A2 `dry_validate` exactly once and returns its
exact `ValidationResult` in `DryValidateResponse`. MCP adds no validator,
rewrites no issue, and makes no execution or admission claim.

`estimate` first checks both provider slots, establishes exact-key public
Challenge visibility, obtains and validates the exact public prior, and calls
public `carbon.schema.dry_validate` exactly once on the captured supported
exact-built-in graph. Its closed result is:

```python
StructuralEstimate(
    schema_version: Literal["1.0"],
    challenge_key: ChallengeKey,
    prior_ref: PriorRef,
    validation: ValidationResult,
    applicable_directives: tuple[PriorDirective, ...],
    disclaimer: Literal["non_binding_structural_prior_only"],
)
```

The returned validation object is the exact A2 result owned by this call.
Applicable directives are an order-preserving, duplicate-free subset of the
referenced published prior. The estimate has no numeric quality, probability,
score, rank, `EvaluationCard`, gate status, cost, weight, or emission estimate.
It is non-binding and cannot admit, reject, start, execute, or publish a
submission.

When the exact A2 result has `ok=False`, A9 does not call
`EstimateProvider`. It returns an A9-owned bounded result with the exact
ChallengeKey, exact public PriorRef, exact owned A2 validation,
`applicable_directives=()`, and exact disclaimer
`"non_binding_structural_prior_only"`. That branch performs no execution or
additional structural interpretation.

If and only if the exact A2 result has `ok=True`, the Strategy is an exact
A2-valid dictionary and A9 calls `EstimateProvider` exactly once. The provider
never receives a non-object, A2-invalid, cyclic, invalid-key, or invalid-value
Strategy, or a ValidationResult with `ok=False`. Its output must preserve the
exact `ok=True` validation, Challenge/prior binding, ordered directive-subset,
disclaimer, response bounds, and all non-execution/non-oracle rules.

The estimate uses no `MockContext`, A8 service, fixture-official context,
official or fixture Score Pack, `ScoreInput`, or `InternalResult` and performs
no execution. It returns no predicted official score, predicted card status,
or predicted gate result.

Absence of either required provider is `mcp.tool_unavailable`; malformed,
cross-bound, or validation-substituting output within response meters and
provider exceptions are `mcp.integration_failure`; a response-meter breach is
`mcp.resource_limit_exceeded`.

## 8. Submission

Before any A7 call, `submit` preflights the maximum valid canonical
`SubmitReceipt` against the injected response limits. That finite envelope is
computed only from the closed nominal topology, schema literal `"1.0"`, the
fixed 36-byte UUIDv4 `SubmissionId`, and the longest closed
`SubmissionState.value`; it does not mint an ID, inspect A7 state, or call a
provider/owner. Unless every canonical receipt fits every applicable response
meter, the call fails as resource and A7 is untouched.

After that preflight, `submit` delegates the captured graph directly to
canonical A7 `SubmissionService.submit`, then calls `get_status` for the
returned ID. MCP does not prevalidate the Strategy, reserve an ID, mutate the
strategy, or add an admission state. The preflight guarantees a well-formed
canonical status cannot create a post-submit response-meter failure.

`SubmitReceipt` contains only schema version `"1.0"` and the exact A7
`SubmissionStatusView`; that status already carries the canonical submission
ID. It is only an A7 lifecycle acknowledgement, not proof of queueing,
acceptance, payment, provenance, execution, official score, scientific
validity, rank, weight, or emission.

MCP never calls A7 `mark_validated`, either admission method, fee-start,
retry, cancellation, execution, completion, or publication, and never calls an
A6 storage method.

This preserves A7 behavior:

- invalid submissions may receive an ID and be `REJECTED`;
- accepted submissions begin `RECEIVED`, not queued or running;
- an open accepted duplicate may return the existing submission ID; and
- a terminal or rejected resubmission may receive a fresh ID.

A malformed status or other integration failure in post-submit status read or
projection—including not-found or authorization for the just-returned internal
ID/requester pair—is `mcp.integration_failure`; MCP does not retry or compensate
after A7 has created or reused the submission. That fail-closed trusted-
integration case is distinct from response capacity, which was rejected before
mutation. Submission-unavailable collapse applies only to the caller-supplied
ID of `get_submission_result`.

## 9. Submission result and query budget

`get_submission_result` is the only Wave-A result-polling tool. Every
resource-valid call invokes `QueryBudgetGate.consume` with the exact owned
requester and `McpTool.GET_SUBMISSION_RESULT` before any A7 lookup. The service
captures the return and requires it to be exact `None`; any other return is an
integration failure and no A7 lookup occurs. An exact gate-raised
`McpQueryBudgetError` is translated without chaining to a fresh fixed
`McpQueryBudgetError`; every other gate failure is
`mcp.integration_failure`. There is no budget refund after a successful
consume for any later outcome, including a missing, unauthorized, nonterminal,
failed, or rejected submission or a response-meter/projection/integration
failure.

After budget consumption, MCP calls A7 `get_status`. It calls
`read_published` only when the exact state is `PUBLISHED`. The closed result
contains schema version `"1.0"`, the exact A7 status, and:

- the exact canonical A6 `EvaluationCard` when published; or
- `None` in every other state.

MCP has no result cache, polling history, card store, submission mirror, or
second lifecycle. It never constructs, repairs, enriches, redacts, or
reinterprets an `EvaluationCard`.

The result exposes no `StrategyHash`, private stored `ChallengeKey`, attempt
history, fee record, retry count, execution handle, `SeedPin`, environment pin,
private failure cause, `InternalResult`, private A6/A7 record, fine score
detail, margin, stress breakdown, private/free-form diagnostic content, or
timestamp not supplied by an owner API. The exact A6 `public_diagnostics`
field remains present and canonically empty.

Canonical not-found and requester-mismatch outcomes collapse to the same fixed
`mcp.submission_unavailable` response. Requester equality is a structural
binding check inherited from A7, not an authentication guarantee.

## 10. Closed errors

Every public failure is one of these exact code/message pairs:

| Error type | Code | Fixed public message |
|---|---|---|
| `McpRequestError` | `mcp.request.invalid` | `MCP request is invalid.` |
| `McpResourceError` | `mcp.resource_limit_exceeded` | `MCP resource limit was exceeded.` |
| `McpToolUnavailableError` | `mcp.tool_unavailable` | `MCP tool is unavailable.` |
| `McpChallengeUnavailableError` | `mcp.challenge_unavailable` | `Challenge is unavailable.` |
| `McpSubmissionUnavailableError` | `mcp.submission_unavailable` | `Submission is unavailable.` |
| `McpQueryBudgetError` | `mcp.query_budget_exceeded` | `MCP query budget was exceeded.` |
| `McpIntegrationError` | `mcp.integration_failure` | `MCP integration failed.` |

These seven rows are seven distinct exact nominal, slot-declared exception
types. Their supported public code/message/argument payload is fixed at
zero-argument construction and exposes no diagnostic field; public translation
constructs only the exact listed type, never a subclass. Interpreter-maintained
exception runtime state is not part of the A9 payload or immutability claim.

No raw exception, representation, traceback, provider detail, hidden
identifier, authorization distinction, or value-derived dynamic text crosses
the boundary. Public translation suppresses exception chaining, and no public
error accepts caller-supplied diagnostics.

After exact top-level call/requester type checks, concurrency admission
precedes all remaining conditions. Within an admitted call, deterministic
precedence is:

1. concurrency exhaustion → resource;
2. malformed schema/tool type or fields-tuple type → request;
3. `max_call_fields` breach → resource;
4. schema/tool framing limit breach, or otherwise invalid framing text → resource or request, respectively;
5. schema-version value other than exact `"1.0"` → request;
6. malformed bounded field entry/name type → request;
7. field-name framing limit breach, or otherwise invalid framing text → resource or request, respectively;
8. duplicate field name → request;
9. exact-string deferred/unknown tool → tool unavailable;
10. known-tool missing/unknown semantic field → request;
11. request-capture resource breach → resource;
12. decoded scalar syntax → request;
13. submit maximum-receipt preflight breach → resource before A7;
14. unconfigured optional provider → tool unavailable;
15. missing/malformed challenge, draft record, inconsistent fixture, unknown lifecycle, or other internal inconsistency → challenge unavailable;
16. result-poll budget exhaustion or non-exact-`None` gate return → query budget or integration, respectively;
17. result-poll missing or requester-mismatched submission → submission unavailable;
18. response-meter or canonical A7 resource/capacity breach → resource;
19. malformed canonical/provider output or unexpected dependency failure → integration.

## 11. Provider interfaces and state ownership

The three optional providers have these exact responsibilities:

```python
class PriorProvider(Protocol):
    def get_prior(self, challenge_key: ChallengeKey) -> PublishedPrior: ...

class ScaffoldProvider(Protocol):
    def get_scaffold(
        self,
        challenge_key: ChallengeKey,
        scaffold_id: str | None,
    ) -> PublishedScaffold: ...

class EstimateProvider(Protocol):
    def estimate(
        self,
        challenge_key: ChallengeKey,
        prior: PublishedPrior,
        strategy: dict,  # owned exact A2-valid Strategy
        validation: ValidationResult,  # exact result with ok=True
    ) -> StructuralEstimate: ...

class QueryBudgetGate(Protocol):
    def consume(self, requester: RequesterIdentity, tool: McpTool) -> None: ...
```

Providers own their data and identity. They do not gain access to the
submission service through MCP. A9 adds no database, cache, filesystem store,
mutable history, list endpoint, or background worker.

The estimate-provider protocol is valid-path-only. A9 invokes it once only
after exact A2 `ok=True`; every captured exact A2-invalid estimate is
constructed by A9 with empty directives and never reaches the provider.

Source dependencies are limited to the standard library and the minimum
public A2, A3, A6 model, and A7 APIs. A9 must not source-import A4 context or
secret types, A5 scoring models or engine, A6 stores, A7 stores, A8, A10–A12,
legacy miner or Landscape code, PoC or neurons, an MCP SDK, HTTP framework,
Bittensor, Torch, JAX, NumPy, chain/weight/emission code, or another
optional-heavy dependency. No network server belongs to Wave A.

The root `carbon.mcp` export surface is exactly:

`ChallengeInfo`, `DryValidateRequest`, `DryValidateResponse`,
`EstimateProvider`, `EstimateRequest`, `GetChallengeInfoRequest`,
`GetMockScaffoldRequest`, `GetPriorRequest`, `GetSubmissionResultRequest`,
`McpCall`, `McpChallengeUnavailableError`, `McpField`, `McpIntegrationError`,
`McpQueryBudgetError`, `McpRequestError`, `McpResourceError`,
`McpResourceLimits`, `McpService`, `McpSubmissionUnavailableError`, `McpTool`,
`McpToolUnavailableError`, `PriorDirective`, `PriorDirectiveKind`,
`PriorProvider`, `PriorRef`, `PublishedPrior`, `PublishedScaffold`,
`QueryBudgetGate`, `ScaffoldProvider`, `ScaffoldRef`, `StructuralEstimate`,
`SubmissionResult`, `SubmitReceipt`, and `SubmitRequest`.

The merged implementation preserves this exact export surface; this document
does not create or broaden it.

The sole canonical focused test is
`tests/cpu/test_mcp_skeleton.py`. Its acceptance matrix is recorded in the A9
ticket and plan and covers exact types, call fields,
resource/response bounds, hostile objects, stable errors, upstream delegation,
standalone `DryValidateResponse` delegation/reconstruction, resource-admissible
supported exact-built-in non-dict `strategy.type` inside `StructuralEstimate`,
invalid field/key/value and cyclic estimate results, empty invalid directives,
zero invalid provider calls, one valid provider call, provider and leakage
failures, draft unavailability, fixture visibility only with exact
`fixture_origin is True` and an exact true A3 fixture assessment, loadable-but-
false fixture-assessment unavailability, effective-live true/false, no
enumeration, mock/light rejection, A7 lifecycle behavior, all-state requester-
bound polling, published-only cards, dependency/export isolation, installed-
wheel import, full CPU regression, Ruff, Black, and no-new-debt checks.
Existing A0–A8 regressions are not A9 test evidence.

## 12. Deferred full-loop and release posture

The broader discover → prior → scaffold → mock → compare → train → submit →
inspect loop remains design intent, not Wave-A scope. Before any Wave-B work,
the owners must separately ratify:

- mock evaluator semantics and resources;
- deterministic execution and evidence disclosure;
- comparison and training request/result schemas;
- adaptive-budget and leakage controls;
- authentication and transport boundaries;
- Launch Bar metrics, including real-user success and quality thresholds; and
- the A8-R15 execution-dependent resource path.

The bounded Wave-A implementation records no owner decision on those deferred
matters and does not satisfy a Launch Bar checkbox.

## 13. Ratification and maturity

At candidate publication (historical):

- exact Wave-A contract: **documentation candidate; not specified/ratified until independent review, explicit human authorization, and merge**;
- implementation: **NO**;
- tests: **NO**;
- qualification or scientific evidence: **NO**;
- A9 wave ticket: **todo**;
- A10, A11, and A12: **todo**.

That candidate was independently reviewed, explicitly human-authorized, and
merged, making the exact bounded Wave-A contract ratified. The separately
authorized in-process implementation and its reviewed test-proof repairs are
also merged on current `main`.

Current bounded maturity:

- exact Wave-A contract: **specified and ratified**;
- exact seven-tool in-process control/disclosure implementation: **YES**;
- tests: **YES only for the recorded CPU, hostile-input, resource,
  concurrency, disclosure, dependency, import, wheel, and quality engineering
  scope**;
- scientific, security, network, commercial, or production qualification:
  **NO**;
- A9 wave ticket: **done only after its closeout is independently reviewed,
  explicitly human-authorized, and merged**;
- A10, A11, and A12: **todo**.

Transport, authentication, production providers and policy, mock/light
execution, adaptive-query qualification, and end-to-end loop integration remain
separately authorized future work.
