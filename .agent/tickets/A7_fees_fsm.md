# Ticket A7 — Fees + permanent submission identity + submission FSM (C13)

**Wave:** A

**Build_Out:** v1.4 §5–§6 submission identity, fees, and C13

**Depends on:** A2 validation; A3 `ChallengeKey`; A4 `EvaluationBinding`; A5
result semantics; A6 private card storage

**Authority:** `.agent/DECISIONS.md` A7-R1 through A7-R15

**Implementation plan:** `.agent/plans/A7_fees_fsm.md`

## Ratification status

```text
A7 SPECIFIED / RATIFIED: YES only after this ratification is explicitly human-authorized and merged
A7 IMPLEMENTED: NO
A7 TESTED: NO
A7 PRODUCTION-QUALIFIED: NO
A7 WAVE STATUS: todo
```

Every checkbox in this ticket is future implementation/test work. This
documentation-only ratification does not satisfy one.

The human policy amendment selects terminal `FAILED_INFRA -> REFUND`,
requester-bound cancellation from `RECEIVED`/`VALIDATED`/`QUEUED`, and the
first atomic `QUEUED -> RUNNING` material-start boundary for the sole exam
`CHARGE`. Those selections do not authorize implementation or make this
candidate ratified before review and merge. The hostile-input amendment also
requires an injected immutable A7 submission-resource policy before full
Strategy/A3 challenge processing.

## Goal and ownership

Give every resource-admissible non-duplicate request that reaches the
structural A7 identity boundary an immutable Carbon-generated `SubmissionId`;
give every accepted Strategy an
exact resource-bounded canonical identity and A3 challenge-version binding;
persist the bounded process-local submission FSM atomically; record isolated
fee operations and minimal retry attempts; and publish completed scientific
results only through A6.

A7 owns permanent submission identity, Strategy identity/hash and an owned
accepted-Strategy snapshot, exact challenge-version binding, the concrete A4
evaluation binding, submission-input resource admissibility/capacity,
structural requester binding, process-local persistence, the core FSM,
open-submit idempotency, minimal execution-attempt history, fee-event
mechanics, infrastructure retry/refund mechanics, cancellation policy/
mechanics, and the A6 adapter.

A7 does not own TrainEval/backend execution or its runtime limits, metric
construction, MCP transport, leaderboard, logging/metrics, invariant
aggregation, execution transcripts, receipts/evidence/signatures, durable
evidence storage, Bittensor, score-to-weight mapping, or emissions. A9 may
later impose stricter transport/rate limits but is not A7's sole DoS boundary.
A8–A12 and later work must integrate with this FSM and may not introduce a
competing submission lifecycle.

## Submission boundary and identity

The conceptual submit boundary is:

```text
submit(
    requester_identity: RequesterIdentity,
    challenge_key: ChallengeKey,
    strategy: object,
) -> SubmissionId
```

`SubmissionResourceLimits` is mandatory immutable store/service
configuration, never a submit-payload field. It has exact positive built-in
integer fields, all within unsigned-64 and `max_challenge_id_bytes`
additionally within unsigned-32:

```text
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
```

Boolean, coercion, absence, sentinel/unbounded, mutable, default,
environment-derived, or submit-selected values are forbidden. Human protocol/
security/operations owners supply production values. Tests/fixtures inject
conspicuous finite fixture-only values. The policy is neither scientific nor
economic and is admission-kind-neutral because identity precedes queue kind. A
fixture-configured store is not production-capable or relabellable; approved
production values require a new store.

It uses the exact A3 `ChallengeKey`, with no default or “latest” version.
`RequesterIdentity` is a separate frozen/slotted nominal label using A3's exact
`validate_version` grammar. Equality is structural binding only, not
authentication, signature proof, Bittensor address proof, metagraph
membership, or chain registration. A7 performs constant-bounded exact wrapper-
shape checks and reads each requester/challenge nominal scalar exactly once.
It applies the challenge-ID resource cap to that local before A3's unbounded
regex/reconstruction, then validates and reconstructs fresh owned
`RequesterIdentity` and `ChallengeKey` values from the same captured
primitives. Every later comparison/binding uses those locals rather than
rereading a caller wrapper. Passing the A7 cap does not establish A3 validity
or change its grammar.

`SubmissionId` is a separate frozen/slotted nominal type. Carbon generates an
exact lowercase hyphenated UUIDv4; the caller cannot select it. It is opaque,
non-sequential, and embeds no requester/hotkey, challenge, time, state, or
attempt. Candidate generation and collision checking are atomic with record
creation. Exactly one UUID candidate is generated; collision raises a typed
no-record store error without regeneration. Reuse, rebinding, normalization,
and overwrite are prohibited and no such API exists; the Wave-A store enforces
collision rejection against its retained records. Retries retain the ID; a
resource-admissible submit after a terminal record gets a fresh ID when
new-record capacity remains. Fresh UUIDv4 generation across restart makes
accidental reuse
negligible but is not a durable global collision registry or restart-durability
claim. The store and caller receive separate fresh nominal wrappers.

