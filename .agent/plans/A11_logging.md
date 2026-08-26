# A11 — bounded in-process operational observability contract candidate

**Ticket:** `.agent/tickets/A11_logging.md`
**Wave status:** `todo`
**Document status:** documentation-only contract candidate; not ratified until independent review, explicit human authorization, and normal merge
**Starting main:** `ea7f78b455f14f8ea674c196db349fd08b355305`
**Starting tree:** `4236542a972071095b8183963434d404d580f80d`
**Starting subject:** `docs: define Wave B miner research buildout`

## 1. Purpose, verified base, and authority

This plan proposes the exact bounded Wave-A A11 contract. It does not
implement or test A11, change an existing owner service, instrument a submit or
score path, create a production sink, or authorize A12. The contract becomes
ratified only after this documentation candidate is independently reviewed,
explicitly human-authorized, and normally merged.

The starting main was independently fetched and verified before editing:

~~~text
commit:  ea7f78b455f14f8ea674c196db349fd08b355305
tree:    4236542a972071095b8183963434d404d580f80d
subject: docs: define Wave B miner research buildout
parent:  404c039596b487cf2649bb1d73b80e9b49baaced
signature: verified=false, reason=unsigned
~~~

The unsigned direct-main topology is current repository truth; this task does
not rewrite, sign, revert, or administratively repair it. Push run
`32987792589` completed successfully on that exact main. CPU job `98238037155`
recorded `1973 passed in 52.48s`. Code quality job `98238037364` recorded
`Ruff 757/776`, `Black 62/68`, removed debt `Ruff 19, Black 6`, zero changed
Python files, and no new debt.

PR #38's normal A10 closeout merge `404c039596b487cf2649bb1d73b80e9b49baaced`
is the sole parent of current main. The original PR #39 candidate head
`75148a18e00a7a9d3c8244fd72c032878dfb98ce`, tree
`7299c37618e864a79884c0c5a249f39915662443`, was based on that A10 closeout.
It was synchronized normally with current main by merge
`24672a11c9f7e60e37fec16e986b850934aa31ef`, tree
`7ad508a8214355104ec8410cc401048580cf34b6`, with ordered parents the old PR
head then current main. The synchronization differed from current main only by
the preserved A11 plan and `agent_pack/README.md`.

The current board has A9 `done`, A10 `done`, A11 `todo`, and A12 `todo`.
Wave A is not closed. Current main also contains a documentation-only Wave B
planning package. Wave A remains controlling; Wave B is candidate-only and
inactive, and no B ticket is authorized here. The starting worktree was clean.

Authority was applied in this order:

1. current repository and code;
2. current authoritative specifications;
3. `.agent/DECISIONS.md`;
4. owner-canonical maturity ledgers;
5. `.agent/WAVE.md`;
6. current context and orientation material;
7. historical handoffs;
8. legacy/archive archaeology.

SPECIFIED, IMPLEMENTED, TESTED, SCIENTIFICALLY_QUALIFIED,
SECURITY_QUALIFIED, NETWORK_QUALIFIED, COMMERCIALLY_VALIDATED, and
PRODUCTION_QUALIFIED remain independent states. Documentation review and the
existing repository regression suite are not A11 implementation/test evidence.

The corrective candidate changes only the six authorized documentation paths.
It leaves `.agent/WAVE.md` at exact current-main blob
`eb0b81acba0225d46d01cfc14f9a2e0b4f9f06da`, preserves every Wave B artifact
and current-main scientific/launch edit, and changes no Python, test, fixture,
dependency, packaging, workflow, CI, quality baseline, A0–A10 behavior, or A12
artifact.

## 2. Reconciliation and KEEP → WRAP → REPAIR → REPLACE

### NO_CONFLICT

The bounded contract below agrees with current authority that:

- observability is operational and cannot become scientific or economic
  authority;
- disclosure is positive and allow-listed;
- official seeds, hidden exam material, score internals, identities, and
  backend diagnostics cannot enter miner/public logs or metrics;
- A5 owns scientific scoring; A7 owns submission identity and lifecycle;
- A7 lifecycle `SCORED` is not A5 scientific `ScoreStatus.SCORED`;
- mandatory-gate failure, strategy failure, infrastructure failure, rejection,
  and non-scientific unavailability must remain distinct;
- infrastructure failure is not scientific failure;
- future receipts, re-execution, frontier, Product Qualification, settlement,
  chain, weight, and emission layers remain separately owned.

### DOCUMENTATION_LAG

The current-main six-bullet A11 ticket is high-level shorthand. A generic logger helper,
pattern-first redaction, implied direct submit/score instrumentation, generic
failure tags, and a non-exact focused path do not define the complete safe
Wave-A boundary. This candidate narrows that shorthand to closed nominal
events/metrics, positive construction, owner-shaped status consistency, closed
A9/A10 safe-error categories, an exact resource/error/sink contract, and the
canonical future focused path `tests/cpu/test_observability.py`.

