# Ticket A10 — Bounded fixture leaderboard projection (C14)

**Wave:** A
**Status:** proposed done by this documentation-only closeout; effective only
after independent review, explicit human authorization, and normal merge
**Build_Out:** C14, interpreted through Design_Specs/Build_Out_Constitutional_Overlay.md
**Depends on:** A3, A5, A6, A7
**Plan:** .agent/plans/A10_leaderboard.md

## Goal

Current main implements one bounded in-process fixture leaderboard projection
with a positive public allow-list. The Wave-A surface is fixture-only,
Challenge-bound, snapshot-bound, deterministic, resource-bounded,
hostile-input-safe, and structurally unable to claim official, LIVE, frontier,
product, settlement, chain, weight, or emission authority.

The implemented service operation is exactly:

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

## Implementation DoD

Every criterion below remains the exact ratified implementation contract. The
criterion texts and order are unchanged; only the checkbox markers change in
this documentation-only closeout. Checking them records implementation and test
truth already merged on current main. This closeout adds no implementation,
test, fixture, dependency, workflow, CI, or quality evidence.

### Exact surface and nominal types

- [x] Add only the smallest package layout: carbon/leaderboard/__init__.py,
  model.py, providers.py, and service.py.
- [x] Export the exact ordered sixteen-name carbon.leaderboard.__all__ tuple
  ratified in A10-R2, with no alias, generic/official type, store, serializer,
  or extra error.
- [x] Implement FixtureLeaderboardProvider as typing.Protocol, permit trusted
  concrete structural implementations without subclassing or runtime-checkable
  introspection, and reject subclasses/coercible substitutes for every exact
  nominal value and nested field instead of exact-typing the provider object.
- [x] Expose exactly FixtureLeaderboardService.list_entries(request) and no
  get-by-submission, global list, cross-Challenge list, identity filter,
  hotkey/participant lookup, score-threshold search, or timestamp search.
- [x] Require ListFixtureLeaderboardRequest to contain exactly challenge_key as
  exact ChallengeKey, page_size as exact built-in int in 1..2**64-1, and cursor
  as exact LeaderboardCursor or None.
- [x] Implement exactly FixtureLeaderboardService(provider,
  resource_limits), with both typed arguments mandatory; copy/validate the
  exact six non-defaulted u64-positive limit fields at construction and use no
  None/default/global/registry/environment/singleton/network/server policy.

### Provider boundary and candidate projection

- [x] Define the exact FixtureLeaderboardProvider.get_snapshot(challenge_key,
  snapshot_sequence) seam returning FixtureLeaderboardCandidateSnapshot or
  None; treat first-page None as no current snapshot, continuation None as the
  exact snapshot absent/stale, and an exact empty snapshot as available; map
  every ordinary error raised by provider-controlled behavior and satisfying
  isinstance(error, Exception), plus every non-None wrong return, to a new fixed
  integration error with no salvage, while a non-Exception BaseException
  propagates unchanged.
- [x] Keep provider ownership of published-candidate selection, exclusion of
  unpublished/cancelled/withdrawn/superseded/stale records, A3 fixture
  eligibility, authorized A5/A6/A7 field copying, both sequences, and retained
  snapshots required by active cursors.
- [x] Accept only the reviewed provider candidate fields and exact snapshot
  fields (ChallengeKey, canonical tagged SHA-256 hash,
  LeaderboardSnapshotSequence, exact possibly-empty candidate tuple):
  submission_id as exact A7 SubmissionId; result_id as the exact bounded A6
  public result-identifier string; challenge_key as exact ChallengeKey;
  scoring_pack_hash; exact ScoreStatus; exact finite overall_score;
  mandatory_gates_passed; fixture_origin; eligible_for_emission; and exact
  PublicationSequence; reuse ChallengeKey/SubmissionId constructors,
  validate_version, is_sha256_digest, and exact ScoreStatus without copying
  owner grammars.
- [x] Prove the candidate projection creates no second SubmissionId,
  submission lifecycle, scoring engine, card schema, or publication store.
- [x] Prove A10 neither imports nor inspects A5 InternalResult/ScoreEngine, A6
  EvaluationCard as input, CardStore/private records, A7 private
  store/records/enumeration, A8 private
  outcomes, or A9 priors/estimates/scaffolds/mock outputs/result feedback.
- [x] Copy and revalidate each authorized provider field into A10-owned
  immutable values before sorting, ranking, cursor construction, or response
  projection; use no generic provider-object serialization.

### Eligibility and score authority

- [x] Rank only exact ScoreStatus.SCORED, mandatory_gates_passed=True, exact
  finite built-in float scores within [0.0, 1.0] whose zero has positive sign
  by math.copysign, fixture_origin=True, and eligible_for_emission=False;
  reject -0.0 as malformed without normalizing it.
- [x] Require every candidate ChallengeKey to equal the requested and snapshot
  ChallengeKey and every scoring_pack_hash to equal the snapshot hash.
- [x] Reject the whole snapshot on duplicate SubmissionId, duplicate result_id,
  or duplicate PublicationSequence.
- [x] Require the provider to exclude MANDATORY_GATE_FAILED, PACK_NOT_READY,
  unpublished, cancelled, withdrawn, superseded, infrastructure-incomplete,
  mock, prior, estimate, and scaffold values; reject the whole snapshot as
  malformed if the provider returns any such candidate, without silently
  filtering it.
- [x] Preserve A5 overall_score and scoring_pack_hash exactly; do not recompute,
  normalize, aggregate, rescale, round, quantize, predict, or estimate scores.
- [x] Prove fee, payment, sponsor, customer-value, and other economic fields
  cannot affect eligibility, order, rank, ties, or any response field.
- [x] Prove mandatory-gate failure is excluded rather than represented as an
  ordinary ranked score of zero.

### Ordering, ties, and selection

- [x] Validate and duplicate-check the complete bounded snapshot, then sort it
  by overall_score descending before any page slice; exact built-in float
  equality is the only Wave-A score tie rule.
- [x] Competition-rank the complete sorted snapshot as 1, 1, 3, order tied rows
  by publication_sequence ascending, and keep rank/tie/order stable across
  pages and valid continuation page_size changes.
- [x] Emit one row per provider-approved published submission and implement no
  best-per-requester/hotkey aggregation, decay, win rate, submission count,
  improvement history, or fee-based ordering.
- [x] Fail the whole operation on malformed, duplicate, mixed-Challenge, or
  mixed-scoring-pack provider output; return no partial page.

### Public allow-list, identity, and time

- [x] Emit row fields only for rank, challenge_key as exact ChallengeKey,
  scoring_pack_hash, overall_score, mandatory_gates_passed,
  publication_sequence, fixture_origin, and eligible_for_emission.
- [x] Emit page fields only for schema_version exactly "1.0", exact
  ChallengeKey, exact scoring_pack_hash, exact snapshot sequence, immutable row
  tuple (including rows=() for an available empty snapshot), next cursor or
  None, fixture_origin=True, and eligible_for_emission=False.
