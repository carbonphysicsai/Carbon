# Carbon Build-Out Constitutional Overlay

**Status:** OWNER-CANONICAL migration guard for current `Build_Out.md` v1.4.  
**Purpose:** preserve the validity of A0–A7 and the active A8–A12 plan while preventing current sequencing language from reintroducing scientific/economic assumptions superseded by the integrated constitution.  
**Authority:** `Build_Out.md` remains detailed sequencing authority. This overlay governs interpretation when its shorthand conflicts with `CONSTITUTION.md` or `SCIENTIFIC_REFERENCE_CANON_V4_MASTER.md`.

---

# 1. Non-rewrite rule

This overlay does **not** retroactively change completed A0–A7 code or claim those stages are production-qualified.

It establishes future-compatibility constraints:

```text
KEEP current bounded contract
→ WRAP where sufficient
→ REPAIR where semantics are stale
→ MIGRATE explicitly where authority changed
→ REPLACE only when necessary
```

No hidden architectural reimplementation is authorized by this document.

---

# 2. Completed Wave-A compatibility

## A0 — package layout

**Disposition:** KEEP.

The current package layout is infrastructure, not a scientific ontology. Future construction, frontier, treasury, private-commercial, or qualification modules may be added without renaming current compliant components for diagram aesthetics.

## A1 — CI skeleton

**Disposition:** KEEP + EXTEND.

Future tests should add constitutional invariant coverage without weakening existing CPU/default lanes.

## A2 — Strategy schema

**Disposition:** KEEP as P0 subtype.

`TrainingStrategy` remains the bounded P0 miner submission object.

Future abstraction:

```text
ModelConstructionStrategy
  └── TrainingStrategy  # P0 subtype
```

Do not broaden A2 execution freedom during A8–A12.

## A3 — Challenge registry

**Disposition:** KEEP + EXTEND prospectively.

Challenge identity and exact qualification hashes remain required.

Future scientific identities may add bindings for:

- `InstanceDistributionContract`;
- `SamplingPlan`;
- `ReferencePolicy`;
- `MeasurementContract` set;
- Score Pack Evidence Use Contract;
- frontier policy;
- product qualification linkage.

Do not weaken the existing fail-closed LIVE gate.

## A4 — seeding

**Disposition:** KEEP.

Seed/domain separation is mandatory operational secrecy, but future science must not mistake seed independence for complete semantic decontamination. Distribution, truth, measurement, and adaptive leakage controls remain separate.

## A5 — scoring engine

**Disposition:** KEEP current bounded engine; MIGRATE policy semantics prospectively.

A5 must remain a deterministic executor of registered scoring policy.

Future Score Pack doctrine requires:

```text
evidence eligibility
→ admissibility
→ estimands / measurement-use roles
→ uncertainty/strata policy
→ aggregation
→ ranking
```

The scoring engine must not own:

- frontier promotion;
- Challenge portfolio allocation;
- treasury policy;
- customer payment;
- cross-Challenge normalization;
- product qualification.

Any current `score -> Yuma/emissions` shorthand is legacy runtime transport, not the target constitutional architecture.

## A6 — card store/disclosure

**Disposition:** KEEP + EXTEND.

Internal/private vs miner/public projection remains mandatory.

Future projections may add authorized audiences:

```text
CUSTOMER
CUSTOMER_DILIGENCE
INDEPENDENT_AUDITOR
CARBON_PRIVATE
```

No new audience receives hidden exam material by default.

## A7 — fees/submission FSM

**Disposition:** KEEP.

A7 owns submission identity, current attempt state, retry/refund/cancellation, and current publication transition.

Future downstream states are separate objects:

```text
ScoreResult
→ FrontierPromotion
→ FrontierAdvanceEvent
→ SettlementObligation
→ TreasurySettlement
```

Do not insert frontier or treasury policy into the A7 submission FSM merely to reuse its state machine.

---

# 3. A8 constitutional contract

A8 is implemented, tested, reviewed, and merged only for the bounded
deterministic process-local fixture-official stub recorded in `.agent/WAVE.md`
and `.agent/DECISIONS.md`. It is not scientifically, security, network,
commercially, or production qualified and grants no LIVE, frontier, weight,
emission, or settlement authority.

The current bounded fixture path remains constitutionally acceptable only while
it preserves:

1. exact trusted composition;
2. fixture-official context only;
3. no generic mode selector;
4. deterministic synthetic execution;
5. A5 as sole score authority;
6. no A6/public publication inside the A8 service;
7. infrastructure vs strategy vs scored-result separation;
8. no miner-code execution;
9. no production runtime values;
10. mechanically non-production/non-emission capability;
11. no claim that the sandbox/reference/science is qualified.

### Compatibility with future reconstruction

A8 should be treated as the first execution/reconstruction seam, not the final architecture.

Future evolution:

```text
FixtureTrainEvalService
        ↓
qualified P0 fresh retraining / TrainEval
        ↓
registered ReconstructionProtocol
        ↓
isolated construction worker
        ↓
FastPhysicalModel + ConstructionReceipt
```

Do not implement `ConstructionProgram` in A8.

---

# 4. A9 constitutional contract

MCP remains a miner-facing research interface, not a public copy of the official exam.

Required separation:

```text
FREE / MOCK / PRACTICE
useful directional signal
never official evidence

PAID / OFFICIAL
protected exam
budgeted result disclosure
```

Prior, estimate, scaffold, mock, or light metrics never enter official scientific score.

Future Landscape outputs may inform priors/hypotheses but remain leakage-governed and non-authoritative.

---

# 5. A10 constitutional contract

A10's exact bounded contract was specified and ratified by the normal merge of
PR #36. Current main implements and tests that contract only as the bounded
in-process fixture leaderboard merged normally in PR #37 at
`3b2d96e287f06c24cc4d57b46dfc418359a9e97f`, with reviewed head
`6f505d5cffd69f0c3d4d0e6d71bb91233c0ce6b1`. The documentation closeout
merged normally in PR #38 as
`404c039596b487cf2649bb1d73b80e9b49baaced` and is ancestral to current
main `4e4a66d29566a2a62a82188adddac76e6e0fb8b8`. A10's bounded Wave-A
status is `done`; A11 and A12 remain `todo`, and Wave A remains
incomplete. The closeout added no implementation or test evidence.

The undefined `max_response_utf8_bytes` accounting procedure identified by the
stopped ready-review gate is `DOCUMENTATION_LAG`. The correction defines an
exact logical successful-page UTF-8 occurrence budget, not a wire-format
contract, and changes no A10 field, architecture, public API, maturity, or owner
boundary.

## 5.1 Bounded Wave-A surface

A10 Wave A is only an in-process fixture leaderboard projection. It provides
no HTTP, REST, GraphQL, web UI, HTML, filesystem publication, network server,
chain or Bittensor access, persistence, scheduler, background refresh, or
current-time behavior. It is neither an official nor a LIVE leaderboard. An
absent official publication feed means that an official board is unavailable;
it must never be represented as an empty authoritative board.

The current implementation is explicitly non-official, non-LIVE,
non-emitting, non-frontier, non-product, non-network, and non-production.

The service and its value objects are distinct nominal fixture-only
types. `FixtureLeaderboardProvider` is a standard-library `typing.Protocol`
satisfied structurally by a trusted concrete provider; concrete providers need
not subclass it and are not subjected to exact-type or runtime-checkable
Protocol introspection. A caller-supplied string cannot relabel any surface as
an official publication type.

The sole operation is:

```text
FixtureLeaderboardService.list_entries(
    request: ListFixtureLeaderboardRequest,
) -> FixtureLeaderboardPage
```

The exact constructor is:

```text
FixtureLeaderboardService(
    provider: FixtureLeaderboardProvider,
    resource_limits: FixtureLeaderboardResourceLimits,
)
```

Both arguments are mandatory. There is no default/`None`, global, registry,
global resource policy, environment, singleton, network, or server substitute;
the exact limits value is copied and validated at construction.

