# Ticket A11 — Bounded operational observability: events + metrics (C16)

**Wave:** A
**Status:** `todo`
**Contract status:** documentation-only candidate; ratified only after independent review, explicit human authorization, and normal merge
**Build_Out:** v1.4 C16, interpreted through `Design_Specs/Build_Out_Constitutional_Overlay.md`
**Depends on:** A5 and A7 public owner values
**Plan:** `.agent/plans/A11_logging.md`

## Goal

Implement one bounded in-process operational observability primitive only after
separate explicit implementation authorization. The future primitive uses
closed immutable event, counter, and duration vocabularies; exact A5/A7 owner
status projection; exact A7 `SubmissionId` correlation; empty metric labels;
positive construction; finite non-blocking capacity; and injected
standard-library Protocol sinks.

It is not a generic logger, evidence store, lifecycle owner, scoring or
Challenge-health authority, production exporter, public API, alerting system,
or frontier/product/settlement/chain/weight/emission surface.

## Required contract

- Sole future semantic and implementation ownership is
  `carbon/observability/{__init__,model,providers,service}.py`, with canonical
  focused tests only at `tests/cpu/test_observability.py`.
  `carbon/logging_utils` remains only the unchanged inert A0 compatibility
  marker; `carbon/audit`, root `carbon` exports, and every A5–A10 owner
  implementation also remain unchanged.
- The service exposes exactly `emit_event(event)`,
  `increment_counter(metric)`, and `observe_duration(stage, duration_ns)`.
  It accepts no mappings, free-form messages, metadata bags, dynamic names,
  arbitrary values, label maps, serializers, batches, or backend selectors.
- Events reuse exact public A7 `SubmissionId`/`SubmissionState` and A5
  `ScoreStatus`; metrics use exact closed enums with no arbitrary labels.
- Construction is positive and allow-listed. No generic serialize-then-redact
  path, recursive sanitizer, hostile `repr`/`str`, current-time access,
  fallback logger, queue, retry, background task, or production provider exists.
- A11 remains `todo` throughout this documentation candidate. Documentation
  review and repository regression evidence are not A11 implementation or test
  evidence.

## Implementation DoD

Every implementation criterion below remains unchecked. This documentation
candidate implements and tests nothing.

### Exact package and public surface

- [ ] Add only `carbon/observability/__init__.py`, `model.py`, `providers.py`,
  and `service.py`; do not modify, alias, import through, or re-export from
  the inert A0 `carbon/logging_utils` compatibility marker, `carbon/audit`, or
  root `carbon/__init__.py`.
- [ ] Export the exact ordered twelve-name `carbon.observability.__all__` tuple
  ratified in A11-R2, with no owner-type re-export, alias, generic logger,
  serializer, production provider, no-op default, or extra error.
- [ ] Implement exact declaration/value order for `EventKind` (`SUBMIT`,
  `SCORE`, `REJECT`, `FAILED_STRATEGY`, `FAILED_INFRA`), `MetricKind`
  (`SUBMIT_COUNT`, `SCORE_COUNT`, `REJECT_COUNT`, `FAILED_INFRA_COUNT`,
  `STAGE_DURATION_NS`), and `DurationStage` (`SUBMIT`, `SCORE`).
- [ ] Implement `ObservabilityEvent` as a frozen, slotted,
  representation-safe value with exact ordered fields `kind`, `submission_id`,
  `submission_state`, `score_status` and no generic serialization/copy path.
- [ ] Implement `ObservabilityResourceLimits` as a frozen, slotted,
  representation-safe value with only required `max_concurrent_calls`, an exact
  built-in integer in `1..2**64-1`.
- [ ] Implement exactly `ObservabilityService(event_sink, metric_sink,
  resource_limits)` with all arguments mandatory and no default, `None`,
  environment, registry, singleton, global sink, backend selector, or production
  numeric policy.
- [ ] Expose only `emit_event(event)`, `increment_counter(metric)`, and
  `observe_duration(stage, duration_ns)`, each returning exact `None` on
  success; expose no `log`, mapping `emit`, generic `metric`, `record`, batch,
  flush, retry, queue, serializer, exporter, or sink-selection operation.
- [ ] Reject subclasses, forged enum members, bool-as-int, coercible
  primitives, generic lookalikes, unknown shapes, and unsupported combinations
  without calling hostile `repr` or `str`.

### Exact event projection and correlation

- [ ] Accept `SUBMIT` only with a fresh copied exact A7 `SubmissionId`, exact
  `SubmissionState.RECEIVED`, and `score_status=None`.
- [ ] Accept `SCORE` only with a fresh copied exact A7 `SubmissionId`, exact
  `SubmissionState.SCORED`, and exact canonical A5 `ScoreStatus.SCORED` or
  `ScoreStatus.MANDATORY_GATE_FAILED`.
