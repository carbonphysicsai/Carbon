# LEVEL4-G5-LANE-MEMORY-01: an 8 GiB memory limit for the Level 4 G5 compile lane only

**Status:** IN REVIEW. **Security-sensitive:** it changes the C-03 worker
sandbox (`carbon/reconstruction/worker/`). The owner reviews it before merge;
tests are evidence, not a security audit (AGENTS.md §13).

**Authority:**
- OWNER-L4-VALUES-01 (the owner, 2026-10-08: "approve §1–§5 as proposed")
  approved "8 GiB for the G5 lane" (`LEVEL4_VALUES_PROPOSAL.md` §4). The
  measured basis: the largest legitimate FNO's G5 compile peaks at 3.35 GiB
  of the worker's fixed 4 GiB.
- The Test Lead's direction, 2026-10-08: build it as its own PR, marked
  security-sensitive, with "no-network and the rest of the C-03 profile
  identical".
- G5 runs only in development and testnet (OWNER-L4-G5-COMPILE-ISOLATION-01);
  mainnet stays fail-closed. This ticket changes neither.

## Change

1. **A second C-03 CPU profile** (`carbon/reconstruction/worker/model.py`):
   `carbon.c03.linux-x86_64-cpu.level4-g5-compile.v1`, version 1.0. Its only
   difference is memory: 8 GiB, swap 0. It has its own profile digest, so a
   container launched under it carries a different policy label.
2. **The existing profile is byte-identical.** Its id, body and digest are
   unchanged, and a test pins that.
3. **The runtime enforces the launching profile's memory**
   (`worker/docker_runtime.py`), in all three places it enforced the global
   constant:
   - `--memory` and `--memory-swap` at launch;
   - the effective `HostConfig` inspection;
   - the cgroup `memory.max`.

   Every other control reads the same values as before: no network, private
   IPC, read-only root, dropped capabilities, no-new-privileges, the PID,
   CPU, cpuset, ulimit, scratch, input and output limits.
4. **Selected only for G5** (`development_session/research_carrier.py`). A run
   gets the G5 profile only when its provenance is
   `LEVEL4_G5_COMPILE_DEVELOPMENT` (`carbon.level4.compile.PROVENANCE`) and it
   requests no accelerator. Every other run, including the miner's own lane,
   is unchanged.

## Not in scope

- A host with less than 9 GiB passes the doctor's 5 GiB floor and still
  launches G5 under an 8 GiB cap. A cap is a limit, not a reservation, so
  such a host runs out of memory sooner. Raising the doctor's floor per
  profile is a follow-up if the owner wants it.
- Any GPU or accelerator profile.
- Mainnet.

## Done when

- The tests pin all of the following:
  - the existing profile is unchanged;
  - the G5 profile differs only in memory;
  - the runtime's launch arguments, inspection and cgroup checks use the
    launching profile's memory, and a container whose effective memory is
    not its profile's is refused (`WorkerCode.POLICY`);
  - only G5's provenance selects the G5 profile.
- The owner has reviewed the sandbox change.
