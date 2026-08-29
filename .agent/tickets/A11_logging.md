# Ticket A11 — Bounded operational observability: events + metrics (C16)

**Wave:** A
**Status:** done
**Contract status:** A11-R1 through A11-R18 are ratified
**Build_Out:** v1.4 C16, interpreted through Design_Specs/Build_Out_Constitutional_Overlay.md
**Depends on:** current A5, A6, A7, A8, A9, and A10 semantic owner boundaries; initial production imports remain limited to exact public A5/A7 values
**Plan:** .agent/plans/A11_logging.md

> **Draft PR #49 closeout authority gate.** The merged A11 implementation and
> the recorded `66/66` audit are current-main engineering evidence. This
> branch's `done` status and checked criteria are proposed administrative state
> only; no criterion is repository-authoritative merely because it is checked
> here. They become repository authority only after the exact PR #49 head
> containing this gate is independently reviewed, explicitly human-authorized,
> and normally merged. Until then, current-main administrative authority
> remains A11 `in_progress` in `.agent/WAVE.md`, this ticket remains at its
> current-main state of `66 unchecked / 0 checked`, A12 remains `todo` and
> unstarted, Wave A remains incomplete, and Wave B remains inactive. This draft
> does not authorize A12 or any later-wave work.

## Closeout current state

PR #46's independently reviewed head
`e5ed60c4043abb3bfd2af945b5dd45b8e1996fcb`, tree
`3d6682803422497efc6bff26451c12d9c306f96c`, merged normally as signed
current-main commit `e2496e92eeae31befdaa430501bb9f00b0e6339e` with ordered
parents prior main `98865dd04c5a4018c8077517cb79aabd6045a468` and that reviewed
head. The reviewed-head-to-merge diff is empty and the prior-main manifest is
exactly `.agent/WAVE.md`, the four `carbon/observability/` source files, and
`tests/cpu/test_observability.py`.

Greptile's exact-head record is `Confidence Score: 5/5`, with no actionable
defect; review threads and formal change requests are both zero. Post-merge
run `33199541335` succeeded on the exact merge: CPU job `98945235783` reported
`2310 passed in 62.62s`, and Code-quality job `98945235938` retained `Ruff
757/776`, `Black 62/68`, removed debt `19/6`, five changed Python paths clean,
and no new debt.

The independent current-main implementation audit is **66 PASS / 0 FAIL**.
Fresh Python 3.11 Linux validation passed the focused suite (`337`), related
owner-boundary suite (`1330`), and full default CPU suite (`2310`). Fresh
wheel evidence is `carbon-0.9.0-py3-none-any.whl`, SHA-256
`ea686e933f6f93c72df281e79a3baebcb05f6789b25d4499ff81e937980e94fe`,
built without dependencies, installed with `--no-deps`, and imported in
isolated mode outside the source tree. Strict Ruff/Black passed all five A11
Python/test paths; the repository quality gate against exact closeout base
`e2496e92...` passed with changed Python files `0`; `git diff --check` passed.

The final snapshot allocator uses private identity-bound weak one-shot
eligibility. Failed, partial, repeated, donor, alternate, `object.__new__`,
abandoned, and concurrent construction paths fail closed while abandoned
allocations remain collectible. This is the ratified A11-R18 implementation;
no new owner decision or semantic amendment was introduced.

A11 is specified/ratified, implemented, and tested only for this bounded
in-process engineering scope. It is not scientifically, security, network,
commercially, or production qualified. A12 remains separately owned and
`todo`; Wave A remains incomplete; Wave B remains inactive.

## Historical pre-merge goal and reconciliation record

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

PR #39 normally merged A11-R1 through A11-R17 at historical commit
`4e4a66d29566a2a62a82188adddac76e6e0fb8b8`. That merge remains ratified, is
PR #47's original base, is the first parent of PR #45, and is ancestral to
current main; it is no longer current main.