- [ ] Accept `REJECT` only with a fresh copied exact A7 `SubmissionId`, exact
  `SubmissionState.REJECTED`, and `score_status=None`.
- [ ] Accept `FAILED_STRATEGY` only with a fresh copied exact A7
  `SubmissionId`, exact terminal `SubmissionState.FAILED_STRATEGY`, and
  `score_status=None`.
- [ ] Accept `FAILED_INFRA` only with a fresh copied exact A7 `SubmissionId`,
  exact terminal `SubmissionState.FAILED_INFRA`, and `score_status=None`.
- [ ] Reject every mismatched kind/state/status combination and direct
  `PACK_NOT_READY`, retryable-infrastructure, `PUBLISHED`, `CANCELLED`,
  pre-record/no-ID, or unsupported future-category projection without
  remapping it to a current event.
- [ ] Preserve A7 lifecycle `SCORED` versus A5 `SCORED` and
  `MANDATORY_GATE_FAILED`; preserve request/admission rejection, terminal
  strategy failure, terminal infrastructure failure, and non-scientific
  `PACK_NOT_READY` as distinct meanings.
- [ ] Prove an open duplicate, pre-record request/resource failure, retryable
  infrastructure result, or omitted future reference/generator/reconstruction
  failure cannot be falsely represented as a new current A11 event.
- [ ] Reconstruct `SubmissionId` only through its public A7 constructor and
  permit it only as the structured internal event correlation field; never
  place it in a metric, label, error, free-form text, representation,
  serialization, miner/customer/public telemetry, or second identity type.
- [ ] Import, accept, and expose no `RequesterIdentity`, result ID, receipt ID,
  cursor, hotkey, wallet, customer/participant identity, or authentication
  material.
- [ ] Prove A11 internal event kinds do not widen A6 public failure tags and
  do not create a second A7 lifecycle or A5 scoring disposition.

### Metrics, labels, durations, and time

- [ ] Permit `increment_counter` only for exact `SUBMIT_COUNT`, `SCORE_COUNT`,
  `REJECT_COUNT`, and `FAILED_INFRA_COUNT`; each successful call represents one
  increment and accepts no delta/value.
- [ ] Reject `STAGE_DURATION_NS` through `increment_counter` and represent it
  only through `observe_duration`.
- [ ] Accept only exact `DurationStage.SUBMIT` or `DurationStage.SCORE` and an
  exact built-in `duration_ns` in `0..2**64-1`, including zero; reject bool,
  subclasses, floats, coercion, negatives, and overflow.
- [ ] Expose exactly zero arbitrary metric labels: no label map, tag tuple,
  keyword metadata, SubmissionId, Challenge, requester, hotkey, wallet,
  customer, result, score, rank, cursor, provider, exception, or arbitrary
  dimension.
- [ ] Prove metric cardinality is structurally bounded by four counter members
  plus two duration stages, with no dynamic metric name, gauge, decrement,
  reset, arbitrary histogram/value, or unratified `FAILED_STRATEGY_COUNT`.
- [ ] Emit no timestamp and import/call no wall clock, monotonic clock,
  current-time, date/timezone, sleep, deadline, or elapsed-time facility; use
  caller-supplied nanoseconds only.
- [ ] Prove duration and every metric are descriptive only and cannot change a
  score, gate, lifecycle, retry, rank, publication, Challenge-health decision,
  frontier, product, settlement, weight, or emission behavior.

### Positive construction and leakage elimination

- [ ] Validate in exact order: outer exact type, declared positive fields,
  exact owner/enum members, prohibited-data exclusion by shape, fresh immutable
  owned reconstruction, capacity/reentrancy acquisition, then one sink access.
- [ ] Use no arbitrary mapping/iterable/descriptor/object-graph traversal,
  reflection, dataclass dump, pickle, JSON, generic serializer, recursive
  sanitizer, serialize-then-redact path, or silent normalization/truncation/
  hashing/anonymization.
- [ ] Prove hostile mappings, iterables, descriptors, aliases, cycles,
  mutation races, `repr`, `str`, CR/LF, Unicode confusables, and oversized
  values cannot enter or be consulted by accepted construction.
- [ ] Include no free-form textual event field or pattern-redaction engine in
  Wave A; eliminate textual injection/leakage structurally and require later
  ratification before any allow-listed text field.
- [ ] Exclude official/master/derived seeds, draw IDs, roles, domains,
  contexts, entropy, nonces, commitments/preimages, hidden-pack identities,
  full Strategies, parameters, weights, checkpoints, and artifacts.
- [ ] Exclude requester/hotkey/wallet/customer/credential, fee/payment/reward,
  result/receipt/cursor/publication/provider, prior/estimate/scaffold/mock/light,
  and query-history material.
- [ ] Exclude raw/combined/component scores, gates, margins, stress values,
  diagnostics, rank/history/delta, backend exceptions, exception objects,
  stack traces, paths, commands, environment/runtime-configuration values, and
  arbitrary diagnostics.
