# A11 — bounded operational observability contract and R18 amendment candidate

**Ticket:** `.agent/tickets/A11_logging.md`
**Wave status:** `todo`
**Document status:** A11-R1 through A11-R17 are ratified; A11-R18 is specified
as this exact documentation-only candidate and is not ratified until independent
review, explicit human authorization, and normal merge
**Current main:** `4e4a66d29566a2a62a82188adddac76e6e0fb8b8`
**Current tree:** `f39946f755d55639190aa96b5de578a10c421725`
**Current subject:** `Merge pull request #39 from
carbonphysicsai/agent/a11-contract-ratification`

## 1. Purpose, verified base, and authority

PR #39 normally merged the exact A11-R1 through A11-R17 documentation contract
into current main. This plan preserves that ratified record and proposes only
A11-R18, the immutable A11-owned sink snapshot amendment. It implements or
tests nothing, changes no owner service, creates no production sink, does not
modify the draft PR #46 branch, updates only that PR's blocker metadata, does
not authorize A12, and does not activate Wave B.

The exact current-main topology is:

~~~text
commit:  4e4a66d29566a2a62a82188adddac76e6e0fb8b8
tree:    f39946f755d55639190aa96b5de578a10c421725
subject: Merge pull request #39 from carbonphysicsai/agent/a11-contract-ratification
parent 1: ea7f78b455f14f8ea674c196db349fd08b355305
parent 2: 6ac0924028e19ba69e82d8f7bba8f93e838e576f
signature: verified=true, reason=valid
~~~

Push run `33019949026` succeeded on that exact main with `1973 passed`. The
repository quality result remained `Ruff 757/776`, `Black 62/68`, removed Ruff
debt `19`, removed Black debt `6`, zero changed Python files, and no new debt.
Current main contains no `carbon/observability` package and no
`tests/cpu/test_observability.py`; A11 is IMPLEMENTED: NO and TESTED: NO there.

Draft PR #46 remains a non-authoritative implementation candidate at head
`5b0b4927f8a4d2e6438b20a8201da43ae2a0645e`, tree
`3a84d98d95e53afaace00d500116cce91e66089e`. Its generic-dataclass
serialization defect is repaired, but its sink seam still passes shared
canonical A11/A5/A7 enum singletons. It is blocked by
`P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS`, must remain draft and unmerged,
and its branch is not changed by this documentation amendment.

The current board has A10 `done`, A11 `todo`, and A12 `todo`. Wave A remains
controlling and incomplete. Wave B remains candidate planning only and
inactive. `.agent/WAVE.md` remains byte-identical to current main at blob
`eb0b81acba0225d46d01cfc14f9a2e0b4f9f06da`.

Authority is applied in this order:

1. current repository and code;
2. current authoritative specifications;
3. ratified `.agent/DECISIONS.md`;
4. `docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md`;
5. `.agent/WAVE.md`;
6. current context and rationale documents;
7. historical handoffs;
8. legacy/archive archaeology.

SPECIFIED / RATIFIED, IMPLEMENTED, TESTED, SCIENTIFICALLY_QUALIFIED,
SECURITY_QUALIFIED, NETWORK_QUALIFIED, COMMERCIALLY_VALIDATED, and
PRODUCTION_QUALIFIED remain independent states. Documentation review, PR #46
tests, and repository regression evidence are not current-main A11
implementation or test evidence.

This amendment changes only the six authorized documentation paths. It changes
no Python, test, fixture, dependency, package, workflow, CI, quality baseline,
A0–A10 behavior, `.agent/WAVE.md`, A12 artifact, or Wave B artifact.

## 2. Reconciliation and KEEP → WRAP → REPAIR → REPLACE

### NO_CONFLICT

The R18 boundary preserves the ratified facts that observability is operational
and authority-free; disclosure is positive and allow-listed; A5 owns scoring;
A7 owns submission identity and lifecycle; owner meanings remain distinct; and
evidence, receipts, Challenge health, frontier, product, settlement, chain,
weight, and emission authority remain separately owned.

### DOCUMENTATION_LAG

The earlier `P1_UNENFORCEABLE_EVENT_PROVENANCE_CLAIM` correction remains
ratified: a canonical UUIDv4 proves no record, retained state, transition, or
authenticated provenance. PR #39 normally merged that correction. Current
documentation now lags the newly confirmed enum-singleton implementation
defect, not the provenance boundary.

### IMPLEMENTATION_LAG

Current main has no A11 package or focused test. PR #46 contains draft code and
tests, but is not repository implementation or test authority. Its repaired
`P1_GENERIC_DATACLASS_SERIALIZATION_BYPASS` remains closed at that draft head;
the closure does not resolve shared mutable enum references at its sink seam.

### MIGRATION_REQUIRED

KEEP `carbon/logging_utils` as the unchanged inert A0 compatibility marker and
KEEP all A5/A7 owner types and source unchanged. REPAIR the future A11 sink seam
by WRAPPING validated request semantics in fresh primitive-only A11-owned
snapshots. REPLACE no owner implementation and add no owner instrumentation.
Legacy logging, audit, receipt, exporter, and network paths remain outside A11.

### NEW_OWNER_DECISION_REQUIRED

The exact blocker is:

~~~text
P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS:
CONFIRMED

implementation defect:
YES

current main defect:
NO

contract-preserving implementation under current owner types:
NO

classification:
NEW_OWNER_DECISION_REQUIRED
~~~

Canonical Python enum members are process-wide mutable singletons. The old
sink-facing contract simultaneously required canonical A11/A5/A7 enums and
fresh sink-safe mutation isolation; no fresh exact canonical member exists.
Validation, copying, locking, or sanitize-and-restore cannot isolate a retained
singleton across concurrent and later calls.

R18 selects Option A only: immutable A11-owned primitive sink snapshots. Option
B, an A5/A7 owner-enum migration, requires separate owner review and is outside
this task. Option C would weaken the security boundary and is not authorized.
Production exporters, sandboxing, persistence, latency policy, dashboards,
alerts, authentication, public APIs, additional vocabulary, and later
scientific/economic authority still require separate decisions.

## 3. Ratified A11-R1 through A11-R17 record and R18 candidate

