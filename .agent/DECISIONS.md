# Agent decisions log

## 2026-08-22 — A5 closure after reviewed merge

**Merge topology and review.** The bounded implementation started from exact
base `af43d68ec3b9dcfd8818a61ab219759b2c859d78` and was independently reviewed
at exact head `fc2f27a7150d5ed0e374e7cd79eea40ef7ede556`. PR #20 merged normally as
`6f813e979ef6edde2b8f1821d1ac26f62938633a`, with tree
`54e3472e34731b64d796f8db7d091da70c6afd43` and ordered parents
`af43d68ec3b9dcfd8818a61ab219759b2c859d78` then
`fc2f27a7150d5ed0e374e7cd79eea40ef7ede556`. The reviewed head is ancestral to
current `main`, and its tree is exactly the merge tree. GitHub contains no
formally submitted approval object, and this record does not claim one;
independent reviews and explicit human authorization are the process evidence.
No amendment or repair commit was made or required.

**Exact-head review evidence.** PR CI run `32474141634` completed successfully
for reviewed head `fc2f27a7150d5ed0e374e7cd79eea40ef7ede556`. Its CPU job passed
`923` tests in `9.57s`; Code quality reported `Ruff 757/776; Black 62/68`,
removed debt `Ruff 19, Black 6`, eight changed Python files, no new debt, and
all changed Python files clean.

**Post-merge evidence.** Push CI run `32494936120` completed successfully for
the exact merge commit. The CPU job passed `923` tests in `10.23s`. Code quality
reported `Ruff 757/776; Black 62/68`, removed debt `Ruff 19, Black 6`, eight
changed Python files, and no new debt, with every changed Python file clean.
The sole canonical fixture remains
`tests/fixtures/score_packs/a5_fixture_v1.json`, exactly 2,126 bytes, with
external digest
`sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57`.

**Closure and boundary.** A5 is **SPECIFIED / RATIFIED: YES**,
**IMPLEMENTED: YES on current `main`**, and **TESTED: YES only to the bounded
fixture CPU scope**; it remains **PRODUCTION-QUALIFIED: NO**. **WAVE STATUS:
`done` after this closeout is merged.** The merge and this documentation-only
closeout added no dependency or lockfile, A6 or later behavior, LIVE or
production-origin pack, or emission-authoritative path. Passing regression CI
is evidence for the merged bounded implementation, not LIVE, scientific,
emission, or production qualification. A5-R1 through A5-R14 remain unchanged.

## 2026-08-21 — A5 bounded fixture implementation evidence

**Scope and disposition.** The authorized implementation branch
`agent/a5-scoring-engine` starts from exact main
`af43d68ec3b9dcfd8818a61ab219759b2c859d78`. It preserves A5-R1 through
A5-R13 and implements the maintainer-authorized A5-R14 clarification in this
same branch. The implementation **KEEPS / WRAPS** A3 identity validation and
descriptor-relative secure artifact access, **REPAIRS** that public boundary
narrowly to return one bounded digest-verified byte sequence, and **REPLACES**
legacy scoring only as canonical authority without modifying legacy files.
No A6+ owner, dependency, production-origin pack, LIVE path, or emission path
is added.

**Bounded artifact and behavior.** The branch contains the init-closed
fixture-only pack/input/result models, strict digest-first schema-1.0 JSON
loader, clarified `ScoreEngine.score(ScoreInput | None, LoadedScorePack)` entry,
complete declared-order gates, exact scalar transforms, and fixed-order
`python_binary64_v1` log-space aggregate. The sole runtime fixture is exactly
2,126 bytes at `tests/fixtures/score_packs/a5_fixture_v1.json`; its required
external digest is
`sha256:255923831905a84f55a88d8575e8ebcab42f3351676d6cf5ac9038dcc495fb57`.
The digest is absent from the JSON, all values/identities are visibly
synthetic, and every result is structurally false-eligible.

**Acceptance and maturity.** Python 3.11.11 passed the focused A5 suite at
`279 passed in 0.45s`, the related registry/package/leakage suite at
`195 passed in 4.07s`, and the complete default CPU suite at
`923 passed in 5.04s`. Compilation, eight-file Ruff/Black checks, the repository
quality ratchet, built-wheel outside-tree import/scoring isolation, and diff
hygiene passed. Independent final review found no remaining P0/P1/P2 issue.
Therefore A5 is **SPECIFIED / RATIFIED: YES**, **IMPLEMENTED: YES on the bounded
draft branch head**, **TESTED: YES only for the recorded fixture CPU scope**,
and **PRODUCTION-QUALIFIED: NO**. Wave status remains `in_progress`; merge,
`done`, closeout, A6, and later work require separate authorization.

## 2026-08-21 — A5 pre-implementation scoring contract ratification

**Status, base, and scope.** An independent GitHub read and a fresh local
fetch both resolved `origin/main` to exact commit
`3d80e09549964251833b0d8a70093cfceb51a501`. At that point GitHub reported no
open pull request and no remote branch matching A5 or scoring work. The
canonical `carbon/scoring/` package contained only its A0 marker; no A5
engine, model, loader, runtime Score Pack, default-CPU A5 test, or A5 plan
existed. On that repository truth, the maintainer ratifies A5-R1 through
A5-R13 below as the bounded implementation contract for future A5 work.

This entry is documentation, not implementation. A5 remains `todo`, not
`in_progress`; every A5 Definition-of-Done item remains unchecked. No Python,
fixture artifact, test, or dependency is added by this ratification. A5 is
**SPECIFIED / RATIFIED**, but it is **NOT IMPLEMENTED**, **NOT TESTED**, and
**NOT PRODUCTION-QUALIFIED**. A6 and all later tickets remain out of scope.

**A5-R1 — Canonical runtime artifact.** The canonical runtime Score Pack is
one strict UTF-8 JSON byte sequence. The runtime loader accepts no YAML and
adds no YAML dependency. YAML may be used only before publication as an
authoring or documentation form; a separately reviewed conversion must
produce the JSON bytes that are actually pinned and loaded. Runtime validation
rejects a UTF-8 BOM, invalid UTF-8, duplicate object keys, non-JSON numeric
constants, trailing data, a non-object top level, missing required members,
unknown members, and type-invalid members. Parsing or reserialization never
redefines the artifact identity.

**A5-R2 — Exact bytes and external digest.** Pack identity is the exact source
bytes together with a required external tagged SHA-256 in A3's only accepted
form, `sha256:<64 lowercase hexadecimal characters>`. The expected digest is
not read from or trusted to a field inside the bytes. It is checked against
SHA-256 of the untouched bytes before UTF-8 decoding and JSON parsing.
Whitespace, line endings, member order, and every other byte therefore affect
identity. There is no self-reported `content_hash`, content-hash stub,
path-only identity, hash of parsed/normalized content, fallback pack, or
missing-digest fallback.

**A5-R3 — Complete exact pin.** One immutable A5 pack pin binds all of:

- exact A3 `ChallengeKey` — challenge ID and exact challenge version;
- exact scoring version and the A5-R2 external scoring digest;
- exact required generator version and tagged generator digest;
- exact Score Pack schema version;
- exact numerical-profile identifier `python_binary64_v1`; and
- exact Boolean `fixture_origin`.

Every field is required, exact-match, and non-defaultable. Generator and
scoring versions reuse A3 `validate_version`; tagged digests reuse A3's exact
digest contract. A5 adds no separate `gate_version`: hard-gate definitions and
thresholds are already bound by the exact Score Pack bytes. The loaded pack,
external registry/loader expectation, and `ScoreInput` pin must agree exactly
before any scientific gate is evaluated.

**A5-R4 — Closed validator-authorized scalar input.** A5 accepts only an
immutable, validator-authorized `ScoreInput` whose schema is closed and whose
payload contains the exact A5-R3 pin plus the complete scalar values required
by that pack. Expected gate/component keys must match exactly; missing,
duplicate, extra, aliased, or unknown keys reject. Free-form metric mappings,
arrays, tensors, predictions, references, raw draws, raw percentiles, and
miner-supplied values are not `ScoreInput`. Prior similarity,
`estimate`/`light_*`, exam fee, mock-only metrics, product-battery results, and
any other forbidden field are rejected rather than ignored. A8 or later
validator-owned metric operators own model execution, predictions,
references, relative-error generation, raw percentile computation, and
construction of an authoritative scalar `ScoreInput`.

**A5-R5 — Binary mandatory hard gates.** Hard-gate decisions are binary.
Resolved threshold gates pass if and only if the validated binary64 actual is
strictly less than the validated binary64 threshold; equality fails. A
validator-authorized Boolean predicate gate passes only on exact `True`.
Before decision, the mandatory gate set and its actuals must be complete. Any
actual failure of a mandatory gate atomically requires both
`combined_score = 0.0` and `eligible_for_emission = False`. A sigmoid may be a
non-emission diagnostic or a soft-leg transform, but it never determines an
official hard-gate pass. A zero soft leg is distinguishable from a mandatory
gate failure even though both can yield a zero combined score.

