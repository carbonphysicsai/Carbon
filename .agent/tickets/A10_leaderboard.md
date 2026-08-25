# Ticket A10 — Bounded fixture leaderboard projection (C14)

**Wave:** A
**Status:** todo
**Build_Out:** C14, interpreted through Design_Specs/Build_Out_Constitutional_Overlay.md
**Depends on:** A3, A5, A6, A7
**Plan:** .agent/plans/A10_leaderboard.md

## Goal

Implement, in a later separately authorized task, one bounded in-process
fixture leaderboard projection with a positive public allow-list. The Wave-A
surface is fixture-only, Challenge-bound, snapshot-bound, deterministic,
resource-bounded, hostile-input-safe, and structurally unable to claim official,
LIVE, frontier, product, settlement, chain, weight, or emission authority.

The future service operation is exactly:

~~~python
FixtureLeaderboardService.list_entries(
    request: ListFixtureLeaderboardRequest,
) -> FixtureLeaderboardPage
~~~

The request binds one exact A3 ChallengeKey, one exact positive built-in
page_size, and an opaque LeaderboardCursor or None.

## Required contract

- The service, candidate, snapshot, row, page, sequences, cursor, request,
  resource limits, and errors are exact nominal A10 values. The provider is a
  standard-library Protocol satisfied structurally by trusted composition, not
  an exact-type or runtime-introspection gate. There is no caller-supplied mode
  string and no official service/provider type in Wave A.
- An injected FixtureLeaderboardProvider returns an exact provider-approved
  fixture publication snapshot or exact None as the sole normal unavailability
  signal. An available snapshot may be empty. A10 never enumerates private
  A5–A9 state.
- Only exact ScoreStatus.SCORED candidates with every eligibility predicate
  satisfied may rank. Mandatory-gate failure is exclusion, never an ordinary
  score of zero.
- A5 remains sole scoring authority. A10 performs no score calculation,
  normalization, aggregation, rescaling, rounding, quantization, prediction, or
  estimation.
- Rows order by overall_score descending. Exact-float ties share competition
  rank; ranks follow 1, 1, 3. publication_sequence ascending orders tied rows
  without changing rank.
- Pagination is snapshot-stable. A public-safe opaque cursor binds the fixture
  board, exact ChallengeKey, scoring_pack_hash, snapshot sequence, and next
  offset only.
- Errors have fixed codes/messages, reveal no supplied value, use no hostile
  repr or str, expose no cause/context chain, and provide no existence oracle.
- Fixture success is not official publication. Absence of a future official
  publication feed means an official board is unavailable, not an empty
  authoritative board.

## Future implementation DoD

Every criterion below is implementation work. Documentation ratification does
not satisfy any item.

### Exact surface and nominal types

- [ ] Add only the smallest package layout: carbon/leaderboard/__init__.py,
  model.py, providers.py, and service.py.
- [ ] Export the exact ordered sixteen-name carbon.leaderboard.__all__ tuple
  ratified in A10-R2, with no alias, generic/official type, store, serializer,
  or extra error.
- [ ] Implement FixtureLeaderboardProvider as typing.Protocol, permit trusted
  concrete structural implementations without subclassing or runtime-checkable
  introspection, and reject subclasses/coercible substitutes for every exact
  nominal value and nested field instead of exact-typing the provider object.
- [ ] Expose exactly FixtureLeaderboardService.list_entries(request) and no
  get-by-submission, global list, cross-Challenge list, identity filter,
  hotkey/participant lookup, score-threshold search, or timestamp search.
- [ ] Require ListFixtureLeaderboardRequest to contain exactly challenge_key as
  exact ChallengeKey, page_size as exact built-in int in 1..2**64-1, and cursor
  as exact LeaderboardCursor or None.
- [ ] Implement exactly FixtureLeaderboardService(provider,
  resource_limits), with both typed arguments mandatory; copy/validate the
  exact six non-defaulted u64-positive limit fields at construction and use no
  None/default/global/registry/environment/singleton/network/server policy.

### Provider boundary and candidate projection

