# A11 — bounded in-process operational observability contract candidate

**Ticket:** `.agent/tickets/A11_logging.md`
**Wave status:** `todo`
**Document status:** documentation-only contract candidate; not ratified until independent review, explicit human authorization, and normal merge
**Starting main:** `404c039596b487cf2649bb1d73b80e9b49baaced`
**Starting tree:** `7fbd85347fb608c9c8ae559e1b720d9794d62dd6`
**Starting subject:** `Merge pull request #38 from carbonphysicsai/agent/a10-closeout`

## 1. Purpose, verified base, and authority

This plan proposes the exact bounded Wave-A A11 contract. It does not
implement or test A11, change an existing owner service, instrument a submit or
score path, create a production sink, or authorize A12. The contract becomes
ratified only after this documentation candidate is independently reviewed,
explicitly human-authorized, and normally merged.

The starting main was independently fetched and verified before editing:

~~~text
commit:  404c039596b487cf2649bb1d73b80e9b49baaced
tree:    7fbd85347fb608c9c8ae559e1b720d9794d62dd6
subject: Merge pull request #38 from carbonphysicsai/agent/a10-closeout
parent1: 3b2d96e287f06c24cc4d57b46dfc418359a9e97f
parent2: f50ce3ec975f311fbf7965c646c0f31d6e0a487e
signature: verified=true, reason=valid
~~~

PR #38 is closed and normally merged at that exact merge commit. Post-merge
`push` run `32958132030` completed successfully on the exact merge SHA. CPU job
`98144278320` recorded `1973 passed in 43.33s`. Code quality job `98144278039`
completed successfully and recorded `Ruff 757/776`, `Black 62/68`, removed
debt `Ruff 19, Black 6`, zero changed Python files, and no new debt.

The fetched board has A9 `done`, A10 `done`, A11 `todo`, and A12 `todo`.
Wave A is not closed. The starting worktree was clean. All fetched branches,
tags, repository paths/history, and GitHub pull requests were searched again;
there is no competing A11 branch, pull request, plan, implementation, repair,
or closeout candidate.

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

This candidate changes only the six authorized documentation paths. It leaves
`.agent/WAVE.md`, every Python file, every test/fixture, dependencies,
packaging, workflows, CI, quality baselines, A0–A10 behavior, and A12
untouched.

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

The current five-bullet A11 ticket is stale shorthand. A generic logger helper,
pattern-first redaction, implied direct submit/score instrumentation, generic
failure tags, and `tests/test_logging_redaction.py` do not define a safe exact
Wave-A boundary. This candidate narrows that shorthand to closed nominal
events/metrics, positive construction, exact owner-status projection, an exact
resource/error/sink contract, and the canonical future focused path
`tests/cpu/test_observability.py`.

Two post-A10 current-state passages also lag repository truth. PR #38 has
merged normally; A10 is `done` only for its exact bounded in-process fixture
leaderboard and remains scientifically, security, network, commercially, and
production unqualified. A11 and A12 remain `todo`; Wave A remains incomplete.
Only `agent_pack/README.md` and
`docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md` are repaired for that
current-state lag. Explicit historical sections remain unchanged.

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

### A11-R1 — Package ownership

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
    "ObservabilityEvent",
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

The three enums have these exact declaration/value orders:

~~~text
EventKind:
    SUBMIT
    SCORE
    REJECT
    FAILED_STRATEGY
    FAILED_INFRA

MetricKind:
    SUBMIT_COUNT
    SCORE_COUNT
    REJECT_COUNT
    FAILED_INFRA_COUNT
    STAGE_DURATION_NS

DurationStage:
    SUBMIT
    SCORE
~~~

`ObservabilityEvent` is a frozen, slotted, representation-safe nominal value
with exactly these fields in this order:

~~~text
kind: exact EventKind
submission_id: exact A7 SubmissionId
submission_state: exact A7 SubmissionState
score_status: exact A5 ScoreStatus | None
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
forged enum members, and generic lookalikes. Event/resource values support no
generic serialization or generic copy/deepcopy path. They never invoke a
caller-controlled `repr` or `str`.