For an exact request, A7 first acquires one non-blocking bounded identity-build
permit and iteratively constructs a resource-metered, topology-preserving
detached candidate. It stops before the next expansion/allocation when any
limit is exceeded. A2 validates that bounded owned topology; A7 applies its
separate repeated-container identity rejection afterward, so only an alias-free
accepted tree reaches hashing/storage. After unchanged challenge/binding checks
and complete canonical hashing, A7 atomically checks the open idempotency key
before new-record capacity. An open duplicate returns the prior ID without new
state, attempt, or fee. A new accepted request capacity-checks before one-
candidate ID creation and `RECEIVED`. Within-budget invalid Strategy input may
take the permanent `RECEIVED -> REJECTED` path if record capacity remains.
Resource/capacity or malformed-wrapper failure returns no ID or record.

## Canonical Strategy identity and A4 binding

A7's first iterative traversal constructs a request-local owned candidate while
enforcing total nodes, per-container cardinality, individual strict-UTF-8
string/key bytes, and complete accepted canonical identity bytes. No separate
nesting-depth field is exposed: accepted-tree depth cannot exceed total value
positions, while one-expansion memoization bounds shared/cyclic capture and
current A2 traversal without inventing unfolded depth.
A memo assigns one fresh exact built-in dict/list per source container, retains
shared/cyclic edges for A2, expands each source container once, and counts every
enumerated value position. Cardinality is checked before child enumeration;
UTF-8 is scanned incrementally without an unbounded encoded copy. A bounded
exact string/key that cannot encode as strict UTF-8 stays in the candidate and
records a later A7 identity failure. Invalid UTF-8 alone does not stop capture;
a provable resource overrun during that scan may. Integer `bit_length` rejects
when the complete tag/length/sign/magnitude frame cannot
fit before materializing the exact minimal unsigned big-endian magnitude.

Capture never hashes, compares, displays, or invokes a method on a hostile non-
string key or non-JSON leaf. Fresh request-local inert sentinels preserve A2's
stable type-issue code/path at the same container or string-key/list position
and can never be accepted, hashed, stored, or exposed. Observed source size,
iteration, or exact built-in access instability fails safely. Undetectable
same-cardinality replacement may instead contribute to one completed detached
capture; that candidate alone becomes authoritative, and no later pass rereads
caller containers. A resource overrun stops immediately and creates no
persistent or scientific artifact.

A7 calls current A2 `dry_validate` once on the bounded topology-preserving
candidate and does not redefine A2 fields, accepted values, issue order, or
semantics. A copied cycle retains A2's `json.cycle`; a bounded lone surrogate
reaches A2 before A7 identity rejection; a copied shared DAG remains A2-valid,
then receives A7's separate repeated-container identity rejection.
Only an A2-valid candidate with no repeated container can proceed as the alias-
free owned tree. After A2/A7 identity checks, A7 checks exact challenge-ID
equality and binding representability. An iterative bottom-up pass rechecks
exact frame lengths against unsigned-64 and the identity-byte policy, then
streams the unchanged document into SHA-256 without recursion or a second
complete serialized copy. No `StrategyHash` exists until the full stream
succeeds. Rejected raw input, sentinels, counters, candidates, and partial
digest are never retained. A2's separate parser/transport-limit policy stays
unresolved; A7 remains independently bounded without A9.

`StrategyHash` is a separate frozen/slotted nominal value formatted exactly as
`sha256:<64 lowercase hex>`. Its domain-separated, versioned typed encoding is
specified exactly by A7-R3: distinct tags for null, false, true, integer,
binary64 float, strict-UTF-8 string, list, and object; unsigned 64-bit lengths
and counts; exact list order; object members sorted by exact key UTF-8 bytes;
and minimal signed integer magnitude encoding. Dict insertion order is
irrelevant; list order is significant; `1` differs from `1.0`; positive and
negative floating zero differ. No Unicode normalization, `repr`, arbitrary
object serialization, JSON text serializer, or raw transport bytes enter the
hash. An A2-valid lone surrogate fails closed at A7's strict-UTF-8 identity
boundary. Limits determine only admissibility: the same accepted value has an
identical StrategyHash under every sufficiently large policy.

The Strategy's exact `challenge_id` must equal
`ChallengeKey.challenge_id`. The complete `ChallengeKey`, including version,
is immutable after acceptance. A7 neither duplicates A3 qualification
artifacts nor becomes a second LIVE gate.

A7 supplies A4 `EvaluationBinding` as the raw SHA-256 digest of a canonical
safe identity-input document: exact ASCII header
`carbon.a7.evaluation-binding.v1`, then A4-style one-byte-tag/four-byte
big-endian-length fields in this order:

1. `0x01`: `SubmissionId.value`;
2. `0x02`: the tagged `StrategyHash.value`;
3. `0x03`: `ChallengeKey.challenge_id`;
4. `0x04`: `ChallengeKey.version`.

These are the only fields. The document contains or derives from no A4
entropy/context/private root, official/master/derived seed, domain/role/draw,
hidden sample/exam identifier, or evaluation realization. Requester/validator
identity, state, attempt/retry count, fee, time, and randomness are excluded.
Retries preserve the binding; terminal resubmission changes it. A4 separately
binds the generator/scoring pins and later official randomness material. A7
retains the binding only inside its private safe A4 identity pin and never
stores or exposes a later context, derived seed, draw, or realization.