- [ ] Define the exact FixtureLeaderboardProvider.get_snapshot(challenge_key,
  snapshot_sequence) seam returning FixtureLeaderboardCandidateSnapshot or
  None; treat first-page None as no current snapshot, continuation None as the
  exact snapshot absent/stale, an exact empty snapshot as available, and every
  provider exception/wrong return as one integration failure with no salvage.
- [ ] Keep provider ownership of published-candidate selection, exclusion of
  unpublished/cancelled/withdrawn/superseded/stale records, A3 fixture
  eligibility, authorized A5/A6/A7 field copying, both sequences, and retained
  snapshots required by active cursors.
- [ ] Accept only the reviewed provider candidate fields and exact snapshot
  fields (ChallengeKey, canonical tagged SHA-256 hash,
  LeaderboardSnapshotSequence, exact possibly-empty candidate tuple):
  submission_id as exact A7 SubmissionId; result_id as the exact bounded A6
  public result-identifier string; challenge_key as exact ChallengeKey;
  scoring_pack_hash; exact ScoreStatus; exact finite overall_score;
  mandatory_gates_passed; fixture_origin; eligible_for_emission; and exact
  PublicationSequence; reuse ChallengeKey/SubmissionId constructors,
  validate_version, is_sha256_digest, and exact ScoreStatus without copying
  owner grammars.
- [ ] Prove the candidate projection creates no second SubmissionId,
  submission lifecycle, scoring engine, card schema, or publication store.
- [ ] Prove A10 neither imports nor inspects A5 InternalResult/ScoreEngine, A6
  EvaluationCard as input, CardStore/private records, A7 private
  store/records/enumeration, A8 private
  outcomes, or A9 priors/estimates/scaffolds/mock outputs/result feedback.
- [ ] Copy and revalidate each authorized provider field into A10-owned
  immutable values before sorting, ranking, cursor construction, or response
  projection; use no generic provider-object serialization.

### Eligibility and score authority

- [ ] Rank only exact ScoreStatus.SCORED, mandatory_gates_passed=True, exact
  finite built-in float scores within [0.0, 1.0] whose zero has positive sign
  by math.copysign, fixture_origin=True, and eligible_for_emission=False;
  reject -0.0 as malformed without normalizing it.
- [ ] Require every candidate ChallengeKey to equal the requested and snapshot
  ChallengeKey and every scoring_pack_hash to equal the snapshot hash.
- [ ] Reject the whole snapshot on duplicate SubmissionId, duplicate result_id,
  or duplicate PublicationSequence.
- [ ] Require the provider to exclude MANDATORY_GATE_FAILED, PACK_NOT_READY,
  unpublished, cancelled, withdrawn, superseded, infrastructure-incomplete,
  mock, prior, estimate, and scaffold values; reject the whole snapshot as
  malformed if the provider returns any such candidate, without silently
  filtering it.
- [ ] Preserve A5 overall_score and scoring_pack_hash exactly; do not recompute,
  normalize, aggregate, rescale, round, quantize, predict, or estimate scores.
- [ ] Prove fee, payment, sponsor, customer-value, and other economic fields
  cannot affect eligibility, order, rank, ties, or any response field.
- [ ] Prove mandatory-gate failure is excluded rather than represented as an
  ordinary ranked score of zero.

### Ordering, ties, and selection

- [ ] Validate and duplicate-check the complete bounded snapshot, then sort it
  by overall_score descending before any page slice; exact built-in float
  equality is the only Wave-A score tie rule.
- [ ] Competition-rank the complete sorted snapshot as 1, 1, 3, order tied rows
  by publication_sequence ascending, and keep rank/tie/order stable across
  pages and valid continuation page_size changes.
- [ ] Emit one row per provider-approved published submission and implement no
  best-per-requester/hotkey aggregation, decay, win rate, submission count,
  improvement history, or fee-based ordering.
- [ ] Fail the whole operation on malformed, duplicate, mixed-Challenge, or
  mixed-scoring-pack provider output; return no partial page.

### Public allow-list, identity, and time

- [ ] Emit row fields only for rank, challenge_key as exact ChallengeKey,
  scoring_pack_hash, overall_score, mandatory_gates_passed,
  publication_sequence, fixture_origin, and eligible_for_emission.