**A5-R6 — Configuration/input/infra is not scientific failure.** A missing or
malformed pack, absent/mismatched external digest or pin, malformed or
incomplete `ScoreInput`, unknown field, and infrastructure/reference failure
are non-scientific failures. They create no synthetic failed gate and no
scientific zero. Infra/reference statuses cannot construct authoritative
`ScoreInput` or enter `ScoreEngine.score`. Those cases return or propagate a
typed non-scoring error with no combined score and a non-emitting disposition;
they do not produce `MANDATORY_GATE_FAILED`.

**A5-R7 — Weighted-geometric top level and exact weights.** The only A5
top-level aggregate is the weighted geometric mean. The pack is the sole
source of the weight map. Every weight is a strictly positive JSON number;
the original JSON number values are validated with exact decimal arithmetic
to sum exactly to decimal `1` before binary64 conversion. The key set must
match the score-bearing top-level legs exactly. Missing, extra, zero,
negative, non-finite-after-conversion, or non-unit-sum weights reject. The
engine never normalizes, renormalizes, clamps, defaults, or substitutes
weights. The same no-default rule applies to required within-leg weights where
the pack schema uses a unit-sum weight map. Decimal unit-sum validation uses
`decimal.Decimal` source lexemes and exact common-base-10 integer coefficient
addition derived from `Decimal.as_tuple()`; it is independent of ambient
decimal context and never uses a binary64 tolerance. The 0.45/0.30/0.25 values
are a pack example/baseline only, never engine constants.

**A5-R8 — Wave A numerical profile.** The exact A5 profile identifier is
`python_binary64_v1`. It uses the Python standard library and built-in
binary64 `float` only for scientific gate and score arithmetic; NumPy, JAX,
Torch, alternate dtypes, and dependency-specific math are outside this
profile. Pack JSON numbers are first retained as exact standard-library
decimal values for schema/range/sum validation, then explicitly converted to
binary64. Conversion must remain finite and must preserve required positivity.
Runtime numeric `ScoreInput` slots require exact built-in `float` values;
Boolean, integer, string, subclassed, coerced, NaN, and infinite values reject
where a number is required. Thresholds are finite and strictly positive; gate
error actuals are finite and non-negative; authorized component scores are in
the closed interval `[0.0, 1.0]`. No epsilon floor, clipping, coercion,
rounding, or silent range repair is permitted.

After all mandatory gates pass, a component score equal to binary64 zero takes
an exact zero branch and returns `combined_score = 0.0` without evaluating its
log. Otherwise, in fixed top-level order `(physics, robustness, accuracy)`, the
engine evaluates each term as binary64
`weight * math.log(component_score)`, combines that materialized three-term
tuple with `math.fsum`, and applies `math.exp` exactly once. JSON object source
order has no arithmetic effect. Within-leg weighted sums use `math.fsum` in
their declared array order; the exact scalar-transform operation order and
stable logistic branches are recorded in `Design_Specs/Scoring.md` §§6–7. The
result is not rounded or clamped. Any non-finite or out-of-range
intermediate/output is a non-scientific scoring error, not a gate failure.
Exact cross-runtime/libm reproducibility remains a later backend qualification
claim; this ratification fixes the Wave A execution behavior but does not
production-qualify a platform.

**A5-R9 — Explicit unresolved states.** The only explicit unresolved
scientific-value states are the exact JSON strings `HUMAN_INPUT` and
`BLOCKED_FOR_LIVE_UNTIL_SET`. They are states, not numeric values, passes,
zeroes, or defaults. JSON `null`, omission, and malformed values are not
aliases for either state. If any mandatory threshold or other score-bearing
required pack value is in either explicit state, the valid pack is
`PACK_NOT_READY`: no gates are evaluated, `combined_score` is absent/`None`,
and `eligible_for_emission = False`. That outcome is not a scientific gate
failure. An unresolved optional, strictly non-score-bearing diagnostic may be
retained only when exact `mandatory = false` marks it as such. While unresolved
it is unevaluated, contributes no expected `ScoreInput` key, creates no gate
result, is omitted from `InternalResult`, and cannot affect readiness, status,
a score, or eligibility.

**A5-R10 — Fixture-only origin.** A5 implements only a structurally
non-emission-authoritative fixture origin. Its runtime pack must bind exact
`fixture_origin = true`; missing or false origin rejects in A5. That field is
part of the exact pin and result, cannot be defaulted or relabelled by the
engine, and is structural labeling rather than authenticated provenance.
Every A5 fixture result has `eligible_for_emission = False`, including a
resolved pass with a non-zero combined score. An actual mandatory failure
still additionally enforces the A5-R5 zero-score invariant. Supporting a
production-origin pack or an emission-authoritative result requires separate
later implementation, qualification, and human authorization.

**A5-R11 — Private `InternalResult`.** A5's stable private result contains
only the scoring status, exact A5-R3 pack pin, fixture-origin state, evaluated
gate decisions/authorized scalar components as applicable, optional combined
score, and `eligible_for_emission`. It does not copy pack weights into the
result. It also excludes raw or derived seeds, seed roles, draw/sample/exam
IDs, evaluation binding, strategy/submission/miner/validator identity, fees,
block/decay/tie-break fields, public-card or disclosure behavior, receipt or
signature behavior, persistence, logging, and weight-writing. A6 owns storage
and public projection; later receipt/evidence, observability, FSM, and
economic owners consume only explicitly authorized fields.

**A5-R12 — Scoring authority and supersession.** `Design_Specs/Scoring.md`
remains the sole mathematical and A5 runtime-contract authority.
`Design_Specs/Scoring_Formulas.md` is subordinate. Its historical
0.40/0.35/0.25 example, sigmoid-as-official-hard-gate description, arithmetic
top-level aggregate, fp32/JAX runtime implication, and missing-input
fail-or-zero language are explicitly superseded and must not be implemented.
Historical PoC/legacy scorers and tests using linear/arithmetic/defaulted
semantics are archaeology, not A5 implementation or test evidence. The
active-looking historical `Design_Specs/Implementation.md` scoring appendix
and the proposed/unratified tuple in `Design_Specs/Strategy_Schema.md` are
likewise superseded for A5 artifact, input, gate, math, and result behavior.

**A5-R13 — Ticket repair and implementation gate.** The A5 ticket is repaired
to require both zero score and false eligibility on actual mandatory failure;
to require rejection rather than “ignored or rejected”; to require exact
bytes plus the external tagged digest rather than a content-hash stub; to use
strict runtime JSON rather than YAML; and to place the future test at the
current default-CPU path `tests/cpu/test_scoring_engine.py`. The new A5 plan is
a pre-implementation ratification plan only. Future implementation may begin
only after this documentation PR is independently reviewed, human-authorized,
merged, and followed by a fresh main/concurrency/status check. This decision
does not itself authorize a merge, start A5, or begin A6 or later work.

**A5-R14 — Literal schema and engine-entry completion.** During the authorized
A5 implementation, the maintainer resolved the remaining literal contract
gaps without changing A5-R1 through A5-R13. Score Pack schema version is the
exact required string `"1.0"`; every other schema token rejects. Every hard-gate
and soft-leg operator record has the exact required discriminator member
`"operator"`. The only accepted values remain `less_than`, `boolean_true`,
`quadratic_barrier`, `tail_logistic`, and `reciprocal_error`; `"type"`, `"kind"`,
omission, aliases, duplicates, and unknown values reject. Schema 1.0 makes
within-leg `weighted_sum` implicit, so nested `"aggregation"` is forbidden;
only top-level `"combination": "weighted_geometric_logspace"` is explicit.

The exact engine entry is
`ScoreEngine.score(score_input: ScoreInput | None, pack: LoadedScorePack)`.
For a valid `PACK_NOT_READY` pack, exact Python `None` returns a result with
empty gate and leg vectors, no combined score, and false eligibility; a
non-`None` input rejects. A ready pack rejects `None` and accepts only the exact
closed, pin-matched `ScoreInput`. Malformed or mismatched packs remain typed
configuration errors and produce no `InternalResult`; Python `None` does not
make JSON `null` valid.

After a ready pack and complete input are fully validated, the engine evaluates
every resolved gate in declared array order without short-circuiting, retains
the full ordered vector, includes resolved optional diagnostics, and omits
unresolved optional diagnostics. Mandatory failure is decided only after the
vector is complete; it returns the full gate vector, canonical `0.0`, false
eligibility, and no soft-leg evidence. Optional-only failure does not affect
scoring. After mandatory pass, an exact zero soft leg remains `SCORED` with
combined score `0.0`. This clarification belongs to the same implementation PR,
does not authorize A6+, and does not production-qualify A5.

## 2026-08-21 — A4 closure after reviewed merge