The A11-R1 through A11-R17 text below is preserved as the ratified historical
record. A11-R18, if independently reviewed, explicitly human-authorized, and
normally merged, supersedes only the sink-facing portions of A11-R1, A11-R2,
A11-R3, A11-R10, A11-R13, A11-R14, and A11-R16. All other behavior and every
authority ceiling remain in force. Until that merge, A11-R18 is a candidate,
not a ratified decision.

### A11-R1 — Exact package and module ownership

The sole future semantic and implementation owner is exactly:

~~~text
carbon/observability/
    __init__.py
    model.py
    providers.py
    service.py
~~~

The canonical focused test path is exactly:

~~~text
tests/cpu/test_observability.py
~~~

Exact file ownership is:

~~~text
model.py
    EventKind, MetricKind, DurationStage, BoundaryErrorKind
    ObservabilityEvent, BoundaryErrorEvent, ObservabilityResourceLimits
    ObservabilityError and its three direct concrete errors
    private exact-copy and validation helpers only
providers.py
    StructuredEventSink, MetricSink
    no concrete/default/global sink
service.py
    ObservabilityService
    private shared-capacity accounting
    private same-service reentrancy accounting
    private sink lookup/invocation/return validation
    private Exception/BaseException translation
    no owner instrumentation
__init__.py
    exact ordered fourteen-name re-export tuple only
    no private helper or owner-type re-export
~~~

The implementation does not repurpose `carbon/audit`, modify or alias the
inert A0 `carbon/logging_utils` compatibility marker, or add top-level
`carbon` exports. The documentation task creates none of these
implementation/test paths.

### A11-R2 — Exact nominal public surface, field order, and construction

The future exact ordered `carbon.observability.__all__` tuple is:

~~~python
(
    "EventKind",
    "MetricKind",
    "DurationStage",
    "BoundaryErrorKind",
    "ObservabilityEvent",
    "BoundaryErrorEvent",
    "ObservabilityResourceLimits",
    "StructuredEventSink",
    "MetricSink",
    "ObservabilityService",
    "ObservabilityError",
    "ObservabilityRequestError",
    "ObservabilityResourceError",
    "ObservabilityIntegrationError",
)
~~~

There is no logger wrapper, generic record, serializer, mapping event,
metadata bag, label bag, production provider, no-op default, global registry,
or extra error export.

The four enums have exact direct `str, Enum` inheritance, declaration order,
member names, and literal values:

~~~python
class EventKind(str, Enum):
    SUBMIT = "SUBMIT"
    SCORE = "SCORE"
    REJECT = "REJECT"
    FAILED_STRATEGY = "FAILED_STRATEGY"
    FAILED_INFRA = "FAILED_INFRA"

class MetricKind(str, Enum):
    SUBMIT_COUNT = "SUBMIT_COUNT"
    SCORE_COUNT = "SCORE_COUNT"
    REJECT_COUNT = "REJECT_COUNT"
    FAILED_INFRA_COUNT = "FAILED_INFRA_COUNT"
    STAGE_DURATION_NS = "STAGE_DURATION_NS"

class DurationStage(str, Enum):
    SUBMIT = "SUBMIT"
    SCORE = "SCORE"

class BoundaryErrorKind(str, Enum):
    MCP_REQUEST = "mcp.request.invalid"
    MCP_RESOURCE = "mcp.resource_limit_exceeded"
    MCP_TOOL_UNAVAILABLE = "mcp.tool_unavailable"
    MCP_CHALLENGE_UNAVAILABLE = "mcp.challenge_unavailable"
    MCP_SUBMISSION_UNAVAILABLE = "mcp.submission_unavailable"
    MCP_QUERY_BUDGET = "mcp.query_budget_exceeded"
    MCP_INTEGRATION = "mcp.integration_failure"
    LEADERBOARD_REQUEST = "leaderboard.request.invalid"
    LEADERBOARD_RESOURCE = "leaderboard.resource.exhausted"
    LEADERBOARD_UNAVAILABLE = "leaderboard.fixture.unavailable"
    LEADERBOARD_INTEGRATION = "leaderboard.integration.failed"
~~~

There are no aliases, `auto()` values, integer values, alternate lowercase
values, or extra members.

`ObservabilityEvent` is a frozen, slotted, representation-safe nominal value
with exactly these fields in this order:

~~~text
kind: exact EventKind
submission_id: exact A7 SubmissionId
submission_state: exact A7 SubmissionState
score_status: exact A5 ScoreStatus | None
~~~

`BoundaryErrorEvent` is a frozen, slotted, representation-safe nominal value
with exactly one field:

~~~text
error_kind: exact BoundaryErrorKind
~~~

`ObservabilityResourceLimits` is a frozen, slotted,
representation-safe nominal value with exactly one required field:

~~~text
max_concurrent_calls: exact built-in int in 1..2**64-1
~~~

The exact constructor is:

~~~python
ObservabilityService(
    event_sink: StructuredEventSink,
    metric_sink: MetricSink,
    resource_limits: ObservabilityResourceLimits,
)
~~~

All three arguments are mandatory. The resource value is copied and validated
at construction. There is no `None`, default, environment-selected backend,
singleton, module global, registry lookup, or production numeric default.

Exact types reject subclasses, booleans-as-integers, coercible primitives,
forged enum members, aliases, and generic lookalikes. Event/resource values
support no generic serialization or generic copy/deepcopy path. They never
invoke a caller-controlled `repr` or `str`.

### A11-R3 — Exact bounded capabilities

The only service operations are:

~~~python
ObservabilityService.emit_event(
    event: ObservabilityEvent | BoundaryErrorEvent,
) -> None
ObservabilityService.increment_counter(metric: MetricKind) -> None
ObservabilityService.observe_duration(
    stage: DurationStage,
    duration_ns: int,
) -> None
~~~

Successful operations return exact `None`. The service exposes no
`log(message, **fields)`, `emit(dict)`, `metric(name, labels, value)`,
`record(anything)`, batch, flush, retry, queue, exporter, serializer, or sink
selection operation. `logging.Logger` is not a Wave-A sink interface.

### A11-R4 — Closed submission-event matrix and honest provenance boundary

The exact valid event matrix is:

| EventKind | exact SubmissionState | exact ScoreStatus |
|---|---|---|
| `SUBMIT` | `RECEIVED` | `None` |
| `SCORE` | `SCORED` | `SCORED` or `MANDATORY_GATE_FAILED` |
| `REJECT` | `REJECTED` | `None` |
| `FAILED_STRATEGY` | `FAILED_STRATEGY` | `None` |
| `FAILED_INFRA` | `FAILED_INFRA` | `None` |

