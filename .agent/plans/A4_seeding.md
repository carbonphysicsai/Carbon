# A4 seeding and leakage implementation plan

**Ticket:** A4 — Seeding domains + leakage tests
**Branch:** `agent/a4-seeding-ratification`
**Exact starting main:** `c5f2dfbda64e4375e3d3f26f7a463ca98cabd07a`
**Status:** planning only; A4 remains `todo` and implementation has not begun

This plan translates the maintainer-ratified A4-R1 through A4-R11 decision into
a bounded future implementation. The current ratification change adds no
Python source and no tests, does not mark A4 `in_progress`, and does not satisfy
any A4 Definition-of-Done item.

## Pre-implementation gate and maturity

- An independent GitHub fetch and a local `git fetch --prune origin` both
  resolved `main` to exact merge commit
  `c5f2dfbda64e4375e3d3f26f7a463ca98cabd07a`, with parents
  `69b938d1c4fd0aca58276940d15df50b1b68e5d1` and
  `43cf3279ca5138ad8fcd8bd87f2833c926a1c710`.
- PR #15 is normally merged, A3 is `done`, A4 is `todo`, and no open or merged
  competing A4 change was found. The recommended A4 branch was not present
  before this branch was created.
- The supported editable-install baseline at the exact starting commit is
  `392 passed`; `carbon/seeding/` contains only the A0 package marker.
- Current repository evidence therefore distinguishes the states correctly:
  A4-R1 through A4-R11 now fully **SPECIFY** the interface, derivation, and
  byte-level contracts needed for bounded A4 implementation. A4 remains
  `todo` and is not **IMPLEMENTED**, **TESTED**, or
  **PRODUCTION-QUALIFIED**.
- A4-R9 ratifies schema-local TLV interpretation, common-field tag reuse, and
  commitment private-root tag `0x0A`. A4-R10 reuses A3 `validate_version` for
  generator/scoring tokens. A4-R11 reuses A3 canonical-identifier grammar for
  `RoleKey` after an A4-owned 64-byte ASCII bound.
- Future implementation may begin only after this ratification PR is reviewed,
  merged, and verified on `main`, followed by a fresh authority/status check.
  This documentation follow-up itself neither starts nor authorizes code.

## Authoritative source map