**Closure topology and review.** A4 implementation began from exact base
`e13baf312b811e2fd6784856c56d851a15f153fd`. Independent review approved exact
implementation head `b0f79cf96b7cd489a97a7a4dd49285d762c962aa` for the bounded A4
ticket, with no unresolved blocking finding. GitHub records no formally
submitted review object, review thread, or PR comment for PR #17, so this entry
does not claim a formal GitHub approval. Exact-head pull-request CI run
`32440327141` completed successfully: the CPU job reported `622 passed in
7.80s`, and Code quality passed at `Ruff 757/776; Black 62/68`, with eight
changed Python files, no new debt, and every changed Python file clean.

PR #17 then merged normally as
`120eab02e406bda280d9c361bbbb7d8ef7a08330`. Its ordered parents are exact base
`e13baf312b811e2fd6784856c56d851a15f153fd` and exact reviewed head
`b0f79cf96b7cd489a97a7a4dd49285d762c962aa`; the reviewed head is ancestral to
current `main`. Exact-merge push CI run `32444857456` completed successfully on
`main`: its CPU job reported `622 passed in 8.68s`, and Code quality again
reported `Ruff 757/776; Black 62/68`, eight changed Python files, no new debt,
and every changed Python file clean.

**Bounded acceptance evidence.** The implementation's focused command for
`tests/cpu/test_seeding.py` and `tests/cpu/test_no_leakage.py` reported `230
passed in 3.55s`; its complete local CPU command reported `622 passed in
4.35s`. The standard-library implementation and acceptance tests also passed
compilation, strict Ruff/Black, and the exact-base no-new-debt gate. A fresh
no-dependency `carbon-0.9.0-py3-none-any.whl` with SHA-256
`4bd58cc8b0e503cd127dd5c64f67970899ecabebd1554860121de8086028c511`
installed into a new environment and exercised the public A4 API from outside
the checkout under CPython `3.11.11` with `python -I`; golden seed and
commitment values passed, the official provider was observed exactly once, and
the blocked optional/consumer import attempted and loaded lists were both
empty.

**Maturity and preserved boundaries.** A4-R1 through A4-R11 remain
**SPECIFIED**; their bounded seeding, provider/fixture, commitment, leakage, and
isolation boundary is now **IMPLEMENTED** on `main` and **TESTED** to the
recorded CPU, deterministic-derivation, canonical-encoding, leakage,
public-projection, mock/fixture-isolation, and import-isolation scope. The exact
head was independently reviewed, merged, ancestry-verified, and post-merge-CI
verified. A4 is therefore `done` for this bounded ticket. This closeout
supersedes only the historical maturity language in the pre-implementation
ratification; it does not alter A4-R1 through A4-R11.

**PRODUCTION-QUALIFIED: NO.** A4 does not implement or qualify a real beacon
provider, provider authentication, entropy quality, chain timing, finality,
nonce lifecycle, reorg/replay handling, fallback policy, or retention and
post-evaluation disclosure policy. It does not define A7's concrete evaluation
binding, submission, fee, or FSM semantics; later receipt/signing semantics; A8
backend/TrainEval conversion; A6 Card-store disclosure integration; A9 MCP
transport; A10 leaderboard; A11 logging; or any scientific, LIVE, security,
operations, production, permanent same-process secrecy, weight-writing, or
emission claim. OQ-005 and OQ-006 remain unresolved, and A5 and all later
tickets remain `todo` and unstarted.

## 2026-08-21 — A4 pre-implementation seeding architecture ratification

**Status, base, and scope.** On exact `origin/main`
`c5f2dfbda64e4375e3d3f26f7a463ca98cabd07a`, the maintainer ratifies
A4-R1 through A4-R11 below as the implementation decision for A4 seeding,
isolation, and the unsigned public exam-commitment boundary. This is a
ratified implementation decision, not implementation: no A4 implementation
source or A4 tests exist beyond the A0 package marker, A4 remains `todo`, and
no Definition-of-Done item is complete. The decision does not select seed
timing or a production beacon, does not change A3, and establishes no
scientific, LIVE, backend, security, operations, production, or emission
qualification.

**A4-R1 — Entropy and provider boundary.** The former A4 helper sketch based
on a Carbon-operated long-lived `master_secret` is superseded. A4 accepts
opaque root material only through the separate exact types `OfficialEntropy`,
`MockEntropy`, `QualificationEntropy`, and `FixtureOfficialEntropy`.
Provider-origin official material crosses a narrow `BeaconProvider` boundary
as exactly 32 opaque bytes. A4 may define that protocol and a deterministic,
separately typed fixture provider, but it does not implement or select a real
Bittensor/Subtensor provider, block delay, finality rule, nonce lifecycle,
reorg policy, production hybrid/drand design, or production fallback. Missing,
malformed, conflicting, or unavailable official entropy fails closed; it never
falls back to zero, wall-clock time, process state, mock material, or a local
default. Those production choices remain protocol-owned under OQ-005 and
OQ-006.

**A4-R2 — Exact domains and typed entry points.** The complete top-level domain
set is exactly `mock`, `official_train`, `official_eval`, `official_stress`,
`reference`, and `dossier`. Initialization, augmentation, shuffle, dropout,
batch order, generator sampling, and similar functions may later be canonical
internal role keys beneath one of those domains; they are not peer domains.
Mock, official, qualification/reference, and fixture-official derivation use
separate typed contexts and public entry points. A4 must not expose a generic
`mode="mock" | "official"` switch or `local_mode` Boolean.

**A4-R3 — Official identity binding.** Every official derivation binds the
exact A3 `ChallengeKey` (`challenge_id` and exact challenge `version`), exact
`generator_version`, exact tagged `generator_digest`, exact
`scoring_version`, exact tagged `scoring_digest`, seed-scheme
identifier/version, an opaque 32-byte `evaluation_binding`, the exact official
domain, a canonical internal role key, and an explicit draw index. The
evaluation binding is only an A4 structural slot: A7 or later supplies its
concrete immutable value. A4 does not define `submission_id`, strategy hashing,
A7 idempotency, fee identity, or receipt identity. It accepts no raw Strategy
mapping or miner hyperparameters, so later Strategy mutation cannot alter an
already-created context.

Validator or miner identity is not scientific entropy. Official derivation
also excludes miner-controlled seeds, nonces, block hashes, draw IDs, and exam
IDs; wall-clock time; process ID; environment variables; thread scheduling;
call order; mutable global RNG state; and retry count. Validator identity must
not influence the scientific exam.

**A4-R4 — HKDF-SHA-256 contract.** A4 uses RFC 5869 HKDF with SHA-256. The
seed-scheme identifier is exactly `carbon.seed.hkdf-sha256.v1`; the Extract
salt is the exact ASCII bytes
`carbon/a4-seeding/hkdf-sha256/v1`; and the applicable typed 32-byte entropy is
the input keying material. Expand `info` is the A4-R5 canonical encoding and
the retained output is exactly 32 bytes. A4 does not reduce the result modulo
an integer range, truncate it to a 32- or 63-bit seed, centrally convert it to
a NumPy/JAX/Torch key, or reuse one value across roles. Backend-specific
conversion belongs behind later A8 TrainEval/backend adapters and must use
further role separation or a documented adapter conversion. The context-kind
values `official`, `mock`, `qualification`, and `fixture_official` are distinct
inputs, so identical root bytes do not collide across context kinds.

**A4-R5 — Canonical seed-info encoding.** A seed `info` document starts with
the exact ASCII header `carbon.seed.info.v1`. The header is followed by the
fields below in exactly this order. Each field is one unsigned one-byte tag,
one unsigned four-byte big-endian payload length, and the exact payload bytes.

| Tag | Field |
|---|---|
| `0x01` | context kind |
| `0x02` | seed-scheme identifier |
| `0x03` | challenge ID |
| `0x04` | challenge version |
| `0x05` | generator version |
| `0x06` | generator digest |
| `0x07` | scoring version |
| `0x08` | scoring digest |
| `0x09` | evaluation binding |
| `0x0A` | seed domain |
| `0x0B` | role key |
| `0x0C` | draw index |

String fields are exact validated ASCII bytes: implementations do not
Unicode-normalize, case-fold, alias, trim, or coerce them. Challenge identity
reuses A3 validation and `ChallengeKey`, not a weaker duplicate parser. Tagged
digests use A3's exact `sha256:<64 lowercase hexadecimal characters>` form.
The evaluation-binding payload is exactly 32 raw bytes. The draw-index payload
is exactly one unsigned 64-bit big-endian integer; Boolean, negative,
overflowing, and non-integer values reject. Unknown or duplicated fields,
invalid order, length, or text encoding, and all malformed values reject.
Delimiter-concatenated strings are not canonical A4 documents.

A4-R10 and A4-R11 below complete the generator/scoring-version and role-key
validation contracts required by this schema.

