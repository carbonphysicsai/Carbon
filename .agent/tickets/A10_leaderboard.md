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

- The service, provider, candidate, row, page, sequences, cursor, request,
  resource limits, and errors are nominal A10 types. There is no caller-supplied
  mode string and no official service/provider type in Wave A.
- An injected FixtureLeaderboardProvider supplies an exact provider-approved
  fixture publication snapshot. A10 never enumerates private A5–A9 state.
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
- [ ] Export the exact reviewed nominal fixture-only service, provider,
  candidate, request, row, page, cursor, sequence, resource-limit, and error
  types, with no aliases or generic mode switch.
- [ ] Reject subclasses and coercible substitutes wherever the contract
  requires exact built-in or exact nominal types.
- [ ] Expose exactly FixtureLeaderboardService.list_entries(request) and no
  get-by-submission, global list, cross-Challenge list, identity filter,
  hotkey/participant lookup, score-threshold search, or timestamp search.
- [ ] Require ListFixtureLeaderboardRequest to contain one exact ChallengeKey,
  one exact positive built-in page_size, and LeaderboardCursor or None.
- [ ] Capture construction-injected positive resource limits for maximum page
  size, snapshot rows, cursor bytes, string bytes, response bytes, and
  concurrent calls without inventing production numeric values.

### Provider boundary and candidate projection

- [ ] Define the injected FixtureLeaderboardProvider.get_snapshot exact seam
  over ChallengeKey and LeaderboardSnapshotSequence or None, returning one
  FixtureLeaderboardCandidateSnapshot.
- [ ] Keep provider ownership of published-candidate selection, exclusion of
  unpublished/cancelled/withdrawn/superseded/stale records, A3 fixture
  eligibility, authorized A5/A6/A7 field copying, both sequences, and retained
  snapshots required by active cursors.
- [ ] Accept only the reviewed provider candidate fields:
  submission_id as exact A7 SubmissionId; result_id as the exact bounded A6
  public result-identifier string; challenge_key as exact ChallengeKey;
  scoring_pack_hash; exact ScoreStatus; exact finite overall_score;
  mandatory_gates_passed; fixture_origin; eligible_for_emission; and exact
  PublicationSequence.
- [ ] Prove the candidate projection creates no second SubmissionId,
  submission lifecycle, scoring engine, card schema, or publication store.
- [ ] Prove A10 neither imports nor inspects A5 InternalResult/ScoreEngine, A6
  CardStore/private records, A7 private store/records/enumeration, A8 private
  outcomes, or A9 priors/estimates/scaffolds/mock outputs/result feedback.
- [ ] Copy and revalidate each authorized provider field into A10-owned
  immutable values before sorting, ranking, cursor construction, or response
  projection; use no generic provider-object serialization.

### Eligibility and score authority

- [ ] Rank only exact ScoreStatus.SCORED, mandatory_gates_passed=True, exact
  finite built-in float scores within [0.0, 1.0], fixture_origin=True, and
  eligible_for_emission=False candidates.
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

- [ ] Sort by overall_score descending with exact built-in float equality as
  the only Wave-A score tie rule.
- [ ] Assign competition ranks 1, 1, 3 and order tied rows by
  publication_sequence ascending without changing their shared rank.
- [ ] Emit one row per provider-approved published submission and implement no
  best-per-requester/hotkey aggregation, decay, win rate, submission count,
  improvement history, or fee-based ordering.
- [ ] Fail the whole operation on malformed, duplicate, mixed-Challenge, or
  mixed-scoring-pack provider output; return no partial page.

### Public allow-list, identity, and time

- [ ] Emit row fields only for rank, challenge_key as exact ChallengeKey,
  scoring_pack_hash, overall_score, mandatory_gates_passed,
  publication_sequence, fixture_origin, and eligible_for_emission.
- [ ] Emit page fields only for schema version, exact ChallengeKey, exact
  scoring_pack_hash, exact snapshot sequence, immutable row tuple, next cursor
  or None, fixture_origin=True, and eligible_for_emission=False.
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
  LeaderboardSnapshotSequence values that are monotonic only within one exact
  fixture Challenge publication stream and carry no wall-clock, chain-height,
  finality, A7 lifecycle, or settlement meaning.