Current `origin/main` is `644c6c38139e9215e5ccc8d3c8e8bc62e843dbb3`,
tree `15637ab89613daeec20f2f46bdefd045cb0ed7c6`, subject `Merge pull request
#48 from carbonphysicsai/agent/science-gtm-wave-integration`, with ordered
parents `bf6e2e8910f90b345ded44bdebb63fca73646b0d` and
`dec7ba8f1ac5d98c48c492abbdbeb8816e25e25e`, signature `verified=true`,
`reason=valid`. The immediately preceding PR #45 merge is
`bf6e2e8910f90b345ded44bdebb63fca73646b0d`, tree
`b6365e31b09339826b7568565bb28c7c32007fac`, ordered parents
`4e4a66d29566a2a62a82188adddac76e6e0fb8b8` and
`74f8edb04b3b806f4edc75de3ba8c4c6273815fb`, signature verified and valid.

Exact current-main push run `33093494970` succeeded. CPU job `98592266955`
recorded `1973 passed in 44.41s`; code-quality job `98592266774` recorded
`Ruff 757/776`, `Black 62/68`, removed debt `19/6`, changed Python files `0`,
and no new debt. Current-main `.agent/WAVE.md` is exact blob
`6369a373630392955ea2d58f258f06482173578c`: A10 is `done`; A11 and A12 are
`todo`; Wave A is controlling and incomplete; Wave B is inactive. Current main
contains no A11 implementation or focused test.

PR #45 contributes candidate-only Wave B v0.3 scientific-hardening planning and
changes only `.agent/DECISIONS.md` among PR #47's six authorized paths. PR #48
contributes Science-GTM future-ticket integration and changes none of the six
paths. Neither merge changes R18 semantics, widens A11/A12, activates Wave B,
implements A11, or creates any scientific, security, network, commercial, or
production authority.

PR #47's original base is `4e4a66d29566a2a62a82188adddac76e6e0fb8b8`;
its initial R18 commit is `9de896dea92e5378d99ef205cd21a29ef9f57fd3`;
its corrected reviewed head is `76ef2b194132bd2e07677d4ac1cf6baa83509faf`.
Old synthetic `7ab62b646ba1dee248e090cbd2490511a4b1d87a` and CI run `33039977702`
are stale old-base evidence only. Current-base drift is confirmed; R18 has no
semantic conflict; no new owner decision is required. The starting-state
classification required normal synchronization and current-state documentation
repair; merge `cf9a773...` and this single rebaseline commit satisfy those two
recovery actions.

The normal synchronization merge is
`cf9a773520645053e6d745c28aede15356fef80a`, tree
`b06e2aa7a0bf28700449010d320d09317201d155`, subject `merge: synchronize
A11-R18 with current main`, with ordered parents
`76ef2b194132bd2e07677d4ac1cf6baa83509faf` and
`644c6c38139e9215e5ccc8d3c8e8bc62e843dbb3`. This rebaseline is the single
documentation commit `docs: rebaseline A11-R18 against current main`, with that
synchronization merge as its sole parent. Its generated SHA/tree are recorded
after creation in PR #47 publication metadata, and its sequential and cumulative
manifest is exactly:

```text
M .agent/DECISIONS.md
M .agent/plans/A11_logging.md
M .agent/tickets/A11_logging.md
M Design_Specs/Build_Out_Constitutional_Overlay.md
M agent_pack/README.md
M docs/context/IMPLEMENTED_VS_SPECIFIED_CURRENT.md
```

The synchronized and rebaselined R18 semantic contract is unchanged.

Draft PR #46 remains open, draft, blocked, non-authoritative, and unchanged at
head `5b0b4927f8a4d2e6438b20a8201da43ae2a0645e`, tree
`3a84d98d95e53afaace00d500116cce91e66089e`. Its blocker body retains
the exact heading `## BLOCKED - A11-R18 owner decision required`,
`P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS`, and the withdrawal of the former
numeric readiness audit. Its generic-dataclass correction does not resolve
shared enum singletons.

```text
A11-R1 through A11-R17:
RATIFIED

A11-R18:
SPECIFIED as the exact synchronized and rebaselined draft candidate;
not RATIFIED until independent exact-head review, explicit human authorization,
and normal merge

A11 IMPLEMENTED:
NO on current main

A11 TESTED:
NO on current main

PR #46:
draft, blocked, non-authoritative, and unchanged

A11 SCIENTIFICALLY_QUALIFIED:
NO

A11 SECURITY_QUALIFIED:
NO

A11 NETWORK_QUALIFIED:
NO

A11 COMMERCIALLY_VALIDATED:
NO

A11 PRODUCTION_QUALIFIED:
NO

A11 WAVE STATUS:
todo on current main

A12:
todo

Wave A:
incomplete

Wave B:
inactive
```