**A4-R6 — Private exam root and unsigned public commitment.** A4 derives a
32-byte private exam root from the same HKDF PRK through an independent Expand
domain. Its `info` document starts with the exact ASCII header
`carbon.exam-root.info.v1`, uses the A4-R5 TLV framing, and binds context kind,
seed-scheme identifier, exact `ChallengeKey`, generator version and digest,
scoring version and digest, and the 32-byte evaluation binding. It includes no
train/eval/stress domain, role key, or draw index.

The public value is an opaque, unsigned `ExamCommitment` in exact tagged form:
`sha256:` plus the lowercase hexadecimal SHA-256 digest of a canonical
commitment document. That document begins with the exact ASCII header
`carbon.exam-commitment.v1`, uses the same TLV framing, and binds the same
context/scheme/challenge/generator/scoring/evaluation fields followed by the
32-byte private exam root. The public value retains no Python reference to the
private context, root, entropy, or derived seeds. A public exam projection may
contain only the commitment, explicitly public challenge/generator/scoring
pins, and explicit fixture status where applicable. It never contains entropy,
the private root, raw or derived seeds, draw or sample IDs, a run nonce, hidden
sample order, a reconstruction-enabling block hash, per-role seed hashes, or
generated-payload hashes.

A4 does not create an EvaluationReceipt, receipt ID, validator signature,
timestamp, score commitment, prediction/reference root, Merkle/MMR log, or
audit record. A4-R9 below completes the exact exam-document tag contract.

**A4-R7 — Bounded security and disclosure claim.** A4 guarantees the interface
and derivation boundary: official entropy, raw or derived official seed
material, draw IDs, and reconstruction-sensitive exam identifiers do not cross
miner/public interfaces or get embedded directly in the public commitment;
official, mock, qualification, and fixture namespaces are distinct; identical
official inputs reproduce identical seeds and commitments across validators;
and validator identity does not affect the scientific exam. This is not an
unconditional mathematical hiding theorem. Resistance to recovery depends on
SHA-256 preimage resistance, HKDF-SHA-256 security, sufficient provider
entropy, and some relevant entropy remaining unavailable to an attacker for
the protocol-required hiding interval. A4 does not decide between
pre-submission unpredictability and permanent post-evaluation secrecy;
operational disclosure and retention remain protocol-owned.

**A4-R8 — Fixture, mock, and qualification isolation.** Fixture entropy is a
different non-coercible type from provider-origin official entropy.
Fixture-official derivation uses `context_kind="fixture_official"`; provider
origin uses `context_kind="official"`. Fixture public projections are
unmistakably fixtures, and fixture/mock identities must remain mechanically
non-emission-capable when emission paths exist. A4 itself adds no emission or
weight writer.

Mock derivation cannot request an official domain, accept official entropy,
access an official context, alter official counters or state, or affect later
official output through query count or call order. Qualification derivation is
limited to `reference` and `dossier`, cannot request mock or official domains,
and remains separate from the live official miner exam. Fixture material
cannot be relabelled or coerced into provider-origin material.

**A4-R9 — Exam-document TLV tag contract.** The exact document headers
`carbon.seed.info.v1`, `carbon.exam-root.info.v1`, and
`carbon.exam-commitment.v1` establish three separate versioned schemas. TLV
tags are interpreted within the schema selected by that exact header, not as
globally unique field identifiers. The `carbon.seed.info.v1` tags and payload
contracts remain unchanged from A4-R5.

`carbon.exam-root.info.v1` reuses the A4-R5 common identity tags and payload
contracts exactly:

| Tag | Field |
|---|---|
| `0x01` | context kind |
| `0x02` | seed-scheme identifier |
| `0x03` | challenge ID |
| `0x04` | challenge version |
| `0x05` | generator version |
| `0x06` | generator digest |
| `0x07` | scoring version |
| `0x08` | scoring digest |
| `0x09` | evaluation binding |

It has no additional fields and ends after `0x09`; it contains no seed domain,
role key, draw index, or private exam root.

`carbon.exam-commitment.v1` reuses those same `0x01` through `0x09` meanings
and payload contracts, then adds exactly `0x0A` — private exam root, whose
payload is exactly 32 raw bytes. Its field order is exactly `0x01` through
`0x0A`, with no additional fields. Reusing `0x0A` for seed domain in
`carbon.seed.info.v1` and private exam root in
`carbon.exam-commitment.v1` is intentional and unambiguous because the header
selects the schema. Implementations must not assign global meanings to tags,
introduce a `0x0D` private-root tag, or reserve unused seed-document tags for
cross-schema uniqueness. Unknown, duplicate, reordered, malformed-length,
malformed-payload, and trailing unrecognized fields reject.

**A4-R10 — Generator and scoring version validation.** A4 creates no second
version grammar. Both `generator_version` and `scoring_version` call and reuse
`carbon.registry.model.validate_version`; implementation must not copy its
regular expression into `carbon/seeding`. The current contract requires an
exact built-in Python `str`, returns its exact spelling without normalization,
trimming, coercion, case folding, or alias resolution, and permits at most 64
characters under the ASCII grammar
`[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*`. Tokens begin and end with an
alphanumeric character; empty segments and adjacent separators without an
intervening alphanumeric segment reject. `1.0` and `burgers1d_v0.1` are valid
examples. If A3's authoritative validator changes before A4 implementation,
the implementation uses the then-current contract and re-evaluates its golden
vectors before coding.

**A4-R11 — Canonical role-key validation.** A4 `RoleKey` is a distinct
semantic type that reuses A3's canonical-identifier grammar. A role key must be
an exact built-in Python `str`, encode as ASCII, be non-empty and at most 64
encoded ASCII bytes, preserve exact spelling without normalization, trimming,
case folding, coercion, or alias resolution, and match
`[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*`. A4 first enforces its own 64-byte bound,
then calls
`carbon.registry.model.validate_canonical_identifier(value, "role_key")`;
it does not duplicate the regular expression. Valid examples include
`generator`, `generator_sampling`, `parameter_init`, `batch_shuffle`,
`dropout`, and `augmentation_1`. Empty, uppercase, leading-digit,
leading/trailing/repeated-separator, dotted, spaced, slashed, non-ASCII, and
over-64-byte values reject. Role keys remain subordinate to one of the six
ratified domains and do not alter any A3 or other identity domain.

**Protocol deferrals and maturity.** OQ-005 and OQ-006 remain unresolved in
their owning protocol/security domains. In particular, this ratification does
not select a chain event, delay, finality/reorg rule, nonce lifecycle, real
provider, hybrid/drand construction, or fallback. Separately, A4-R7 leaves
operational entropy retention and post-evaluation disclosure policy to their
protocol owner. A4 remains `todo`; none of the behavior above is
**IMPLEMENTED**, **TESTED**, or **PRODUCTION-QUALIFIED** by this documentation
entry.

## 2026-08-21 — A3 closure after reviewed merge

**Closure evidence.** A3 began from exact base
`e6fb20b1dc361ded442fcf41d118cea5f2c775cd`. Independent review identified
the fixture-relabel provenance gap, missing production-backbone requirement,
and quality-attribution correction; the same A3 branch repaired them, and
independent rereview approved final head
`149f9a74351b02a9b615d0015c22b74187ab0f55`. Repaired-head PR CI run
`32377387086` passed both CPU tests and Code quality. PR #14 then merged
normally as `69b938d1c4fd0aca58276940d15df50b1b68e5d1`, whose parents are exact A3
base `e6fb20b1dc361ded442fcf41d118cea5f2c775cd` and reviewed head
`149f9a74351b02a9b615d0015c22b74187ab0f55`; the reviewed head is ancestral to
current `main`. Exact-merge push CI run `32379421897` completed successfully on
`main`: CPU job `96458664242` reported 392 passing tests, and Code quality job
`96458663684` passed with inventory unchanged from the A3 base at
`Ruff 757/776; Black 62/68`, no new debt, and all changed Python files clean.

**Maturity and preserved boundaries.** A3 is therefore `done` and may be
described as **SPECIFIED**, **IMPLEMENTED**, **TESTED**, independently reviewed,
merged, and post-merge-CI verified for the structural challenge registry/LIVE
gate only. Canonical identity remains exact `(challenge_id, version)`; the gate
hashes actual artifact bytes against tagged SHA-256 bindings; fixture-origin
evidence remains structurally blocked from production; and production LIVE
requires at least one allowed canonical backbone. `fixture_origin` is
structural, not authenticated, provenance; signer/authentication mechanisms
remain future work. No real challenge was made LIVE, and A3 does not establish
scientific, backend, security, operations, production, or emission
qualification. No thresholds or approvals were invented. A4 remains `todo`
and has not started; all A4+ behavior remains outside this closeout.

## 2026-08-20 — A3 exact-version registry and structural LIVE gate