`ObservabilityEvent` is an owner-shaped, process-local operational observation
request. A11 validates only exact nominal types, field shape, and the closed
kind/state/status consistency matrix. It does not verify A7 record existence,
read the current retained A7 state, prove that an A7 transition occurred, or
authenticate A5/A7 provenance. Trusted composition alone supplies the factual
relationship to an owner transition.

`None`, wrong types, subclasses, malformed UUIDs, and mismatched matrix rows
reject. A syntactically valid but unbound canonical UUIDv4 remains valid at the
A11 shape boundary, but carries no lifecycle, scientific, audit, receipt,
public, security, settlement, or economic authority. Exact nominal values are
correctness values, not authenticated capabilities. Production provenance,
authorization, and evidence remain separately deferred. No A7 service/store,
private record, capability, signature, receipt, second identity, or new event
field is added.

Every kind/state/status combination outside the table is an invalid request.
In particular, `PUBLISHED`, `CANCELLED`, `VALIDATED`, `QUEUED`, `RUNNING`,
retryable infrastructure, `PACK_NOT_READY`, and forged or cross-enum statuses
are not silently remapped to a current event.

This event family is internal operational telemetry. It is not a public card,
MCP result, leaderboard value, receipt, evidence record, lifecycle store, or
scientific result.

### A11-R5 — Closed A9/A10 safe-error observation

`BoundaryErrorEvent` accepts only exact `BoundaryErrorKind`. It contains no
`SubmissionId`, Challenge key, requester, request value, tool payload, cursor,
provider, exception object/text, message, cause, context, traceback, private
field, hidden identifier, seed, draw, arbitrary string, or mapping.

Trusted composition may map only these exact public owner classes to these
exact closed members:

| Exact owner error class | `BoundaryErrorKind` member |
|---|---|
| `McpRequestError` | `MCP_REQUEST` |
| `McpResourceError` | `MCP_RESOURCE` |
| `McpToolUnavailableError` | `MCP_TOOL_UNAVAILABLE` |
| `McpChallengeUnavailableError` | `MCP_CHALLENGE_UNAVAILABLE` |
| `McpSubmissionUnavailableError` | `MCP_SUBMISSION_UNAVAILABLE` |
| `McpQueryBudgetError` | `MCP_QUERY_BUDGET` |
| `McpIntegrationError` | `MCP_INTEGRATION` |
| `LeaderboardRequestError` | `LEADERBOARD_REQUEST` |
| `LeaderboardResourceError` | `LEADERBOARD_RESOURCE` |
| `LeaderboardUnavailableError` | `LEADERBOARD_UNAVAILABLE` |
| `LeaderboardIntegrationError` | `LEADERBOARD_INTEGRATION` |

The mapping uses exact class identity, not `isinstance` or arbitrary `.code`
inspection. Production `carbon.observability` imports neither owner package; a
test-local mapping harness may import those public classes.

Every raw provider exception must first be translated by its A9/A10 owner.
A11 never receives or classifies it. Unknown codes, raw exceptions, owner
payloads, identities, and hidden values fail closed. Reference, generator,
reconstruction, retry, evidence, treasury, settlement, commercial-acceptance,
and Challenge-health categories remain unrepresented until exact public owner
types and integration seams exist. Omission is not collapse.

### A11-R6 — Closed metrics, durations, empty labels, and cardinality

The counter operation accepts only exact `SUBMIT_COUNT`, `SCORE_COUNT`,
`REJECT_COUNT`, and `FAILED_INFRA_COUNT`. Each call increments exactly one and
accepts no supplied value or delta. `STAGE_DURATION_NS` is rejected by
`increment_counter` and is represented only by
`observe_duration(stage, duration_ns)`.

Wave-A metric labels are exactly empty. The `MetricSink` receives no mapping,
tuple of labels, keyword metadata, or tag collection. Neither public metric
operation accepts a label argument.

`SubmissionId`, Challenge identity/version, requester, hotkey, wallet,
customer, result ID, score, rank, cursor, provider, exception, failure cause,
or arbitrary value cannot become a metric label. `DurationStage` is a closed
typed argument to the one duration operation, not an arbitrary label map.

Metric cardinality is therefore bounded structurally by four counter members
plus the two closed duration stages. Adding a metric or stage requires a later
contract change and review.

No `FAILED_STRATEGY_COUNT`, gauge, arbitrary histogram, set, decrement, reset,
dynamic name, arbitrary numeric value, or generic metric operation exists.
Direct A5–A10 instrumentation remains deferred.

### A11-R7 — Exact A7 correlation identity only

A11 reuses exact public A7 `SubmissionId`. It creates no correlation ID,
trace ID, span ID, request ID, receipt ID, result ID, or alias.

Before sink access, A11 reconstructs a fresh exact `SubmissionId` through its
owner constructor from the exact allow-listed value. The copied value may
appear only as the structured `ObservabilityEvent.submission_id` correlation
field. It may not appear in a metric, metric label, error, free-form text,
`repr`, generic serialization, public/miner/customer value, or requester
identity.

This reconstruction proves canonical UUIDv4 syntax and mutation isolation
only. It does not prove Carbon minting, record existence, retained state, or a
transition. An unbound but syntactically valid UUID remains non-authoritative.

`RequesterIdentity` never crosses the A11 boundary and is not imported.
Nothing in this contract revokes the separately ratified A7/A9 use of
`SubmissionId` in their own owner-controlled interfaces; “not public” here
means not emitted as public observability material.

### A11-R8 — Failure and lifecycle separation

A11 does not invent lifecycle or scientific semantics. It reuses exact public
A7 `SubmissionState` and A5 `ScoreStatus` only through the A11-R4 matrix.

- `REJECT` is the owner-shaped declaration of exact A7 `REJECTED` request or
  admission semantics; it is not strategy, scientific, or infrastructure
  failure.
- `FAILED_STRATEGY` accepts only the exact terminal A7 `FAILED_STRATEGY` label;
  it does not accept ambiguous or infrastructure causes.
- `FAILED_INFRA` accepts only the exact terminal A7 `FAILED_INFRA` label; it
  does not absorb retryable infrastructure or scientific failure.
- `SCORE` with exact A7 `SCORED` and A5 `SCORED` carries only the closed scored
  category, never its numeric score.