- [x] Prove submission_id and result_id never appear in a row, page, cursor,
  error, representation, or other public/reachable response graph.
- [x] Omit requester, hotkey, wallet, public/anonymized participant ID,
  timestamps, components, gate IDs/counts, failure tags, diagnostics, margins,
  stress values, fee/payment fields, rank delta, history, counts, win rate,
  data-source labels, and provider metadata.
- [x] Treat existing RequesterIdentity only as a structural upstream requester
  binding, not authentication proof or a public hotkey; perform no identity
  filtering, participant publication, anonymization, or cross-Challenge
  correlation.
- [x] Expose no timestamp and perform no current-time access.
- [x] Use provider-owned nominal PublicationSequence and
  LeaderboardSnapshotSequence, each with exactly one exact built-in int value in
  0..2**64-1, monotonic only within one exact fixture Challenge publication
  stream and carrying no wall-clock, chain-height, finality, A7 lifecycle, or
  settlement meaning.
- [x] Prove A10 never generates either provider-owned sequence.

### Pagination, snapshots, and resource bounds

- [x] Give LeaderboardCursor exactly one bounded exact built-in ASCII str and
  bind its private logical payload to exactly schema_version="1.0",
  board_kind="fixture_leaderboard", exact ChallengeKey, canonical tagged
  SHA-256 hash, exact LeaderboardSnapshotSequence, and absolute u64 next_offset;
  require an emitted next_cursor.value to satisfy both max_cursor_utf8_bytes and
  max_string_utf8_bytes, charge it exactly once in response_utf8_bytes(page),
  exclude an incoming cursor from that response total while retaining its
  existing request/cursor limits, and never double-count its decoded private
  payload fields.
- [x] Prove cursors contain no submission/result/requester/identity value,
  seed, draw, context, private pack material, timestamp, path, or provider
  object.
- [x] Return no total row count; allow a continuation to vary valid page_size
  without binding it into the cursor, and never emit a cursor at or beyond the
  snapshot end.
- [x] Map exact provider None for a missing first-page snapshot and a missing or
  stale retained continuation snapshot to the same LeaderboardUnavailableError,
  distinct from successful exact empty-snapshot pagination.
- [x] Keep the service free of durable cache, database, filesystem store,
  scheduler, background refresh, wall-clock expiry, and current-time behavior.
- [x] Keep bounded in-process fixture snapshot retention with the provider and
  test stable pagination/ranks across retained immutable snapshots, empty
  snapshots, and continuation page_size changes.
- [x] Enforce exact required max_page_size, max_snapshot_rows,
  max_cursor_utf8_bytes, max_string_utf8_bytes, max_response_utf8_bytes, and
  max_concurrent_calls fields, each exact int in 1..2**64-1; define
  response_utf8_bytes(page) as the exact occurrence sum of page schema_version,
  page Challenge ID/version, page scoring-pack hash, each row Challenge
  ID/version and scoring-pack hash in final tuple order, and optional emitted
  next_cursor.value exactly once, where utf8(value) is
  len(value.encode("utf-8")); apply max_string_utf8_bytes per occurrence, permit
  totals at the response limit, and raise the fixed resource error one byte over
  before any partial response escapes; exclude fixed errors and all non-formula
  material from this success-page meter without recursively metering a resource
  error; release each acquired concurrency permit in finally after success,
  public failure, translated Exception, and propagated non-Exception
  BaseException.

### Stable errors and hostile boundaries

- [x] Implement LeaderboardError(Exception) and only four direct subclasses:
  LeaderboardRequestError, LeaderboardResourceError,
  LeaderboardUnavailableError, and LeaderboardIntegrationError.
- [x] Use exact fixed code/message pairs:
  leaderboard.request.invalid / Leaderboard request is invalid.;
  leaderboard.resource.exhausted / Leaderboard resource limit was exceeded.;
  leaderboard.fixture.unavailable / Fixture leaderboard is unavailable.; and
  leaderboard.integration.failed / Leaderboard provider response is invalid.
- [x] Ensure errors never echo requester/provider values, invoke hostile repr
  or str, expose provider exception text/value/payload or a cause/context chain,
  attach private context, or distinguish NotFound.
- [x] Collapse only exact provider None for absent/stale/unavailable state to
  unavailable without an existence oracle; translate each ordinary provider
  Exception, including provider-raised LeaderboardRequestError,
  LeaderboardResourceError, LeaderboardUnavailableError, and
  LeaderboardIntegrationError, to one new fixed integration error without
  passthrough/chaining; propagate every non-Exception BaseException unchanged
  and forbid `except BaseException` at every provider/public translation seam;
  preserve the exact mappings of all A10-created public failures.
- [x] Treat request, cursor, nominal values, provider return values, nested
  fields, tuples, and mutable/reentrant objects as hostile or malformed, with
  exact-type/subclass rejection and bounded access; treat the trusted concrete
  provider structurally, without exact-type or runtime Protocol inspection;
  map missing/call-incompatible methods and ordinary-Exception descriptor/hook/
  call failures to integration, but propagate KeyboardInterrupt, SystemExit,
  GeneratorExit, and other non-Exception BaseException values unchanged.
- [x] Demonstrate immutable copying, mutation isolation, reentrancy safety, and
  no provider-owned alias reachable from rows, pages, cursors, errors, caches,
  or representations.
- [x] Forbid generic serialization of A5, A6, A7, and provider objects and prove
  seed/draw/role/domain/context/entropy/hidden-pack/margin/stress/diagnostic/
  fee/path/private-timestamp/hidden-identity values cannot leak.

### Dependency and installed-artifact boundary

- [x] Restrict future imports to the Python standard library plus exactly
  carbon.registry ChallengeKey/is_sha256_digest/validate_version,
  carbon.scoring ScoreStatus, and carbon.fees SubmissionId.
- [x] Import no InternalResult, ScoreEngine, EvaluationCard input,
  CardStore/private A6 record,
  private A7 store/record/enumerator, A8 object, A9 service/provider/result,
  Landscape, emission/chain package, Bittensor, optional scientific package,
  web/HTML framework, filesystem/environment module, or current-time module.
- [x] Preserve zero mandatory package dependencies and import the exact public
  API from a fresh no-dependency installed wheel outside the source tree.
- [x] Demonstrate that importing carbon.leaderboard loads no forbidden
  optional-heavy, legacy, web, HTML, filesystem, time, Landscape, neuron,
  Bittensor, chain, weight, or emission module.

### Tests and evidence

- [x] Add the sole canonical focused suite at
  tests/cpu/test_leaderboard.py; do not create a second leaderboard test path.
- [x] Cover the exact ordered exports, Protocol/concrete-provider distinction,
  constructor, fields, six resource limits, schema literals, direct error
  inheritance, u64/ASCII bounds, subclass/coercion rejection, hostile input,
  fixed messages/chains, the exact response_utf8_bytes(page) formula and
  chargeable/uncharged source manifest, declared page/row traversal order,
  per-occurrence charging of repeated equal and identity-shared strings,
  per-string and dual cursor bounds, concurrent-call limits, source guards
  against reflection/generic serialization and `except BaseException`, and
  finally-based permit release on every translated or propagating path.
