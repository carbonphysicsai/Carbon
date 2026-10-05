# VALIDATOR-18: one answer key for every validator

**Status:** design, for review before any build.

**Authority:**
- OWNER-SHARED-ANSWER-KEY-01 (2026-10-05);
- OWNER-VALIDATOR-MAINNET-PARITY-01 items 3 and 5.

**Executor:** the Carbon Validator session. Branch
`claude/validator-18-shared-answer-key`, from main `c690f6f70`.

## What exists

Each battery deployment today draws its own batches from its own root (a
32-byte secret seed) and solves its own references. Validators therefore do
not share cases, which conflicts with the ruling.

## Design

**1. One key maker (Carbon).** For each Challenge, one operator-held root
draws every batch (`seeds.make_batch`, unchanged). Each batch is solved once,
on the reference host. The resulting **answer-key batch** is the cases, the
hidden duplicates and the reference records.
- **Fingerprint:** the batch's existing fingerprint, plus the references
  digest, committed to the key maker's append-only journal before any
  validator receives it.
- **Rotation:** follows the Challenge's registered cost-based schedule
  (parity item 5). The key maker prepares the next batch ahead of its window.

**2. Distribution.**
- Each batch goes to every admitted validator, encrypted to that validator's
  registered public key. The plaintext never touches shared storage.
- **The manifest** carries:
  - the fingerprint and references digest;
  - the activation window (block range);
  - the rule and contract digests.

  It is signed by Carbon's service key. A validator refuses any batch whose
  decrypted contents do not reproduce the manifest's digests.
- Each copy is recorded per recipient, so a leak is attributable to a copy.

**3. Validator side** (it replaces drawing its own batches).
- `import_batch` (it exists) takes the answer-key batch.
- It refuses to activate a batch outside its manifest window, or one whose
  digests differ.
- Its references are ingested verbatim. No validator re-solves.

**4. The same data for every miner.** Within a window, every validator
activates the same batch at the same block (the manifest's window). Every
miner scored in that window is therefore scored on identical cases and
references.

**5. Identical rebuilds.** A scored rebuild runs on the pinned GPU class with
the pinned determinism configuration and image (`GPU_DETERMINISM_STAGE_B`).
- The validator records the device class, the driver build and the
  configuration digest with each rebuild.
- A rebuild on another class or on CPU is typed `NOT_SCORED_UNPINNED_DEVICE`,
  never scored.
- **Cross-validator agreement check:** validators publish each rebuild's
  weight digest per submission. A digest that disagrees is a typed finding
  (`REBUILD_DISAGREEMENT`), not a score.

**6. Audit after retirement.** The key maker reveals a retired batch's
plaintext (`SeedJournal.reveal`, which exists). Anyone can check it against
the fingerprint that was committed before use, and against the scores the
validators published.

## Gaps against today's code

1. **Validator deployments draw their own batches.** They need an
   import-only mode with manifest checks.
2. **Today's validator backends** (the CPU carrier and `direct`) are not the
   pinned GPU class. A GPU validator backend with the pinned determinism
   configuration is needed for scored mainnet rebuilds.
3. **New code:** encryption to validator keys, signed manifests, the
   distribution channel and the per-recipient copy record.
4. **Publishing rebuild digests and the agreement check.**

## Open decisions (the owner's)

- **Validator admission:** how a validator's public key is registered, and by
  whom.
- **The distribution channel:** for example a Carbon-hosted encrypted bucket,
  or direct transfer.
- **Security acceptance** of the whole path (AGENTS.md §13).

## Maturity

Design only.
