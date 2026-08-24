# A9 Miner MCP bounded Wave-A control plane — pre-implementation plan

**Ticket:** A9 — bounded Miner MCP control/disclosure skeleton

**Ratification branch:** `agent/a9-contract-ratification`

**Ratification starting main:**
`adcf0578052bba2c0cf9aa24e7a07ebfe87ca46d`

**Ratification starting tree:**
`c41119356ce811b2186a19dd2906e29e443fecf2`

**Candidate status:** documentation only. This candidate adds no A9 source,
test, fixture, provider publication, dependency, packaging, CI, quality
baseline, server, network adapter, or later-ticket implementation.

```text
A9 EXACT BOUNDED CONTRACT: specified and ratified only after independent
review, explicit human authorization, and merge of this candidate
A9 IMPLEMENTED: NO
A9 TESTED: NO
A9 SCIENTIFICALLY_QUALIFIED: NO
A9 SECURITY_QUALIFIED: NO
A9 NETWORK_QUALIFIED: NO
A9 COMMERCIALLY_VALIDATED: NO
A9 PRODUCTION_QUALIFIED: NO
A9 WAVE STATUS: todo
A10--A12: todo
```

This plan is not implementation authority before merge. After ratification, a
separate explicitly authorized implementation task must re-fetch current
`main`, verify the ratification topology and green CI, prove A9 remains `todo`
and unimplemented, and only then mark A9 `in_progress`. Every implementation
criterion in the A9 ticket remains unchecked in this candidate.

## Repository gate

- Fresh fetch/prune resolved `origin/main` to the exact starting commit/tree
  above, subject `Merge pull request #31 from
  carbonphysicsai/agent/a8-closeout`.
- Ordered parents are exact A8 corrective merge
  `b30c3f5fc2a53df0611d5e8b80120fbf4b64531c` followed by exact PR #31 head
  `7ab627f027675960622c2e147095ce92822f15c2`.
- GitHub reports PR #31 merged normally as the starting commit. Its exact head
  is parent two; head and merge tree are both
  `c41119356ce811b2186a19dd2906e29e443fecf2`, and the head-to-merge diff is
  empty. GitHub reports no formal review objects/comments or review decision,
  so this candidate verifies the head/parent/tree fact without inventing a
  formal GitHub review event.
- Post-merge push run `32690165406` is `completed / success` on the exact
  starting head. Both `CPU tests` and `Code quality` completed successfully:
  `1584 passed in 40.72s`; quality inventory `Ruff 757/776; Black 62/68`;
  removed debt `Ruff 19, Black 6`; zero changed Python files; no new debt.
- `.agent/WAVE.md` records A8 `done` and A9--A12 `todo`. The A8 ticket has
  twenty-five checked and zero unchecked bounded implementation criteria.
- All pull requests, remote branch names, unmerged remote commits, and current
  source were searched for A9, MCP, Miner MCP, prior, scaffold, estimate,
  `light_compare`, `light_train`, mock/light, and submission transport. No
  competing A9 branch, PR, implementation, test, plan, or ratification
  candidate exists. Historical references are archaeology only.
- `carbon/mcp/__init__.py` is still the one-line A0 namespace marker. There is
  no A9 model, provider, service, canonical test, dependency, or prior plan.
  Legacy miner clients and the HTTP example are not the A9 contract.
- Starting `git status --porcelain=v1` was empty.

## Authority and conflict map

| Source | A9 ruling |
|---|---|
| Current A2--A8 code and canonical CPU tests | **NO_CONFLICT / controlling implementation truth.** A9 wraps exact A2 validation, A3 public challenge facts, A7 submit/status/publication, and the exact A6 card type. |
| Constitution, invariants, and constitutional overlay | **NO_CONFLICT.** A9 is a miner-facing control/disclosure boundary, not official evaluation or scientific/economic authority. |
| Current `Miner_MCP.md`, Build Out C9, and the short A9 ticket | **DOCUMENTATION_LAG.** They combine Wave-A control/disclosure with deferred mock/light execution, stale aliases, fee/queue language, and overbroad challenge information. This candidate repairs only that contract. |
| A8-R15 mock reservation | **NO_CONFLICT.** Its gate continues to block every execution-dependent estimate/light path. The coupled shorthand in Build Out/A9 prose is `DOCUMENTATION_LAG`; the separately ratified A9 estimate is pure structural/prior interpretation and never enters the A8 mock lane. |
| Current A3/A6/A7 requester and storage boundaries | **NO_CONFLICT.** A9 uses positive projections and A7-mediated card reads; it creates no authentication claim or second store. |
| Legacy miner, `agent_tools`, clients, neurons, prior publisher, Landscape, HTTP example, and old Strategy-schema code | **REPLACE/EXCLUDE as A9 authority.** Retained as archaeology only; no migration or compatibility alias is authorized. |
| Actual prior/scaffold content, directive vocabulary, resource values, query/fee/quota/rate policy, authentication, mock pack/resource policy, and adaptive-query evidence | **NEW_OWNER_DECISION_REQUIRED for deployment, not for this fail-closed skeleton.** Missing inputs remain unavailable; no value is invented. |

