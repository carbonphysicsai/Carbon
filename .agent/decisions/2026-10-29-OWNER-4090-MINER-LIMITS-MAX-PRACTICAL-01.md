# OWNER-4090-MINER-LIMITS-MAX-PRACTICAL-01: miner limits on the validator host are the biggest practical values its measurements allow

- **Received by:** the Validator session (local_9d14c86b-b50e-4cf2-a2ef-5c69ad1ed1e0), directly from the owner in chat, 2026-10-29. Landed by the Lead.
- **Owner's words:** "yes we want biggest practical limits that throughput and bandwidth allow."
- **Decided:** on the validator host (HOSTKEY NL 7950X + RTX 4090), the per-miner limits are not fixed in advance. Each is set from the host's own measurements, as large as throughput and bandwidth allow. This replaces the fixed PROVISIONAL numbers. Scope: testnet.
- **Derivation (Validator's implementation of the owner's rule; MAILBOX/LEAD.md "2026-10-29 OWNER ANSWERS"):**
  - **Lanes:** as many as throughput needs (3, PROVISIONAL). Never fewer just to make each lane bigger.
  - **Lane memory:** floor((MemTotal − the measured host + receiver + grading peak − 8 GiB margin) / lanes), with shm inside it. RLIMIT_AS = lane memory.
  - **GPU memory:** VRAM − the measured CUDA context and allocator reserve. The same on every Challenge, one GPU rebuild at a time.
  - **CPUs:** (32 − the measured host and grading need) / lanes, in whole cores.
  - **Scratch:** the largest value that still leaves the disk budget for every lane at once.
  - **Output:** the largest the validation and bank path handles inside the rebuild wall over 1 Gbps, at most the lane memory.
- **Bounds:**
  - Every value is written with its measurement digest.
  - The MINER_FREEDOM T3 lowering rules still apply: floors only go up.
  - Containment limits are unchanged: pids, nofile, inodes, network none, read-only root, intake parse bounds.
  - This is not a security acceptance.
