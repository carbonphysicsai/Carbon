# Ticket A11 — Bounded operational observability: events + metrics (C16)

**Wave:** A
**Status:** todo
**Contract status:** A11-R1 through A11-R17 are ratified; A11-R18 is specified
as this exact documentation-only candidate and is ratified only after
independent review, explicit human authorization, and normal merge
**Build_Out:** v1.4 C16, interpreted through Design_Specs/Build_Out_Constitutional_Overlay.md
**Depends on:** current A5, A6, A7, A8, A9, and A10 semantic owner boundaries; initial production imports remain limited to exact public A5/A7 values
**Plan:** .agent/plans/A11_logging.md

## Goal

Implement one bounded in-process operational observability primitive only after
separate explicit implementation authorization. The future primitive uses
closed validated submission-event, boundary-error, counter, and duration
requests; an exact owner-shaped A5/A7 consistency matrix; exact A7 SubmissionId
validation; fixed safe A9/A10 public-error mappings supplied by trusted
composition; empty metric labels; positive request-to-snapshot construction;
finite non-blocking capacity; and injected standard-library Protocol sinks that
receive only fresh primitive A11-owned snapshots.

ObservabilityEvent is an owner-shaped, process-local operational observation
request. Exact nominal values and the closed kind/state/status matrix establish
shape and consistency only. A11 does not verify A7 record existence, current
retained state, or an owner transition, and it does not authenticate A5/A7
provenance. Trusted composition alone supplies the factual relationship to an
owner transition. Exact nominal values are correctness values, not
authenticated capabilities.

`ObservabilityEvent`, `BoundaryErrorEvent`, `MetricKind`, and `DurationStage`
are request values only. They are never sink arguments and are not sink-safe
snapshots. A valid request maps through A11-owned fixed literal tables to one
fresh `SubmissionEventSnapshot`, `BoundaryErrorSnapshot`,
`CounterMetricSnapshot`, or `DurationMetricSnapshot` before capacity or sink
access. No enum member, owner nominal object, request object, or arbitrary enum
attribute crosses that boundary.

A11 is not a generic logger, evidence store, lifecycle owner, scoring or
Challenge-health authority, production exporter, public API, alerting system,
or frontier/product/settlement/chain/weight/emission surface.

PR #39 normally merged A11-R1 through A11-R17 into current main
`4e4a66d29566a2a62a82188adddac76e6e0fb8b8`. Current main contains no A11
implementation or focused test. Draft PR #46 is blocked by
`P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS`; its branch is non-authoritative and
unchanged by this documentation amendment, while its body metadata records the
blocker and withdraws the stale audit claim. Its generic-dataclass correction
remains intact at that draft head but does not resolve shared enum singletons.

A11-R18 supersedes only the sink-facing portions of A11-R1, A11-R2, A11-R3,
A11-R10, A11-R13, A11-R14, and A11-R16. All other A11-R1 through A11-R17
behavior and authority ceilings remain in force. The effective amended contract
becomes A11-R1 through A11-R18 only after independent review, explicit human
authorization, and normal merge of this exact amendment candidate.

## Required contract

- Sole future semantic and implementation ownership is
  carbon/observability/{__init__,model,providers,service}.py, with canonical
  focused tests only at tests/cpu/test_observability.py.
  carbon/logging_utils remains only the unchanged inert A0 compatibility
  marker; carbon/audit, root carbon exports, and every A5–A10 owner
  implementation also remain unchanged.
- model.py owns EventKind, MetricKind, DurationStage, BoundaryErrorKind,
  ObservabilityEvent, BoundaryErrorEvent, ObservabilityResourceLimits,
  SubmissionEventSnapshot, BoundaryErrorSnapshot, CounterMetricSnapshot,
  DurationMetricSnapshot,
  ObservabilityError, ObservabilityRequestError, ObservabilityResourceError,
  ObservabilityIntegrationError, and private exact request-validation and
  snapshot-construction helpers only.
- providers.py owns StructuredEventSink and MetricSink, with no concrete,
  default, or global sink. service.py owns ObservabilityService plus private
  request-to-snapshot conversion,
  shared-capacity accounting, same-service reentrancy accounting, sink
  lookup/invocation/return validation, and Exception/BaseException translation
  only. __init__.py contains the exact eighteen-name re-export tuple only.
