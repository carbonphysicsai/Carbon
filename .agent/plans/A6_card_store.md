# A6 card store and Phase-0 disclosure — executed historical plan

**Ticket:** A6 — Card store + Phase 0 disclosure (C12)

**Historical ratification branch:** `agent/a6-contract-ratification`

**Ratification starting main:**
`dfd9bcc74434d2ddb5fc1862a9bdfd7ba5c64450`

**Status:** executed historical ratification and implementation plan; the
original pre-implementation guidance is retained below, and the closure record
at the end governs current maturity after the documentation closeout merges.

```text
A6 SPECIFIED / RATIFIED: YES
A6 IMPLEMENTED: YES on current main
A6 TESTED: YES only to the bounded recorded CPU/security/import scope
A6 PRODUCTION-QUALIFIED: NO
A6 WAVE STATUS: done after this closeout is merged
```

This plan closes the bounded A6 contract without adding source, tests,
fixtures, dependencies, durability, receipts, transport, or later-ticket
behavior. A fresh implementation branch may start only after this ratification
is independently reviewed, human-authorized, merged, and followed by a new
main/status/concurrency check.

## Repository gate at ratification

- A fresh fetch and independent remote read resolved `origin/main` to
  `dfd9bcc74434d2ddb5fc1862a9bdfd7ba5c64450`; the initial checkout and local
  `main` matched it exactly.
- GitHub reported no open pull request, and the fetched remote contained no
  competing A6-named branch.
- `.agent/WAVE.md` recorded A6 and A7–A12 as `todo`; A5 was closed at `done`.
- `carbon/cards/` contained only the A0 package marker. No A6 source, plan,
  focused test, fixture, or dependency existed.
- Historical Model Card, PoC card, strategy-store, and filesystem result-store
  code is noncanonical archaeology, not competing A6 implementation.

## Authority and reconciliation map

| Source | A6 use |
|---|---|
| Root `AGENTS.md` | Governs private-by-default disclosure, hostile input, no seed leakage, fixture non-emission, narrow scope, maturity, and review gates. |
| `agent_pack/EXECUTION_PROTOCOL.md` | Requires one ticket, a coherent plan for this persistence/security boundary, baseline regression, review, and no status advancement from documentation. |
| `.agent/INVARIANTS.md` | Requires allow-listed public output, no hidden-evaluation leakage, no placeholder emission, and infra/science separation. |
| `Design_Specs/Build_Out.md` | Owns C12 sequencing and the broad future private/public split; its rich Model Card shorthand does not expand the exact A5 record. |
| `Design_Specs/Miner_MCP.md` | Owns the miner feedback budget and exact tier `phase0_budgeted`; its A7/A9-integrated response metadata is not A6 identity ownership. |
| `Design_Specs/Scoring.md` and current `carbon/scoring/` | Own the exact private `InternalResult`, three statuses, external scoring digest, ordered gates/legs, fixture origin, and eligibility source. |
| `Design_Specs/Data_Management.md` and root `SPEC.md` | Reinforce hidden-realization, no-seed, immutable-result, and scientific/economic separation. Their historical seed examples do not enter A6. |
| `Design_Specs/Build_Out_Protocol_Extension.md` | Preserves a future transcript/receipt/Model Card/evidence architecture; bounded A6 implements none of those later-owned artifacts. |
| A7–A12 tickets | Retain permanent submission/auth identity, execution, transport, leaderboard, observability, and invariant-integration ownership. |
| `docs/context/Implemented_vs_Specified` | Remains the maturity ledger: specification does not imply implementation, tests, or production qualification. |

No same-domain contradiction remains: `Miner_MCP.md` now distinguishes the
bounded card from later A7/A9 response-envelope enrichment, and the broad
Build-Out Model Card/evidence shapes remain future layers. The bounded A6
object is the conservative pre-A7 projection defined here and in
A6-R1–A6-R12.

## KEEP / WRAP / REPAIR / REPLACE findings

| Area | Disposition |
|---|---|
| `carbon/cards/__init__.py` | **KEEP / REPAIR later.** Retain the canonical package boundary and add only explicit A6 exports during implementation. |
| A5 `InternalResult` and nested exact value types | **KEEP / WRAP.** Store the exact validated result; do not copy its fields into a second score schema. |
| A3 `validate_version` token contract | **KEEP / WRAP.** Reuse its bounded, non-normalizing 1–64 ASCII token grammar for both nominal opaque A6 key values. |
| `carbon/common/model_card.py` | **Do not wrap.** It writes mutable filesystem JSON/JSONL containing raw strategies, seeds, arbitrary metrics, and extras without the A6 authorization/allow-list boundary. |
| PoC card/handoff paths | **Do not wrap.** They expose seed-rich/fine data and use broad serialization; they are historical only. |
| Other filesystem stores | **Do not promote.** Their durability, mutation, and schema semantics are unrelated to the bounded insert-only A6 store. |