| Source | Authority and A4 use |
|---|---|
| Root `AGENTS.md` | Governs authority, conflict escalation, no leakage, mock isolation, exact maturity claims, KEEP → WRAP → REPAIR → REPLACE, dependency discipline, and completion evidence. |
| `.agent/DECISIONS.md` — 2026-08-21 A4 entry | Ratified implementation decision for A4-R1 through A4-R11. It supersedes the ticket's `master_secret` sketch and completes the A4 byte contract without claiming implementation. |
| `.agent/INVARIANTS.md` | Requires no official seed/draw leakage, structural mock isolation, pinned official evaluation, determinism, and no placeholder LIVE/emission material. |
| `Design_Specs/Build_Out.md` §0, §2, §7 | Sequencing authority; owns the C6 placement, exact six top-level domains, and required role/leakage/mock test families. Its conceptual TrainEval `mode` belongs to later A8 and is not the A4 public API. |
| `Design_Specs/Build_Out_Protocol_Extension.md` §2 A4 | Assigns A4 the safe `exam_commitment` projection and permits a provider protocol while leaving seed timing to the data/seeding owners. |
| `SPEC.md` §§4 and 15 | Requires a shared validator-independent official exam, public physics with hidden realization, pinned generator/scoring identity, and train/eval/stress separation. |
| `Design_Specs/Data_Management.md` §§1–2 | Current semantic authority for hidden validator material, train/eval/stress separation, and later product-seed decontamination. Its direct-hash example is superseded only as an A4 byte-level implementation sketch by A4-R1/R4/R5. |
| `Design_Specs/Trustless_Verification.md` §§2–5 | Current semantic authority for shared public-unpredictable randomness intent, validator-hotkey exclusion, and local/official separation. A4-R1/R4/R5 supply the narrower typed byte contract without displacing those intended behaviors. |
| `Design_Specs/Generator_Creation.md` §§2, 6, 10 | Defines downstream deterministic `(seed, role)` generator expectations and qualification boundaries; A4 supplies bytes, not generator science. |
| `Design_Specs/Generator_Validation.md` §§1, 5–9 | Current semantic authority for keeping reference/dossier evidence distinct from the live exam and official seeds hidden. Its delimiter/truncation/PRNG examples are superseded only as A4 byte-level implementation sketches. |
| `Design_Specs/Evidence_and_Envelope_Standards.md` §§3–5 | Defines the dossier/reference purpose and in-envelope stress intent; it does not add seed domains or a derivation formula. |
| `Design_Specs/Miner_MCP.md` §§3, 9, 11, 14 | Owns the miner disclosure boundary: mock-only free paths and no official seeds/draw IDs on MCP or EvaluationCard. |
| `Design_Specs/Evaluation_Evidence_and_Validator_Audit.md` §§1–2, 4, 10–11 | Owns later receipt/evidence/audit semantics, distinguishes commitment from disclosure, recommends `BeaconProvider`, and requires exact commitment reproducibility without moving receipts into A4. |
| `docs/context/Decisions.md` D-003–D-007, D-029–D-030, D-039, D-041 | Records shared exam, role separation, commitment/disclosure separation, provider adapters, and constitutional leakage/isolation testing. |
| `docs/context/Open_Questions.md` OQ-005/OQ-006 | Authoritatively leaves exact seed timing/nonce lifecycle and production beacon/fallback qualification unresolved. Its later delayed-block/hybrid discussion is a proposal, not a ratified policy. |
| `docs/context/Implemented_vs_Specified` | Confirms A3 is merged/tested while shared seed flow, leakage prevention, and mock isolation lack A4 acceptance proof. Do not update it for a planning-only change. |
| `docs/context/Architecture_Rationale.md` | Explains shared exams, train/eval/stress separation, commitment without disclosure, incomplete honest mock practice, and adapter boundaries. |
| `docs/context/Carbon_Context.md` | Restates the public/hidden trust boundary, exact non-floating reproducibility, provider evolution, and maturity vocabulary. |
| Current `carbon/registry/` and `carbon/schema/` | Code authority for exact A3 `ChallengeKey`, tagged digest validation, and A2's miner-controlled seed/draw rejection. A4 reuses these boundaries and never infers code from a specification. |

The historical-blob pointer in `Data_Management.md` and old PoC/archive code do
not override the current checked-in repository under the authority hierarchy.
The current data/generator specifications retain semantic authority; only
their incompatible byte-level sketches are superseded for A4 by the ratified
implementation decision.

## KEEP / WRAP / REPAIR / REPLACE findings

| Area | Disposition for later A4 implementation |
|---|---|
| `carbon/seeding/` | **KEEP** the canonical dependency-free namespace; **REPAIR** its A0 marker by adding the ratified modules and explicit exports only when implementation starts. |
| `carbon.registry.ChallengeKey` | **KEEP and reuse directly**. It is the exact frozen A3 challenge identity; A4 must not accept a weaker tuple or duplicate its parser. |
| `carbon.registry.digest.is_sha256_digest` | **WRAP/reuse directly** for generator/scoring tagged-digest validation. `ArtifactBinding` alone only type-checks and is not sufficient. |
| `carbon.registry.model.validate_version` | **WRAP/reuse directly** for generator/scoring version tokens under A4-R10. Do not copy its regular expression; challenge version remains owned by `ChallengeKey`. |
| `carbon.registry.model.validate_canonical_identifier` | **WRAP/reuse directly** for A4-R11 role-key grammar after A4 enforces its separate 64-byte ASCII bound. The A3 helper itself has no length bound. |
| A2 `dry_validate` seed/draw controls | **KEEP** as the miner-input boundary. A4 contexts never accept or retain a Strategy mapping, so post-context Strategy mutation is irrelevant. |
| `carbon/common/seeds.py` | **REPLACE as canonical A4 semantics; leave untouched as legacy.** It uses delimiter concatenation, 63-bit modulo integers, a common `master_seed`, role aliases, `local_mode`, and public seed bundles that conflict with A4-R1–R5/R8. |
| PoC seed contexts/generators/cards/tests | **REPLACE/retire as A4 authority; leave untouched.** They expose master/raw seeds, block hash, nonce, integer conversions, and generic local/official switches. Preserve only historical evidence that determinism and role separation were intended. |
| Legacy `carbon/common/model_card.py` | **Do not wrap.** It serializes raw seeds and belongs to later A6 migration, not the A4 public projection. |
| Backend/global RNG consumers | **KEEP outside A4.** Torch/NumPy/JAX integer/key conversion and RNG mutation belong behind later A8 adapters and require their own qualified conversion contract. |