The corrective review of parent `9de896dea92e5378d99ef205cd21a29ef9f57fd3`
records `P1_SNAPSHOT_TYPE_MUTATION_SCOPE_OVERCLAIM` as a `CONTRACT_DEFECT`
(`current main defect: NO`; `PR #47 candidate defect at that parent: YES`) and
`P2_PUBLIC_SNAPSHOT_CONSTRUCTION_AMBIGUITY` as a
`CONTRACT_PRECISION_DEFECT`.

```text
P1_SNAPSHOT_TYPE_MUTATION_SCOPE_OVERCLAIM:
CORRECTED

P2_PUBLIC_SNAPSHOT_CONSTRUCTION_AMBIGUITY:
CORRECTED
```

A11-R18 supersedes only the sink-facing portions of A11-R1, A11-R2, A11-R3,
A11-R10, A11-R13, A11-R14, and A11-R16. All other A11-R1 through A11-R17
behavior and authority ceilings remain in force. The effective amended contract
becomes A11-R1 through A11-R18 only after independent review, explicit human
authorization, and normal merge of this exact amendment candidate.

## Required contract

- Sole semantic and implementation ownership is
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
  public-constructor invocation helpers only.
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
- The four exact sink values are:

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
  exception, mapping, iterable, descriptor, object graph, or metadata.
  Direct public construction of all four snapshot classes is allowed through
  exactly the displayed parameter names and order, with every parameter
  required. Each constructor accepts only the exact built-in field types,
  literal sets, canonical UUIDv4 spelling, event-matrix combinations, and
  integer range above; rejects bool, field-type subclasses, coercion, malformed
  values, extra positional or keyword fields, constructor re-entry, partially
  initialized values, and subclass construction; creates the exact manual
  slotted non-dataclass instance with no instance dict and a fixed safe
  representation; and retains every assignment/deletion/copy/deepcopy/pickle/
  dataclass-operation rejection above. There is no hidden token, private-
  factory requirement, alternate constructor, or service-only construction
  path. Directly constructed snapshots remain authority-free and prove only
  exact closed shape, not provenance, owner transition, or lifecycle/
  scientific/audit/receipt/public/security/settlement/economic authority. The
  service rejects every snapshot type as a request value.
- The service exposes exactly emit_event(event), accepting exact
  ObservabilityEvent or BoundaryErrorEvent; increment_counter(metric); and
  observe_duration(stage, duration_ns). It accepts no mappings, free-form
  messages, metadata bags, dynamic names, arbitrary values, label maps,
  serializers, batches, backend selectors, or snapshot request values.
- StructuredEventSink receives only exact SubmissionEventSnapshot or
  BoundaryErrorSnapshot. MetricSink.increment_counter receives only exact
  CounterMetricSnapshot, and MetricSink.observe_duration receives only exact
  DurationMetricSnapshot. The Protocols remain structural and
  non-runtime-checkable; concrete sinks subclass neither Protocol. They are
  trusted in-process integration seams. Only trusted composition supplies a
  sink at mandatory service construction; miner-controlled or service-request
  input cannot choose or supply a sink implementation.
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
- Mutation of the supplied snapshot instance and its declared primitive fields,
  including normal assignment and object.__setattr__, cannot alter caller,
  owner, retained, concurrent, another-service, or later A11 state. A sink
  escape hatch may alter only its own distinct per-call snapshot instance; a
  retained instance cannot affect another call. A11 retains no snapshot for
  reuse, holds no ordinary mutex across sink code, and performs no shared-enum
  sanitize/restore.
- A11 does not defend against sink code that deliberately retrieves and mutates
  the snapshot class, A11 module globals, owner classes/modules, or any other
  process global. Such class/global mutation is outside the trusted in-process
  sink contract and requires process isolation or capability restriction,
  neither of which Wave A implements or claims. This exclusion does not permit
  any shared enum, owner nominal, request, mapping, exception, metadata, or
  other mutable shared instance to cross the sink seam; caller-added enum
  attributes remain excluded. Production-sink hardening, process isolation,
  plugin capability restriction, and hostile-sink qualification remain
  deferred. A11 claims no resistance to arbitrary malicious Python in the same
  process; SECURITY_QUALIFIED and PRODUCTION_QUALIFIED remain NO.
