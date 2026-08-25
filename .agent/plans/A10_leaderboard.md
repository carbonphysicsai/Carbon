# A10 — bounded fixture leaderboard contract and future implementation plan

**Ticket:** .agent/tickets/A10_leaderboard.md
**Wave status:** todo
**Document status:** documentation-only contract candidate
**Starting main:** f308281e69580216d5ebf5ec94a9d6c069cf1a56
**Starting tree:** a2875c0b12caf7d4c07316626c218c55f3eb77ea
**Starting subject:** Merge pull request #35 from carbonphysicsai/agent/a9-closeout

## 1. Purpose and authority

This plan proposes the exact bounded Wave-A A10 contract. The contract becomes
ratified only after independent review, explicit human authorization, and
normal merge of the documentation candidate. It does not implement or test
A10, create leaderboard data, or authorize A11/A12.

Authority was applied in this order:

1. current repository and code;
2. current authoritative specifications;
3. ratified .agent/DECISIONS.md;
4. current maturity ledgers;
5. current orientation and rationale documents;
6. historical handoffs;
7. legacy code and archives as archaeology only.

SPECIFIED, IMPLEMENTED, TESTED, SCIENTIFICALLY_QUALIFIED,
SECURITY_QUALIFIED, NETWORK_QUALIFIED, COMMERCIALLY_VALIDATED, and
PRODUCTION_QUALIFIED remain independent states. Specification and documentation
tests are not implementation or runtime-test evidence.

The current source contains only the A0 package marker:

~~~text
carbon/leaderboard/__init__.py
    Public leaderboard projection boundary; publication behavior is deferred.
~~~

No A10 plan, model, provider, service, focused test, fixture, publication data,
or current official feed exists at the starting tree.

## 2. Reconciliation and conflict taxonomy

### NO_CONFLICT

The bounded contract below agrees with current authority that:

- public disclosure is positive and allow-listed;
- ranking is bound to one exact Challenge and Challenge scores are not globally
  comparable by default;
- evidence eligibility and mandatory admissibility precede ranking;
- prior, estimate, light, mock, fee, payment, sponsor, and customer-value
  inputs do not become official scientific score;
- fixture/stub values cannot become LIVE, production, frontier, settlement, or
  emission authority;
- a leaderboard rank is neither a FrontierRecord, FrontierAdvanceEvent, Product
  Qualification, nor commercial rank;
- rank may nominate under a separately authorized future policy, but ordinary
  A10 ranking creates no frontier event;
- A5 owns score semantics, A6 owns its private store/card boundary, A7 owns
  submission lifecycle, and A10 owns only the bounded projection defined here.

### DOCUMENTATION_LAG

The pre-ratification A10 ticket is stale shorthand. Its list-or-get operation,
hotkey-or-anonymized identity, timestamp, optional fixture/official switch, old
test path, and underspecified field list do not define the exact Wave-A
boundary. Build Out's broad public-leaderboard language and the existing
high-level ledger statement that A10 is specified likewise do not establish
this exact service/provider/snapshot/error/resource contract.

This candidate narrows that shorthand prospectively. It does not rewrite
unrelated history or claim that the exact contract was previously implemented
or tested.

### IMPLEMENTATION_LAG

The canonical carbon.leaderboard package is only a reserved marker. No A10
source or test implements the detailed contract. The maturity result remains
IMPLEMENTED: NO and TESTED: NO.

### MIGRATION_REQUIRED

Historical scripts/generate_leaderboard.py, scripts/generate_score_data.py,
legacy validator code, carbon/emission mechanics, Landscape/specialist
prototypes, examples, and archived REST/GraphQL/HTML/chain descriptions are not
A10 authority. They use incompatible wallet/hotkey identity, generated data,
current time, filesystem/HTML publication, global or multi-Challenge views,
improvement/win-rate/submission-count fields, mutable leader state, score
adjustment, breakthrough, stipend, weight, or emission behavior.

They remain archaeology or superseded reference. Any attempt to promote them
into canonical A10 would require explicit migration or replacement under a
separate task. Their existence is not a competing A10 implementation and they
must not be imported, wrapped, or repaired by the bounded implementation.

