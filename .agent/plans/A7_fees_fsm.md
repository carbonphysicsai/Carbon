# A7 fees, permanent submission identity, and FSM — pre-implementation plan

**Ticket:** A7 — Fees + permanent submission identity + submission FSM (C13)

**Ratification branch:** `agent/a7-contract-ratification`

**Ratification starting main:**
`ba0b2b3dffd114d02fd5f6a71af08052a3e0a1ed`

**Starting tree:**
`e3718deceef355936cdf427bb04b68fa3d98c760`

**Status:** documentation-only ratification plan; not executed implementation

```text
A7 SPECIFIED / RATIFIED: YES only after this ratification is explicitly human-authorized and merged
A7 IMPLEMENTED: NO
A7 TESTED: NO
A7 PRODUCTION-QUALIFIED: NO
A7 WAVE STATUS: todo
```

This plan changes no Python, test, dependency, package, fixture, A0–A6 closure,
or A8+ work. A fresh implementation branch may start only after the
ratification is independently reviewed, explicitly human-authorized, merged,
and followed by a new main/status/concurrency check.

The human policy amendment selects terminal `FAILED_INFRA -> REFUND`,
requester-bound cancellation from `RECEIVED`/`VALIDATED`/`QUEUED`, and first
atomic `QUEUED -> RUNNING` as the sole exam-charge boundary. Those selections
do not execute this plan or make the candidate ratified before merge. The
hostile-input amendment additionally requires an injected immutable A7
submission-resource policy before full Strategy/A3 challenge processing.

## Repository gate at ratification

- A fresh fetch resolved `origin/main` to the exact expected commit and tree
  recorded above. The commit is the normal A6-closeout merge.
- The pre-publication GitHub check reported no open pull request, and the
  fetched remote contained no competing A7-named branch before this candidate
  was pushed.
- `.agent/WAVE.md` records A7 as `todo`; A0–A6 remain closed at their current
  states and A8–A12 remain `todo`.
- `carbon/fees/` contains only its A0 package marker. There is no A7 source,
  focused test, fixture, or runtime dependency to preserve as implementation.
- Historical timestamp IDs, `carbon.protocol.StrategySynapse`,
  `carbon/common/model_card.py`, PoC hashing, and queue sketches are
  noncanonical archaeology, not an A7 implementation.

## Authority and reconciliation map

| Source | A7 use |
|---|---|
| Root `AGENTS.md` | Governs hostile-input safety, private-by-default data, no hidden-evaluation leakage, fee/science separation, bounded maturity claims, and review gates. |
| `agent_pack/EXECUTION_PROTOCOL.md` | Requires one coherent ticket/plan, fresh repository checks, evidence-backed implementation, independent review, and no status advancement from documentation. |
| `.agent/INVARIANTS.md` | Requires fee not to affect score, infrastructure not to become science, hidden data not to leak, and no emission behavior from incomplete plumbing. |
| `docs/context/Open_Questions.md` | Canonically retains human ownership of OQ-005/OQ-006 production randomness, OQ-010 exam pricing, and OQ-012 retry/operating-envelope policy; A7 supplies no defaults. |
| `Design_Specs/Build_Out.md` | Owns ordering and the broad lifecycle. A7 owns the core persisted C13 FSM; later C7/validator execution integrates with it rather than defining another lifecycle. |
| `Design_Specs/Scoring.md` and current A5 | Own exact scientific result semantics. Current constructors accept only fixture-origin pins/results. A7 may consume exact fixture `SCORED`/`MANDATORY_GATE_FAILED` outcomes and does not reinterpret `PACK_NOT_READY` as science; a production origin/result path remains separately ratified work. |
| Current A2 | Owns structural Strategy validation. A7 first constructs one resource-bounded detached candidate, then calls A2 as the first semantic authority without changing A2 fields/issues. |
| Current A3 | Owns exact `ChallengeKey`, version-token grammar, and qualification/LIVE authority. A7 applies resource admissibility before its unbounded challenge-ID scan/reconstruction, then reuses the unchanged key/grammar without copying qualification logic. Current fail-closed false/ineligible results define admission denial, but no public adapter binds a LIVE key to exact qualified generator/Score Pack pins. |
| Current A4 | Owns seed/exam identity types and requires an opaque 32-byte evaluation binding. A7 supplies the exact binding while A4 retains generator/scoring/randomness binding. |
| Current A6 | Owns exact private `InternalResult` storage, requester-key authorization stub, and positive public projection. A7 adapts identities and sequences publication without aliasing or bypassing it. |
| `Miner_MCP.md` | Constrains later miner response/disclosure. Its paid-loop/SubmitReceipt sequence is product/transport shorthand, not A7 ledger-event timing; it does not move MCP into A7, prove settlement, or authorize a public raw-Strategy/A5-result surface. |
| `Data_Management.md`, `Trustless_Verification.md`, `Evaluation_Evidence_and_Validator_Audit.md`, root `SPEC.md`, and protocol extension specs | Reinforce no-seed/private-evidence, deterministic identity, economic/scientific separation, and the later valid-receipt prerequisite for authoritative production results. |
| A8–A12 tickets | Retain TrainEval execution/runtime limits, MCP transport and stricter future parser/rate limits, leaderboard, observability, and invariant-integration ownership. A9 limits may not replace A7's independent submission-input boundary. |
| `docs/context/Implemented_vs_Specified` | Remains the maturity ledger: specification does not imply implementation, tests, or production qualification. |

Reconciliations recorded in A7-R1–A7-R15 govern this work: the stale ticket's
bare `hotkey`/`challenge_id` and root-level test path are repaired; Wave board
“FAILED_INFRA refund” now agrees with the selected default but does not imply
implementation; historical A6 “authenticated requester” wording does not
turn equality into authentication; and proposed Strategy `compute_tier`/fee
language is not promoted into authority.