- [x] Cover owner-validator/constructor reuse, Challenge/hash isolation, all
  eligibility predicates including negative zero, fixture/official separation,
  exact score preservation, whole-snapshot ordering/ranking before slicing,
  competition ties, duplicate rejection, and no partial page.
- [x] Cover exact provider None unavailability, RuntimeError-to-integration and
  provider-public-error-to-new-integration mapping without message/cause/context
  leakage, unchanged KeyboardInterrupt/SystemExit propagation and unchanged
  GeneratorExit propagation where practical, capacity recovery after
  translated Exception and propagated non-Exception BaseException, exact
  empty-page response accounting, exact-at-limit success, one-byte-over resource
  failure with no partial page, fixed-error exclusion, private cursor binding,
  absolute offsets, no end cursor, exactly-once emitted-cursor charging without
  private-payload duplication, continuation page_size variation, immutable
  retained snapshots, provider mutation isolation, no existence oracle, and no
  repr, dataclass, JSON, HTTP, REST, wire-format, or network dependency.
- [x] Cover the positive row/page allow-lists and every prohibited identifier,
  identity, seed, diagnostic, score-detail, time, path, fee, provider, and
  representation leakage route; lock the explicit response-accounting field
  manifest and require a separately ratified formula update before any future
  public string field can count, without reflection or default-public behavior.
- [x] Prove public validate_version/is_sha256_digest reuse, no EvaluationCard
  input or private A5–A9 access, and no optional-heavy, web, HTML,
  filesystem, time, Landscape, neuron, Bittensor, chain, weight, or emission
  dependency/import.
- [x] Pass the complete default CPU regression suite without weakening existing
  A0–A9 behavior or maturity.
- [x] Pass strict Ruff and Black for all changed Python files and the repository
  no-new-debt quality gate.

## Administrative closeout evidence

Checking the 57 criteria above records implementation and tests already merged
to current main. This documentation-only closeout creates no new
implementation, test, fixture, dependency, packaging, workflow, CI, or quality
evidence.

### Ratification, implementation, and review topology

- Contract ratification merge:
  `f4ad756a994a9bf21d919fccc4f164fc9719f4e6`, tree
  `17140d76d8c50d0c78880a95c00f9b75f3be8ee1`, ordered parents
  `f308281e69580216d5ebf5ec94a9d6c069cf1a56` and
  `aca22b4727e9e571a95745294004f733aa419e14`, subject
  `Merge pull request #36 from carbonphysicsai/agent/a10-contract-ratification`.
- Implementation merge/current closeout base:
  `3b2d96e287f06c24cc4d57b46dfc418359a9e97f`, tree
  `6a6e95262773b9b2e22ad5c43837194f06e070a6`, ordered parents
  `bc95ef09910014ff3d08d3f0a9fbfaf6999c2d79` and
  `6f505d5cffd69f0c3d4d0e6d71bb91233c0ce6b1`, subject
  `Merge pull request #37 from carbonphysicsai/agent/a10-leaderboard`.
- Reviewed implementation head:
  `6f505d5cffd69f0c3d4d0e6d71bb91233c0ce6b1`, tree
  `6a6e95262773b9b2e22ad5c43837194f06e070a6`, sole parent
  `6be31d10272ac18b580a4733079318f7d3d69309`. Its tree equals the
  implementation-merge tree and its file diff to the merge is empty.
- Exact reviewed five-commit history:
  `d69b5ec77e630914fce4068abe2dc5303876cd12`,
  `1c5196a5a48caeb6c9a14f90cef3c00fd6cfd7b9`,
  `bd263c44fa955f32a28a6afd1c56ed8b9334cf11`,
  `6be31d10272ac18b580a4733079318f7d3d69309`, and
  `6f505d5cffd69f0c3d4d0e6d71bb91233c0ce6b1`.
- PR #37 merged normally at `2026-08-26T07:14:59Z`; auto-merge was never
  enabled and the source branch remains present. The exact parent-one delta is
  six paths: `.agent/WAVE.md` `M +2/-2`;
  `carbon/leaderboard/__init__.py` `M +45/-1`;
  `carbon/leaderboard/model.py` `A +781/-0`;
  `carbon/leaderboard/providers.py` `A +24/-0`;
  `carbon/leaderboard/service.py` `A +905/-0`; and
  `tests/cpu/test_leaderboard.py` `A +3368/-0`; total `+5125/-3`.
- Exact merged blobs: WAVE
  `9f95f658ba22e801290e3a770db2106249c83734`; root export
  `67823bc69da8591f5d2729e79fc679443a42e5ce`; model
  `2450cc8f3487bb8a1a9b258445900aafa36e82f4`; provider
  `000aebd1b0eced4122c2a0496d8ecc5b434a9d78`; service
  `ca7bfa97f126fab2b251f729ede2254da078d36f`; focused tests
  `23480fb2dc6e4d59ecf16c5207c105cf4274dd81`.
- Exact-main push run `32941840184` completed successfully on
  `3b2d96e287f06c24cc4d57b46dfc418359a9e97f`: CPU job `98094221825`
  recorded `1973 passed in 53.86s`; quality job `98094221851` recorded Ruff
  `757/776`, Black `62/68`, removed debt `19/6`, five changed Python files,
  no new debt, and all changed Python files clean.
- Final exact-head Greptile check `98088524053` succeeded with six files
  reviewed and zero comments added. Summary `5420464156` recorded confidence
  `5/5`, no blocking failure, and both findings addressed. Threads
  `PRRT_kwDOTTqcu86cVNoB` and `PRRT_kwDOTTqcu86cWEry` are resolved and
  outdated; unresolved substantive thread count is zero. Formal reviews remain
  `COMMENTED`, not `APPROVED`; no formal GitHub approval is claimed. The stale
  historical sentence in the closed PR body is not current-state authority.

### Fresh independent closeout audit

- Python: `3.11.11`.
- Focused suite: `246 passed in 6.05s`.
- Exact related suite: `1530 passed in 29.62s`.
- Full default suite: `1973 passed in 30.61s`.
- Ruff `0.16.3`: strict focused-source check passed.
- Black `26.5.1`: five focused Python files unchanged.
- Wheel: `carbon-0.9.0-py3-none-any.whl`, `183340` bytes, SHA-256
  `e39008b41550ecd3d198a1a2e01548178f72cc4f0aa722c99aa185ba538153d7`.
- Outside-checkout isolated install: installed distribution `carbon==0.9.0`;
  mandatory dependencies `0`; exact ordered sixteen-name export tuple;
  representative public values constructed; representative valid
  `list_entries` returned the expected fixture row; blocked optional/later
  dependency attempts `0`; blocked modules loaded `0`; result `PASS`.
- Ticket audit: the pre-closeout ticket blob was identical to the ratification
  blob `46a3e5759418acde51cba91534e9eb467051e7a4`; exactly 57 criterion
  texts occurred in unchanged order. Independent result: `57 PASS / 0 FAIL`.