- [ ] Prove A10 never generates either provider-owned sequence.

### Pagination, snapshots, and resource bounds

- [ ] Bind each opaque cursor only to its cursor schema, fixture-board
  discriminator fixed by service type, exact ChallengeKey, scoring_pack_hash,
  LeaderboardSnapshotSequence, and next offset.
- [ ] Prove cursors contain no submission/result/requester/identity value,
  seed, draw, context, private pack material, timestamp, path, or provider
  object.
- [ ] Return no total row count.
- [ ] Map missing and stale retained cursor snapshots to the same
  LeaderboardUnavailableError.
- [ ] Keep the service free of durable cache, database, filesystem store,
  scheduler, background refresh, wall-clock expiry, and current-time behavior.
- [ ] Keep bounded in-process fixture snapshot retention with the provider and
  test stable pagination across retained immutable snapshots.
- [ ] Enforce page-size, snapshot-row, cursor-byte, string-byte,
  response-byte, and concurrent-call limits before an oversized or partial
  response escapes.

### Stable errors and hostile boundaries

- [ ] Implement only LeaderboardError, LeaderboardRequestError,
  LeaderboardResourceError, LeaderboardUnavailableError, and
  LeaderboardIntegrationError with the exact ratified inheritance.
- [ ] Use exact fixed code/message pairs:
  leaderboard.request.invalid / Leaderboard request is invalid.;
  leaderboard.resource.exhausted / Leaderboard resource limit was exceeded.;
  leaderboard.fixture.unavailable / Fixture leaderboard is unavailable.; and
  leaderboard.integration.failed / Leaderboard provider response is invalid.
- [ ] Ensure errors never echo requester/provider values, invoke hostile repr
  or str, expose a cause/context chain, attach private context, or distinguish
  NotFound.
- [ ] Collapse absent, stale, unpublished, and ineligible fixture-provider
  state reported without a snapshot to unavailable without an existence
  oracle; classify any returned candidate in such a state as malformed
  provider output and one integration failure for the whole operation.
- [ ] Treat request, cursor, nominal values, provider return values, nested
  fields, tuples, and mutable/reentrant objects as hostile or malformed, with
  exact-type/subclass rejection and bounded access.
- [ ] Demonstrate immutable copying, mutation isolation, reentrancy safety, and
  no provider-owned alias reachable from rows, pages, cursors, errors, caches,
  or representations.
- [ ] Forbid generic serialization of A5, A6, A7, and provider objects and prove
  seed/draw/role/domain/context/entropy/hidden-pack/margin/stress/diagnostic/
  fee/path/private-timestamp/hidden-identity values cannot leak.

### Dependency and installed-artifact boundary

- [ ] Restrict future imports to the Python standard library,
  carbon.registry.ChallengeKey, carbon.scoring.ScoreStatus, and
  carbon.fees.SubmissionId.
- [ ] Import no InternalResult, ScoreEngine, CardStore/private A6 record,
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
- [ ] Cover exact types/exports, subclass/coercion rejection, hostile input,
  stable errors, fixed messages, no cause/context, resource capture, response
  bounds, and concurrent-call limits.
- [ ] Cover Challenge/scoring-pack isolation, all eligibility predicates,
  fixture/official separation, exact score preservation, deterministic order,
  competition ties, duplicate rejection, and no partial page.
- [ ] Cover pagination/cursor binding, stale/missing snapshot collapse,
  immutable retained snapshots, provider mutation isolation, and no existence
  oracle.
- [ ] Cover the positive row/page allow-lists and every prohibited identifier,
  identity, seed, diagnostic, score-detail, time, path, fee, provider, and
  representation leakage route.
- [ ] Prove no private A5–A9 access and no optional-heavy, web, HTML,
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
SPECIFIED / RATIFIED: pending merge of this documentation PR
IMPLEMENTED: NO
TESTED: NO
SCIENTIFICALLY_QUALIFIED: NO
SECURITY_QUALIFIED: NO
NETWORK_QUALIFIED: NO
COMMERCIALLY_VALIDATED: NO
PRODUCTION_QUALIFIED: NO
WAVE STATUS: todo
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