## Exact pre-A7 identity seam

Implementation defines two non-interchangeable frozen nominal values:

```text
CardRecordKey(value)
RequesterAuthorizationKey(value)
```

Each `value` must be an exact built-in `str`, 1–64 ASCII characters, and match
the non-normalizing token grammar already enforced by A3 `validate_version`:

```text
[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*\Z
```

No coercion, trimming, case folding, Unicode normalization, aliasing, or
subclass acceptance is allowed. The nominal wrappers—not bare strings—cross
the A6 Python boundary.

`CardRecordKey` is an opaque A6 lookup/result token, not a promise about A7's
permanent `submission_id`. `RequesterAuthorizationKey` is an opaque identity
binding label, not a password, signing/private key, credential container,
Bittensor address validator, signature proof, or production hotkey
authentication protocol. A7 may later validate its own identities and supply
compatible values through these wrappers.

## Wave-A private store

The only ratified store is a per-instance, process-local, in-memory,
insert-only mapping. One frozen private record contains exactly:

| Field | Contract |
|---|---|
| `record_schema_version` | Exact literal `"1.0"`. |
| `record_key` | Exact `CardRecordKey`. |
| `requester_authorization_key` | Exact `RequesterAuthorizationKey`. |
| `internal_result` | Exact, recursively A5-valid `carbon.scoring.model.InternalResult`. |

The store does not serialize the result or duplicate status, pins, scores,
gates, components, fixture state, or eligibility into index columns or a
second model. The full A5 value is retained for every one of its statuses,
including gate failure and `PACK_NOT_READY`.

Before any write lookup/comparison/insertion or read lookup/projection, A6 must
enforce exact nominal types and revalidate the current A5 invariants without
accepting a mapping, coercing a look-alike object, or creating an alternate
scoring schema. Error handling must not call attacker-controlled `repr`,
`str`, comparison, or display hooks.

For every write request, A6 must explicitly reconstruct a safe candidate with
fresh nominal/container nodes and a recursively independent exact-A5 value
graph, field by field through the exact constructors. Lookup and duplicate/
conflict comparison use only that validated candidate and the owned stored
record; the first valid write retains the candidate. The store retains no
caller-owned mutable object reference, exposes no private-record/result getter,
and does not use generic copy/serialization hooks. Later caller tampering with
a submitted wrapper or nested A5 object therefore cannot alter a key,
authorization binding, duplicate comparison, or projected card.

### Write behavior

```text
write_internal(record_key, requester_key, internal_result)
```

- First valid write returns `INSERTED`.
- The same key plus value-equal exact requester binding and exact A5 result
  returns `ALREADY_PRESENT` without replacing or mutating the stored record.
- The same key with any requester/result difference raises typed
  `CardConflictError`; the original stored value remains unchanged.
- No update, delete, rollback, supersession, rebind, or mutation API exists.
- This is storage idempotency after a result exists. It does not hash a
  strategy, find an open submission, charge/refund a fee, or implement A7
  submission idempotency.

The contract makes no filesystem, SQLite, database, restart, retention,
migration, crash-recovery, corruption-recovery, interprocess/distributed, or
production-concurrency guarantee. Those require separate later design and
qualification.

### Read and authorization behavior

```text
read_budgeted(record_key, requester_key) -> EvaluationCard
```

The store validates both nominal keys, locates the private record, verifies
the exact requester binding, and only then calls the positive projection.
There is no unauthenticated projection helper accepting a private record on a
miner/public path. A6 equality is only this bounded Wave-A authorization stub;
it does not authenticate a Bittensor hotkey.

Malformed request, not-found, authorization denial, record conflict,
store/infrastructure failure, and projection failure use the respective typed
`CardRequestError`, `CardNotFoundError`, `CardAuthorizationError`,
`CardConflictError`, `CardStoreError`, and `CardProjectionError`, each with a
constant non-echoing code/message. They never become an `EvaluationCard`, an
A5 `ScoreStatus`, a failed gate, a scientific zero, or `FAILED_INFRA`. A7/A8
own infra/FSM/retry/refund integration.

## Immutable public schema

The A6 value types are frozen/recursively immutable. Conceptually:

```text
EvaluationComponentScores(physics, robustness, accuracy)
EvaluationGateResult(gate_id, passed)

EvaluationCard(
  schema_version,
  result_id,
  status,
  scoring_pack_hash,
  overall_score,
  component_scores,
  gate_results,
  failure_tags,
  fixture_origin,
  eligible_for_emission,
  public_diagnostics,
  disclosure_tier,
)
```

The public projection is written as direct field construction from the exact
stored sources below. It may not apply `dataclasses.asdict`, generic model/
dict/JSON dumps, object introspection, `__dict__`, serialize-then-delete, or
deny-list redaction to any private/store object to create the public value. A9
may later encode an already-constructed public card under its separate
transport contract.

| Public field | Literal/source and reduction |
|---|---|
| `schema_version` | Exact public-card literal `"1.0"`; distinct in meaning from the private record and A5 pack schema even though the current token matches. |
| `result_id` | Exact `.value` of the authorized `CardRecordKey`. This is the sole allowed projection of storage identity. |
| `status` | Exact `InternalResult.status.value`, preserving only `SCORED`, `MANDATORY_GATE_FAILED`, and `PACK_NOT_READY`. |
| `scoring_pack_hash` | Exact `InternalResult.pack_pin.scoring_digest`; do not recompute it and do not expose the containing pin. |
| `overall_score` | Exact `InternalResult.combined_score` when present, including canonical `0.0`; otherwise `None`. No rounding/coarsening. |
| `component_scores` | For `SCORED`, one immutable object built from only the three ordered top-level `LegScore.score` values named `physics`, `robustness`, and `accuracy`; otherwise `None`. Never expose `LegScore.components` or `ScalarScore`. |
| `gate_results` | Immutable tuple in stored A5 order; each item contains only `gate_id` and `passed`. Omit `mandatory` and every pack/input/threshold/margin fact. |
| `failure_tags` | Exact tuple `("mandatory_gate_failed",)` only for `MANDATORY_GATE_FAILED`; exact empty tuple for the other statuses. This closed vocabulary contains no severity or free text. |
| `fixture_origin` | Exact stored `InternalResult.pack_pin.fixture_origin`; no request override. |
| `eligible_for_emission` | Exact stored `InternalResult.eligible_for_emission`; no request override or A6 recomputation. |
| `public_diagnostics` | Exact empty tuple for every bounded Wave-A card. Only a separately ratified/versioned authorized source may change this. |
| `disclosure_tier` | Exact literal `"phase0_budgeted"`. |

### Status matrix

| A5 status | Overall | Components | Gates | Failure tags | Scientific meaning |
|---|---:|---|---|---|---|
| `SCORED` | Exact float, possibly `0.0` | Exactly three top-level scores | Full evaluated A5 vector | `()` | Scored result; a zero leg is not a gate failure. |
| `MANDATORY_GATE_FAILED` | Exact canonical `0.0` | `None` | Full evaluated A5 vector | `("mandatory_gate_failed",)` | Actual scientific mandatory-gate failure. |
| `PACK_NOT_READY` | `None` | `None` | `()` | `()` | Readiness/configuration disposition, never scientific failure. |

For current A5, `fixture_origin` is mechanically `True` and
`eligible_for_emission` mechanically `False` for all three rows. A6 preserves
those exact stored values and has no API to label a result production/LIVE or
emission-authoritative.

## Private retention and forbidden public disclosure

The private record retains its three A6 metadata/binding fields and the exact
A5 `InternalResult`. The nested result necessarily includes the full private
`ScorePackPin`, gate metadata, and fine `ScalarScore` component vectors. A6
does not duplicate any of those nested values into parallel record fields or
add any private field beyond the exact four-field schema.

The public allow-list above is closed. Any future private field remains private
until a reviewed public schema/disclosure change names its source and
transformation. Of the A6 storage/authorization metadata, the authorized
projection exposes only `CardRecordKey.value` as `result_id`. Of the full
private `ScorePackPin`, it exposes only `scoring_digest` as
`scoring_pack_hash` and `fixture_origin` as the same-named public field. It
does not expose the requester binding, record schema, wrappers, or any other
pin metadata. In particular, no public A6 path discloses:

- raw/derived seeds, seed roles, entropy, draw/sample/exam IDs, private exam
  roots, or evaluation bindings;
- raw strategies, strategy hashes, models, predictions, references, datasets,
  or training output;
- `ScoreInput` values/keys, thresholds, margins, fine `ScalarScore` component
  vectors, or per-stress/per-regime numeric breakdowns;
