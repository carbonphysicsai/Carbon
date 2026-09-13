# C-03 — Isolated reconstruction worker

**Wave:** C1 real scientific execution foundations
**Status:** `in_progress`
**Current slice:** PR #151 completed the selected prerequisite-hardening
continuation; broader protected/security/production requirements remain open
**Depends on:** C-01; B-02B; B-02C; A4
**Adapter prerequisite:** C-02's merged DEVELOPMENT adapter capability is
satisfied by PR #148; full C-02 closure remains open and non-blocking for this
slice.
**Selection authority:** `OWNER-C03-DEV-ISOLATION-01`, followed by
`OWNER-C1-BURGERS-ALPHA-01`'s C-03 prerequisite-hardening selection
**Primary Hub map_ref:** `WAVE-C/C-03`
**Authority ceiling:** engineering implementation and controlled public
DEVELOPMENT tests only; no protected execution, security qualification,
scientific qualification, production, network, reward, or LIVE authority

## Selected slice

Wrap the merged C-02 adapter in one pinned Docker/OCI worker on Linux x86-64,
cgroup v2, and CPU only. The controller stages a single immutable public TRAIN
snapshot, records C-01-owned launch intent and a non-resetting 600-second
deadline, verifies effective controls before authorizing training, exports a
bounded provisional artifact, terminates the entire container, and only then
validates and associates the snapshot. The miner interface is unchanged.

The exact profile is `carbon.c03.linux-x86_64-cpu.development.v1`, recorded in
`docs/development/c03_worker_profile_v1.json`. It permits one worker, two
eligible logical CPUs with cpuset and aggregate quota, 4 GiB memory with no
swap, 256 kernel tasks, 512 MiB aggregate scratch with 8,192 inodes, 128 MiB
input and output/expanded limits, 1,024 output files, 1 MiB control and
diagnostic limits, 1,024 file descriptors, disabled core dumps, five seconds
grace and thirty seconds cleanup confirmation. Exact lower-cap test subprofiles
are test-only and not admission choices.

## Threat and trust boundary

The development host administrator, Linux kernel, Docker daemon/runtime,
image-build path and Carbon supervisor are trusted. Declarative parameters,
archives, checkpoints, worker messages and artifacts are untrusted at parsing
and association. A malformed request or native numerical defect may control
the worker. The supported interface never accepts arbitrary participant code,
callbacks, plugins, import paths, shell fragments, commands, devices, mounts,
security options or daemon access.

The worker is numeric non-root UID/GID 65532, read-only-root, capability-free,
no-new-privileges, default-seccomp, private PID/IPC, `network=none`,
`restart=no`, and receives one read-only attempt input plus bounded disposable
scratch. It receives no daemon socket, repository/home/cache mount, host
credential, device, master entropy, EVAL/STRESS case, evaluation target,
reference answer, validator/signing key, chain credential or auditor secret.
TRAIN solution arrays remain permitted training labels.

Root/daemon compromise, malicious image supply, kernel/container zero-days,
microarchitectural side channels, physical attacks, compromised auditors,
confidential-host defense and protected-exam administrator collusion remain
outside the claim. The slice is eligible only for disposable public/synthetic
work on authorized development/CI machines without production secrets.
MQ-015 therefore has scoped DEVELOPMENT implementation decisions, while
implementation evidence and broader security acceptance remain open. Global
MQ-015 is not resolved and `SECURITY_QUALIFIED` is not earned.

## Identity, lifecycle and failure rules

- C-01 owns the attempt journal. C-03 adds an exact image, worker-policy,
  stage, replica, launch nonce/container and deadline binding; container and
  policy digests are execution provenance, not Strategy/scientific/reward
  identity.
- Intent is durable before Docker create. One exact execution ID has one create
  effect. A lost create response reconciles by deterministic name and exact
  label; an exact associated replay validates the retained snapshot and causes
  no new pack, seed, replica, partial or reward effect.