- The exact ordered carbon.observability.__all__ tuple is:

  ~~~text
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
  superseded only after A11-R18 is independently reviewed, explicitly
  human-authorized, and normally merged. No owner type, generic logger,
  serializer, provider, mapper, private helper, or extra error is exported.

- All four enums are exact direct str, Enum types, with no aliases, auto(),
  integer values, alternative lowercase values, or extra members:

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

- ObservabilityEvent remains the exact four-field owner-shaped request:
  kind, submission_id, submission_state, score_status. BoundaryErrorEvent is
  the exact one-field request: error_kind. Neither is evidence or authenticated
  provenance. These request values and all enum members are never sink
  arguments.
- The four exact future sink values are:

  ~~~text
  SubmissionEventSnapshot(
      kind: str,
      submission_id: str,
      submission_state: str,
      score_status: str | None,
  )

  BoundaryErrorSnapshot(error_code: str)
  CounterMetricSnapshot(metric_name: str)
  DurationMetricSnapshot(stage: str, duration_ns: int)
  ~~~

  Submission-event snapshot fields are exactly ordered and follow the existing
  matrix. `kind` is exact built-in `str` from SUBMIT, SCORE, REJECT,
  FAILED_STRATEGY, FAILED_INFRA; `submission_id` is an exact 36-ASCII canonical
  UUIDv4 built-in string validated through fresh public A7 reconstruction;
  `submission_state` is exact built-in `str` from RECEIVED, SCORED, REJECTED,
  FAILED_STRATEGY, FAILED_INFRA; and `score_status` is None or exact built-in
  `str` SCORED or MANDATORY_GATE_FAILED. `error_code` is exact built-in `str`
  from the existing eleven BoundaryErrorKind literals. `metric_name` is exact
  built-in `str` from SUBMIT_COUNT, SCORE_COUNT, REJECT_COUNT, or
  FAILED_INFRA_COUNT. Duration `stage` is exact built-in `str` SUBMIT or SCORE,
  and `duration_ns` is exact built-in `int` in 0..2**64-1.
- Each snapshot is an exact manual slotted non-dataclass nominal class, fresh
  per admitted call, with no instance __dict__; immutable through normal
  assignment/deletion; representation-safe; non-copyable by copy/deepcopy;
  non-pickleable; rejected by dataclasses.asdict/astuple/replace; and composed
  only of exact built-in str, int, or None. It contains no request, enum, owner,
  exception, mapping, iterable, descriptor, object graph, or metadata. A
  snapshot is never a service request and direct construction proves shape
  only, not owner transition or any lifecycle/scientific/audit/public/security/
  settlement/economic authority.
- The service exposes exactly emit_event(event), accepting exact
  ObservabilityEvent or BoundaryErrorEvent; increment_counter(metric); and
  observe_duration(stage, duration_ns). It accepts no mappings, free-form
  messages, metadata bags, dynamic names, arbitrary values, label maps,
  serializers, batches, backend selectors, or snapshot request values.
- StructuredEventSink receives only exact SubmissionEventSnapshot or
  BoundaryErrorSnapshot. MetricSink.increment_counter receives only exact
  CounterMetricSnapshot, and MetricSink.observe_duration receives only exact
  DurationMetricSnapshot. The Protocols remain structural and
  non-runtime-checkable; concrete sinks subclass neither Protocol.
- Production A11 imports only Python standard library and exact public A5/A7
  request values. Snapshot classes use only built-ins and local A11 validation.
  A11 never imports A9/A10. A test-local trusted-composition harness may
  map exact public A9/A10 error classes to closed BoundaryErrorKind members
  after those owners have already translated any raw provider exception.
- Construction is positive and allow-listed. No generic serialize-then-redact
  path, recursive sanitizer, enum-__dict__ traversal/copy,
  snapshot-and-restore mutation, hostile repr/str, current-time access,
  fallback logger, queue, retry, background task, or production provider
  exists. After exact request/canonical-enum/matrix validation and fresh A7 ID
  reconstruction, A11 maps semantics through fixed local literal tables and
  constructs a fresh snapshot before capacity and sink access.