- A syntactically valid but unbound UUIDv4 has no lifecycle, scientific, audit,
  receipt, public, security, settlement, or economic authority. Production
  provenance and evidence remain separately deferred.
- A11-R1 through A11-R18 are ratified. The merged implementation and recorded
  tests establish only the bounded engineering scope; no documentation,
  implementation, test, or CI evidence widens the qualification ceilings.

## Implementation DoD

The independent exact-current-main closeout audit passed every criterion below:
**66 PASS / 0 FAIL**. Each checked item is supported by merged production
source, canonical focused tests, and CI, wheel, import, quality, or topology
evidence where applicable.

### Exact package and public surface

- [x] Add only carbon/observability/__init__.py, model.py, providers.py, and
  service.py with the effective A11-R18 module ownership: model request/resource
  values, four snapshot types, errors, and private exact request-validation and
  public-constructor invocation helpers only; provider Protocols only; service
  request-to-snapshot conversion, private accounting, sink invocation, and
  translation only; and __init__.py exact re-exports only. Do not modify,
  alias, import through, or re-export from the inert A0 carbon/logging_utils
  compatibility marker, carbon/audit, or root carbon/__init__.py.
- [x] Export the exact ordered eighteen-name carbon.observability.__all__ tuple
  amended by A11-R18, with all four snapshots in their exact specified order
  and directly publicly constructible through only their exact displayed
  required constructors, with no hidden token, private-factory requirement,
  alternate/subclass constructor, owner-type re-export, alias, generic logger,
  serializer, production provider, no-op default, private helper, or extra
  error.
- [x] Implement exact direct str, Enum inheritance, declaration order, names,
  and literal values for EventKind (SUBMIT, SCORE, REJECT, FAILED_STRATEGY,
  FAILED_INFRA), MetricKind (SUBMIT_COUNT, SCORE_COUNT, REJECT_COUNT,
  FAILED_INFRA_COUNT, STAGE_DURATION_NS), and DurationStage (SUBMIT, SCORE),
  with no aliases, auto(), integer values, alternative lowercase values, or
  extra members.
- [x] Implement ObservabilityEvent as a frozen, slotted,
  representation-safe owner-shaped operational-observation request with exact
  ordered fields kind, submission_id, submission_state, score_status and no
  generic serialization/copy path; it is a validated request only, never a sink
  argument or sink-safe snapshot, its public request constructor continues to
  accept the exact canonical owner enums rather than primitive snapshot fields,
  and it proves neither retained-record existence nor authenticated provenance.
- [x] Implement ObservabilityResourceLimits as a frozen, slotted,
  representation-safe value with only required max_concurrent_calls, an exact
  built-in integer in 1..2**64-1.
- [x] Implement exactly ObservabilityService(event_sink, metric_sink,
  resource_limits) with all arguments mandatory and no default, None,
  environment, registry, singleton, global sink, backend selector, or
  production numeric policy.
- [x] Expose only emit_event(event: ObservabilityEvent |
  BoundaryErrorEvent), increment_counter(metric), and
  observe_duration(stage, duration_ns), each returning exact None on success;
  accept no snapshot as a request;
  expose no fourth operation, log, mapping emit, generic metric, record, batch,
  flush, retry, queue, serializer, exporter, or sink-selection operation.
- [x] Reject subclasses, forged enum members, corrupted canonical enum name or
  literal value, bool-as-int, coercible primitives, generic lookalikes, unknown
  shapes, and unsupported combinations through exact type, identity, name, and
  literal validation without calling hostile repr or str; never inspect, copy,
  traverse, retain, render, or emit unrelated caller-added enum attributes.
  For each public snapshot constructor, also reject bool, field-type and
  snapshot-class subclasses, coercion, malformed values/combinations, extra
  positional or keyword fields, constructor re-entry, and partially initialized
  values before any accepted snapshot instance is exposed.

### Exact submission event consistency and correlation

- [x] Accept a SUBMIT-shaped request only with a fresh copied exact A7
  SubmissionId, exact SubmissionState.RECEIVED, and score_status=None.