### Owner-evidence key

- `O3`: `carbon/registry/model.py::ChallengeKey`, `validate_version`;
  `carbon/registry/digest.py::is_sha256_digest`;
  `tests/cpu/test_registry.py::test_public_registry_validation_helpers_preserve_a3_contracts`.
- `O5`: `carbon/scoring/model.py::ScoreStatus`, `InternalResult`;
  `carbon/scoring/engine.py::ScoreEngine`;
  `tests/cpu/test_scoring_engine.py::test_internal_result_private_copy_preserves_each_exact_status`,
  `test_mandatory_failure_result_requires_full_atomic_zero_false_invariant`,
  `test_fixture_golden_scoring_result_is_exact_binary64`, and
  `test_every_fixture_result_disposition_is_non_emitting`.
- `O6`: `carbon/cards/model.py::EvaluationCard`;
  `carbon/cards/store.py::CardStore`;
  `tests/cpu/test_card_store.py::test_component_scores_preserve_a5_binary64_values_including_negative_zero`,
  `test_first_write_recursively_owns_the_complete_nonempty_a5_graph`, and
  `test_public_projection_is_allow_listed_and_has_no_private_graph`.
- `O7`: `carbon/fees/model.py::SubmissionId`, `RequesterIdentity`;
  `carbon/fees/service.py::SubmissionService`;
  `tests/cpu/test_submission_fsm.py::test_submission_id_accepts_only_canonical_uuid4`,
  `test_fixture_happy_path_is_exact_and_publishes_only_a6_card`,
  `test_mandatory_gate_failure_is_completed_science_not_infrastructure`, and
  `test_public_exports_are_exact_and_no_private_store_surface_exists`.
- `O8`: `carbon/traineval/service.py::FixtureTrainEvalService`;
  `tests/cpu/test_traineval_stub.py::test_private_outcomes_have_minimum_fields_and_no_hidden_material_graph`,
  `test_no_a2_a3_or_a6_operation_is_repeated_inside_a8`, and
  `test_source_import_graph_and_calls_exclude_forbidden_owners`.
- `O9`: `carbon/mcp/service.py::McpService`;
  `carbon/mcp/providers.py::PriorProvider`, `ScaffoldProvider`,
  `EstimateProvider`;
  `tests/cpu/test_mcp_skeleton.py::test_fixture_challenge_projection_is_minimal_and_does_not_enumerate`,
  `test_source_dependency_and_owner_call_guards`, and
  `test_service_surface_has_no_cache_history_or_store`.

### Exclusion and maturity key

- `X0`: bounded fixture-only, non-official, non-LIVE, non-frontier,
  non-product, non-network, and non-production; no settlement, chain, weight,
  or emission authority.
- `X1`: no public identity, authentication, anonymization, correlation, or
  timestamp.
- `X2`: no private A5-A9 graph, economics, diagnostics, hidden material, or
  generic serialization.
- `X3`: no transport, web/HTML, filesystem, persistence, durable cache,
  scheduler, environment, or current-time behavior.
- `X4`: provider projection only; no second identity mint, lifecycle, scoring
  engine, card schema, or publication store.
- `X5`: cursor is logical and opaque only; no authentication, confidentiality,
  durability, wire-format, or production-security claim.
- `X6`: fixture availability/publication is not official publication; a future
  official feed remains separately unratified.
- `X7`: no A11 logging/metrics or A12 aggregate-invariant work.
- `M0` applies to every row: specified, implemented, and tested only in the
  recorded engineering scope; scientific, security, network, commercial, and
  production qualification remain `NO`; administrative `done` remains
  conditional on closeout review, authorization, and normal merge.

All unqualified test names in the matrix below are in
`tests/cpu/test_leaderboard.py`.

Within the matrix, `model.py`, `providers.py`, and `service.py` denote the
exact current paths `carbon/leaderboard/model.py`,
`carbon/leaderboard/providers.py`, and `carbon/leaderboard/service.py`.

### 57-row closure evidence matrix

