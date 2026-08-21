# Ticket A4 — Seeding domains + leakage tests (C6)

**Wave:** A
**Build_Out:** §7 Seeding (C6), invariants 1–2, plus the ratified evidence
extension's A4 `exam_commitment` boundary
**Depends on:** A0, A1, and A3's exact `ChallengeKey` and tagged-digest
identity
**Status:** `todo`; architecture is ratified, but implementation and tests have
not begun

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

- [ ] Define only the six ratified top-level domains and the four distinct
  canonical context-kind values.
- [ ] Add non-coercible exact 32-byte entropy types, private derived-value
  types, exact A3 challenge/digest reuse, and immutable typed contexts.
- [ ] Add a narrow fail-closed `BeaconProvider` protocol and a separately
  typed deterministic fixture provider without selecting production timing,
  chain, finality, reorg, nonce, drand/hybrid, or fallback policy.
- [ ] Add separate mock, official, qualification, and fixture-official
  derivation entry points with their exact domain matrix and no shared mode
  switch.
- [ ] Implement RFC 5869 HKDF-SHA-256 with scheme
  `carbon.seed.hkdf-sha256.v1`, exact ratified salt, canonical TLV `info`, and
  full 32-byte output retention.
- [ ] Implement strict versioned TLV encoding/validation, including hostile
  ordering, duplication, length, ASCII, digest, binding, and draw-index cases,
  using the exact A4-R9 schema tags and A4-R10/A4-R11 validator boundaries.
- [ ] Bind every official identity input, exclude every forbidden dynamic or
  miner/validator-controlled input, and prove Strategy mutation, call order,
  retries, and global RNG state cannot alter a context or later result.
- [ ] Implement the independent 32-byte private exam root, opaque unsigned
  `ExamCommitment`, and value-only public projection without implementing an
  EvaluationReceipt or audit/evidence log.
- [ ] Prove mock cannot request/access/affect official derivation;
  qualification is restricted to `reference`/`dossier`; and fixture material
  cannot be relabelled as provider-origin official material.
- [ ] Prove A4 public projections, card/leaderboard/MCP-shaped regression
  fixtures, representations, and errors expose no official entropy, seed,
  draw, or reconstruction-sensitive material. Actual A6/A9/A10 serializers
  retain their own later integration tests.
- [ ] Prove the installed `carbon.seeding` public API is dependency-free and
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

Neither test file exists yet; both belong to the later A4 implementation
change. Every Definition-of-Done checkbox remains open in this ratification
task.