## KEEP / WRAP / REPAIR / REPLACE findings

| Area | Disposition |
|---|---|
| A2 `dry_validate` and Strategy field/value semantics | **KEEP / WRAP.** Construct a resource-bounded topology-preserving detached candidate, call A2 once, then apply A7's separate alias/identity rule; only accepted storage is alias-free. Do not alter A2. |
| `SubmissionResourceLimits` | **ADD seam later.** Require immutable explicit per-value, concurrent-build, and retained-store bounds at A7 construction. Supply no defaults; keep configuration/counters out of records and identity. |
| A3 `ChallengeKey` and `validate_version` | **KEEP / WRAP.** Store the exact key; reuse only its bounded token validator inside distinct A7 nominal wrappers. |
| A3 qualification/LIVE policy | **KEEP / WRAP.** Use separate exact production and fixture assessment calls at queue admission; treat current A3 fail-closed false/ineligible as denial, and do not duplicate artifacts, slots, reason classification, or gate logic. Production stays unavailable until A3 owns a qualified-pin adapter. |
| A4 `EvaluationBinding` and `SeedPin` | **KEEP / REPAIR seam.** Construct the missing exact 32-byte A7 binding, build one owned scientific SeedPin through the fixture seam or future A3 production adapter, and preserve it across retries. |
| A5 `InternalResult` and `ScoreEngine` | **KEEP.** Accept exact fixture completed-result semantics; add no fee argument/field, alternate status/scoring model, or fabricated production origin. |
| A6 `CardRecordKey`, `RequesterAuthorizationKey`, and `CardStore` | **KEEP / WRAP.** Deliberately reconstruct separate A6 keys; A7 exclusively owns its dedicated store and gates all write/read access under the A7 guard. |
| `carbon/fees/__init__.py` | **KEEP / REPAIR later.** Preserve the package and add only explicit A7 exports during authorized implementation. |
| A7 ticket | **REPAIR now as documentation.** Replace stale identity/API/test shorthand with the ratification candidate while leaving every implementation checkbox open. |
| Legacy model-card, protocol, timestamp-ID, serializer/hash, queue, and filesystem-store code | **Do not wrap.** It conflicts with nominal identity, typed encoding, privacy, atomicity, or current A2–A6 boundaries. |
| New runtime dependencies or A8+ imports | **REPLACE with standard library / forbid.** A7 core must remain independently importable. |

## Exact model to implement later

Future A7 values will be frozen/slotted and non-interchangeable:

```text
SubmissionId(value)       # canonical lowercase hyphenated UUIDv4
StrategyHash(value)       # sha256:<64 lowercase hex>
RequesterIdentity(value)  # exact A3 validate_version grammar
FeePolicyKey(value)       # exact A3 validate_version grammar
FeeOperationKey(value)    # exact A3 validate_version grammar

SubmissionResourceLimits fields:
max_total_value_nodes
max_object_members
max_list_items
max_string_utf8_bytes
max_object_key_utf8_bytes
max_strategy_identity_bytes
max_challenge_id_bytes
max_concurrent_identity_builds
max_retained_submission_records
max_retained_value_nodes
max_retained_strategy_identity_bytes

AdmissionKind = PRODUCTION | FIXTURE

SubmissionState =
  RECEIVED | VALIDATED | QUEUED | RUNNING | SCORED |
  PUBLISHED | REJECTED | FAILED_INFRA | FAILED_STRATEGY | CANCELLED

AttemptEventKind =
  QUEUED | RUNNING | RETRYABLE_INFRA | SCORED |
  FAILED_STRATEGY | FAILED_INFRA | CANCELLED

FeeEventKind = CHARGE | REFUND | RETRY_CREDIT
FeeOperationContext =
  INITIAL_RUN_START | RETRY | TERMINAL_INFRA | PUBLICATION_INFRA

ExecutionEnvironmentPin =
  backend_profile_id (exact 1-128 ASCII token) +
  container_digest (sha256:<64 lowercase hex>)

ExecutionAttemptHandle =
  owned SubmissionId + exact attempt number + AdmissionKind +
  owned A4 SeedPin + owned ExecutionEnvironmentPin

ProductionExecutionEnvelope | FixtureExecutionEnvelope =
  owned handle + fresh alias-free Strategy + StrategyHash + ChallengeKey

SubmissionStatusView = owned SubmissionId + SubmissionState

InitialRunStartResult =
  STARTED(FeeEvent, private kind-specific ExecutionEnvelope) |
  ALREADY_STARTED(FeeEvent, SubmissionState)  # exact replay; no envelope
```

The private `ExecutionEnvironmentPin` is A7's wrapper/comparison of safe
attempt-identity references, not ownership of an A8 runtime:
`backend_profile_id` is an exact built-in 1–128-character ASCII token
under `[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*`, and `container_digest` is exact
tagged lowercase SHA-256. A7 neither selects nor launches a backend and stores
no path, runtime object, metric, runtime resource limit, or A8 raw result/
status/error payload. A8 owns concrete selection/configuration, execution
limits, invocation, runtime, and outcome semantics. This is separate from
A7's submission-input limits. A fixture harness supplies conspicuous
non-emission values; future production values must cross-check the A3
qualified profile, human-qualified profile/container evidence, and A8 declared
environment below. The pin binds immutable identity but does not prove that
execution occurred.

The exact A4 `SeedPin` is safe identity metadata rather than a seed: only the
owned ChallengeKey, generator/scoring versions and digests, A7
EvaluationBinding, and fixed scheme identifier. It contains no A4 context,
entropy, private root, domain/role/draw, derived seed, or realization.

