# Ticket A4 — Seeding domains + leakage tests (C6)

**Wave:** A
**Build_Out:** §7 Seeding (C6), invariants 1–2, plus the ratified evidence
extension's A4 `exam_commitment` boundary
**Depends on:** A0, A1, and A3's exact `ChallengeKey` and tagged-digest
identity
**Status:** `done`; bounded implementation on `agent/a4-seeding` began from
exact base `e13baf312b811e2fd6784856c56d851a15f153fd`. Independently reviewed
head `b0f79cf96b7cd489a97a7a4dd49285d762c962aa` merged normally in PR #17 as
`120eab02e406bda280d9c361bbbb7d8ef7a08330`, is ancestral to current `main`,
and passed exact-head and post-merge CI; the bounded A4 ticket is closed

**Ratified decision:** `.agent/DECISIONS.md`, “2026-08-21 — A4
pre-implementation seeding architecture ratification” (A4-R1 through A4-R11).

**Goal:** Implement deterministic, non-colliding typed seed contexts and an
opaque unsigned public `exam_commitment`, while proving that official material
cannot cross miner/public interfaces and that mock, qualification, fixture,
and provider-origin paths cannot cross.

## Ratified boundary

The former sketch
`derive_seed(domain, challenge_version, role_key, master_secret)` is
superseded. A4 must not define a Carbon-operated long-lived `master_secret` as
the official root. Root material is exact, opaque, and separately typed as
`OfficialEntropy`, `MockEntropy`, `QualificationEntropy`, or
`FixtureOfficialEntropy`. Provider-origin official material comes only through
a fail-closed `BeaconProvider` observation of exactly 32 bytes.

The complete top-level domain set is exactly:

```text
mock | official_train | official_eval | official_stress | reference | dossier
```

Internal purposes such as initialization, augmentation, shuffle, dropout,
batch order, and generator sampling are role keys beneath a top-level domain,
not additional domains. Mock, official, qualification/reference, and
fixture-official derivation use separate typed contexts and entry points; A4
has no generic mode switch or `local_mode` Boolean.

Official derivation binds exact challenge, generator, scoring, seed-scheme,
evaluation, domain, role, and draw identities using RFC 5869 HKDF-SHA-256 and
the ratified canonical TLV documents. The retained seed is exactly 32 bytes.
Backend integer/NumPy/JAX/Torch conversion remains later A8 adapter work.

The A4 public projection is a value-only boundary containing a typed
`ExamCommitment("sha256:<64 lowercase hex>")`, explicit public pins, and
fixture status where applicable. It retains no private context/root reference
and contains no entropy, seeds, draw/sample IDs, nonce, hidden ordering, or
reconstruction-sensitive hashes. A4 does not implement a receipt, signature,
timestamp, score/result root, evidence log, card store, MCP handler, backend,
or emission writer.

A4-R9 through A4-R11 complete the byte-level contract. Exam-root and
commitment common fields reuse tags `0x01` through `0x09` under their exact
schema headers; commitment tag `0x0A` holds the exact 32-byte private exam
root. Generator/scoring versions reuse
`carbon.registry.model.validate_version`, while the distinct A4 `RoleKey`
enforces its 64-byte ASCII bound before reusing
`carbon.registry.model.validate_canonical_identifier`. Tags are schema-local,
and A4 does not duplicate either A3 validation grammar.

## Definition of Done

- [x] Define only the six ratified top-level domains and the four distinct
  canonical context-kind values.
- [x] Add non-coercible exact 32-byte entropy types, private derived-value
  types, exact A3 challenge/digest reuse, and immutable typed contexts.
- [x] Add a narrow fail-closed `BeaconProvider` protocol and a separately
  typed deterministic fixture provider without selecting production timing,
  chain, finality, reorg, nonce, drand/hybrid, or fallback policy.
- [x] Add separate mock, official, qualification, and fixture-official
  derivation entry points with their exact domain matrix and no shared mode
  switch.
- [x] Implement RFC 5869 HKDF-SHA-256 with scheme
  `carbon.seed.hkdf-sha256.v1`, exact ratified salt, canonical TLV `info`, and
  full 32-byte output retention.
- [x] Implement strict versioned TLV encoding/validation, including hostile
  ordering, duplication, length, ASCII, digest, binding, and draw-index cases,
  using the exact A4-R9 schema tags and A4-R10/A4-R11 validator boundaries.
- [x] Bind every official identity input, exclude every forbidden dynamic or
  miner/validator-controlled input, and prove Strategy mutation, call order,
  retries, and global RNG state cannot alter a context or later result.
- [x] Implement the independent 32-byte private exam root, opaque unsigned
  `ExamCommitment`, and value-only public projection without implementing an
  EvaluationReceipt or audit/evidence log.
- [x] Prove mock cannot request/access/affect official derivation;
  qualification is restricted to `reference`/`dossier`; and fixture material
  cannot be relabelled as provider-origin official material.
- [x] Prove A4 public projections, card/leaderboard/MCP-shaped regression
  fixtures, representations, and errors expose no official entropy, seed,
  draw, or reconstruction-sensitive material. Actual A6/A9/A10 serializers
  retain their own later integration tests.
