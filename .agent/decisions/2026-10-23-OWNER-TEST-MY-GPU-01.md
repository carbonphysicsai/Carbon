# OWNER-TEST-MY-GPU-01: an opt-in "Test my GPU" step in Launchpad setup

Date: 2026-10-23
Status: APPROVED by the owner, directly in the Lead session (local_b7032708-92d1-4a7c-a1d3-9ad008ba9cae). Asked whether to add an optional "Test my GPU" button that runs one roughly 1-minute test on the miner's own GPU, after showing the exact command and only with the miner's OK, the owner replied: "yes".
Amends: OWNER-MINER-COMPUTE-LINK-ONLY-01. The compute check itself still starts nothing. This separate step starts one test container, only when the miner explicitly chooses it.

## Decided

- After Setup's compute check, Launchpad offers an opt-in "Test my GPU" button. It is never automatic.
- It shows the exact command and where it runs (the miner's own compute: their machine or their linked server), then runs only after the miner confirms.
- It runs one short GPU smoke per installed framework (PyTorch, JAX) on public synthetic data, with no exam data and no keys. It reports in plain words: "works", or "your driver X is older than needed Y; update it or use the CPU / another backend".
- It never rents, stops or bills compute. Carbon never starts it on its own.