No unresolved owner decision blocks ratifying the bounded fail-closed contract.
No current implementation must migrate in this documentation task.

## KEEP → WRAP → REPAIR → REPLACE

| Area | Disposition |
|---|---|
| `carbon/mcp/__init__.py` namespace | **KEEP; REPAIR later.** Preserve the package and add only the ratified modules in the separately authorized implementation. |
| A2 `dry_validate` and immutable validation result | **KEEP / WRAP.** Delegate directly and copy only its public result; do not recreate schema logic. |
| A3 `ChallengeKey`, exact record load, and effective-LIVE check | **KEEP / WRAP.** Construct the minimum exact-key public challenge projection; never list records, add an admission gate, or expose record internals or qualification reasons. |
| A6 `EvaluationCard` model | **KEEP.** Type the optional result card only; never import or reach `CardStore`. |
| A7 `RequesterIdentity`, `SubmissionId`, `SubmissionStatusView`, `SubmissionState`, and `SubmissionService` public methods | **KEEP / WRAP.** Submit, status, and published-card access remain A7-owned. |
| Existing Miner MCP specification | **REPAIR.** Separate Wave-A control/disclosure from Wave-B mock/light execution and replace stale aliases/fields. |
| Legacy miner/client/agent-tools/HTTP/example surface | **REPLACE/EXCLUDE.** No compatibility wrapper or alias registration in A9. |
| A8 fixture service and future mock service | **KEEP separate; do not call.** A9 Wave A has no execution path. |
| New MCP SDK, HTTP framework, server, or optional-heavy dependency | **REPLACE with an in-process standard-library/current-owner seam.** None is justified. |

## Exact Wave-A ownership

A9 Wave A owns only:

- exact in-process call dispatch for seven registered tool names;
- bounded, exact-built-in ownership capture at the untrusted call boundary;
- the minimum public Challenge projection;
- public provider seams for a prior and a declarative scaffold;
- exact A2 dry-validation delegation;
- a pure provider-derived structural/prior estimate;
- exact A7 submission intake and lifecycle acknowledgement;
- query-budgeted A7 status and A7-mediated published-card retrieval;
- stable public error collapse and positive response reconstruction.

A9 Wave A does not own or perform:

- mock, fixture-official, or production execution;
- A8 context, seed, backend, materialization, scoring, or result behavior;
- official or fixture Score Packs, `ScoreInput`, `InternalResult`, metrics,
  gates, weights, ranks, or emission;
- A7 validation/admission/start/retry/cancel/fail/complete/publish operations;
- A6 storage or private records;
- prior publication policy/content or scaffold content;
- authentication, a network transport, an MCP SDK, HTTP, or server lifecycle;
- A10 leaderboard, A11 logging/metrics, A12 invariant aggregation, chain,
  treasury, settlement, business, publication, or Product Qualification.

## Deferred Wave-B mock/light contract

The following remain deferred together and are not specified by this A9
Wave-A candidate:

```text
exact future MockExecutionRequest
exact future MockRunOutcome
exact future MockTrainEvalService.run_mock
mock pack identity and registry
mock resource and isolation policy
mock execution and disclosure
light_compare
light_train
adaptive-query security evidence
```

The future entry point remains nominally distinct from fixture-official and
production execution:

```text
MockTrainEvalService.run_mock(
    request: exact future MockExecutionRequest
) -> exact future MockRunOutcome
```

That future outcome is not an A5 `InternalResult`, cannot enter A7 or A6,
creates no card, and affects no fee, official score, rank, weight, or emission.
`list_my_submissions` is also excluded from Wave A but is not part of the mock
execution contract. A separate future ratification must decide whether and
where it belongs.

## Exact module and dependency contract

The future implementation layout is exactly:

```text
carbon/mcp/
    __init__.py
    model.py
    providers.py
    service.py
```

Source dependency direction:

```text
model.py
  -> standard library + minimum public A2/A3/A6-model/A7 nominal types

providers.py
  -> standard library typing + exact A2/A3/A7 and A9 model types

service.py
  -> standard library + public A2, public A3, A6 EvaluationCard model,
     public A7 service/model APIs, and A9 model/providers

__init__.py
  -> explicit A9 public exports only
```

A9 must not source-import A4 context/secret types, A5 scoring models or engine,
A6 stores, A7 stores, A8, A10--A12, legacy miner/Landscape code, PoC,
neurons, MCP SDKs, HTTP frameworks, Bittensor, Torch, JAX, NumPy, or any other
optional-heavy dependency. No network server belongs in this contract.

## Exact service construction and dispatch

The only public service is constructed with every dependency explicit and no
provider fallback:

```text
McpService(
    registry: exact ChallengeRegistry,
    submission_service: exact SubmissionService,
    resource_limits: exact McpResourceLimits,
    query_budget_gate: QueryBudgetGate,
    prior_provider: PriorProvider | None,
    scaffold_provider: ScaffoldProvider | None,
    estimate_provider: EstimateProvider | None
)

McpService.call(
    call: exact McpCall,
    requester_identity: exact out-of-band RequesterIdentity
) -> (
    ChallengeInfo | PublishedPrior | PublishedScaffold |
    DryValidateResponse | StructuralEstimate | SubmitReceipt |
    SubmissionResult
)
```