Exact built-in types are required; no coercion, subclass acceptance, trimming,
case folding, Unicode normalization, wrapper aliasing, or unbounded value in an
error. Every inbound nominal is reconstructed before lookup/retention and
every returned nominal/view/event is a separate owned reconstruction.
`uuid.UUID` parsing is not permission to accept alternate textual UUID forms:
stored/exposed `SubmissionId.value` is canonical exact text. New record
creation generates exactly one UUID candidate; collision is a typed
no-record/no-regeneration error.

The public conceptual submit operation remains:

```text
submit(RequesterIdentity, ChallengeKey, hostile_strategy_object) -> SubmissionId
```

Implementation should expose typed, constant-message failures at minimum for
malformed request wrappers, unavailable resource policy, resource limit,
resource capacity, identity encoding, store failure/collision, illegal
transition, fee-policy absence, and fee-operation conflict. Those failures may
expose bounded stable codes but never limit categories/values, observed counts,
submitted values, keys, object `repr`, backend exception text, or the private
record. A9 owns eventual transport error mapping.

The resource taxonomy is closed: missing/invalid mandatory configuration is
typed `SubmissionResourcePolicyError` with constant code
`submission.resource_policy_unavailable`; a per-request overrun is typed
`SubmissionResourceError` with `submission.resource_limit_exceeded`; exhausted
build/retention capacity uses that same type with
`submission.resource_capacity_exceeded`. None is an FSM/scientific/
infrastructure status, and none carries a category, configured/observed value,
path, or attacker text.

## Identity construction sequence

Every executable store receives one frozen/slotted exact
`SubmissionResourceLimits` at construction. Each field is an exact positive
built-in integer no greater than unsigned-64; Boolean/coercion/absence/
sentinel values reject, and `max_challenge_id_bytes` is additionally no greater
than unsigned-32. Total value nodes count root and every list-item/object-value
position; object keys are separate. Member/item limits are per container. No
separate nesting-depth field is exposed: accepted-tree depth cannot exceed the
total-position cap, while one-expansion memoization bounds shared/cyclic
capture and current A2 traversal without inventing unfolded depth. String/key
counts use strict UTF-8 bytes, and Strategy
identity bytes cover the exact complete header-and-frame preimage, including
integer magnitude and framing. The final four fields cap concurrent candidate
builds plus aggregate retained records, accepted value nodes, and accepted
identity bytes. Production values are explicit human security/operations
inputs; fixture tests inject conspicuous finite values. There is no default,
environment fallback, admission-kind switch, or A9 dependency. A fixture-
configured store is not production-capable or relabellable; production values
require a new store.

The future submit path will perform these steps in order:

1. Non-blockingly acquire one configured identity-build permit. Exhaustion is
   a constant no-ID capacity error; release the permit on every exit.
2. Perform constant-bounded exact wrapper-shape checks and capture every
   requester/challenge nominal scalar exactly once. Apply
   `max_challenge_id_bytes` to that local with a capped scan before A3 regex
   validation or fresh reconstruction; every later comparison/binding uses the
   same captured primitive. Passing this A7 check says nothing about A3
   validity; malformed wrappers/fields still fail before ID.
3. Iteratively construct one request-local topology-preserving owned candidate
   while enforcing every Strategy limit before the next expansion/allocation.
   Memoize fresh exact built-in dict/list containers, expand each source
   container once, and count each enumerated value position without recursively
   exploding shared/cyclic edges. Check cardinality before enumeration;
   incrementally scan strict UTF-8 and exact identity bytes. Preserve a bounded
   exact string/key that fails strict UTF-8 in the candidate while recording a
   post-A2 A7 identity failure. Invalid UTF-8 alone does not stop capture; a
   provable resource overrun during that scan may. Use integer
   `bit_length` to reject when the complete tag/length/sign/magnitude frame
   cannot fit before materializing the exact minimal unsigned big-endian
   magnitude; and stop on first exceed. Represent hostile non-string keys and
   non-JSON leaves with request-local inert sentinels that preserve A2's type-
   issue code/path without hashing/comparing/displaying or invoking the hostile
   object. Observed size/iteration/access instability fails safely. If capture
   completes despite an undetectable concurrent replacement, the detached
   candidate is authoritative; no later pass rereads the caller graph.
4. Call current A2 `dry_validate` once on the bounded topology-preserving
   candidate. Preserve its cycle and shared-DAG behavior and every field/issue
   semantic. If A2 succeeds, apply A7's recorded repeated-container and strict-
   UTF-8 identity rules. A bounded lone surrogate therefore reaches A2 first;
   a shared DAG is A2-valid but A7-rejected; a candidate proceeding to hash/
   storage is necessarily an alias-free tree.
5. Compare the A2/A7-accepted candidate's exact `challenge_id` to the
   reconstructed exact `ChallengeKey.challenge_id`, then defensively check
   every A7-R4 binding payload fits its unsigned-32 length.
6. Compute exact nested-frame payload lengths bottom-up with checked
   unsigned-64 arithmetic and the configured complete-identity-byte cap, then
   stream the unchanged flat A7-R3 encoding into SHA-256. Construct no
   `StrategyHash` until the complete stream succeeds; a partial digest is never
   returned, retained, or keyable.
7. Acquire the store guard and look up exact
   `(RequesterIdentity, ChallengeKey, StrategyHash)` among open records. Return
   a fresh reconstruction of an existing ID before applying new-record
   capacity.
8. For a new accepted identity, atomically require record/value-node/identity-
   byte capacity, generate and collision-check exactly one UUIDv4 candidate,
   insert owned `RECEIVED` plus its open index, and commit constant-size
   aggregate accounting. Any failure creates no ID/record/index/accounting.
9. For a within-budget A2/identity/challenge failure after valid wrappers,
   atomically require record capacity, generate/collision-check one ID, and
   insert the terminal `RECEIVED -> REJECTED` record with no snapshot/hash/open
   index. A resource limit or capacity failure instead returns its constant
   typed no-ID/no-record error.