The request has exactly `challenge_key` as an exact A3 `ChallengeKey`,
`page_size` as an exact built-in integer in `1..2**64-1`, and `cursor` as an
exact `LeaderboardCursor` or `None`. There is no generic
caller-selected `mode="fixture|official"`, `get(submission_id)`, global or
cross-Challenge listing, identity/hotkey/participant lookup, score-threshold
search, or timestamp search. A future official publication service requires a
separate contract, nominal types, provider/feed, and qualification path.

The exact ordered `carbon.leaderboard.__all__` tuple is:

```python
(
    "PublicationSequence",
    "LeaderboardSnapshotSequence",
    "LeaderboardCursor",
    "ListFixtureLeaderboardRequest",
    "FixtureLeaderboardCandidate",
    "FixtureLeaderboardCandidateSnapshot",
    "FixtureLeaderboardRow",
    "FixtureLeaderboardPage",
    "FixtureLeaderboardResourceLimits",
    "FixtureLeaderboardProvider",
    "FixtureLeaderboardService",
    "LeaderboardError",
    "LeaderboardRequestError",
    "LeaderboardResourceError",
    "LeaderboardUnavailableError",
    "LeaderboardIntegrationError",
)
```

No alias, generic service/provider type, official type, store, serializer, or
extra error is exported.

## 5.2 Provider-owned publication projection

Trusted composition injects a concrete structural implementation of the A10
`FixtureLeaderboardProvider` Protocol with the exact seam:

```text
FixtureLeaderboardProvider.get_snapshot(
    challenge_key: ChallengeKey,
    snapshot_sequence: LeaderboardSnapshotSequence | None,
) -> FixtureLeaderboardCandidateSnapshot | None
```

Exact `None` is the sole normal unavailable return. For a first-page call it
means there is no current retained fixture snapshot; for a continuation it
means the exact cursor-bound snapshot is absent or stale. Both map to the fixed
unavailable error. An exact snapshot, including one with zero candidates, is
available. A missing/call-incompatible method and a non-`None` malformed/wrong
return map to the fixed integration error. Every ordinary exception `error`
raised by provider-controlled behavior for which
`isinstance(error, Exception)` is true, including one encountered during a
hostile descriptor/hook, invocation, or access to provider-controlled values
during result validation, maps to one new fixed integration error.

A provider must not pass a public A10 error through the service boundary.
Because `LeaderboardRequestError`, `LeaderboardResourceError`,
`LeaderboardUnavailableError`, and `LeaderboardIntegrationError` inherit from
`Exception`, a provider-raised instance of any of them is translated into one
new fixed `LeaderboardIntegrationError` without passthrough or chaining. The
translation exposes no provider text, value, payload, cause, context, or partial
response.
A10-created public failures retain their exact existing mappings; this
provider-origin rule does not reclassify them.

A `BaseException` value that is not an `Exception` instance propagates
unchanged. A10 never catches or translates `KeyboardInterrupt`, `SystemExit`,
or `GeneratorExit` and must not use `except BaseException` around provider
method lookup, invocation, result validation, or the top-level public error
translation boundary. A hostile descriptor or hook raising such a value also
propagates unchanged. Once acquired, the concurrency permit is released in
`finally` after success, public failure, translated ordinary `Exception`, and
propagated non-`Exception` `BaseException`.

The provider, not A10, selects published candidates; excludes unpublished,
cancelled, withdrawn, superseded, stale, and infrastructure-incomplete
records; consults A3 fixture eligibility; copies only authorized A5/A6/A7
facts; assigns fixture publication and snapshot sequences; and retains the
exact bounded snapshots required by active cursors. A10 must not inspect or
enumerate A5 `InternalResult`, A6 `CardStore` or private records, A7 private
store or records, A8 private execution outcomes, or A9 priors, estimates,
scaffolds, mock outputs, or result feedback.

The provider-only candidate projection contains exactly:

- the exact A7 `SubmissionId`;
- the exact bounded A6 `result_id` value;
- the exact A3 `ChallengeKey`;
- the exact A6 public `scoring_pack_hash`;
- the exact A5 `ScoreStatus`;
- the exact finite A5/A6 `overall_score`;
- exact `mandatory_gates_passed`, `fixture_origin`, and
  `eligible_for_emission` Booleans; and
- the provider-owned nominal non-negative `PublicationSequence`.

The exact candidate snapshot contains one exact `ChallengeKey`, one exact
canonical tagged SHA-256 `scoring_pack_hash`, one exact
`LeaderboardSnapshotSequence`, and one exact tuple of candidates that may be
empty. Integration copying reconstructs `ChallengeKey` and `SubmissionId` with
their public constructors, validates `result_id` with `validate_version`,
validates the hash with `is_sha256_digest`, and requires exact `ScoreStatus`.
A10 duplicates none of those owner grammars.

`submission_id` and `result_id` are integration-only values. They never cross
into a row, page, cursor, error, representation, or other public projection.
The candidate is not a second submission identity/lifecycle, scoring engine,
card schema, or publication store.

## 5.3 Eligibility, score, and ordering

A candidate may rank only when its status is exactly `ScoreStatus.SCORED`, all
mandatory gates passed, its score is an exact finite built-in float in
`[0.0, 1.0]`, and, when the score equals zero,
`math.copysign(1.0, overall_score) == 1.0`; `fixture_origin is True`,
`eligible_for_emission is False`, and
its Challenge and scoring-pack bindings exactly match the requested snapshot.
Within the snapshot, `SubmissionId`, `result_id`, and `PublicationSequence`
must each be unique. Any duplicate, mixed Challenge, mixed scoring-pack hash,
or otherwise malformed provider output fails the whole snapshot; no partial
page survives.

`MANDATORY_GATE_FAILED`, `PACK_NOT_READY`, unpublished, cancelled, withdrawn,
superseded, stale, infrastructure-incomplete, mock, prior, estimate, or
scaffold values are excluded. A mandatory-gate failure must not become an
ordinary ranked score of zero. Fees, payments, sponsor value, and customer
value are never eligibility or ordering inputs. No current result is eligible
for an official board.

Negative zero is malformed provider output. A10 rejects `-0.0` as an
integration failure and never normalizes it to `+0.0`.

A5 remains the sole scoring authority. A10 consumes the exact provider-copied
score and scoring-pack hash and never recomputes, normalizes, aggregates,
rescales, rounds, quantizes, predicts, or estimates a score. Fixture scores may
retain exact precision; official precision, cadence, and adaptive-query
controls remain deferred.

Rows order by `overall_score` descending. Exact float equality creates a tie;
tied rows share competition rank (`1, 1, 3`) and are ordered by
`PublicationSequence` ascending without changing rank. There is one row per
provider-approved published submission. The complete bounded snapshot is
validated, duplicate-checked, sorted, and ranked before any page is sliced, so
rank stays stable across pages and page-size changes. No best-per-requester/hotkey,
participant aggregation, decay, win rate, submission count, rank delta,
improvement history, or fee-based ordering exists. Retry, republication,
withdrawal, and supersession selection remain provider-owned.

## 5.4 Positive public allow-list

The immutable row allow-list is exactly:

```text
rank
challenge_key: exact ChallengeKey
scoring_pack_hash
overall_score
mandatory_gates_passed
publication_sequence
fixture_origin
eligible_for_emission
```

The page contains only `schema_version="1.0"`, exact `ChallengeKey`, exact
scoring-pack hash, exact `LeaderboardSnapshotSequence`, immutable row tuple,
next cursor or `None`, `fixture_origin=True`, and
`eligible_for_emission=False`. It exposes no total row count.

An available snapshot with zero candidates returns a successful page that
preserves its exact Challenge, hash, and snapshot sequence, with `rows=()` and
`next_cursor=None`. Provider `None` remains unavailable and is not an empty
snapshot.

Rows and pages omit requester, hotkey, wallet, public/anonymized participant
identity, `SubmissionId`, `result_id`, timestamp, component scores, gate IDs or
counts, optional-gate outcomes, failure tags, private diagnostics, margins,
stress values, fee/payment data, rank delta, improvement history, submission
count, win rate, data-source labels, and provider metadata.
`RequesterIdentity` remains an upstream structural requester binding, not
authentication proof or a public hotkey. Wave A exposes no participant field
and performs no anonymization; no anonymization key, stability/rotation period,
or cross-Challenge correlation policy is invented.