Before full A3 validation/reconstruction, A7 checks the challenge contribution
against injected `max_challenge_id_bytes`; exceeding it is a no-ID A7 resource
error, not A3 invalidity. A value under that practical cap must still satisfy
A3 unchanged. Before open lookup/accepted allocation, A7 also checks every TLV
payload fits unsigned-32. UUID/hash/version remain bounded, and the configured
challenge cap itself cannot exceed `4_294_967_295`. Neither check changes any
accepted `ChallengeKey` or EvaluationBinding byte.

One logical Carbon intake allocates this ID/binding once. Every validator for
that logical submission must consume the same canonical envelope; a
validator-local A7 instance may not mint a replacement. Wave A does not claim
the later durable/distributed propagation mechanism or its qualification.

“Shared exam identity” means validators share the same pinned exam contract,
pack/domain, and one submission-specific A7 binding for the same logical
submission. When combined later with separately governed A4 inputs it
participates in reproducible derivation, but A7 neither selects, contains,
constructs, persists, exposes, nor proves the realization. It does not require
different submissions to share an identical realization; OQ-005/OQ-006 still
govern provider/timing policy.

## Persistence and open-submit idempotency

The exact open key is the value tuple:

```text
(RequesterIdentity, ChallengeKey, StrategyHash)
```

No partial digest may form this tuple. Resource-limit failure occurs before a
complete hash and creates no key/ID/record. After a bounded complete identity,
an exact open duplicate is resolved before retained-store capacity and still
returns its prior ID at capacity. New accepted or within-budget-invalid input
must fit the applicable retained capacity before one-candidate UUID allocation
and atomic record/index/accounting commit.

The open states are exactly `RECEIVED`, `VALIDATED`, `QUEUED`, `RUNNING`, and
`SCORED`. An exact open duplicate atomically returns its existing
`SubmissionId` and creates no record, transition, attempt, `CHARGE`, or other
fee event. The terminal states are exactly `PUBLISHED`, `REJECTED`,
`FAILED_INFRA`, `FAILED_STRATEGY`, and `CANCELLED`; they leave the key free for
a later capacity-permitted submit with a fresh ID. This is pre-execution
request idempotency and is separate from A6 exact-duplicate card-write
idempotence.

The bounded Wave-A store is guarded, process-local, and in-memory. Submission
creation/open-key lookup, legal state transitions, attempt updates, and fee
operations are atomic within that process. It makes no database, restart,
crash-recovery, migration, retention, interprocess, distributed-concurrency,
or production-concurrency claim. Resource/fee/retry policies are immutable for
the store lifetime; reconfiguration requires a new store.

The minimum private record is:

```text
record_schema_version = "1.0"
submission_id
requester_identity
challenge_key
strategy_hash?             # absent until/when identity succeeds
owned_strategy_snapshot?   # accepted submissions only; no caller alias
state
admission_kind?             # PRODUCTION | FIXTURE; set at first queue admission
terminal_infra_disposition? # REFUND; fixed at first queue
terminal_infra_operation_key? # reserved with first RUNNING/CHARGE
current_attempt_number?
a4_seed_pin?                # safe exact A4 SeedPin identity; no seed/context material
execution_environment_pin?  # safe profile/digest reference; no runtime state
running_attempt_handle?     # exact private current A7 handle with both pins
attempt_history
fee_events
```

It has no public raw-Strategy getter and never contains raw official seeds,
entropy, draw IDs, hidden sample/exam identifiers, hidden evaluation realization, an A4 private
root, duplicated A5 result/scientific values, `ScoreInput`, predictions,
references, backend metrics, stack traces, private keys/credentials, receipt
signatures/evidence, A8 runtime result/status/error payloads,
leaderboard/logging/metrics/emission fields, or unbounded diagnostics.

Private error details, rejected/invalid raw values, and attacker-controlled
representations on error surfaces are never retained or echoed. The accepted
owned Strategy snapshot remains private. Operations may return bounded stable
codes/messages, but the minimum record stores no rejection reason or
diagnostic field.

The minimum record never contains `SubmissionResourceLimits`, per-request
counters, measured sizes, offending limit/category/path/value, or mutable
capacity accounting. The service keeps only constant-size aggregate build-
permit/record/value-node/identity-byte counters. Reservation, record/index
mutation, and accounting commit/rollback are atomic. No policy value or
measured unit enters StrategyHash, EvaluationBinding, fees, attempts, A5, or
A6.

Every nominal boundary value is exact-type validated and reconstructed before
lookup, dict-key use, or retention. Stored `SubmissionId`,
`RequesterIdentity`, `ChallengeKey`, fee keys, active handle/pin, and returned
IDs/views/events are separate owned objects. Low-level mutation of a
caller-held frozen wrapper cannot corrupt identity, indexes, bindings,
authorization, or fee history.

## Closed FSM and attempts

Resource limit/capacity rejection happens before `create`; it is not an FSM
state or transition and cannot become a later terminal status.

The only structural transitions are:

```text
create                 -> RECEIVED
RECEIVED               -> VALIDATED | REJECTED | CANCELLED
VALIDATED              -> QUEUED | REJECTED | CANCELLED
QUEUED                 -> RUNNING | FAILED_INFRA | CANCELLED
RUNNING                -> SCORED | FAILED_STRATEGY | FAILED_INFRA
RUNNING                -> QUEUED  # explicit infrastructure retry only
SCORED                 -> PUBLISHED | FAILED_INFRA
PUBLISHED              -> <none>
REJECTED               -> <none>
FAILED_INFRA           -> <none>
FAILED_STRATEGY        -> <none>
CANCELLED              -> <none>
```

`RECEIVED -> REJECTED` is an A7 structural/identity rejection. The closed
`VALIDATED -> REJECTED` seam is a trusted pre-queue denial: Wave A A7 uses it
only for A3 challenge admission, while later-owned authenticated payment/auth
denials may use the edge through their own explicit adapter. It is not a
generic transition/reason API. Missing later queue-admission fee/retry/pin
configuration leaves `VALIDATED` unchanged; this does not include the mandatory
construction-time submission-resource policy. A production queue operation calls
`ChallengeRegistry.is_effectively_live` on the stored exact key; a separate
fixture-only operation calls
`ChallengeRegistry.assess_live_eligibility(..., fixture_mode=True).eligible`.
Success atomically stores closed `AdmissionKind.PRODUCTION` or `FIXTURE`, both
safe identity pins, attempt `1`, and `QUEUED` without a fee event. For a new
queue admission A7 first requires exact `VALIDATED`, then eligibility runs and
A7 calls
`ChallengeRegistry.is_backbone_allowed` with the stored key and accepted exact
Strategy backbone. False eligibility or compatibility rejects before
attempt/charge with only the applicable bounded return code; false eligibility
deliberately includes typed registry/artifact
failures that current A3 catches and converts to false/ineligible. A7 does not
reclassify A3 reasons or copy its gate/allow-list. The record stores no reason;
the returned codes are `admission.challenge_not_live`,
`admission.challenge_not_fixture_eligible`, or
`admission.backbone_not_allowed`. A later submit after A3 recovery receives a
new ID when record capacity remains. A compatibility
`RegistryError`, or any exception escaping A3, leaves `VALIDATED` unchanged.
There is no generic mode flag, fallback, or
fixture/production relabel path.

The sole initial exam `CHARGE` is atomic with the later first
`QUEUED -> RUNNING` material-start transition. If a requester cancellation of
the initial queued attempt wins the store race, it is wholly uncharged; if
first start commits first, the state and charge are both `RUNNING` and
cancellation is denied.

The initial queue admission creates attempt `1`; `QUEUED -> RUNNING` retains
that number. An explicit retry atomically appends `RETRYABLE_INFRA` for
attempt `n`, creates attempt `n + 1`, and moves `RUNNING -> QUEUED` without
changing the submission, Strategy, challenge, or evaluation identity.
`FAILED_INFRA -> QUEUED` is forbidden. Attempt history is ordered and
append-only but contains only attempt number and the applicable lifecycle
event; it stores no backend metrics, seeds, predictions, references, A8 raw
runtime result/status/error payloads, or stack traces. A pre-queue cancellation
has no attempt; an authorized requester cancellation from `QUEUED` closes the
current queued attempt with `CANCELLED`.

`ExecutionEnvironmentPin` is A7's private frozen/slotted wrapper/comparison of
safe `backend_profile_id` plus `container_digest` references, not ownership of
an execution environment. The profile is a built-in 1–128-character ASCII
token under
`[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*`; the digest is exact tagged lowercase
SHA-256. A7 neither selects nor launches a backend. A8 owns concrete backend
selection/configuration, execution/runtime resource limits, invocation,
runtime objects, and raw runtime result/status/error semantics. No such
payload enters the pin or attempt record; those limits are distinct from A7's
submission-input policy.

The exact A4 `SeedPin` is also safe identity metadata, not seed material: it
contains only the owned ChallengeKey, generator/scoring versions and digests,
the A7 EvaluationBinding, and fixed scheme identifier. It contains no context,
entropy, private root, domain/role/draw, derived seed, or realization.

Before the first fixture queue commit, A7 constructs and validates one
exact owned A4 `SeedPin` and one exact owned `ExecutionEnvironmentPin` from the
stored challenge/binding and conspicuous trusted fixture-only generator, Score
Pack, backend-profile, and container-digest identity inputs. The atomic commit
stores both pins, fixture kind, attempt `1`, and `QUEUED` without charging.
This binds comparison references without implementing execution, selecting a
runtime, or claiming provenance. After an A3 LIVE result, production queue
additionally requires all
production adapters to resolve and cross-check before commit: an A3-owned
qualified generator/Score Pack/backend-profile adapter; a human-qualification-
owned adapter binding that profile to an exact container digest; a ratified A5
production origin/result path; an A8 handle-aware declaration of the exact
profile/container it will execute; and a configured A4 official-context policy
after OQ-005/OQ-006 resolution. Production also requires a re-ratified
production-capable A6 private-store/projection path and a later-owned valid
submission/pin-bound evidence/receipt adapter. A7 cross-checks every
profile/digest, and A8 configuration alone is not qualification. Actual A4
entropy/context is acquired only by the later A8/orchestration adapter and is
never selected, received, or stored by A7. The configured A6/receipt capability is
required before queue/start even though used after execution. Current production
seams are incomplete, so bounded Wave-A production remains fail-closed in
`VALIDATED`, uncharged and without an attempt. Every retry reuses both fixed
pins. A private
`ExecutionAttemptHandle` binds owned SubmissionId, attempt number,
AdmissionKind, SeedPin, and ExecutionEnvironmentPin. `QUEUED -> RUNNING`
builds the handle from retained pins. On attempt `1` only, that guarded
transaction also appends the sole `CHARGE`, reserves the distinct terminal
refund key, records `RUNNING`, and returns the envelope. Failed precommit first
start remains `QUEUED` and uncharged; retry start reuses the prior charge and
never appends another. Separate production/fixture start operations
return correspondingly typed private execution envelopes containing a fresh
handle, fresh alias-free Strategy, StrategyHash, and ChallengeKey; retries
change only attempt number. The stored handle adds no payload beyond the state,
attempt, kind, and safe pins already retained.

