## 2026-10-05 — GRAPHITE-CARRIER-CONTAINMENT-01: a deterministic containment check of the real miner lane in Graphite's release gates

**Authority.** The Test Lead approved this, relayed by the coordinator to the
Test Engineer on 2026-10-05. The request: add a deterministic containment
check that uses the REAL miner research lane container (not the Attacker's
choices) to `phase4 prelive` and the phase-3 dry run. These are engineering
choices within GRAPHITE-01's delegated authority
(`.agent/tickets/GRAPHITE-01_in_house_testing_agent.md`). `phase4 prelive`'s
output is release evidence under OWNER-GRAPHITE-TEST-WAVE-05 §3. Not
security acceptance.

**Before.** Both gates put a fake where the miner door stands
(`phase4_prelive.FakeMinerDoor`, `phase3.DryRunMiner`). No release gate ran
code through the carrier's miner lane, so nothing in release evidence showed
that the Attacker's `run_python`/`run_julia` cell is contained.

**Decision.**

1. **The check** (`carbon/development_session/containment_check.py`). It runs
   one fixed code cell through the real lane: `research_carrier.run_script` ->
   `_run(miner_authored=True)` -> `miner_container.create_arguments` -> the
   fixed docker create/start. It uses the campaign's pinned analysis image,
   checked by `verify_image`. The cell's probes are fixed in Carbon's code and
   are never chosen by the Attacker.
   - **The canary.** Before the run, a canary is planted on the HOST, outside
     every mount: a fresh world-readable directory in the system temp dir
     holding a random marker. It is removed afterwards, even on failure, and
     the removal is checked.
   - **Data passed into the cell.** The canary's path and the host user's real
     `$HOME` path. The cell reports only byte counts, entry counts and digests;
     no names or contents leave it.
   - **The probes**, each with its pass rule:
     - **Canary:** the read and the directory listing are absent or denied.
     - **`/proc/1/comm`:** PID 1 is the container's own init. The host's own
       `/proc/1/comm` is read on the host side for the comparison.
     - **`/proc/self/cgroup`:** the container's namespaced root (`0::/`), not
       the host's hierarchy.
     - **Host home:** the stat, the listing and the read of `.profile` are
       absent or denied.
     - **Network:** TCP connect to 1.1.1.1:53, a UDP send there, and a DNS
       lookup all fail.
     - **Writes outside `/scratch`:** writes to `/`, `/tmp`, `/opt`, `/input`
       and the canary's host directory all fail.
   - **The report.** A structured report: each probe, what was observed,
     PASS/FAIL, the image id, the create arguments' digest (the lane's own
     `create_arguments`, rebuilt from the run's durable intent), and the
     inspected isolation.
   - **Fail closed.** Each of these is a FAIL, typed
     `containment_check_unavailable` where the check could not run:
     - no Docker;
     - no manifest, or an unreadable one;
     - an image that does not verify;
     - a carrier refusal.

     A failed cell, a missing output or a canary left behind is a FAIL
     (`containment_check_failed`). Nothing passes by default.
2. **`phase4 prelive`** gets a `carrier_containment` step, which runs first. It
   is a phase-4 live-path blocker, because the Attacker runs code. Its
   report is under `carrier_containment`. The new
   `--analysis-image-manifest` argument names the pinned image; without it the
   step fails closed.
   - **The prelive's own network guard holds.** The host process reaches
     Docker only through the CLI subprocess. Every network attempt happens
     inside the container, whose network is `none`. A test asserts the guard
     records nothing.
3. **The phase-3 dry run** reports `dry_run.carrier_containment` and exits
   nonzero unless it passes (`run --dry-run --analysis-image-manifest PATH`).
4. **Tests that are about something else** use a labelled passing double
   (`tests/cpu/containment_double.py`, `synthetic_test_double: true`). The
   check's own tests use a Docker double where the daemon stands. One
   real-Docker test runs where `CARBON_ANALYSIS_IMAGE_MANIFEST` and Docker
   exist. It is skipped elsewhere, and the gates still fail closed there.

**Real run, 2026-10-05, this WSL operator host.**
- **Image:** the most recent verifying analysis image, `sha256:002b543b…`
  (manifest under `~/carbon-p3/.carbon-artifacts/research-images/a4794a04…`).
  It verifies against this commit's runtime digest.
- **Result: PASS, all six probes contained.**
  - The canary and its directory were absent.
  - PID 1 was `python`; the host's is `systemd`.
  - The cgroup was `0::/`.
  - The host home was absent.
  - TCP and UDP failed with ENETUNREACH and DNS with `gaierror`.
  - Every write was refused with EROFS, and the canary's directory was absent.
  - The container ran as uid 65532, and the canary was removed.

**Coordinator addition, approved by the Test Lead: BLOCKED, not
implemented.** The coordinator relayed two further Test Lead approvals for
this branch:
- a registered INTERNAL resource profile (`internal-carrier-profile.v1`:
  `--memory`, `--cpus`, `--pids-limit` and a scratch quota, sized from the
  host) for Carbon's own internal Graphite campaigns only;
- per-session scratch for those campaigns, owned by the worker uid, mode 0700,
  and deleted at session end.

The miner lane was to stay byte-identical. The permission classifier refused
the edit to `carbon/development_session/miner_container.py` that the profile
needs. As instructed, the work stopped there. The two hunks that had already
landed were reverted, and this branch changes neither `miner_container.py`
nor `research_carrier.py`.

The design chosen before the stop is recorded for whoever picks it up:
- **Selection.** A `ContextVar` bound only by `miner_path.attach`, holding the
  registered policy object. Miner paths stay byte-identical.
- **Sizing.**
  - memory: a quarter of host memory, no swap;
  - CPUs: a quarter of host CPUs;
  - processes: 128 per CPU, at least 256;
  - shared memory: an eighth of the memory limit.
- **Scratch.** A kernel-enforced `--tmpfs /scratch` of half the memory
  limit, with uid/gid set to the worker and mode 0700. It is checked on this
  host's Docker (29.x, overlayfs snapshotter, cgroup v2), where
  `--storage-opt size` is unavailable. Outputs are exported by a fixed tar
  stream before removal, and the scratch is gone with the container on every
  path.
- **Typing.** Limit hits are typed `CANDIDATE_RESOURCE_EXCEEDED`, from the
  container's cgroup `memory.events` and `pids.events` (readable on the host)
  and a scratch `statvfs`.

**Smallest decision required:** the owner switches the session to
approve-edits mode (or allows the edit) so the change to `miner_container.py`
and `research_carrier.py` can land.