- Mutation through an object supplied by A11 to a sink cannot alter caller,
  owner, retained, concurrent, or later A11 state. A sink escape hatch may
  alter only its own distinct per-call snapshot. A11 retains no snapshot for
  reuse, holds no global lock across sink code, performs no shared-state
  sanitize/restore, and claims no sandbox for unrelated globals independently
  imported by arbitrary in-process sink code.
- A syntactically valid but unbound UUIDv4 has no lifecycle, scientific, audit,
  receipt, public, security, settlement, or economic authority. Production
  provenance and evidence remain separately deferred.
- A11 remains todo throughout this documentation candidate. A11-R1 through
  A11-R17 remain ratified; A11-R18 remains a candidate until independently
  reviewed, explicitly human-authorized, and normally merged. Documentation,
  PR #46 tests, and repository regression evidence are not current-main A11
  implementation or test evidence.

## Implementation DoD

Every implementation criterion below remains unchecked. This documentation
candidate implements and tests nothing.

### Exact package and public surface

- [ ] Add only carbon/observability/__init__.py, model.py, providers.py, and
  service.py with the effective A11-R18 module ownership: model request/resource
  values, four snapshot types, errors, and private exact request-validation and
  snapshot-construction helpers only; provider Protocols only; service
  request-to-snapshot conversion, private accounting, sink invocation, and
  translation only; and __init__.py exact re-exports only. Do not modify,
  alias, import through, or re-export from the inert A0 carbon/logging_utils
  compatibility marker, carbon/audit, or root carbon/__init__.py.
- [ ] Export the exact ordered eighteen-name carbon.observability.__all__ tuple
  amended by A11-R18, with all four snapshots in their exact specified order
  and no owner-type re-export, alias, generic logger,
  serializer, production provider, no-op default, private helper, or extra
  error.
- [ ] Implement exact direct str, Enum inheritance, declaration order, names,
  and literal values for EventKind (SUBMIT, SCORE, REJECT, FAILED_STRATEGY,
  FAILED_INFRA), MetricKind (SUBMIT_COUNT, SCORE_COUNT, REJECT_COUNT,
  FAILED_INFRA_COUNT, STAGE_DURATION_NS), and DurationStage (SUBMIT, SCORE),
  with no aliases, auto(), integer values, alternative lowercase values, or
  extra members.
- [ ] Implement ObservabilityEvent as a frozen, slotted,
  representation-safe owner-shaped operational-observation request with exact
  ordered fields kind, submission_id, submission_state, score_status and no
  generic serialization/copy path; it is a validated request only, never a sink
  argument or sink-safe snapshot, and proves neither retained-record existence
  nor authenticated provenance.
- [ ] Implement ObservabilityResourceLimits as a frozen, slotted,
  representation-safe value with only required max_concurrent_calls, an exact
  built-in integer in 1..2**64-1.
- [ ] Implement exactly ObservabilityService(event_sink, metric_sink,
  resource_limits) with all arguments mandatory and no default, None,
  environment, registry, singleton, global sink, backend selector, or
  production numeric policy.
- [ ] Expose only emit_event(event: ObservabilityEvent |
  BoundaryErrorEvent), increment_counter(metric), and
  observe_duration(stage, duration_ns), each returning exact None on success;
  accept no snapshot as a request;
  expose no fourth operation, log, mapping emit, generic metric, record, batch,
  flush, retry, queue, serializer, exporter, or sink-selection operation.
- [ ] Reject subclasses, forged enum members, corrupted canonical enum name or
  literal value, bool-as-int, coercible primitives, generic lookalikes, unknown
  shapes, and unsupported combinations through exact type, identity, name, and
  literal validation without calling hostile repr or str; never inspect, copy,
  traverse, retain, render, or emit unrelated caller-added enum attributes.

### Exact submission event consistency and correlation

- [ ] Accept a SUBMIT-shaped request only with a fresh copied exact A7
  SubmissionId, exact SubmissionState.RECEIVED, and score_status=None.
- [ ] Accept a SCORE-shaped request only with a fresh copied exact A7
  SubmissionId, exact SubmissionState.SCORED, and exact canonical A5
  ScoreStatus.SCORED or ScoreStatus.MANDATORY_GATE_FAILED.
- [ ] Accept a REJECT-shaped request only with a fresh copied exact A7
  SubmissionId, exact SubmissionState.REJECTED, and score_status=None.