- [x] Accept a SCORE-shaped request only with a fresh copied exact A7
  SubmissionId, exact SubmissionState.SCORED, and exact canonical A5
  ScoreStatus.SCORED or ScoreStatus.MANDATORY_GATE_FAILED.
- [x] Accept a REJECT-shaped request only with a fresh copied exact A7
  SubmissionId, exact SubmissionState.REJECTED, and score_status=None.
- [x] Accept a FAILED_STRATEGY-shaped request only with a fresh copied exact A7
  SubmissionId, exact terminal SubmissionState.FAILED_STRATEGY, and
  score_status=None.
- [x] Accept a FAILED_INFRA-shaped request only with a fresh copied exact A7
  SubmissionId, exact terminal SubmissionState.FAILED_INFRA, and
  score_status=None.
- [x] Reject every mismatched kind/state/status combination and direct
  PACK_NOT_READY, retryable-infrastructure, PUBLISHED, CANCELLED,
  pre-record/no-ID, or unsupported future-category request without remapping it
  to a current event.
- [x] Preserve A7 lifecycle SCORED versus A5 SCORED and
  MANDATORY_GATE_FAILED; preserve request/admission rejection, terminal
  strategy failure, terminal infrastructure failure, and non-scientific
  PACK_NOT_READY as distinct meanings while making no retained-state or
  transition-occurrence claim.
- [x] Prove an open duplicate, pre-record request/resource failure, retryable
  infrastructure result, omitted future reference/generator/reconstruction
  failure, or syntactically valid but unbound UUIDv4 cannot be falsely promoted
  into lifecycle, scientific, audit, receipt, public, security, settlement, or
  economic authority.
- [x] Reconstruct SubmissionId only through its public A7 constructor and
  permit only its exact canonical 36-ASCII built-in string as
  SubmissionEventSnapshot.submission_id for internal correlation; never pass a
  SubmissionId object to a sink or place it in a metric, label, error,
  free-form text, representation, serialization, miner/customer/public
  telemetry, or second identity type. Exact nominal validity is a correctness
  value, not an authenticated capability.
- [x] Import, query, accept, and expose no SubmissionService,
  _SubmissionStore, private A7 record, A7 fee/store internal,
  RequesterIdentity, A8 private outcome, result ID, receipt/evidence store or
  ID, cursor, hotkey, wallet, customer/participant identity, signature,
  capability token, or authentication material. Trusted composition alone
  supplies any factual relationship to an owner transition.
- [x] Prove A11 internal event kinds do not widen A6 public failure tags, do
  not create a second A7 lifecycle or A5 scoring disposition, and do not
  authenticate A5/A7 provenance.

### Exact A9/A10 boundary-error observations

- [x] Implement BoundaryErrorKind with exact direct str, Enum inheritance and
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
  a fixed local table to the distinct primitive field accepted by the direct
  public BoundaryErrorSnapshot(error_code) constructor and never passes the
  request enum to a sink or accepts the snapshot as a request.
- [x] Implement BoundaryErrorEvent as a frozen, slotted,
  representation-safe request with exactly one field, error_kind, accepting
  only exact BoundaryErrorKind; it is never a sink argument. Through the same
  direct public exact constructor available to callers, construct a fresh
  one-field BoundaryErrorSnapshot containing only the validated built-in
  literal; reject malformed/extra/coercible/subclass/re-entry/partial snapshot
  construction and exclude SubmissionId, ChallengeKey, requester, request/tool
  payload, cursor, provider, enum member, exception object/text, message,
  cause/context/traceback, private field, hidden identifier, seed/draw, and
  arbitrary string/mapping material.
- [x] In a test-local trusted-composition harness only, prove exact public A9
  mappings: McpRequestError to MCP_REQUEST; McpResourceError to MCP_RESOURCE;
  McpToolUnavailableError to MCP_TOOL_UNAVAILABLE;
  McpChallengeUnavailableError to MCP_CHALLENGE_UNAVAILABLE;
  McpSubmissionUnavailableError to MCP_SUBMISSION_UNAVAILABLE;
  McpQueryBudgetError to MCP_QUERY_BUDGET; and McpIntegrationError to
  MCP_INTEGRATION. Production carbon.observability imports no A9 module.