**Base, authority, and scope.** A3 began on `agent/a3-challenge-registry` from
exact `origin/main` commit
`e6fb20b1dc361ded442fcf41d118cea5f2c775cd`, after the reviewed A2 merge and
post-merge CI closure. `Design_Specs/Build_Out.md` C1 and §8 define the core
registry and LIVE-manifest contract; the ratified
`Design_Specs/Build_Out_Protocol_Extension.md` reserves receipt-schema and
backend-profile identities. No authoritative source changes the exact
ChallengeKey, tagged SHA-256, eight-slot, or fixture-isolation requirements,
and no qualification-manifest signature algorithm is ratified. A3 remains
`in_progress`. Initial PR #14 review found a fixture-relabel provenance gap, a
missing production-backbone requirement, and incorrect quality attribution;
the same-branch repair is recorded below, while independent rereview/approval,
merge, and post-merge CI are not established by this entry.

**Canonical boundary (REPLACE/RETIRE).** `carbon.registry` is the canonical A3
authority. It replaces historical mutable challenge record/loader semantics
for this boundary. `carbon/challenges/*` is RETIRE/defer evidence, remains
untouched, and does not become registry authority. The mutable runtime backbone
registry remains independent; A3 stores only exact declarative compatibility
identifiers and imports no backend. PoC hashing contributes only the raw-byte
SHA-256 concept and is not reused as an authority for scoring, execution, or
qualification.

**Exact identity and persistence.** One immutable `ChallengeKey` is the exact
pair `(challenge_id, version)`, stored only at
`<registry_root>/<challenge_id>/<version>.json`; embedded and file-location
identities must match. Strict JSON rejects duplicate keys, unknown fields,
non-JSON constants, malformed types, and duplicate embedded keys during scans.
Registry and artifact files are opened descriptor-relatively with symbolic
links disallowed and regular-file checks applied. Writes serialize
deterministically and use a per-key interprocess lock, a fsynced temporary file
in the destination directory, descriptor-relative atomic replacement, and a
directory fsync where available. These mechanics provide the A3 file boundary;
they are not a general distributed transaction or remote-filesystem guarantee.
No ratified A2/A3 source supplies a maximum length for the shared canonical
identifier syntax, so A3 does not invent one in this correction; a protocol
limit remains explicitly deferred.

**Qualification gate.** The exact ordered requirements are
`generator_envelope=APPROVED`, `generator_validation=PASSED`,
`dossier_level_1=APPROVED`, `score_pack=APPROVED`,
`mock_incompleteness=APPROVED`, `train_backend=QUALIFIED`,
`launch_bar=SIGNED`, and `mcp_readiness=SIGNED`. Every slot also needs a
human-owned reference and a known artifact identifier. Every declared artifact
uses only canonical `sha256:<64 lowercase hex>` and is re-hashed from the bytes
of the same securely opened regular file. An effective-LIVE query re-runs the
gate, and only checked production activation may persist `live`; ordinary save
cannot create or mutate LIVE state. Production LIVE also requires at least one
allowed backbone, without restricting that declarative list to today's A2
backbone names.

**Fixture and protocol-extension boundaries.** Fixture eligibility requires
four independent barriers: fixture lifecycle status, fixture manifest mode, a
required `fixture_origin=true` record provenance bit, and an explicit
fixture-mode API call. Fixture labels require that origin at model validation,
and ordinary save cannot change it for an existing `ChallengeKey`. Production
assessment rejects fixture origin even after status and mode are relabelled;
activation has no fixture bypass. This is structural provenance, not an
authenticated or signed origin claim. The record's ordered allowed-backend-
profile binding and required selection are structurally bound to
`train_backend` evidence; the receipt schema version is structurally bound to
`mcp_readiness` evidence. Equality of those identifiers never approves a
backend or environment, makes evidence scientifically correct, verifies a
signer, or proves that a receipt is signed.

**Public API and unclaimed maturity.** A configured `ChallengeRegistry` exposes
exact-version `load`, `save`, diagnostic/boolean eligibility,
effective-LIVE, checked activation, and backbone-compatibility operations plus
deterministic `scan()`. The focused path is
`tests/cpu/test_registry.py`, with structure-only static data under
`tests/fixtures/registry/`. Local repair verification passed 134 focused tests
in 0.33s and 392 complete default CPU tests in 0.74s, with strict Ruff/Black on
all six changed Python files. The CI-equivalent gate introduced no new debt and
left inventory unchanged from the exact A3 base at
`Ruff 757/776; Black 62/68`; `git diff --check` and a fresh no-dependency
outside-tree wheel/import boundary also passed. The inherited PoC
smoke still exits 2 on its pre-existing missing `role_seed` collection import.
A3 does not ship a production-LIVE record or real
scientific hashes and does not implement scientific/backend qualification,
receipt signing, Score Pack semantics, official seeding, scoring, model cards,
execution, MCP transport, Bittensor operation, or any A4+ capability.

## 2026-08-20 — A2 closure after reviewed merge

**Closure evidence.** The initial A2 implementation received independent
review, and its findings were corrected at final reviewed head
`d73f697ebd9df9b8c96b7a46fd4c9986444f0928`. Independent rereview found no
remaining blockers. PR #12 then merged normally as
`bfc0b97e1b16625141de3950428bc2fdf69f42ea`; the reviewed head is ancestral to
current `main`. Post-merge push CI run `32360050671` passed: the default CPU
suite reported 258 passing tests and the code-quality gate succeeded. A2 is
therefore `done`. A3 remains `todo` and unstarted.

**Maturity and remaining boundaries.** A2 is **IMPLEMENTED and TESTED** only
for its Strategy schema/`dry_validate` boundary. This closure does not claim
production qualification, end-to-end hostile execution isolation, LIVE
qualification, scientific validation, challenge-registry binding, persistent
strategy hashing, parameter execution semantics, MCP integration, or
Bittensor integration. OQ-008 remains broader and unresolved beyond A2's
declarative validation boundary.

## 2026-08-20 — A2 canonical Strategy v1.0 and pure dry validation

**Base, authority, and scope.** A fresh remote read verified both
`origin/main` and the dedicated `agent/a2-strategy-schema` starting point at
`e696cc43ace96a963f00bb28394da03d35eb267e`. A1 and its PR #9 cold-start
registry repair are ancestral and complete, the sequencing hold is closed,
the supported pre-edit CPU baseline passed 27 tests, and no canonical A2
implementation had landed. The ratified A2 instruction resolves conflicting
historical text: `schema_version` supersedes this ticket's old
`strategy_version` wording; rich top-level training/loss/curriculum/data
examples were not the A2 contract. The Miner MCP scaffold is reconciled to the
A2 envelope; the pending Strategy Schema v1.1 proposal remains design input,
not implementation truth. For OQ-008, the ratified instruction settles only
the narrow A2 declarative schema/validation boundary; it does not close the
broader execution threat model or qualify execution isolation.

**Canonical contract (REPLACE).** Strategy v1.0 has exactly four required
top-level fields: exact `schema_version: "1.0"`, canonical-string
`challenge_id`, canonical-string `backbone`, and exact-object `parameters`.
The recognized schema-level backbone set is the immutable
`deeponet`/`fno`/`physicsnemo_fno`/`uno` set; validation never imports or calls
the mutable runtime registry. Both identifiers must already match ASCII
`[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*`. No aliases, defaults, case folding,
coercion, clamping, semantic dropping, document rewriting, or protocol hash is
provided. The legacy `carbon/common/strategy_schema.py` remains untouched for
historical callers but is not canonical A2 behavior.

**Pure hostile-input boundary.** `carbon.schema.dry_validate` returns frozen,
slotted `ValidationResult` and `ValidationIssue` values with stable codes,
JSON-Pointer-like paths, deterministic sorting, and generic messages that do
not echo submitted values or representations. Exact built-in JSON types are
validated iteratively. Active-ancestor and completed-container identity sets
reject cycles while bounding traversal work for shared DAGs; non-finite
numbers, non-string keys, subclasses, bytes, tuples, sets, callables, and
arbitrary objects fail closed without `repr` or user display methods. A small,
explicit, versioned reserved-key vocabulary rejects the ratified capability
and official-control fields; only case/camel-case differences and hyphen,
ASCII-space, or underscore separators (including compact spellings) are
matched.
Arbitrary English meaning and string contents are not interpreted: unknown
keys and URL/path/code-looking strings remain inert. This denylist is defense
in depth, not comprehensive executable-intent detection. Later execution must
use positive parameter handlers, never execute/import/fetch from unknown
fields, never pass arbitrary parameters blindly into constructors, and never
silently drop unknown fields.

**Explicitly unresolved.** OQ-008 remains open beyond declarative validation:
the permitted execution surface, sandbox/process isolation, immutable execution
environment, parser and runtime resource limits, kill policy, audit controls,
and production security/operations qualification still require their owning
later tickets and human approval. A2 uses no fabricated production numbers and
keeps iterative frames suitable for adding ratified parser limits later.
Persistent canonicalization and `strategy_hash` remain A7 work. Challenge
lookup/LIVE qualification, official seeding, scoring, cards, fees/FSM,
TrainEval/model construction, MCP transport, leaderboard, production
observability, Bittensor operation, and all other A3+ behavior remain absent.