Every constructor argument is required; the three explicit `None` provider
slots are how trusted composition selects fail-closed unavailability. There is
no implicit provider, query gate, resource policy, registry, A7 service, or
global singleton. Trusted composition must pass the same exact
`ChallengeRegistry` instance that was used to construct the injected
`SubmissionService`; A9 does not inspect A7 private state and cannot repair a
mismatched composition. Failures are raised as exactly one of the seven fixed
public A9 error types. The closed tool-to-response mapping is:

| Tool | Exact response type |
|---|---|
| `get_challenge_info` | `ChallengeInfo` |
| `get_prior` | `PublishedPrior` |
| `get_mock_scaffold` | `PublishedScaffold` |
| `dry_validate` | `DryValidateResponse` |
| `estimate` | `StructuralEstimate` |
| `submit` | `SubmitReceipt` |
| `get_submission_result` | `SubmissionResult` |

No generic mapping, raw dictionary, iterator, stream, or transport response is
returned. The service itself owns no server lifecycle.

## Exact call framing and tool registration

`McpTool` is an exact closed string enum with exactly these values, in this
order:

```text
GET_CHALLENGE_INFO = "get_challenge_info"
GET_PRIOR = "get_prior"
GET_MOCK_SCAFFOLD = "get_mock_scaffold"
DRY_VALIDATE = "dry_validate"
ESTIMATE = "estimate"
SUBMIT = "submit"
GET_SUBMISSION_RESULT = "get_submission_result"
```

No alias is registered. In particular `info`, `prior`, `scaffold`,
`validate_strategy`, and `submit_strategy` are unavailable. `light_compare`,
`light_train`, and `list_my_submissions` are unavailable in Wave A.

The first untrusted in-process boundary is an exact frozen/slotted
`McpCall`, never a raw dictionary:

```text
McpField(name: exact built-in str, value: object)

McpCall(
    schema_version: exact built-in str,
    tool: exact built-in str,
    fields: exact tuple[McpField, ...]
)
```

These two raw-envelope nominals are storage-only: their constructors freeze
the references supplied by the caller but intentionally perform no eager
type, schema, field-name, duplicate, resource, or semantic validation. Thus an
exact `McpCall` can carry malformed internal framing into `McpService.call`
without forged objects; `call` alone checks the exact outer types, admits
concurrency, captures ownership, and applies the ordering below.

Field order is retained until request decoding. Duplicate field names are
therefore observable and rejected before any dictionary materialization.
Duplicate, non-string, subclassed, or over-limit structural fields fail closed;
after exact tool dispatch, known-tool unknown/missing semantic fields also fail
closed. The exact A9 call schema version is `"1.0"`; no alias, normalization,
default version, or version negotiation exists.

Exact wire field sets are:

| Tool | Required fields | Optional fields |
|---|---|---|
| `get_challenge_info` | `challenge_id`, `challenge_version` | none |
| `get_prior` | `challenge_id`, `challenge_version` | none |
| `get_mock_scaffold` | `challenge_id`, `challenge_version` | `scaffold_id` (exact canonical token when present) |
| `dry_validate` | `strategy` | none |
| `estimate` | `challenge_id`, `challenge_version`, `strategy` | none |
| `submit` | `challenge_id`, `challenge_version`, `strategy` | none |
| `get_submission_result` | `submission_id` | none |

Requester identity is never a call field. Trusted composition supplies it out
of band to the service call.

## Exact resource policy

`McpResourceLimits` is frozen, slotted, non-serializable, mandatory, and
injected with no defaults. Its exact positive finite integer fields are:

```text
max_call_fields
max_total_request_value_nodes
max_request_object_members
max_request_list_items
max_request_string_utf8_bytes
max_request_object_key_utf8_bytes
max_request_integer_bits
max_total_request_utf8_bytes
max_total_response_value_nodes
max_response_sequence_items
max_response_string_utf8_bytes
max_response_integer_bits
max_total_response_utf8_bytes
max_concurrent_calls
```

Every field must be an exact built-in positive integer representable as an
unsigned 64-bit value. No production value, query count, fee, quota, rolling
window, rate, retry delay, or retry-after field is ratified here.

Capture is iterative and non-recursive. It accepts only exact built-ins:
`None`, `bool`, `int`, finite `float`, `str`, `list`, and `dict`. Dictionary
keys may be exact built-in scalar values at this capture layer so A2/A7 retain
authority to reject non-string Strategy keys; decoded MCP field names
themselves must still be exact strings. Capture rejects subclasses, tuple/set
containers, arbitrary mappings/iterables, unstable containers, non-finite
numbers, and hostile objects without calling their `repr` or `str`. It creates
a fresh built-in graph while preserving shared references and cycles so exact
A2/A7 validation and identity semantics are not silently changed; visited-node
accounting bounds that graph without looping. It retains no caller alias.
Request resource failure occurs before any provider or A2/A3/A7 call. Response
projection reconstructs exact nominal/public values and enforces the response
limits before release.

Accounting is exact and identity-aware:

- Only exact top-level `McpCall` and requester type checks precede concurrency
  admission; wrong or subclassed outer values are request errors without
  invoking their attributes. Every exact-top-level call then acquires one
  concurrency permit before framing, tool, field, value, provider, or owner
  work. This includes internally malformed and exact-string unknown/deferred
  tool calls. The permit is held through response projection or public error
  translation and always released in `finally`.
- Inside the permit, shallow framing first validates exact schema/tool types
  and the exact fields-tuple type. It checks `len(fields)` against
  `max_call_fields` before scanning any entry and meters schema/tool strings
  before use. Only after those meters pass is the schema value checked for
  exact equality with `"1.0"`. Each now-bounded tuple entry is checked in order
  for exact `McpField` type, exact string name, the name's framing UTF-8 meters,
  and only then duplicate identity. Thus neither an unbounded tuple nor an
  overlong name reaches scanning/hash/equality. An exact-string
  unknown/deferred tool is then unavailable without assigning it a semantic
  field schema, capturing values, or making a downstream call. Only a known
  tool is next checked for its exact missing/unknown semantic fields and then
  proceeds to value capture/decoding.
- Each `McpField.value` root consumes one request value node. On first
  expansion of each distinct exact list/dict, each list item or dict member
  value consumes one node. Alias and cycle edges are charged by their
  containing cardinality, but an already-seen container's children are not
  expanded or charged twice. Dict keys are not value nodes; every member is
  bounded by the per-object limit and its value-node charge.
- `max_request_object_members` and `max_request_list_items` apply separately
  to every first-seen container. `max_request_integer_bits` is exact
  `int.bit_length(value)` for every exact int occurrence, including scalar
  dict keys; exact bool is not an int for this rule.
- `max_request_string_utf8_bytes` applies to schema version, tool, field names,
  graph string values, and string dict keys.
  `max_request_object_key_utf8_bytes` additionally applies to every string
  dict key. `max_total_request_utf8_bytes` sums those widths by logical
  occurrence; contents of an already-seen container are not summed twice.
- Strict UTF-8 width is counted by code point without allocating an encoded
  copy. A surrogate is charged one byte to keep the scan bounded and marks the
  request invalid; a resource breach already encountered remains a resource
  error. Other scalar dict keys contribute no UTF-8 bytes but remain subject
  to member and integer-bit bounds.
- Response accounting begins with one node for the top-level success value and
  adds one for every nominal field, sequence item, and dict member value when
  each distinct container is first expanded. Dict keys are not nodes.
  Traversal accepts only the exact closed A9/owner nominal and enum types plus
  exact `None`/bool/int/finite-float/string/tuple/list/dict field values
  permitted by those models; another type or subclass is integration failure.
  `max_response_sequence_items` applies to every exact tuple/list;
  `max_response_string_utf8_bytes` applies to every response string value and
  string dict key; `max_response_integer_bits` uses exact `int.bit_length` for
  every exact int value or scalar dict key, excluding bool;
  and `max_total_response_utf8_bytes` is their occurrence sum. Each exact
  string enum is one value node and its exact `.value` is charged as a response
  string. The same bounded surrogate scan marks response text invalid while
  charging one byte. A response dict must fit the remaining total-node budget
  before it is copied.
- Exact top-level/provider shape and cross-binding are checked before deep
  positive projection where possible. A response-meter breach is always
  `McpResourceError`; malformed, subclassed, unstable, invalid-UTF-8,
  or cross-bound provider output within the meters is `McpIntegrationError`.
  Traversal order is the exact call-field tuple, list/tuple index, built-in dict
  insertion order, declared nominal-field order, and provider sequence order.
  If multiple conditions exist, the first encountered in that order controls.

The concurrency field controls every simultaneous in-process call with exact
top-level call/requester types. Query budget is a separately injected policy
gate. A9 defines no default for either.

## Exact internal request types

Each decoded request is an exact frozen/slotted nominal value:

```text
GetChallengeInfoRequest(challenge_key: exact ChallengeKey)
GetPriorRequest(challenge_key: exact ChallengeKey)
GetMockScaffoldRequest(
    challenge_key: exact ChallengeKey,
    scaffold_id: exact str | None
)
DryValidateRequest(strategy: freshly owned supported exact-built-in graph)
EstimateRequest(
    challenge_key: exact ChallengeKey,
    strategy: freshly owned exact built-in dict
)
SubmitRequest(
    challenge_key: exact ChallengeKey,
    strategy: freshly owned supported exact-built-in graph
)
GetSubmissionResultRequest(submission_id: exact SubmissionId)
```

These are transient internal dispatch values. Frozen/slotted wrappers do not
turn nested Python containers into security capabilities; A9 retains no
request history and reconstructs ownership at every downstream boundary.

## Exact provider/publication model

Identity references are exact frozen/slotted values:

```text
PriorRef(
    challenge_key: exact ChallengeKey,
    prior_id: exact canonical token,
    prior_version: exact version token,
    content_hash: exact tagged lowercase SHA-256
)

ScaffoldRef(
    challenge_key: exact ChallengeKey,
    scaffold_id: exact canonical token,
    scaffold_version: exact version token,
    content_hash: exact tagged lowercase SHA-256
)
```