No historical file is deleted, rewritten, or declared compliant by A4.

## Exact scope and context/domain matrix

The only top-level domains are:

```text
mock
official_train
official_eval
official_stress
reference
dossier
```

The future public entry points must make invalid crossings unrepresentable or
reject them by exact runtime type; they must not dispatch on a generic mode
string or Boolean.

| Entry point/context | Root type | Canonical context kind | Allowed domains |
|---|---|---|---|
| Mock derivation | `MockEntropy` | `mock` | `mock` only |
| Provider-origin official derivation | `OfficialEntropy` obtained from `BeaconProvider` | `official` | `official_train`, `official_eval`, `official_stress` only |
| Fixture-official derivation | `FixtureOfficialEntropy` from a separate fixture boundary | `fixture_official` | the three `official_*` domains only |
| Qualification/reference derivation | `QualificationEntropy` | `qualification` | `reference`, `dossier` only |

Initialization, augmentation, shuffle, dropout, batch order, generator
sampling, and other consumers are canonical internal role keys inside one row;
they are never added to the top-level domain set. Entropy wrapper types must be
separate and non-inheriting, with exact runtime-type checks, copied bytes, and
non-disclosing representations. Supported A4 constructors never coerce across
those types; this is structural interface separation, not authenticated proof
of byte origin against a caller that deliberately rewraps bytes.

## Expected types and public API

The exact names may be tightened during implementation review without changing
semantics, but the package boundary is expected to expose:

- exact 32-byte `OfficialEntropy`, `MockEntropy`, `QualificationEntropy`, and
  `FixtureOfficialEntropy` value types;
- an opaque copied 32-byte `EvaluationBinding` structural value;
- exact domain/context-kind values and canonical internal `RoleKey`;
- immutable official, fixture-official, mock, and qualification context types
  carrying exact `ChallengeKey`, generator/scoring pins, seed scheme, and
  evaluation binding without retaining Strategy or provider objects;
- a private value type for the complete 32-byte derived seed and a distinct
  private 32-byte exam-root type, neither serializable through public helpers;
- opaque `ExamCommitment("sha256:<64 lowercase hex>")` and a frozen value-only
  public exam projection containing only the commitment, explicit public
  challenge/generator/scoring pins, plus an unmistakable explicit fixture
  marker/status when the projection is fixture-origin;
- a `BeaconProvider` protocol whose one observation returns only
  `OfficialEntropy`, plus a separate deterministic fixture provider returning
  only `FixtureOfficialEntropy` through a distinct fixture API. Official
  acquisition enforces the exact return type rather than trusting protocol
  return annotations.

Expected separate derivation functions are conceptually:

```text
derive_mock_seed(mock_context, role_key, draw_index)
derive_official_seed(official_context, official_domain, role_key, draw_index)
derive_fixture_official_seed(fixture_context, official_domain, role_key, draw_index)
derive_qualification_seed(qualification_context, qualification_domain, role_key, draw_index)
```

The implementation may use shared private HKDF/TLV helpers, but no public
function accepts a union of entropy/context types plus `mode`, and no context
can be relabelled after creation. Provider acquisition creates and copies one
immutable official context or fails; later derivations are stateless and do
not call the provider again.

## Expected package layout

Prefer only the Python standard library (`dataclasses`, `enum`, `hashlib`,
`hmac`, `struct`, `typing`) under `carbon/seeding/`:

| Future file | Responsibility |
|---|---|
| `carbon/seeding/model.py` | Domains, context kinds, entropy/binding/private/public value types, exact pins, immutable contexts, safe representations, and validation orchestration. |
| `carbon/seeding/encoding.py` | Versioned TLV encoders plus a private strict validator/parser used to reject unknown, duplicate, reordered, malformed, or noncanonical documents. |
| `carbon/seeding/derive.py` | RFC 5869 Extract/Expand, separate typed derivation entry points, and no global/counter/backend state. |
| `carbon/seeding/commitment.py` | Independent private exam-root Expand, canonical commitment hash, and value-only public projection. |
| `carbon/seeding/provider.py` | `BeaconProvider`, fail-closed provider acquisition, and the separately typed deterministic fixture provider; no real chain/network implementation. |
| `carbon/seeding/__init__.py` | Small explicit public export surface only. |

The dependency direction should remain acyclic: model may reuse the
dependency-free A3 identity helpers; encoding depends on model; derivation on
model/encoding; commitment on model/encoding/derivation; provider only on
model. Importing `carbon.seeding` must not import execution, cards, MCP,
validator, chain, Bittensor, scientific, or backend packages.

## Identity and validation contract

Every derivation context carries and copies the following immutable inputs:

- exact A3 `ChallengeKey`, including both challenge ID and exact challenge
  version;
- exact generator version validated by
  `carbon.registry.model.validate_version` and an A3-form tagged generator
  digest;
- exact scoring version validated by
  `carbon.registry.model.validate_version` and an A3-form tagged scoring
  digest;
- exact seed-scheme identifier `carbon.seed.hkdf-sha256.v1`;
- exact 32 raw-byte evaluation binding;
- exact canonical context kind.

One seed derivation additionally binds the exact allowed top-level domain,
canonical role key, and explicit draw index. Draw indices require
`type(value) is int` and `0 <= value <= 2**64 - 1`; Boolean, negative,
overflowing, subclassed/coerced, and non-integer values fail before encoding.
Generator/scoring versions call
`carbon.registry.model.validate_version` directly: exact built-in `str`, exact
unchanged spelling, inclusive 64-character bound, and ASCII grammar
`[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*`. The implementation does not trim,
normalize, coerce, case-fold, resolve aliases, or duplicate the A3 regular
expression. `1.0` and `burgers1d_v0.1` are valid; empty values and leading,
trailing, or adjacent separators reject.

`RoleKey` is a distinct A4 type. It requires an exact built-in `str`, strict
ASCII encoding, no normalization/trimming/case folding/coercion/alias
resolution, and at most 64 encoded bytes. A4 applies that byte bound, then
calls `carbon.registry.model.validate_canonical_identifier(value, "role_key")`
for grammar `[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*`; it does not copy the regular
expression. The A3 helper provides the grammar, not the A4 length bound. If
either A3 validator changes before implementation, re-check the authoritative
contract and regenerate/review all affected golden vectors before coding.

The context constructor accepts no validator/miner identity, Strategy mapping,
miner hyperparameter, miner seed/nonce/block hash/draw ID/exam ID, clock, PID,
environment value, scheduling state, retry count, or RNG state. Tests must
prove those values cannot influence output through mutation, call ordering, or
ambient process state.

## HKDF-SHA-256 contract

Use RFC 5869 exactly:

```text
scheme = ASCII("carbon.seed.hkdf-sha256.v1")
salt   = ASCII("carbon/a4-seeding/hkdf-sha256/v1")
IKM    = the applicable typed 32-byte entropy value
PRK    = HMAC-SHA256(salt, IKM)
OKM    = HKDF-Expand(PRK, canonical_info, 32)
```

For a 32-byte output under SHA-256, Expand is one standard RFC 5869 block; the
implementation should still name and test a bounded private Expand helper so
the independent exam-root domain cannot be confused with seed info. Retain all
32 output bytes in the private type. Do not expose an integer conversion,
truncate, apply modulo, reuse output across roles, or import a backend RNG.