- The external watchdog owns the fixed deadline. Cooperative Python
  cancellation is not the kill boundary. Cleanup targets one exact recorded
  container, never a global prune.
- Output streamed through the fixed capped exporter while alive is provisional.
  Association occurs only after the worker and descendants are gone, intake is
  closed, and the controller-owned immutable snapshot passes C-02
  receipt/artifact/checkpoint identity,
  structure, dtype, shape, counter and finite-value validation.
- Cleanup uncertainty quarantines only the affected execution capacity and
  yields no successful reconstruction. Infrastructure failures remain distinct
  from physics/scientific failures. Cancelled/failed repeats stay retained and
  are not silently replenished.

## Development acceptance for this slice

- [x] C-02's current lab/Foundax source, exact profile/lock facts and real
      adapter entry points are used without a second training loop.
- [x] The grouped threat/resource/runtime decision is recorded; missing v0.2
      intake remains deferred and unverified.
- [x] Controller staging, durable launch association, exact replay,
      create-response-loss recovery, bounded export, post-exit validation,
      cancellation, reconciliation and quarantine are implemented.
- [x] The image recipe and worker doctor use exact source/wheel/lock/base/
      recipe/entrypoint/image identities and reject unsupported capabilities.
- [x] The required Linux service-backed lane passed the real lab FNO,
      Foundax 512-point, resume/conformance, enforcement, hostile-probe and
      recovery tests for accepted head
      `ef4d5e336c942b7ff40856fcfee03f522ef2d1d5` in run `34770761721`.
- [x] PR #149 normally merged that exact accepted worker slice as
      `d94a22bb3c09089e01402db9e7ebf6eb3c662966`; image/config
      `sha256:dae4717ae00d3174b8644159934eb4edbe94c0ad125549f6ade570a6f4c7e630`
      remains historical evidence for that source only.

## Selected prerequisite-hardening continuation

`OWNER-C1-BURGERS-ALPHA-01` retained C-03 long enough to disposition four
narrow concerns before C-04 consumed the worker:

- enforce Docker CLI response caps while bytes are received, rather than
  after an unbounded `capture_output` allocation;
- validate worker artifacts in a separate controller-owned process with fixed
  CPU, address-space, descriptor, core-dump and wall limits;
- retain cgroup memory/CPU/PID observations, bounded output observations and
  honest unavailable/high-water notation on success and failure; and
- prove the same-boot controller deadline is monotonic, persist cross-restart
  host/boot/deadline identity, and keep cleanup uncertainty quarantined.

C-01 admits a successor only after its distinct `RETRYABLE_INFRA` terminal.
C-03 deliberately uses source-owned `FAILED_INFRA` after worker execution, so
policy exhaustion, deadline, malformed output or unknown consumption cannot
mint another attempt, replica or resource budget. Exit status alone does not
establish OOM; retained cgroup `memory.events` is the cause evidence when it is
available. PR #151 accepted exact head
`abc490495528d8960ff8c66f50feabeae3affd34` in required RUNTIME_FULL run
`34778563403` and normally merged it as
`2d5872aff89ca7bef3e3f062b293aeefe17769aa`. The run passed the required
Linux worker service lane, canonical environment, clean development image,
Hub validation and Merge gate. That closes only this prerequisite-hardening
slice and selected C-04; it does not close full C-03.

## Still open

Full C-02 production closure, a production reconstruction-repeat policy,
protected inputs, production backend selection, independent security review,
broader MQ-015 acceptance, scientific truth/thresholds, official grading,
real archive acknowledgement, reward, network and LIVE authority remain open.
The absent `carbon_jax_research` v0.2 file-set digest
`sha256:1e539a856a35701ec7ff85880ba9e5a84eaf13970a6212e56f13a32b9d65955e`
remains `NOT VERIFIED`; v0.1 is not substituted. Foundax remains recorded
conservatively as EPL-2.0 because shipped source/wheel license bytes conflict
with package metadata; no commercial permission is granted here.