**Local evidence.** The focused A2 suite passed 181 tests and the full default
CPU lane passed 208. Ruff and Black passed strictly for all three changed
Python files. The repository no-new-debt gate passed at Ruff 757/776 and Black
62/68, unchanged from the A2 base; A2 added no Ruff or Black debt. The 19 Ruff
and six Black reduction is cumulative from older baseline work, not attributable
to A2. `git diff --check` passed. A fresh no-dependency wheel imported
`carbon.schema.strategy` from `site-packages` outside the checkout and returned
a valid result with every optional scientific/Bittensor and non-schema Carbon
boundary blocked; attempted and loaded sensitive-module lists were empty. An
initial local adversarial pass drove shared-DAG and path-ambiguity regressions.
Independent review on draft PR #12 subsequently identified the broad semantic
classifier, generic string-value heuristics, non-ASCII public paths,
specification/status drift, and quality-attribution error addressed by the
focused correction on the same A2 branch. Independent rereview of the
correction remains outstanding.

The existing `POC_FAST=1 bash poc/scripts/smoke.sh` completed its oracle and
three protocol fixture runs, then exited 2 during collection at the unchanged
inherited `ImportError` for `poc.generators.burgers1d.role_seed`. That defect is
not widened into A2. A2 is locally **IMPLEMENTED and TESTED** for its narrow
schema boundary only. It is not scientifically validated, end-to-end
execution-isolated, LIVE-qualified, production-qualified, or
Bittensor-integrated. The Wave item remains `in_progress` until external review
and merge.

**Draft PR #12 review-fix evidence.** The focused A2 suite passes 231 tests and
the full default CPU lane passes 258 after replacing semantic inference with
the explicit v1.0 reserved-key vocabulary and making public paths fixed-ASCII.
Ruff and Black pass strictly for the two correction Python files;
`git diff --check` passes. The repository quality inventory remains Ruff
757/776 and Black 62/68 from the exact A2 base, so this correction adds no
debt; the gate's reported 19 Ruff and six Black removal remains cumulative
against the older committed baseline. A fresh non-editable, no-dependency
wheel imported from `site-packages` outside the checkout. With every optional
scientific/Bittensor and non-schema Carbon boundary blocked, no blocked import
was attempted or loaded; neutral URL/code-looking strings remained inert, a
reserved `OfficialSeed` key failed closed, and a Greek key produced the
fixed-ASCII path `/parameters/~u0003b1`. Independent rereview remains pending.

## 2026-08-20 — Post-merge A1 cold-start backbone registry correction

**Historical correction and status.** A1 PR #5 was reviewed at
`c4d0a9210aaacad077287c2ca14e20b2bb6d396e` and merged as
`5f810a57379a608119aa9cc9bbd6fc78a48baf13` before a subsequent independent
review's optional-backend blocker was repaired. At that merged head, a cold
`carbon.backbones` import had no known adapters, the CPU tests imported adapter
modules before exercising lookup, and `carbon.backbones.registry` owned a
second disconnected mapping. This corrects the registry-path implementation
and test claim in the 2026-08-19 A1 decision below; it does not rewrite the
original install, CPU CI, quality-ratchet, or PoC evidence.

**Corrective decision (WRAP/REPAIR).** The initial fetch found the expected
post-PR-#6/PR-#7 `main` at
`3e29fef703d4b60c97ff4873cb395d2436cdad0a`. Before publication, `main`
advanced through PR #8, which changed only the scientific-reference canon and
did not overlap this repair. The branch was fast-forwarded, so its actual repair
base is `7f499e589b86ed127745831ccacdc1c8e4ffb677`. `carbon.backbones` remains
the package-facing API and is now the sole registry state owner. An explicit
map links `physicsnemo_fno`, `fno`, `deeponet`, and `uno` to their local Carbon
adapter modules. Listing names imports no adapter, and resolving a built-in
imports only its local adapter. The compatibility API in
`carbon.backbones.registry` delegates registration, listing, and resolution to
the package registry while preserving its historical construct-with-keywords
behavior; it no longer owns a second mapping.

Fresh isolated subprocess tests block `physicsnemo`, `neuralop`, and `torch`,
prove all four names are cold-discoverable without loading those packages, and
exercise extra-specific construction failures through the registry for both
backend families. Separate cold-registry tests prove a transitive
`ModuleNotFoundError` is re-raised unchanged. Installed-backend API
compatibility, model behavior, and scientific or production qualification
remain untested and unclaimed. This correction introduces no A2+ behavior.

**Local corrective evidence.** In a fresh Python 3.11.11 virtual environment,
the literal `python -m pip install -e ".[dev]"` exited 0 and installed
`carbon==0.9.0`; `python -m pytest -q` exited 0 with 27 passed and no skipped,
xfailed, or failed tests. The nine optional-backend tests passed individually,
including both registry-path missing-extra cases and both transitive-error
cases. An isolated cold-process diagnostic listed all four built-ins, resolved
their local wrapper classes, and found no `physicsnemo`, `neuralop`, or `torch`
module loaded. The quality gate passed at Ruff 757/776 and Black 62/68 with all
three changed Python files strict-clean. Compared with untouched repair base
`main` at Ruff 769/776 and Black 64/68, the patch removes 12 Ruff and two Black
fingerprints and adds none. `git diff --check` exited 0. With the explicit PoC
extra installed, `POC_FAST=1 bash poc/scripts/smoke.sh` exited 2 at the unchanged
inherited import failure for absent `poc.generators.burgers1d.role_seed`.

At the corrective branch's pre-merge record, A1 remained `in_progress` until
the draft PR received independent rereview and was merged. A2 remained `todo`
behind that temporary sequencing gate. Local and GitHub Actions evidence for
the final corrective head was recorded in the corrective PR because a commit
cannot record its own SHA or subsequent run IDs.

**Corrective merge and A1 closure.** The independently rereviewed PR #9 final
head `a247bb189d44ddf18de504572ef620cf5d501d10` passed final-head CI run
`32326384939`: the CPU job ran the default suite with 27 passing tests, and the
code-quality job passed the existing no-new-debt ratchet. PR #9 then merged as
`819da3c163c2fb9476a6881aab8740cc6984066e`. That merge is ancestral to the
closure base `fb6bbf393f77ae80d76abf3eda0e53a7dfd12f17`; intervening PR #10 added
only non-conflicting specification and context documents. The cold-start
registry gap is therefore repaired on current `main`, and A1 is `done`. A2 is
the next Build_Out ticket and remains `todo`; no A2 implementation begins in
this closure. Installed-backend API compatibility, scientific correctness, and
scientific or production qualification remain untested and unclaimed.

## 2026-08-19 — A1 truthful CPU CI and pytest baseline

**Base, branch, and scope.** A fresh fetch verified `origin/main` at the
authorized `0b2eec30250f1767cc434836e189cca219154d4d`, which is also merged PR
#4's merge commit. A1 started from that exact commit on
`agent/a1-ci-skeleton`. This decision implements engineering infrastructure
only; it does not promote or qualify A2+ schemas, registries, seeding, scoring,
cards, fees, TrainEval, MCP, leaderboard, logging, invariants, Bittensor
transport, or scientific behavior.

**Inherited baseline and actual Actions stages.** The local baseline used an
isolated detached worktree, CPython 3.11.11, and pip 24.0. Exact results:

| Command | Base result |
|---|---|
| `python -m pip install -e ".[dev]"` | Exit 1: no matching `physicsnemo` distribution. |
| `python -m pytest -q` | Forced diagnostic, exit 2: 22 collection errors from unavailable PoC/scientific and legacy dependencies. |
| `pytest tests/ -q --tb=no` | Forced exact-workflow diagnostic, exit 2: five legacy collection errors; first material signature is missing `neurons`. |
| `ruff check .` | Exit 1: 776 findings, 544 fixable. |
| `black --check .` | Exit 123: 66 files would reformat, 70 unchanged, and parse failures at `carbon/challenges/navier_stokes_2d.py:34:61` and `carbon/validator/sciml_validation.py:37:8`. |
| `POC_FAST=1 bash poc/scripts/smoke.sh` | Exit 2 after the oracle and three JAX fixture runs; final pytest collection cannot import `role_seed` from `poc.generators.burgers1d`. |
| Editable `--no-deps` install plus isolated imports from outside the tree | Exit 0 for `carbon==0.9.0`, `carbon`, and all 14 A0 role packages. |
| `git diff --check` | Exit 0. |

Base Actions run `32244438188` is the authoritative workflow record. Test job
`96041796858` failed installation and **skipped** its pytest step. Quality job
`96041796669` installed tools, failed Ruff on 776 findings, and skipped Black.
The forced commands above are diagnostics, not descriptions of skipped Actions
stages.