- generator digest or other internal pin metadata beyond the specifically
  approved `scoring_pack_hash` and `fixture_origin` projections;
- exception text, backend/internal diagnostics, or arbitrary failure strings;
- requester bindings, authorization/storage internals, record schema metadata,
  or the record-key wrapper beyond the approved `result_id` value;
- receipt, signature, commitment, transcript, or other evidence internals;
- fees, FSM/retry/refund state, permanent submission/strategy identity,
  timestamps, leaderboard/logging fields, or later-owner metadata; or
- private keys, credentials, tokens, secrets, or attacker-controlled
  representations.

Public exceptions and future logs must use fixed safe codes/messages and never
include record-key, requester-key, or private-result representations.

## Later ownership and staged integration

| Owner | Retained responsibility |
|---|---|
| A7 | Permanent `submission_id`; canonical strategy identity/hash; authenticated requester/hotkey protocol; fees; FSM; submission idempotency; retry/refund; concrete evaluation binding. |
| A8+ | TrainEval/backend execution, status conversion, predictions/references, and authoritative metric construction. |
| A9 | MCP transport and later integration envelope. It may carry A7-owned metadata alongside, not inside, the immutable A6 card. |
| A10 | Public leaderboard schema/ranking/filtering. |
| A11 | Logs, metrics, redaction, and wider failure-tag ontology. |
| A12 | Cross-cutting invariant CI once the owning implementations exist. |
| Later evidence owner | ExecutionTranscript, Internal Model Card, EvaluationReceipt, signing/commitment, evidence retention/audit, and durable evidence ledger. |
| Later economic/chain owner | Score-to-weight mapping, Bittensor transport, and emission publication. |

Receipt/evidence designs remain valid future architecture but do not enter the
bounded A6 record. Historical Model Card/result-store code cannot widen this
contract or count as implementation evidence.

## Future implementation surface and tests

Expected implementation files after a fresh authorized start are bounded to
`carbon/cards/` modules for nominal/private/public models, the insert-only
store, explicit projection, and exports. The focused future test is
`tests/cpu/test_card_store.py`. No fixture file or dependency should be needed.

Future tests must cover at least:

- exact key type/grammar and cross-type rejection;
- recursively malformed/tampered A5 result rejection;
- insert, exact duplicate, requester conflict, result conflict, and preserved
  first record;
- post-write caller mutation attempts cannot change lookup, duplicate
  comparison, authorization, stored value, or public projection;
- not-found and authorization denial before projection;
- all three status rows and exact external scoring digest mapping;
- top-level leg-only and gate `gate_id`/`passed`-only reduction;
- approved failure-tag mapping and immutable empty diagnostics;
- canary unknown private fields and every forbidden field/value class absent
  by value, name, reference, serialization, error, and public reachability;
- fixture/eligibility non-override and attempted relabel rejection;
- immutable return structures and repeatable reads; and
- import isolation from A7/A8/A9/A10/A11, evidence, chain/Bittensor, database,
  and optional scientific dependencies.

Future validation includes the focused test, complete default CPU suite,
strict checks for changed Python, repository no-new-debt quality gate,
installed/outside-tree import isolation, and `git diff --check`.

## Ratification-only validation

This documentation branch runs the full existing default CPU suite in the
supported installed environment, the repository quality ratchet against exact
starting main, documentation/diff hygiene checks, and path/suffix audits
proving there is no Python, test, fixture, dependency, or A7+ implementation
delta. Those checks validate documentation scope only. They do not make A6
implemented or tested.

## Explicit non-goals

- No Python, tests, fixtures, dependencies, or packaging change.
- No A6 implementation or tracker advancement.
- No A7 or later implementation.
- No durable/distributed store, retention policy, migration, recovery, or
  production concurrency claim.
- No production authentication/hotkey protocol.
- No receipt, signature, evidence, transcript, audit, Bittensor, leaderboard,
  logging, fee/FSM, retry/refund, score-to-weight, or emission behavior.
- No public free-text diagnostic source or unapproved failure ontology.
- No LIVE, scientific, security, operations, emission, or production
  qualification.

After this ratification is merged, A6 may be described as
**SPECIFIED / RATIFIED: YES** only. It remains **IMPLEMENTED: NO**,
**TESTED: NO**, **PRODUCTION-QUALIFIED: NO**, and Wave status `todo` until a
separately authorized implementation is reviewed, merged, and evidenced.

## Executed-plan and closure evidence

The preceding body is the preserved pre-implementation ratification plan. Its
"future" and ratification-only statements describe the repository state at
that stage; the evidence below records execution without rewriting that
historical guidance or changing A6-R1–A6-R12.

