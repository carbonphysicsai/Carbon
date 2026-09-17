# C-CORE-09: pinned TPU worker and prospective request contract

Programme #209; dependency C-CORE-03 / PR #221, starting head
`6d592d640f7b7009f3c9fccea8ef99fc409ba00d`. Owner v3 authorizes implementation
and local packaging tests, not cloud spending, host installation or TPU access.
Primary Hub map_ref `SYSTEM/AGENT-EXECUTION`; map_structural impact, with root
integration owner batching Hub before delivery. Status: in progress.

## Working decision C-CORE-09-D1

KEEP C03 controller/admission/accounting and the existing registered TPU
environment/plan compiler. The service already performs explicit JAX backend,
device-count, process and precision verification after admission. WRAP the
existing clean-source image builder with the hash-locked TPU environment.
Preserve all CPU and CUDA historical schemas, digests and image identities.

Add a distinct prospective TPU worker profile and v3 request interpretation.
The profile binds one v5e host/eight chips, both existing execution roles and the
current resource policy/class. It is a typed preparation contract, not admission.
Reject TPU at reconstruction admission even with a fabricated typed worker
profile, before staging, training import or backend initialization. Existing outer
C03 dispatch remains GPU-only. No second launcher, scheduler, ledger or cloud API.
No cloud credentials, metadata access, host network, privileged container or
device broadening is added to the closed worker. No scientific thresholds change.

Build from the exact source commit via normal C03 parent construction; install
only existing hash-locked binary packages during image build. Verify provenance,
all dependency versions, source identities and nonroot readability in a bounded
network-disabled, read-only package instrument without importing numerical
backends or initializing any accelerator. Actual TPU execution remains open.

Official JAX 0.10.2 setup.py requires Python >=3.11, JAXlib 0.10.2 and
libtpu 0.0.42.*, matching the existing exact pins. Upstream sources verified:
- https://raw.githubusercontent.com/jax-ml/jax/jax-v0.10.2/setup.py
- https://docs.jax.dev/en/latest/installation.html
- https://docs.cloud.google.com/tpu/docs/run-calculation-jax
- https://docs.cloud.google.com/tpu/docs/v5e
- https://docs.cloud.google.com/tpu/docs/run-in-container

Google distinguishes eight-chip 2x4 single-host serving configurations from
training-optimized slices starting at sixteen chips. Small training may have
lower availability; the proposed v5litepod-8 is not an approved allocation.
Upstream privileged/host-network examples do not satisfy Carbon containment.

Owned files: this ticket; new `.devcontainer/accelerators/Dockerfile.tpu`,
`TPU_PREPARATION.md`; `scripts/dev/tpu_worker_image.sh`,
`inspect_tpu_worker_image.py`; `tests/cpu/test_tpu_worker_preparation.py`;
bounded prospective changes to `carbon/reconstruction/accelerators.py` and
`worker/model.py`, `worker/protocol.py`, `worker/docker_runtime.py` (explicit
unsupported-adapter guard). No changes to other worktrees/campaigns.
Root was notified of the shared seam before editing these existing fields.

Rejected alternatives: pretending NVIDIA device controls prove TPU containment,
request-selected device paths, copying privileged cloud examples, widening CPU
identities, inventing host facts, or treating package import as numerical evidence.
Reversal removes only the prospective TPU schema/image wrapper.

## Acceptance and remaining authority

Run focused malformed/version/role/admission tests, CPU/GPU compatibility tests,
exact quality checks, and local immutable image/package inspection. Full required
canonical, package, invariant, isolated-service and Hub delivery remain applicable
under current classification. A prepared image may merge admission-disabled.

Missing input remains REQUESTED_NOT_GRANTED in the existing programme resource
request. Need named project/account/zone/resource, grant and aggregate budget,
VM/kernel/runtime/device identities, device access without broad privilege,
network and metadata isolation, exclusive ownership and HBM/release telemetry,
expired-lease/controller-loss cleanup and allocation deletion authority. No
hardware acceptance, multi-device workload, numerical comparison, scientific or
security qualification is earned here. Completion is conditional on normal
tested expected-head merge under OWNER-DX-03.

## Prepared source and measured package evidence

Implementation source `cba4b6a597250591972c8f512ab7d42500c87e6a` produced image
`sha256:4b037bd720d7c154cd012de0ad4803a8b92d360062f102bb9b8c80cf78155dc0`.
Source archive digest:
`sha256:65ea0a773b0f71d2dda8d652082e2e60cdd6bae73b582e2a0b632e07060a75ef`.
TPU lock remains
`sha256:f42354e5eaec6c995fbee84407b095529b201ce82c04ea78b37777581d7bb3b2`.
The exact source/wheel/entrypoint identities are retained in the generated C03
manifest. Image size is 1,949,643,897 bytes; no inference/training timing or cost
claim follows from image size or build duration.

The local base container doctor passed. The isolated package instrument verified
all 23 pinned distributions, Python 3.11.16, readable immutable provenance and
environment files, Carbon service/protocol imports and no JAX/JAXlib/libtpu/Torch
imports. Its controls were UID65532, read-only root, network none, no devices,
512 MiB memory with no extra swap, 64 PIDs and 30-second attached-process deadline.
Exact container removal and absence were verified. A later inspection-tool repair
also reconciles an uncertain create response using an exact ownership label;
it does not change the built worker code or image identity. No image is relabelled
as a later source revision. Local logs/manifests are under
`.carbon-local/build-source/.carbon-artifacts/` in this ticket's worktree.

Baseline accelerator contracts passed 39 tests (one CPU numerical fixture
deselected). Integrated TPU/CPU/GPU worker contracts passed 66 tests with that
same fixture deselected; after the package-tool cleanup repair, eight focused
TPU/cleanup tests passed. All six changed Python files passed isolated/no-cache
Ruff and Black with the exact Python3.10 target. These are local diagnostics;
normal canonical delivery checks remain required. No cloud calls/spend, TPU/GPU
initialization, host installation, approved grant creation or campaign execution
occurred. Hardware and scientific acceptance remain open.
