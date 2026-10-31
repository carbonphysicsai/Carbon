# OWNER-UID0-HOTKEY-UNENCRYPTED-ON-VALIDATOR-01: the UID 0 hotkey goes on the testnet validator box unencrypted, for the unattended weights service

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae).
Owner's words: "that's fine lets do what we need"

## Context

The owner wallet's runbook step 2 found that the UID 0 hotkey (`publisher`, 5HWGPxuumoCdSXmbT62wNEnBN4rgU1WZXdPJfw4zqjLqV1wR) is password-protected. The weights service runs unattended, and the hotkey password never goes on the box. The Lead recommended an unencrypted copy of the hotkey only; the hotkey cannot move funds or stake.

## Decided

- An unencrypted copy of the UID 0 hotkey, plus the public coldkey file, is placed on the testnet validator box for the weights service. The owner made the copy and copied it himself.
- The original hotkey stays password-protected on the owner's PC. The coldkey never goes on the box.
- The owner deleted the local unencrypted export after the copy.

## Bounds

- Testnet 567 only. Mainnet hotkey custody needs its own owner decision.
- Weights still run only after a real crown, under the owner's pre-approval.