- [x] Prove the installed `carbon.seeding` public API is dependency-free and
  imports no optional scientific, backend, MCP, validator, chain, or Bittensor
  modules.

## Must not

Do not expose official entropy, private roots, raw/derived official seeds,
draw IDs, or reversible identifiers through EvaluationCard, leaderboard, MCP,
public projections, logs, errors, or representations. Do not choose production
beacon/timing/disclosure policy, implement A7 identity semantics, convert to
backend RNG keys, add dependencies, or make scientific/LIVE/production/
security/emission claims.

## Expected tests

```bash
python -m pytest tests/cpu/test_seeding.py tests/cpu/test_no_leakage.py -q
```

## Implementation evidence

- Exact implementation base:
  `e13baf312b811e2fd6784856c56d851a15f153fd`.
- Branch and interpreter: `agent/a4-seeding`; CPython `3.11.11`.
- Implementation: `carbon/seeding/model.py`, `encoding.py`, `derive.py`,
  `commitment.py`, `provider.py`, and the explicit package exports in
  `carbon/seeding/__init__.py`.
- Acceptance tests: `tests/cpu/test_seeding.py` and
  `tests/cpu/test_no_leakage.py`.
- Focused command:
  `python -m pytest tests/cpu/test_seeding.py tests/cpu/test_no_leakage.py -q`
  — `230 passed in 3.55s`.
- Complete default CPU command: `python -m pytest -q` —
  `622 passed in 4.35s` (untouched-base baseline: `392 passed in 0.97s`).
- Compilation command:
  `python -m compileall -q carbon/seeding tests/cpu/test_seeding.py tests/cpu/test_no_leakage.py`
  — passed.
- Strict changed-file quality: `ruff check carbon/seeding
  tests/cpu/test_seeding.py tests/cpu/test_no_leakage.py` — all checks passed;
  `black --check carbon/seeding tests/cpu/test_seeding.py
  tests/cpu/test_no_leakage.py` — eight files unchanged.
- Repository quality gate against the exact base — passed with inventory
  `Ruff 757/776; Black 62/68`, eight changed Python files, no new debt, and
  every changed Python file clean. Report: `/tmp/carbon-quality-a4.json`.
- Fresh project wheel: `carbon-0.9.0-py3-none-any.whl`, SHA-256
  `4bd58cc8b0e503cd127dd5c64f67970899ecabebd1554860121de8086028c511`.
  A no-dependency install in a fresh venv ran the installed public API from
  outside the checkout under CPython `3.11.11` with `python -I`: exact golden
  seed and commitment passed, the provider was observed once, and blocked
  optional/consumer imports were both attempted `[]` and loaded `[]`.

## Closure evidence

- Independent review approved exact implementation head
  `b0f79cf96b7cd489a97a7a4dd49285d762c962aa` for the bounded ticket, with no
  unresolved blocking finding. GitHub records no formally submitted review
  object, review thread, or PR comment, and this closeout does not claim one.
- Exact-head pull-request CI run `32440327141` completed successfully: CPU
  reported `622 passed in 7.80s`; Code quality reported
  `Ruff 757/776; Black 62/68`, eight changed Python files, no new debt, and all
  changed Python files clean.
- PR #17 merged normally as
  `120eab02e406bda280d9c361bbbb7d8ef7a08330`, with ordered parents exact base
  `e13baf312b811e2fd6784856c56d851a15f153fd` and exact reviewed head
  `b0f79cf96b7cd489a97a7a4dd49285d762c962aa`. The reviewed head is ancestral
  to current `main`.
- Exact-merge `main` push CI run `32444857456` completed successfully: CPU
  reported `622 passed in 8.68s`; Code quality again reported
  `Ruff 757/776; Black 62/68`, eight changed Python files, no new debt, and all
  changed Python files clean.
- The focused `230`-test acceptance suite, complete `622`-test local suite,
  compilation, strict Ruff/Black, exact-base quality gate, and fresh
  no-dependency wheel/outside-tree `python -I` proof remain the bounded
  implementation evidence recorded above.
- Consumer-shaped leakage fixtures prove the A4 public-value boundary only.
  They are not acceptance of future A6 card storage, A9 MCP transport, A10
  leaderboard, or A11 logging integrations, which retain their own tests.
- A4-R1 through A4-R11 remain **SPECIFIED**; the bounded A4 boundary is now
  **IMPLEMENTED** on `main`, **TESTED** to the recorded scope, independently
  reviewed, merged, ancestry-verified, and post-merge-CI verified. A4 is `done`.
  **PRODUCTION-QUALIFIED: NO.**

This closure adds no real provider, timing/finality/nonce/reorg/fallback or
provider-authentication policy; no A7 binding semantics; no A8 backend
conversion; no A6/A9/A10/A11 consumer implementation; and no scientific, LIVE,
security, production, permanent same-process secrecy, weight-writing, or
emission claim. OQ-005 and OQ-006 remain unresolved. A5 and later tickets remain
`todo` and unstarted.