- `SCORE` with exact A7 `SCORED` and A5 `MANDATORY_GATE_FAILED` preserves the
  mandatory scientific-gate disposition and does not relabel it as strategy,
  infrastructure, or request failure.
- A5 `PACK_NOT_READY` remains non-scientific unavailability. It cannot satisfy
  A7 `SCORED`, cannot construct a `SCORE` event, and cannot be relabeled by A11
  as `FAILED_STRATEGY`, `FAILED_INFRA`, or `REJECT`. The matrix accepts only
  the exact terminal `FAILED_INFRA` label; A11 does not verify that an owner
  action created that state.

A8 private failure causes and outcomes are not imported. Current A7 terminal
states provide the first public projection seam; future reference, generator,
reconstruction, retry, treasury, settlement, commercial, or incident
categories require owner types and later ratification. Omission is not
collapse.

A11 event kinds are internal operational categories and do not widen A6's
exact public `failure_tags` vocabulary.

### A11-R9 — No score, rank, or adaptive-oracle telemetry

A11 never accepts, derives, inspects, serializes, or emits:

- raw or combined score;
- score components, legs, gates, margins, thresholds, stress values, or
  diagnostics;
- score delta, rank, rank delta, ordering, tie, history, or leaderboard state;
- priors, estimates, scaffolds, mock/light results, feedback, or query history.

The exact A5 `ScoreStatus` member on a `SCORE` event is a closed category only.
A5 remains sole scoring authority. A11 cannot become an adaptive-exam oracle,
change a score, influence ranking, or decide Challenge health.

### A11-R10 — Positive construction; no generic sanitization

Every public operation follows this order before sink access:

~~~text
exact outer type validation
→ positive field extraction in declared field order
→ exact owner/closed-enum validation
→ prohibited-data exclusion by the closed shape
→ fresh immutable A11-owned reconstruction
→ non-blocking resource/reentrancy acquisition
→ one corresponding sink access
~~~

Unknown fields and wrong shapes fail closed. Exact slotted event/resource
values, closed enums, fixed integers, and exact owner values structurally
eliminate arbitrary mappings, iterables, descriptors, object graphs, cycles,
aliases, and free-form textual payloads from the accepted model.

The implementation does not traverse or stringify a mapping, iterable,
exception, strategy, provider object, or arbitrary value. It does not call
hostile `repr`/`str`, use reflection to discover fields, call `asdict`, pickle,
JSON, generic serialization, or generic recursive redaction. It does not
serialize then redact.

Because Wave A has no allow-listed free-form textual event field, it has no
pattern-redaction engine. CR/LF injection, Unicode confusables, embedded
secrets, and oversized text are eliminated by type/field absence; the one
correlation string is reconstructed through the exact fixed-length ASCII UUID
owner. Any later allow-listed text field requires a new contract; pattern
redaction could then be defense in depth only.

Unsafe material is rejected rather than silently normalized, truncated,
hashed, anonymized, or transformed.

### A11-R11 — Forbidden observability material

No accepted event, metric, duration, error, representation, sink argument, or
captured alias may contain:

- official/master/derived seeds, draw IDs, roles, domains, contexts, entropy,
  nonces, commitments, preimages, or hidden-pack identity;
- full Strategy documents, parameters, weights, checkpoints, or artifacts;
- `RequesterIdentity`, hotkeys, wallets, customer/participant identity,
  credentials, authentication material, fee/payment/reward state;
- result IDs, receipt IDs, cursors, publication sequences, provider metadata;
- priors, estimates, scaffolds, mock/light feedback or query history;
- score values/components, gates, margins, stress values, diagnostics, rank or
  rank history;
- backend exception text, exception objects, stack traces, file paths,
  commands, environment names/values, or arbitrary diagnostics.

Fixed A11 sink/error handling cannot introduce a diagnostic payload or
fallback message containing forbidden material. Sink exceptions are never
echoed. A production sink remains separately responsible for honoring this
contract; no production sink is shipped or qualified in Wave A.

### A11-R12 — Duration and clock policy

`observe_duration` accepts exactly:

~~~text
stage: exact DurationStage.SUBMIT or DurationStage.SCORE
duration_ns: exact built-in int in 0..2**64-1
~~~

Booleans, subclasses, floats, coercible numerics, negatives, and overflow are
invalid requests. Nanoseconds are the only unit. Zero is valid.

`ObservabilityService` emits no timestamp and performs no wall-clock,
monotonic-clock, current-time, timezone, date, sleep, deadline, or elapsed-time
measurement. Duration is supplied by trusted composition, copied as an exact
integer, and is descriptive only. It cannot alter a domain result, score,
lifecycle, retry, rank, publication, Challenge health, or economic action.

Execution, publication, MCP, leaderboard, Challenge-health, evidence, and
other stage additions require later owner-approved integration.

### A11-R13 — Protocol seams and no concrete production provider

The exact standard-library Protocol seams are:

~~~python
class StructuredEventSink(Protocol):
    def emit_event(
        self,
        event: ObservabilityEvent | BoundaryErrorEvent,
        /,
    ) -> None: ...

class MetricSink(Protocol):
    def increment_counter(self, metric: MetricKind, /) -> None: ...
    def observe_duration(
        self,
        stage: DurationStage,
        duration_ns: int,
        /,
    ) -> None: ...
~~~

Trusted composition supplies structural concrete sinks. Sinks need not
subclass the Protocols. The Protocols are not runtime-checkable, and the
service performs no `isinstance` Protocol introspection or exact-type gate on
the concrete sink objects.

Each sink method must return exact `None`. A missing or call-incompatible
method or a non-`None` return is an integration failure. Test acceptance may
use test-local in-memory recording sinks; no in-memory sink is exported from
the package.

No OpenTelemetry, Prometheus, StatsD, logging backend, HTTP client/server,
filesystem, database, socket, queue, thread, task, exporter, dashboard,
alerting, or environment-selected provider is added. There is no default
global sink, fallback logger, or singleton.

### A11-R14 — Sink failure, capacity, blocking, reentrancy, and domain results

`max_concurrent_calls` is one shared per-service non-blocking capacity across
all three public operations. Capacity exhaustion raises the fixed resource
error before sink method lookup or invocation. The permit is released in
`finally` after success, A11-created failure, translated ordinary `Exception`,
and propagated non-`Exception` `BaseException`.