Every first application of an asynchronous `RUNNING` outcome must return the
exact current handle. Wrong/stale handles fail without mutation. The same
applies to retry, terminal-infra, strategy-failure, `PACK_NOT_READY`, and
scientific completion callbacks. The only carve-out is exact replay of an
already-recorded fee-bearing transaction: it validates the supplied historical
handle against the event's source attempt and returns that event without
mutation before current-state/current-handle checks. The handle is structural
coordination with a trusted later adapter—not authenticated result provenance,
evidence, or A8 implementation.

`FAILED_STRATEGY` is only a trusted post-acceptance `RUNNING` classification
that the submitted Strategy cannot execute/evaluate. A2 rejection is
`REJECTED`; infrastructure/configuration failure is `FAILED_INFRA`; neither is
a failed physics gate or scientific zero. Retryable infrastructure failure
may retry only when recovery is performed and the injected retry policy
permits it; otherwise it terminalizes as `FAILED_INFRA`. Retry
class/count/budget remains an injected policy, not a hard-coded production
value.

## Fee contract

Production fee amount, denomination/asset, schedule, policy version, and retry
classes/count/budget remain human/protocol-owned. A7 has no built-in,
fallback, or environment-derived production fee. The terminal
`FAILED_INFRA` default is now fixed to `REFUND`. Tests may inject conspicuous
fixture-only fee/retry values under that fixed terminal rule.

`FeePolicyKey` and `FeeOperationKey` are separate frozen/slotted nominal labels
using the exact A3 `validate_version` grammar and are reconstructed before
event lookup/retention. A trusted economic/orchestration adapter—not the raw
submit payload—supplies the stable operation key. Every amount is an exact
built-in integer in the supplying policy's minor units, at least zero;
Boolean, float, negative, and coerced amounts reject. Events are append-only
and monotonically sequenced per submission: exact built-in integer sequence
starts at `1` and increments by exactly one. The minimum payload is:

The fee kind remains closed to `CHARGE`, `REFUND`, and `RETRY_CREDIT`; its
coupled operation context is independently closed to `INITIAL_RUN_START`,
`RETRY`, `TERMINAL_INFRA`, and `PUBLICATION_INFRA`. `RETRY_CREDIT` and
`RETRY` remain representable only for a future separately ratified policy;
bounded Wave A never selects them as the terminal remedy or during retry.

```text
sequence
operation_key
policy_key
kind                 # CHARGE | REFUND | RETRY_CREDIT
operation_context    # one closed FeeOperationContext value
admission_kind       # PRODUCTION | FIXTURE
source_attempt_number # exact positive attempt coupled to this event
amount_minor
charge_operation_key?  # required for REFUND/RETRY_CREDIT; absent for CHARGE
```

The operation-idempotency scope is `(SubmissionId, FeeOperationKey)`. Exact
replay of the same kind/context/admission-kind/source-attempt/amount/policy/
linkage returns the existing event; reuse with a different payload is a typed
conflict. `CHARGE`
records the existing queued attempt `1`; later events identify the attempt whose
coupled operation produced them. A submission has at most one `CHARGE`,
appended atomically only with its first `QUEUED -> RUNNING` material-start
transition. Queue admission, cancellation, and retry start never append a
charge. An adjustment must link to that exact
charge, use its policy key, and cumulative `REFUND` plus `RETRY_CREDIT` amounts
cannot exceed the charge. Neither adjustment can exist without a charge.
The terminal-infrastructure operation key reserved atomically with first start
is distinct, cannot be used by another event, and is consumed only by the fixed
`REFUND` under `TERMINAL_INFRA` or internal `PUBLICATION_INFRA`. Duplicate
submit and repeated result reads never charge. An A7 ledger event does not
prove production payment authorization, reservation, transfer, or settlement.
`Miner_MCP.md`'s paid-loop/SubmitReceipt sequence is later product/transport
shorthand; it neither moves this ledger charge before material start nor makes
the fixture event a payment receipt.

For a transaction that appended a fee event, safe boundary/submission/key
reconstruction and existing operation-key replay/conflict resolution precede
policy/configuration, lifecycle, current-handle, and every other fallible
operation prerequisite; A3 assessment belongs to the earlier no-fee queue
admission. Only a new key reaches those checks. Exact
replay returns the prior event and changes nothing even after state
advancement/terminalization. A new key must pass source-state validation before
operation-specific handle/policy checks. If the
original operation required a handle, the supplied historical handle must
equal the one reconstructed from the event attempt plus immutable stored
submission/admission/scientific/environment-pin fields. A different attempt,
handle, or payload conflicts.