**Dependency decision (REPAIR).** The canonical root and 14 A0 role packages
import with every inherited third-party dependency blocked, so the truthful
core dependency set is empty. The supported `dev` extra pins pytest 9.1.1,
Ruff 0.16.3, and Black 26.5.1. Bittensor is retained only behind optional
`chain`, `validator`, and `miner` aliases; the aliases use plain Bittensor
because upstream has no `validator` or `miner` extras. NeuralOperator,
PhysicsNeMo, and the historical PoC each have explicit optional extras.
PhysicsNeMo uses the actual `nvidia-physicsnemo` distribution and its documented
`physicsnemo.models.fno` import boundary; that extra is Python 3.11+ upstream.
The retained NeuralOperator model-argument compatibility remains explicitly
deferred and unqualified.

Both backend adapters now register lazily without importing their scientific
packages. Direct or registry-based construction without an extra raises an
actionable extra-specific error. A missing transitive module in an installed
backend is re-raised rather than mislabeled as an absent backend. No fake or
vendored scientific package was introduced.

**Test classification (WRAP).** The default `python -m pytest -q` lane is
`tests/cpu/`: 22 tests cover `carbon`, all 14 A0 roles, distribution identity,
isolated outside-tree imports, optional-dependency absence, and backend failure
contracts. Five inherited root tests were moved with assertions preserved to
`tests/legacy/`; they target retired `neurons` APIs or superseded
scoring/schema/seeding behavior and contain collection/API failures not solved
by installing heavyweight dependencies. The 67 PoC tests remain in place and
are marked `poc`; 32 are additionally integration, two JAX-backend, and one
gold. The `invariant` marker is registered for A12, but no A12 tests or behavior
were added.

**Quality debt decision (WRAP/REPAIR).** Full cleanup is not appropriate in A1:
the base has 776 Ruff findings across legacy code, 66 Black reformat candidates,
and two files Black cannot parse. A complete normalized fingerprint inventory
is committed at `.ci/quality-baseline.json` and anchored to the authorized base.
The blocking gate enumerates Python files explicitly, runs pinned isolated
Ruff, runs Black with the empty `/dev/null` configuration, validates Black's
full-file summary, rejects diagnostics absent from the base inventory, and
strictly checks every added/touched Python file. It permits debt removal, not
new debt, and uploads the complete current report. This converts a permanently
red inherited job into a meaningful ratchet without deleting, excluding, or
making quality controls non-blocking. Running the committed generator against
a second clean detached checkout of the starting SHA reproduced the baseline
JSON byte-for-byte: 776 Ruff diagnostics and 68 Black debt entries.

**Local clean-candidate result.** In a detached candidate worktree, `python -m
pip install -e ".[dev]"` exited 0 and installed `carbon==0.9.0`; `python -m
pytest -q` exited 0 with 22 passed. Isolated imports from `/private/tmp` passed
for the package and all 14 roles. A separate wheel build/install contained 69
files, included all 14 roles, and imported `carbon` from `site-packages`. The
quality gate exited 0 at Ruff 769/776 and Black 64/68, with seven Ruff and four
Black baseline entries removed, no additions, and 12 changed Python files
strict-clean. Raw audits remain visibly red at 769 Ruff findings (537 fixable)
and Black exit 123 with 62 reformat candidates, 79 unchanged files, and the same
two parse failures. `git diff --check` exited 0.

The post-change `POC_FAST=1 bash poc/scripts/smoke.sh` again exited 2 at the
same missing-`role_seed` collection error after completing its oracle/fixtures.
This is an unchanged inherited PoC failure, not a passed A1 stage or scientific
claim.

**Authoritative draft-PR result.** Draft PR #5 run `32250522522` completed
successfully on Ubuntu/Python 3.11.15. CPU tests job `96060233144` passed the
supported development install, reached the actual `python -m pytest -q` step,
and reported 22 passed in 0.13 seconds. Code-quality job `96060233203` passed at
Ruff 769/776 and Black 64/68 with all 12 changed Python files strict-clean, then
uploaded complete report artifact `9364221072`. No blocking step was skipped.

A1 is now **IMPLEMENTED and TESTED** for its CPU engineering-infrastructure
scope. Scientific, security, LIVE, emissions, and production qualification
remain unclaimed. The exact final PR head and its post-evidence Actions run are
maintained in the draft PR body because a commit cannot record its own SHA.

## 2026-08-19 — A0 canonical package layout

**Base and scope.** A0 started from clean `main`/`origin/main` at
`ab765b07bc8c41106194ce6d06b4a2bd1c03f9a1` on branch
`agent/a0-repo-layout`. The root `.agent/` directory remains the runtime board:
`.agent/WAVE.md`, `.agent/tickets/`, and `.agent/INVARIANTS.md` are canonical;
`agent_pack/` contains protocol documentation only.

**Package-root decision.** Keep the existing root-layout `carbon/` package as
the sole canonical namespace. It is already selected by
`[tool.setuptools.packages.find] where = ["."]` and `include = ["carbon*"]`, so
introducing `src/carbon/` would create a second mapping without A0 benefit.
`carbon/__init__.py` already makes `python -c "import carbon"` succeed. A0 adds
only the required package boundaries: `schema`, `registry`, `seeding`,
`scoring`, `cards`, `fees`, `traineval`, `mcp`, `leaderboard`, `logging_utils`,
`evaluation`, `audit`, `chain`, and `qualification`. The empty `evaluation`
and `chain` boundaries reserve the adapter seam: future scientific/evaluation
code remains independent of Bittensor SDK objects, while SDK implementations
belong behind `carbon.chain`. No chain, receipt, audit, qualification, scoring,
or scientific behavior is implemented by A0.

**Current-tree mapping.** The current base differs from the older A-1 tree
snapshot: a 51-file legacy `carbon/` tree is present, while `Carbon_Logic/` is
absent. No legacy module is thereby promoted as current-spec compliant.

| Current root | A0 mapping |
|---|---|
| `carbon/` | Canonical import/package root; legacy modules remain audit inputs until later scoped tickets promote, wrap, repair, or replace them. |
| `poc/` | First Burgers TrainEval promotion source only; its current science, scoring, seed disclosure, and fixed values are not qualified. |
| `Carbon_Logic/` | Legacy selective-promotion source named by the maintainer disposition, but absent at this base; it is not recreated or supported as a namespace. |
| `neurons/` | Preserved legacy Bittensor reference; A0 found no import/layout acceptance need to reuse it. |
| `Julia/` | Preserved v0 generator-verification path; inclusion is not repair, scientific validation, or qualification. |
| `Design_Specs/` | Domain-owned semantic authority. |
| `.agent/` | Canonical runtime board, tickets, decisions, and invariants. |
| `agent_pack/` | Execution protocol/templates only, never a competing board. |

**Import inventory and migration decision.** The audit found 40 lowercase
`carbon` import statements, 21 `hydrogen` statements, one uppercase `Carbon`
statement, and no `Carbon_Logic` import statement. No import migration is
required for A0 acceptance because the canonical root import already succeeds;
changing legacy callers would broaden A0 into implementation repair. Migrated
callers: **none**. Deferred retired-namespace callers:

- `hydrogen`: `carbon/base/validator.py`;
  `carbon/challenges/{burgers,darcy_2d,heat,navier_stokes_2d}.py`;
  `carbon/data/__init__.py`; `carbon/landscape/agent.py`;
  `carbon/specialist/distillation.py`; `carbon/symbolic/pysr_evolver.py`;
  `carbon/training/{physicsnemo_trainer,trainer}.py`; and
  `carbon/validator/validator.py` (21 statements total).
- uppercase `Carbon`: `scripts/generate_leaderboard.py` (one statement).
- `Carbon_Logic`: none in the current Python import inventory.

These callers are explicitly unsupported/deferred, not compatibility promises.

**Pre-change baseline (Python 3.11.11).** These commands were run on the clean
A0 branch before package-boundary edits. The inherited baseline is red.

| Exact command | Exit/result before A0 |
|---|---|
| `python -m pytest tests/ -q --tb=no` | Exit 2: three collection errors (`test_physics_gates.py`, `test_reproducibility.py`, `test_scorer.py`). |
| `python -m pytest tests/ -q` | Exit 2: the same three collection errors, rooted in missing `torch`. |
| `POC_FAST=1 PYTHONPATH=. python -m pytest poc/tests -q` | Exit 2: one collection error; `poc.generators.burgers1d` does not export `role_seed`. |
| `POC_FAST=1 ./poc/scripts/smoke.sh` | Exit 126: tracked script is not executable. |
| `POC_FAST=1 bash poc/scripts/smoke.sh` | Exit 2 after three protocol-only `numpy_fd` cases; its final PoC pytest step has the same missing-`role_seed` collection error. Generated artifacts were removed after capture. |
| `python -m compileall -q Carbon_Logic neurons poc tests scripts examples` | Exit 0 with `Can't list 'Carbon_Logic'`; all existing requested roots compiled. |
| `ruff check .` | Exit 127: `ruff` is not installed. |
| `black --check .` | Exit 127: `black` is not installed. |
| `julia --version` | Exit 127: `julia` is not installed. |

