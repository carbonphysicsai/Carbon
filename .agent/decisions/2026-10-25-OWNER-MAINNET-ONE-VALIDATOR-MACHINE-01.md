# OWNER-MAINNET-ONE-VALIDATOR-MACHINE-01: mainnet runs on one 4090 machine

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-25.
- **Owner's words:** "Doesn't a 4090 have CPU components that can do that work? Honestly, whatever is the most simple way to execute this" (in reply to the Validator's ruling that mainnet needs separate rebuild and grading hosts).
- **Decided:** mainnet validation runs on ONE dedicated 4090 server (the HOSTKEY pick, Ryzen 9 5950X, 128 GB):
  - miner recipe rebuilds use the GPU, inside the containment sandbox VM (CONTAINMENT_VM_TEST_PROCEDURE_20261025.md);
  - sealed exam copies and grading/graph inference stay OUTSIDE the sandbox, on the host CPU;
  - its CPU is registered as the mainnet grading class, and the speed gate is timed on it.
- **Supersedes:** the Validator's separate-hosts ruling (VALIDATOR_GPU_ANY_HOST_RULINGS end, 16:33Z) for mainnet. The owner holds security authority. This is conditional on the containment VM test passing (OWNER-MAINNET-SECURITY-ACCEPT-01); if it fails, the separate-host design comes back to the owner.
- **Throughput later:** extra 4090s only for rebuilds, when volume needs them (an owner decision then).
- **Testnet:** unchanged (ccx33 grading class).