- [ ] Accept a FAILED_STRATEGY-shaped request only with a fresh copied exact A7
  SubmissionId, exact terminal SubmissionState.FAILED_STRATEGY, and
  score_status=None.
- [ ] Accept a FAILED_INFRA-shaped request only with a fresh copied exact A7
  SubmissionId, exact terminal SubmissionState.FAILED_INFRA, and
  score_status=None.
- [ ] Reject every mismatched kind/state/status combination and direct
  PACK_NOT_READY, retryable-infrastructure, PUBLISHED, CANCELLED,
  pre-record/no-ID, or unsupported future-category request without remapping it
  to a current event.
- [ ] Preserve A7 lifecycle SCORED versus A5 SCORED and
  MANDATORY_GATE_FAILED; preserve request/admission rejection, terminal
  strategy failure, terminal infrastructure failure, and non-scientific
  PACK_NOT_READY as distinct meanings while making no retained-state or
  transition-occurrence claim.
- [ ] Prove an open duplicate, pre-record request/resource failure, retryable
  infrastructure result, omitted future reference/generator/reconstruction
  failure, or syntactically valid but unbound UUIDv4 cannot be falsely promoted
  into lifecycle, scientific, audit, receipt, public, security, settlement, or
  economic authority.
- [ ] Reconstruct SubmissionId only through its public A7 constructor and
  permit only its exact canonical 36-ASCII built-in string as
  SubmissionEventSnapshot.submission_id for internal correlation; never pass a
  SubmissionId object to a sink or place it in a metric, label, error,
  free-form text, representation, serialization, miner/customer/public
  telemetry, or second identity type. Exact nominal validity is a correctness
  value, not an authenticated capability.
- [ ] Import, query, accept, and expose no SubmissionService,
  _SubmissionStore, private A7 record, A7 fee/store internal,
  RequesterIdentity, A8 private outcome, result ID, receipt/evidence store or
  ID, cursor, hotkey, wallet, customer/participant identity, signature,
  capability token, or authentication material. Trusted composition alone
  supplies any factual relationship to an owner transition.
- [ ] Prove A11 internal event kinds do not widen A6 public failure tags, do
  not create a second A7 lifecycle or A5 scoring disposition, and do not
  authenticate A5/A7 provenance.

### Exact A9/A10 boundary-error observations

- [ ] Implement BoundaryErrorKind with exact direct str, Enum inheritance and
  the exact eleven-member declaration order, names, and literal values:
  MCP_REQUEST/mcp.request.invalid,
  MCP_RESOURCE/mcp.resource_limit_exceeded,
  MCP_TOOL_UNAVAILABLE/mcp.tool_unavailable,
  MCP_CHALLENGE_UNAVAILABLE/mcp.challenge_unavailable,
  MCP_SUBMISSION_UNAVAILABLE/mcp.submission_unavailable,
  MCP_QUERY_BUDGET/mcp.query_budget_exceeded,
  MCP_INTEGRATION/mcp.integration_failure,
  LEADERBOARD_REQUEST/leaderboard.request.invalid,
  LEADERBOARD_RESOURCE/leaderboard.resource.exhausted,
  LEADERBOARD_UNAVAILABLE/leaderboard.fixture.unavailable, and
  LEADERBOARD_INTEGRATION/leaderboard.integration.failed; assert no aliases,
  auto(), integer/alternative values, or extra members. It remains request
  vocabulary only; after exact validation, A11 maps the chosen literal through
  a fixed local table to BoundaryErrorSnapshot.error_code and never passes the
  enum to a sink.
- [ ] Implement BoundaryErrorEvent as a frozen, slotted,
  representation-safe request with exactly one field, error_kind, accepting
  only exact BoundaryErrorKind; it is never a sink argument. Construct a fresh
  exact one-field BoundaryErrorSnapshot containing only the validated built-in
  literal, and exclude SubmissionId, ChallengeKey, requester, request/tool
  payload, cursor, provider, enum member, exception object/text, message,
  cause/context/traceback, private field, hidden identifier, seed/draw, and
  arbitrary string/mapping material.
- [ ] In a test-local trusted-composition harness only, prove exact public A9
  mappings: McpRequestError to MCP_REQUEST; McpResourceError to MCP_RESOURCE;
  McpToolUnavailableError to MCP_TOOL_UNAVAILABLE;
  McpChallengeUnavailableError to MCP_CHALLENGE_UNAVAILABLE;
  McpSubmissionUnavailableError to MCP_SUBMISSION_UNAVAILABLE;
  McpQueryBudgetError to MCP_QUERY_BUDGET; and McpIntegrationError to
  MCP_INTEGRATION. Production carbon.observability imports no A9 module.