Reentry into the same `ObservabilityService` from one active sink call is
rejected non-blockingly with the same resource error before a second sink call,
even when configured capacity remains. Reentry through another service
instance is outside this instance's policy. The service holds no ordinary
mutex across a sink call and creates no recursive fallback diagnostic.

One public A11 operation makes at most one corresponding synchronous sink
call. There is no batching, queue, retry, fallback, background work, or
exactly-once durability claim. Concurrent callers receive no total-order
guarantee; A11 itself does not delay, queue, suppress, duplicate, or reorder a
domain action.

Every ordinary sink-origin `Exception`, including a sink-raised public A11
error, descriptor/hook failure, invocation failure, or wrong return, maps to
one new fixed `ObservabilityIntegrationError` without cause/context chaining.
No sink text, object, payload, or partial value escapes. A `BaseException` that
is not an `Exception`, including `KeyboardInterrupt`, `SystemExit`, and
`GeneratorExit`, propagates unchanged. Source must contain no `except
BaseException` around sink access or translation.

Finite concurrency bounds simultaneous sink occupancy but cannot prove that a
trusted synchronous in-process sink will return. Wave A adds no timer,
preemption, worker, or background thread. Sink latency/blocking qualification
is a later composition/production-provider responsibility. Trusted
composition must invoke telemetry outside owner locks and only after any
domain result that must survive has been determined.

A11 accepts and returns no domain result and owns no domain mutation. The
first implementation instruments no A5–A10 owner. A later composition task
must preserve an already-determined domain result when telemetry raises; it
must not roll back, retry, suppress, reorder, or reinterpret the domain action.

### A11-R15 — Exact error taxonomy

The hierarchy is exactly:

~~~text
ObservabilityError(Exception)

ObservabilityRequestError(ObservabilityError)
    code: observability.request.invalid
    message: Observability request is invalid.

ObservabilityResourceError(ObservabilityError)
    code: observability.resource.exhausted
    message: Observability resource limit was exceeded.

ObservabilityIntegrationError(ObservabilityError)
    code: observability.integration.failed
    message: Observability sink failed.
~~~

The three concrete errors are direct `ObservabilityError` subclasses. Errors
have fixed immutable code/message values, no diagnostic constructor argument,
no value echo, no hostile `repr`/`str`, no private payload, no cause/context
chain, and no generic serialization/copy path.

Wrong caller/event/enum/metric/stage/duration shapes and malformed mandatory
constructor resource policy map to `ObservabilityRequestError`. Operational
capacity/reentrancy exhaustion maps to `ObservabilityResourceError`. Sink
integration failures map to `ObservabilityIntegrationError`.

Repository conventions are mixed: A7 has a separate historical resource
policy error, while the closest bounded A10 surface uses its fixed
request/resource taxonomy for construction validation versus runtime
exhaustion. The requested A11 hierarchy is complete and sufficient, so this
contract deliberately adds no separate constructor/resource-policy error.

### A11-R16 — Exact dependency direction and initial non-integration

The exact per-file direction is:

~~~text
model.py
    -> Python standard library
    -> from carbon.fees import SubmissionId, SubmissionState
    -> from carbon.scoring import ScoreStatus
providers.py
    -> Python standard-library typing
    -> A11 model types only
service.py
    -> Python standard library
    -> A11 model types
    -> A11 provider Protocols
__init__.py
    -> explicit local model/provider/service re-exports only
~~~

These exact public owner types preserve A7 lifecycle versus A5 scientific
disposition without duplicating either vocabulary. Their public package-root
imports may transitively initialize owner modules; the enforceable prohibition
is no direct A11 source import or call of A5 engine/results, A7
service/private-store/record/fee internals, or other owner behavior. Tests must
not claim impossible `sys.modules` absence for those transitive imports.

Production A11 directly imports no A6, A8, A9, or A10 module, no
`RequesterIdentity`, and no legacy validator/neuron/Landscape object. The
exact A9/A10 class mapping exists only in trusted later composition and a
test-local harness. A5–A10 packages do not import `carbon.observability`; no
owner service changes or is instrumented. Direct instrumentation is a later
task requiring an exact non-circular hook and domain-result-preservation
review. No circular import is permitted.

The package preserves zero mandatory distribution dependencies and must import
from a no-dependency installed wheel outside the checkout without loading
optional scientific, web, filesystem, network, environment, current-time,
logging-backend, Landscape, neuron, Bittensor, chain, settlement, weight, or
emission modules.

### A11-R17 — A12 and authority boundary

A11 may expose the closed source/runtime facts above for a later A12 invariant
suite. A11 does not create `tests/invariants/`, add or change a pytest marker,
modify CI/workflows, change a quality baseline, change A12 status/ticket, or
claim Wave A complete.

A11 is not and cannot become in this contract:

- scientific evidence, an `EvaluationCard`, receipt, transcript, audit or
  re-execution system, durable event ledger, or submission lifecycle owner;
- scoring, Challenge-health, information-budget, adaptive-query, frontier, or
  Product Qualification authority;
- authentication, public API, production monitoring backend, incident system,
  dashboard, alerting service, or threshold owner;
- commercial, settlement, treasury, chain, Bittensor, weight, emission, or
  LIVE authority;
- A12 aggregate-invariant CI.

No A11 value creates scientific, economic, LIVE, frontier, product,
settlement, chain, weight, or emission authority. A12 remains separately owned
and `todo`. Current-main Wave B planning remains candidate-only and inactive;
this contract changes no activation artifact and authorizes no B ticket.

### A11-R18 — Immutable A11-owned sink snapshot boundary

The public service request API remains exactly:

~~~python
ObservabilityService.emit_event(
    event: ObservabilityEvent | BoundaryErrorEvent,
) -> None

ObservabilityService.increment_counter(
    metric: MetricKind,
) -> None

ObservabilityService.observe_duration(
    stage: DurationStage,
    duration_ns: int,
) -> None
~~~

`ObservabilityEvent`, `BoundaryErrorEvent`, `MetricKind`, and `DurationStage`
are validated request values only. They are not sink arguments and are not
called sink-safe snapshots. Public request construction continues to accept
exact canonical A11/A5/A7 enums and creates no record, provenance,
authentication, evidence, or authority claim.

The future public A11-owned sink values are exactly:

~~~text
SubmissionEventSnapshot(
    kind: str,
    submission_id: str,
    submission_state: str,
    score_status: str | None,
)

