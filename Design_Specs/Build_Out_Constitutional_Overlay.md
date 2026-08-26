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

A8 remains **not implemented** until code/test/review/merge evidence exists.

The currently specified fixture path is constitutionally acceptable only if it preserves:

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
`6f505d5cffd69f0c3d4d0e6d71bb91233c0ce6b1`. Administrative closeout remains
conditional on independent review, explicit human authorization, and normal
merge of the documentation-only closeout. That closeout adds no implementation
or test evidence.

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
A10 WAVE STATUS: done only after this closeout is independently reviewed, explicitly human-authorized, and normally merged
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

Observability must support later scientific/economic separation.

Where applicable distinguish:

- candidate/scientific failure;
- reference failure;
- generator failure;
- reconstruction failure;
- infrastructure failure;
- treasury/settlement failure;
- commercial acceptance failure.

These categories must not be collapsed into one generic failed result.

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
InstanceDistributionContract
SamplingPlan
CanonicalChallengeCase
ReferencePolicy
MeasurementContract
Validation Dossier
Score Pack / Evidence Use Contract
ExperimentRecord
```

The scientific job owns the population. The generator does not define the population merely by what it happens to sample.

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