The test suite must include an RFC 5869 reference vector for the private helper
and Carbon-specific golden bytes for each fully ratified document.

## Canonical TLV encoding

Seed `info` starts with exact ASCII `carbon.seed.info.v1`, followed by this
exact sequence. Each item is `tag:u8 || length:u32be || payload`.

| Tag | Field | Payload contract |
|---|---|---|
| `0x01` | context kind | Exact `official`, `mock`, `qualification`, or `fixture_official` ASCII |
| `0x02` | seed-scheme identifier | Exact scheme ASCII |
| `0x03` | challenge ID | Exact bytes validated by A3 `ChallengeKey` |
| `0x04` | challenge version | Exact bytes validated by A3 `ChallengeKey` |
| `0x05` | generator version | Exact A4-R10/A3 version token |
| `0x06` | generator digest | Exact A3-form tagged lowercase SHA-256 ASCII |
| `0x07` | scoring version | Exact A4-R10/A3 version token |
| `0x08` | scoring digest | Exact A3-form tagged lowercase SHA-256 ASCII |
| `0x09` | evaluation binding | Exactly 32 raw bytes |
| `0x0A` | seed domain | One exact allowed domain ASCII value |
| `0x0B` | role key | Exact A4-R11 canonical role-key ASCII |
| `0x0C` | draw index | Exactly eight bytes, unsigned big-endian |

The exact header selects the versioned schema before any TLV tag is
interpreted. Tags are schema-local, not global identifiers.

`carbon.exam-root.info.v1` reuses the seed document's common field tags and
payload contracts exactly:

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

The exam-root document ends after `0x09`, with no domain, role, draw, private
root, or trailing field. Its distinct header and complete input document
provide an independent Expand domain from role-seed derivation.

`carbon.exam-commitment.v1` reuses those same `0x01` through `0x09` tags and
payload contracts, then adds exactly `0x0A` — private exam root, with a payload
of exactly 32 raw bytes. The order is exactly `0x01` through `0x0A`, with no
additional or trailing fields. Tag `0x0A` intentionally means seed domain in
`carbon.seed.info.v1` and private exam root in
`carbon.exam-commitment.v1`; the distinct headers make that reuse unambiguous.
Implementations must not use a global tag map, introduce `0x0D` for the private
root, or reserve unused seed-schema tags for cross-schema uniqueness.

No delimiter concatenation, JSON, Unicode normalization, alternative field
order, or permissive decoding is allowed. Unknown, duplicate, reordered,
malformed-length, malformed-payload, and trailing unrecognized fields reject.

## Private exam root and public commitment boundary

- Derive the private exam root with the same PRK and independent exam-root
  `info`; retain exactly 32 private bytes.
- Hash the canonical commitment document once with SHA-256 and expose only the
  lowercase tagged `ExamCommitment` value.
- Construct the public projection from copied public values. It must not retain
  the context, entropy wrapper, derived seed, private root, provider, callable,
  closure, or mutable mapping from which private values could be reached.
- Secret-bearing value representations and validation errors must be generic
  and non-echoing. Public commitment representation may show the commitment
  because it is intentionally public.
- Fixture projections expose `fixture_official` explicitly; no relabelling or
  omission of fixture status is permitted.
- A4 creates no receipt, ID, signature, timestamp, score/prediction/reference
  commitment, execution transcript, Merkle/MMR log, or audit record.

The security statement is deliberately conditional. A4 proves interface
non-disclosure and deterministic domain binding, not unconditional hiding.
Recovery resistance relies on SHA-256 and HKDF-SHA-256 assumptions, adequate
provider entropy, and relevant entropy remaining unavailable for the required
protocol interval.

## Isolation and fail-closed behavior

- Provider-origin official acquisition accepts only exact `OfficialEntropy`
  from `BeaconProvider`; absence, wrong length/type, a provider-signalled
  conflict, or exception becomes a stable generic failure with no
  default/fallback value. A4 does not independently compare multiple chain
  observations or assess entropy strength/disclosure history.
