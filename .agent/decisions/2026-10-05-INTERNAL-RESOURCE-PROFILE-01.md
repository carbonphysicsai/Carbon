## 2026-10-05 — INTERNAL-RESOURCE-PROFILE-01: Carbon's own host can bound the miner lane; a miner's machine never is

**Authority.**
- The owner approved this edit in the Test Engineer session on 2026-10-05,
  under his "protect-first" direction: build on protection rather than
  narrowing freedom, with maximum value alignment and maximum freedom.
- The Test Lead relayed the same approval.
- It closes lesson E5 in `docs/development/graphite/LESSONS_REGISTER.md`
  (the internal resource profile for agent code on the shared operator host).
- Security acceptance stays the owner's. This is a tested implementation,
  not a security audit (AGENTS.md §13).

**Decision.**
1. **The default is unchanged.** On a miner's machine nothing changes. The
   owner's 23 September 2026 direction stands: the miner's research has no
   Carbon-imposed CPU, memory, process, file or time limit. With no profile
   named, `create_arguments` produces exactly the arguments it did before.
2. **Carbon's own operator host may name a profile.** The operator names an
   owner-only file in `CARBON_RESEARCH_RESOURCE_PROFILE`, schema
   `carbon.miner-research.resource-profile.v1`, with exactly these fields:
   `cpus`, `memory_bytes`, `pids_limit` and `nofile`. Each must be a positive
   integer.
   - Carbon chooses no values: the operator writes them for the host's
     capacity.
   - The profile adds `--cpus`, `--memory` and `--memory-swap` (equal to
     `--memory`, so no swap beyond the bound), `--pids-limit`, a `nofile`
     ulimit and a digest label.
   - Shared memory and the BLAS/OMP thread counts are capped at the profile's
     values.
   - The isolation flags are untouched.
3. **Fail closed.** A named file that is not a regular, owner-only file owned
   by the operator, or whose record is not exactly v1, refuses the launch
   before any container command runs. The research carrier settles it as
   "nothing created". A host that asked for bounds never runs unbounded.
4. **Verified after create.** `inspect_isolation` checks that the container
   received exactly the profile: the label digest, `NanoCpus`, `Memory`,
   `MemorySwap`, `PidsLimit` and the `nofile` ulimit. Its record carries the
   profile digest. Without a profile the gate asserts nothing about size, as
   before, and its record is unchanged.
5. **Exclusive host window.** Once the operator writes a profile on the
   operator host, Graphite Attacker sessions no longer need an exclusive
   host window (the Test Lead's interim rule). Writing the file is an
   operator step, done outside the repository.

**Not in scope.**
- The private per-session scratch already sits under the owner-only
  campaign root (`prepare_scratch`), so this change leaves it alone.
- Level 4–5 rebuild isolation is separate work.