The hash is a provider-owned publication identity. A9 validates exact tagged
SHA-256 syntax and cross-binding but does not invent publication bytes, a
canonical publisher format, a file store, or a second cache.

Every `canonical token` in this contract is an exact built-in `str` accepted
without normalization by public A3
`validate_canonical_identifier(value, field_name)`. The applicable MCP string
and aggregate UTF-8 limits supply its size bound. Every `version token` is an
exact built-in `str` accepted without normalization by public A3
`validate_version`.

`PriorDirectiveKind` is the exact closed string enum:

```text
STRUCTURAL_STEER = "structural_steer"
AVOID = "avoid"
EXPLORE = "explore"
NOT_INCLUDED = "not_included"
```

An exact frozen/slotted `PriorDirective` has:

```text
kind: exact PriorDirectiveKind
subject: exact bounded canonical token
tokens: exact tuple of bounded canonical tokens
```

`subject` and `tokens` are closed publication-vocabulary identifiers, not free
text, numbers, weights, parameter values, or executable instructions. The
allowed vocabulary and actual directives remain explicit owner/provider
inputs. A9 neither supplies nor silently expands that vocabulary.

Exact top-level provider responses use A9 response schema `"1.0"`:

```text
PublishedPrior(
    schema_version: "1.0",
    prior_ref: exact PriorRef,
    directives: exact provider-ordered, duplicate-free
                tuple[PriorDirective, ...]
)

PublishedScaffold(
    schema_version: "1.0",
    scaffold_ref: exact ScaffoldRef,
    strategy: freshly owned exact built-in A2-valid Strategy,
    informed_by_prior: exact PriorRef | None,
    execution_deferred: exact True
)

StructuralEstimate(
    schema_version: "1.0",
    challenge_key: exact ChallengeKey,
    prior_ref: exact PriorRef,
    validation: exact owned A2 ValidationResult,
    applicable_directives: exact tuple[PriorDirective, ...],
    disclaimer: exact "non_binding_structural_prior_only"
)
```

`applicable_directives` must be an order-preserving duplicate-free subset of
the exact published prior supplied to the estimate provider. There is no
arbitrary diagnostic/free-text field.

Provider protocols are exactly:

```text
PriorProvider.get_prior(
    ChallengeKey
) -> PublishedPrior

ScaffoldProvider.get_scaffold(
    ChallengeKey,
    scaffold_id: str | None
) -> PublishedScaffold

EstimateProvider.estimate(
    ChallengeKey,
    PublishedPrior,
    owned Strategy,
    ValidationResult
) -> StructuralEstimate

QueryBudgetGate.consume(
    RequesterIdentity,
    McpTool
) -> None
```

No provider receives `RequesterIdentity`; prior and scaffold publication are
one-channel public seams. Provider absence produces the stable tool-unavailable
error. Provider exceptions or malformed, subclassed, cross-bound, unstable,
or otherwise invalid outputs within response meters produce the stable
integration error; a response-meter breach produces the stable resource error.
Positive reconstruction detaches provider-owned objects while preserving valid
internal graph topology.
The future implementation adds test providers only, not a production
provider, prior publication, scaffold body, or policy value.

## Prior contract

A valid prior is coarse, public, versioned, hashed, non-executable,
non-binding, one-channel, and closed-directive-only. It contains no Strategy,
free text, numeric weight vector, hyperparameter recipe, champion identity,
champion weights, official score, rank, fee, seed, pack identity, or emission
field. Its directives never become A5 input or A7/A8 authority.

The service first checks that the prior provider is configured, then
establishes public Challenge visibility, calls the exact provider once,
validates exact type/version/reference/content shape, makes a fresh positive
projection, and returns it. It performs no publication caching or history
retention.

## Scaffold contract

A valid scaffold remains separate from the prior. Its exact reference pins
scaffold ID, version, content hash, and ChallengeKey. The strategy is a fresh
owned exact built-in A2-valid Strategy whose `challenge_id` equals the exact
ChallengeKey challenge ID. An optional `informed_by_prior` reference is
metadata only and must bind the same exact ChallengeKey. The literal
`execution_deferred` field is always true in Wave A.

The service first checks that the scaffold provider is configured, then
establishes public Challenge visibility and calls the provider once. It calls
canonical `carbon.schema.dry_validate` exactly once on the detached returned
Strategy and requires the exact result to have `ok=True`; a non-`ok` result is
malformed provider output and becomes integration failure. It does not trust a
provider validity claim or recreate A2 validation. When the request contains
`scaffold_id`, the returned
`PublishedScaffold.scaffold_ref.scaffold_id` must equal it exactly. When the
selector is absent, the provider owns selection of the returned canonical ID.

A9 does not call the prior provider to construct or complete a scaffold, fill
prior omissions, derive a scaffold from a prior, interpret inert A2
parameters, call A8, execute anything, or infer scientific validity,
mediocrity, non-champion status, or Challenge compatibility from type checks.
No external caller or provider alias is retained or returned; valid internal
graph topology is preserved in the detached projection.

## Challenge-information contract

The exact frozen/slotted positive projection is:

```text
ChallengeInfo(
    schema_version: "1.0",
    challenge_key: exact ChallengeKey,
    lifecycle_status: exact "draft" | "fixture" | "live",
    fixture_origin: exact bool,
    effectively_live: exact bool,
    allowed_backbones: exact tuple[str, ...]
)
```

`schema_version` is response framing. The five disclosed Challenge fields are
exactly `challenge_key`, `lifecycle_status`, `fixture_origin`,
`effectively_live`, and `allowed_backbones`.

Visibility is exact-key and deliberately does not become a second admission
gate:

- exact A3 `draft`, `fixture`, and `live` records are visible when the caller
  already supplies their exact `ChallengeKey`;
- A9 never calls `scan` or adds listing/discovery;
- `effectively_live` is false for every non-live record and, for a `live`
  record, is exactly the Boolean returned by A3
  `is_effectively_live(challenge_id, version)`; an ineffective live record is
  still projected as `lifecycle_status="live"`, `effectively_live=False`;
- `fixture_origin` is copied exactly and is not authentication or scientific
  qualification;
- missing, malformed, internally inconsistent, or other lifecycle values are
  unavailable.

The projection never exposes artifact paths/digests, qualification references
or evidence, backend-profile evidence, receipt evidence, fee values, Score
Pack hashes, generator hashes, active mock-pack IDs, mock ranges, tag or
disclosure catalogs, private qualification reasons, seeds, or contexts.

## Exact A2 validation and structural estimate

`DryValidateResponse` is:

```text
DryValidateResponse(
    schema_version: "1.0",
    validation: exact freshly reconstructed A2 ValidationResult
)
```

The handler calls current public `carbon.schema.dry_validate` exactly once on
the freshly owned request value and returns a positive reconstruction of that
exact result. It adds no challenge lookup, normalization, default, alias,
execution, provider, score, or status.

The estimate handler:

1. checks that both prior and estimate providers are configured;
2. establishes public Challenge visibility;
3. obtains and positively validates the exact public prior;
4. calls exact A2 `dry_validate` once on a fresh owned Strategy;
5. calls the exact estimate provider with fresh owned/cross-bound inputs;
6. validates and positively reconstructs the exact `StructuralEstimate`.

The provider may use only the Strategy's inert declarative structure, exact A2
validation result, and published prior directives. It performs no execution;
uses no `MockContext`; calls no A8 service; uses no fixture-official context,
official or fixture Score Pack; constructs no `ScoreInput` or
`InternalResult`; and returns no floating-point quality score, predicted
official score, rank, predicted card status, predicted gate result, weight, or
emission value. The result remains non-binding and structural-prior-only.
Missing prior or estimate provider fails closed as tool unavailable.

This is the exact A8-R15 reconciliation: A8-R15 continues to block every
execution-dependent estimate/light implementation until the complete future
mock request/resource/disclosure contract is separately ratified. The A9
structural estimate above never crosses that gate because it has no mock or
other execution path.

## Exact A7 submit contract

Trusted composition supplies an exact copied `RequesterIdentity` out of band.
After the non-mutating maximum-receipt resource preflight below, the submit
handler's only owner calls are:

```text
submission_id = SubmissionService.submit(
    exact RequesterIdentity,
    exact ChallengeKey,
    freshly owned Strategy
)
status = SubmissionService.get_status(
    exact SubmissionId,
    exact RequesterIdentity
)
SubmitReceipt(schema_version="1.0", status=exact SubmissionStatusView)
```

`SubmitReceipt` contains the exact positively reconstructed
`SubmissionStatusView`. It is an A7 lifecycle acknowledgement only. It is not
proof of queueing, acceptance, payment, provenance, execution, official score,
scientific validity, rank, weight, or emission.

Before any A7 method, the submit handler resource-preflights the maximum valid
canonical `SubmitReceipt`: the closed nominal node topology, schema literal
`"1.0"`, fixed 36-byte UUIDv4 `SubmissionId`, and longest closed
`SubmissionState.value`. This is a finite arithmetic/constant check only; it
mints no ID and inspects no owner state. If every canonical receipt cannot fit
the injected response meters, the handler raises resource before A7 mutation.
Consequently, a well-formed canonical post-submit status is already known to
fit; malformed/trusted integration output still fails integration.

A9 performs no preliminary A2/A3 admission that would replace A7 intake and
never calls `mark_validated`, either admission method, fee-start, retry,
cancellation, execution, completion, publication, or A6 storage methods. Exact
A7 duplicate-open idempotence is preserved: an open duplicate returns the same
SubmissionId with no second record, lifecycle transition, fee event, or
charge. When A7 retained-record capacity permits creation, exact `REJECTED`
and `RECEIVED` outcomes remain visible through the returned status.

## Exact result contract and polling order

`SubmissionResult` is:

```text
SubmissionResult(
    schema_version: "1.0",
    status: exact SubmissionStatusView,
    card: exact EvaluationCard | None
)
```

Every structurally valid result poll must call:

```text
QueryBudgetGate.consume(exact RequesterIdentity, McpTool.GET_SUBMISSION_RESULT)
```