- [ ] Emit page fields only for schema_version exactly "1.0", exact
  ChallengeKey, exact scoring_pack_hash, exact snapshot sequence, immutable row
  tuple (including rows=() for an available empty snapshot), next cursor or
  None, fixture_origin=True, and eligible_for_emission=False.
- [ ] Prove submission_id and result_id never appear in a row, page, cursor,
  error, representation, or other public/reachable response graph.
- [ ] Omit requester, hotkey, wallet, public/anonymized participant ID,
  timestamps, components, gate IDs/counts, failure tags, diagnostics, margins,
  stress values, fee/payment fields, rank delta, history, counts, win rate,
  data-source labels, and provider metadata.
- [ ] Treat existing RequesterIdentity only as a structural upstream requester
  binding, not authentication proof or a public hotkey; perform no identity
  filtering, participant publication, anonymization, or cross-Challenge
  correlation.
- [ ] Expose no timestamp and perform no current-time access.
- [ ] Use provider-owned nominal PublicationSequence and
  LeaderboardSnapshotSequence, each with exactly one exact built-in int value in
  0..2**64-1, monotonic only within one exact fixture Challenge publication
  stream and carrying no wall-clock, chain-height, finality, A7 lifecycle, or
  settlement meaning.
- [ ] Prove A10 never generates either provider-owned sequence.

### Pagination, snapshots, and resource bounds

- [ ] Give LeaderboardCursor exactly one bounded exact built-in ASCII str and
  bind its private logical payload to exactly schema_version="1.0",
  board_kind="fixture_leaderboard", exact ChallengeKey, canonical tagged
  SHA-256 hash, exact LeaderboardSnapshotSequence, and absolute u64 next_offset.
- [ ] Prove cursors contain no submission/result/requester/identity value,
  seed, draw, context, private pack material, timestamp, path, or provider
  object.
- [ ] Return no total row count; allow a continuation to vary valid page_size
  without binding it into the cursor, and never emit a cursor at or beyond the
  snapshot end.
- [ ] Map exact provider None for a missing first-page snapshot and a missing or
  stale retained continuation snapshot to the same LeaderboardUnavailableError,
  distinct from successful exact empty-snapshot pagination.
- [ ] Keep the service free of durable cache, database, filesystem store,
  scheduler, background refresh, wall-clock expiry, and current-time behavior.
- [ ] Keep bounded in-process fixture snapshot retention with the provider and
  test stable pagination/ranks across retained immutable snapshots, empty
  snapshots, and continuation page_size changes.
- [ ] Enforce exact required max_page_size, max_snapshot_rows,
  max_cursor_utf8_bytes, max_string_utf8_bytes, max_response_utf8_bytes, and
  max_concurrent_calls fields, each exact int in 1..2**64-1, before an
  oversized or partial response escapes.

### Stable errors and hostile boundaries

- [ ] Implement LeaderboardError(Exception) and only four direct subclasses:
  LeaderboardRequestError, LeaderboardResourceError,
  LeaderboardUnavailableError, and LeaderboardIntegrationError.
- [ ] Use exact fixed code/message pairs:
  leaderboard.request.invalid / Leaderboard request is invalid.;
  leaderboard.resource.exhausted / Leaderboard resource limit was exceeded.;
  leaderboard.fixture.unavailable / Fixture leaderboard is unavailable.; and
  leaderboard.integration.failed / Leaderboard provider response is invalid.
- [ ] Ensure errors never echo requester/provider values, invoke hostile repr
  or str, expose a cause/context chain, attach private context, or distinguish
  NotFound.
- [ ] Collapse only exact provider None for absent/stale/unavailable state to
  unavailable without an existence oracle; collapse provider exceptions
  (including attempted public A10 errors), wrong returns, and any returned
  ineligible candidate to one integration failure with no passthrough or
  partial response.
- [ ] Treat request, cursor, nominal values, provider return values, nested
  fields, tuples, and mutable/reentrant objects as hostile or malformed, with
  exact-type/subclass rejection and bounded access; treat the trusted concrete
  provider structurally, without exact-type or runtime Protocol inspection.
- [ ] Demonstrate immutable copying, mutation isolation, reentrancy safety, and
  no provider-owned alias reachable from rows, pages, cursors, errors, caches,
  or representations.
