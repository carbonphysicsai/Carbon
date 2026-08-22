# Ticket A6 — Card store + Phase 0 disclosure (C12)

**Wave:** A

**Build_Out:** C12, §9 Model Card vs EvaluationCard

**Depends on:** A5 (`InternalResult` shape)

**Ratified contract:** `.agent/DECISIONS.md` A6-R1–A6-R12 and
`.agent/plans/A6_card_store.md`

**Goal:** Store the exact private A5 `InternalResult` behind a caller-supplied
opaque record/authorization seam and return only an immutable, explicitly
allow-listed Phase-0 `EvaluationCard` after authorization.

```text
SPECIFIED / RATIFIED: YES
IMPLEMENTED: YES on current main
TESTED: YES only to the bounded recorded scope
PRODUCTION-QUALIFIED: NO
WAVE STATUS: done after this closeout is merged
```

## Bounded ownership

A6 owns only:

- process-local, in-memory, insert-only storage of an exact A5 result;
- a separate requester-authorization binding;
- storage duplicate/conflict behavior; and
- the immutable Phase-0 miner-facing projection.

A7 owns permanent `submission_id`, strategy identity/hash, authenticated
requester/hotkey integration, fees, FSM, retry/refund, and submission
idempotency. A8+ owns execution/backend semantics; A9 MCP transport; A10 the
leaderboard; and A11 logging/metrics. Receipt, signature, execution-evidence,
Bittensor, and emission-weight behavior remain later-owned.

`CardRecordKey` and `RequesterAuthorizationKey` are distinct nominal types over
exact, bounded canonical opaque tokens. Neither is an A7 production
`submission_id`, a credential/private key, nor a production hotkey
authentication protocol. A7 may later supply its permanent identifier and
authenticated requester through this seam.

## Conceptual API

```text
write_internal(
    record_key: CardRecordKey,
    requester_key: RequesterAuthorizationKey,
    internal_result: InternalResult,
) -> INSERTED | ALREADY_PRESENT

read_budgeted(
    record_key: CardRecordKey,
    requester_key: RequesterAuthorizationKey,
) -> EvaluationCard
```

The private record contains exactly:

```text
record_schema_version = "1.0"
record_key
requester_authorization_key
internal_result       # exact A5 InternalResult; no duplicated scoring fields
```

An exact duplicate write is storage-idempotent. Reusing a key with any
different requester binding or `InternalResult` is a typed conflict and never
overwrites the first record. A6 exposes no update, delete, rollback,
supersession, or mutation API. This record-write behavior is not A7 submission
idempotency. Every write first validates and explicitly reconstructs a safe,
recursively independent exact-value candidate; lookup and duplicate/conflict
comparison use only that candidate and the owned record. A successful first
write stores the candidate, retains no caller-owned mutable object reference,
and exposes no private-record/result getter.

## Phase-0 public allow-list

The immutable `EvaluationCard` is constructed positively, field by field:

| Public field | Exact A5/A6 source |
|---|---|
| `schema_version` | Exact literal `"1.0"`. |
| `result_id` | The successfully authorized `CardRecordKey` value; it is not named or represented as `submission_id`. |
| `status` | Exact A5 value: `SCORED`, `MANDATORY_GATE_FAILED`, or `PACK_NOT_READY`. |
| `scoring_pack_hash` | Exact stored `InternalResult.pack_pin.scoring_digest` (the externally supplied tagged SHA-256). |
| `overall_score` | Exact `combined_score` when present; otherwise `None`. |
| `component_scores` | Only the top-level `physics`, `robustness`, and `accuracy` `LegScore.score` values when A5 provides them. |
| `gate_results` | Every evaluated decision in A5 order, reduced to only `gate_id` and `passed`. |
| `failure_tags` | `("mandatory_gate_failed",)` only for `MANDATORY_GATE_FAILED`; otherwise `()`. |
| `fixture_origin` | Exact stored `InternalResult.pack_pin.fixture_origin`. |
| `eligible_for_emission` | Exact stored `InternalResult.eligible_for_emission`. |
| `public_diagnostics` | Exact immutable empty sequence `()` in bounded Wave A. |
| `disclosure_tier` | Exact literal `"phase0_budgeted"`. |

`PACK_NOT_READY` is not scientific failure: it has no score, components, gate
evaluation, or failure tag. Authorization, not-found, malformed request,
record conflict, store/infrastructure error, and projection failure are typed
non-card errors, never A5 statuses. A6 does not introduce `FAILED_INFRA`.

Applying generic `dataclasses.asdict`, model serialization, private-object
dumps followed by deletion, or another deny-after-serialization mechanism to a
private/store object to construct the projection is forbidden. Unknown or
future private fields remain private until a reviewed public-schema change
explicitly adds them. Encoding an already-public card is later A9 transport
work, not A6 projection behavior.

## DoD (bounded implementation verified for closeout)

- [x] Exact nominal/canonical validation and owned-candidate reconstruction for
      both opaque keys and the exact A5 `InternalResult` occurs before any
      write/read lookup or comparison; malformed/tampered values fail closed
      without echoing their representations.
- [x] Per-store, process-local in-memory insert-only record storage with the
      exact four-field private schema above.