### NEW_OWNER_DECISION_REQUIRED

No new owner decision is required for the exact fixture-only engineering
contract below. Production feed selection, official publication, identity,
anonymization, time/cadence, adaptive-query policy, frontier policy,
qualification, commercial ranking, settlement, network, and production limit
values remain explicitly deferred and fail closed rather than guessed.

## 3. Decisions proposed for ratification

### A10-R1 — Scope: bounded in-process fixture projection only

Wave-A A10 is one bounded in-process fixture leaderboard projection. It has no:

- HTTP, REST, GraphQL, MCP, web UI, or HTML surface;
- filesystem or object-store publication;
- network server or remote transport;
- chain, Bittensor, weight, or emission access;
- persistence, durable cache, database, scheduler, or background refresh;
- current-time or wall-clock behavior;
- official or LIVE leaderboard authority.

The service does not manufacture fixture publication data. Trusted composition
injects a fixture provider. If a future official publication feed is absent,
the official board is unavailable; absence must never be represented as an
empty authoritative board.

Wave A makes no scientific, security, network, commercial, or production
qualification claim.

### A10-R2 — Nominal fixture-only type family

The future implementation uses nominal A10 fixture-only types. The recommended
type family is:

~~~text
PublicationSequence
LeaderboardSnapshotSequence
LeaderboardCursor
ListFixtureLeaderboardRequest
FixtureLeaderboardCandidate
FixtureLeaderboardCandidateSnapshot
FixtureLeaderboardRow
FixtureLeaderboardPage
FixtureLeaderboardResourceLimits
FixtureLeaderboardProvider
FixtureLeaderboardService
LeaderboardError
LeaderboardRequestError
LeaderboardResourceError
LeaderboardUnavailableError
LeaderboardIntegrationError
~~~

The exact reviewed implementation export tuple must contain only the authorized
public A10 types and no aliases.

There is no caller-supplied mode="fixture|official" string, generic service,
generic provider, or official-provider alias. Future official publication
requires a separate contract, separate nominal provider/service/publication
types, and separate qualification evidence.

Nominal dataclasses/value objects are immutable, slotted where appropriate, and
reject subclasses or coercible lookalikes whenever the contract requires exact
types. Exact built-in type rules reject bool as int and custom int/float/str
subclasses.

### A10-R3 — One service operation

The only operation is:

~~~python
FixtureLeaderboardService.list_entries(
    request: ListFixtureLeaderboardRequest,
) -> FixtureLeaderboardPage
~~~

The request contains exactly the semantics needed to bind:

- one exact A3 ChallengeKey;
- one exact positive built-in page_size;
- one opaque LeaderboardCursor or None.

The exact request and cursor representation remain A10-owned and resource
bounded. The operation does not accept a requester, identity, mode, raw
snapshot sequence, scoring-pack selector, order selector, filter graph, or
provider object.

Not ratified:

- get(submission_id);
- global or all-Challenge listing;
- cross-Challenge comparison or normalization;
- requester or identity filtering;
- hotkey, wallet, participant, SubmissionId, or result lookup;
- score-threshold search;
- timestamp or time-range search;
- caller-selected scoring pack, snapshot, rank policy, or official mode.

### A10-R4 — Injected fixture publication provider

The recommended provider protocol has one operation:

~~~python
FixtureLeaderboardProvider.get_snapshot(
    challenge_key: ChallengeKey,
    snapshot_sequence: LeaderboardSnapshotSequence | None,
) -> FixtureLeaderboardCandidateSnapshot
~~~

The provider supplies one exact separately ratified fixture publication
projection through trusted composition. The first-page call supplies None;
cursor continuation supplies the cursor-bound exact snapshot sequence after the
cursor itself has passed A10 validation.

The provider, not A10, owns:

- selecting provider-approved published candidates;
- excluding unpublished, cancelled, withdrawn, superseded, and stale records;
- consulting exact A3 fixture eligibility;
- copying only authorized A5/A6/A7 fields;
- assigning PublicationSequence values;
- assigning LeaderboardSnapshotSequence values;
- retaining exact immutable snapshots required by active cursors;
- retry, republication, withdrawal, and supersession selection.

