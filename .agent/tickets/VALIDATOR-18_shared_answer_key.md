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
- Each fetch is recorded per recipient. Fetches are attributable. A leaked key
  is byte-identical across validators, so it only narrows the leak to the set
  of fetchers in that window.

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

## The validator GPU (OWNER-SHARED-ANSWER-KEY-01, the validator-GPU addendum)

- **Pinned part: the NVIDIA A40 (48 GB) for launch.**
  - About 25x the memory any registered contract needs today.
  - Bit-identical across hosts and datacenters under the pinned configuration
    (`GPU_DETERMINISM_STAGE_B`).
  - The same digests as L4 and RTX 3060 on the tiny test model
    (`GPU_DETERMINISM_STAGE_A`).

  It is revisited only if testing needs more. Any change of part is a single
  standard switch for all validators, after a determinism re-run at real
  model sizes.
- **Build items:**
  1. A battery validator GPU backend on the pinned A40 configuration for JAX
     recipes, using the reconstruction worker's existing GPU profile.
  2. **PyTorch GPU rebuild:** a CUDA build of the PyTorch worker image, with
     its own pinned determinism settings. Prove same-part bit-identity on two
     A40 hosts before it scores.
  3. **Record peak GPU memory** for every rebuild. It has never been measured.
     The 600 s deadline and the envelope stay the contract's.
  4. **Refuse any scored rebuild** that is not on an A40 with the pinned
     configuration (`NOT_SCORED_UNPINNED_DEVICE`).

## Admission and distribution (OWNER-SHARED-ANSWER-KEY-01, the standard-Bittensor addendum)

These replace §2's per-validator encryption and the two open decisions above.

- **Admission:** a hotkey with a validator permit in the latest finalized
  metagraph. It is read with the existing read-only chain adapter, extended
  with the permit field. No registration step exists.
- **Distribution:** the answer-key service (HTTPS, Carbon-hosted).
  - **`GET` of the active batch** with a `btauth/1`-signed request
    (`carbon/chain/auth.py`). The service checks:
    - the signature, freshness and replay;
    - that the hotkey holds a validator permit at the finalized block.
  - **The response** is the batch and its signed manifest.
  - **Every fetch** is logged per hotkey, with the batch fingerprint.
- **Validator side:** one command fetches, verifies the manifest's digests
  and imports the batch, using the validator's hotkey and nothing else.
  Activation follows the manifest's block window.
- **Still owner-reserved:** security acceptance (AGENTS.md §13), and where the
  service is hosted.