- [ ] In a test-local trusted-composition harness only, prove exact public A10
  mappings: LeaderboardRequestError to LEADERBOARD_REQUEST;
  LeaderboardResourceError to LEADERBOARD_RESOURCE;
  LeaderboardUnavailableError to LEADERBOARD_UNAVAILABLE; and
  LeaderboardIntegrationError to LEADERBOARD_INTEGRATION. Production
  carbon.observability imports no A10 module.
- [ ] Reject raw provider exceptions, owner exceptions outside the exact
  mapped public classes, unknown or forged codes, subclasses/lookalikes, owner
  payloads, request values, identities, private fields, hidden identifiers,
  seeds/draws, arbitrary strings/mappings, and future reference/generator/
  reconstruction/retry/evidence/treasury/settlement/commercial/
  Challenge-health categories. Mapping uses exact class identity, never
  arbitrary `.code` inspection. No owner error, payload, request object, enum
  member, or caller-added enum attribute enters the snapshot. Omission is not
  collapse, and every raw provider error must first be translated by its A9/A10
  owner boundary.

### Metrics, labels, durations, and time

- [ ] Permit increment_counter only for exact SUBMIT_COUNT, SCORE_COUNT,
  REJECT_COUNT, and FAILED_INFRA_COUNT; each successful call represents one
  increment and accepts no delta/value, then maps through a fixed local literal
  table to one fresh CounterMetricSnapshot(metric_name) containing the exact
  built-in string.
- [ ] Reject STAGE_DURATION_NS through increment_counter and represent it only
  through observe_duration as a fresh DurationMetricSnapshot; never pass
  STAGE_DURATION_NS or any MetricKind member to a sink.
- [ ] Accept only exact DurationStage.SUBMIT or DurationStage.SCORE and an
  exact built-in duration_ns in 0..2**64-1, including zero; reject bool,
  subclasses, floats, coercion, negatives, and overflow; map the validated
  values to one fresh DurationMetricSnapshot whose stage is an exact local
  built-in literal and whose duration_ns is the exact built-in integer, with no
  DurationStage member reaching the sink.
- [ ] Expose exactly zero arbitrary metric labels: no label map, tag tuple,
  keyword metadata, SubmissionId, Challenge, requester, hotkey, wallet,
  customer, result, score, rank, cursor, provider, exception, boundary-error
  code, or arbitrary dimension in either request APIs or snapshots.
- [ ] Prove metric cardinality is structurally bounded by four counter members
  mapped to four exact CounterMetricSnapshot names plus two duration stages
  mapped to two exact DurationMetricSnapshot stage literals, with no dynamic
  metric name, gauge, decrement, reset, arbitrary histogram/value,
  boundary-error counter, or unratified FAILED_STRATEGY_COUNT.
- [ ] Emit no timestamp and import/call no wall clock, monotonic clock,
  current-time, date/timezone, sleep, deadline, or elapsed-time facility; use
  caller-supplied nanoseconds only.
- [ ] Prove duration and every metric are descriptive only and cannot change a
  score, gate, lifecycle, retry, rank, publication, Challenge-health decision,
  frontier, product, settlement, weight, or emission behavior.

### Positive construction and leakage elimination

- [ ] Validate in exact order before capacity or sink access: exact outer
  request type; exact canonical enum type, identity, name, and literal; exact
  event matrix or metric/duration boundary; fresh SubmissionId reconstruction
  through public A7 where applicable; mapping through A11-owned fixed literal
  tables; construction of one fresh snapshot with no request, owner, or enum
  reference; capacity/reentrancy acquisition; then at most one sink call.
- [ ] Use no arbitrary mapping/iterable/descriptor/object-graph traversal,
  reflection, dataclass dump, pickle, JSON, generic serializer, recursive
  sanitizer, serialize-then-redact path, or silent normalization/truncation/
  hashing/anonymization; never traverse/copy an enum __dict__ or sanitize and
  restore shared enum state.