after request/resource validation and before any A7 lookup. The return is
captured and must be exact `None`; any other value is an integration failure
and prevents A7 lookup. An exact gate-raised `McpQueryBudgetError` is translated
without chaining to a fresh public `McpQueryBudgetError` containing only its
fixed literals; every other gate failure is an integration failure. No
retry-after, queue position, or completion-time estimate is invented. Once
exact consume succeeds, no later outcome refunds it, including unavailable or
nonterminal status and any response-meter, projection, or integration failure.

After budget consumption, the handler calls `SubmissionService.get_status`
first. It calls `SubmissionService.read_published` only when the exact returned
state is `SubmissionState.PUBLISHED`. Every other A7 state returns that exact
status with `card=None`. Published state returns the exact A7-mediated A6
`EvaluationCard` positive projection.

Not-found and wrong-requester A7 cases collapse to the same public submission-
unavailable error. The response never exposes StrategyHash, ChallengeKey from
private submission storage, attempt history, fee records, retry counts,
execution handles, SeedPin, environment pins, private failure causes,
InternalResult, private A6/A7 records, fine score detail, margins, stress
breakdowns, private/free-form diagnostic content, or timestamps not supplied
by an owner API. The exact A6 `public_diagnostics` field remains present and
canonically empty.

## Requester and authentication boundary

`RequesterIdentity` is supplied only by trusted composition and never appears
in `McpCall.fields`. A9 requires an exact current A7 `RequesterIdentity` and
passes a fresh exact value to the query gate and A7.

Current `RequesterIdentity` provides structural equality and requester binding
only. It is not proof of authentication, hotkey ownership, signature validity,
session authority, or network identity. A future network adapter must perform
real authentication before constructing the out-of-band identity. This A9
contract adds no adapter or authentication claim.

## Stable public errors

Each error is a distinct exact nominal, slot-declared exception type with a
frozen public contract payload. It has a zero-argument public constructor,
literal-backed read-only `code` and fixed message/argument values, supports no
diagnostic fields, and is raised with suppressed exception chaining at the
public boundary. This immutability claim does not include interpreter-owned
`BaseException` runtime metadata (`__traceback__`, `__context__`, `__cause__`,
or its inherited implementation dictionary):

| Type | Code | Fixed message |
|---|---|---|
| `McpRequestError` | `mcp.request.invalid` | `MCP request is invalid.` |
| `McpResourceError` | `mcp.resource_limit_exceeded` | `MCP resource limit was exceeded.` |
| `McpToolUnavailableError` | `mcp.tool_unavailable` | `MCP tool is unavailable.` |
| `McpChallengeUnavailableError` | `mcp.challenge_unavailable` | `Challenge is unavailable.` |
| `McpSubmissionUnavailableError` | `mcp.submission_unavailable` | `Submission is unavailable.` |
| `McpQueryBudgetError` | `mcp.query_budget_exceeded` | `MCP query budget was exceeded.` |
| `McpIntegrationError` | `mcp.integration_failure` | `MCP integration failed.` |

The closed mapping is:

| Boundary condition | Public result |
|---|---|
| wrong/subclassed call/request, schema mismatch, structural field failure, known-tool missing/unknown semantic field, or invalid caller scalar/identity syntax | `McpRequestError` |
| request/response/concurrency limit or exact A7 resource/capacity exhaustion | `McpResourceError` |
| unknown, alias, deferred tool, or missing tool-specific provider | `McpToolUnavailableError` |
| A3 missing/unreadable/malformed/internally inconsistent exact record | `McpChallengeUnavailableError` |
| exact A7 not-found or authorization failure during poll | `McpSubmissionUnavailableError` |
| exact `McpQueryBudgetError` raised by the query gate | fresh fixed `McpQueryBudgetError`, with chaining suppressed |
| subclassed query error or any other gate failure | `McpIntegrationError` |
| provider exception or malformed/subclassed/mismatched provider output | `McpIntegrationError` |
| unexpected A2/A3/A6/A7 failure after a valid boundary | `McpIntegrationError` |

Only a wrong/subclassed outer call or requester is rejected before concurrency
admission. Every exact-top-level call acquires a permit before all remaining
validation, so concurrency exhaustion precedes internal framing/tool/field
conditions. Within an admitted call, request and response meter breaches are
resource errors.

An exact A7 request error caused by malformed decoded identity maps to
`McpRequestError`; when A7 retained-record capacity permits, semantically
invalid resource-admissible Strategy values do not raise it because A7 records
and returns exact `REJECTED`. Capacity exhaustion is `McpResourceError`. No
internal exception subtype or text is exposed.

Errors contain no field value, object representation, provider/A2/A3/A6/A7
exception text, path, secret, seed, context, pack, private state, configured
limit, observed size, quota, retry-after, stack, or exception object. Hostile
`repr`/`str` is never invoked.

## Retention, caching, replay, and side effects

A9 retains zero request history, response history, provider history, or cache.
It creates no submission store. Provider publications remain versioned and
provider-owned. A7 alone retains its current process-local submission state and
duplicate-open idempotence.

