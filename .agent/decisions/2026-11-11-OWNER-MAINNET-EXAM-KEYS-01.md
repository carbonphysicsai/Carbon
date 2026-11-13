# OWNER-MAINNET-EXAM-KEYS-01: fresh mainnet exam keys, pinned for finney 116

Date: 2026-11-11
Status: APPROVED by the owner, typed in the custody operator's (TL-2B) session on Wed 11 Nov 2026. The keys were created the same day.
Scope: MAINNET (finney, netuid 116), for the Fri 13 Nov launch versions. It leaves OWNER-TESTNET-EXAM-KEYS-01 (testnet 567) unchanged.

## The owner's line

"Mainnet exam keys: TL-2B may create a fresh mainnet exam producer key and a fresh mainnet K_master on carbon-custody2, owner-only, never printed, copied or committed, and make one passphrase-encrypted backup of both that I keep offline. Their public producer key may be pinned for finney 116 by a reviewed commit. Signing for mainnet runs only on custody2. TL-2B may issue mainnet copies for Carbon's own mainnet door hotkeys for the Fri 13 Nov launch versions. Any other mainnet issuance asks me."

## Decided

1. **Two fresh mainnet keys exist on the custody host `carbon-custody2`:**
   - the **mainnet exam producer signing key** (`answer_key.ProducerKey`, Ed25519);
   - the **mainnet K_master** copy key.

   They are distinct from the testnet keys, and the testnet keys are never reused for mainnet.
2. **Custody:**
   - Both private keys were generated on that host and never leave it, except as the one passphrase-encrypted backup the owner keeps offline.
   - They are not printed, logged, copied or committed.
   - Their paths are in the private ledger only.
3. **The public half is the mainnet trust root, pinned for `finney-116` only** in `carbon/challenge_validator/exam_producer.json` (schema v3, one key per network):
   - producer public key `e5672ac1539b3858fca4e782da4ec66224e3786687c01cb289fface56fd09c5b`;
   - key_id `carbon-producer-e2906e038e95ab4c`.

   A finney door verifies exams only against this key. A testnet door never trusts it, and the release refuses any record that pins one key for two networks.
4. **Mainnet signing runs only on custody2.**
5. **Issuance:**
   - Mainnet copies go only to Carbon's own mainnet door hotkeys, for the Fri 13 Nov launch versions.
   - Any other mainnet issuance asks the owner.

## Not decided here

- Rotation of the mainnet keys: a rotation needs a new owner decision and one reviewed pin commit.
- Any hardware security module.