## 5.5 Time, cursors, snapshots, and resources

Provider-owned `PublicationSequence` and `LeaderboardSnapshotSequence` are
nominal values with exact fields
`PublicationSequence(value: exact built-in int in 0..2**64-1)` and
`LeaderboardSnapshotSequence(value: exact built-in int in 0..2**64-1)`; bool
and subclasses are rejected. They are monotonic only within one exact fixture
Challenge publication stream. They carry no wall-clock, chain-height,
finality, A7-lifecycle, or settlement meaning, and A10 never generates them.
A10 exposes no timestamp and accesses no current time.

`LeaderboardCursor(value: exact built-in ASCII str)` has that one public field
and is opaque and bounded to callers. Its private logical payload contains
exactly
`schema_version="1.0"`, `board_kind="fixture_leaderboard"`, exact
`ChallengeKey`, exact canonical tagged SHA-256 `scoring_pack_hash`, exact
`LeaderboardSnapshotSequence`, and absolute `next_offset` as an exact built-in
integer in `0..2**64-1`. It contains no IDs, requester/identity, seed, draw,
context, private pack material, timestamp, path, or provider object. The
provider retains bounded in-process fixture snapshots; the service owns no
durable cache, database, filesystem store, expiry clock, or refresh loop. A
missing and a stale cursor snapshot map to the same unavailable result.

A continuation may vary an otherwise valid `page_size` because that value is
not cursor-bound; it cannot change the snapshot, order, tie relation, or rank.
A cursor is emitted only when its next offset is strictly before the snapshot
end, never at or beyond it. The public cursor exposes no decoded mapping and no
generic mode/official discriminator.

`FixtureLeaderboardResourceLimits` contains exactly the six required,
non-defaulted fields `max_page_size`, `max_snapshot_rows`,
`max_cursor_utf8_bytes`, `max_string_utf8_bytes`,
`max_response_utf8_bytes`, and `max_concurrent_calls`. Each is an exact
built-in integer in `1..2**64-1`; bool and subclasses are rejected. This
contract ratifies no default, `None`, global/registry/environment policy, or
production numeric value.

`max_response_utf8_bytes` is the exact logical public-response UTF-8 occurrence
budget for a candidate successful `FixtureLeaderboardPage`. It is evaluated
only after complete validation, ordering, competition ranking, pagination, and
optional cursor construction, but before any page, row tuple, or cursor is
released. It is not Python heap size, object size, `repr` length, JSON size,
field-name size, serialized wire size, HTTP response size, transport framing,
or a future network protocol. The exact formula is:

```text
response_utf8_bytes(page) =
    utf8(page.schema_version)
  + utf8(page.challenge_key.challenge_id)
  + utf8(page.challenge_key.version)
  + utf8(page.scoring_pack_hash)
  + sum(
        utf8(row.challenge_key.challenge_id)
      + utf8(row.challenge_key.version)
      + utf8(row.scoring_pack_hash)
      for row in page.rows
    )
  + (
        utf8(page.next_cursor.value)
        if page.next_cursor is not None
        else 0
    )

utf8(value) = len(value.encode("utf-8"))
```

The meter charges exactly those public string occurrences. It traverses the
candidate page in exact declared page-field order, `page.rows` in final tuple
order, and each row in exact declared row-field order. Equal strings are
charged once per public field occurrence; shared object identity and string
interning never deduplicate the charge. Every chargeable value is already
required to be an exact built-in ASCII string. After exact ASCII validation,
the implementation may use `len(value)` because each ASCII code point is one
UTF-8 byte.

Every chargeable string occurrence other than the optional cursor separately
satisfies `max_string_utf8_bytes` before entering the total. When `next_cursor`
is present, its exact emitted ASCII value must separately satisfy both
`max_cursor_utf8_bytes` and `max_string_utf8_bytes` and is then charged exactly
once. An incoming request cursor is not a response occurrence. The decoded
private logical cursor fields are not charged again. The incoming cursor
remains subject to the existing request and cursor validation and limits.

The meter does not charge field names; nominal class/type names; tuple or
container structure; hypothetical serialization delimiters or punctuation;
rank, snapshot-sequence, publication-sequence, or cursor-offset integers except
as an offset is already encoded in `next_cursor.value`; `overall_score` floats;
Boolean fields; `None`; Python object overhead; `repr` or `str` output;
provider-only `SubmissionId` or `result_id`; private candidate fields; private
cursor payload fields separately; private provider objects; or hidden/forbidden
values. A syntactically malformed, subclassed, or non-ASCII provider-derived
value is an integration failure under the existing hostile-provider rules and
is never normalized for metering.

A candidate page is permitted when `response_utf8_bytes(page)` is less than or
equal to `max_response_utf8_bytes`. A total greater than the limit raises the
exact fixed `LeaderboardResourceError` before any success value escapes; no
partial page survives. Fixed public error codes and messages are constants,
not candidate successful pages, and are excluded from this meter. An available
empty page still charges `schema_version`, the page Challenge ID/version, and
the page scoring-pack hash, but no row string or cursor. Exact-at-limit
succeeds; one-byte-over fails. A resource failure never recursively constructs
another metered success response.

If a separately ratified future schema adds a public string field, that
ratification must explicitly update this formula before implementation. No
field enters the meter through reflection, generic serialization, dataclass
conversion, object introspection, or default-public behavior. This closed
occurrence-sum rule follows the bounded A9 logical-response-meter principle
without copying A9's larger graph/node model or adding an A9 dependency.

## 5.6 Fail-closed boundary

The fixed public hierarchy is:

```text
LeaderboardError(Exception)

LeaderboardRequestError(LeaderboardError)
    leaderboard.request.invalid
    Leaderboard request is invalid.

LeaderboardResourceError(LeaderboardError)
    leaderboard.resource.exhausted
    Leaderboard resource limit was exceeded.

LeaderboardUnavailableError(LeaderboardError)
    leaderboard.fixture.unavailable
    Fixture leaderboard is unavailable.

LeaderboardIntegrationError(LeaderboardError)
    leaderboard.integration.failed
    Leaderboard provider response is invalid.
```

Each of the four concrete public errors is a direct `LeaderboardError`
subclass; there is no intermediate error class.

Errors use only those fixed codes/messages, accept no diagnostic payload, echo
no caller/provider value, never invoke hostile `repr`/`str`, suppress cause and
context chaining, and expose no not-found or other existence oracle. Absent,
stale, unpublished, and ineligible fixture-provider state reported without a
snapshot collapses to the same unavailable error. If a provider returns a
purported candidate in any such state, the snapshot is malformed and fails the
complete operation as an integration error; A10 never silently filters it.
`response_utf8_bytes(page) > max_response_utf8_bytes` is the fixed resource
error and fails before any page escapes. Fixed public errors are excluded from
successful-page metering.

Exact-type and subclass rejection applies to ChallengeKey, sequences, request,
cursor, snapshot, candidate, row, page, resource limits, and nested fields; it
does not require the trusted concrete provider to subclass or be the Protocol.
A10 performs no runtime-checkable provider introspection. Missing methods,
call-incompatible methods, and malformed returns are integration failures.
Hostile descriptors/hooks and provider calls map to integration when they raise
an ordinary `Exception`; a non-`Exception` `BaseException` propagates unchanged
after `finally` releases the permit. Provider output is hostile until validated,
and all accepted values are copied into immutable A10-owned projections with
mutation isolation. Generic
serialization of A5, A6, A7, or provider objects is forbidden. Rows, pages,
cursors, errors, caches, and representations must not leak seeds, draws,
roles, domains, contexts, entropy, hidden pack material, margins, stress,
diagnostics, fees, paths, private timestamps, or hidden identities.

The current implementation is exactly:

```text
carbon/leaderboard/
    __init__.py
    model.py
    providers.py
    service.py
```

Its exact non-standard-library imports are:

```python
from carbon.registry import (
    ChallengeKey,
    is_sha256_digest,
    validate_version,
)
from carbon.scoring import ScoreStatus
from carbon.fees import SubmissionId
```

It does not import A5 `InternalResult`/`ScoreEngine`, use A6 `EvaluationCard`
as input, import A6/A7 private stores or records, import A8/A9 result
or service models, Landscape, neurons, emissions, weights, chain, Bittensor,
optional scientific dependencies, web/HTML frameworks, filesystem,
environment, or current-time modules. The implementation preserves zero
mandatory package dependencies and supports installed-wheel, outside-tree
imports. Canonical focused tests live only at
`tests/cpu/test_leaderboard.py`; the merged suite covers
the exact Provider `None`/empty-snapshot distinction; RuntimeError and
provider-raised public-A10-error translation to a new exact integration error
without message/cause/context leakage; unchanged A10-created public-error
mappings; unchanged KeyboardInterrupt/SystemExit propagation and unchanged
GeneratorExit propagation where practical; capacity release after translated
`Exception` and propagated non-`Exception` `BaseException`; a source guard
forbidding `except BaseException`; Protocol versus concrete implementation;
constructor, resource fields, schema literals, ordered exports, public validator
reuse, u64 bounds, canonical zero, whole-snapshot ranking before slicing, and
continuation page-size variation in addition to the existing fail-closed matrix.
It also locks the exact `response_utf8_bytes(page)` formula and explicit
chargeable/uncharged source manifest; declared page-field, final row-tuple, and
declared row-field traversal order; per-occurrence charging of repeated equal or
identity-shared strings; per-string and dual cursor bounds; exactly-once emitted
cursor charging without private-payload duplication; incoming-cursor exclusion;
empty-page accounting; exact-at-limit success; one-byte-over resource failure;
fixed-error exclusion; and no partial response. The accounting path must use no
`repr`, generic serializer, dataclass dump, JSON, HTTP, REST, GraphQL,
wire-format, or network dependency.

## 5.7 Maturity ceiling and deferrals

```text
A10 SPECIFIED / RATIFIED: YES
A10 IMPLEMENTED: YES on current main only for the exact bounded in-process fixture leaderboard
A10 TESTED: YES only for the exact recorded CPU, hostile-input, resource, concurrency, leakage, dependency, import, wheel, and quality engineering scope, including all reviewed repairs
A10 SCIENTIFICALLY_QUALIFIED: NO
A10 SECURITY_QUALIFIED: NO
A10 NETWORK_QUALIFIED: NO
A10 COMMERCIALLY_VALIDATED: NO
A10 PRODUCTION_QUALIFIED: NO
A10 WAVE STATUS: done for the bounded fixture scope after the reviewed
documentation closeout merged normally in PR #38 as
404c039596b487cf2649bb1d73b80e9b49baaced
A11: todo
A12: todo
```

Production publication feed, official/LIVE leaderboard, public identity,
anonymization, timestamps, official score precision/cadence/adaptive-query
policy, frontier nomination or promotion, `FrontierRecord`,
`FrontierAdvanceEvent`, Product Qualification, commercial rank, settlement,
chain, weights, emissions, A11 logging/metrics, and A12 aggregate invariants
remain explicitly deferred. Production remains fail closed.

Do not conflate:

```text
fixture leaderboard rank
with
official publication
with
FrontierRecord or FrontierAdvanceEvent
with
Product Qualification
with
commercial ranking or economic entitlement
```

A later frontier-promotion layer may use separately qualified ordinary scores
as nomination evidence, but this fixture projection creates no frontier,
product, commercial, network, settlement, weight, or emission authority.

---

# 6. A11 constitutional contract

PR #39 normally merged the exact bounded A11-R1 through A11-R17 contract as
current-main commit `4e4a66d29566a2a62a82188adddac76e6e0fb8b8`.
Those decisions are `SPECIFIED / RATIFIED`; they remain recorded below as the
historical contract. Current main still contains no A11 implementation or
focused A11 test, leaves A11 `todo`, does not begin A12, and does not activate
Wave B.

Draft implementation PR #46 is blocked by
`P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS`. Its correction for the earlier
`P1_GENERIC_DATACLASS_SERIALIZATION_BYPASS` does not repair the fact that its
sink seam carries shared canonical A11/A5/A7 enum singletons. A11-R18 below is
a documentation-only owner-decision candidate for an immutable A11-owned sink
snapshot boundary. It is not ratified until the exact amendment is
independently reviewed, explicitly human-authorized, and normally merged.

## A11-R1 — Exact owner paths and module ownership

The sole future A11 semantic and implementation owner is:

```text
carbon/observability/
    __init__.py
    model.py
    providers.py
    service.py
```

Canonical focused tests belong only at
`tests/cpu/test_observability.py`. The documentation candidate creates
none of these paths.

Exact module ownership is:

- `model.py` owns `EventKind`, `MetricKind`,
  `DurationStage`, `BoundaryErrorKind`,
  `ObservabilityEvent`, `BoundaryErrorEvent`,
  `ObservabilityResourceLimits`, the four A11 errors, and private
  exact-copy/validation helpers only;
- `providers.py` owns `StructuredEventSink` and `MetricSink`
  Protocols, with no concrete, default, or global sink;
- `service.py` owns `ObservabilityService` and private shared-capacity
  accounting, same-service reentrancy accounting, sink
  lookup/invocation/return validation, and `Exception`/`BaseException`
  translation only, with no owner instrumentation; and
- `__init__.py` owns only the exact fourteen-name re-export tuple, with
  no private helper or owner-type re-export.

A0's importable `carbon/logging_utils` package remains an unchanged inert
compatibility marker. Its prospective A11 semantic ownership is REPLACED by
`carbon/observability`, while the package itself is KEPT without a
wrapper, alias, re-export, sink behavior, or alternate A11 surface.
`carbon/audit` remains reserved for evaluation receipts and authorized
re-execution. Root `carbon` exports remain unchanged.

## A11-R2 — Exact nominal surface, enums, values, and limits

The exact ordered `carbon.observability.__all__` tuple is:

```python
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
```

Exactly fourteen names are exported. No A5, A7, A9, or A10 owner type is
re-exported.

The four enums have exact direct `str, Enum` inheritance and these exact
declaration orders, names, and literal values:

```python
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
```

There are no aliases, `auto()` values, integer values, alternative
lowercase values, or extra members. Future tests must prove exact direct
inheritance, declaration order, names, literals, and absence of aliases.

`ObservabilityEvent` is frozen, slotted, representation-safe, and has
exactly these fields in this order:

```text
kind: exact EventKind
submission_id: exact A7 SubmissionId
submission_state: exact A7 SubmissionState
score_status: exact A5 ScoreStatus | None
```

`BoundaryErrorEvent` is frozen, slotted, representation-safe, and has
exactly one field:

```text
error_kind: exact BoundaryErrorKind
```

`ObservabilityResourceLimits` is frozen, slotted,
representation-safe, and has exactly one required field:

```text
max_concurrent_calls: exact built-in int in 1..2**64-1
```

Exact types reject subclasses, forged enum members, booleans-as-integers, and
coercible or lookalike values. These nominal values expose no generic
serialization, copy, or deepcopy path and never invoke caller-controlled
`repr` or `str`.

## A11-R3 — Exactly three service capabilities

Construction is exactly:

```python
ObservabilityService(
    event_sink: StructuredEventSink,
    metric_sink: MetricSink,
    resource_limits: ObservabilityResourceLimits,
)
```

All arguments are mandatory. The resource value is copied and validated at
construction. There is no `None`, default, singleton, module global,
registry lookup, environment-selected backend, or production numeric default.

The only service operations are:

```python
emit_event(
    event: ObservabilityEvent | BoundaryErrorEvent,
) -> None

increment_counter(
    metric: MetricKind,
) -> None

observe_duration(
    stage: DurationStage,
    duration_ns: int,
) -> None
```

Successful calls return exact `None`. There is no fourth operation and no
generic logger, mapping, free-form message, labels, metadata, serializer,
exporter, queue, batch, retry, flush, background worker, or backend selector.