Read handlers have no A9 mutation beyond the mandatory query-budget consume for
result polling and transient concurrency accounting. Submit has exactly the
A7 side effect described above. Its maximum-receipt response preflight occurs
before that side effect. A9 performs no retry or compensation if the
post-submit status read/projection nevertheless encounters a trusted
integration failure; response capacity alone cannot cause that post-mutation
case.

## Exact future root exports

The future `carbon.mcp.__all__` is exactly the following public surface, with
no aliases or legacy exports:

```text
ChallengeInfo
DryValidateRequest
DryValidateResponse
EstimateProvider
EstimateRequest
GetChallengeInfoRequest
GetMockScaffoldRequest
GetPriorRequest
GetSubmissionResultRequest
McpCall
McpChallengeUnavailableError
McpField
McpIntegrationError
McpQueryBudgetError
McpRequestError
McpResourceError
McpResourceLimits
McpService
McpSubmissionUnavailableError
McpTool
McpToolUnavailableError
PriorDirective
PriorDirectiveKind
PriorProvider
PriorRef
PublishedPrior
PublishedScaffold
QueryBudgetGate
ScaffoldProvider
ScaffoldRef
StructuralEstimate
SubmissionResult
SubmitReceipt
SubmitRequest
```

No A2--A8 owner type is re-exported through A9.

## Canonical future acceptance matrix

The sole canonical focused location is
`tests/cpu/test_mcp_skeleton.py`. A future implementation must cover:

1. exact construction, storage-only raw-envelope construction, shared A3/A7
   registry composition, frozen/slotted nominal types, slot-declared/fixed-
   payload errors, enum membership, and subclass rejection;
2. exact `"1.0"` call/response schema version;
3. unknown, missing, duplicate, non-string, and ordered call fields;
4. every `McpResourceLimits` boundary, all-call concurrency admission, exact
   node/alias/cycle/UTF-8/surrogate/integer accounting, and response bounds;
5. hostile `repr`/`str` and stable non-echoing errors with suppressed chaining;
6. exact registered tool names and rejection of aliases/light/list tools;
7. exact A2 direct delegation and positive `ValidationResult` reconstruction;
8. exact A3 positive Challenge projection and draft/fixture/live visibility;
9. provider absence/order, exception, subclass, malformed output, ownership
   detachment/topology, selector, resource, version, hash, and cross-binding;
10. prior/scaffold prohibited-field and canary leakage;
11. declarative-only A2-valid scaffold, exact Challenge binding, optional
    prior metadata, and literal deferred execution;
12. pure structural non-binding estimate, directive-subset binding, and
    invalid-Strategy validation preservation;
13. rejection of mock/light execution, MockContext, fixture/official contexts,
    official/fixture packs, ScoreInput/InternalResult, A8 calls, and score/gate/
    rank/weight/emission output;
14. maximum-receipt preflight before mutation, exact A7 submit delegation,
    status acknowledgement, duplicate-open idempotence, and capacity-qualified
    `REJECTED`/`RECEIVED` behavior;
15. no duplicate fee, lifecycle, validation, admission, start, retry, cancel,
    execute, complete, publish, or A6-store operation;
16. requester-bound result retrieval across every exact A7 state;
17. exact-`None` query-gate success, budget consumed before every A7 poll
    lookup, stable exhaustion, and no post-consume refund;
18. exact A6 card only after publication and status-with-no-card otherwise;
19. not-found/authorization collapse without private distinction;
20. no private A6/A7 stores, records, InternalResult, StrategyHash, attempt,
    fee, retry, handle, pin, context, seed, pack, path, exception, timestamp,
    private/free-form diagnostic, fine-score, margin, or stress leakage while
    exact A6 `public_diagnostics` remains empty;
21. zero A9 cache/history/second-store retention and fresh positive responses;
22. no A10/A11/chain/treasury/weight/emission import or behavior;
23. exact root exports and no compatibility aliases;
24. optional dependency isolation and no network/MCP/HTTP SDK import;
25. installed-wheel/outside-tree import from isolated `site-packages`;
26. full default CPU regression without A0--A8 behavior changes;
27. Ruff, Black, and repository no-new-debt checks with every changed Python
    file clean.

Documentation and existing A0--A8 regression tests are not A9 test evidence.

## Future implementation sequence

1. Re-fetch the ratification merge and verify exact topology, status, CI,
   ticket counts, no competing work, and a clean tree.
2. Mark only A9 `in_progress` in the separately authorized implementation
   candidate.
3. Add exact `model.py` values/errors/capture/resource logic.
4. Add exact provider protocols with no production providers.
5. Add the in-process service/dispatch and seven handlers.
6. Add only `tests/cpu/test_mcp_skeleton.py` for the focused A9 contract.
7. Verify dependency/root-export/wheel isolation and complete CPU/quality
   regression.
8. Leave Wave-B mock/light, A10+, and all deployment/owner inputs untouched.
9. Publish a separate draft implementation candidate for independent review;
   do not self-ratify, self-close, or merge it.

## Ratification validation boundary

This documentation candidate may validate only its seven-file manifest,
unchecked implementation criteria, formatting, internal consistency, and
absence of forbidden changes. It does not provide A9 implementation or test
evidence and must not change `.agent/WAVE.md`.
