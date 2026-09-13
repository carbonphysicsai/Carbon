# Isolated Reconstruction Worker — DEVELOPMENT profile

**Decision:** `OWNER-C03-DEV-ISOLATION-01`
**Profile:** `carbon.c03.linux-x86_64-cpu.development.v1`
**Scope:** public/synthetic DEVELOPMENT execution only

## Flow

```text
verified B-02B plan + B-02C resource/replica refs + admitted C-01 attempt
  -> controller copies and binds public TRAIN/plan/DerivedSeed bytes
  -> C-01-owned worker journal fixes image, policy, container and deadline
  -> Docker creates numeric non-root, read-only, network-none CPU worker
  -> controller inspects Docker config, process status and cgroup v2 files
  -> controller releases the fixed entry point to call C-02 reconstruct()
  -> bounded provisional output is copied while worker scratch exists
  -> exact container/cgroup and descendants are removed
  -> immutable snapshot is validated with C-02 semantics
  -> development partial-work association, or typed failure/quarantine
```

No new miner request, reveal, fee or submission action is introduced. The
container identifier and execution-policy digest are provenance for an existing
attempt/replica, not a new Strategy, candidate, Challenge, pack or reward
identity.

## Controller and worker division

The trusted controller resolves identity-to-location mappings and accepts no
caller path, mount, image, device, Docker option, command, import or callable.
It snapshots permitted input through one open file descriptor, rejects links,
special files, traversal, duplicate JSON, excessive archive members/expansion
and identity mismatches, then mounts only that attempt directory read-only.

The worker uses a fixed image entry point and re-decodes the canonical
construction plan. It calls the existing C-02 reconstruction service directly.
A requested continuation test first seals the ordinary partial C-02 checkpoint
and resumes it under the same attempt, plan, TRAIN bytes and DerivedSeed. There
is no adaptive smaller model, shorter successful plan, distributed JAX path,
download, observer callback or general inference service.

Output is copied to controller-owned staging before tmpfs disappears, without
following links or extracting worker archives. The copied bytes are immutable
and provisional. Only after exact cleanup does the controller validate the
artifact, checkpoint, source/environment/scaling/data/randomness/request
relationships, counters, finite arrays, shapes and dtypes. A worker exit code,
message, digest or label cannot authorize association alone.

## Isolation mechanism

The selected Linux/amd64 Docker profile enforces the values in
`docs/development/c03_worker_profile_v1.json`. Docker configuration and live
kernel observations must agree: CFS quota and cpuset, `memory.max`,
`memory.swap.max`, `pids.max`, scratch size/inodes, capabilities,
no-new-privileges and seccomp mode are all inspected before the authorization
file is written. Missing or downgraded support refuses launch.

`network=none` excludes external interfaces and DNS but retains private
loopback. The claim is therefore external network denial, not zero socket
syscalls. The default Docker seccomp filter and available host LSM remain in
force; the run records the observed LSM profile and does not claim one when it
is absent or unreported. JAX executable memory is not disabled, while installed
code/root/input are immutable and scratch is filesystem `noexec`.

## Deadline, restart and replay

The C-01-owned SQLite record is committed before Docker create. A transaction
grants one create effect. The container name and launch label are deterministic,
so create-success/response-loss reconciles the same resource. The recorded
wall deadline never resets. A detached trusted watchdog exists before work is
released and performs exact-label cleanup at the deadline. Docker restart is
disabled.

An exact replay after association revalidates the retained immutable snapshot
and makes no new Docker, seed, replica or partial-work effect. Changed request
bytes under the same execution identity conflict. Nonterminal restart state is
reported by the operator command and must be reconciled to the same exact
container. Unprovable cleanup quarantines only that slot and produces no
successful output.

## Image identity

`.devcontainer/Dockerfile.reconstruction-worker` builds Carbon's wheel under
the existing pinned Ubuntu/Python 3.11 and `uv.lock` science-JAX set. The build
script binds the Git archive, wheel, lock, base image, recipe and entrypoint,
then records the resulting Docker config/image digest in a controller-side
manifest. Dispatch uses that `sha256:` image ID, never the convenience tag.
Keeping the completed image identity outside the image avoids a circular
manifest.

At the selected baseline the science set is JAX/JAXlib 0.10.2, NumPy 2.4.6,
SciPy 1.17.1, Optax 0.2.8, Chex 0.1.92, Equinox 0.13.8, Einops 0.8.2, Foundax
0.2.0 and PyYAML 6.0.3. Build and doctor verify the repository lock and image
facts rather than resolving a new set.

## Claim boundary

This design implements and tests containment and correct association under the
named trusted-host model. It is not protection from host root or daemon
compromise, image-build malice, kernel/runtime zero-days, side channels,
physical attacks or compromised auditors. It does not qualify protected exams,
scientific correctness, production availability, commercial rights, archives,
rewards, network use or LIVE operation.