A10 never inspects, imports, or enumerates:

- A5 InternalResult, ScoreEngine, ScoreInput, gates, legs, or private pack
  objects;
- A6 CardStore or private records;
- A7 private stores, private records, fee events, attempts, or enumeration;
- A8 private requests, handles, outcomes, backend material, or execution state;
- A9 priors, estimates, scaffolds, mock outputs, service state, or result
  feedback;
- Landscape, legacy validator, emission, chain, or Bittensor state.

No A6 or A7 change is part of A10. A future official provider/feed is
unratified.

An unavailable provider state, including an absent or stale requested fixture
snapshot, maps to LeaderboardUnavailableError. If a provider returns a
purported snapshot whose shape, field values, isolation, or eligibility
contract is malformed, the whole operation maps to
LeaderboardIntegrationError. A10 never salvages a partial provider response.

### A10-R5 — Provider-only candidate projection

FixtureLeaderboardCandidate has only these provider-integration semantics:

| Field | Exact contract |
|---|---|
| submission_id | exact A7 SubmissionId |
| result_id | exact built-in string satisfying the bounded A6 public result-identifier contract |
| challenge_key | exact A3 ChallengeKey |
| scoring_pack_hash | exact A6 public score-pack hash |
| score_status | exact A5 ScoreStatus |
| overall_score | exact finite built-in float |
| mandatory_gates_passed | exact built-in bool |
| fixture_origin | exact built-in bool |
| eligible_for_emission | exact built-in bool |
| publication_sequence | exact PublicationSequence |

The candidate snapshot binds:

- one exact ChallengeKey;
- one exact scoring_pack_hash;
- one exact LeaderboardSnapshotSequence;
- one exact immutable tuple of FixtureLeaderboardCandidate values.

The provider boundary reconstructs/copies each authorized value; A10 then
reconstructs it again into A10-owned immutable values before use. No provider
object or mutable alias is reachable from a public result.

submission_id and result_id exist only for provider integration validation and
duplicate detection. They never appear in a public row, page, cursor, error,
representation, cache value, or other reachable response graph.

This projection is not:

- a second SubmissionId or identity mint;
- a submission lifecycle or A7 state machine;
- a scoring engine or score authority;
- a second card schema;
- a publication database or store;
- evidence, receipt, frontier, settlement, or emission state.

### A10-R6 — Exact public row and page allow-lists

FixtureLeaderboardRow exposes exactly:

| Field | Meaning |
|---|---|
| rank | exact positive built-in competition rank |
| challenge_key | exact copied ChallengeKey |
| scoring_pack_hash | exact provider-supplied A5/A6 hash |
| overall_score | exact finite built-in A5/A6 score |
| mandatory_gates_passed | exactly True for every row |
| publication_sequence | exact copied PublicationSequence |
| fixture_origin | exactly True |
| eligible_for_emission | exactly False |

FixtureLeaderboardPage exposes exactly:

| Field | Meaning |
|---|---|
| schema_version | exact fixed A10 page-schema value |
| challenge_key | exact copied request/snapshot ChallengeKey |
| scoring_pack_hash | exact snapshot hash |
| snapshot_sequence | exact copied LeaderboardSnapshotSequence |
| rows | immutable tuple of FixtureLeaderboardRow values |
| next_cursor | opaque LeaderboardCursor or None |
| fixture_origin | exactly True |
| eligible_for_emission | exactly False |

The response exposes no total row count.

The following are explicitly omitted from rows, pages, cursors, errors, reprs,
or any reachable public representation:

- requester;
- hotkey or wallet;
- public participant ID;
- anonymized or pseudonymous ID;
- SubmissionId or result_id;
- timestamp or age;
- component scores;
- gate IDs, optional-gate outcomes, or gate counts;
- failure tags or private diagnostics;
- margins or stress values;
- fee, payment, sponsor, reward, or customer-value fields;
- rank delta or improvement history;
- submission count or win rate;
- data-source labels;
- provider metadata or provider objects.

There is no generic serialization of provider/A5/A6/A7 objects. Public
construction is field-by-field from the positive A10 allow-list.

