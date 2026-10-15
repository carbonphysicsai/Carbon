# PyTorch practice adoption

This is an engineering route for public development practice. Images, successful
imports and practice results do not grant official evaluation, security or
scientific qualification.

## CPU: install a complete matching pair

The existing Launchpad fields are sufficient: `image_manifest` is the primary
worker, and `analysis_image_manifest` must name an analysis image whose exact
`parent_image` is that worker's image ID. Setup verifies both images and the
accepted checkout's source identity. Battery practice serves `jax,pytorch` only
when the primary worker's lock matches the checkout's CPU Torch requirements.

For a release **that includes this repair and publishes its Torch companion**:

```bash
./scripts/install_miner.sh --release <matching-worker-images-tag> --pytorch --no-start
```

This selects `torch-worker-image.json` plus
`torch-analysis-worker-image.json`. The default invocation selects C03 plus
its C03-parented analysis as before. Repeat `--pytorch` on updates. The flag
selects the CPU worker; `--gpu` still installs the separate JAX GPU worker.
Select local CPU in setup to use CPU Torch practice. A GPU setup advertises the
backend of its independently selected GPU image instead.

The existing local build route, when the host operator authorizes it, is:

```bash
./scripts/install_miner.sh --ref <accepted-matching-revision> --pytorch --no-start
```

It uses `torch_worker_image.sh` and the existing analysis builder with that exact
Torch manifest as `--parent-manifest`. No backend declaration overrides an image.

## Required publication sequence

Root chooses one coherent merged source after dependent repairs. The existing
release rehearsal must pass for that exact source, including both C03 and Torch
analysis children built from their pushed parents and checked against their
parent layers. Only the release owner creates a release tag and dispatches the
existing release workflow.

The release script builds the workers, verifies their C03 parent identities,
pushes and records the Torch parent before building its analysis child, then
publishes `torch-analysis` under `carbon-torch-miner-analysis`. Build outputs,
capability-job pulls and release attachments all carry the new companion record
and manifest. The companion uses the existing closed analysis schema and `d4`
parent/runtime labels. Setup still requires exact parent equality, source digest,
doctor eligibility, analysis runtime identity and matching filesystem layers.

The existing `worker-images-v4` source is
`c41ba0680fdc009fc5fbf1ef3d07757f5e59d4b9`. Its CPU Torch image is
`ghcr.io/carbonphysicsai/carbon-torch-worker@sha256:886bd745fa129f773a53ff5e71634b2f2cca7cacd43632283116a8bf280389ba`.
That release verifies CPU Torch 2.13.0+cpu, torchvision 0.28.0+cpu,
neuraloperator 2.0.0 and nvidia-physicsnemo 2.2.0 in its capability report.
It publishes only C03-parented analysis. It cannot satisfy this new selection;
do not replace its manifests, re-label its analysis parent, or mix its workers
with a later checkout. Existing v4 installation and evidence remain unchanged.

## Actual GPU validation: separate public practice path

The owner offers an RTX 3060 or RunPod 4090. Root's recorded host observation is
an RTX 3060 Laptop with 6144 MiB, so plan within the observed device's memory.
Root owns hardware observation, TEST dispatch, any rental/spend and cleanup.

Test **both JAX and PyTorch on GPU** through the existing independent
`gpu_image_manifest` and public battery GPU setup path. Each backend has its own
image, profile and environment; one backend's success does not test the other.
Keep the CPU primary and its matching analysis pair.

| GPU leg | Released kind | Existing practice program | Offered backends |
|---|---|---|---|
| JAX | `accelerator` | `battery_gpu.GPU_PROGRAM` | `[jax]` |
| PyTorch | `torch-gpu` | `battery_gpu.TORCH_GPU_PROGRAM` | `[pytorch]` |

Verify each exact accepted source, device identity, toolkit, profile and lock.
Use the current portable GPU profile; the retained historical RTX 3060 profile
is readable historical evidence and is not dispatchable.
The v4 Torch GPU reference, relevant to immutable v4 evidence only, is
`ghcr.io/carbonphysicsai/carbon-torch-gpu-worker@sha256:fa49ec480f9fb387651fce2955fc8c79561becd8da2938d505a07730c439b18a`.
Its Torch 2.13.0+cu130 imports do not demonstrate actual CUDA device execution.
Later source needs its own matching worker.

Root's hardware acceptance must record actual driver/device/container identity,
CUDA visibility, exact worker/source/profile/lock, the offered
backend for that image, a matching recipe routed through the corresponding
program above, actual CUDA fit/prediction output and measured
time/memory, plus cleanup and any attributed spend. Retain an explicit failure
or unverified result for an unavailable/incompatible device. Do not silently
fall back to CPU and call it GPU evidence. Run separate bounded public practice
legs so their incompatible CUDA dependency environments remain separate.
Use a supported base recipe for these hardware legs. This does not enable
composed construction training on GPU or discharge its separate compiler and
security obligations.

The current installer `--gpu` selects JAX; local Torch GPU testing requires its
explicit manifest in the existing setup request. Remote setup's
`installed.released_gpu` recognizes the `accelerator` release kind only; it
does not automatically offer a published Torch GPU reference. Root must verify
the actual selected remote route if choosing RunPod rather than infer it from
the CPU `--pytorch` flag. This CPU repair does not change remote GPU selection.

`worker_image_capability.py --gpus --expect-device-kind <observed-kind>` can
observe imports/device/determinism, but the validator accelerator rebuild leg
deliberately remains disabled. Actual training must use the authorized public
miner practice route. Never bypass validator admission or retry rejected R8
probes to obtain a hardware PASS. No GPU training, performance or qualification
claim is earned by this source repair or its fixture tests.