The old candidate's assertion that each event projects an existing A7 record
is `P1_UNENFORCEABLE_EVENT_PROVENANCE_CLAIM`, taxonomy
`DOCUMENTATION_LAG`, not an A11 implementation defect. Public
`SubmissionId` validates canonical UUIDv4 syntax but proves no record, current
state, transition, or authenticated provenance. This correction adds no
private lookup, capability, signature, receipt, or field.

Current-main overlay introductory prose and the preserved old-branch README
also lag repository truth. PR #38 merged normally and is ancestral to current
main; A10 is `done` only for its exact bounded in-process fixture leaderboard
and remains scientifically, security, network, commercially, and production
unqualified. A11 and A12 remain `todo`; Wave A remains incomplete; Wave B
remains inactive candidate planning. Explicit historical chronology remains
unchanged.

### IMPLEMENTATION_LAG

No `carbon/observability` package, focused test, typed event/metric sink,
service, or source-level dependency guard exists. The one-line
`carbon/logging_utils` marker is a reserved boundary, not A11 implementation.
A11 remains IMPLEMENTED: NO and TESTED: NO.

### MIGRATION_REQUIRED

A0 reserved the importable `carbon/logging_utils` package, whose inert marker
names a deferred logging/redaction boundary. The explicit A11-R1 owner
direction resolves that prospective ownership seam as KEEP + REPLACE: KEEP
`carbon/logging_utils` unchanged as an inert A0 compatibility marker, while
REPLACE its prospective semantic ownership with `carbon/observability` as the
sole future A11 implementation and API owner. The marker gains no wrapper,
alias, re-export, sink behavior, or alternate A11 surface. This
documentation-only candidate performs no code migration.

Legacy Bittensor/validator logging, exception interpolation, hotkey/path
logging, scientific metric dictionaries, PoC telemetry, Landscape/Physics
Intelligence telemetry, and receipt/audit designs are not A11 authority. They
use incompatible free-form text, dynamic mappings, score material, customer or
network identity, evidence storage, filesystem/network behavior, or later-wave
semantics. They remain archaeology or future-owner work and are not wrapped,
repaired, or imported by the first A11 implementation.

`carbon/audit` remains reserved for evaluation receipts and authorized
re-execution. The normative evidence specification's transcript, receipt,
append-only ledger, and audit telemetry are not moved into A11.

### NEW_OWNER_DECISION_REQUIRED

No new owner decision is required for the exact in-process primitive below.
Production exporters, sink latency/timeout policy, persistence, retention,
dashboards, alert thresholds, incident management, timestamps, additional
event/stage/metric vocabulary, direct owner-service hook locations, Challenge
health, adaptive-query detection, evidence/receipt integration, official/LIVE
operations, frontier/Product Qualification, settlement, chain, weights, and
emissions all require later separately authorized owner decisions. They fail
closed here.

## 3. Decisions proposed for ratification

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

## 4. Canonical future threat and test contract

The sole future focused path is:

~~~text
tests/cpu/test_observability.py
~~~

This documentation task does not create or modify it. The future suite must
cover at least the following.

### Surface and exact nominal values

- exact ordered fourteen-name root export tuple with no aliases or extras;
- exact direct `str, Enum` inheritance, declaration order, member names,
  literal values, and absence of aliases for all four enums;
- exact four-field submission event, one-field boundary-error event, and
  one-field resource-limit order;
- frozen/slotted/representation-safe values and no generic serialization;
- exact three-argument constructor and exact three service operations only;
- exact type, forged-member, subclass, bool/int, coercion, and u64 rejection;
- unknown field/shape rejection without mapping, iterable, descriptor, or
  object-graph traversal.

### Event and owner projection

- every exact A11-R4 valid combination and every mismatched combination;
- fresh A7 `SubmissionId` reconstruction and mutation isolation;
- exact `SubmissionState.RECEIVED`, `SCORED`, `REJECTED`,
  `FAILED_STRATEGY`, and terminal `FAILED_INFRA` projection;
- A5 `SCORED` versus `MANDATORY_GATE_FAILED` separation on `SCORE`;
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

- exact one-field `BoundaryErrorEvent` and exact eleven-member closed enum;
- exact-class-only test-local mapping for all seven public A9 and four public
  A10 concrete errors, including distinct budget/unavailable meanings;
- no mapping for the code-less A10 `LeaderboardError` base, subclasses,
  generic exceptions, lookalike objects, or unknown codes;
- no production A9/A10 import and no exception object/text/message/cause/
  context/traceback, owner payload, identity, provider, seed, or draw crossing
  the A11 boundary;
- proof that A9/A10 owner translation precedes A11 and a closed enum does not
  authenticate that an owner error actually occurred.

### Metric and duration bounds

- exact four incrementable counter members and rejection of
  `STAGE_DURATION_NS` as a counter;
- exact `SUBMIT`/`SCORE` duration stages;
- exact built-in integer nanoseconds in `0..2**64-1`, including zero and both
  bounds;