Initial kind-specific start generates rather than accepts its handle. Its
private result is the closed sum `STARTED(FeeEvent, ExecutionEnvelope)` or
`ALREADY_STARTED(FeeEvent, SubmissionState)`; the replay form has no envelope.
The immutable store policy supplies exact fee policy/amount, while the trusted
start adapter supplies stable charge and distinct refund operation keys. First
application requires exact `QUEUED`, attempt `1`, no charge, and both safe
pins; it atomically stores the handle/refund key, appends `RUNNING` and the
`INITIAL_RUN_START` charge, transitions to `RUNNING`, and returns closed
`STARTED` with event plus private envelope. Failed precommit validation leaves
`QUEUED` uncharged.

Exact start replay also compares the refund key, SeedPin, and
ExecutionEnvironmentPin, and returns closed `ALREADY_STARTED` with only prior
event/current status—never an envelope or a second A8 launch authorization.
Queue admission, requester cancellation, and retry start have no fee event and
no fee-operation replay claim.
There is no standalone adjustment operation. `complete_and_publish` is not a
fee-operation replay surface even when A6 failure internally consumes the
reserved refund; repeated completion remains a typed terminal-state error.
Its event uses distinct `PUBLICATION_INFRA` context, so a later
`TERMINAL_INFRA` callback conflicts rather than retrieving it.

Fee policy, amount, and events have no dependency, argument, field, or
conversion path into A5 `ScoreInput`, `ScoreEngine.score`, `InternalResult`,
or later score-to-weight/emission calculation. Fee is never score.

## Rejection, infrastructure, and publication

Missing/invalid mandatory limits fail store construction with typed
`SubmissionResourcePolicyError` and constant code
`submission.resource_policy_unavailable`. Any per-request limit overrun returns
typed `SubmissionResourceError` with
`submission.resource_limit_exceeded` before UUID/hash/record/FSM; exhausted
build/retained capacity returns the same typed error with
`submission.resource_capacity_exceeded`, with no new ID or stored candidate.
The errors disclose no category, policy value, count, byte size, path, raw
value, or `repr`. They create no open key, attempt, fee, queue admission, A5/A6
artifact, gate, scientific zero, or emission blame and are never
`FAILED_STRATEGY`, `FAILED_INFRA`, or `PACK_NOT_READY`.

A within-budget Strategy rejected by A2, bounded capture/post-A2 alias rule,
strict-UTF-8/frame/binding identity, or challenge-ID matching receives a
permanent ID when record capacity remains and atomically records
`RECEIVED -> REJECTED`, but no open-key entry, attempt, charge, A5 result, A6
card, physics gate, scientific zero, or emission disposition. It returns only
bounded stable codes/messages and stores no reason/diagnostic, hostile raw
input, attacker-controlled `repr`, or unbounded diagnostics.

The A7 submission-resource/fee/retry policy sets are immutable for the store
lifetime; reconfiguration requires a new store. Kind-specific A3
admission runs before the no-fee queue transition: false rejects as above.
After an eligible result, first queue admission requires complete fee/retry
configuration, both valid kind-specific pins, and, for production, every
production seam above. It stores fixed terminal disposition `REFUND`; missing
that later queue configuration leaves `VALIDATED`, uncharged, and without an
attempt. The mandatory submission-resource policy already exists before
`submit`.

First start supplies stable charge and distinct refund keys, then commits them
only with the sole charge and `RUNNING`. A pre-first-start failure from initial
`QUEUED` terminalizes as `FAILED_INFRA` without a fee event because no charge
exists. Once charged, an operational failure uses the explicit human-owned
retry policy. If retry is authorized, the matching handle moves the same
submission to next-attempt `QUEUED` without another charge or current-policy
fee event. Otherwise charged retry-`QUEUED`, `RUNNING`, or `SCORED`
terminalizes with linked `REFUND` for exactly the remaining balance.
`RETRY_CREDIT` remains future vocabulary, not the Wave-A terminal or retry
default. A5 `PACK_NOT_READY` and pack/input/computation failure use this path,
never `FAILED_STRATEGY`. Partial/private operational evidence remains
later-owned and never becomes A5 input, a gate, scientific zero,
EvaluationCard, or emission blame.

Each A7 instance exclusively owns its dedicated A6 `CardStore`; the store is
not exposed, and all A6 access occurs under the A7 guard. Scientific
completion/publication is one operation:

```text
complete_and_publish(ExecutionAttemptHandle, InternalResult)
```

A wrong/stale handle returns a typed no-mutation error. For the current handle,
A7 reconstructs a fresh exact A5 graph and compares its `ScorePackPin`
ChallengeKey, generator version/digest, and scoring version/digest with the
stored handle's A4 `SeedPin`; fixture/production admission kind cannot cross.
The handle must also retain the exact stored `ExecutionEnvironmentPin`; no
lifecycle score exists without both pins. A current integration mismatch
follows retry/`RUNNING -> FAILED_INFRA`, before `SCORED` or A6 write.