- The deterministic fixture provider returns only
  `FixtureOfficialEntropy`. It is not accepted by the provider-origin context
  constructor, which never casts or relabels it through a shared base class.
  This does not authenticate provenance against a caller deliberately creating
  a new wrapper; real provider authentication/qualification remains external.
- Mock derivation accepts only `MockEntropy` and the `mock` domain. It cannot
  receive an official context, request official domains, touch a provider, or
  mutate any counter/state used by official derivation.
- Qualification derivation accepts only `QualificationEntropy` and only
  `reference`/`dossier`; it cannot request mock or official domains.
- All derivation is pure and stateless. Different query counts, reordered
  calls, thread scheduling, retries, global RNG mutations, environment/clock
  changes, and failed mock calls leave later official bytes unchanged.
- Identical official inputs produce identical 32-byte outputs and commitments
  across validators; validator hotkey is absent from the input model.

## Cross-ticket ownership

| Ticket/boundary | Ownership |
|---|---|
| A3 | Supplies exact `ChallengeKey` and tagged-digest validation. A4 does not modify registry persistence/LIVE qualification or infer generator/scoring pins from generic artifacts. |
| A4 | Owns typed entropy/context/domain separation, canonical encoding, 32-byte HKDF outputs, private exam root, unsigned commitment, value-only public projection, and its focused leakage/isolation proof. |
| A5 | Later supplies/loads exact scoring-version/digest pins and scoring behavior. A4 treats pins as opaque identity and implements no score semantics. |
| A6 | Owns InternalResult/EvaluationReceipt/Card storage and actual allow-listed miner projections. Its miner/public projection may consume only A4 public values. Whether authorized private evidence storage retains A4 private material is protocol-owned and must never make that material reachable from EvaluationCard. |
| A7 | Owns `submission_id`, strategy hashing, fees, FSM/idempotency, and the concrete immutable value supplied through A4's 32-byte `evaluation_binding` slot. A4 assigns no A7 semantics. |
| A8 | Owns TrainEval mode dispatch, backend-specific seed/key conversion, deterministic stub behavior, and non-emission capability. Its adapters use further role-separated derivation or a documented adapter conversion from A4 bytes; A4 imports no backend. |
| A9 | Owns miner-facing MCP handlers and consumes A6's budgeted output. If later A6/A9 policy exposes the A4 commitment/projection, MCP may receive only that public value and never an entropy/context/private-seed object. |
| A10/A11/A12 | Later leaderboard, logging, and constitutional integration tests repeat the public allow-list and redaction invariants across their real surfaces. A4 does not pre-implement them. |

## Expected implementation files

Only the later A4 implementation should create or modify:

```text
carbon/seeding/model.py
carbon/seeding/encoding.py
carbon/seeding/derive.py
carbon/seeding/commitment.py
carbon/seeding/provider.py
carbon/seeding/__init__.py
tests/cpu/test_seeding.py
tests/cpu/test_no_leakage.py
```

The implementer may combine a pair of small private modules if that reduces
surface area without weakening type separation or testability. No A4 source or
test file is created by this plan.

## Expected CPU tests

`tests/cpu/test_seeding.py` should cover:

- RFC 5869 helper vector and exact Carbon scheme/salt/header/golden bytes;
- all six domains, four context kinds, role/domain/draw separation, complete
  32-byte retention, and identical-input reproducibility;
- exact `ChallengeKey` reuse and change sensitivity for every generator,
  scoring, evaluation-binding, domain, role, and draw field;
- A3-form lowercase tagged-digest rejection cases;
- strict TLV unknown/duplicate/order/length/ASCII/value rejection;
- Boolean/negative/overflow/non-integer draw rejection;
- provider absence/error/wrong type/wrong length/conflict with no fallback;
- fixture/provider non-coercion and unmistakable fixture projection;
- mock/official/qualification domain matrix and cross-context separation;
- query-count/call-order/thread/global-RNG/retry/clock/environment independence;
- mutation of a Strategy after context creation having no effect because no
  Strategy object is retained;
- exam-root versus role-seed separation and commitment determinism/change
  sensitivity under the exact A4-R9 tag contract;
