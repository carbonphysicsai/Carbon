# OWNER-COPY-REISSUE-UID0-01: re-issue the same four sealed copies to UID 0 instead of the rehearsal validator

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Validator session (local_9d14c86b-b50e-4cf2-a2ef-5c69ad1ed1e0); written here by PR Head from the Validator's report (GPUYARD_GPU4_REPEAT_EVIDENCE_RULING_20261030.md).
Owner's words: "Yes, re-issue to UID 0"

## Why

The Validator's earlier statement that the rehearsal validator signs weights and serves as the receiver was wrong. Under null consensus only the largest-stake UID (UID 0) keeps a validator permit (null_consensus_switch.py:51-54), and the receiver watches its hotkey's validator permit (receiver_permit_lost, :1629; the publisher is exempt, :1645).

## Decided

- Re-issue the same four packs (Motor d40782ab… and e27dd6b5…, Cooling e5f6e2a1… and 220b0808…, full fingerprints in OWNER-COPY-ISSUE-MOTOR-COOLING-01) to hotkey 5HWGPxuumoCdSXmbT62wNEnBN4rgU1WZXdPJfw4zqjLqV1wR, testnet 567, a 90-day window, one copy each.
- The copies issued to the rehearsal validator are superseded and never imported.
- Receivers are prepared with --hotkey 5HWGPx… (ss58 only). The weights signer is UID 0; the owner places its key tomorrow, just before the first set_weights.
- Executed at activate block 8335004, retire 8983004.

## Bounds

- Testnet 567 only. check-weights runs once the weights config exists and before the first set_weights.
