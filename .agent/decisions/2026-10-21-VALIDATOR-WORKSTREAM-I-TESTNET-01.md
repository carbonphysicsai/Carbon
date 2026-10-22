# VALIDATOR-WORKSTREAM-I-TESTNET-01: the official-path rehearsal on testnet 567 (three open choices)

Date: 2026-10-21
Status: DECIDED by the Carbon Validator. The owner delegated it directly, in the Validator's session ("make your best judgement").
Scope: **testnet netuid 567 and rehearsal only.** Mainnet stays fail closed. LIVE economics, mainnet keys and the security acceptance remain the owner's (AGENTS §3, §14).
Maturity: engineering design decision. No scientific, security or economic acceptance is created, and no chain action is taken by this record.
Design: Workstream I (sealed grade → KOTH → set_weights), steps I5–I7.

## 1. Testnet weights from sealed-exam KOTH crowns: YES, testnet only

- **Why:** testnet must run as mainnet will (OWNER-VALIDATOR-MAINNET-PARITY-01). The owner rejected public-practice scoring as test evidence; only hidden-condition scoring that sets real weights counts. As it stands, the reward layer refuses every KOTH crown (`PROMOTION_DEVELOPMENT_ONLY`, `carbon/rewards/winner_eligibility.py:70-71`), so the weight path can never be exercised past Battery.
- **The rule to build (I5):**
  - A crown decided by `compare_private_pair` **on a sealed-exam evaluation version** carries a new incumbent reason, `bank_comparison_sealed_testnet`.
    - Public-practice or `DEVELOPMENT_PUBLIC_ADAPTIVE` evidence never carries it.
    - Today's `bank_comparison_development` stays refused.
  - `winner_eligibility` pays the new reason **only** when the active weight policy's `network` is the testnet one. Any other network refuses it with a typed code.
  - The frontier/promotion separation (AGENTS §7.7) is unchanged. A testnet weight is not a FrontierAdvanceEvent and creates no settlement entitlement.
- **Tests:**
  - a sealed crown is paid under a testnet policy and refused under a non-testnet policy;
  - a development or public-practice crown is still refused.

## 2. Who operates the testnet validator, and how often

- **Identity:** **valV3**, UID 12, hotkey `5DWznJMnCeoevFSwsck7LXdYBWAbiw1G1qrxnghqSHqQj2qr`. It is the staked rehearsal validator (0.5 test TAO).
  - Not UID 0, the subnet owner's publisher, so the rehearsal tests a permit-holding validator as mainnet will have.
  - Not UID 1, which the owner said to leave alone.
- **Host:** the DEVELOPMENT class host, Hetzner ccx33 (VALIDATOR-HOST-CLASS-CCX33-01). The Test Lead operates it.
- **Keys:** the owner provisions valV3's hotkey on the host by hand. An agent never creates, unlocks or reads a password or key file. Unattended signing (an unencrypted hotkey on the host) is the owner's security choice, made at provisioning.
- **Cadence:**
  - `weights_every_s` = **1200 s**, a third of a 360-block epoch (about 4,320 s at 12 s blocks). The issuer deduplicates per epoch, so this gives one publication per epoch with two spare attempts.
  - `sync_every_s` = **3600 s**.
  - Both are engineering values, not economic ones.
- **Weight policy:** `testnet-winner-v3-five-challenge-dev` (N = 5), per the owner's 2026-10-19 "Include it." The registry's `current` moves to v3 with that citation.
- **Standing authorization (`load_standing`):** drafted by the Validator when I6 is ready, and **confirmed by the owner directly** before the first `weights run`. It authorizes chain transactions under the owner's keys, so it is not delegated here.
- **Mainnet operators:** decided at launch, alongside the mainnet hardware (TBD).

## 3. Alert channel: none external for the rehearsal

- The I7 monitor writes typed alerts to the validator's local status file and exits non-zero:
  - heartbeat age;
  - last weights epoch older than 2 epochs;
  - last sync older than 2 × `sync_every_s`.
- The Test Lead's sweep (at least every 2 hours) reads it.
- **Why:** this needs no third-party account or secret. An external channel (webhook or e-mail) is chosen before mainnet, and it needs the owner's account.