- [x] In a test-local trusted-composition harness only, prove exact public A10
  mappings: LeaderboardRequestError to LEADERBOARD_REQUEST;
  LeaderboardResourceError to LEADERBOARD_RESOURCE;
  LeaderboardUnavailableError to LEADERBOARD_UNAVAILABLE; and
  LeaderboardIntegrationError to LEADERBOARD_INTEGRATION. Production
  carbon.observability imports no A10 module.
- [x] Reject raw provider exceptions, owner exceptions outside the exact
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

- [x] Permit increment_counter only for exact SUBMIT_COUNT, SCORE_COUNT,
  REJECT_COUNT, and FAILED_INFRA_COUNT; each successful call represents one
  increment and accepts no delta/value, then maps through a fixed local literal
  table to the distinct direct public CounterMetricSnapshot(metric_name)
  constructor for one fresh snapshot containing the exact built-in string;
  never accept that snapshot as the metric request.
- [x] Reject STAGE_DURATION_NS through increment_counter and represent it only
  through observe_duration as a fresh directly publicly constructed
  DurationMetricSnapshot; never pass STAGE_DURATION_NS or any MetricKind member
  to a sink and never accept either metric snapshot as a request value.
- [x] Accept only exact DurationStage.SUBMIT or DurationStage.SCORE and an
  exact built-in duration_ns in 0..2**64-1, including zero; reject bool,
  subclasses, floats, coercion, negatives, and overflow; map the validated
  values through the direct public DurationMetricSnapshot(stage, duration_ns)
  constructor to one fresh snapshot whose stage is an exact local built-in
  literal and whose duration_ns is the exact built-in integer, with no
  DurationStage member reaching the sink; direct constructor input obeys the
  same literal/type/range checks but creates no valid service request.
- [x] Expose exactly zero arbitrary metric labels: no label map, tag tuple,
  keyword metadata, SubmissionId, Challenge, requester, hotkey, wallet,
  customer, result, score, rank, cursor, provider, exception, boundary-error
  code, or arbitrary dimension in either request APIs or snapshots.
- [x] Prove metric cardinality is structurally bounded by four counter members
  mapped to four exact CounterMetricSnapshot names plus two duration stages
  mapped to two exact DurationMetricSnapshot stage literals, with no dynamic
  metric name, gauge, decrement, reset, arbitrary histogram/value,
  boundary-error counter, or unratified FAILED_STRATEGY_COUNT.
- [x] Emit no timestamp and import/call no wall clock, monotonic clock,
  current-time, date/timezone, sleep, deadline, or elapsed-time facility; use
  caller-supplied nanoseconds only.
- [x] Prove duration and every metric are descriptive only and cannot change a
  score, gate, lifecycle, retry, rank, publication, Challenge-health decision,
  frontier, product, settlement, weight, or emission behavior.

### Positive construction and leakage elimination

- [x] Validate in exact order before capacity or sink access: exact outer
  request type; exact canonical enum type, identity, name, and literal; exact
  event matrix or metric/duration boundary; fresh SubmissionId reconstruction
  through public A7 where applicable; mapping through A11-owned fixed literal
  tables; construction through the same direct public exact constructor of one
  fresh snapshot with no request, owner, or enum reference; capacity/reentrancy
  acquisition; then at most one sink call. Direct snapshot construction never
  bypasses or satisfies this service-request validation path.
- [x] Use no arbitrary mapping/iterable/descriptor/object-graph traversal,
  reflection, dataclass dump, pickle, JSON, generic serializer, recursive
  sanitizer, serialize-then-redact path, or silent normalization/truncation/
  hashing/anonymization; never traverse/copy an enum __dict__ or sanitize and
  restore shared enum state.
- [x] Prove hostile mappings, iterables, descriptors, aliases, cycles,
  mutation races, repr, str, CR/LF, Unicode confusables, and oversized values
  cannot enter or be consulted by accepted construction; caller-added enum
  attributes are ignored, and request-enum mutation after snapshot construction
  cannot alter that snapshot.
- [x] Include no free-form textual event field or pattern-redaction engine in
  Wave A; eliminate textual injection/leakage structurally and require later
  ratification before any allow-listed text field.