- [x] Field-by-field owned snapshotting prevents post-write mutation of any
      caller-held key, binding, result, or nested A5 object from changing the
      record, lookup, duplicate comparison, authorization, or projection.
- [x] Exact duplicate write returns the idempotent disposition; every
      same-key conflict raises the typed conflict without mutation.
- [x] Read validates the request, verifies the requester binding, and only
      then constructs the public projection.
- [x] Frozen/recursively immutable public value types implement exactly the
      field-by-field allow-list and status matrix above.
- [x] Tests cover insert, exact duplicate, requester/result conflict,
      not-found, authorization denial, malformed/tampered input, and safe
      non-scientific error messages.
- [x] Tests prove no private object/generic serializer reaches the public
      path; unknown private canary fields default private.
- [x] Tests prove component/gate reduction, empty diagnostics, approved tag
      mapping, and every forbidden field/value class remains unreachable.
- [x] Tests prove fixture origin and emission eligibility come only from the
      stored result and cannot be caller-overridden or relabelled.
- [x] Tests distinguish A6 storage duplicate handling from A7 submission
      idempotency and add no A7+ implementation.

## Final implementation and closure evidence

The bounded implementation started from exact base
`bfb8412d9aae3782d59e9814fc5b3a8c6379f86f`, was independently reviewed at
`569d450cce5943089874ad89f62f80ab5182d97a`, and was synchronized without
implementation-blob change at
`20a1d2f74f10b24ddb8922c6b87c7325828299b3`. PR #23 merged normally as
`5c7c3a924d305a386ed92d6f054981761d5c74b7`, with ordered parents
`40c58a1578c6d16ded4ec147561455df66859697` then
`20a1d2f74f10b24ddb8922c6b87c7325828299b3` and tree
`d302aaf46f211030faf81920deee4dff27eac4a4`. The reviewed heads are ancestral,
the synchronized and merge trees are equal, and all five approved
implementation blobs are preserved.

Implementation scope was exactly `.agent/WAVE.md`, `carbon/cards/__init__.py`,
`carbon/cards/model.py`, `carbon/cards/store.py`, and
`tests/cpu/test_card_store.py`. Independent implementation and closure audits
found no P0, P1, or P2 issue and mapped source/test evidence to all eleven DoD
items above. No formal submitted GitHub approval object is claimed; independent
review and explicit human authorization are the recorded process evidence.

Validation evidence is:

- focused A6 suite: `181 passed`;
- related scoring/leakage/package boundaries: `499 passed`;
- full default CPU suite: `1104 passed`;
- fresh no-dependency wheel/outside-tree proof: `1 passed`;
- strict Ruff and Black: clean for all four implementation Python files;
- quality: `Ruff 757/776; Black 62/68`, four changed Python files clean, no new
  debt;
- synchronized PR CI `32550337528`: completed/success, `1104 passed in 21.97s`,
  same quality inventory and no-new-debt result; and
- post-merge push CI `32551173696`: completed/success on exact merge,
  `1104 passed in 18.65s`, same quality inventory and no-new-debt result.

A6 is `done` only for this bounded process-local Wave-A scope. Current fixture
results remain false-eligible and non-emission-authoritative. The store is not
durable, restart/crash recoverable, distributed, or production-concurrency
qualified; requester equality is not production authentication; and neither
fixture origin nor structural validation establishes authenticated ScoreEngine
provenance, LIVE status, or scientific/security/operations qualification.

A7–A12 remain pending, as do rich Model Card, transcript, receipt, signature,
evidence, durable persistence, MCP, leaderboard, logging, Bittensor, and
emission work. No miner-facing path returns the private `InternalResult` or a
rich Model Card; only the immutable bounded `EvaluationCard` is public at this
boundary.

## Explicit deferrals and prohibitions

Wave-A persistence is not durable. Filesystem/SQLite/database storage,
retention, migration, crash/corruption recovery, distributed operation, and
production concurrency qualification are deferred.

The private record retains its schema/key/requester fields and the entire exact
A5 `InternalResult`, including its full private `ScorePackPin`, gate metadata,
and fine `ScalarScore` vectors. A6 does not duplicate those nested values or
add fields beyond that four-field schema.

The public projection discloses none of the following: raw strategies;
raw/derived seeds; draw/sample IDs; private evaluation bindings; `ScoreInput`
values or keys; thresholds or margins; fine `ScalarScore` vectors;
per-stress/per-regime numeric breakdowns; generator digest or internal pin
metadata beyond the approved `scoring_pack_hash` and `fixture_origin`
projections; internal/backend diagnostics or exceptions; the requester
binding, record schema, or storage metadata beyond the approved `result_id`
value; receipts/signatures/evidence; fees/FSM/retry state; predictions/
references; secrets/private keys; or any later-owner field.

Historical Model Card/result-store code is archaeology and cannot override or
satisfy this ticket.

**Focused test evidence:**
`python -m pytest tests/cpu/test_card_store.py -q` — `181 passed`

**Must not:** Return an `InternalResult` or rich Model Card on any miner/public
path; add durability or receipt/evidence behavior; introduce public free-text
diagnostics; implement A7 or later work; or change `.agent/WAVE.md` from
`todo` during contract ratification.