## A11-R4 — Submission-event matrix and honest provenance boundary

The only valid `ObservabilityEvent` matrix is:

| `EventKind` | exact `SubmissionState` | exact `ScoreStatus` |
|---|---|---|
| `SUBMIT` | `RECEIVED` | `None` |
| `SCORE` | `SCORED` | `SCORED` or `MANDATORY_GATE_FAILED` |
| `REJECT` | `REJECTED` | `None` |
| `FAILED_STRATEGY` | `FAILED_STRATEGY` | `None` |
| `FAILED_INFRA` | `FAILED_INFRA` | `None` |

Every other kind/state/status combination is invalid. `PUBLISHED`,
`CANCELLED`, `VALIDATED`, `QUEUED`, `RUNNING`,
retryable infrastructure, `PACK_NOT_READY`, forged or cross-enum
statuses, and unsupported future categories are rejected or omitted, never
remapped.

A request that fails before a safe A7 `SubmissionId` exists cannot
construct an `ObservabilityEvent`. The separate
`BoundaryErrorEvent` carries no correlation field. Trusted composition
must not represent an open duplicate or any owner action with no corresponding
record/transition as a new submission event.

The former assertion that every event projects an existing exact A7 record is:

```text
P1_UNENFORCEABLE_EVENT_PROVENANCE_CLAIM
taxonomy: DOCUMENTATION_LAG
A11 implementation defect: NO
new private lookup authorized: NO
```

`ObservabilityEvent` is only an owner-shaped, process-local operational
observation request. A11 validates exact nominal types and the closed
kind/state/status consistency matrix. It does not verify that an A7 record
exists, that the stated A7 state is the current retained state, that an owner
transition occurred, or that the values have authenticated A5/A7 provenance.
Trusted composition alone supplies the factual relationship to an owner
transition. Exact nominal values are correctness values, not authenticated
capabilities. A syntactically valid but unbound UUIDv4 has no lifecycle,
scientific, audit, receipt, public, security, settlement, or economic
authority. Production provenance and evidence remain separately deferred.

No store lookup, capability token, signature, receipt, second identity, or
additional event field is authorized.

## A11-R5 — Closed A9/A10 boundary-error projection

Trusted composition may map only these exact public A9 classes:

| Exact public A9 class | `BoundaryErrorKind` |
|---|---|
| `McpRequestError` | `MCP_REQUEST` |
| `McpResourceError` | `MCP_RESOURCE` |
| `McpToolUnavailableError` | `MCP_TOOL_UNAVAILABLE` |
| `McpChallengeUnavailableError` | `MCP_CHALLENGE_UNAVAILABLE` |
| `McpSubmissionUnavailableError` | `MCP_SUBMISSION_UNAVAILABLE` |
| `McpQueryBudgetError` | `MCP_QUERY_BUDGET` |
| `McpIntegrationError` | `MCP_INTEGRATION` |

and only these exact public A10 classes:

| Exact public A10 class | `BoundaryErrorKind` |
|---|---|
| `LeaderboardRequestError` | `LEADERBOARD_REQUEST` |
| `LeaderboardResourceError` | `LEADERBOARD_RESOURCE` |
| `LeaderboardUnavailableError` | `LEADERBOARD_UNAVAILABLE` |
| `LeaderboardIntegrationError` | `LEADERBOARD_INTEGRATION` |

Mapping is by exact public class identity, not arbitrary `.code` text.
Unknown codes, raw exceptions, base errors, subclasses, and owner payloads fail
closed and cannot construct a boundary event. Every ordinary raw provider
error must first be translated by its A9/A10 owner boundary; A11 never receives
or classifies the raw provider exception.

`BoundaryErrorEvent` contains no `SubmissionId`,
`ChallengeKey`, requester, request value, tool payload, cursor, provider,
exception object or text, message, cause, context, traceback, private field,
hidden identifier, seed/draw, arbitrary string, or mapping. Production A11
source imports no A9 or A10 module. A test-local composition harness may import
their public errors solely to prove the exact mapping.

Reference, generator, reconstruction, retry, evidence, treasury, settlement,
commercial-acceptance, and Challenge-health categories remain unrepresented
until exact public owner types and integration seams exist. Omission is not
collapse.

## A11-R6 — Metrics, durations, labels, and cardinality

The metric vocabulary is exactly `SUBMIT_COUNT`,
`SCORE_COUNT`, `REJECT_COUNT`, `FAILED_INFRA_COUNT`,
and `STAGE_DURATION_NS`. Only the first four are counter inputs, and each
accepted call means exactly one increment with no supplied delta or value.
`STAGE_DURATION_NS` is rejected by `increment_counter` and is
represented only by `observe_duration`.

Metric labels are exactly empty. Neither public metric operation nor
`MetricSink` receives a mapping, tuple of labels, keyword metadata, or
tag collection. No `SubmissionId`, Challenge identity/version,
requester, hotkey, wallet, customer, result, score, rank, cursor, provider,
exception, or arbitrary value becomes a dimension. `DurationStage` is a
closed typed argument, not an arbitrary label map. Cardinality is structurally
bounded by four counter members and two duration stages. There is no
`FAILED_STRATEGY_COUNT`, gauge, arbitrary histogram, set, decrement,
reset, dynamic name, or generic metric operation.

## A11-R7 — Exact A7 SubmissionId correlation boundary

A11 creates no correlation, trace, span, request, receipt, or result identity.
For a valid submission event it reconstructs a fresh exact public A7
`SubmissionId` through its owner constructor. The copied ID may appear
only as `ObservabilityEvent.submission_id` for internal structured
correlation; it cannot appear in a boundary-error event, metric, label, error,
free-form text, representation, generic serialization, or miner/customer/public
observability value.

Canonical UUIDv4 validation proves syntax only and supplies none of the
provenance disclaimed in A11-R4. `RequesterIdentity` never crosses the
A11 boundary and is not imported. This restriction does not revoke A7/A9's
separately owned opaque submission-ID interfaces.

## A11-R8 — Owner failure and lifecycle separation

A11 does not invent lifecycle or scientific semantics:

- `REJECT` remains exact A7 request/admission rejection, not strategy,
  scientific, or infrastructure failure;
- `FAILED_STRATEGY` remains the exact terminal A7 strategy disposition
  and accepts no ambiguous or infrastructure cause;
- `FAILED_INFRA` remains the exact terminal A7 infrastructure
  disposition and does not absorb retryable infrastructure;
- `SCORE` requires lifecycle `SCORED` while retaining exact A5
  `SCORED` versus `MANDATORY_GATE_FAILED`; and
- `PACK_NOT_READY` remains non-scientific unavailability, cannot satisfy
  lifecycle `SCORED`, and is rejected or omitted rather than relabeled.

A6 public failure tags are not widened. A8 private outcomes and causes are not
imported. Reference, generator, reconstruction, retry, settlement, treasury,
commercial-acceptance, incident, and Challenge-health meanings remain deferred
instead of being collapsed into a generic failed result.

## A11-R9 — No score, rank, or adaptive-oracle telemetry

A11 accepts or emits no raw, combined, or component score; gate; margin; stress
value; diagnostic; delta; rank or rank history; prior; estimate; scaffold;
practice/mock/light result; feedback; or query history. Exact
`ScoreStatus` is a closed disposition only. A5 remains sole scoring
authority. No event, metric, duration, error, or sink result creates scientific
evidence, an adaptive-exam oracle, Challenge-health decision, frontier event,
Product Qualification, publication authority, or economic entitlement.

## A11-R10 — Positive construction

The accepted boundary order is:

```text
exact outer-type validation
→ declared-order positive field extraction
→ exact owner/closed-enum validation
→ prohibited-data exclusion by the closed shape
→ fresh immutable A11-owned reconstruction
→ non-blocking resource/reentrancy acquisition
→ at most one corresponding sink access
```