BoundaryErrorSnapshot(
    error_code: str,
)

CounterMetricSnapshot(
    metric_name: str,
)

DurationMetricSnapshot(
    stage: str,
    duration_ns: int,
)
~~~

`SubmissionEventSnapshot` has exactly ordered fields `kind`, `submission_id`,
`submission_state`, `score_status`. `kind` is an exact built-in `str` from
`SUBMIT`, `SCORE`, `REJECT`, `FAILED_STRATEGY`, or `FAILED_INFRA`.
`submission_id` is an exact built-in `str`, exactly 36 ASCII characters, in the
canonical UUIDv4 spelling already validated through a fresh public A7
`SubmissionId` reconstruction; it is internal correlation only.
`submission_state` is an exact built-in `str` from `RECEIVED`, `SCORED`,
`REJECTED`, `FAILED_STRATEGY`, or `FAILED_INFRA`. `score_status` is `None` or an
exact built-in `str` from `SCORED` or `MANDATORY_GATE_FAILED`. The exact A11-R4
event matrix remains authoritative. The snapshot contains no `EventKind`,
`SubmissionState`, `ScoreStatus`, `SubmissionId`, or other enum or owner object.

`BoundaryErrorSnapshot` has exactly one field, `error_code`, an exact built-in
`str` drawn only from the existing eleven `BoundaryErrorKind` literal values.
It contains no enum member, owner error, exception, payload, request value,
provider value, identity, seed, draw, or metadata.

`CounterMetricSnapshot` has exactly one field, `metric_name`, an exact built-in
`str` from `SUBMIT_COUNT`, `SCORE_COUNT`, `REJECT_COUNT`, or
`FAILED_INFRA_COUNT`. There is no label, delta, dynamic name, boundary-error
counter, gauge, reset, or decrement.

`DurationMetricSnapshot` has exactly ordered fields `stage`, `duration_ns`.
`stage` is an exact built-in `str` from `SUBMIT` or `SCORE`; `duration_ns` is an
exact built-in `int` in `0..2**64-1`. It contains no clock, timestamp, label
map, arbitrary dimension, or `DurationStage` member.

Each snapshot must be an exact manual slotted non-dataclass nominal class; a
fresh outer object per admitted service operation; free of an instance
`__dict__`; immutable through normal assignment and deletion;
representation-safe; non-copyable through `copy.copy` and `copy.deepcopy`;
non-pickleable; and rejected by `dataclasses.asdict`, `dataclasses.astuple`, and
`dataclasses.replace`. Snapshot fields contain only exact immutable built-in
`str`, `int`, or `None`, with no mapping, iterable, descriptor, arbitrary object
graph, owner object, enum, exception, or metadata. Snapshots are authority-free
and are never accepted as service requests. Direct public construction, if
retained, proves exact closed shape only and creates no owner transition,
lifecycle, scientific, audit, receipt, public, security, settlement, or
economic authority.

The effective future ordered `carbon.observability.__all__` tuple becomes:

~~~python
(
    "EventKind",
    "MetricKind",
    "DurationStage",
    "BoundaryErrorKind",
    "ObservabilityEvent",
    "BoundaryErrorEvent",
    "ObservabilityResourceLimits",
    "SubmissionEventSnapshot",
    "BoundaryErrorSnapshot",
    "CounterMetricSnapshot",
    "DurationMetricSnapshot",
    "StructuredEventSink",
    "MetricSink",
    "ObservabilityService",
    "ObservabilityError",
    "ObservabilityRequestError",
    "ObservabilityResourceError",
    "ObservabilityIntegrationError",
)
~~~

Exactly eighteen names are exported. The previous fourteen-name surface is
superseded only after A11-R18 normally merges. No owner type, generic logger,
serializer, provider, mapper, private helper, or extra error is exported.

Effective future module ownership becomes:

~~~text
model.py
    EventKind, MetricKind, DurationStage, BoundaryErrorKind
    ObservabilityEvent, BoundaryErrorEvent, ObservabilityResourceLimits
    SubmissionEventSnapshot, BoundaryErrorSnapshot
    CounterMetricSnapshot, DurationMetricSnapshot
    ObservabilityError and its three direct concrete errors
    private exact request-validation and snapshot-construction helpers only
providers.py
    StructuredEventSink, MetricSink
    no concrete/default/global sink
service.py
    ObservabilityService
    request-to-snapshot conversion
    shared capacity and same-service reentrancy accounting
    sink lookup/invocation/return validation
    exception translation
    no owner instrumentation
__init__.py
    exact ordered eighteen-name re-export tuple only
~~~

The exact structural, non-runtime-checkable Protocols become:

~~~python
class StructuredEventSink(Protocol):
    def emit_event(
        self,
        event: SubmissionEventSnapshot | BoundaryErrorSnapshot,
        /,
    ) -> None: ...


class MetricSink(Protocol):
    def increment_counter(
        self,
        metric: CounterMetricSnapshot,
        /,
    ) -> None: ...

    def observe_duration(
        self,
        metric: DurationMetricSnapshot,
        /,
    ) -> None: ...
~~~

Concrete sinks subclass neither Protocol. No production sink is added. The
three public service methods remain unchanged.

Before capacity acquisition or sink access, the service must:

1. validate the exact outer request type;
2. validate exact canonical enum type, identity, name, and literal value;
3. validate the exact event matrix or metric/duration boundary;
4. reconstruct and validate `SubmissionId` through the public A7 constructor
   where applicable;
5. map validated semantics to A11 module-owned hard-coded literal strings;
6. construct a fresh snapshot containing no request, owner, or enum reference;
7. acquire capacity and same-service reentrancy permission; and
8. make at most one sink call.

The service never passes `EventKind`, `MetricKind`, `DurationStage`,
`BoundaryErrorKind`, `SubmissionState`, `ScoreStatus`, `SubmissionId`,
`ObservabilityEvent`, or `BoundaryErrorEvent` to a sink. It never carries a
mutable enum member forward, traverses or copies an enum member `__dict__`, or
uses an enum attribute as emitted material. Caller-added enum attributes are
never consulted, copied, retained, rendered, or emitted. Corrupted `_name_` or
`_value_` state rejects before capacity and sink access. Snapshot fields come
from A11 fixed literal tables after exact validation. No sanitize-and-restore
mutation of shared state is permitted, and no global lock is held across sink
code.

The exact supplied-value scope is:

~~~text
Mutation through an object supplied by A11 to a sink cannot alter caller,
owner, retained, concurrent, or later A11 state.
~~~

Each sink receives one distinct fresh per-call snapshot. A sink may use Python
escape hatches such as `object.__setattr__` to alter its own snapshot, but that
mutation cannot affect another operation because the snapshot contains no
shared mutable owner or enum reference and A11 retains no snapshot for reuse. A
sink-retained snapshot cannot alter a later call. A11 does not sandbox arbitrary
in-process sink code; a sink that independently imports and mutates unrelated
process globals acts outside the A11 supplied-value boundary. Process
isolation, capability restriction, and hostile-code sandboxing remain deferred.
This is not permission to supply a shared mutable object to a sink.

The service-request dependencies remain exact public `SubmissionId` and
`SubmissionState` from `carbon.fees`, exact public `ScoreStatus` from
`carbon.scoring`, and Python standard library. Snapshot classes depend only on
Python built-ins and local A11 validation. A11 imports no production A9/A10
module; no A5/A7 owner source changes; no owner package imports
`carbon.observability`; and no owner service is instrumented.

## 4. Canonical future threat and test contract

The sole future focused path is:

~~~text
tests/cpu/test_observability.py
~~~

This documentation task does not create or modify it. The future suite must
cover at least the following.

### Surface and exact nominal values

- exact ordered eighteen-name root export tuple with no aliases or extras;
- exact direct `str, Enum` inheritance, declaration order, member names,
  literal values, and absence of aliases for all four request enums;
- exact four-field submission event, one-field boundary-error event, and
  one-field resource-limit request order;
- exact snapshot types and ordered fields: `SubmissionEventSnapshot(kind,
  submission_id, submission_state, score_status)`,
  `BoundaryErrorSnapshot(error_code)`,
  `CounterMetricSnapshot(metric_name)`, and
  `DurationMetricSnapshot(stage, duration_ns)`;
- exact manual slotted non-dataclass snapshot classes with no instance
  `__dict__`, normal assignment/deletion, generic copy/deepcopy, pickle, or
  dataclass traversal path, and only exact built-in primitive fields;
- request/resource representation safety and the previous generic-dataclass
  correction remain intact;
- exact three-argument constructor and exact three service operations only;
- exact type, forged-member, subclass, bool/int, coercion, and u64 rejection;
- unknown field/shape rejection without mapping, iterable, descriptor, or
  object-graph traversal.

### Event and owner projection

- every exact A11-R4 valid combination and every mismatched combination;
- fresh A7 `SubmissionId` reconstruction followed by exact canonical built-in
  string projection into a fresh `SubmissionEventSnapshot`;
- exact `SubmissionState.RECEIVED`, `SCORED`, `REJECTED`,
  `FAILED_STRATEGY`, and terminal `FAILED_INFRA` request validation and literal
  snapshot projection;
- A5 `SCORED` versus `MANDATORY_GATE_FAILED` separation on `SCORE`;
- no sink receives an `EventKind`, `SubmissionState`, `ScoreStatus`,
  `SubmissionId`, or `ObservabilityEvent` object;
- each request enum may carry an arbitrary caller-added canary attribute
  without that attribute being consulted or reaching the snapshot;
- corrupted canonical `_name_` or `_value_` state rejects before capacity and
  sink access;
- request-enum mutation after snapshot construction cannot alter the snapshot;
- rejection of `None`, wrong/subclass/malformed IDs and acceptance of a
  syntactically valid unbound UUID without granting owner provenance;
- proof that A11 performs no A7 lookup, current-state check, transition proof,
  or A5/A7 authentication and that trusted composition owns factual timing;
- rejection/omission of `PACK_NOT_READY`, retryable infrastructure,
  `PUBLISHED`, `CANCELLED`, and unsupported future categories;
- no second identity/lifecycle/status vocabulary and no A8 private-type
  dependency;
- no `RequesterIdentity`, result ID, cursor, public correlation, or A6 failure
  tag widening.

### A9/A10 boundary-error projection

- exact one-field `BoundaryErrorEvent` request, exact eleven-member closed enum,
  and exact primitive-only `BoundaryErrorSnapshot(error_code)` sink value;
- exact-class-only test-local mapping for all seven public A9 and four public
  A10 concrete errors, including distinct budget/unavailable meanings;
- no mapping for the code-less A10 `LeaderboardError` base, subclasses,
  generic exceptions, lookalike objects, or unknown codes;
- no production A9/A10 import and no exception object/text/message/cause/
  context/traceback, owner payload, identity, provider, seed, or draw crossing
  the A11 snapshot boundary;
- no sink receives a `BoundaryErrorKind` or `BoundaryErrorEvent` object, and
  caller-added enum attributes never cross;
- proof that A9/A10 owner translation precedes A11 and a closed enum does not
  authenticate that an owner error actually occurred.

### Metric and duration bounds

- exact four incrementable counter members and rejection of
  `STAGE_DURATION_NS` as a counter;
- exact mapping to four primitive `CounterMetricSnapshot.metric_name` values;
- exact `SUBMIT`/`SCORE` duration-stage requests and primitive
  `DurationMetricSnapshot.stage` values;
- exact built-in integer nanoseconds in `0..2**64-1`, including zero and both
  bounds, copied into `DurationMetricSnapshot.duration_ns`;
- no sink receives `MetricKind`, `DurationStage`, or a raw duration pair;
- empty arbitrary-label surface and structurally bounded cardinality;
- no dynamic name, gauge, arbitrary histogram, decrement, reset, value, or
  unratified failed-strategy counter;
- no timestamp/current-time import, access, or nondeterministic clock read.

### Positive construction and leakage

- exact outer request, canonical enum semantics, matrix/boundary, fresh A7 ID,
  fixed-literal mapping, and fresh snapshot construction before capacity or
  sink access;
- no generic serializer, recursive sanitizer, reflection, `asdict`, pickle,
  JSON, serialize-then-redact path, enum-`__dict__` traversal/copy, or
  snapshot-and-restore mutation of shared enum state;
- hostile `repr`/`str`, mapping, iterable, descriptor, cycle, alias, mutation,
  CR/LF, Unicode, and oversized-value traps, including caller-added enum
  attributes and mutation races;
- complete exclusion of seed/secret/Strategy/parameter/requester/hotkey/wallet/
  customer/result/cursor/score/rank/query/exception object or text/stack/path/
  command/environment material, including values attached to an enum member;
