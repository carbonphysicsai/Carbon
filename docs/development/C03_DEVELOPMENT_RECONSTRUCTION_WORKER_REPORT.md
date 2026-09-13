# C-03 bounded DEVELOPMENT worker report

## Owner summary

Carbon now has a bounded parent/worker path that can execute the canonical
C-02 JAX adapter on a public synthetic TRAIN fixture in one CPU-only Linux
Docker container. The parent, not the worker, owns the C-01 attempt, validates
the exact plan/archive/randomness/replica/resource/image/profile bindings, and
accepts only a validated frozen reconstruction artifact and target-free
prediction as retained partial work. This adds no evaluator, score, reference
answer, evaluation-pack sharing, publication, reward, production or LIVE path.

The container profile enforces a read-only root and input, private tmpfs
scratch/output, non-root UID/GID, no Docker network, no capabilities,
no-new-privileges, one CPU, 2 GiB RAM with no swap, a 120-second parent wall
deadline, 256 PIDs, 512 MiB scratch, 256 MiB output and 256 file descriptors.
Docker also bounds its local log to one 16 KiB file; the parent retains only a
bounded byte count and digest. The 128-thread setting configures the pinned JAX runtime; the PID cgroup remains
the operating-system boundary. Docker supplies CPU quota, but the profile does
not yet supply a separate CPU-time kill or authoritative per-attempt CPU
accounting. That consumption remains unknown rather than zero.

## Source and identity

- Baseline: `83186be004a4087b27b07278da490dad36785acb` (merged PR #148).
- Canonical reconstruction provenance: `carbon_jax_lab`, including the exact
  Foundax profile already in Carbon.
- Optional `carbon_jax_research` v0.2: absent and unverified; no digest or
  equivalence is asserted, and it is not a worker blocker.
- Profile: `carbon_c03_cpu_development_v1`, scope
  `UNQUALIFIED_PUBLIC_DEVELOPMENT`, security state
  `REVIEWABLE_NOT_SECURITY_ACCEPTED`.
- The exact source revision and immutable built image digest are bound at build,
  C-01 admission, parent request, container labels/environment and result
  validation.

The worker request has no participant command, module/import, executable
checkpoint, dependency, URI or filesystem-path field. The container receives
only a private seed for its already-bound reconstruction replica, the compiled
plan, a public TRAIN archive and target-free prediction arrays. It receives no
host repository mount, home, Docker socket, credentials, signing keys, master
entropy, protected EVAL fixture or reference answer.

## Lifecycle and failure behavior

Before the C-01 claim, the parent validates every source-owned binding, stages
the input and inspects the created container's effective envelope. A known
pre-claim failure removes that unclaimed container and staging directory, so it
does not consume an attempt or force a false reconciliation. After the exact
claim, the parent records start intent before `docker start`; an ambiguous
owner restart therefore enters C-01 reconciliation and cannot silently
redispatch.

Cancellation kills the container and descendants, records a terminal
non-scientific C-01 cancellation and grants no successor. Wall expiry, OOM,
worker failure, invalid output and cleanup failure remain typed operational
failures, not physics results. They use the terminal C-01 infrastructure path,
not the separately owned retryable-infrastructure transition. A new attempt
requires C-01's existing explicit successor policy.

Worker output is untrusted. The parent checks the bounded output tree and
symlinks, request and result schemas, actual sizes, exact attempt/replica and
all source/environment/profile digests, C-02 artifact manifest/checkpoint,
prediction dtype/shape/finiteness and content digest. Exact sealed reads are
idempotent; changed, late, malformed, partial, oversized or cross-attempt bytes
fail closed. A validated recovery associates an already-produced result to the
same attempt without another dispatch.

## Verification record

Local macOS checks provide model/interface evidence only; Docker is absent on
that host and no local isolation claim follows.

```text
Focused C-03/C-02/C-01 and dependency invariants: 47 passed
Full invariant lane: 212 passed
Science lane: 34 passed
Package/wheel/outside-tree lane: 88 passed
Hub newcomer tests: 9 passed
Hub validator unit tests: 81 passed
Hub validation and static/interactive route checks: passed
Focused Black 26.5.1 and Ruff 0.16.3: passed
```

The canonical Ubuntu/Docker service lane and RUNTIME_FULL acceptance are
pending for this candidate revision. Until they pass, network/filesystem and
resource enforcement, real three-replica reconstruction, cancellation and
restart are implemented claims awaiting service-backed acceptance—not earned
delivery evidence. The service test retains all three prospectively frozen
engineering replica outcomes without best-of-three selection and records
observed stage durations. Three replicas are not a production repeat count or
a reliable population-variance estimate. CPU-time, checkpoint load/save
subspans and accelerator consumption remain explicitly unavailable.

## Ticket reconciliation and remaining decision

C-02 remains `in_progress`: its validated adapter is the implementation
prerequisite for this worker, while the C-03 envelope is a completion
prerequisite for the wider C-02 execution contract. C-03 alone is selected for
this slice. Neither ticket is fabricated as complete.

MQ-015 security acceptance of this exact reviewable profile remains required
before protected workloads. The owner/security review must decide whether this
trusted-Docker-host boundary and its residual host-root/daemon, kernel escape,
side-channel and independent-integrity risks are acceptable, or require a
stronger runtime. No open-ended profile questionnaire is needed: the exact v1
profile is ready for that decision after canonical service evidence.

The next dependency-ready implementation work is C-04 protected reference
runtime only after C-03's applicable acceptance and the required MQ-015
security decision. C-02 protected/scientific integration and production repeat
policy also remain open. No later task is selected here.

## Delivery status

Implementation branch: `agent/c-03-development-reconstruction-worker`.
PR, accepted head, canonical run and merge identities are recorded here and in
the C-03 evidence record only after they actually exist and pass; queued or
local results are never relabeled as canonical acceptance.
