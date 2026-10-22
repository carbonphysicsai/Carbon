# OWNER-TESTNET-EXAM-KEYS-01: fresh testnet exam keys are created on the new exam server

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Carbon Validator's session: "let the team create fresh testnet keys on the new exam server". It answers the Validator's question O-KEY: neither the exam producer signing key nor the K_master copy key existed on any custody host.
Scope: TESTNET 567 and rehearsal only. Mainnet keys and their custody are a separate owner decision, taken at the mainnet gate.

## Decided

1. **Two fresh keys are created on the new exam server**, the custody host `carbon-custody2`:
   - the **exam producer signing key** (`answer_key.ProducerKey`, Ed25519). It signs canonicalisation records, sealed-pack commitments and withdrawal notices;
   - the **K_master copy key**, from which each validator hotkey's traceable-copy key is derived (`K_v = HMAC(K_master, hotkey)`, E4).
2. **Custody of the keys:**
   - Both private keys are generated on that host and never leave it. They are not copied, not printed, not logged and not committed.
   - Each sits in its own owner-only file (0600) under the producer's custody directory.
   - Its path is recorded in the private ledger only, never in a public record.
3. **Signing runs on that host.** The canonical re-pack (`SEALED_REPACK_GRID_F02_F08_20261022`) signs its records there, in place, so no manifest needs to move.
4. **The public half becomes the trust root by a reviewed change:**
   - The producer public key (64 hex) is set in `carbon/challenge_validator/exam_producer.json` by one commit with a Validator receipt.
   - The same value goes into the distribution host's and the receivers' `producer_public_key` configs.
   - The public key and its `key_id` may appear in records.
5. **Nothing signed under an earlier or unknown key is trusted.** The old rehearsal producer key (2026-10-13) is not reused.

## Not decided here

- Mainnet key generation, custody, backup or rotation.
- Any hardware security module.