### A10-R7 — Identity is not an A10 public concept

Current A7 RequesterIdentity is a structural requester binding only. It is not:

- authentication proof;
- a credential, signature, wallet, or public hotkey;
- a participant identity;
- an A10 filter or grouping key.

Wave A exposes no participant field, performs no anonymization, and implements
no best-per-requester or best-per-hotkey policy. It does not invent an
anonymization key, stability period, rotation policy, or cross-Challenge
correlation policy.

### A10-R8 — No time; provider-owned nominal sequences

A10 exposes no timestamp and imports/calls no current-time facility.

PublicationSequence and LeaderboardSnapshotSequence are provider-owned nominal
non-negative integer value types. Exact built-in integers are required;
booleans and subclasses are rejected. Their values are monotonic only within
one exact fixture Challenge publication stream.

The sequences carry no:

- wall-clock or elapsed-time meaning;
- chain height, epoch, block, finality, or reorg meaning;
- A7 lifecycle/attempt meaning;
- publication timestamp or retention deadline;
- frontier, settlement, weight, or emission meaning.

A10 copies and validates these sequences but never generates, increments,
repairs, normalizes, or infers them.

### A10-R9 — Eligibility is conjunctive and fail closed

A candidate may rank only when all of the following hold:

1. score_status is exactly ScoreStatus.SCORED;
2. mandatory_gates_passed is exactly True;
3. overall_score is an exact built-in float;
4. overall_score is finite;
5. 0.0 <= overall_score <= 1.0;
6. fixture_origin is exactly True;
7. eligible_for_emission is exactly False;
8. candidate ChallengeKey exactly equals the request and snapshot key;
9. candidate scoring_pack_hash exactly equals the snapshot hash;
10. submission_id is unique across the whole snapshot;
11. result_id is unique across the whole snapshot;
12. publication_sequence is unique across the whole snapshot.

Excluded:

- ScoreStatus.MANDATORY_GATE_FAILED;
- ScoreStatus.PACK_NOT_READY;
- unpublished results;
- cancelled or withdrawn results;
- superseded or stale results;
- infrastructure-incomplete results;
- mock, prior, estimate, or scaffold values;
- fee, payment, sponsor, reward, and customer-value inputs.

The provider owns lifecycle/publication selection. A10 independently validates
the authorized projection. A purported snapshot with an ineligible or
inconsistent candidate is malformed provider output and fails as one
LeaderboardIntegrationError; no partial page or silently filtered salvage
survives.

A mandatory-gate failure never becomes an ordinary ranked score of zero. No
current result is eligible for an official board.

### A10-R10 — A5 is sole score and gate authority

A10 consumes exact overall_score and scoring_pack_hash values supplied through
the provider projection. It does not inspect A5 private objects.

A10 must not:

- compute or recompute a score;
- normalize or cross-normalize scores;
- aggregate components or gates;
- rescale, clamp, round, or quantize;
- predict, estimate, smooth, decay, or impute;
- use fees, payments, priors, mock values, customer value, or competitor
  population as score inputs.

Primary ordering is overall_score descending. Fixture scores retain their exact
binary64 precision. Official score precision, display precision, cadence, and
adaptive-query controls remain deferred.

The only public gate summary is mandatory_gates_passed=True. Gate IDs,
optional-gate outcomes, failed-gate counts, component scores, failure tags,
margins, stress values, and diagnostics remain private.

### A10-R11 — Deterministic order, competition ties, and duplicates

Order and rank are exact:

1. primary sort key: overall_score descending;
2. exact built-in float equality creates a tie;
3. tied rows share a competition rank;
4. the next rank skips occupied places: 1, 1, 3;
5. publication_sequence ascending deterministically orders tied rows;
6. tie ordering does not change the shared rank.

The service emits one row per provider-approved published submission. It does
not implement:

- best per requester/hotkey/participant;
- participant aggregation;
- score decay;
- win rate or submission count;
- rank delta or improvement history;
- fee/reward/payment ordering;
- retry/republication/withdrawal/supersession policy.