**A0 implementation plan / DoD mapping.** Retain the existing canonical root;
add only the fourteen required package markers; use `evaluation/` and `chain/`
as the SDK-independent seam; migrate no caller not needed by the import/layout
test; preserve all current PoC, neurons, Julia, specifications, tests, and
legacy code; then re-run the exact table above plus `python -c "import carbon"`
and `git diff --check`. A0 may be marked done only if the package inventory,
before/after signatures, and focused diff evidence every listed DoD item.

**Post-change validation and delta.** Every exact baseline command above was
re-run. Exit codes and failure signatures were unchanged: root pytest still has
the same three missing-`torch` collection errors; PoC pytest and the Bash smoke
path still stop at the same missing `role_seed`; direct smoke remains exit 126;
compileall remains exit 0 with the absent-`Carbon_Logic` notice; and
Ruff/Black/Julia remain unavailable at exit 127. Therefore A0 introduced zero
new baseline failures, but the inherited repository baseline remains red.
`python -c "import carbon"` passed at exit 0. `git diff --check` passed at exit
0. Generated smoke/test artifacts and bytecode caches were removed and are not
part of the change.

### Blocking-review follow-up: installability and CI-equivalent evidence

**Compared states and isolation.** The review follow-up compared detached,
clean Git worktrees created with `git worktree add --detach`: base
`ab765b07bc8c41106194ce6d06b4a2bd1c03f9a1` at
`/private/tmp/carbon-a0-base.Mxz8U8` and the pre-follow-up A0 head
`e2f91a428c91a963caf261747f2ffd05ea0e1821` at
`/private/tmp/carbon-a0-head.ZWnuEh`. Each workflow path used a separate clean
virtual environment. Local comparisons used CPython 3.11.11 on macOS arm64
with virtual-environment pip 24.0. Neither worktree was dirty.

**No-dependency editable-install proof (A0 head).** From a clean virtual
environment, the actual project build configuration succeeded without a
packaging-metadata change:

```text
python -m pip install --no-deps -e /private/tmp/carbon-a0-head.ZWnuEh
exit 0; built and installed distribution carbon==0.9.0
```

Build isolation was left enabled; `--no-build-isolation` was not necessary.
From `/private/tmp` (outside the repository), the installed interpreter
`/private/tmp/carbon-a0-venvs.pRnWzd/head-editable/bin/python` imported
`carbon` and all fourteen required role packages at exit 0. Resolved paths
were:

```text
carbon              -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/__init__.py
carbon.schema       -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/schema/__init__.py
carbon.registry     -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/registry/__init__.py
carbon.seeding      -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/seeding/__init__.py
carbon.scoring      -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/scoring/__init__.py
carbon.cards        -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/cards/__init__.py
carbon.fees         -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/fees/__init__.py
carbon.traineval    -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/traineval/__init__.py
carbon.mcp          -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/mcp/__init__.py
carbon.leaderboard  -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/leaderboard/__init__.py
carbon.logging_utils -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/logging_utils/__init__.py
carbon.evaluation   -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/evaluation/__init__.py
carbon.audit        -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/audit/__init__.py
carbon.chain        -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/chain/__init__.py
carbon.qualification -> /private/tmp/carbon-a0-head.ZWnuEh/carbon/qualification/__init__.py
```

This proves only editable installation and import discovery for A0. It does
not prove that application dependencies, scientific behavior, CI, or any
backend is healthy or production-qualified.

**Exact current-workflow base/head comparison.** The authoritative workflow is
`.github/workflows/ci.yml`. It uses Python 3.11, a test job with
`pip install -e ".[dev]"` followed by `pytest tests/ -q --tb=no`, and a lint
job with `pip install ruff black pytest`, `ruff check .`, then
`black --check .`.

| Workflow command / stage | Base `ab765b07` | A0 head `e2f91a42` | Delta |
|---|---|---|---|
| `pip install -e ".[dev]"` | Exit 1 while resolving declared dependencies: `No matching distribution found for physicsnemo` | Exit 1 at the same stage with the same first material error | No new A0 failure; the workflow test command was not reached in either sequential job. |
| `pytest tests/ -q --tb=no` (forced in the isolated lint-tool environment because the test-job install cannot complete) | Exit 2; five collection errors; first material signatures are missing `neurons`, then `carbon` | Exit 2 with the same five files and signatures | No delta. This forced run is not represented as a successful or reached test-job stage. |
| `pip install ruff black pytest` | Exit 0 | Exit 0 | No delta. |
| `ruff check .` | Exit 1; 776 errors, 544 fixable | Exit 1; 776 errors, 544 fixable | Identical inherited lint failure. |
| `black --check .` (forced after Ruff for comparison; Actions skips it after Ruff fails) | Exit 123; 66 files would reformat, 56 unchanged, and two legacy parse failures | Exit 123; 66 files would reformat, 70 unchanged, and the same two parse failures | Same failure stage/signatures; the fourteen new one-line package markers account for the additional unchanged files. |

GitHub Actions corroborates the local comparison. Base run
`32232686102` and PR-head run `32234794106` both fail the test job at
`pip install -e ".[dev]"` on unavailable `physicsnemo`, skip the test step,
install lint tools successfully, and fail Ruff with the same 776 findings;
Black is skipped in both actual runs. These are inherited CI failures, not A0
regressions.

**Maturity statement.** The lowercase namespace and fourteen behavior-free
package boundaries are **IMPLEMENTED**. Editable installation and outside-tree
imports are **TESTED** by the isolated proof above. Full dependency resolution,
the inherited test/lint baseline, scientific semantics, backend behavior,
Bittensor integration, LIVE readiness, and production qualification are not
green and are not claimed. No packaging defect was found, so A0 changes no
packaging metadata or dependency declaration. The evidence supports retaining
A0 as `done`: installation/import acceptance is proven, exact base/head
workflow failures are non-regressing, and the base-to-head diff remains solely
A0 layout, mapping, evidence, and status work.

After this evidence-only documentation update, the no-dependency editable
install and all outside-tree imports passed again; the full workflow install,
forced test/Ruff/Black comparisons, and every original A0 baseline command
retained the signatures recorded above. `git diff --check` also passed. No
generated smoke artifacts, bytecode, or editable-install metadata is included.

## 2026-08-19 — Evaluation evidence / validator audit extension

- `Design_Specs/Evaluation_Evidence_and_Validator_Audit.md` is the normative owner for execution evidence, receipts, reproducibility qualification, validator audit/re-execution, and scientific-vs-emission separation.
- `Design_Specs/Build_Out_Protocol_Extension.md` is an additive sequencing extension pending fold-in to the next `Build_Out.md` revision.
- **Do not reorder Wave A.** Continue A0 → A12 in the current board order.
- Fold receipt/evidence hooks into existing Wave A tickets only where the extension explicitly assigns them.
- JAX is the first P0 backend targeted for qualification; other backend adapters are non-emission-capable until separately qualified.
- Do not expose raw official seeds/draw IDs in receipts, cards, logs, MCP, leaderboard, or public evidence.
- No ZK/proof-of-training work is required for P0.

## 2026-08-18 — A-1 maintainer dispositions for A0

These decisions govern A0 planning; they do not implement A0 or qualify any scientific behavior.

- Establish lowercase `carbon/` as the canonical package. Support only import paths that remain necessary; do not preserve `Carbon_Logic`, `hydrogen`, or `Carbon` as canonical namespaces.
- Use the Burgers PoC as the first vertical promotion source, without treating its current science, fixed values, scoring, or disclosure behavior as qualified.
- Retire the legacy `Carbon_Logic`, `hydrogen`, and `Carbon` namespaces; reuse `neurons/` only where an A0 audit finds it useful.
- Include Julia in the first build as the verification path for the v0 data generator. Repair and scientific validation remain explicitly owned work, not implied by inclusion.
- Normalize the `docs/context/` filenames in the appropriate scoped ticket. Treat the proposal appendix in `Open_Questions.md` as the v0 direction, subject to team audit; it does not override domain-owned specifications or authorize LIVE values.

## 2026-08-17 — Canonical .agent path

- Root `/.agent/` is the only board/ticket location.
- `agent_pack/` holds protocol docs only; Hermes notes under `agent_pack/executors/hermes/`.
- Build_Out pin: **v1.4**.

## 2026-08-14 — Pack bootstrap (historical)

- Early path used Hermes + Engy; execution is now executor-agnostic.
- Scope lock: Wave A only until WAVE.md checklist is done.
- Existing repo dirs (`poc/`, `neurons/`, `Design_Specs/`) are mapped, not deleted.

## Escalate / spend log (agent fills)

| Date | Ticket | Why stop/escalate | Outcome |
|------|--------|-------------------|---------|
| | | | |
