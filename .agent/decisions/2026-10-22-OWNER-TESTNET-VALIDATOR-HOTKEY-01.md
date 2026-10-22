# OWNER-TESTNET-VALIDATOR-HOTKEY-01: the testnet validator's hotkey signs unattended on the class host

Date: 2026-10-22
Status: APPROVED by the owner, directly in the Carbon Validator's session ("go with (a) when we get there").
Scope: **testnet netuid 567 only**, from Phase B step 7 of the submit-to-weights plan (after all five Challenges pass internal testing). Mainnet key handling is a separate owner decision.
Amends: VALIDATOR-WORKSTREAM-I-TESTNET-01 §2 (the key-provisioning choice it left to the owner).

## Decided

- **Option (a):** valV3's **hotkey** (UID 12, `5DWznJMnCeoevFSwsck7LXdYBWAbiw1G1qrxnghqSHqQj2qr`) is placed on the ccx33 class host **unencrypted**, so `validator_setup weights` can sign every 1200 s without a person present.
- **The coldkey stays offline with the owner.** A hotkey can set weights and act as the validator, and it cannot move funds.
- **Who does what:**
  - **the owner provisions the hotkey on the host by hand**, when step 7 comes;
  - **agents never create, unlock, copy or read the key or its password.**
  - The host keeps it owner-only (mode 600, in the validator's own account).
- **The standing authorization** for the weights run is still confirmed by the owner directly before the first `weights run`.
