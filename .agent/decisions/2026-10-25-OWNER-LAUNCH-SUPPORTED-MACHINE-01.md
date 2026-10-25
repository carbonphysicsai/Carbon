# OWNER-LAUNCH-SUPPORTED-MACHINE-01: one supported machine setup for launch; warn, don't block, elsewhere

- **Received by:** the Lead session, directly from the owner in chat, 2026-10-25.
- **Owner's words:** "I'm also like 5 minutes from saying we should just restrict the type of machine miners can run launchpad on ... I'm not spinning our wheels for days to make it anything", then "Yes. Fix that so we can press forward."
- **Decided:**
  - **Supported setup for the testnet launch:** Ubuntu 22.04/24.04 x86_64 + Docker 29 (the installer may install it), ≥ 16 GB RAM, ~150 GB free disk.
  - **GPU optional:** any NVIDIA with a minimum driver version set from what Carbon's JAX/PyTorch builds need (Launchpad states it with its source).
  - **Before launch, only the supported setup is tested:** M1, plus a clean fresh host on the same setup.
- **Not a block:** other setups get a clear warning ("not a supported setup yet; it may work; use the supported setup for a guaranteed run") and the miner may proceed. This keeps OWNER max-miner-freedom and avoids hard hardware rules.
- **After launch:** support widens one setup at a time, backed by the fake-host test corpus (Docker 28, other distros, wider GPU shapes).
- **Still a launch blocker:** the worker /scratch/tmp crash, which occurred on Ubuntu 24.04 (inside the supported setup).
