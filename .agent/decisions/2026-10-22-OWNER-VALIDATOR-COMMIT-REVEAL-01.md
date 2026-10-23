# OWNER-VALIDATOR-COMMIT-REVEAL-01: validators commit to their score documents before they reveal them

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Carbon Validator's session: "we will use commit reveal". The owner said it in answer to the Validator's options for checking that validators run the right code.

## Decided

1. **Commit-reveal for validators' grading results.** Each round, every validator first publishes a commitment (a full sha256 digest) to its score document. It publishes the document itself only after the commit window closes. A validator therefore cannot copy another validator's results.
2. **Its purpose is an integrity check, not scoring.**
   - Honest validators produce byte-identical score documents: same pinned image, same GPU class, deterministic grading (OWNER-VALIDATOR-GPU-CLASS-01 and the E9 two-copy test).
   - A revealed document must match its commitment, and it should match the other validators' documents.
   - A mismatch is evidence for review. It does not change any score by itself.

## Not decided here

- **The mechanism:** where the commitments go (on-chain or off-chain), the window lengths, and what happens on a late, missing or mismatched reveal. The Validator lane designs these and brings back any consequence that touches weights or economics.
- **Bittensor's own weights commit-reveal** (a subnet hyperparameter) is a separate chain setting. It needs its own owner decision.
- Spot-check reruns and hardware attestation stay options. They are not adopted.
- **Scope:** testnet first, under the testnet = mainnet parity rule. Mainnet use follows the mainnet gate.