- [ ] Prove hostile mappings, iterables, descriptors, aliases, cycles,
  mutation races, repr, str, CR/LF, Unicode confusables, and oversized values
  cannot enter or be consulted by accepted construction; caller-added enum
  attributes are ignored, and request-enum mutation after snapshot construction
  cannot alter that snapshot.
- [ ] Include no free-form textual event field or pattern-redaction engine in
  Wave A; eliminate textual injection/leakage structurally and require later
  ratification before any allow-listed text field.
- [ ] Exclude official/master/derived seeds, draw IDs, roles, domains,
  contexts, entropy, nonces, commitments/preimages, hidden-pack identities,
  full Strategies, parameters, weights, checkpoints, and artifacts, including
  any such value attached as an arbitrary request-enum attribute.
- [ ] Exclude requester/hotkey/wallet/customer/credential, fee/payment/reward,
  result/receipt/cursor/publication/provider, prior/estimate/scaffold/mock/light,
  and query-history material, including any such value attached as an arbitrary
  request-enum attribute.
- [ ] Exclude raw/combined/component scores, gates, margins, stress values,
  diagnostics, rank/history/delta, backend exceptions, exception objects,
  stack traces, paths, commands, environment/runtime-configuration values, and
  arbitrary diagnostics, including any such value attached as an arbitrary
  request-enum attribute.
- [ ] Prove no sink/error fallback diagnostic can reintroduce forbidden
  material and no score/rank/adaptive-query signal creates an exam oracle.

### Sink Protocols, calls, errors, and resources

- [ ] Implement exact standard-library Protocol seams with exact None returns:
  StructuredEventSink.emit_event(event: SubmissionEventSnapshot |
  BoundaryErrorSnapshot, /), MetricSink.increment_counter(metric:
  CounterMetricSnapshot, /), and MetricSink.observe_duration(metric:
  DurationMetricSnapshot, /).
- [ ] Accept trusted structural concrete sinks without Protocol subclassing,
  runtime_checkable, exact-type gating, or runtime Protocol introspection.
- [ ] Make at most one corresponding synchronous sink call per public
  operation, passing one exact fresh snapshot, and no sink call after caller
  validation, capacity, or reentrancy failure.
- [ ] Construct a distinct primitive-only A11-owned snapshot for every admitted
  call before invocation. Mutation through an A11-supplied object, including
  normal or object.__setattr__ mutation and a sink-retained reference, cannot
  alter caller, owner, retained, concurrent, another-service, or later A11
  state. A11 reuses no snapshot, mutates/restores no shared enum, holds no
  ordinary mutex across sink code, and claims no sandbox for unrelated globals
  independently imported by a sink.
- [ ] Treat missing/call-incompatible methods, non-None returns, hostile
  descriptor/hook ordinary exceptions, invocation ordinary exceptions, and
  sink-raised public A11 errors as one new fixed integration error.
- [ ] Translate every sink-origin ordinary Exception without passthrough,
  value/text/payload echo, partial value, cause, or context chain; never invoke
  hostile repr/str and never call a fallback logger.
- [ ] Propagate each non-Exception BaseException, including KeyboardInterrupt,
  SystemExit, and GeneratorExit, unchanged and add a source guard forbidding
  except BaseException around sink/public translation seams.
- [ ] Enforce one shared per-service non-blocking max_concurrent_calls policy
  across all operations; reject exact capacity exhaustion before sink access
  with the fixed resource error.
- [ ] Reject same-service sink reentrancy non-blockingly before a second sink
  call, even if general configured capacity remains, without holding an
  ordinary mutex across the sink.
- [ ] Release acquired capacity in finally after success, A11-created error,
  translated ordinary Exception, and propagated non-Exception BaseException.
- [ ] Implement no batching, queue, retry, fallback, worker, thread, async
  task, background work, suppression/reordering of domain actions, or
  exactly-once/durability claim.
- [ ] Demonstrate that a blocking test sink consumes only its finite capacity,
  additional calls fail non-blockingly, and A11 makes no timeout/preemption or
  production-availability claim.
- [ ] Implement exactly ObservabilityError(Exception) with direct
  ObservabilityRequestError, ObservabilityResourceError, and
  ObservabilityIntegrationError subclasses and no fourth policy error.
- [ ] Use the exact fixed code/message pairs from A11-R15 with immutable
  payloads, no diagnostic constructor arguments, no value echo, no hostile
  representation, no cause/context chain, and no generic serialization/copy.