| # | Control / owner boundary | Exact current source path and symbol | Canonical test evidence | Supporting owner evidence | Result | Preserved exclusion / limitation |
|---:|---|---|---|---|---|---|
| 1 | A10-R14 | `carbon/leaderboard/{__init__.py,model.py,providers.py,service.py}` | `test_exact_package_exports_fields_and_root_namespace` | - | PASS | X0, X3, M0 |
| 2 | A10-R2 | `carbon/leaderboard/__init__.py::__all__` | `test_exact_package_exports_fields_and_root_namespace` | - | PASS | No alias, generic/official type, store, serializer, or extra error; X0, M0 |
| 3 | A10-R2/R3/R13 | `providers.py::FixtureLeaderboardProvider`; `service.py::_invoke_provider`; exact-type copy helpers | `test_protocol_is_structural_and_not_runtime_checkable`; `test_constructor_does_not_introspect_or_invoke_provider`; `test_nominal_subclasses_are_rejected` | O3/O5/O7 | PASS | Structural provider is not public/runtime type authority; X6, M0 |
| 4 | A10-R2 | `service.py::FixtureLeaderboardService.list_entries`; class `__slots__` | `test_service_constructor_signature_and_only_public_operation` | - | PASS | No get/global/cross-Challenge/identity/threshold/time operation; X0/X1, M0 |
| 5 | A10-R2/R11/R13 | `model.py::ListFixtureLeaderboardRequest`; `service.py::_copy_request`, `_copy_request_cursor`, `_copy_request_challenge` | `test_exact_package_exports_fields_and_root_namespace`; `test_request_page_size_requires_exact_positive_u64`; `test_cursor_requires_an_exact_ascii_string`; `test_owner_nominals_are_exact_and_reconstructed` | O3 | PASS | No requester, mode, selector, raw snapshot, or provider input; X1, M0 |
| 6 | A10-R2/R11/R13 | `model.py::FixtureLeaderboardResourceLimits`; `service.py::FixtureLeaderboardService.__init__`, `_copy_limits` | `test_each_resource_limit_requires_exact_positive_u64`; `test_resource_limits_are_required_and_copied_by_service` | - | PASS | No default/global/registry/environment/network policy; X3, M0 |
| 7 | A10-R3/R12/R13 | `providers.py::FixtureLeaderboardProvider.get_snapshot`; `service.py::_invoke_provider`, `_copy_snapshot`, `_list_admitted`, `list_entries` | `test_first_page_provider_arguments_call_count_and_owned_projection`; `test_exact_none_is_unavailable_but_empty_snapshot_is_success`; `test_non_none_wrong_provider_returns_map_to_integration`; `test_every_provider_exception_becomes_a_new_integration_error`; `test_non_exception_baseexceptions_propagate_unchanged` | O3 | PASS | No salvage/public-error passthrough; exact empty differs from `None`; X6, M0 |
| 8 | A10-R3/R4 | Provider seam; `service.py::_copy_snapshot`, `_copy_candidate` | `test_first_page_provider_arguments_call_count_and_owned_projection`; `test_continuation_passes_cursor_snapshot_sequence_and_absolute_offset`; `test_source_has_no_private_owner_or_deferred_authority_dependency` | O3/O5/O6/O7/O8/O9 | PASS | Selection, lifecycle exclusions, fields, sequences, and retention remain provider-owned; X2/X4/X6, M0 |
| 9 | A10-R4/R8/R14 | `model.py::FixtureLeaderboardCandidate`, `FixtureLeaderboardCandidateSnapshot`; provider-field copy helpers | `test_owner_nominals_are_exact_and_reconstructed`; `test_public_owner_validators_are_applied_without_coercion`; `test_candidate_constructor_requires_exact_provider_field_shapes`; `test_snapshot_requires_an_exact_tuple_of_exact_candidates`; repair tests below | O3/O5/O6/O7 | PASS | Reviewed fields only; no copied owner grammar; X4/X6, M0 |
| 10 | A10-R4 | `model.py::FixtureLeaderboardCandidate`; `service.py::_copy_submission_id`, `_construct_candidate`; package import graph | `test_candidate_preserves_exact_score_and_pack_but_hides_private_ids`; `test_source_has_no_private_owner_or_deferred_authority_dependency`; `test_dependency_import_and_runtime_escape_policy` | O5/O6/O7 | PASS | No ID mint, lifecycle, scoring engine, card schema, or store; X4, M0 |
| 11 | A10-R3/R4/R14 | All four leaderboard modules' import graph | `test_source_has_no_private_owner_or_deferred_authority_dependency`; `test_dependency_import_and_runtime_escape_policy`; `test_import_with_optional_and_later_dependencies_blocked` | O5/O6/O7/O8/O9 | PASS | No private A5-A9 access/enumeration; X2/X3, M0 |
| 12 | A10-R4/R13 | Field copy helpers; `service.py::_copy_candidate`, `_copy_snapshot`, `_new_row`, `_new_page` | `test_first_page_provider_arguments_call_count_and_owned_projection`; `test_provider_snapshot_mutation_after_return_cannot_change_page`; `test_provider_mutation_during_callback_cannot_change_owned_request`; `test_continuation_provider_cannot_mutate_retained_cursor_sequence`; `test_no_provider_owned_private_alias_is_reachable_from_success` | O3/O7 | PASS | Field-by-field immutable ownership; no generic serialization; X2, M0 |
| 13 | A10-R8/R9 | `service.py::_copy_score_status`, `_copy_candidate` | `test_forged_ineligible_provider_candidate_rejects_whole_snapshot`; `test_exact_float_equality_is_the_only_tie_rule_and_scores_are_preserved` | O5 | PASS | SCORED-only, positive-zero, fixture-only, non-emitting; X0/X6, M0 |
| 14 | A10-R8 | `service.py::_copy_candidate`, `_copy_snapshot`, `_same_challenge` | `test_forged_ineligible_provider_candidate_rejects_whole_snapshot`; `test_mixed_challenge_or_pack_snapshots_fail_without_partial_page`; `test_continuation_cannot_drift_or_fall_forward` | O3/O5/O6 | PASS | No cross-Challenge or cross-pack comparison; X0/X6, M0 |
| 15 | A10-R8/R10 | `service.py::_copy_snapshot` duplicate sets | `test_duplicate_provider_identity_rejects_the_complete_snapshot[submission/result/publication]` | O6/O7 | PASS | No duplicate salvage/partial page; X6, M0 |
| 16 | A10-R3/R8 | Provider seam; `service.py::_copy_score_status`, `_copy_candidate` | `test_forged_ineligible_provider_candidate_rejects_whole_snapshot`; `test_source_has_no_private_owner_or_deferred_authority_dependency` | O5/O7/O8/O9 | PASS | Provider owns lifecycle/publication exclusion; malformed projection fails closed; X2/X6, M0 |
| 17 | A10-R9 | `service.py::_copy_candidate`, `_sort_key`, `_new_row` | `test_candidate_preserves_exact_score_and_pack_but_hides_private_ids`; `test_exact_float_equality_is_the_only_tie_rule_and_scores_are_preserved` | O5/O6 | PASS | No recompute/normalization/rounding/prediction/estimate; M0 |
| 18 | A10-R5/R6/R8/R9 | `model.py::FixtureLeaderboardRow`, `FixtureLeaderboardPage`; projection constructors | `test_public_allowlist_has_no_identity_time_diagnostics_or_economics`; `test_source_has_no_private_owner_or_deferred_authority_dependency` | O5/O7 | PASS | Economics cannot enter eligibility/order/rank/response; X1/X2, M0 |
| 19 | A10-R8/R9 | `service.py::_copy_score_status`, `_copy_candidate` | `test_forged_ineligible_provider_candidate_rejects_whole_snapshot` | O5 | PASS | Mandatory failure excluded, never ranked as zero; X6, M0 |
| 20 | A10-R10/R11/R13 | `service.py::_copy_snapshot`, `_sort_key`, `_rank_snapshot`, `_list_admitted` | `test_snapshot_bound_is_committed_before_candidate_access`; `test_duplicate_provider_identity_rejects_the_complete_snapshot`; `test_complete_snapshot_is_sorted_and_competition_ranked_before_slice` | O5 | PASS | Complete bounded snapshot precedes slicing; M0 |
| 21 | A10-R10/R11 | `service.py::_sort_key`, `_rank_snapshot`, `_list_admitted` | `test_complete_snapshot_is_sorted_and_competition_ranked_before_slice`; `test_provider_order_cannot_change_final_order_or_rank`; `test_continuation_passes_cursor_snapshot_sequence_and_absolute_offset` | O5 | PASS | Exact-float ties; stable `1,1,3`; M0 |
| 22 | A10-R6/R10 | `service.py::_rank_snapshot`, `_new_row`, `_list_admitted` | `test_one_row_is_emitted_for_each_provider_approved_candidate`; `test_public_allowlist_has_no_identity_time_diagnostics_or_economics` | O7 | PASS | No participant aggregation/decay/count/history/fee order; X1/X2, M0 |
| 23 | A10-R8/R10/R12/R13 | `service.py::_copy_candidate`, `_copy_snapshot`, `list_entries` | `test_forged_ineligible_provider_candidate_rejects_whole_snapshot`; `test_duplicate_provider_identity_rejects_the_complete_snapshot`; `test_mixed_challenge_or_pack_snapshots_fail_without_partial_page`; `test_hostile_nested_values_fail_without_repr_equality_or_hashing` | O3/O5/O7 | PASS | Whole-operation failure only; X6, M0 |
| 24 | A10-R5 | `model.py::FixtureLeaderboardRow`; `service.py::_new_row` | `test_exact_package_exports_fields_and_root_namespace`; `test_public_row_and_page_exact_invariants`; `test_public_allowlist_has_no_identity_time_diagnostics_or_economics` | O3/O5 | PASS | Exact positive row allow-list; X1/X2, M0 |
| 25 | A10-R5/R11 | `model.py::FixtureLeaderboardPage`; `service.py::_new_page`, `_list_admitted` | `test_exact_package_exports_fields_and_root_namespace`; `test_public_row_and_page_exact_invariants`; `test_first_page_provider_arguments_call_count_and_owned_projection`; `test_exact_none_is_unavailable_but_empty_snapshot_is_success`; `test_empty_page_response_charge_is_exact` | O3/O5 | PASS | Exact page allow-list; available empty snapshot succeeds; X0/X2, M0 |
| 26 | A10-R4/R5/R6/R13 | Private candidate/cursor reprs; public row/page/error projections | `test_candidate_preserves_exact_score_and_pack_but_hides_private_ids`; `test_no_provider_owned_private_alias_is_reachable_from_success`; `test_cursor_and_public_representations_contain_no_hidden_material` | O7 | PASS | Submission/result identity absent from public graphs; X1/X2, M0 |
| 27 | A10-R5/R6/R9/R13 | Exact row/page allow-list fields | `test_public_allowlist_has_no_identity_time_diagnostics_or_economics`; `test_cursor_and_public_representations_contain_no_hidden_material` | O5/O6/O7 | PASS | Identity/time/diagnostic/economic/history/provider fields omitted; X1/X2, M0 |
| 28 | A10-R6 | Service/request/row/page surfaces; no `RequesterIdentity` import | `test_service_constructor_signature_and_only_public_operation`; `test_public_allowlist_has_no_identity_time_diagnostics_or_economics`; `test_source_has_no_private_owner_or_deferred_authority_dependency` | O7 | PASS | No authentication/identity filtering/anonymization/correlation; X1, M0 |
| 29 | A10-R1/R7/R14 | All leaderboard imports/public fields | `test_public_allowlist_has_no_identity_time_diagnostics_or_economics`; `test_dependency_import_and_runtime_escape_policy`; `test_service_owns_no_cache_store_history_or_background_state` | - | PASS | No timestamp/current-time access; X1/X3, M0 |
| 30 | A10-R7 | `model.py::PublicationSequence`, `LeaderboardSnapshotSequence`; sequence copy helpers | `test_sequences_require_exact_nonnegative_u64`; `test_first_page_provider_arguments_call_count_and_owned_projection`; `test_continuation_passes_cursor_snapshot_sequence_and_absolute_offset` | O7 | PASS | No wall-clock/chain/finality/lifecycle/settlement meaning; X0/X1, M0 |
| 31 | A10-R3/R7 | Sequence copy helpers; provider seam | `test_first_page_provider_arguments_call_count_and_owned_projection`; `test_continuation_passes_cursor_snapshot_sequence_and_absolute_offset`; `test_source_has_no_private_owner_or_deferred_authority_dependency` | O7 | PASS | Copies/validates provider values only; no generator; M0 |
| 32 | A10-R11 | `model.py::_CURSOR_FIELDS`, `LeaderboardCursor`, `_encode_cursor`, `_decode_cursor`; `service.py::_copy_request_cursor`, `_new_cursor`, `_response_utf8_bytes` | `test_cursor_has_exact_schema_fields_board_literal_and_canonical_encoding`; `test_continuation_passes_cursor_snapshot_sequence_and_absolute_offset`; `test_incoming_cursor_obeys_both_bounds_before_provider_invocation`; `test_emitted_cursor_obeys_both_cursor_and_string_byte_limits`; `test_incoming_cursor_is_excluded_from_response_meter`; `test_emitted_cursor_is_charged_once_without_decoded_payload_duplication` | O3 | PASS | Logical opaque cursor; no wire/crypto authority; X5, M0 |
| 33 | A10-R11/R13 | Cursor field encoder and opaque repr | `test_cursor_and_public_representations_contain_no_hidden_material`; `test_cursor_has_exact_schema_fields_board_literal_and_canonical_encoding` | O3/O7 | PASS | No identity/hidden/time/path/provider content; X1/X2/X5, M0 |
| 34 | A10-R5/R11 | `model.py::FixtureLeaderboardPage`; `service.py::_list_admitted` | `test_one_row_is_emitted_for_each_provider_approved_candidate`; `test_complete_snapshot_is_sorted_and_competition_ranked_before_slice`; `test_continuation_passes_cursor_snapshot_sequence_and_absolute_offset`; `test_terminal_offset_is_allowed_but_offset_beyond_snapshot_is_invalid` | - | PASS | No total count/page-size binding/end cursor; M0 |
| 35 | A10-R3/R11/R12 | `service.py::_list_admitted` exact-`None` branch | `test_exact_none_is_unavailable_but_empty_snapshot_is_success`; `test_missing_first_or_stale_continuation_have_the_same_unavailable_error` | - | PASS | No existence oracle; unavailable differs from empty fixture board; X6, M0 |
| 36 | A10-R1/R11/R14 | `service.py::FixtureLeaderboardService.__slots__`; import graph | `test_service_owns_no_cache_store_history_or_background_state`; `test_dependency_import_and_runtime_escape_policy` | - | PASS | No durable state/filesystem/scheduler/time; X3, M0 |
| 37 | A10-R3/R11 | Provider retention seam; `service.py::_copy_snapshot`, `_list_admitted` | `test_continuation_cannot_drift_or_fall_forward`; `test_continuation_passes_cursor_snapshot_sequence_and_absolute_offset`; `test_exact_none_is_unavailable_but_empty_snapshot_is_success`; `test_provider_snapshot_mutation_after_return_cannot_change_page`; `test_continuation_provider_cannot_mutate_retained_cursor_sequence` | - | PASS | Provider owns bounded retained snapshots; X3/X6, M0 |
| 38 | A10-R3/R11/R13 | Resource-limit model; UTF-8, response-meter, concurrency helpers | `test_each_resource_limit_requires_exact_positive_u64`; `test_page_size_and_snapshot_row_bounds_are_exact`; `test_utf8_capacity_counts_exact_valid_scalar_widths`; `test_string_limit_is_per_occurrence_and_exact_at_boundary`; `test_emitted_cursor_obeys_both_cursor_and_string_byte_limits`; `test_exact_response_formula_repeated_occurrences_and_one_byte_over`; `test_identity_shared_strings_are_still_charged_per_occurrence`; `test_empty_page_response_charge_is_exact`; `test_incoming_cursor_is_excluded_from_response_meter`; `test_emitted_cursor_is_charged_once_without_decoded_payload_duplication`; `test_fixed_errors_are_not_recursively_response_metered`; `test_capacity_is_nonblocking_precedes_internal_copy_and_releases`; `test_capacity_is_restored_after_translated_and_propagated_failures` | O3/O5/O7 | PASS | Logical success-page meter only; permits always released; X3/X5, M0 |
| 39 | A10-R12 | `model.py::LeaderboardError` and four direct subclasses | `test_error_hierarchy_and_fixed_nonserializable_payloads`; `test_error_base_is_the_only_additional_exception_type` | - | PASS | No intermediate/extra/NotFound error; X2, M0 |
| 40 | A10-R12 | Four error classes' fixed code/message descriptors | `test_error_hierarchy_and_fixed_nonserializable_payloads` | - | PASS | Exact fixed non-diagnostic pairs; X2, M0 |
| 41 | A10-R12/R13 | Fixed errors and service translation boundary | `test_error_hierarchy_and_fixed_nonserializable_payloads`; `test_provider_exception_repr_and_str_are_never_invoked`; `test_every_provider_exception_becomes_a_new_integration_error` | - | PASS | No echo/rendering/context/cause/private attachment/oracle; X2, M0 |
| 42 | A10-R3/R12/R13 | `service.py::_invoke_provider`, `_list_admitted`, `list_entries` | `test_exact_none_is_unavailable_but_empty_snapshot_is_success`; `test_every_provider_exception_becomes_a_new_integration_error`; `test_non_exception_baseexceptions_propagate_unchanged`; `test_capacity_is_restored_after_translated_and_propagated_failures` | - | PASS | Ordinary `Exception` collapses; non-`Exception` propagates; X6, M0 |
| 43 | A10-R3/R13 | All hostile capture/copy helpers and provider call boundary | `test_missing_uncallable_and_subclassed_provider_results_fail_closed`; `test_provider_descriptor_failure_is_translated_only_at_call_time`; `test_hostile_nested_values_fail_without_repr_equality_or_hashing`; `test_missing_and_container_substituted_provider_fields_fail_closed`; `test_non_exception_baseexceptions_propagate_unchanged`; `test_dependency_import_and_runtime_escape_policy` | O3/O5/O7 | PASS | Exact nominal rejection without exact-typing provider; no `except BaseException`; X2, M0 |
| 44 | A10-R3/R13 | Frozen/slotted models; fresh-copy helpers; admission/release | `test_nominal_values_are_frozen_slotted_and_have_no_instance_dictionary`; `test_provider_snapshot_mutation_after_return_cannot_change_page`; `test_provider_mutation_during_callback_cannot_change_owned_request`; `test_continuation_provider_cannot_mutate_retained_cursor_sequence`; `test_reentrant_provider_callback_is_bounded_without_deadlock`; `test_no_provider_owned_private_alias_is_reachable_from_success` | - | PASS | No provider alias/mutable leakage/deadlock/capacity loss; X2, M0 |
| 45 | A10-R4/R5/R13 | `model.py::_NoSerialization`; private reprs; explicit projections/meter | `test_nominal_values_reject_generic_pickle_serialization`; `test_candidate_preserves_exact_score_and_pack_but_hides_private_ids`; `test_cursor_and_public_representations_contain_no_hidden_material`; `test_meter_uses_no_reflection_serialization_or_wire_representation`; `test_source_has_no_private_owner_or_deferred_authority_dependency` | O5/O6/O7 | PASS | No generic serialization or hidden/economic/path/time leakage; X1/X2, M0 |
| 46 | A10-R14 | Imports in all four leaderboard modules | `test_dependency_import_and_runtime_escape_policy` | O3/O5/O7 | PASS | Standard library plus exact allowed owner symbols only; X3, M0 |
| 47 | A10-R3/R14/R16 | Complete leaderboard source/import graph | `test_source_has_no_private_owner_or_deferred_authority_dependency`; `test_dependency_import_and_runtime_escape_policy`; `test_import_with_optional_and_later_dependencies_blocked` | O5/O6/O7/O8/O9 | PASS | No private/Landscape/optional/web/filesystem/time/chain dependency; X0/X2/X3, M0 |
| 48 | A10-R14 | `pyproject.toml::project.dependencies=[]`; installed package | `test_fresh_no_dependency_wheel_imports_exact_surface_outside_tree` | O3/O5/O7 | PASS | Zero mandatory dependencies; bounded installed API; X3, M0 |
| 49 | A10-R14/R16 | Root package and transitive imports | `test_import_with_optional_and_later_dependencies_blocked`; `test_fresh_no_dependency_wheel_imports_exact_surface_outside_tree` | O8/O9 | PASS | No optional-heavy/legacy/web/time/Landscape/neuron/chain/emission load; X0/X3, M0 |
| 50 | A10-R15 | Sole `tests/cpu/test_leaderboard.py` path | Exact filesystem inventory and 246-test focused collection | - | PASS | One canonical focused suite; X7, M0 |
| 51 | A10-R2/R3/R11/R12/R13/R15 | Exports, Protocol/service signatures, model/error/resource/cursor/meter/concurrency helpers | `test_exact_package_exports_fields_and_root_namespace`; `test_protocol_is_structural_and_not_runtime_checkable`; `test_service_constructor_signature_and_only_public_operation`; `test_sequences_require_exact_nonnegative_u64`; `test_each_resource_limit_requires_exact_positive_u64`; `test_nominal_subclasses_are_rejected`; `test_error_hierarchy_and_fixed_nonserializable_payloads`; `test_exact_response_formula_repeated_occurrences_and_one_byte_over`; `test_response_meter_has_exact_explicit_field_manifest_and_order`; `test_capacity_is_nonblocking_precedes_internal_copy_and_releases`; `test_dependency_import_and_runtime_escape_policy` | O3/O5/O7 | PASS | Surface/resource tests do not confer production/security qualification; X0/X5, M0 |
| 52 | A10-R4/R8/R9/R10/R15 | Candidate/snapshot copy, validation, ordering, ranking, row projection | `test_owner_nominals_are_exact_and_reconstructed`; `test_public_owner_validators_are_applied_without_coercion`; `test_forged_ineligible_provider_candidate_rejects_whole_snapshot`; `test_candidate_preserves_exact_score_and_pack_but_hides_private_ids`; `test_complete_snapshot_is_sorted_and_competition_ranked_before_slice`; `test_exact_float_equality_is_the_only_tie_rule_and_scores_are_preserved`; `test_duplicate_provider_identity_rejects_the_complete_snapshot`; `test_mixed_challenge_or_pack_snapshots_fail_without_partial_page` | O3/O5/O6/O7 | PASS | No official eligibility/cross-Challenge score/recompute/salvage; X0/X6, M0 |
| 53 | A10-R3/R11/R12/R13/R15 | Provider translation, cursor/snapshot/resource/concurrency/mutation paths | `test_exact_none_is_unavailable_but_empty_snapshot_is_success`; `test_every_provider_exception_becomes_a_new_integration_error`; `test_non_exception_baseexceptions_propagate_unchanged`; `test_capacity_is_restored_after_translated_and_propagated_failures`; `test_empty_page_response_charge_is_exact`; `test_exact_response_formula_repeated_occurrences_and_one_byte_over`; `test_fixed_errors_are_not_recursively_response_metered`; `test_continuation_cannot_drift_or_fall_forward`; `test_provider_snapshot_mutation_after_return_cannot_change_page`; `test_meter_uses_no_reflection_serialization_or_wire_representation` | O3/O7 | PASS | No oracle/wire contract/mutable alias/capacity leak; X3/X5/X6, M0 |
| 54 | A10-R5/R6/R13/R15 | Exact row/page fields; representations; explicit meter manifest | `test_public_allowlist_has_no_identity_time_diagnostics_or_economics`; `test_cursor_and_public_representations_contain_no_hidden_material`; `test_no_provider_owned_private_alias_is_reachable_from_success`; `test_response_meter_has_exact_explicit_field_manifest_and_order`; `test_meter_uses_no_reflection_serialization_or_wire_representation` | O5/O6/O7 | PASS | Future public strings require separate formula ratification; X1/X2/X5, M0 |
| 55 | A10-R14/R15 | Owner-validator calls, source imports, installed artifact | `test_public_owner_validators_are_applied_without_coercion`; `test_dependency_import_and_runtime_escape_policy`; `test_source_has_no_private_owner_or_deferred_authority_dependency`; `test_import_with_optional_and_later_dependencies_blocked`; `test_fresh_no_dependency_wheel_imports_exact_surface_outside_tree` | O3/O5/O6/O7/O8/O9 | PASS | No private owner/optional/later import; X0/X2/X3, M0 |
| 56 | A10-R15/R17 | All A10 source plus unchanged A0-A9 source/tests | Fresh full `1973 passed in 30.61s`; exact-main push CPU `1973 passed in 53.86s` | O3/O5/O6/O7/O8/O9 | PASS | Regression does not widen maturity or begin A11/A12; X7, M0 |
| 57 | A10-R15/R17 | Five focused Python paths | Fresh Ruff/Black pass; exact-main quality job `98094221851` passed with no new debt | - | PASS | Quality is engineering evidence only; X7, M0 |

