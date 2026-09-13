# C-03 CPU DEVELOPMENT reconstruction worker

## What exists

Carbon can dispatch the canonical C-02 JAX reconstruction adapter into one
non-root, disposable Linux Docker container for a public synthetic TRAIN
fixture. The parent binds the compiled Strategy plan, C-01 attempt, C-02
profile, immutable image/source identity, TRAIN archive, owner-derived replica
randomness, B-02C resource/replica identities and target-free prediction
request before claiming the exact attempt.

The worker is not an evaluator. It has no score, reference answer, protected
case, reward, publication, pack-sharing or production route. Successful output
is recorded only as C-01 reconstruction partial work so later owners retain
their gates.

## Exact profile and threat boundary

`carbon/reconstruction/profiles/c03_cpu_development_v1.json` is the sole
machine-readable profile. It pins the image definition and dependency lock and
uses the canonical `carbon_jax_lab` adapter already in Carbon. The optional
`carbon_jax_research` v0.2 archive is absent and unverified; no equivalence is
claimed and its absence does not block this worker.

The disposable host and Docker daemon are trusted. Participant influence is
limited to a previously compiled declarative Strategy and validated arrays;
participant imports, Python, checkpoints, commands, dependencies, paths and
URIs are not request fields. The worker receives only a read-only staged input
directory and fresh private tmpfs scratch/output mounts. It does not receive the
repository as a host mount, home, Docker socket, credentials, validator state,
signing material, master entropy, EVAL data or reference answers.

The development envelope is one linux/amd64 CPU, 2 GiB RAM with no swap, a
120-second wall deadline, 256 PIDs, at most 128 configured JAX threads, 512 MiB
scratch, 256 MiB output, 256 open files and 16 KiB retained diagnostic bytes.
The root filesystem is read-only; capabilities are dropped; no-new-privileges
is set; Docker networking is `none`; and Docker's local log is bounded to one
16 KiB file before the parent retains only a bounded byte count and digest.
These are finite engineering settings, not production limits or scientific
thresholds. Docker enforces CPU quota but
this profile has no separate CPU-time kill; host CPU-time consumption therefore
remains an unresolved observation while the worker's process CPU report is only
diagnostic.

Host root, daemon compromise, kernel/container escape, hardware side channels,
denial of the trusted host and independent execution integrity are residual
risks. MQ-015 security acceptance remains required before protected use.

## Lifecycle and validation

The parent stages immutable inputs and creates and inspects the constrained
container before atomically claiming the exact C-01 attempt. It records start
intent before starting. Cancellation and wall expiry kill the container and
descendants; cancellation is terminal and neither cancellation nor resource
exhaustion automatically grants a successor. An ambiguous owner restart enters
C-01 reconciliation and may associate already-produced, fully validated output
without redispatch.

Worker output is untrusted. The parent checks the output tree and symlinks,
actual bytes, exact request/attempt/replica/source/image/profile associations,
C-02 manifest and checkpoint, array dtype/shape/finiteness, and content
digests. A sealed replay is read-only and exact; changed, stale, duplicate,
late, malformed, oversized or cross-attempt bytes fail closed. Cleanup failure
is retained and never reported as isolation success.

## Operator commands

Build only from a clean exact checkout:

```bash
.venv/bin/python -c 'from pathlib import Path; from carbon.reconstruction import build_development_worker_image; print(build_development_worker_image(Path.cwd()))'
```

Run focused non-service tests:

```bash
.venv/bin/python -m pytest tests/cpu/test_c03_development_worker.py tests/cpu/test_c01_durable_execution.py -q
```

Run the canonical Docker evidence lane:

```bash
CARBON_REQUIRE_DOCKER_TESTS=1 CARBON_ARTIFACT_DIR=.carbon-artifacts \
  .venv/bin/python -m pytest tests/service/test_c03_worker_service.py -q -s
```

Cancellation uses `DevelopmentReconstructionWorker.execute(..., cancel=...)`.
After ambiguous owner restart, inspect the retained run directory and C-01
`RECONCILIATION_REQUIRED` state; use `recover_completed` only for the same
dispatch after the parent validates the existing output. Never delete ambiguous
state and redispatch. Disposable successful/cancelled containers are removed by
the parent; a reported cleanup failure requires operator quarantine and manual
Docker inspection/removal before the host is reused.

## Maturity

This is unqualified DEVELOPMENT containment on one trusted host. It does not
settle MQ-015, select production repeat counts, permit protected workloads,
establish hostile-host resistance, qualify reconstruction or an exam, finalize
an archive, publish an answer or activate rewards/network operations.
