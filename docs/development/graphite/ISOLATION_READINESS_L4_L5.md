# Level 4-5 isolation readiness: a read-only assessment

**Authority.** OWNER-GRAPHITE-TEST-WAVE-03 §3 (owner, 2026-10-04), "Assess
Level 4-5 isolation now". The record is on
`origin/claude/graphite-test-wave-03` (`3b267bff4`) as
`.agent/decisions/2026-10-04-OWNER-GRAPHITE-TEST-WAVE-03.md`; it is not on
main at the time of writing. **Ticket:** GRAPHITE-ADMISSION-01. **Read at:**
`origin/main` `992d046b6`. Every `file:line` below refers to that commit.

**What this is.** An assessment only. It changes no code, runs nothing, starts
no pod and spends nothing. It is not a security review, not isolation
acceptance and not a resolution of MQ-015. Running participant-supplied
executables still needs the security owner's isolation acceptance
(OWNER-GRAPHITE-TEST-WAVE-03 lines 102-104; GRAPHITE-ADMISSION-01 ticket,
line 114). Nothing here is `SECURITY_QUALIFIED`, and this document does not
say that any path is secure.

## 0. Summary

- **No Graphite path runs participant-supplied executables today.**
  - Graphite's pods run Carbon's own fixed GPU program on a declarative
    strategy (`carbon/agent_campaign/graphite/pod_phase.py:9-27`).
  - C-03 does not accept participant code, callbacks, plugins, commands or
    executables as inputs (`.agent/DECISIONS.md:13563-13564`;
    `.agent/tickets/C-03_isolated_reconstruction_worker.md:41-44`).
  - The research carrier runs miner-authored Python. The miner lane does so on
    the miner's own host, in a container without Carbon resource limits, and
    its output is self-reported.
  - The battery attack adapter declares Levels 3-5 as seams that are
    `NOT_RUN` (`carbon/agent_campaign/attack/adapters/battery.py:1586-1608`).
- **The closest mechanism is C-03's Carbon lane.** It is IMPLEMENTED and
  TESTED for public DEVELOPMENT work on its exact image and runtime. It is
  not SECURITY_QUALIFIED, the C-03 ticket is `in_progress`, and MQ-015
  remains `SECURITY_REVIEW_REQUIRED`. Its stated claim boundary leaves out
  the threats that hostile participant code brings, such as kernel and
  runtime zero-days and side channels.
- **The pod path is further away.**
  - Carbon applies no isolation of its own inside a pod.
  - The participant program would share a uid, a PID namespace, a filesystem
    and open network egress with the bootstrap.
  - The pod's provider credential is reachable by a program running under
    that uid: the Carbon Validator's open item (§4.2).
- **Neither level's execution interface exists.** There is no constrained
  inference interface for Level 4 and no independently isolated inference
  stage for Level 5. Both are design work, and both depend on security-owner
  decisions.