The exact typed encoding table, integer/binary64/string rules, object sort,
domain header, and tagged hash format in A7-R3 are normative. An independent
test encoder—not the implementation helper—will produce golden vectors for
empty/nested values, large integers, UTF-8 ordering, list/order changes,
`1`/`1.0`, and signed floating zero. Any Strategy admitted under two different
policies has exactly the same hash; limits never truncate or enter the
preimage.

After a new accepted ID exists, A7 derives the A4 `EvaluationBinding` exactly
as A7-R4 specifies. Its canonical binding-input document contains only the
safe SubmissionId, StrategyHash, challenge ID, and version identifiers—no A4
context, entropy, root, seed, domain/role/draw, hidden sample/exam ID, or
realization. The digest is immutable in meaning and reproducible from stored
identity fields; it need not be duplicated in the minimum record. Tests
reconstruct and adapt it into A4's exact 32-byte type.

Because SubmissionId enters the A4 binding, a logical Carbon intake allocates
the ID/binding once. Later validator integration must propagate that canonical
envelope unchanged; validators may not independently remint it. The Wave-A
store does not claim the later durable/distributed mechanism.

Root SPEC's shared-exam wording is read with the Trustless/OQ addendum:
validators share one pinned contract/domain and the same submission-specific
A7 binding for a logical submission. When combined later with separately
governed A4 inputs it participates in reproducible derivation, but A7 neither
selects, contains, constructs, persists, exposes, nor proves a realization.
Provider/timing/finality remains OQ-005/OQ-006.

## Guarded store and transition operations

The future store will maintain one private record mapping by `SubmissionId`
and one derived open-key index. Both are per-instance and guarded by a
standard-library lock. The injected submission-resource and fee/retry policy
sets are immutable for the store lifetime; reconfiguration requires a new
store. Terminal `REFUND` and requester-bound cancellation semantics are fixed.
A7
constructs and exclusively owns the A6
`CardStore` holding its cards, exposes no direct reference, and performs every
A6 call under the same guard. A test-failure seam must transfer exclusive
ownership and cannot model a production side channel.

After a positive A3 production admission result, first admission also requires
all later production seams before queue/attempt: an A3-owned qualified
generator/Score Pack/backend-profile adapter; a human-qualification-owned
profile/container-digest evidence adapter; ratified OQ-005/OQ-006 A4 official-
context policy; a separately ratified A5 production origin/result path; an A8
handle-aware declaration of the exact environment it will execute; and a
separately ratified production-capable A6 private-store/projection path plus a
later-owned submission/pin-bound evidence/receipt adapter whose production
completion integration requires re-ratification. A7 cross-checks the three
profile/digest sources before constructing its private pin; A8 configuration is
not qualification authority. The later A8/orchestration adapter, not A7,
acquires any A4 context and owns runtime execution/results. None exists as a complete set on the
ratification base, so bounded Wave A leaves an otherwise eligible production
submission `VALIDATED` and uncharged; only conspicuous fixture-only mechanics
can execute.

The exact private record remains:

```text
record_schema_version = "1.0"
submission_id
requester_identity
challenge_key
strategy_hash?
owned_strategy_snapshot?
state
admission_kind?
terminal_infra_disposition?  # REFUND; fixed at queue admission
terminal_infra_operation_key? # reserved with first RUNNING/CHARGE
current_attempt_number?
a4_seed_pin?                 # safe exact A4 identity metadata; no seed/context
execution_environment_pin?   # safe profile/digest reference; no runtime state
running_attempt_handle?      # no payload beyond state/attempt/kind/safe pins
attempt_history
fee_events
```

No caller receives this record or its stored Strategy. The private start seam
returns a kind-specific execution envelope with a fresh alias-free Strategy
tree and fresh owned identity wrappers; it never publishes a store reference.

The record and attempt history never contain official/master/derived seed
values, entropy/context/private roots, domain/role/draw or hidden sample/exam
IDs, reversible realization data, duplicated A5 results/scientific values,
predictions/references, backend metrics/stacks, private keys, receipt
signatures, A8 raw runtime result/status/error payloads, or unbounded
diagnostics. Only mapped closed A7 state/attempt events may persist.

`SubmissionResourceLimits`, its per-request counters, measured sizes, limit
category, and offending value/path are not record fields. The store keeps only
constant-size aggregate permit/record/value-node/identity-byte accounting at
its service boundary. Capacity reservation and record/index/accounting commit
are atomic; failure rolls them all back. No policy value or measured unit
enters StrategyHash, EvaluationBinding, attempt history, fees, or science.

Every mutation will validate all preconditions before committing a new record
value and related index/event changes. On error there is no partial state,
attempt, open-index, or fee mutation. Transitioning to a terminal state removes
the open index atomically; terminal records remain queryable by ID and are
never overwritten. State mutations occur only through semantic operations,
not a general caller-supplied `set_state` method.

Planned semantic operations are:

| Operation | Exact effect |
|---|---|
| submit | Require resource policy/build permit; bounded-copy before A2; complete hash before open lookup. Return an open duplicate before capacity. New accepted input atomically capacity-checks and creates `RECEIVED`; within-budget invalid input capacity-checks and creates terminal `REJECTED`; resource/capacity errors create no ID/record/state. |
| mark validated | `RECEIVED -> VALIDATED` only after accepted identity/snapshot is present. |
| admit production queue | Require exact `VALIDATED`, call A3 production eligibility, then exact-key backbone compatibility; either false performs safe `VALIDATED -> REJECTED`, while an escaping compatibility error leaves `VALIDATED`. After both pass, resolve/cross-check both pins, complete immutable policy inputs, and every production seam, or leave `VALIDATED` unchanged and uncharged. With every prerequisite, atomically store both pins, `PRODUCTION`, fixed `REFUND`, attempt `1`, and `QUEUED` with no fee event. |
| admit fixture queue | Require exact `VALIDATED`, use separate A3 fixture eligibility, then exact-key backbone compatibility, conspicuous fixture-only/non-emission fee/retry values, and both fixture pins. Apply the same no-fee queue mechanics, store `FIXTURE`, and never fall back/relabel. |
| start first production/fixture attempt | Receive stable charge/refund operation keys, resolve charge replay/conflict first, and for a new key require exact initial `QUEUED`, both retained pins, configured fee policy/amount, and no charge. Atomically build/store the handle, reserve the refund key, append `CHARGE` plus `RUNNING`, transition to `RUNNING`, and return closed `STARTED` with event/envelope. Exact replay returns no-envelope `ALREADY_STARTED`. Production cannot reach this operation until every production seam above exists. |
| start retry attempt | Reuse both immutable stored pins and the prior charge, create the next kind-specific handle/envelope, append `RUNNING`, and move `QUEUED -> RUNNING` without a fee event or second charge. |
| retry infrastructure | Require matching current handle; append `RETRYABLE_INFRA` for `n` and `QUEUED` for `n + 1`, clear current handle, and move to `QUEUED` atomically. Current Wave A appends no retry fee event. |
| fail strategy | Require matching current handle; append `FAILED_STRATEGY`, clear handle, move terminal, and remove the open index. |
| fail infrastructure | From initial pre-start `QUEUED` with no charge, append the attempt event and terminalize without a fee event. From charged retry-`QUEUED`, or `RUNNING` with matching handle, append the event and fixed full-remaining-balance `REFUND`; A6 failure does the same internally from transient `SCORED` under `PUBLICATION_INFRA`. Remove the open index atomically. |
| complete and publish | Require matching handle with both stored pins; reconstruct/cross-check one exact A5 result against its SeedPin; route non-completion operationally, or under one guard record `RUNNING -> SCORED`, A6 write, then `PUBLISHED` or `FAILED_INFRA`. No separate mark/publish API or fee-replay surface. |
| cancel | Reconstruct ID/requester, require exact stored requester equality and current `RECEIVED`, `VALIDATED`, or `QUEUED`, then atomically move terminal. Append no fee event; deny every other state and every stale/racing request. |
| get status | Verify structural requester binding and return only fresh owned SubmissionId/state. |
| read published | Require `PUBLISHED`, adapt fresh A6 keys, and return only A6 `EvaluationCard`; repeat read has no fee. |

The transition table in A7-R8 is closed. A general transition helper, if used
internally, remains private and cannot bypass semantic preconditions.
`FAILED_INFRA -> QUEUED` and every terminal successor are forbidden.

`VALIDATED -> REJECTED` is the closed trusted pre-queue denial seam required by
Build Out. Wave A uses it only for A3 admission; later-owned authenticated
payment/auth denial adapters may use the same edge, but no generic caller API
or stored reason exists. At no-fee queue admission, current A3 deliberately
converts typed registry or artifact failures to false/ineligible, so those exact
results take the generic A3 admission denial without A7 reason-code
reclassification. Eligible submissions then use A3's exact-key backbone
compatibility API; false denies admission, while `RegistryError`/escaping
failure leaves `VALIDATED`. Missing later queue-admission fee/retry/pin
configuration or a production seam is configuration absence, not proof of
nonpayment, and also leaves `VALIDATED` unchanged and uncharged. The mandatory
construction-time submission-resource policy is excluded.

Attempt `1` is created only with initial queue admission, which also fixes one
exact owned A4 SeedPin and one exact owned A7 ExecutionEnvironmentPin. First
start atomically builds the handle, reserves the refund key, appends the sole
charge plus `RUNNING`, and returns the envelope. Retry uses `n + 1` under the
same submission, reuses the existing charge, both pins, Strategy hash,
challenge key, evaluation binding, and AdmissionKind, and never charges again.
Every `RUNNING`
callback requires the stored current handle;
stale success/failure/retry callbacks mutate nothing on first application. The
only carve-out is exact no-mutation replay of an already-recorded fee-bearing
transaction using the event-bound historical attempt/handle described below.
Pre-queue rejection/cancellation has no attempt. Requester cancellation from
`QUEUED` closes the current queued attempt without a fee event. Initial queued
cancellation is wholly uncharged; retry-queued cancellation retains the prior
material-start charge. Attempt history contains no handle, pin, clock, metrics,
seeds, prediction/reference, scientific scalar, A8 runtime result/status/error
payload, stack trace, or arbitrary diagnostic.

## Fee operations and policy seam

The future implementation will require an immutable injected policy set.
It supplies a `FeePolicyKey`, exact integer-minor-unit amount, and explicit
retry policy; terminal disposition is fixed `REFUND` and cancellation is the
fixed requester-bound/no-event rule. The policy key supplies denomination/
asset/schedule/version meaning; A7 hard-codes none. Queue admission requires
those inputs to be complete but appends no fee event. The trusted first-start
adapter supplies stable charge and distinct refund operation keys. Fixture
tests use labels and values that cannot be mistaken for production
configuration. Nominal inputs are reconstructed before lookup/retention. None
of this process-local ledger state proves payment authorization, reservation,
transfer, or settlement. `Miner_MCP.md`'s paid-loop/SubmitReceipt sequence is
later product/transport shorthand and does not move the A7 ledger charge before
material start or make it a payment receipt.