### Ratification and implementation topology

- The A6-R1–A6-R12 ratification merged before implementation began.
- Implementation started from exact base
  `bfb8412d9aae3782d59e9814fc5b3a8c6379f86f`.
- Independent review covered exact implementation commit
  `569d450cce5943089874ad89f62f80ab5182d97a` with no P0, P1, or P2 finding.
- Current-main synchronization produced exact head
  `20a1d2f74f10b24ddb8922c6b87c7325828299b3` without changing any
  implementation blob.
- PR #23 merged normally as
  `5c7c3a924d305a386ed92d6f054981761d5c74b7`, with ordered parents
  `40c58a1578c6d16ded4ec147561455df66859697` then
  `20a1d2f74f10b24ddb8922c6b87c7325828299b3` and tree
  `d302aaf46f211030faf81920deee4dff27eac4a4`.
- The reviewed and synchronized heads are ancestral to current `main`; the
  synchronized and merge trees are equal, and the approved five implementation
  blobs remain exact.
- No formal submitted GitHub approval object is claimed. Independent review
  plus explicit human authorization supplied the review/merge process evidence.

### Exact implementation files

The bounded implementation changed exactly:

1. `.agent/WAVE.md`;
2. `carbon/cards/__init__.py`;
3. `carbon/cards/model.py`;
4. `carbon/cards/store.py`; and
5. `tests/cpu/test_card_store.py`.

No fixture, dependency, lockfile, packaging, CI, quality-baseline,
specification, or A7+ implementation file changed.

### Implemented API and disclosure boundary

The executed implementation provides the two exact opaque key wrappers, fixed
typed safe errors, immutable public card values, and one concrete `CardStore`
with only `write_internal` and `read_budgeted`. Every write reconstructs an
owned exact A5 graph before lookup or comparison. One unexported frozen record
contains exactly the private schema version, record key, requester binding, and
exact `InternalResult`. The first insert is retained; exact duplicates are
recognized; conflicts never overwrite it. Reads validate, locate, and authorize
before building a new field-by-field `phase0_budgeted` card.

The public card implements only the ratified schema/status matrix, top-level
component and gate reductions, closed failure tag, exact fixture/non-emission
fields, and empty diagnostics. Private A5/store objects, fine vectors,
mandatory flags, seed/evaluation material, internal pins beyond the approved
digest/origin projections, requester/storage metadata, and later-owner fields
remain unreachable. Tests tripwire generic copy, serialization, and
introspection paths.

### Tests, security, CI, and quality evidence

- Focused A6 suite: `181 passed`.
- Related A5/scoring, leakage, and package boundaries: `499 passed`.
- Complete default CPU suite: `1104 passed`.
- Fresh no-dependency wheel imported and exercised outside the source tree:
  `1 passed`.
- Strict Ruff and Black checks passed on all four implementation Python files.
- Quality inventory: `Ruff 757/776; Black 62/68`; removed debt
  `Ruff 19, Black 6`; four changed Python files clean; no new debt.
- PR CI `32550337528` passed on synchronized head `20a1d2f...`: `1104` tests
  passed in `21.97s`, with the same quality result.
- Post-merge push CI `32551173696` passed on exact merge `5c7c3a9...`:
  `1104 passed in 18.65s` plus the same quality result.
- Independent closure audit mapped current source/tests to every one of the
  eleven ticket DoD items and found no unresolved P0, P1, or P2 issue.

### Final maturity

```text
A6 SPECIFIED / RATIFIED: YES
A6 IMPLEMENTED: YES on current main
A6 TESTED: YES only to the bounded recorded CPU/security/import scope
A6 PRODUCTION-QUALIFIED: NO
A6 WAVE STATUS: done after this closeout is merged
```

### Residual limitations and non-goals

Closure is limited to the process-local, in-memory, insert-only Wave-A store and
its allow-listed disclosure boundary. It establishes no durability, retention,
migration, restart/crash/corruption recovery, distributed operation, or
production concurrency qualification. Same-process Python is not a sandbox;
the requester binding is not production authentication; and structural fixture
origin is not authenticated ScoreEngine provenance. No result is LIVE,
production, or emission-authoritative.

This plan closes no A7+ work. Permanent submission/strategy identity,
authenticated requester integration, fees/FSM/retry/refund, TrainEval/backend
execution, receipts/evidence/signing, MCP transport, leaderboard,
logging/metrics, invariant-CI integration, Bittensor, score-to-weight, and
emission behavior all remain pending under their later owners.
