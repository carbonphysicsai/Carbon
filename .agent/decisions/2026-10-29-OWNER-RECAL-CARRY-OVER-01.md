# OWNER-RECAL-CARRY-OVER-01: a validator-code hotfix carries the registered calibration over through a quick check, not a full recalibration

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29.
- **Owner's words:** "carry-over yes". This answers the Lead's question about the Validator's carry-over proposal (codex-queue/reports/IMAGE_DIGEST_SCOPE_AND_M9PRIME_RULING_20261029.md).
- **Decided:** when a hotfix changes a worker build input (for example `carbon/`) and the worker images move, the registered calibration and the GPU receipts carry over to the new images without a full recalibration, if a carry-over check on the registered class passes:
  - the registered control rebuilds with an identical fingerprint;
  - each non-bit-identical noise-panel member rebuilds 3 times, all within the registered range.
- **If the check fails:** a full recalibration runs.
- **Bounds:**
  - The carry-over is recorded with the old and new image identities and the check evidence.
  - Testnet now. Mainnet uses its own registered recalibration.
  - Changes outside the scoped build inputs (miner app, docs, tests) don't move the images at all (image-digest scoping in M9').