Each immutable event contains only exact built-in integer sequence starting at
`1` and increasing by exactly one, `FeeOperationKey`, `FeePolicyKey`, closed
kind, closed `FeeOperationContext`, exact stored `AdmissionKind`, exact positive
`source_attempt_number`, exact `amount_minor`, and a charge-operation link for
adjustments. The contexts are exactly `INITIAL_RUN_START`, `RETRY`,
`TERMINAL_INFRA`, and `PUBLICATION_INFRA`. `RETRY_CREDIT`/`RETRY` remain
schema vocabulary for a future separately ratified policy and are not emitted
by the current retry or terminal rules. `CHARGE` records the existing queued
attempt `1`; later events identify their coupled source attempt. The guarded
record enforces:

- after safe boundary/submission/key reconstruction, a transaction that
  appended a fee event resolves existing operation-key replay/conflict before
  policy/configuration, lifecycle/current-handle, or any other fallible
  prerequisite; A3 belongs to earlier no-fee queue admission, and only a new
  key reaches source-state then operation-specific handle/policy checks;
- exact kind/context/admission-kind/source-attempt/amount/policy/link replay of
  a completed coupled transaction returns its event with no mutation even after
  state advancement/terminalization;
- replay of a handle-requiring callback must supply the exact historical
  handle reconstructed from event attempt plus immutable stored submission,
  admission, scientific-pin, and environment-pin fields;
- initial start generates its handle: first application requires initial
  `QUEUED`, configured fee policy/amount, both safe pins, stable charge/refund
  keys, and no charge, then atomically stores the handle/refund key, appends
  `CHARGE` plus `RUNNING`, moves to `RUNNING`, and returns closed `STARTED`
  with event/envelope;
- exact initial-start replay must match refund key, SeedPin, and
  ExecutionEnvironmentPin, and returns closed `ALREADY_STARTED` with only the
  prior event/current status—never an envelope or second launch authority;
- the same operation key with a changed context, admission kind, attempt,
  handle, fee kind, amount, policy, or link raises a typed conflict without
  mutation;
- exactly zero or one charge, with the charge atomic only with first
  `QUEUED -> RUNNING`; retry start never charges;
- no adjustment without the exact charge link and matching policy key;
- cumulative refund plus retry-credit amount no greater than charged amount;
- the reserved terminal key is distinct, unavailable to all other events, and
  consumed only for fixed full-remaining-balance `REFUND` under
  `TERMINAL_INFRA` or internal `PUBLICATION_INFRA`;
- no fee event from invalid submit, open duplicate, queue admission,
  cancellation, retry start/current-policy retry, result read, or A6 exact
  duplicate write; and
- no import, argument, model field, callback, or conversion from fee policy or
  event into A5 scoring or later weight/emission calculations.

An operation that appended no fee event has no fee-operation replay claim. No
standalone adjustment operation exists. Failed initial-start validation leaves
`QUEUED` uncharged. Pre-start initial-queued `FAILED_INFRA` has no charge and
no refund event; charged retry-`QUEUED`, `RUNNING`, or `SCORED` failure consumes
the reserved key for the full remaining-balance refund. Cancellation emits no
fee event: initial queued cancellation is wholly uncharged, while retry-queued
cancellation retains the prior charge. Conspicuous fixture-only fee/retry
values may exercise the fixed refund/cancellation mechanics; production
remains fail-closed.

`complete_and_publish` is excluded from the fee-operation replay surface even
if its atomic A6-failure path consumes the reserved refund.
Repeated completion remains a typed terminal-state error; the internal event
uses distinct `PUBLICATION_INFRA` context, so a later `TERMINAL_INFRA` callback
conflicts rather than retrieving or duplicating it.

## A5 completion and A6 publication sequence

A7 does not import A8 and does not execute TrainEval. A later-owned execution
adapter receives the private kind-specific A7 execution envelope and returns
its current `ExecutionAttemptHandle` with an exact A5 `InternalResult`. A wrong
or stale handle is a typed no-mutation error. With the matching handle, A7
reconstructs a fresh exact A5 graph through current model constructors and
compares its `ScorePackPin` to the stored handle's A4 `SeedPin`:

- exact ChallengeKey;
- scoring version and digest; and
- required generator version and digest.

The SeedPin fixes the A7-derived EvaluationBinding and immutable scientific
pins across retries; the same handle must retain the exact stored
ExecutionEnvironmentPin. AdmissionKind is stored in the handle and
kind-specific envelope; fixture completion requires exact fixture origin and
production cannot relabel the current fixture-only A5 result. These are
structural bindings, not proof that execution occurred. The trusted adapter
must pair result with handle; authenticated end-to-end result provenance
remains later receipt/evidence work because bare `InternalResult` has no
submission identity.

On the ratification base, current A5 accepts only fixture-origin pins/results,
so this sequence is implementable/testable only with conspicuous non-emission
fixture inputs and A7's private environment binding. After positive A3
admission, production stays `VALIDATED` and uncharged until every production
seam above exists. Current A6 is fixture-only and authoritative production
requires a valid later-owned receipt, so the two-argument operation remains
fixture-only; a production completion/A6/evidence surface requires
re-ratification. Fixture results may never be relabelled as production.

- A5 `SCORED` and `MANDATORY_GATE_FAILED` are completed scientific outcomes
  and may move A7 to lifecycle `SCORED`.
- A5 `PACK_NOT_READY`, pack/input/configuration errors, and computation or
  infrastructure errors use the retryability decision and ultimately
  `FAILED_INFRA`; none may move to `SCORED`, `PUBLISHED`, or
  `FAILED_STRATEGY`.
- A2 validation rejection is already terminal `REJECTED`.
- `FAILED_STRATEGY` is a trusted post-acceptance runner classification, not an
  exception catch-all, scientific gate failure, or infrastructure outcome.

For a matching handle, reconstruction/pin mismatch occurs while `RUNNING` and
uses retry/`FAILED_INFRA`; no A6 write or `SCORED` transition occurs. For a
completed valid result, one operation holds the A7 guard, records
`RUNNING -> SCORED`, clears the running handle, deliberately adapts fresh A6
keys, and passes that same transient result to its exclusively owned
`CardStore.write_internal`. A7 stores no duplicate result/digest/token.