Duplicate SubmissionId, result_id, or PublicationSequence fails the entire
snapshot. Mixed ChallengeKey or scoring_pack_hash fails the entire snapshot.
Malformed candidate order supplied by the provider is irrelevant because A10
applies the exact deterministic order after full snapshot validation. No partial
page survives any malformed provider output.

### A10-R12 — Snapshot-bound opaque pagination and resources

ListFixtureLeaderboardRequest binds:

- exact ChallengeKey;
- exact positive built-in page_size;
- opaque LeaderboardCursor or None.

FixtureLeaderboardResourceLimits is injected at construction and contains exact
positive built-in bounds for:

- maximum page size;
- maximum snapshot rows;
- maximum cursor bytes;
- maximum string bytes;
- maximum response bytes;
- maximum concurrent calls.

No production numeric value is ratified here. Missing production values keep a
future production surface unavailable.

The cursor binds only:

- exact cursor schema;
- fixture-board discriminator fixed structurally by the service type;
- exact ChallengeKey;
- exact scoring_pack_hash;
- exact LeaderboardSnapshotSequence;
- exact non-negative next offset.

The cursor contains no:

- submission_id or result_id;
- requester, hotkey, wallet, participant, or other identity;
- seed, derived seed, draw, role, domain, context, or entropy;
- hidden or private Score Pack material;
- timestamp, expiry, path, filesystem detail, or provider object.

Cursor encoding is opaque to callers and uses only an explicit A10-owned,
bounded, public-safe field encoding. No cryptographic authentication,
confidentiality, durability, or production-security claim is inferred.

The service owns no durable cache, database, filesystem store, scheduler,
background refresh, current-time lookup, or wall-clock expiry. The provider
owns bounded in-process retention of exact immutable fixture snapshots needed
by active cursors.

A cursor continuation must resolve the same exact snapshot. Missing and stale
retained snapshots map to the same LeaderboardUnavailableError. A10 does not
fall forward to a newer snapshot, recompute old pages, or expose whether a
particular hidden result once existed.

Resource validation is fail closed. Oversized request/cursor/snapshot/string/
response state and exhausted concurrent-call capacity map to the stable
resource error before a partial response escapes.

### A10-R13 — Fixed safe error hierarchy

The future hierarchy is exactly:

~~~text
LeaderboardError

LeaderboardRequestError
    code: leaderboard.request.invalid
    message: Leaderboard request is invalid.

LeaderboardResourceError
    code: leaderboard.resource.exhausted
    message: Leaderboard resource limit was exceeded.

LeaderboardUnavailableError
    code: leaderboard.fixture.unavailable
    message: Fixture leaderboard is unavailable.

LeaderboardIntegrationError
    code: leaderboard.integration.failed
    message: Leaderboard provider response is invalid.
~~~

Every error:

- uses its exact fixed code and message;
- never echoes request, cursor, Challenge, score, identifier, or provider value;
- never invokes hostile repr or str;
- has no exposed cause or context chain;
- attaches no provider object or private diagnostic;
- provides no NotFound subtype or distinction;
- provides no existence oracle.

Request shape/type/cursor-binding failures map to LeaderboardRequestError.
Configured resource-limit failures map to LeaderboardResourceError. Absent,
stale, unpublished, or otherwise unavailable provider state maps to the same
LeaderboardUnavailableError. A returned purported snapshot with invalid shape,
types, values, duplicates, mixed keys/hashes, or ineligible candidates maps to
LeaderboardIntegrationError and fails the whole operation.

### A10-R14 — Hostile input, copying, mutation, and leakage

Caller and provider values are hostile until fully captured and revalidated.
The implementation requires:

- exact-type and subclass rejection;
- bounded field access and bounded container traversal;
- no duck-typing or generic coercion;
- no hostile value interpolation into exceptions/logs/reprs;
- full snapshot validation before sorting or slicing;
- fresh reconstruction of nominal values;
- immutable tuples for snapshot and page membership;
- no provider-owned list/dict/tuple/object alias in a response;
- resistance to mutation between observations;
- safe behavior under reentrant objects and provider callbacks;
- construction-time capture of resource policy;
- bounded concurrent-call accounting with release on every outcome;
- one whole-operation failure with no partial page.

Generic serialization of A5, A6, A7, provider, legacy, or store objects is
forbidden.