- [ ] Map malformed mandatory construction/resource policy to request error,
  acquired-capacity/reentrancy exhaustion to resource error, and sink failures
  to integration error while preserving A11-created mappings.

### Domain, authority, dependency, packaging, and regression

- [ ] Accept, return, store, mutate, retry, suppress, or reorder no domain
  result; instrument no A5–A10 owner in the first implementation.
- [ ] Add a test-local composition harness proving an already-determined
  domain result survives telemetry failure and no telemetry exception changes
  scientific, lifecycle, publication, or economic state.
- [ ] In production A11 source, permit only Python standard library plus exact
  public SubmissionId and SubmissionState imports from carbon.fees and exact
  public ScoreStatus from carbon.scoring; do not re-export those owner types.
  Snapshot classes depend only on Python built-ins and local A11 validation;
  no A5/A7 owner source changes occur.
  Test-local A9/A10 mapping imports do not widen production dependencies.
  Because those permitted package-root imports may transitively initialize
  existing owner modules, source guards must prohibit direct A11 imports/calls
  rather than assert impossible absence of all transitive modules from
  `sys.modules`.
- [ ] Enforce the exact dependency graph: model.py to standard library plus
  public A5/A7 request values and local request-validation/snapshot helpers;
  providers.py to standard-library typing plus A11 snapshot model types;
  service.py to standard library plus A11 model/provider types and
  request-to-snapshot conversion; and __init__.py to the explicit eighteen
  model/provider/service re-exports. Add source guards
  against A5 engine/results, A6, A7 service/private records/store/fee internals, A8
  private outcomes/causes, production A9/A10, carbon.logging_utils,
  audit/evidence/receipt, legacy validator/neuron, Landscape, chain,
  settlement, weight, and emission imports.
- [ ] Prove A5–A10 packages do not import carbon.observability and no existing
  owner source or service is modified or instrumented merely to satisfy A11,
  including no A5/A7 enum hardening or monkeypatch.
- [ ] Add no OpenTelemetry, Prometheus, StatsD, logging backend, HTTP/network,
  filesystem/database, persistence, environment-selected backend, exporter,
  dashboard, alerting, threshold, authentication, public API, or production
  provider dependency/behavior.
- [ ] Prove no Challenge-health, information-budget, adaptive-query,
  scientific evidence, receipt/re-execution, durable ledger, frontier/Product
  Qualification, commercial, LIVE, settlement, treasury, chain, Bittensor,
  weight, or emission authority exists.
- [ ] Build a fresh zero-dependency wheel, install it with --no-deps outside
  the source tree, and prove isolated import exposes only the exact eighteen
  A11 names without loading forbidden optional/later-wave modules; prove all
  four exact snapshot shapes and primitive fields, non-dataclass/copy/pickle/
  dataclass-operation protections, unchanged public service signatures,
  request-to-snapshot conversion, distinct/retained/concurrent/later mutation
  isolation, and unchanged A5/A7 owner source.
- [ ] Pass the canonical focused suite at
  pytest tests/cpu/test_observability.py -q.
- [ ] Pass the complete default CPU regression without treating it as A11
  implementation evidence beyond the new focused contract.
- [ ] Pass strict Ruff and Black on later changed Python/test paths and the
  repository no-new-debt quality gate.
- [ ] Leave A12 separately owned and todo; create no tests/invariants/,
  pytest invariant marker, workflow/CI change, quality-baseline change, Wave-A
  closeout, Wave-B activation, or launch claim.

## Must not

Do not implement A11-R18 under this documentation task. Do not modify or
synchronize the PR #46 branch; do not mark PR #46 ready; do not mark A11
in_progress or done; do not check any criterion; do not modify .agent/WAVE.md;
do not create the package or test; do not modify Python, tests, fixtures,
dependencies, packaging, workflows, CI, or quality baselines; do not modify or
instrument A5–A10; do not add a production sink; do not begin A12; and do not
activate Wave B.

## Future focused command

~~~text
pytest tests/cpu/test_observability.py -q
~~~

The file and command are future repaired R18 implementation evidence only.
They do not exist or run as current-main A11 evidence in this documentation
candidate, and PR #46 evidence is non-authoritative until repaired and reviewed.