- [ ] Forbid generic serialization of A5, A6, A7, and provider objects and prove
  seed/draw/role/domain/context/entropy/hidden-pack/margin/stress/diagnostic/
  fee/path/private-timestamp/hidden-identity values cannot leak.

### Dependency and installed-artifact boundary

- [ ] Restrict future imports to the Python standard library plus exactly
  carbon.registry ChallengeKey/is_sha256_digest/validate_version,
  carbon.scoring ScoreStatus, and carbon.fees SubmissionId.
- [ ] Import no InternalResult, ScoreEngine, EvaluationCard input,
  CardStore/private A6 record,
  private A7 store/record/enumerator, A8 object, A9 service/provider/result,
  Landscape, emission/chain package, Bittensor, optional scientific package,
  web/HTML framework, filesystem/environment module, or current-time module.
- [ ] Preserve zero mandatory package dependencies and import the exact public
  API from a fresh no-dependency installed wheel outside the source tree.
- [ ] Demonstrate that importing carbon.leaderboard loads no forbidden
  optional-heavy, legacy, web, HTML, filesystem, time, Landscape, neuron,
  Bittensor, chain, weight, or emission module.

### Tests and evidence

- [ ] Add the sole canonical focused suite at
  tests/cpu/test_leaderboard.py; do not create a second leaderboard test path.
- [ ] Cover the exact ordered exports, Protocol/concrete-provider distinction,
  constructor, fields, six resource limits, schema literals, direct error
  inheritance, u64/ASCII bounds, subclass/coercion rejection, hostile input,
  fixed messages/chains, response bounds, and concurrent-call limits.
- [ ] Cover owner-validator/constructor reuse, Challenge/hash isolation, all
  eligibility predicates including negative zero, fixture/official separation,
  exact score preservation, whole-snapshot ordering/ranking before slicing,
  competition ties, duplicate rejection, and no partial page.
- [ ] Cover exact provider None unavailability, provider exception-to-
  integration mapping, exact empty-snapshot success, private cursor binding,
  absolute offsets, no end cursor, continuation page_size variation, immutable
  retained snapshots, provider mutation isolation, and no existence oracle.
- [ ] Cover the positive row/page allow-lists and every prohibited identifier,
  identity, seed, diagnostic, score-detail, time, path, fee, provider, and
  representation leakage route.
- [ ] Prove public validate_version/is_sha256_digest reuse, no EvaluationCard
  input or private A5–A9 access, and no optional-heavy, web, HTML,
  filesystem, time, Landscape, neuron, Bittensor, chain, weight, or emission
  dependency/import.
- [ ] Pass the complete default CPU regression suite without weakening existing
  A0–A9 behavior or maturity.
- [ ] Pass strict Ruff and Black for all changed Python files and the repository
  no-new-debt quality gate.

## Canonical future test command

~~~text
pytest tests/cpu/test_leaderboard.py -q
~~~

The test file does not exist in this documentation-only ratification task and
must not be treated as current A10 test evidence.

## Maturity after this documentation candidate

~~~text
A10 SPECIFIED / RATIFIED: pending merge of PR #36
A10 IMPLEMENTED: NO
A10 TESTED: NO
A10 SCIENTIFICALLY_QUALIFIED: NO
A10 SECURITY_QUALIFIED: NO
A10 NETWORK_QUALIFIED: NO
A10 COMMERCIALLY_VALIDATED: NO
A10 PRODUCTION_QUALIFIED: NO
A10 WAVE STATUS: todo
A11: todo
A12: todo
~~~

No implementation checkbox above may be checked by documentation work.

## Explicitly deferred

Production publication provider/feed; official and LIVE leaderboard; public
identity; anonymization; timestamps; official score precision and cadence;
adaptive-query qualification; frontier nomination/promotion policy;
FrontierRecord; FrontierAdvanceEvent; Product Qualification; commercial rank;
settlement; chain; weights; emissions; A11 logging/metrics; and A12 aggregate
invariants. Production remains fail closed.

## Must not

Do not turn fixtures, stubs, mocks, priors, estimates, scaffolds, historical
validator state, Landscape output, legacy HTML, or legacy emission mechanics
into an official board. Do not infer implementation, testing, qualification, or
production readiness from this contract.