There is no arbitrary mapping, iterable, descriptor, reflection, object-graph
or cycle traversal, alias retention, generic serializer, recursive sanitizer,
or serialize-then-redact path. A11 never invokes hostile `repr` or
`str`. Because there is no allow-listed free-form textual field, CR/LF,
Unicode, oversized-text, secret-pattern, and arbitrary-message attacks are
eliminated structurally; no pattern-redaction engine is shipped. Unsafe
material is rejected, not normalized, truncated, hashed, anonymized, or
transformed.

## A11-R11 — Forbidden material

Events, metrics, durations, errors, representations, sink arguments, and
retained aliases contain no:

- official/master/derived seed, draw ID, role, domain, context, entropy, nonce,
  commitment, preimage, or hidden pack;
- Strategy, parameter, weight, checkpoint, or artifact;
- requester, hotkey, wallet, customer, participant, credential,
  authentication, fee, payment, reward, or identity payload;
- result, receipt, cursor, publication sequence, provider metadata, prior,
  estimate, scaffold, practice/mock/light feedback, or query history;
- score, component, gate, margin, stress value, diagnostic, rank, or rank
  history; or
- exception text/object, traceback, path, command, environment value,
  runtime-configuration value, or arbitrary diagnostic.

No sink/error fallback diagnostic may reintroduce forbidden material.

## A11-R12 — Duration and clock boundary

Duration stages are exactly `DurationStage.SUBMIT` and
`DurationStage.SCORE`. `duration_ns` is an exact built-in
`int` in `0..2**64-1`; booleans, subclasses, coercible values,
negative integers, floats, and overflow reject. A11 reads no wall, monotonic,
date, timezone, sleep, deadline, or current-time source and emits no timestamp.
Caller-supplied duration is descriptive only and cannot change a domain result
or authority decision. Additional stages require a later contract change.

## A11-R13 — Exact Protocol seams and no production sink

The standard-library Protocols are exactly:

```python
class StructuredEventSink(Protocol):
    def emit_event(
        self,
        event: ObservabilityEvent | BoundaryErrorEvent,
        /,
    ) -> None: ...


class MetricSink(Protocol):
    def increment_counter(
        self,
        metric: MetricKind,
        /,
    ) -> None: ...

    def observe_duration(
        self,
        stage: DurationStage,
        duration_ns: int,
        /,
    ) -> None: ...
```

Trusted concrete sinks are structural. They need not subclass a Protocol and
are not checked through `runtime_checkable`, exact-type gates, or runtime
Protocol introspection. No concrete sink, default/global sink, no-op default,
`logging.Logger` wrapper, or production exporter is exported.

## A11-R14 — Sink failure, resources, reentrancy, and domain-result preservation

Each public operation makes at most one corresponding synchronous sink call
and requires exact `None` as its return. Missing or call-incompatible
methods, non-`None` returns, hostile descriptor/hook ordinary
exceptions, invocation ordinary exceptions, and sink-raised public A11 errors
map to one fresh fixed integration error. Translation exposes no original
exception, value, text, payload, partial value, cause, or context chain, calls
no hostile `repr`/`str`, and invokes no fallback logger.
Non-`Exception` `BaseException` values, including
`KeyboardInterrupt`, `SystemExit`, and `GeneratorExit`,
propagate unchanged.

One shared per-service non-blocking `max_concurrent_calls` policy covers
all three operations. Exact capacity exhaustion and same-service sink
reentrancy reject before another sink access, even when general capacity
remains. No ordinary mutex is held across the sink. Capacity is released in
`finally` after success, A11-created error, translated ordinary
`Exception`, and propagated non-`Exception`
`BaseException`.

There is no batch, queue, retry, fallback, worker, thread, async task,
background work, timeout/preemption, suppression or reordering of domain
actions, durability, or exactly-once claim. A blocking sink consumes only its
finite capacity and may block its caller. Trusted composition calls telemetry
outside owner locks and only after any domain result that must survive has been
determined. Telemetry failure cannot change that scientific, lifecycle,
publication, or economic result.

## A11-R15 — Exact A11 errors

The hierarchy and fixed values are exactly:

```text
ObservabilityError(Exception)

ObservabilityRequestError
  code: observability.request.invalid
  message: Observability request is invalid.

ObservabilityResourceError
  code: observability.resource.exhausted
  message: Observability resource limit was exceeded.

ObservabilityIntegrationError
  code: observability.integration.failed
  message: Observability sink failed.
```

There is no fourth public error. Errors are immutable, fixed, non-echoing,
representation-safe, unchained, and non-serializable; they accept no diagnostic
constructor argument. The three concrete errors are direct
`ObservabilityError` subclasses. Malformed mandatory construction or caller
values map to request error, acquired-capacity/reentrancy exhaustion maps to
resource error, and sink failure maps to integration error.

## A11-R16 — Dependency direction and initial non-integration

The exact first-implementation dependency direction is:

```text
model.py
  → Python standard library
  → exact public SubmissionId and SubmissionState from carbon.fees
  → exact public ScoreStatus from carbon.scoring

providers.py
  → Python standard-library typing
  → A11 model types only

service.py
  → Python standard library
  → A11 model types
  → A11 provider Protocols

__init__.py
  → explicit re-exports from model, providers, and service
```

There is no circular import; production A11 imports no A6, A8, A9, or A10
module, A5 engine/result, A7 service/private record/store/fee implementation,
`carbon.logging_utils`, `carbon.audit`, evidence/receipt,
filesystem/network/environment, optional exporter, Landscape, neuron,
Bittensor, chain, settlement, weight, or emission surface. No owner package
imports `carbon.observability` in the first implementation.

The semantic dependencies remain A5 ownership of `ScoreStatus`, A6
public failure-tag stability, A7 ownership of `SubmissionId` and
lifecycle meaning, A8 private-outcome exclusion, and the closed A9/A10 public
error mapping in A11-R5. Initial A11 modifies or instruments no A5–A10 owner.
Direct instrumentation is a later composition task requiring its own exact,
non-circular, domain-result-preserving hook review.

The required public package-root imports may transitively initialize existing
owner modules: `carbon.fees` initializes its current service dependencies, and
`carbon.scoring` initializes its current engine/pack exports. The enforceable
rule is therefore no direct A11 source import or call of those forbidden owner
internals; tests must not assert impossible absence of every transitive module
from `sys.modules`. Production A11 remains free of A9/A10 imports and loads
caused by A11 itself.

## A11-R17 — A12 separation, maturity, and authority ceiling

Production exporters, persistence/retention, dashboards, alert thresholds,
authentication, public APIs, incident systems, current timestamps, additional
vocabulary/stages, Challenge-health or adaptive-query authority,
evidence/receipt lifecycle, official/LIVE operation, frontier/Product
Qualification, commercial acceptance, treasury/settlement, chain, Bittensor,
weights, and emissions remain separately owned, deferred, and fail closed.

```text
A11 SPECIFIED / RATIFIED:
YES for A11-R1 through A11-R17, normally merged in PR #39

A11-R18:
SPECIFIED as the exact documentation candidate below; RATIFIED only after
independent review, explicit human authorization, and normal merge

A11 IMPLEMENTED: NO on current main
A11 TESTED: NO on current main
A11 SCIENTIFICALLY_QUALIFIED: NO
A11 SECURITY_QUALIFIED: NO
A11 NETWORK_QUALIFIED: NO
A11 COMMERCIALLY_VALIDATED: NO
A11 PRODUCTION_QUALIFIED: NO
A11 WAVE STATUS: todo on current main
PR #46: draft, blocked, and non-authoritative
A12: todo
Wave A: incomplete
Wave B: candidate planning only; inactive
```

A11 creates no implementation or focused test, `tests/invariants/`,
pytest invariant marker, dependency, packaging, workflow/CI,
quality-baseline, A12 artifact/status change, Wave-A closeout, Wave B
activation, or launch claim.

## A11-R18 — Immutable A11-owned sink snapshot boundary

This amendment selects **Option A: immutable A11-owned sink snapshots**. The
finding that requires the amendment is:

```text
P1_MUTABLE_ENUM_SINGLETON_BOUNDARY_BYPASS:
CONFIRMED

implementation defect: YES
current main defect: NO
contract-preserving implementation under the current owner types: NO
classification: NEW_OWNER_DECISION_REQUIRED
```