The following must not leak through rows, pages, cursors, errors, reprs, cache
objects, captured aliases, or any generic representation:

- official or fixture seeds and derived seeds;
- draw IDs, roles, domains, contexts, entropy, nonces, or evaluation bindings;
- hidden/private pack material;
- margins, stress values, component scores, gate details, diagnostics, or
  failure tags;
- fees, payments, sponsors, rewards, or commercial values;
- filesystem paths, environment values, private timestamps, or provider
  internals;
- requester, SubmissionId, result_id, hotkey, wallet, or hidden participant
  identity.

### A10-R15 — Minimal dependency boundary

The smallest future layout is:

~~~text
carbon/leaderboard/
    __init__.py
    model.py
    providers.py
    service.py
~~~

Allowed future imports:

- Python standard library;
- carbon.registry.ChallengeKey;
- carbon.scoring.ScoreStatus;
- carbon.fees.SubmissionId.

Forbidden future imports include:

- carbon.scoring.InternalResult or ScoreEngine;
- carbon.cards.CardStore or any A6 private record/store implementation;
- A7 private store, private records, enumeration, fee, or lifecycle internals;
- carbon.traineval objects;
- carbon.mcp service, providers, estimates, priors, scaffolds, responses, or
  mock outputs;
- carbon.landscape or historical Landscape/specialist code;
- carbon.emission, carbon.chain, neurons, Bittensor, weights, or settlement;
- optional scientific/numeric dependencies;
- HTTP, REST, GraphQL, web, or HTML frameworks;
- filesystem, environment, scheduler, or current-time modules.

The implementation preserves zero mandatory package dependencies. A fresh
no-dependency wheel must import the exact A10 public API from outside the source
tree without loading forbidden optional-heavy, web, HTML, filesystem, time,
Landscape, neuron, Bittensor, chain, weight, or emission modules.

### A10-R16 — Canonical future test contract

The sole focused test path is:

~~~text
tests/cpu/test_leaderboard.py
~~~

This documentation task does not create or modify it.

The later implementation suite must cover at least:

#### Surface and exact types

- exact export tuple and no aliases;
- exact service constructor and sole list_entries operation;
- request, limits, cursor, sequences, candidate, snapshot, row, and page
  construction;
- exact built-in values, subclass rejection, bool/int separation, and
  non-coercion;
- fixture nominal separation and rejection of generic/official mode strings.

#### Provider and upstream ownership

- exact provider call count and arguments for first and continuation pages;
- provider absence/unavailability;
- malformed return type and nested field failures;
- exact A3 ChallengeKey and scoring-pack isolation;
- no A5/A6/A7/A8/A9 private object/store enumeration or serialization;
- provider-owned sequence and snapshot-retention behavior;
- no A6/A7 mutation or bypass.

#### Eligibility and score integrity

- every conjunctive eligibility predicate;
- SCORED-only ranking;
- mandatory-gate failure and PACK_NOT_READY exclusion;
- infrastructure/mock/prior/estimate/scaffold/fee/payment exclusion;
- exact finite built-in float and [0.0, 1.0] bounds;
- exact score/hash preservation and absence of normalization, rounding, or
  recomputation;
- fixture_origin=True and eligible_for_emission=False;
- no current result eligible for an official board.

#### Ordering, ties, and malformed snapshots

- descending overall_score order;
- exact float equality;
- competition ranks 1, 1, 3;
- publication_sequence ascending tie order without rank change;
- one row per provider-approved published submission;
- duplicate SubmissionId, result_id, and PublicationSequence rejection;
- mixed ChallengeKey/hash rejection;
- no partial page after any malformed provider output;
- no participant aggregation, decay, win rate, history, or fee ordering.

#### Pagination and resources

- positive exact page size and maximum-page enforcement;
- exact cursor schema/board/key/hash/snapshot/offset binding;
- cursor byte and string bounds;
- stable continuation over one retained immutable snapshot;
- stale and missing snapshot collapse;
- no silent move to a newer snapshot;
- maximum snapshot rows and response bytes;
- maximum concurrent calls, rejection at capacity, and capacity release after
  success and every failure;