Current A5 accepts only fixture-origin pins/results. A7's narrow environment
pin makes a structurally bound fixture happy path possible with conspicuous
non-emission inputs, but does not claim execution or authenticated provenance.
Current A6 is also fixture-only, while an authoritative production result needs
a valid later-owned receipt. The two-argument operation is therefore
fixture-only. Production completion remains unavailable/fail-closed until every
production seam above exists and a receipt-gated A6 operation is re-ratified;
no fixture result may be relabelled.

Only A5 `SCORED` or `MANDATORY_GATE_FAILED` may then record
`RUNNING -> SCORED`. With that same transient result and guard, A7 adapts fresh
distinct A6 keys and calls `CardStore.write_internal`. `INSERTED` or exact
`ALREADY_PRESENT` permits `SCORED -> PUBLISHED`; A6 conflict/store failure
follows `SCORED -> FAILED_INFRA` with the fixed remaining-balance refund under
`PUBLICATION_INFRA`. `PUBLISHED` and `FAILED_STRATEGY` retain the sole
material-start charge. There is no separate mark-scored/publish API or
retained A5 result. A repeated completion after terminal state is a typed
no-mutation error.

`get_status(SubmissionId, RequesterIdentity)` returns a fresh
`SubmissionStatusView` containing only owned submission ID and current state
after structural requester comparison. `read_published` additionally requires
exact `PUBLISHED`, adapts fresh A6 keys, and returns only A6
`EvaluationCard`. Both reads are fee-free. Neither exposes Strategy/hash,
attempt/history, fees, rejection reasons, pins, diagnostics, or
`InternalResult`; A9 later owns transport.

## Authorized policy and remaining human gates

Terminal `FAILED_INFRA` now has fixed default `REFUND` for the remaining
balance whenever a charge exists. `RETRY_CREDIT` remains supported vocabulary
for a future separately ratified policy and is not the bounded Wave-A default.

Cancellation exact-type validates the submitted ID/requester and requires
structural equality with the stored requester under the A7 guard. That
requester alone may cancel from `RECEIVED`, `VALIDATED`, or `QUEUED`.
`RUNNING`, `SCORED`, `PUBLISHED`, `REJECTED`, `FAILED_INFRA`,
`FAILED_STRATEGY`, and `CANCELLED` deny cancellation; `CANCELLED` is terminal.
Whichever legal start, terminalization, or cancellation transition commits
first wins, and a stale request cannot regress state.

Cancellation creates no charge or refund event. An initial queued cancellation
is wholly uncharged. A retry-queued cancellation creates no new event and
leaves its prior material-start charge unchanged; if `FAILED_INFRA` wins
instead, its refund applies. Structural equality is not production
authentication. A later external production cancellation surface must bind an
authenticated actor to stored RequesterIdentity; no validator/operator path or
signature/Bittensor claim is implied. The ledger likewise makes no production
payment authorization/reservation/settlement claim.

Production configuration also requires explicit human security/operations
values for every `SubmissionResourceLimits` field, plus human-owned fee amount/
denomination/schedule/version and retryable fault classes/count/budget. Those
are required inputs, not A7 defaults; missing resource limits prevent
executable production store construction. They are not sufficient without the
A3/backend-qualification/A4-OQ-005/OQ-006/A5/A6/A8/evidence production seams
and re-ratification above. A bounded implementation may inject conspicuous
finite fixture-only submission limits and fee/retry values under the fixed
terminal/cancellation semantics while every production path remains
fail-closed.

The untouched A8 ticket's generic mode/status API is not an A7 integration
contract. A8 must later reconcile to A7's kind-specific envelope, current
handle, execution-environment pin, and status-to-FSM mappings before any
integration. A later A8 fixture adapter may use only A4
`FixtureOfficialContext` and fixture-official derivation, never
MOCK/provider-official context; a later production adapter may use only
provider-acquired `OfficialContext` and official derivation after
OQ-005/OQ-006. A7 receives no context, derived seed, or raw runtime payload.
A8 `invalid_strategy` cannot redo A7 schema/backbone denial. This ticket
creates no A8 work.

The untouched A12 ticket must later add completed A7 as a dependency and reuse
this fee-isolation boundary before claiming fee-versus-score coverage. This
ticket does not edit or start A12.

## Future implementation definition of done

- [ ] Frozen/slotted nominal identities and closed enums implement A7-R2,
      A7-R5, A7-R8, and A7-R10 without aliasing A3/A4/A6 nominal types;
      one injected UUID collision fails before record creation.
- [ ] Immutable explicit `SubmissionResourceLimits` and bounded topology-
      preserving capture precede A2; exact-at-limit/one-over tests cover nodes,
      cardinality, string/key and complete identity bytes, a huge integer
      rejected before magnitude allocation with admitted golden hashes
      unchanged, and challenge-ID bytes. Copied cycles retain A2's exact issue;
      a spy proves a bounded lone surrogate reaches A2 before A7 rejection;
      shared DAGs remain A2-valid then A7-reject; accepted values are alias-free.
      Hostile non-string keys/leaves invoke no hash/equality/display/arbitrary
      method while inert sentinels preserve A2 type-issue code/path. Observed
      capture instability fails boundedly; an undetectable race may instead use
      one authoritative detached candidate that is never reread from the caller.
