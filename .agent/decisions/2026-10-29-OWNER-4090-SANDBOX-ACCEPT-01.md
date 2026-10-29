# OWNER-4090-SANDBOX-ACCEPT-01: the owner accepts the miner-code sandbox on the validator host (HOSTKEY NL 7950X + RTX 4090) for testnet

- **Received by:** the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae), directly from the owner in chat, 2026-10-29.
- **Owner's words:** "I accept the sandbox."
- **Context:** the Lead had listed this as step 4 before the registered calibration: "Your acceptance of the sandbox that runs miner code on this machine, with the GPU attached ... It's a security call, so it's yours."
- **Decided:** the containment that runs miner-controlled work on [held in custody] is accepted for testnet operation and the registered recalibration:
  - with the GPU attached;
  - with the same containment limits as the 10-21 testnet acceptance: network none, read-only root, pids, nofile, inodes, intake parse bounds;
  - with the measured lane limits under OWNER-4090-MINER-LIMITS-MAX-PRACTICAL-01.
- **Bounds:**
  - **Scope:** testnet and rehearsal only. Mainnet needs the security review plus a new, direct owner acceptance.
  - **Re-ask condition:** if the remaining measurements (concurrency, peak RSS), or any later change, alter a containment limit or the isolation design, the acceptance must be asked again.
  - Tests are not a production security audit.