`INSERTED` or exact `ALREADY_PRESENT` permits `SCORED -> PUBLISHED`; only an
A6 conflict/store failure after `SCORED` follows `SCORED -> FAILED_INFRA` with
the fixed remaining-balance refund under `PUBLICATION_INFRA`. `PUBLISHED` and
`FAILED_STRATEGY` retain the sole material-start charge. There is no
independent mark-scored or later publish API. A repeated completion after
terminal is a typed no-mutation error; the caller uses `get_status` and, if
published, `read_published`.

Both reads reconstruct SubmissionId/requester, verify structural requester
binding, and run under the same guard. Status returns only fresh ID/state;
card read additionally requires `PUBLISHED` and delegates to A6 positive
projection. No direct A6 store reference exists, so no caller can observe an
inserted card before A7 publication. There is intentionally no cross-store
crash/durability claim; future recovery/outbox design requires separate
specification and qualification.

## Expected future implementation surface

The authorized implementation should remain under `carbon/fees/`, likely
separating:

- nominal models/enums/events and fixed safe errors;
- immutable submission-resource limits, bounded candidate construction,
  typed hash, A4 binding construction, and the private execution-environment
  pin;
- guarded private record/index/FSM/attempt-handle/fee mechanics plus
  constant-size build/retention accounting;
- split A3 production/fixture admission and kind-specific private execution
  envelopes;
- orchestration for submit, policy-gated retry/terminal operations, fixed
  requester cancellation,
  one-operation A6 publication, and bounded status/card reads; and
- explicit package exports.

Exact filenames may follow repository conventions at implementation review;
the semantic boundaries above may not be collapsed. No database, ORM, queue,
clock, serializer, crypto package, optional scientific backend, Bittensor,
MCP, logging/metrics, leaderboard, evidence/receipt, or A8+ dependency is
needed. Use standard-library dataclasses, enums, `hashlib`, `struct`, `uuid`,
and synchronization.

## Future test matrix

The canonical focused path is
`tests/cpu/test_submission_fsm.py`, replacing the stale root-level ticket
path. Tests will include at least:

### Identity and hostile input

- exact nominal type/grammar/cross-type rejection, canonical UUIDv4 generation,
  injected first-candidate collision/no-record failure, and no caller-selected
  identity;
- independent Strategy hash golden vectors plus field/type/order/UTF-8/large
  integer/binary64 perturbations;
- iterative deep input; topology-preserving capture that keeps A2's exact
  `json.cycle` path and shared-DAG validity; post-A2 repeated-container
  rejection; and alias-free accepted/returned values;
- exact-at-limit acceptance and one-over rejection for every per-request
  policy field: total nodes, object/list cardinality, one string/key,
  complete identity bytes including a huge integer rejected before magnitude-
  byte materialization while admitted large-integer golden hashes stay
  unchanged, and challenge ID;
- deep-but-allowed iterative structure, excessive aggregate node/work and
  identity-byte cases, and observed source instability without an unbounded A2
  call; same-cardinality mutation races may return a bounded error or use one
  completed authoritative capture but never reread or mutate retained identity;
- inert-key/leaf tests prove no hostile `__hash__`, equality, display, or other
  method is invoked while preserving A2 `json.key_type`/`json.value_type` code
  and path;
- generic A2 failure and exact copied-cycle `json.cycle` on the bounded owned
  topology, plus a spy proving bounded lone-surrogate input reaches A2 before
  A7 identity rejection, and challenge mismatch, all without raw-input leakage;
- resource rejection before A2/A3 heavy processing, UUID generation, retained
  snapshot/hash/open index/record/attempt/fee, A5, A6, or science; no partial
  digest and no resource category/value/count/path/`repr` leakage;
- accepted Strategy hash golden equality under distinct admitting limits and,
  with the same injected UUID, byte-identical A4 EvaluationBinding;
- A9-absent direct-core enforcement, missing/invalid configuration failure,
  conspicuous finite fixture policy, and missing production values failing
  closed without a default;
- exact concurrent-build/retained-record/value-node/identity-byte capacity,
  cap-plus-one failure, permit/accounting rollback, duplicate-at-capacity
  success, invalid-flood bounding, and concurrent last-slot commit-once tests;
- exact A4 binding golden vectors, all-field perturbations, u32
  representability versus smaller A7 challenge-resource admissibility, retry
  stability, and terminal-resubmission difference;
- single-read requester/challenge-wrapper race and post-call mutation canaries,
  no remint/rebind API, and deterministic binding reconstruction from one
  record's owned fields; and
- no implicit/latest challenge version or duplicated A3 LIVE gate.

### Idempotency, FSM, and attempts

- fixture happy path and every legal exceptional edge;
- an in-test or A7-owned conspicuous non-emission fixture aligning exact
  ChallengeKey, A2-valid/A3-allowed backbone, Score Pack/result, and both pins;
  do not silently reuse the currently incompatible A3/A5 fixtures;
- separate A3 admission operations covering fixture success, fail-closed
  denial including caught typed A3 failure, escaping exception, exact-key
  backbone allowed/false/`RegistryError`, no fee event during either A3 call,
  crossing/no-fallback, and positive production eligibility followed by
  missing-seam no-charge/no-attempt behavior;
- every illegal edge, terminal immutability, and no `FAILED_INFRA` revival;
- sequential and concurrent open duplicates return one ID/record and no extra
  attempt/fee event;