- [ ] Low-level mutation of every input/returned wrapper, handle, view, and
      event cannot alter stored identity, indexes, bindings, authorization, or
      fee history; requester/challenge scalars are captured once and the same
      locals drive cap, validation, reconstruction, comparison, and binding.
- [ ] Exact A4 binding bytes have golden, field-perturbation, and unsigned-32
      representability tests, distinguish smaller A7 challenge admissibility,
      and stay identical across retry and distinct admitting resource policies
      when the same UUID is injected.
- [ ] Process-local guarded store implements the minimum private record,
      immutable policy set, exclusively owned A6 store, atomic open-key
      lookup/create, terminal resubmission, finite build/retained capacities,
      and reservation/accounting rollback without per-record counters.
- [ ] Fixture happy path is exactly
      `RECEIVED -> VALIDATED -> QUEUED -> RUNNING -> SCORED -> PUBLISHED`.
- [ ] An in-test or A7-owned conspicuous non-emission fixture aligns exact
      ChallengeKey, an A2-valid/A3-allowed backbone, Score Pack/result, SeedPin,
      and ExecutionEnvironmentPin; existing incompatible A3/A5 fixtures are not
      silently relabelled or used to change A2–A6 semantics.
- [ ] Every illegal/terminal transition fails without partial state, attempt,
      index, or fee mutation.
- [ ] Separate A3 production/fixture admission operations cover fixture
      success, fail-closed false including caught typed A3 failure, escaping
      failure, exact-key backbone allowed/false/`RegistryError`, no fee event
      during either A3 call, crossing/fallback rejection, and current
      production eligible-but-missing-seam no-charge/no-attempt behavior.
- [ ] Open duplicate concurrency returns one ID—even at new-record capacity—and
      never duplicates a charge; last-slot creation commits once, capacity and
      invalid-flood tests remain bounded, and A6 card-write idempotence stays
      separate.
- [ ] Within-budget invalid Strategy records safe `REJECTED` before queue/start
      charge. Resource limit/capacity errors create no ID, record, partial hash,
      key, attempt, fee, A5/A6/science path, and retain or echo no hostile raw
      value, resource category/value/count/path, or `repr`.
- [ ] Attempts start at `1`; retry is atomic, increments once, retains all
      scientific identity plus both pins, rejects stale handles for every new
      `RUNNING` callback, permits only exact historical fee-event replay, and
      never revives terminal `FAILED_INFRA`; retry start never charges, and the
      fixture environment pin has exact backend/container golden and mutation
      coverage without an A8 runtime-ownership claim.
- [ ] Fee amount/type bounds, closed vocabulary, exact replay/conflict,
      operation-context/admission/source-attempt/historical-handle binding,
      replay-before-state precedence, initial-start comparison of both pins and
      refund configuration, `STARTED` versus no-envelope `ALREADY_STARTED`,
      adjustment linkage/cap, sole start-time charge, retry-no-recharge,
      conditional full-balance refund, publication-infra replay exclusion, and
      charge/`RUNNING` atomicity are proven.
- [ ] Tests prove fee data cannot enter A5 scoring or later weight/emission
      inputs.
- [ ] Tests distinguish `REJECTED`, `FAILED_STRATEGY`, `FAILED_INFRA`, A5
      mandatory-gate failure, A5 `PACK_NOT_READY`, resource-limit error,
      resource-capacity error, and missing-policy configuration error without
      scientific-zero or emission-blame conversion.
- [ ] A6 integration proves exact cross-binding, inserted/already-present
      one-operation publication, conflict/store failure routing, exclusive
      pre-publication read exclusion, status authorization, and positive
      fixture-only projection after `PUBLISHED`; production completion remains
      unavailable without re-ratified A3/backend-qualification/A4/A5/A6/A8/
      evidence seams.
- [ ] Private-record and public-surface leakage tests cover every forbidden
      field/category, including resource policy/counters/measurements, A4 hidden
      material, A8 runtime payloads, and bounded errors.
- [ ] Fixed `REFUND` and requester-only cancellation cover every allowed/denied
      state, initial- versus retry-queued economics, stale requests, and atomic
      start/cancel/terminalization races; production auth/payment claims remain
      absent.
- [ ] Full default CPU suite, focused isolation, installed-wheel/outside-tree
      import, Ruff, Black, and repository quality-ratchet checks pass.
- [ ] Direct A7 resource enforcement works with A9 absent, conspicuous finite
      fixture-only limits are non-production, missing production limits fail
      closed, and no new runtime dependency or A8/A9/A10/A11 implementation
      enters A7.

**Canonical focused tests:**
`python -m pytest tests/cpu/test_submission_fsm.py -q`

## Must not

Do not use fee as a score/weight/emission feature. Do not emit weights from the
FSM. Do not treat infra/configuration failure as scientific failure. Do not
add execution, transport, observability, evidence/receipt, leaderboard,
Bittensor, or A8+ behavior. Do not classify submission-resource rejection as
FSM rejection, infrastructure/strategy failure, A5 status, or emission blame;
do not rely on A9 as its sole guard. Do not mark A7 `in_progress` or `done`
until the separate implementation and closure gates are actually satisfied.