### Reviewed repair families

1. `bd263c44fa955f32a28a6afd1c56ed8b9334cf11` — Challenge identity
   capacity precedes ASCII validation and A3 reconstruction in
   `service.py::_copy_request_challenge` and `_copy_provider_challenge`.
   Canonical evidence: `test_oversized_request_challenge_id_is_bounded_before_provider_call`,
   `test_oversized_request_challenge_version_has_resource_precedence`,
   `test_oversized_snapshot_challenge_precedes_candidate_access`,
   `test_oversized_candidate_challenge_rejects_the_whole_snapshot`,
   `test_oversized_challenge_never_reaches_owner_reconstruction`, and
   `test_bounded_malformed_challenge_keeps_boundary_error_mapping`.
2. `6be31d10272ac18b580a4733079318f7d3d69309` — `SubmissionId`,
   `result_id`, and scoring-pack capacity precedes A7/A3 owner validation in
   `service.py::_copy_submission_id`, `_copy_result_id`, and
   `_copy_provider_hash`. Canonical evidence:
   `test_oversized_submission_id_is_resource_safe_and_releases_capacity`,
   `test_submission_capacity_precedes_owner_construction`,
   `test_bounded_malformed_submission_id_is_integration_error`,
   `test_submission_id_capacity_boundary_is_exact_and_freshly_owned`,
   `test_oversized_result_id_is_resource_safe`,
   `test_result_capacity_precedes_owner_validator`,
   `test_bounded_malformed_result_id_is_integration_error`,
   `test_result_id_capacity_boundary_preserves_the_exact_string`,
   `test_oversized_provider_hash_has_resource_precedence`,
   `test_provider_hash_capacity_precedes_owner_validator`,
   `test_bounded_malformed_provider_hash_is_integration_error`,
   `test_provider_hash_capacity_boundary_preserves_the_exact_string`, and
   `test_provider_identifier_helpers_lock_capacity_before_owner_validation`.