- [x] Exclude official/master/derived seeds, draw IDs, roles, domains,
  contexts, entropy, nonces, commitments/preimages, hidden-pack identities,
  full Strategies, parameters, weights, checkpoints, and artifacts, including
  any such value attached as an arbitrary request-enum attribute; prove no
  arbitrary enum attribute enters any declared snapshot-instance field through
  service conversion or direct public construction.
- [x] Exclude requester/hotkey/wallet/customer/credential, fee/payment/reward,
  result/receipt/cursor/publication/provider, prior/estimate/scaffold/mock/light,
  and query-history material, including any such value attached as an arbitrary
  request-enum attribute.
- [x] Exclude raw/combined/component scores, gates, margins, stress values,
  diagnostics, rank/history/delta, backend exceptions, exception objects,
  stack traces, paths, commands, environment/runtime-configuration values, and
  arbitrary diagnostics, including any such value attached as an arbitrary
  request-enum attribute.
- [x] Prove no sink/error fallback diagnostic can reintroduce forbidden
  material and no score/rank/adaptive-query signal creates an exam oracle.

### Sink Protocols, calls, errors, and resources

- [x] Implement exact standard-library Protocol seams with exact None returns:
  StructuredEventSink.emit_event(event: SubmissionEventSnapshot |
  BoundaryErrorSnapshot, /), MetricSink.increment_counter(metric:
  CounterMetricSnapshot, /), and MetricSink.observe_duration(metric:
  DurationMetricSnapshot, /). These exact snapshot parameters remain distinct
  from the unchanged public service-request parameters and define trusted
  in-process integration seams only.
- [x] Accept trusted structural concrete sinks without Protocol subclassing,
  runtime_checkable, exact-type gating, or runtime Protocol introspection.
- [x] Make at most one corresponding synchronous sink call per public
  operation, passing one exact fresh snapshot, and no sink call after caller
  validation, capacity, or reentrancy failure.
- [x] Construct a distinct primitive-only A11-owned snapshot for every admitted
  call before invocation. Mutation of the supplied snapshot instance and its
  declared primitive fields, including normal assignment and
  object.__setattr__, cannot alter caller, owner, retained, concurrent,
  another-service, or later A11 state. Retained instance mutation cannot affect
  another call. A11 reuses no snapshot, mutates/restores no shared enum, and
  holds no ordinary mutex across sink code. Deliberate mutation of the snapshot
  class, A11 module globals, owner classes/modules, or any process global is
  outside the trusted in-process sink contract and requires unclaimed process
  isolation or capability restriction; no arbitrary-hostile-Python resistance
  is asserted.
- [x] Treat missing/call-incompatible methods, non-None returns, hostile
  descriptor/hook ordinary exceptions, invocation ordinary exceptions, and
  sink-raised public A11 errors as one new fixed integration error.
- [x] Translate every sink-origin ordinary Exception without passthrough,
  value/text/payload echo, partial value, cause, or context chain; never invoke
  hostile repr/str and never call a fallback logger.
- [x] Propagate each non-Exception BaseException, including KeyboardInterrupt,
  SystemExit, and GeneratorExit, unchanged and add a source guard forbidding
  except BaseException around sink/public translation seams.
- [x] Enforce one shared per-service non-blocking max_concurrent_calls policy
  across all operations; reject exact capacity exhaustion before sink access
  with the fixed resource error.
- [x] Reject same-service sink reentrancy non-blockingly before a second sink
  call, even if general configured capacity remains, without holding an
  ordinary mutex across the sink.
- [x] Release acquired capacity in finally after success, A11-created error,
  translated ordinary Exception, and propagated non-Exception BaseException.
- [x] Implement no batching, queue, retry, fallback, worker, thread, async
  task, background work, suppression/reordering of domain actions, or
  exactly-once/durability claim.
- [x] Demonstrate that a blocking test sink consumes only its finite capacity,
  additional calls fail non-blockingly, and A11 makes no timeout/preemption or
  production-availability claim.
- [x] Implement exactly ObservabilityError(Exception) with direct
  ObservabilityRequestError, ObservabilityResourceError, and
  ObservabilityIntegrationError subclasses and no fourth policy error.
- [x] Use the exact fixed code/message pairs from A11-R15 with immutable
  payloads, no diagnostic constructor arguments, no value echo, no hostile
  representation, no cause/context chain, and no generic serialization/copy.