- exact A4-R10 version and A4-R11 role-key valid/invalid examples, the
  role-key 64-byte boundary, and proof that the A3 validators are reused rather
  than duplicated.

`tests/cpu/test_no_leakage.py` should cover:

- exact field allow-list for the A4 public projection and its serialized form;
- no reference path from the public object to entropy/context/private root or
  derived seed objects;
- safe secret-type `repr`, exception, and provider-error messages;
- recursive value checks proving known private bytes do not occur in public
  commitment/projection/card-, leaderboard-, or MCP-shaped regression values;
- absence of forbidden exact private field names and reconstruction-sensitive
  values in those shaped fixtures;
- explicit fixture status and no emission-capability field/claim;
- proof that tests do not apply a broad `"seed" in key` blacklist to arbitrary
  miner-authored Strategy parameters, which would contradict A2's inert JSON
  contract. Actual A6/A9/A10 serializers receive integration tests in their
  own tickets.

Run the focused suite with:

```bash
python -m pytest tests/cpu/test_seeding.py tests/cpu/test_no_leakage.py -q
```

Then run the complete default CPU suite.

## Import-isolation requirement

Add an installed/outside-tree `python -I` subprocess proof modelled on the A2
and A3 tests. It should import and exercise all public A4 APIs while blocking:

- optional roots such as Bittensor, JAX, NumPy, Torch, SciPy, YAML,
  NeuralOperator, PhysicsNeMo, and MCP;
- Carbon execution/disclosure packages including backbones, cards, chain,
  evaluation, fees, leaderboard, logging, MCP, scoring, TrainEval, training,
  and validator.

The dependency-free A3 registry package may load because A4 must reuse
`ChallengeKey`; no registry I/O object is constructed. The diagnostic records
attempted and loaded blocked modules and requires both lists to be empty. Build
a fresh no-dependency wheel for the completion proof so success cannot depend
on importing the checkout through the working directory.

## Security risks and required mitigations

| Risk | Required treatment |
|---|---|
| Cross-schema TLV tag confusion | Dispatch on the exact versioned header, interpret each A4-R9 schema independently, test both meanings of `0x0A`, and reject unknown/duplicate/reordered/trailing fields. |
| Validator drift or duplicated identity grammar | Call the then-current A3 helpers, keep the separate A4 64-byte RoleKey bound explicit, and regenerate/review golden vectors if A3 changes before implementation. |
| Weak or prematurely disclosed provider entropy | Opaque 32 bytes do not let A4 detect this. Entropy quality/timing and real-provider/fallback qualification remain OQ-005/OQ-006 work; retention/disclosure remains separately protocol-owned under A4-R7. |
| Missing, malformed, unavailable, or provider-signalled conflicting observation | Fail closed with a generic error and no default. A4 neither resolves multiple observations nor chooses a fallback. |
| Fixture/mock relabelling | Non-inheriting types, exact runtime checks, distinct context-kind bytes, fixture-marked public projection, and negative crossing tests. |
| Ambiguous/colliding identities | Exact A3 challenge/digest reuse, length-prefixed ordered TLV, exact domain/context values, explicit draw, and golden/perturbation tests. |
| Secret leakage through values, errors, repr, references, or shaped public records | Private/public types, copied allow-listed projection, generic errors/reprs, reachability and serialization tests, and later A6/A9/A10 integration gates. |
| Hidden state or query-order influence | Pure derivation, no counters/global RNG/environment/clock, one copied provider observation per context, and reordered/concurrent regression tests. |
| Premature backend conversion | No integer/NumPy/JAX/Torch API in A4; A8 owns and documents further derivation/conversion. |
| Overstated hiding or production readiness | State only the conditional interface/cryptographic boundary and preserve explicit maturity labels and human protocol/security ownership. |
| Python memory-lifetime assumptions | Do not claim guaranteed zeroization of immutable Python bytes; minimize copies/references and keep private objects outside public surfaces. |

## Explicit non-goals

A4 does not implement or choose:

- a Bittensor/Subtensor, chain, drand, hybrid, or production beacon provider;
- block delay, chain event, finality, nonce lifecycle, reorg, fallback,
  retention, or post-evaluation disclosure policy;