Ordinary direct `str, Enum` members are process-wide mutable singletons. The
R1-R17 request model requires exact canonical A11/A5/A7 enum members, while
its sink-facing isolation language requires every sink argument to be a fresh
immutable A11-owned value whose mutation cannot affect caller, owner,
retained, concurrent, or later A11 state. Passing the canonical members cannot
satisfy both requirements. Merely detecting later corruption, deleting
unexpected attributes, sanitizing and restoring global enum state, trusting a
sink, or holding a process-global lock across arbitrary sink code does not
close that boundary.

Option B, separately hardening the A5/A7 owner enums, requires an owner-reviewed
migration and is outside A11. Option C, narrowing sink-mutation isolation,
weakens the security boundary and is not authorized. R18 therefore introduces
fresh primitive-only sink snapshots without changing A5/A7 owner source or the
public service-request API.

The corrected R18 scope does not select Option C: Option C would permit shared
owner/request/enum state or weaken mutation isolation of the supplied snapshot
instance and its declared fields. Deliberate class/module/global mutation
requires a stronger isolation boundary and is outside the trusted in-process
sink contract.

### R18 status and exact supersession

The corrective review of parent `9de896dea92e5378d99ef205cd21a29ef9f57fd3`
records `P1_SNAPSHOT_TYPE_MUTATION_SCOPE_OVERCLAIM` as a `CONTRACT_DEFECT`
(`current main defect: NO`; `PR #47 candidate defect at that parent: YES`) and
`P2_PUBLIC_SNAPSHOT_CONSTRUCTION_AMBIGUITY` as a
`CONTRACT_PRECISION_DEFECT`.

A11-R1 through A11-R17 remain ratified historical decisions. Only after the
exact R18 candidate is independently reviewed, explicitly human-authorized,
and normally merged does the effective contract become A11-R1 through A11-R18.
At that point R18 supersedes only the sink-facing portions of A11-R1, A11-R2,
A11-R3, A11-R10, A11-R13, A11-R14, and A11-R16. All other behavior, matrices,
failure separation, resource limits, leakage prohibitions, dependency
boundaries, and maturity/authority ceilings in R1-R17 remain in force.

The public service-request API remains exactly:

```python
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
```

`ObservabilityEvent`, `BoundaryErrorEvent`, `MetricKind`, and `DurationStage`
are validated request values only. They are not sink arguments and are not
sink-safe snapshots after R18. Public request construction continues to accept
exact canonical A11/A5/A7 enums and continues to prove no record existence,
owner transition, provenance, authentication, evidence, or authority.

### Future public snapshot values

R18 adds these four future public A11-owned nominal types:

```python
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
```

`SubmissionEventSnapshot` has exactly the ordered fields `kind`,
`submission_id`, `submission_state`, and `score_status`:

- `kind` is an exact built-in `str` selected from `SUBMIT`, `SCORE`, `REJECT`,
  `FAILED_STRATEGY`, and `FAILED_INFRA`;
- `submission_id` is an exact built-in 36-character ASCII `str` in canonical
  UUIDv4 spelling, after validation through a fresh public A7 `SubmissionId`
  reconstruction, and remains internal correlation only;
- `submission_state` is an exact built-in `str` selected from `RECEIVED`,
  `SCORED`, `REJECTED`, `FAILED_STRATEGY`, and `FAILED_INFRA`; and
- `score_status` is `None` or the exact built-in `str` `SCORED` or
  `MANDATORY_GATE_FAILED`.

The exact existing A11-R4 event matrix remains authoritative. The snapshot
contains no `EventKind`, `SubmissionState`, `ScoreStatus`, `SubmissionId`, or
other A11/owner enum or nominal object.

`BoundaryErrorSnapshot` has exactly one field, `error_code`. It is an exact
built-in `str` selected from the existing eleven values:

```text
mcp.request.invalid
mcp.resource_limit_exceeded
mcp.tool_unavailable
mcp.challenge_unavailable
mcp.submission_unavailable
mcp.query_budget_exceeded
mcp.integration_failure
leaderboard.request.invalid
leaderboard.resource.exhausted
leaderboard.fixture.unavailable
leaderboard.integration.failed
```

It contains no `BoundaryErrorKind`, owner error, exception, payload, request
value, provider value, identity, seed, draw, or arbitrary metadata.

`CounterMetricSnapshot` has exactly one field, `metric_name`, which is an exact
built-in `str` selected from `SUBMIT_COUNT`, `SCORE_COUNT`, `REJECT_COUNT`, and
`FAILED_INFRA_COUNT`. It has no label, delta, dynamic name, boundary-error
counter, gauge, reset, or decrement.

`DurationMetricSnapshot` has exactly the ordered fields `stage` and
`duration_ns`. `stage` is an exact built-in `str`, `SUBMIT` or `SCORE`, and
`duration_ns` is an exact built-in `int` in `0..2**64-1`. It has no clock,
timestamp, label map, or arbitrary dimension.

Every snapshot must be an exact manual slotted non-dataclass nominal class and
a fresh outer object per admitted service operation. It has no instance
`__dict__`, rejects normal assignment and deletion, has a fixed safe
representation, rejects `copy.copy`, `copy.deepcopy`, and pickle, and is
rejected by `dataclasses.asdict`, `dataclasses.astuple`, and
`dataclasses.replace`. Its fields contain only exact immutable built-in `str`,
`int`, or `None` values. No mapping, iterable, descriptor, object graph, owner
object, enum member, exception, or metadata is retained.

Snapshots are authority-free and are never accepted as service requests.
Direct public construction of all four snapshot classes is allowed. Each has
exactly the displayed parameter names and order, and every displayed parameter
is required. The constructors accept only the exact built-in field types,
literal sets, canonical UUIDv4 spelling, event-matrix combinations, and integer
range stated above. They reject `bool`, field-type subclasses, coercible or
malformed values, extra positional or keyword fields, constructor re-entry,
and partially initialized values. Construction always creates an exact manual
slotted non-dataclass instance with no instance `__dict__`, a fixed safe
representation, and the assignment, deletion, copy, deepcopy, pickle, and
dataclass-operation rejections stated above. No hidden token, private-factory
requirement, alternate constructor, or subclass construction is permitted; the
service uses these same public constructors after deriving exact primitive
fields. Directly constructed snapshots prove only exact closed shape and
create no provenance, owner transition, lifecycle, scientific, audit, receipt,
public, security, settlement, or economic authority. The service rejects all
four snapshot types as request values.

### Future public surface and module ownership

After R18 is ratified and implemented, the exact ordered
`carbon.observability.__all__` tuple is:

```python
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
```

Exactly eighteen names are exported. The previous fourteen-name surface is
superseded only after R18 normally merges. No owner type, generic logger,
serializer, provider, mapper, or extra error is exported.

The effective future module ownership is:

```text
model.py
  EventKind, MetricKind, DurationStage, BoundaryErrorKind
  ObservabilityEvent, BoundaryErrorEvent, ObservabilityResourceLimits
  SubmissionEventSnapshot, BoundaryErrorSnapshot
  CounterMetricSnapshot, DurationMetricSnapshot
  ObservabilityError, ObservabilityRequestError
  ObservabilityResourceError, ObservabilityIntegrationError
  private exact request-validation and public-constructor invocation helpers only

providers.py
  StructuredEventSink, MetricSink Protocols
  no concrete, default, or global sink

service.py
  ObservabilityService
  request-to-snapshot conversion
  shared-capacity and same-service reentrancy accounting
  sink lookup/invocation/return validation and exception translation
  no owner instrumentation

__init__.py
  exact ordered eighteen-name re-export tuple only
```

### Exact future Protocol seams

```python
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
```

The Protocols remain structural and non-runtime-checkable. Concrete sinks
subclass neither Protocol. No concrete or production sink is added. These
Protocols are trusted in-process integration seams. Only trusted composition
supplies sinks at mandatory service construction; miner-controlled or service-
request input cannot choose or supply a sink implementation.

