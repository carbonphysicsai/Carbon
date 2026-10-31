# OWNER-WEIGHTS-RUNTIME-486-AND-WINDOW-01: adopt testnet runtime spec 486 and a 14-day standing weights authorization window

Date: 2026-10-30 (CST)
Status: DECIDED by the owner, directly in the Validator session (local_9d14c86b-b50e-4cf2-a2ef-5c69ad1ed1e0); relayed by the Validator to the Lead, who records it here.
Owner's words: "Adopt runtime spec 486. Standing authorization window: from the current block for 100,800 blocks (14 days)."

## Decided

- The weights operator config's `expected_runtime_spec` is 486, the live testnet runtime spec read from chain on 2026-10-30. It replaces the earlier adopted 477.
- The standing weights authorization for policy testnet-winner-v4-launch (sha256:b26fed6c50229413223b3c785bc0439b66094e60b9af1afad2dce406fe41c325) is valid from the block at its creation through that block plus 100,800 blocks (14 days).

## Bounds

- If the live chain spec is not 486 when the file is built or used, the step stops and comes back to the owner.
- First weights still run only after a real crown, with a preview showing only crowned UIDs.
- Testnet 567 only. Renewing the window is a new owner decision.