- a Carbon-operated long-lived master secret or environment-secret fallback;
- new peer seed domains, domain aliases, a generic mode switch, or
  `local_mode`;
- `submission_id`, strategy canonicalization/hash, fee/FSM/idempotency,
  receipt identity, or concrete evaluation-binding semantics;
- an EvaluationReceipt, signature, timestamp, score/result/prediction/reference
  root, execution transcript, append-only log, Merkle/MMR checkpoint, or audit;
- generator logic, dossier science, reference solvers, Score Pack/scoring
  behavior, backend execution, RNG-key conversion, cards, MCP, leaderboard,
  logging, Bittensor weights, or emissions;
- scientific validity, LIVE activation, backend/security/operations approval,
  production qualification, permanent secrecy, or emission capability;
- broad rewrites of current domain specifications, context ledgers, legacy
  PoC files, or A3 source.

## OQ-005 and OQ-006 remain unresolved

Together, OQ-005 and OQ-006 retain exact Phase-0 seed timing and production
beacon policy: chain event/block selection, delay, finality, nonce lifecycle,
reorg/replay handling, real-provider selection, hybrid/drand construction,
security qualification, observation handling, and production fallback. The
delayed-future-block and hybrid material in the Open Questions appendix is
recommendation/proposal, not ratified policy. A4 accepts one opaque 32-byte
provider observation and fails closed on missing, malformed, unavailable, or
provider-signalled conflicting material; that failure behavior does not select
a production fallback.

A4-R7 separately leaves entropy retention and post-evaluation disclosure
policy protocol-owned. This plan does not assign that policy to OQ-005 or
OQ-006 and does not choose it.

## Bounded implementation sequence

1. After this ratification PR is reviewed, merged, and verified on `main`,
   re-check exact base, ticket status, competing changes, authority files, and
   the then-current A3 validator contracts before beginning implementation.
2. Implement immutable model/root/pin/context/public types with exact A3 reuse
   and non-disclosing representations.
3. Implement and golden-test strict canonical encoders/validators.
4. Implement RFC 5869 private helpers and the four separate typed derivation
   entry points without ambient state.
5. Implement provider/fixture acquisition and every fail-closed crossing.
6. Implement the independent private exam root, commitment, and copied public
   projection.
7. Add focused determinism, hostile-input, isolation, leakage, reference, and
   import-boundary tests.
8. Run the complete verification set, review the entire exact-base diff, and
   obtain independent human review before changing A4 status.

## Completion evidence required before A4 can be `done`

- Implementation and golden vectors use the ratified A4-R9 schema-local tag
  contract and A4-R10/A4-R11 validator boundaries. Any intervening A3
  validator change is explicitly re-evaluated against the current authority
  before code is written.
- Every A4 ticket checkbox is supported by named source and acceptance tests;
  no checkbox is completed from documentation alone.
- Both focused CPU files pass, followed by the complete default CPU suite with
  no regression.
- `git diff --check`, strict Ruff/Black for every changed Python file, and the
  repository no-new-debt quality gate against the exact implementation base
  all pass with actual inventory recorded.
- A fresh no-dependency wheel passes the outside-tree import/isolation proof
  with no blocked optional or Carbon consumer imports attempted or loaded.
- The full diff contains only bounded A4 source/tests and necessary workflow
  evidence; A3 exact identity, fixture/LIVE gates, and every A3+ invariant are
  unchanged.
- Review confirms public objects cannot retain/reveal private material,
  fixture/mock/qualification identities cannot cross into provider-origin
  official material, and no backend/emission path was introduced.
- The final evidence accurately distinguishes **SPECIFIED**,
  **IMPLEMENTED**, **TESTED**, and **PRODUCTION-QUALIFIED**, and repeats the
  conditional—not theorem-level—security claim.
- Independent review, merge, reviewed-head ancestry, and post-merge CI evidence
  are recorded before `.agent/WAVE.md` or the ticket marks A4 `done`.

Until all of that completion evidence exists, A4 stays `todo`. This
documentation follow-up begins no implementation and makes no qualification
claim.