3. `6f505d5cffd69f0c3d4d0e6d71bb91233c0ce6b1` — Exact valid-Unicode
   UTF-8 byte widths and dual incoming-cursor byte limits in
   `service.py::_require_utf8_capacity`, `_require_string_capacity`, and
   `_copy_request_cursor`, including all identifier/challenge callers.
   Canonical evidence: `test_utf8_capacity_counts_exact_valid_scalar_widths`,
   `test_utf8_capacity_stops_after_the_first_over_limit_scalar`, all multibyte
   identifier/challenge tests
   (`test_multibyte_submission_id_is_resource_safe_before_reconstruction`,
   `test_multibyte_result_id_is_resource_safe_before_owner_validation`,
   `test_multibyte_provider_hash_is_resource_safe_before_digest_validation`,
   and `test_multibyte_challenge_identity_is_bounded_before_owner_validation`),
   both multibyte incoming-cursor tests
   (`test_multibyte_incoming_cursor_obeys_each_utf8_byte_limit` and
   `test_multibyte_incoming_cursor_exact_byte_boundary_reaches_ascii_rule`),
   `test_nonencodable_string_is_safe_and_releases_concurrency_capacity`, and
   `test_utf8_capacity_source_policy_and_ascii_len_guards`.

## Canonical focused test command