- [x] Map malformed mandatory construction/resource policy to request error,
  acquired-capacity/reentrancy exhaustion to resource error, and sink failures
  to integration error while preserving A11-created mappings.

### Domain, authority, dependency, packaging, and regression

- [x] Accept, return, store, mutate, retry, suppress, or reorder no domain
  result; instrument no A5–A10 owner in the first implementation.
- [x] Add a test-local composition harness proving an already-determined
  domain result survives telemetry failure and no telemetry exception changes
  scientific, lifecycle, publication, or economic state.
- [x] In production A11 source, permit only Python standard library plus exact
  public SubmissionId and SubmissionState imports from carbon.fees and exact
  public ScoreStatus from carbon.scoring; do not re-export those owner types.
  Snapshot classes depend only on Python built-ins and local A11 validation;
  no A5/A7 owner source changes occur.
  Test-local A9/A10 mapping imports do not widen production dependencies.
  Because those permitted package-root imports may transitively initialize
  existing owner modules, source guards must prohibit direct A11 imports/calls
  rather than assert impossible absence of all transitive modules from
  `sys.modules`.
- [x] Enforce the exact dependency graph: model.py to standard library plus
  public A5/A7 request values and local request-validation/public-constructor
  invocation helpers;
  providers.py to standard-library typing plus A11 snapshot model types;
  service.py to standard library plus A11 model/provider types and
  request-to-snapshot conversion; and __init__.py to the explicit eighteen
  model/provider/service re-exports. Add source guards
  against A5 engine/results, A6, A7 service/private records/store/fee internals, A8
  private outcomes/causes, production A9/A10, carbon.logging_utils,
  audit/evidence/receipt, legacy validator/neuron, Landscape, chain,
  settlement, weight, and emission imports.
- [x] Prove A5–A10 packages do not import carbon.observability and no existing
  owner source or service is modified or instrumented merely to satisfy A11,
  including no A5/A7 enum hardening or monkeypatch.
- [x] Add no OpenTelemetry, Prometheus, StatsD, logging backend, HTTP/network,
  filesystem/database, persistence, environment-selected backend, exporter,
  dashboard, alerting, threshold, authentication, public API, or production
  provider dependency/behavior.
- [x] Prove no Challenge-health, information-budget, adaptive-query,
  scientific evidence, receipt/re-execution, durable ledger, frontier/Product
  Qualification, commercial, LIVE, settlement, treasury, chain, Bittensor,
  weight, or emission authority exists.
- [x] Build a fresh zero-dependency wheel, install it with --no-deps outside
  the source tree, and prove isolated import exposes only the exact eighteen
  A11 names without loading forbidden optional/later-wave modules; prove all
  four direct public exact snapshot constructors and required parameter order,
  malformed/extra/re-entry/partial/subclass/coercion rejection, primitive
  fields, non-dataclass/copy/pickle/dataclass-operation protections, unchanged
  public service signatures, request-to-snapshot conversion, and supplied-
  instance/declared-field isolation across distinct, retained, concurrent, and
  later calls. Do not claim isolation from deliberate snapshot-class/module/
  global mutation or arbitrary hostile sink code. Prove unchanged A5/A7 owner
  source.
- [x] Pass the canonical focused suite at
  pytest tests/cpu/test_observability.py -q.
- [x] Pass the complete default CPU regression without treating it as A11
  implementation evidence beyond the new focused contract.
- [x] Pass strict Ruff and Black on later changed Python/test paths and the
  repository no-new-debt quality gate.
- [x] Leave A12 separately owned and todo; create no tests/invariants/,
  pytest invariant marker, workflow/CI change, quality-baseline change, Wave-A
  closeout, Wave-B activation, or launch claim.

## Closeout limits

This documentation-only closeout changes no Python, tests, fixtures,
dependencies, packaging, workflows, CI, or quality baselines; modifies or
instruments no A5–A10 owner; adds no production sink; begins no A12 work;
marks no Wave-A completion; activates no Wave B work; and creates no scientific,
security, network, commercial, production, LIVE, frontier, product,
settlement, chain, weight, emission, or launch claim.

## Canonical focused command

~~~text
pytest tests/cpu/test_observability.py -q
~~~

The file is merged current-main A11 evidence. Fresh closeout execution reported
`337 passed`; the exact post-merge full-suite run reported `2310 passed`.