- capacity-permitted terminal resubmit receives a new ID and A4 binding;
- invalid submissions are not open-indexed;
- atomic failure injection proves no partial record/index/state mutation;
- attempt numbering, kind-specific execution envelopes, immutable SeedPin and
  exact backend-profile/container-digest ExecutionEnvironmentPin, owned-copy
  mutation canaries, atomic no-fee queue construction, retry stability,
  stale-handle no-mutation for every new
  RUNNING disposition, exact event-bound historical replay, retry policy
  exhaustion, retry-no-recharge, no A8 runtime ownership, and minimal/no-
  sensitive history; and
- requester-only cancellation from every allowed source, every denied state,
  stale/racing requests, no fee event, and initial- versus retry-queued charge
  history.

### Fees and separation

- exact built-in integer acceptance including zero, with Boolean/float/
  negative/coercion rejection;
- closed event/context/admission kinds, monotonic sequence, exact
  source-attempt/historical-handle replay, mismatched replay conflict,
  replay-before-state precedence, initial-start comparison of both pins plus
  fixed refund configuration, closed `STARTED` versus no-envelope
  `ALREADY_STARTED`, sole start-time charge, required linkage/policy match,
  retry-no-recharge, conditional full-balance refund, aggregate cap, and
  completion's distinct publication-infra context plus alternate-callback
  replay exclusion;
- charge atomic with first `QUEUED -> RUNNING` and never on queue admission,
  cancellation, retry start, invalid/open duplicate, or repeat read;
- fixed refund mechanics for charged terminal infra, no event before first
  start, and `RETRY_CREDIT` retained only as future vocabulary; and
- import/signature/object-graph canaries proving fee values cannot reach A5
  `ScoreInput`, `ScoreEngine`, `InternalResult`, or weight/emission code.

### Scientific/operational and A6 boundary

- A5 `SCORED` and `MANDATORY_GATE_FAILED` completion versus `PACK_NOT_READY`;
- runner strategy failure versus retryable/non-retryable infrastructure,
  configuration, input, and computation failures;
- no infra/request failure creates a gate, scientific zero, A5 status/card, or
  emission-blame value;
- exact current handle with both stored pins, A4 SeedPin/A5 ScorePackPin
  challenge plus generator/scoring cross-binding, and wrong handle versus
  current integration failure dispositions kept distinct;
- deliberate nominal adaptation, A6 `INSERTED`/`ALREADY_PRESENT`, conflict,
  store error, exclusive-store pre-publication read exclusion, minimal status,
  and fixture public-card read gate; production A6/evidence stays unavailable
  pending re-ratification;
- A6 authorization/projection remains the only public result path; and
- forbidden-field/value/name/reference/serialization/error leakage canaries
  over the private record, accepted snapshot, errors, status view, and card
  path, expressly including all A4 hidden material and A8 raw runtime
  result/status/error payloads.

### Import and regression boundary

- no import of A8/A9/A10/A11, backend, MCP, leaderboard, observability,
  evidence, Bittensor, database, or optional dependency from A7 core;
- installed-wheel and outside-source-tree import isolation with no new runtime
  requirement;
- focused test plus related A2–A6 security/regression suites; and
- full default CPU, strict Ruff/Black, repository no-new-debt ratchet, and
  `git diff --check`.

## Ratification-only validation

For this documentation task, validation is limited to:

- exact base/remote/tree and branch/concurrency/status checks;
- changed-file allow-list and documentation-only diff inspection;
- internal reference, transition-set, state-set, checkbox, maturity-ledger,
  authorized-policy, resource-bound/error/order, and remaining-human-input
  consistency checks;
- independent read-only authority and implementation audits; and
- whitespace/Markdown hygiene.

No Python suite, new test, formatter, dependency operation, implementation
import, or A7 behavior claim belongs to this ratification. Existing A0–A6
closure evidence remains unchanged.

## Authorized policy and implementation start gate

Human authorization now fixes terminal `FAILED_INFRA` to `REFUND` when a
charge exists and fixes requester-bound/no-event cancellation from
`RECEIVED`, `VALIDATED`, and `QUEUED`. All other source states and actors are
denied. Initial queued cancellation is wholly uncharged; retry-queued
cancellation retains the already-earned material-start charge. These are no
longer open policy choices.

Production configuration still requires explicit human security/operations
values for every `SubmissionResourceLimits` field, plus fee amount/
denomination/schedule/version and retryable fault classes/count/budget; A7
supplies no defaults. Missing limits prevent executable store construction.
Those remaining inputs are necessary but not sufficient: production also
remains gated on the A3 qualified-pin adapter, human-qualified profile/
container evidence, OQ-005/OQ-006 A4 policy, ratified A5 and A6 production
paths, A8's handle-aware environment adapter, a valid later-owned receipt/
evidence adapter, and contract re-ratification. A later external production
cancellation surface must additionally bind an authenticated actor to stored
RequesterIdentity; structural equality is not a production credential. The A7
ledger does not prove payment authorization/reservation/settlement.

After this documentation is reviewed, explicitly human-authorized, and merged,
the next task is a fresh A7 implementation-start gate: fetch current main,
confirm A7 remains `todo` and unimplemented, recheck open PR/branch
concurrency, retain the fixed refund/cancellation outcomes, record explicit
finite fixture-only submission limits and fee/retry values plus the remaining
production limitations, then implement only the bounded fixture-capable A7
contract on a new branch while production remains `VALIDATED` and uncharged.
A8 needs its own later
pre-implementation reconciliation to consume A7 envelopes/handles/environment
pins and map outcomes. A later fixture A8 adapter may use only A4
FixtureOfficialContext/fixture-official derivation, while a later production
adapter may use only provider-acquired OfficialContext/official derivation
after OQ-005/OQ-006; A7 receives neither context nor derived seed, and A8
`invalid_strategy` cannot redo A7 schema/backbone denial.
A12 must later add completed A7 as a dependency before claiming fee-isolation
coverage. Do not create either work here. Do not merge or mark a future PR
ready without explicit authorization.