### A11-R3 — Exact bounded capabilities

The only service operations are:

~~~python
ObservabilityService.emit_event(event: ObservabilityEvent) -> None
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

### A11-R4 — Closed event vocabulary and exact owner projection

The exact valid event matrix is:

| EventKind | exact SubmissionState | exact ScoreStatus |
|---|---|---|
| `SUBMIT` | `RECEIVED` | `None` |
| `SCORE` | `SCORED` | `SCORED` or `MANDATORY_GATE_FAILED` |
| `REJECT` | `REJECTED` | `None` |
| `FAILED_STRATEGY` | `FAILED_STRATEGY` | `None` |
| `FAILED_INFRA` | `FAILED_INFRA` | `None` |

Every event therefore correlates an already-created exact A7 record. A request
that fails before a safe A7 `SubmissionId` exists cannot construct an A11
event. The first implementation does not invent a second pre-record identity
or accept `submission_id=None`.

Every kind/state/status combination outside the table is an invalid request.
In particular, `PUBLISHED`, `CANCELLED`, `VALIDATED`, `QUEUED`, `RUNNING`,
retryable infrastructure, `PACK_NOT_READY`, and forged or cross-enum statuses
are not silently remapped to a current event.

This event family is internal operational telemetry. It is not a public card,
MCP result, leaderboard value, receipt, evidence record, lifecycle store, or
scientific result.

### A11-R5 — Closed metric vocabulary and operations

The counter operation accepts only these exact `MetricKind` members:

~~~text
SUBMIT_COUNT
SCORE_COUNT
REJECT_COUNT
FAILED_INFRA_COUNT
~~~

Each accepted call means exactly one counter increment and supplies no value,
delta, labels, or dimensions. `STAGE_DURATION_NS` is rejected by
`increment_counter`; it is the fixed metric represented only by
`observe_duration(stage, duration_ns)`.

No `FAILED_STRATEGY_COUNT`, gauge, arbitrary histogram, set, decrement, reset,
dynamic name, arbitrary numeric value, or generic metric operation exists.
The typed primitive does not choose the later integration hook at which a
domain action calls a counter; direct A5–A10 instrumentation is deferred.

### A11-R6 — Zero arbitrary metric labels and bounded cardinality

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

### A11-R7 — Exact A7 correlation identity only

A11 reuses exact public A7 `SubmissionId`. It creates no correlation ID,
trace ID, span ID, request ID, receipt ID, result ID, or alias.

Before sink access, A11 reconstructs a fresh exact `SubmissionId` through its
owner constructor from the exact allow-listed value. The copied value may
appear only as the structured `ObservabilityEvent.submission_id` correlation
field. It may not appear in a metric, metric label, error, free-form text,
`repr`, generic serialization, public/miner/customer value, or requester
identity.

`RequesterIdentity` never crosses the A11 boundary and is not imported.
Nothing in this contract revokes the separately ratified A7/A9 use of
`SubmissionId` in their own owner-controlled interfaces; “not public” here
means not emitted as public observability material.

### A11-R8 — Failure and lifecycle separation

A11 does not invent lifecycle or scientific semantics. It reuses exact public
A7 `SubmissionState` and A5 `ScoreStatus` only through the A11-R4 matrix.

- `REJECT` is the operational projection of exact A7 `REJECTED` request or
  admission semantics; it is not strategy, scientific, or infrastructure
  failure.
- `FAILED_STRATEGY` is the operational projection of exact terminal A7
  `FAILED_STRATEGY`; it does not accept ambiguous or infrastructure causes.
- `FAILED_INFRA` is the operational projection of exact terminal A7
  `FAILED_INFRA`; it does not absorb retryable infrastructure or scientific
  failure.
- `SCORE` with exact A7 `SCORED` and A5 `SCORED` records only that the owner
  produced the closed scored category, never its numeric score.
- `SCORE` with exact A7 `SCORED` and A5 `MANDATORY_GATE_FAILED` preserves the
  mandatory scientific-gate disposition and does not relabel it as strategy,
  infrastructure, or request failure.