~~~text
pytest tests/cpu/test_leaderboard.py -q
~~~

The sole canonical focused suite exists at this exact path and passes on current
main. No second leaderboard test path exists.

## Exact closeout maturity ceiling

~~~text
A10 SPECIFIED / RATIFIED:
YES

A10 IMPLEMENTED:
YES on current main only for the exact bounded in-process fixture leaderboard

A10 TESTED:
YES only for the exact recorded CPU, hostile-input, resource, concurrency,
leakage, dependency, import, wheel, and quality engineering scope, including
all reviewed repairs

A10 SCIENTIFICALLY_QUALIFIED:
NO

A10 SECURITY_QUALIFIED:
NO

A10 NETWORK_QUALIFIED:
NO

A10 COMMERCIALLY_VALIDATED:
NO

A10 PRODUCTION_QUALIFIED:
NO

A10 WAVE STATUS:
done only after this closeout is independently reviewed, explicitly
human-authorized, and normally merged

A11:
todo

A12:
todo
~~~

The checked boxes record already-merged implementation truth. They become
authoritative closeout state only after this documentation-only closeout is
independently reviewed, explicitly human-authorized, and normally merged.

## Explicitly deferred

A10 does not provide or authorize:

- a production provider or publication feed;
- an official leaderboard;
- a LIVE leaderboard;
- public identity or authentication;
- hotkey publication;
- anonymization;
- timestamp publication;
- durable persistence;
- HTTP, REST, GraphQL, HTML, or network transport;
- official score precision or cadence;
- adaptive-query security qualification;
- cross-Challenge ranking;
- global ranking;
- FrontierRecord;
- FrontierAdvanceEvent;
- frontier nomination authority beyond informational rank;
- Product Qualification;
- commercial ranking;
- settlement;
- treasury;
- chain;
- Bittensor;
- weights;
- emissions;
- A11 logging or metrics;
- A12 aggregate invariant work;
- scientific qualification;
- security qualification;
- network qualification;
- commercial validation; or
- production qualification.

Production remains fail closed.

## Must not

Do not turn fixtures, stubs, mocks, priors, estimates, scaffolds, historical
validator state, Landscape output, legacy HTML, or legacy emission mechanics
into an official board. Do not infer any qualification or production readiness
from the bounded implementation and engineering-test evidence recorded here.