- empty arbitrary-label surface and structurally bounded cardinality;
- no dynamic name, gauge, arbitrary histogram, decrement, reset, value, or
  unratified failed-strategy counter;
- no timestamp/current-time import, access, or nondeterministic clock read.

### Positive construction and leakage

- declared-order positive extraction and immutable owned copies before sink
  access;
- no generic serializer, recursive sanitizer, reflection, `asdict`, pickle,
  JSON, or serialize-then-redact path;
- hostile `repr`/`str`, mapping, iterable, descriptor, cycle, alias, mutation,
  CR/LF, Unicode, and oversized-value traps;
- complete exclusion of seed/secret/Strategy/parameter/requester/hotkey/wallet/
  customer/result/cursor/score/rank/query/exception object or text/stack/path/
  command/environment material;
- no adaptive-exam oracle, Challenge-health transition, scientific evidence,
  frontier/Product Qualification, settlement, chain, weight, or emission
  behavior.

### Sink, errors, concurrency, and domain isolation

- structural Protocol implementations without subclassing or runtime Protocol
  introspection;
- exact sink method arguments, successful exact `None`, and one sink call at
  most per public operation;
- copied-event mutation isolation and no caller/sink alias reuse;
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

- per-file source guards enforcing the exact R16 matrix, including no direct
  A5 engine/result or A7 service/private-store/fee import or call while not
  making a false transitive-module-absence claim;
- source guards against direct A6, A8, A9, A10, `logging_utils`,
  audit/evidence, optional exporters, filesystem,
  network, environment, time, Landscape, neuron, Bittensor, chain, settlement,
  weight, and emission imports;
- no OpenTelemetry, Prometheus, StatsD, logging backend, HTTP, database,
  dashboard, alert, or production provider;
- fresh no-dependency wheel install and outside-tree isolated import;
- full default CPU regression;
- strict Ruff and Black on later changed Python paths;
- repository no-new-debt evidence.

Documentation statements, existing A0–A10 tests, and repository regression
success do not count as A11 implementation or A11 test evidence.

## 5. Future implementation sequence

After and only after normal ratification merge plus a separate explicit
implementation authorization, the smallest sequence is:

1. re-fetch and verify the exact ratification merge, authority, clean tree,
   A11/A12 `todo` status, and absence of competing work;
2. create the four-file `carbon/observability` package without touching
   `carbon/logging_utils`, `carbon/audit`, or existing owner packages;
3. implement the exact nominal values, four enums, two event types, errors,
   and Protocol seams;
4. implement positive event/metric/duration validation and immutable copying;
5. implement non-blocking capacity/reentrancy accounting and exact sink
   exception boundaries;
6. add only `tests/cpu/test_observability.py` for the focused contract;
7. run focused, full CPU, quality, source-guard, wheel, and outside-tree import
   evidence;
8. seek independent exact-head review before any status change or merge.

Direct A5–A10 instrumentation, production providers, and A12 work are not part
of that first implementation sequence.

## 6. Documentation-candidate validation and maturity boundary

Before publication, this candidate must prove:

- the diff contains exactly the six authorized documentation paths and no
  seventh path;
- `.agent/WAVE.md` is byte-identical to current main at blob
  `eb0b81acba0225d46d01cfc14f9a2e0b4f9f06da`;
- A10 remains `done`; A11 and A12 remain `todo`; Wave A remains incomplete;
- all A11 implementation DoD boxes remain unchecked;
- this plan contains no implementation-completion checkbox markers;
- no Python, test, fixture, dependency, packaging, workflow, CI, or quality
  baseline changes;
- the current-state post-A10 documentation lags are repaired without
  rewriting explicit historical sections;
- all current-main Wave B artifacts and activation gates are byte-preserved,
  Wave A remains controlling, and Wave B remains inactive;
- no A0–A10 contract is weakened and no production/exporter/persistence/auth/
  alert/threshold/Challenge-health/adaptive-query/evidence/frontier/product/
  settlement/chain/weight/emission authority is added;
- `git diff --check` passes;
- the required synchronization merge and one corrective documentation commit
  have exact topology/manifests and the worktree is clean;
- publication is a draft PR only, with no ready/merge/auto-merge action.

The exact candidate maturity ceiling is:

~~~text
A11 SPECIFIED / RATIFIED:
YES only after this exact corrected documentation contract is independently reviewed,
explicitly human-authorized, and normally merged

A11 IMPLEMENTED: NO
A11 TESTED: NO
A11 SCIENTIFICALLY_QUALIFIED: NO
A11 SECURITY_QUALIFIED: NO
A11 NETWORK_QUALIFIED: NO
A11 COMMERCIALLY_VALIDATED: NO
A11 PRODUCTION_QUALIFIED: NO
A11 WAVE STATUS: todo
A12: todo
Wave A: incomplete
Wave B: candidate planning only; inactive
~~~

A draft PR is only a candidate. It is not review, authorization, readiness,
ratification, implementation, test evidence, or merge authority.