- A5 `PACK_NOT_READY` remains non-scientific unavailability. It cannot satisfy
  A7 `SCORED`, cannot construct a `SCORE` event, and cannot be relabeled by A11
  as `FAILED_STRATEGY`, `FAILED_INFRA`, or `REJECT`. A later owner action may
  independently terminalize A7 as `FAILED_INFRA`; only that exact terminal A7
  state may then project the terminal A11 event.

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
    def emit_event(self, event: ObservabilityEvent, /) -> None: ...

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

### A11-R16 — Dependency direction and initial non-integration

The only non-standard-library imports ratified for the first implementation
are:

~~~python
from carbon.fees import SubmissionId, SubmissionState
from carbon.scoring import ScoreStatus
~~~

These are exact public owner types. Reusing both status families preserves the
existing distinction between A7 lifecycle and A5 scientific disposition
without duplicating either vocabulary.

The first implementation does not import A5 score values/results/engine,
A6 cards/store, A7 service/private store/records/fees, A8 private outcomes or
causes, A9 control/disclosure objects, A10 candidates/pages/provider, or any
legacy validator/neuron/Landscape object. It imports no `RequesterIdentity`.

A5–A10 packages do not import `carbon.observability` in the first
implementation. No existing owner service changes merely to satisfy A11.
Direct instrumentation of A5, A7, A8, A9, or A10 is a later
composition/integration task requiring an exact non-circular hook and
domain-result-preservation review.

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
and `todo`.

## 4. Canonical future threat and test contract

The sole future focused path is:

~~~text
tests/cpu/test_observability.py
~~~

This documentation task does not create or modify it. The future suite must
cover at least the following.

### Surface and exact nominal values

- exact ordered twelve-name root export tuple with no aliases or extras;
- exact enum member/value order for events, metrics, and stages;
- exact four-field event order and one-field resource-limit order;
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
- rejection/omission of `PACK_NOT_READY`, retryable infrastructure,
  `PUBLISHED`, `CANCELLED`, and unsupported future categories;
- no second identity/lifecycle/status vocabulary and no A8 private-type
  dependency;
- no `RequesterIdentity`, result ID, cursor, public correlation, or A6 failure
  tag widening.

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
  customer/result/cursor/score/rank/query/exception/stack/path/command/
  environment material;
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

- source guards permitting only standard library plus exact public
  `SubmissionId`, `SubmissionState`, and `ScoreStatus` imports;
- source guards against A5 engine/results, A6, A7 service/private state, A8,
  A9, A10, `logging_utils`, audit/evidence, optional exporters, filesystem,
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
3. implement the exact nominal values, errors, and Protocol seams;
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
- `.agent/WAVE.md` is byte-identical to base;
- A10 remains `done`; A11 and A12 remain `todo`; Wave A remains incomplete;
- all A11 implementation DoD boxes remain unchecked;
- this plan contains no implementation-completion checkbox markers;
- no Python, test, fixture, dependency, packaging, workflow, CI, or quality
  baseline changes;
- the two current-state post-A10 documentation lags are repaired without
  rewriting explicit historical sections;
- no A0–A10 contract is weakened and no production/exporter/persistence/auth/
  alert/threshold/Challenge-health/adaptive-query/evidence/frontier/product/
  settlement/chain/weight/emission authority is added;
- `git diff --check` passes;
- the branch is committed as one documentation-only commit and is clean;
- publication is a draft PR only, with no ready/merge/auto-merge action.

The exact candidate maturity ceiling is:

~~~text
A11 SPECIFIED / RATIFIED:
YES only after this documentation contract is independently reviewed,
explicitly human-authorized, and normally merged

A11 IMPLEMENTED: NO
A11 TESTED: NO
A11 SCIENTIFICALLY_QUALIFIED: NO
A11 SECURITY_QUALIFIED: NO
A11 NETWORK_QUALIFIED: NO
A11 COMMERCIALLY_VALIDATED: NO
A11 PRODUCTION_QUALIFIED: NO
A11 WAVE STATUS: todo
~~~

A draft PR is only a candidate. It is not review, authorization, readiness,
ratification, implementation, test evidence, or merge authority.