Headline gaps (detail in §5; sizes in §5's legend):

| Dimension | Local C-03 | RunPod pod |
| --- | --- | --- |
| Compute | S | M |
| Memory | S | M |
| Filesystem | S | M |
| Network | S | L |
| Process | L | L |
| Time (wall and CPU) | S | M |
| Separate uid | M | M |
| Images (pinned, immutable) | S | M |
| Secrets and credentials | S | M |
| GPU access | L | L |
| Output channel and trust | L | M |
| Logging and evidence | M | M |
| Teardown and cleanup | S | S |

## 1. What Levels 4 and 5 ask for

The ladder, word for word from Admission §3 (`carbon/challenge_pipeline/ladder.py:46-53`;
`Design_Specs/Challenge_Admission.md:102-109`):
- Level 4: "New architectures exporting through a constrained inference
  interface".
- Level 5: "Custom inference in an independently isolated execution stage".

Battery's accepted level proposals widen nothing at these levels. Level 4 is
empty, and Level 5 lists capabilities that are already rebuildable
(OWNER-GRAPHITE-TEST-WAVE-03, lines 55-60). The attack adapter declares
`level_4_constrained_inference_export` and `level_5_custom_inference` as
seams that need participant code and the security owner's isolation decision
(`battery.py:1539-1544`, `1593-1608`).

What running participant code needs, from the authorities:
- **MQ-015.** "Real execution runs in a locked environment with no network,
  scratch-only filesystem, CPU/GPU/RAM/VRAM/wall-clock/step/output limits,
  immutable image/dependency identity, process isolation, and redacted logs."
  Arbitrary participant code belongs only to a later `ConstructionProgram`
  threat model (`docs/context/MASTER_OPEN_DESIGN_QUESTIONS.md:379-381`).
- **Admission §3.** Use disposable hosts, synthetic canaries and no
  production credentials. Runtime isolation is required for hostile
  executable tests. Pin and inspect the actual worker and transport. Stop on
  escape or answer-key exposure (`Challenge_Admission.md:163-167`). The
  families in scope at these levels are "hidden preprocessing/compilation,
  child processes, device/host memory, inference/solver hybrids, resource
  escapes and selective crash/retry abuse", plus construction-to-evaluator
  access and exfiltration (`:158-161`).
- **OWNER-GRAPHITE-TEST-WAVE-03.** "Isolation before participant code runs
  where real secrets live" is kept (line 110). Level 3 stays a declarative
  menu, with no participant code until the security owner accepts isolation
  (lines 69-70).

## 2. C-03, the isolated reconstruction worker

Sources: `Design_Specs/Isolated_Reconstruction_Worker.md`;
`.agent/tickets/C-03_isolated_reconstruction_worker.md`;
OWNER-C03-DEV-ISOLATION-01 (`.agent/DECISIONS.md:13532-13634`);
`carbon/reconstruction/worker/docker_runtime.py`;
`docs/development/c03_worker_profile_v1.json`; `scripts/dev/c03_worker*.sh`;
`tests/cpu/test_c03_worker_contract.py`;
`tests/service/test_c03_worker_service.py`.

### 2.1 What it enforces

`create_arguments` (`docker_runtime.py:452-602`) builds a fixed argument
list. It accepts no caller command, mount, option or device. Docker
configuration is then checked against it, and so are the kernel's own
readings (`inspect_effective_controls`, `:605-873`). Launch is refused on any
difference.

| Control | Set at | Checked at |
| --- | --- | --- |
| No network (`--network none`) | `:487-488` | `:663`; canary and DNS denial with a negative control, `test_c03_worker_service.py:588-667` |
| Private IPC and PID namespaces | `:489-493` | `:664-665` |
| Read-only root | `:494` | `:661` |
| Numeric non-root uid/gid 65532 | `:495-496`; `model.py:34-35` | `:658`; image user checked by `doctor`, `:366` |
| All capabilities dropped; no-new-privileges | `:497-500` | `:682-683`, `:688`; `/proc/1/status` `CapEff` 0, `NoNewPrivs` 1, `Seccomp` 2, `:764-773` |
| 256 tasks | `:501-502` | `:676`; `pids.max`, `:804`; probe, `test_c03_worker_service.py:463-467` |
| 4 GiB memory, no swap | `:503-506` | `:677-678`; `memory.max` and `memory.swap.max`, `:802-803`; probe with a negative control, `test_c03_worker_service.py:492-516` |
| Two CPUs: cpuset plus CFS quota | `:507-510` | `:679-680`; `cpu.max` and `cpuset.cpus.effective`, `:788-806` |
| 1,024 descriptors; no core dumps | `:511-514` | `:689-690` |
| No restart; bounded local log | `:515-524` | `:666-675` |
| Scratch tmpfs `noexec,nosuid,nodev`, 512 MiB and 8,192 inodes aggregate with `/dev/shm` | `:527-534` | `:695`; `df` readings, `:807-837`; probes, `test_c03_worker_service.py:469-490` |
| One read-only input bind mount and no other mounts | `:535-536` | `:640-643`, `:691-694` |
| Fixed environment and no host passthrough | `:537-554` | effective `Env` for the GPU profile, `:723-748` |
| Image by `sha256:` id, bound to source, wheel, lock, base, recipe and entrypoint | `:462`, `:555`; `scripts/dev/c03_worker_image.sh:16-45` | `doctor`, `:353-392`; `load_image_identity`, `:1091-1115` |
| Deadline watchdog, detached from the caller | `spawn_watchdog`, `:1054-1088` | blocked worker reaped, `test_c03_worker_service.py:670-693` |
| Exact-label stop, kill and remove, with absence confirmed | `remove_exact_container`, `:959-1051` | descendants do not survive, `test_c03_worker_service.py:696-727` |
| Evidence: digest of effective controls, cgroup counters | `:838-873`, `:876-955` | |

A GPU variant (`carbon.c03.cuda.development.v1`) attaches exactly one host
device by UUID through the NVIDIA runtime, with
`NVIDIA_DRIVER_CAPABILITIES=compute,utility` (`:557-601`). It checks the
device, environment and authority labels after create (`:707-763`). The v1
CPU profile itself records `"accelerators": "NOT_APPLICABLE"`
(`c03_worker_profile_v1.json:2`).

### 2.2 What it does not claim

- **Trust boundary.** The host administrator, kernel, Docker daemon and
  runtime, image build and Carbon supervisor are trusted. Root or daemon
  compromise, malicious image supply, kernel and runtime zero-days,
  microarchitectural side channels, physical attacks and compromised auditors
  are outside the demonstrated claim (`.agent/DECISIONS.md:13558-13567`;
  `Isolated_Reconstruction_Worker.md:96-103`; ticket `:54-58`).
- **Inputs.** Participant code, callbacks, plugins, commands and executables
  are not supported inputs (`DECISIONS.md:13563-13564`; ticket `:41-44`).
- **Loopback.** Private loopback remains, so the claim is external network
  and DNS denial, not zero socket syscalls. Docker's default seccomp filter
  and the host LSM are kept; the run records the observed LSM profile and
  claims none when it is absent (`Isolated_Reconstruction_Worker.md:58-63`;
  `docker_runtime.py:844`).
- **Executable memory.** JAX executable memory is not disabled; only scratch
  is `noexec` (`Isolated_Reconstruction_Worker.md:62-63`).
- **Rejected alternatives for that slice.** gVisor, microVMs, a second
  container engine, rootless-daemon claims and in-process "isolated" fallback
  were rejected (`DECISIONS.md:13620-13626`). `doctor` refuses a rootless
  daemon (`docker_runtime.py:347-352`).
- **Scope.** Only disposable public or synthetic workloads without
  production secrets (`DECISIONS.md:13615-13616`; ticket `:57-58`).

### 2.3 Maturity

- **Earned, in its exact scope:** SPECIFIED, IMPLEMENTED, TESTED.
  - Scope: public DEVELOPMENT, the exact image and runtime, Linux x86-64,
    cgroup v2.
  - Evidence: PR #149 (ticket `:97-104`) and the PR #151 hardening slice
    (`:125-131`).
- **Not earned:** SECURITY_QUALIFIED.
  - The ticket is `in_progress` (ticket `:4`). Its authority ceiling excludes
    security qualification (`:14-16`).
  - Still open: independent security review and broader MQ-015 acceptance
    (`:133-138`).
- **MQ-015.**
  - Globally `SECURITY_REVIEW_REQUIRED`
    (`MASTER_OPEN_DESIGN_QUESTIONS.md:385-392`).
  - This slice has scoped DEVELOPMENT implementation decisions only
    (`DECISIONS.md:13612-13618`).
  - No reviewer identity, findings, retest or security-owner acceptance is
    recorded (`MASTER_OPEN_DESIGN_QUESTIONS.md:389-392`).

## 3. The research sandbox carrier

`carbon/development_session/research_carrier.py`.

**Correction to the brief.** `run_script` (`:57-93`) does not run the miner's
Python under C-03's `create_arguments`.
- It sets `provenance="MINER_SELF_REPORTED"` and `miner_authored=True`
  (`:87`, `:91`), so `_run_locked` takes the miner lane (`:260`, `:412-435`).
- The miner lane builds its container with
  `carbon/development_session/miner_container.py:create_arguments`
  (`research_carrier.py:717-724`, `:792`).
- Only Carbon's own fixed programs in this carrier use C-03's
  `create_arguments`, watchdog and effective-control inspection
  (`:453-479`).

The miner-lane module says the two lanes share no argument builder, so it
cannot loosen the validator's settings (`miner_container.py:11-14`).

**What the miner lane keeps** (`miner_container.py:103-128`, checked by
`inspect_isolation`, `:189-235`):
- `--network none`, private IPC and PID, read-only root;
- uid 65532, all capabilities dropped, no-new-privileges;
- no core dumps, no restart, a bounded local log;
- exactly two mounts: `/input` read-only and `/scratch`.

**What it drops, by owner direction** (`miner_container.py:3-9`; 23
September 2026):
- No `--memory`, `--cpus`, `--cpuset-cpus`, `--pids-limit` or nofile limit.
  `/dev/shm` is sized to host memory (`:129-132`, `:182-186`).
- `/scratch` is a bind mount of a world-writable host directory
  (`prepare_scratch`, `:75-86`; `:138-142`). It has no size bound, and it is
  not `noexec`.
- The wall allowance is optional. With none, a controller-liveness reaper
  guards the container instead of a deadline (`research_carrier.py:257-269`,
  `:342-346`, `:796-805`).
- `inspect_isolation` records memory, CPU and PID limits as `None` and
  checks no kernel-side readings: no `/proc/1/status` seccomp or capability
  check and no cgroup files (`miner_container.py:227-235`; compare
  `docker_runtime.py:764-806`).

**The `BOOTSTRAP`** (`research_carrier.py:45-54`) copies `/input` into
`/scratch/workspace` and `execv`s the miner's program under
`python -I`. A GPU code cell attaches the host's installed device under a
device lease (`:289-303`, `:756-791`).

**Output trust.**
- Every result carries `provenance: MINER_SELF_REPORTED`,
  `scientific_qualification: false` and `official_eligible: false`
  (`:905-914`). It is never scored.
- Collection copies regular files only and refuses links and special files
  (`miner_container.py:268-307`). It has no size or count limit.
- The last 64 KiB of stdout and of stderr are kept (`research_carrier.py:935`).

**Tests.** `tests/service/test_cw1_research_carrier.py:195-257` asserts the
unlimited lane: 600 MiB of output, no wall allowance, no memory or CPU cap,
no network and a read-only root. `:17-105` asserts the public-only stage,
the absent Docker socket and absent API keys, and a reaped background child.

**What this means for Levels 4-5.** The miner lane is the right shape for a
miner's own machine, where the miner bears the cost. For participant code run
by Graphite on a Carbon host it removes the limits that C-03 enforces: CPU,
memory, tasks, descriptors, scratch size, `noexec` scratch and a mandatory
deadline. A Graphite hostile-code lane would need C-03's limits, not the
miner lane's.

## 4. Graphite's pods

Sources: `carbon/agent_campaign/graphite/pods.py`, `pod_phase.py`,
`scripts/dev/exam_design/runpod/bootstrap.py`,
`scripts/dev/exam_design/runpod/operator_compute/runpod.py`,
`scripts/dev/exam_design/runpod/pod_control.py`.

### 4.1 What runs on a pod today

- **The lifecycle.** Carbon's runner launches one pod per proposal, on
  Carbon's operator account only, and terminates it and verifies its absence
  whatever the outcome (`pods.py:1-26`, `:556-563`).
- **The image.** It is pinned by digest (`pod_control.py:291-294`).
- **The entrypoint.** The bootstrap becomes the container's entrypoint
  through `dockerEntrypoint` (`pods.py:445`; `runpod.py:362-367`).
- **The bootstrap's work.** It fetches every shipped file at a pushed commit
  and refuses any whose sha256 differs (`bootstrap.py:243-259`). It installs
  hash-locked wheel overlays (`:203-233`). Then it runs the phase as a child
  (`:300-314`).
- **The phase.** `graphite_practice` compiles a declarative strategy with
  Carbon's compiler. It refuses to run unless the staged files and program
  equal what Carbon pinned. It then runs Carbon's fixed `GPU_PROGRAM` under a
  wall timeout (`pod_phase.py:9-27`, `:96-115`).
- **No participant executable runs on a pod today.**
- **The provider is the only containment.** The bootstrap describes itself as
  "containment from the provider's runtime ... not validator isolation
  acceptance" (`bootstrap.py:3-6`). Carbon sets no namespace, uid change,
  seccomp profile, cgroup or network rule inside the pod.

### 4.2 The provider-credential item (from the Carbon Validator)

The Carbon Validator's open security item, recorded in
OWNER-GRAPHITE-TEST-WAVE-03: on a pod, the provider credential RunPod places
in the container is reachable by a program running under the same uid as
Carbon's bootstrap.

- This assessment checked the item against the code and confirmed it. The
  line-by-line verification, the read path and the exposure detail are held
  by the owner, not in this public repository, until a fix is accepted.
- The credential's injection and scope are asserted in the repository but
  not verified, so the impact depends on its real scope.
- **Today's exposure is to Carbon's own code.** The only program on a pod is
  Carbon's fixed one, run from Carbon's compiled recipe (§4.1). The exposure
  becomes real when participant code runs on a pod, which is exactly
  Levels 4-5.
- Candidate fixes are named in §6.

## 5. Have versus need

Size legend:
- **S:** one bounded change in existing code with tests; no new trust
  boundary.
- **M:** several modules, or a new profile, with service tests on a real host
  or a disposable pod.
- **L:** a new boundary, mechanism or external dependency, or a design that
  needs a decision before it can be built.

"Local" is the C-03 Carbon lane (`docker_runtime.py`). Where the carrier's
miner lane differs, the row says so. "Pod" is Graphite's RunPod path.

| Dimension | Path | Have (where) | Gap for Levels 4-5 | Size | Why |
| --- | --- | --- | --- | --- | --- |
| Compute | Local | Two CPUs, cpuset plus CFS quota, kernel-checked (`docker_runtime.py:507-510`, `:788-806`). Miner lane: none (`miner_container.py:129-130`) | Ceilings are engineering DEVELOPMENT values, not set for hostile load. A Graphite lane must use C-03's limits, not the miner lane's | S | The mechanism and its checks exist; only a profile choice and a guard are needed |
| Compute | Pod | Provider's allocation; thread-count hints only (`bootstrap.py:289-292`) | No per-program CPU bound in the pod; a program can starve the bootstrap's server and watchdog | M | Cgroups are not normally delegated inside a provider container; `nice` and `RLIMIT_CPU` are partial |
| Memory | Local | 4 GiB, swap 0, kernel-checked; OOM evidence from `memory.events` (`:503-506`, `:802-803`, `:940-945`) | No VRAM bound on the GPU variant (see GPU) | S | The host-memory side exists and is tested |
| Memory | Pod | Provider's container limit, shared by bootstrap and program | A program OOM can take the bootstrap with it, losing its status, results server and self-termination | M | `RLIMIT_AS` conflicts with CUDA's virtual reservations; a real bound needs a cgroup or a separate container |
| Filesystem | Local | Read-only root; read-only input; `noexec` tmpfs scratch with size and inode bounds; no other mounts (`:494`, `:527-536`, `:640-643`) | None for containment. Miner lane: unbounded, executable host-disk scratch (`miner_container.py:75-86`, `:138-142`) | S | C-03 already has it; only the lane choice matters |
| Filesystem | Pod | Verified code and overlays written to `/tmp/carbon` and `/tmp/overlay`; results in `/tmp/out` (`bootstrap.py:60`, `:256-259`) | All are writable by the program (same uid). It can rewrite Carbon's verified code after verification and anything in the results directory | M | Needs a separate uid or a read-only layer for code, and a results directory the program cannot write except through a defined channel |
| Network | Local | `--network none`, checked; external and DNS denial proven with a negative control (`:487-488`, `:663`; `test_c03_worker_service.py:588-667`) | Loopback remains by design (`Isolated_Reconstruction_Worker.md:58-61`) | S | Matches MQ-015's "no network" for external access |
| Network | Pod | Full egress, used to fetch code and wheels; inbound port 8000 through the provider proxy, gated by token (`bootstrap.py:162-197`, `:238`) | The program has the same egress: any readable secret or result can leave the pod | L | Removing egress after the fetch needs a network namespace (privileged) or a provider-level control |
| Process | Local | Private PID namespace, 256 tasks, no capabilities, no-new-privileges, default seccomp checked as mode 2 (`:489-502`, `:764-773`); descendants removed (`test_c03_worker_service.py:696-727`). Miner lane: no task or descriptor limits | Shares the host kernel through runc with Docker's default seccomp. Kernel and runtime zero-days are outside the claim. A stronger boundary (gVisor, microVM) was rejected for that slice (`DECISIONS.md:13620-13622`) | L | Choosing the boundary for hostile code is the security owner's decision, and may reopen a rejected alternative |
| Process | Pod | None of Carbon's own; the program is a plain child in the bootstrap's PID namespace | The program shares the bootstrap's uid and PID namespace, so it can interfere with the bootstrap | L | Needs a separate uid, PID namespace or container; each depends on privileges the provider may not grant |
| Time (wall and CPU) | Local | Fixed 600 s deadline (`model.py:17`); detached watchdog (`:1054-1088`); exact removal (`:959-1051`). CPU time is bounded by quota times wall. Miner lane: wall optional, reaper otherwise (`research_carrier.py:257-269`, `:796-805`) | Graphite runs must always carry a deadline | S | Exists in C-03; the miner lane's optional deadline is the only difference |
| Time (wall and CPU) | Pod | Phase program timeout (`pod_phase.py:113`); bootstrap deadline watchdog (`bootstrap.py:112-116`, deadline from `pods.py:366`); Carbon-side wait and terminate (`pods.py:514-530`, `:556-563`) | `subprocess.run`'s timeout kills only the direct child, so a program's own descendants survive until the pod ends. The bootstrap's runner child has no timeout (`bootstrap.py:300-314`). The in-pod backstop needs the credential | M | Process-group kill is small; removing the backstop's need for the credential is not (§6) |
| Separate uid | Local | Worker uid 65532, distinct from the controller's host user (`:495-496`, `:658`). No user-namespace remap; rootless refused (`:347-352`) | All runs share uid 65532. An escape lands as host uid 65532 | M | Per-run uids or a userns-remapped daemon is a host and daemon change that needs review |
| Separate uid | Pod | None: bootstrap and program share uid 65532 (receipt `:22`) | This is the provider-credential item (§4.2) | M | Needs a privileged start or a different execution host (§6) |
| Images (pinned, immutable) | Local | Dispatch by `sha256:` id; identity binds source tree, wheel, lock, base, recipe and entrypoint (`:353-392`; `c03_worker_image.sh:16-45`); read-only root | Participant code arrives as input, not image. Its dependencies need their own pinned identity; MQ-015 forbids arbitrary dependencies (`MASTER_OPEN_DESIGN_QUESTIONS.md:373-374`) | S | The pinning mechanism exists. A dependency policy for participant code is an owner decision; build work after it is small |
| Images (pinned, immutable) | Pod | Image by digest (`pod_control.py:291-294`); code by per-file sha256 at a commit (`bootstrap.py:243-259`); hash-locked wheels (`:203-209`) | The verified code and overlays land in writable `/tmp`; they are not immutable once the program runs | M | Same fix as the pod filesystem row |
| Secrets and credentials | Local | Fixed environment, no host passthrough, no daemon socket or extra mounts (`:537-554`, `:640-643`); never-received list (`DECISIONS.md:13604-13610`); tested (`test_cw1_research_carrier.py:41`, `:52`) | Levels 4-5 need canary secrets in tests that probe for them | S | The boundary exists; this is test work |
| Secrets and credentials | Pod | The child's environment omits the credential (`bootstrap.py:272-276`) | The credential stays reachable by the program (§4.2) | M | See §6: one small hardening step and one structural change |
| GPU access | Local | One device by UUID, NVIDIA runtime, `compute,utility`, checked after create (`:557-601`, `:707-763`); host device lease (`research_carrier.py:441-450`, `:756-791`) | No VRAM limit; no device memory clearing between runs; the NVIDIA driver is kernel attack surface. "Permitted hardware beyond the CPU worker envelope" is human-reserved (GRAPHITE-ADMISSION-01 ticket `:112-114`) | L | GPU isolation for hostile code is a security-owner decision; MIG or a dedicated host is new infrastructure |
| GPU access | Pod | Whole A40 through the provider | Same as local, plus residue and driver state managed by the provider | L | Outside Carbon's control |
| Output channel and trust | Local | Bounded exporter stream; decoded and validated only after exact cleanup; association by C-02 semantics (`research_carrier.py:480-499`, `:531-535`; `Isolated_Reconstruction_Worker.md:42-47`). Miner lane: regular files only, unbounded, self-reported (`miner_container.py:268-307`; `research_carrier.py:905-914`) | Level 4 needs a constrained inference interface and Level 5 an independently isolated inference stage. Neither exists | L | New interfaces and a separate stage, designed against the grader boundary ("Carbon can widen what participants are allowed to discover without changing who controls the grade") |
| Output channel and trust | Pod | Files served by token; sha256 listed by the same pod; Carbon rebuilds and scores on its own host (`bootstrap.py:130-159`; `pods.py:532-554`; `pod_phase.py:26-27`) | The listing protects transport only: the program writes the same directory and can forge `built.json` or `DONE.json` | M | Carbon already rebuilds independently; it must also treat every pod file as untrusted at Levels 4-5 and stop reading pod-side status as fact |
| Logging and evidence | Local | Effective-controls digest and cgroup observations (`:838-873`, `:876-955`); 1 MiB local log; miner lane keeps 64 KiB of stdout and stderr (`research_carrier.py:935`) | No syscall or audit record of escape attempts; high-water marks "UNAVAILABLE_WITHOUT_CONTINUOUS_SAMPLING" (`:954`) | M | Needs host-side auditing and sampling outside the container |
| Logging and evidence | Pod | `phase.log` written by the program into the results directory (`bootstrap.py:299-314`); bootstrap status in memory; operator compute store records intent, ownership and termination | Every in-pod log is under the program's control | M | Trustworthy evidence must come from outside the pod |
| Teardown and cleanup | Local | Exact-label stop, kill and remove, absence confirmed, quarantine on uncertainty (`:959-1051`); miner lane the same plus a `ps` check (`research_carrier.py:836-847`) | Miner-lane scratch persists on host disk inside the operation folder | S | Bounded cleanup policy |
| Teardown and cleanup | Pod | Carbon terminates and verifies absence (`pods.py:15-16`, `:556-563`); the pod is disposable (container disk only) | The in-pod backstop uses the credential | S | The outside path exists; the backstop question is in §6 |

## 6. The provider-credential gap: candidate fixes

None of these has been built or tested. Any of them closes the item only when
the security owner accepts it. The mechanism detail behind each is held with
§4.2's detail.

| # | Candidate | Size | Security owner |
| --- | --- | --- | --- |
| K1 | Harden the bootstrap process so a same-uid program cannot read its state; prove it on a disposable pod with a Carbon-authored canary program | S | Implementation is engineering hardening; accepting it as the fix is the security owner's |
| K3 | Restart the bootstrap at start without the credential or the probe token in its environment, passing the token by another channel; pairs with K4 and K1 | S-M | Engineering; acceptance is the security owner's |
| K4 | Move self-termination out of the pod: an operator-side watchdog, like C-03's detached watchdog, terminates by deadline, so the pod no longer needs the credential; needs a detached operator-side reaper for a lost operator host | M | Engineering for the watchdog; the security owner decides whether outside termination alone is acceptable |
| K5 | Test whether the provider's injection can be suppressed from the create request, or ask the provider not to inject it | S to try | Engineering to test; the security owner accepts the evidence |
| K6 | Run the program under a separate uid (start privileged, then drop the program to an unprivileged uid) | M | Yes: it changes the pod's trust boundary |
| K7 | Process-visibility isolation for the program (a separate PID namespace or equivalent); needs privileges a provider container may not grant | L | Yes |
| K8 | Do not run participant code on provider pods; run it on Carbon-controlled hosts through a C-03-based lane, including its GPU variant | M-L | Yes: chooses where hostile code may run |

Removing the credential from the bootstrap's own environment variables after
start is not sufficient on its own and is not listed.

## 7. Security-owner reservations and open items

- **OWNER-GRAPHITE-ATTACKER-01 §1.**
  - Higher-level families are declared seams and reported `NOT_RUN`. These
    include participant code, child processes and solver hybrids.
  - Executing hostile code needs the security owner's isolation decision,
    which is reserved and not built
    (`.agent/decisions/2026-10-04-OWNER-GRAPHITE-ATTACKER-01.md:13-14`).
- **GRAPHITE-ATTACKER-AT-C, "Not decided here."** Isolation for hostile code
  is reserved to the security owner
  (`.agent/decisions/2026-10-04-GRAPHITE-ATTACKER-AT-C.md:182-186`).
- **MQ-015.**
  - Globally `SECURITY_REVIEW_REQUIRED`
    (`MASTER_OPEN_DESIGN_QUESTIONS.md:385-392`).
  - Arbitrary participant code belongs to a later `ConstructionProgram` threat
    model that does not exist yet (`:381`).
  - Owner: security, protocol and Physics/SciML. Proof required: a formal
    threat model, sandbox review and abuse tests (`:383-384`).
- **GRAPHITE-ADMISSION-01, human-reserved (each fails closed).**
  - "Isolation acceptance".
  - "Reconstruction tolerances and permitted hardware beyond the CPU worker
    envelope".
  - Approval of the attacker model.
  - Source: `.agent/tickets/GRAPHITE-ADMISSION-01_graphite_admission_testing.md:104-115`.
- **Attack adapter seams** (`carbon/agent_campaign/attack/adapters/battery.py:1545-1609`).
  - `level_3_numerical_routines`, `level_4_constrained_inference_export` and
    `level_5_custom_inference` each carry "security owner: isolation for
    executing participant code" (`:1586-1608`).
  - `pod_timeout_typing` is an open owner question: is a pod timeout
    `FAILED_INFRA` or `CANDIDATE_FAILED`? (`:1554-1563`). It is the technical
    owner's, not the security owner's. It matters here because a hostile
    program can force a timeout.
- **OWNER-GRAPHITE-TEST-WAVE-03** (branch record, §1 and §3).
  - Level 3 is a declarative menu only until the security owner accepts
    isolation (lines 69-70).
  - This assessment is brought forward, but acceptance is not granted (lines
    95-104).
  - "Isolation before participant code runs where real secrets live" is kept
    (line 110).
- **The Carbon Validator's open security item.** The pod's provider
  credential is reachable by the program's uid (§4.2). It is still open; this document proposes
  fixes and resolves nothing.

## 8. Recommended order

Each step is marked **[Engineering]** (buildable now, claiming nothing) or
**[Security owner]** (a decision or acceptance only the security owner can
give).

1. **[Security owner]** Decide where Levels 4-5 hostile code may run at all.
   The choices are Carbon-controlled hosts through C-03 (K8), provider pods,
   or both. This decides how much of §6 is needed. Until then, no participant
   code runs on either path.
2. **[Engineering]** Pod credential hardening that claims nothing: K1, then
   K3 with K4, and the K5 test.
   - Prove each on a disposable pod with a Carbon-authored canary program
     that tries to reach the credential and to interfere with the bootstrap.
   - A pod run needs its own grant; this record creates none.
   - Separately, record the key's actual scope for the security owner.
3. **[Engineering]** Kill the whole process group on timeout, in `bootstrap.py`
   and `pod_phase.py`. Treat every pod-side file and status as untrusted
   (§5, output row).
4. **[Engineering]** Define a "Graphite internal hostile-code" lane on C-03:
   - the Carbon lane's limits, mandatory deadline and kernel-side checks;
   - an explicit refusal of the unlimited miner lane for Graphite runs.
   This is a profile and a guard over existing code.
5. **[Engineering]** Extend the C-03 service probes into a Level 4-5 canary
   battery, written by Carbon, as the existing `_probe_arguments` tests are.
   - Probes: descendants and process-group escape, device and host memory,
     resource exhaustion, scratch exec, loopback use, secret canaries.
   - Measure, and claim no boundary.
6. **[Security owner]** Write the participant-code (`ConstructionProgram`)
   threat model required by MQ-015 (`:381`, `:384`). Choose the execution
   boundary: runc with default seccomp as today, a custom seccomp or LSM
   profile, or a stronger boundary rejected for the C-03 slice (gVisor,
   microVM; `DECISIONS.md:13620-13622`).
7. **[Security owner]** Decide GPU use for hostile code: VRAM bounds, device
   memory clearing between runs, MIG or dedicated hosts, and permitted
   hardware (GRAPHITE-ADMISSION-01 reserved value).
8. **[Engineering]** Design, then build, the Level 4 constrained inference
   interface and the Level 5 independently isolated inference stage.
   - The inference stage runs in its own container.
   - It holds no construction state and reaches no grader material.
   - The grader stays Carbon's.
   - Building follows the threat model in step 6.
9. **[Engineering]** Host-side evidence: auditing and continuous sampling
   outside the container, so escape attempts leave a record the program cannot
   edit.
10. **[Security owner]** Independent review of the chosen lane, retest of
    confirmed fixes, and isolation acceptance (GRAPHITE-ADMISSION-01). Only
    then may Graphite's Attacker run participant code at Levels 3-5, within a
    grant.

## 9. Method and limits

- Read at `origin/main` `992d046b6`. The TEST-WAVE-03 record was read at
  `origin/claude/graphite-test-wave-03` `3b267bff4`.
- Nothing was executed. No pod, container, Docker command or test run was
  started for this assessment.
- Provider behaviour was not verified: injection and scope of the
  credential, the process layout, kernel settings, capabilities, delegated
  cgroups and egress controls. Each
  such statement above is marked as unverified.
- Sizes are engineering estimates for planning. They are not commitments,
  budgets or acceptance criteria.