- [ ] Prove no sink/error fallback diagnostic can reintroduce forbidden
  material and no score/rank/adaptive-query signal creates an exam oracle.

### Sink Protocols, calls, errors, and resources

- [ ] Implement exact standard-library `StructuredEventSink.emit_event(event)`
  and `MetricSink.increment_counter(metric)` / `observe_duration(stage,
  duration_ns)` Protocol seams with positional typed arguments and exact
  `None` returns.
- [ ] Accept trusted structural concrete sinks without Protocol subclassing,
  `runtime_checkable`, exact-type gating, or runtime Protocol introspection.
- [ ] Make at most one corresponding synchronous sink call per public
  operation and no sink call after caller validation, capacity, or reentrancy
  failure.
- [ ] Copy every sink argument into an immutable sink-safe owner value before
  invocation and prove caller/sink mutation cannot alter a retained or later
  A11 value.
- [ ] Treat missing/call-incompatible methods, non-`None` returns, hostile
  descriptor/hook ordinary exceptions, invocation ordinary exceptions, and
  sink-raised public A11 errors as one new fixed integration error.
- [ ] Translate every sink-origin ordinary `Exception` without passthrough,
  value/text/payload echo, partial value, cause, or context chain; never invoke
  hostile `repr`/`str` and never call a fallback logger.
- [ ] Propagate each non-`Exception` `BaseException`, including
  `KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`, unchanged and add a
  source guard forbidding `except BaseException` around sink/public translation
  seams.
- [ ] Enforce one shared per-service non-blocking `max_concurrent_calls`
  policy across all operations; reject exact capacity exhaustion before sink
  access with the fixed resource error.
- [ ] Reject same-service sink reentrancy non-blockingly before a second sink
  call, even if general configured capacity remains, without holding an
  ordinary mutex across the sink.
- [ ] Release acquired capacity in `finally` after success, A11-created error,
  translated ordinary `Exception`, and propagated non-`Exception`
  `BaseException`.
- [ ] Implement no batching, queue, retry, fallback, worker, thread, async
  task, background work, suppression/reordering of domain actions, or
  exactly-once/durability claim.
- [ ] Demonstrate that a blocking test sink consumes only its finite capacity,
  additional calls fail non-blockingly, and A11 makes no timeout/preemption or
  production-availability claim.
- [ ] Implement exactly `ObservabilityError(Exception)` with direct
  `ObservabilityRequestError`, `ObservabilityResourceError`, and
  `ObservabilityIntegrationError` subclasses and no fourth policy error.
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
- [ ] Permit only Python standard library plus exact public imports
  `SubmissionId`, `SubmissionState`, and `ScoreStatus`; do not re-export those
  owner types from `carbon.observability`.
- [ ] Add source guards against A5 engine/results, A6, A7 service/private
  records/store/fees, A8 private outcomes/causes, A9, A10,
  `carbon.logging_utils`, audit/evidence/receipt, legacy validator/neuron,
  Landscape, chain, settlement, weight, and emission imports.
- [ ] Prove A5–A10 packages do not import `carbon.observability` and no
  existing owner service is modified merely to satisfy A11.
- [ ] Add no OpenTelemetry, Prometheus, StatsD, logging backend, HTTP/network,
  filesystem/database, persistence, environment-selected backend, exporter,
  dashboard, alerting, threshold, authentication, public API, or production
  provider dependency/behavior.
- [ ] Prove no Challenge-health, information-budget, adaptive-query,
  scientific evidence, receipt/re-execution, durable ledger, frontier/Product
  Qualification, commercial, LIVE, settlement, treasury, chain, Bittensor,
  weight, or emission authority exists.
- [ ] Build a fresh zero-dependency wheel, install it with `--no-deps` outside
  the source tree, and prove isolated import exposes only the exact A11 API
  without loading forbidden optional/later-wave modules.
- [ ] Pass the canonical focused suite at
  `pytest tests/cpu/test_observability.py -q`.
- [ ] Pass the complete default CPU regression without treating it as A11
  implementation evidence beyond the new focused contract.
- [ ] Pass strict Ruff and Black on later changed Python/test paths and the
  repository no-new-debt quality gate.
- [ ] Leave A12 separately owned and `todo`; create no `tests/invariants/`,
  pytest invariant marker, workflow/CI change, quality-baseline change, Wave-A
  closeout, or launch claim.

## Must not

Do not implement A11 under this documentation task. Do not mark A11
`in_progress` or `done`; check any criterion; modify `.agent/WAVE.md`; create
the package or test; modify Python, tests, fixtures, dependencies, packaging,
workflows, CI, or quality baselines; instrument A5–A10; add a production sink;
or begin A12.

## Future focused command

~~~text
pytest tests/cpu/test_observability.py -q
~~~

The file and command are future implementation evidence only. They do not
exist or run as A11 evidence in this documentation candidate.