- no adaptive-exam oracle, Challenge-health transition, scientific evidence,
  frontier/Product Qualification, settlement, chain, weight, or emission
  behavior.

### Sink, errors, concurrency, and domain isolation

- structural Protocol implementations without subclassing or runtime Protocol
  introspection;
- exact R18 Protocol arguments: submission/boundary snapshots for events,
  counter snapshot for increment, and one duration snapshot for observation;
- successful exact `None` and at most one sink call receiving one exact fresh
  snapshot per admitted public operation;
- every snapshot field is exact built-in `str`, `int`, or `None`, with no enum,
  owner nominal, request object, arbitrary object graph, or retained A11 alias;
- normal or `object.__setattr__` mutation of a supplied snapshot cannot affect
  the caller, owner enums, another service, a concurrent operation, or a later
  call; a sink-retained snapshot cannot affect later calls;
- distinct outer snapshots for every call, no snapshot reuse, no
  sanitize-and-restore global mutation, and no ordinary mutex held across sink
  execution;
- no process-sandbox claim for a sink that independently imports and mutates an
  unrelated process global;
- missing/call-incompatible method, wrong return, hostile descriptor/hook, and
  ordinary `Exception` translation;
- sink-raised A11 public errors translated to a fresh integration error;
- no sink value/text/payload/cause/context leakage and no fallback logger;
- unchanged propagation of `KeyboardInterrupt`, `SystemExit`, and
  `GeneratorExit` where practical, plus a source guard forbidding `except
  BaseException`;
- shared non-blocking capacity, exact-at-capacity behavior, same-service
  reentrancy rejection, and `finally` release after every exit class;
- no queue, retry, batching, background work, or exactly-once claim;
- a blocking-sink test proving the configured capacity rejects additional
  calls without claiming timeout/preemption;
- no owner lock/domain object/result accepted or mutated, and a composition
  harness proving an already-determined domain result survives telemetry
  failure.

### Dependency, packaging, and regression

- per-file source guards enforcing the amended R16 matrix: request values use
  exact public A5/A7 types, snapshots use only built-ins/local A11 validation,
  service owns request-to-snapshot conversion, and providers reference snapshot
  types;
- no A5/A7 owner-source change, no owner instrumentation, and no owner import
  of `carbon.observability`;
- source guards including no direct
  A5 engine/result or A7 service/private-store/fee import or call while not
  making a false transitive-module-absence claim;
- source guards against direct A6, A8, A9, A10, `logging_utils`,
  audit/evidence, optional exporters, filesystem,
  network, environment, time, Landscape, neuron, Bittensor, chain, settlement,
  weight, and emission imports;
- no OpenTelemetry, Prometheus, StatsD, logging backend, HTTP, database,
  dashboard, alert, or production provider;
- source-tree and fresh no-dependency installed-wheel/outside-tree proof of the
  exact eighteen-name surface, snapshot structure, primitive fields, request
  conversion, distinct/retained/concurrent/later mutation isolation, unchanged
  service signatures, and absence of owner changes;
- full default CPU regression;
- strict Ruff and Black on later changed Python paths;
- repository no-new-debt evidence.

Documentation statements, existing A0–A10 tests, and repository regression
success do not count as A11 implementation or A11 test evidence.

## 5. Future implementation sequence

The exact next-move sequence is:

1. independently review and ratify exact A11-R18;
2. normally merge the exact reviewed amendment only after explicit human
   authorization;
3. synchronize PR #46 with the amendment merge;
4. repair PR #46 to implement the immutable A11-owned snapshot boundary; and
5. independently review the repaired exact-head implementation before any
   ready or merge action.

PR #46 remains draft and blocked; its branch stays unchanged while its body is
updated only to record the blocker and withdraw the stale audit claim.
Direct A5–A10 instrumentation, production providers, A12 work, Wave-A closeout,
and Wave-B activation remain outside this sequence.

## 6. Documentation-candidate validation and maturity boundary

Before publication, this candidate must prove:

- the diff contains exactly the six authorized documentation paths and no
  seventh path;
- `.agent/WAVE.md` is byte-identical to current main at blob
  `eb0b81acba0225d46d01cfc14f9a2e0b4f9f06da`;
- A10 remains `done`; A11 and A12 remain `todo`; Wave A remains incomplete;
- the A11 ticket contains exactly 66 unchecked implementation criteria and zero
  checked criteria;
- this plan contains zero checkbox markers;
- no Python, test, fixture, dependency, packaging, workflow, CI, or quality
  baseline changes;
- PR #39's A11-R1 through A11-R17 ratification history remains explicit while
  the exact R18 sink-facing supersession is recorded without silent rewriting;
- PR #46 remains draft and unmerged at unchanged branch head
  `5b0b4927f8a4d2e6438b20a8201da43ae2a0645e`, with its stale audit claim
  withdrawn only through the PR body metadata update;
- all current-main Wave B artifacts and activation gates are byte-preserved,
  Wave A remains controlling, and Wave B remains inactive;
- no A0–A10 contract is weakened and no production/exporter/persistence/auth/
  alert/threshold/Challenge-health/adaptive-query/evidence/frontier/product/
  settlement/chain/weight/emission authority is added;
- `git diff --check` passes;
- the documentation commit has exact current-main parent and the exact six-path
  manifest, and the final worktree is clean;
- publication is a draft PR only, with no ready/merge/auto-merge action.

The exact candidate maturity ceiling is:

~~~text
A11-R1 through A11-R17:
RATIFIED

A11-R18:
SPECIFIED as this exact candidate;
RATIFIED only after independent review, explicit human authorization, and
normal merge

A11 IMPLEMENTED: NO on current main
A11 TESTED: NO on current main
A11 draft implementation:
PR #46 is blocked by P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS and is not
current repository implementation or test authority.
A11 SCIENTIFICALLY_QUALIFIED: NO
A11 SECURITY_QUALIFIED: NO
A11 NETWORK_QUALIFIED: NO
A11 COMMERCIALLY_VALIDATED: NO
A11 PRODUCTION_QUALIFIED: NO
A11 WAVE STATUS: todo on current main
A12: todo
Wave A: incomplete
Wave B: candidate planning only; inactive
~~~

A draft PR is only a candidate. It is not review, authorization, readiness,
ratification, implementation, test evidence, or merge authority.