- no total row count.

#### Errors and no existence oracle

- exact hierarchy, codes, and messages;
- no value echo;
- no hostile repr/str;
- no cause/context chain;
- no NotFound distinction;
- absent/stale/unpublished/ineligible provider-state collapse;
- malformed provider output integration collapse;
- indistinguishable protected existence cases.

#### Mutation, reentrancy, and leakage

- caller mutation before/during/after capture;
- provider mutation before/during/after return;
- tuple/list/dict/object alias and subclass traps;
- reentrant properties, iteration, equality, hashing, repr, and str traps;
- immutable copied rows/pages/cursors/snapshots;
- exact positive row/page field allow-lists;
- absence of submission/result/requester/hotkey/wallet/participant IDs;
- absence of seeds, draws, roles, domains, contexts, entropy, hidden packs,
  components, gate details, diagnostics, margins, stress, fees, paths,
  timestamps, and provider objects;
- safe reprs and rejection of generic serialization.

#### Dependency, packaging, and regression

- standard-library plus exact A3/A5/A7 allowed imports only;
- source/import guards against A5 InternalResult/ScoreEngine, A6 CardStore and
  private records, A7 private stores/records, A8/A9, Landscape, emissions,
  chain, Bittensor, web/HTML, filesystem, environment, and time;
- fresh no-dependency installed-wheel import from outside the checkout;
- complete default CPU regression;
- strict Ruff and Black on changed Python;
- repository no-new-debt evidence.

Documentation statements and pre-existing A0–A9 tests do not count as A10 test
evidence. Every future implementation DoD checkbox remains unchecked in this
candidate.

### A10-R17 — Maturity, claims, and deferred owners

This documentation candidate has exactly this maturity:

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

The pending ratification becomes repository authority only after independent
review, explicit human authorization, and normal merge. A later implementation
task must re-fetch main, verify the reviewed merge and clean preconditions,
search again for competing A10 work, and only then may propose an
in_progress transition under the normal ticket loop.

Explicitly deferred:

- production publication provider/feed;
- official and LIVE leaderboard;
- public identity and authentication;
- anonymization and correlation policy;
- timestamps, wall-clock expiry, and publication cadence;
- official score precision/display policy;
- adaptive-query/red-team qualification;
- frontier nomination/promotion policy;
- FrontierRecord and FrontierAdvanceEvent;
- Product Qualification and commercial rank;
- settlement and treasury;
- chain, Bittensor, weights, and emissions;
- A11 logging/metrics;
- A12 aggregate invariant CI.

Production remains fail closed. No current fixture, result, provider, historical
script, validator, Landscape record, or emission state may be described as an
official or LIVE leaderboard.

## 4. Future implementation sequence

This sequence is planning guidance only; it is not authorization to implement
before ratification closes.

1. Re-fetch exact post-ratification main and repeat the conflict/precondition
   audit.
2. Mark A10 in_progress only in the separately authorized implementation task.
3. Implement immutable model/error/resource/cursor types in model.py.
4. Implement only the FixtureLeaderboardProvider protocol in providers.py.
5. Implement the sole list_entries operation in service.py with full capture,
   validation, eligibility, ordering, ranking, pagination, error, resource,
   concurrency, and mutation-isolation behavior.
6. Re-export the exact reviewed A10 public surface from __init__.py.
7. Add only tests/cpu/test_leaderboard.py and prove the full matrix above.
8. Run focused, related, full CPU, strict-format/lint, no-new-debt, and fresh
   installed-wheel evidence.
9. Submit implementation for independent review; do not self-close A10.
10. Record exact merge/post-merge evidence before any A10 done transition or
    any A11 work.

## 5. Documentation-candidate validation boundary

This ratification task changes documentation only. It must:

- leave .agent/WAVE.md unchanged with A10, A11, and A12 todo;
- leave every A10 future implementation checkbox unchecked;
- add no Python, test, fixture, dependency, packaging, workflow, CI, or quality
  baseline change;
- leave A0–A9 maturity and behavior unchanged;
- claim no A10 implementation or test evidence;
- leave production fail closed.

Implementation tests are not run as evidence for this documentation-only task.