### Positive request-to-snapshot conversion

Before capacity acquisition or sink access, the future service must:

1. validate the exact outer request type;
2. validate exact canonical enum type, identity, name, and literal value;
3. validate the existing event matrix or metric/duration boundary;
4. reconstruct and validate `SubmissionId` through its public A7 constructor
   where applicable;
5. map validated semantic values to A11-module-owned hard-coded literal
   strings;
6. use the same direct public exact constructor to construct a fresh snapshot
   containing no request, owner, or enum reference;
7. acquire non-blocking capacity and reentrancy permission; and
8. make at most one corresponding sink call.

The service never passes `EventKind`, `MetricKind`, `DurationStage`,
`BoundaryErrorKind`, `SubmissionState`, `ScoreStatus`, `SubmissionId`,
`ObservabilityEvent`, or `BoundaryErrorEvent` to a sink. It never carries a
mutable enum member forward to derive a sink field, traverses or copies an
enum-member `__dict__`, or consults, copies, retains, renders, or emits a
caller-added enum attribute. Corrupted enum `_name_` or `_value_` state rejects
before capacity acquisition and sink access. Snapshot primitives come from
A11-owned fixed literal tables after exact validation. No sanitizing mutation
or snapshot-and-restore of shared enum state is permitted, and no ordinary or
process-global lock is held across sink code.

### Exact snapshot-instance mutation-isolation scope

```text
Mutation of the supplied snapshot instance and its declared primitive fields,
including normal assignment and object.__setattr__, cannot alter caller,
owner, retained, concurrent, another-service, or later A11 state.
```

Each sink receives one fresh per-call snapshot instance. A sink may use Python
escape hatches to alter that instance, but the retained instance cannot affect
another call because its declared fields are exact immutable built-in
primitives, it contains no shared mutable owner or enum reference, and A11
never reuses a snapshot object.

A11 does not defend against sink code that deliberately retrieves and mutates
the snapshot class, A11 module globals, owner classes/modules, or any other
process global.

Such class/global mutation is outside the trusted in-process sink contract and
requires process isolation or capability restriction, neither of which Wave A
implements or claims.

This exclusion does not permit A11 to pass a shared enum, owner nominal,
request object, mapping, exception, metadata, or other mutable shared instance.
Caller-added enum attributes remain excluded; no shared enum sanitize/restore
occurs; and no ordinary mutex is held across sink code. Production-sink
hardening, process isolation, plugin capability restriction, and hostile-sink
qualification remain separately deferred. A11 claims no resistance to
arbitrary malicious Python executing in the same process. `SECURITY_QUALIFIED`
and `PRODUCTION_QUALIFIED` remain `NO`.

### Dependencies, implementation evidence, and maturity

The service-request dependency remains:

```text
model.py
  → Python standard library
  → public SubmissionId and SubmissionState from carbon.fees
  → public ScoreStatus from carbon.scoring
```

Snapshot types depend only on Python built-ins and local A11 validation. No
A5/A7 owner source changes, runtime owner monkey-patching, A9/A10 production
import, owner import of `carbon.observability`, or owner-service
instrumentation is authorized.

A later repaired implementation must prove in both source-tree and installed
wheel tests that caller-added enum attributes never enter snapshots; sinks
receive no enum or `SubmissionId`; snapshot fields are exact built-in
primitives; semantic enum corruption rejects; all four direct public exact
constructors enforce their displayed required parameters and closed values;
each call receives a distinct outer snapshot; normal assignment or
`object.__setattr__` mutation of the supplied snapshot instance and its
declared primitive fields cannot affect the caller, owner enums, another
service, concurrent operations, or later calls; a retained snapshot-instance
mutation cannot affect a later call; no snapshot-and-restore global mutation
or lock across sink execution exists; deliberate snapshot-class/module/global
mutation is outside the trusted seam and is not an instance-isolation proof;
the prior dataclass/copy/pickle protections and event matrix remain intact;
the exact eighteen-name surface and revised Protocols hold; and A5/A7 owner
source, owner services, A12, and Wave B remain untouched.

This documentation amendment implements and tests nothing. PR #46 remains a
blocked draft implementation candidate; its historical engineering evidence
is not current-main A11 implementation or test authority.

```text
A11-R1 through A11-R17: RATIFIED
A11-R18: SPECIFIED as this exact candidate; RATIFIED only after independent
review, explicit human authorization, and normal merge
A11 IMPLEMENTED: NO on current main
A11 TESTED: NO on current main
A11 SCIENTIFICALLY_QUALIFIED: NO
A11 SECURITY_QUALIFIED: NO
A11 NETWORK_QUALIFIED: NO
A11 COMMERCIALLY_VALIDATED: NO
A11 PRODUCTION_QUALIFIED: NO
A11 WAVE STATUS: todo on current main
PR #46: draft, blocked, and non-authoritative
A12: todo
Wave A: incomplete
Wave B: candidate planning only; inactive
```

---

# 7. A12 constitutional contract

Wave-A invariant tests should close on current enforceable guarantees and explicitly reserve future ones.

Current required themes:

- seed secrecy;
- mock isolation;
- pin integrity;
- disclosure allow-list;
- LIVE qualification gate;
- forbidden score inputs;
- infra != science;
- deterministic fixture execution;
- placeholder/stub cannot become LIVE/production evidence;
- fees/payment do not alter score;
- A8 fixture path cannot publish emission/settlement entitlement.

Future frontier/treasury/product invariants belong to later waves once their types exist.

---

# 8. Wave B–D migration additions

When Waves B–D begin, `Build_Out.md` should be revised or supplemented to make these first-class rather than implicit:

```text
PhysicalSystemSpec
CandidateOutputContract
CandidateAssemblyContract
InstanceDistributionContract
SamplingPlan
CanonicalChallengeCase
ReferencePolicy
MeasurementContract
Validation Dossier
Score Pack / Evidence Use Contract
ParameterCatalog
ResolvedConstructionPlan
ChallengeInteractionManifest
ResearchTask
ExperimentRecord
ResearchReceipt
PriorPack
PriorPolicyBundle
PriorIndexSnapshot
PriorPublicationReceipt
PriorDisclosureLedger
PublicEstimand
```

The scientific job owns the population. The generator does not define the population merely by what it happens to sample.

The miner research surface must also distinguish public contract facts,
evidence-labeled priors, candidate-specific practice measurements, and official
evidence. Strategy parameters receive executable meaning only through a
Challenge-bound catalog and deterministic compiler. Practice and official
execution remain nominally separate. Prior, practice, scaffold, forecast, and
information-value artifacts never acquire score authority.

---

# 9. Wave E–G interpretation

Existing Build Out shorthand:

```text
E Landscape
F Specialist Bank
G Customer bounds / sponsors
```

is retained but expanded by `Agentic_Development_Master_Plan.md`.

Interpretation:

- E = evidence memory / Landscape proposal layer;
- F = exact artifact/system Product Qualification plane;
- G = commercial/private/sponsored engagement plane.

None of these may rewrite a current scientific result.

---

# 10. Economic migration rule

Any current documentation that says or implies:

```text
ScoreResult
→ directly determines permanent performance emissions
```

must be treated as **current/legacy runtime transport**, not the target economic constitution.

Target architecture:

```text
ScoreResult
→ contender nomination
→ common fresh promotion evidence where required
→ FrontierAdvanceEvent
→ SettlementObligation
→ separately governed treasury settlement
```

This target may not be implemented piecemeal inside A8–A12 without an authorized frontier/treasury wave.

---

# 11. Business migration rule

No A-ticket may absorb business logic such as:

- customer pricing;
- commercial rights;
- contract acceptance;
- sponsor invoice semantics;
- investor reporting;
- OpCo revenue accounting.

Commercial integration belongs to the later commercial plane and must reference `Business/` authority.

---

# 12. Overlay closing rule

> **A0–A7 are preserved as bounded foundations. A8–A12 should complete the P0 software skeleton without smuggling future frontier, treasury, commercial, or generalized-construction authority into the wrong layer. Future waves then migrate the architecture explicitly, one authority boundary at a time.**
