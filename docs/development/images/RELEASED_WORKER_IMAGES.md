# Released worker images

IMAGE-RELEASE-01. The owner (2026-10-06) asked for one main-ready image to
test with, so nothing is rebuilt locally. The worker images are built once,
from a release tag cut from main, and pushed to
`ghcr.io/carbonphysicsai/...`. Every host then pulls them by digest. **A
deleted image is re-pulled, never rebuilt.**

| Kind | Repository | Built by | Stack |
|---|---|---|---|
| `c03` | `ghcr.io/carbonphysicsai/carbon-c03-worker` | `scripts/dev/c03_worker_image.sh` | JAX CPU |
| `accelerator` | `ghcr.io/carbonphysicsai/carbon-accelerator-worker` | `scripts/dev/accelerator_worker_image.sh` | JAX GPU (CUDA 13), on `c03` |
| `torch` | `ghcr.io/carbonphysicsai/carbon-torch-worker` | `scripts/dev/torch_worker_image.sh` | PyTorch CPU, on `c03` |
| `torch-gpu` | `ghcr.io/carbonphysicsai/carbon-torch-gpu-worker` | `scripts/dev/torch_gpu_worker_image.sh` | PyTorch GPU (CUDA 13), on `c03`, its own environment |

The PyTorch GPU worker (TORCH-GPU-01) installs the exact-hashed
`.devcontainer/torch/torch-cu130-py311.txt` (torch 2.13.0+cu130) on the C-03
worker. It does not share the JAX accelerator image: torch 2.13.0+cu130 needs
cuDNN 9.20.0.48 and the JAX CUDA 13 lock pins 9.12.0.46, so the two do not
resolve together. JAX's lock is unchanged. The image build refuses if the
cu130 install changes any C-03 distribution's version. It runs the way the
JAX accelerator worker runs: the controller's accelerator overlay sets the
platform (`JAX_PLATFORMS=cuda`), the bound device kind and the CUDA library
controls at run time, and battery implementation 2.0 rebuilds a PyTorch
recipe there under the GPU determinism settings (the recipe never chooses the
device). The validator path's accelerator dispatch stays disabled in the
repository, for JAX and PyTorch alike, so neither image is yet a scored
rebuild path.

PyTorch determinism is pinned as two profiles with separate identities
(`carbon/reconstruction/torch_profile.py`):
- `CPU_DETERMINISM`: deterministic algorithms, 2 threads, explicit-generator
  seeds. The PyTorch CPU image carries its digest as the
  `carbon.torch.determinism` label.
- `GPU_DETERMINISM`: the CPU settings, PyTorch's in-process CUDA settings
  (`accelerators.GPU_DETERMINISM_TORCH`, beside JAX's XLA flags) and JAX's
  CUDA library controls (`accelerators.GPU_DETERMINISM_ENVIRONMENT`). It is
  pinned inside the PyTorch GPU accelerator profile, which the image carries
  under JAX's labels (`carbon.accelerator.profile`, `.environment`), and is
  applied by `carbon/reconstruction/torch_gpu.py`.

The CPU torch environment and every Level-0 pin are unchanged.

None of these images is qualified. The scope is
`UNQUALIFIED_PUBLIC_DEVELOPMENT`. Security acceptance before mainnet is the
owner's (HUMAN_INPUT). The A40 determinism re-run is granted (#681) and has
not run yet.

## What the release publishes

The workflow is `.github/workflows/release-worker-images.yml`. It runs on
manual dispatch only, with the release tag as input. It attaches these assets
to the tag's GitHub release:

- `<kind>-worker-image.json`: the build's exact `carbon.c03.worker-image.v1`
  manifest;
- `<kind>-worker-image.release.json`: the release record
  (`carbon.worker-image-release.v1`). It holds the registry reference, the
  expected identity labels and the manifest;
- `capability-report.json`: the capability matrix (below).

## The host pull

```bash
python scripts/dev/worker_image_release.py pull \
  --record <kind>-worker-image.release.json [--out <manifest path>]
```

The pull fetches `repository@sha256:…`. It then refuses unless the pulled
image is the manifest's image: the same image ID, the reference among its
repository digests, linux/amd64, user `65532:65532`, the fixed entrypoint and
every identity label. Only then does it write the manifest, byte for byte.
The default path is `.carbon-artifacts/<kind>-worker-image.json`, which the
validator, the battery service and the Launchpad already read. An existing
different file is never overwritten.

**Host requirement:** Docker on the containerd image store. On that store an
image's ID is its registry digest, so one `image_id` names the image on every
host. The operator host already uses it. A host on the classic store is
refused with `image_id_mismatch`.

New GHCR packages start private. Until the owner makes `carbon-c03-worker`,
`carbon-torch-worker` and `carbon-torch-gpu-worker` public, a host needs its own `docker login ghcr.io`
with read access. The pull never logs in.

## Capability matrix

The matrix runs after the push, against the pulled digests
(`scripts/dev/worker_image_capability.py`). Each check is VERIFIED,
UNVERIFIED or FAILED.

| Cell | Verified on a standard (GPU-less) runner | Unverified until the granted A40 run (#681) |
|---|---|---|
| JAX CPU (`c03`) | imports, CPU devices, lock versions (`uv.lock`), one recipe rebuilt through the validator carrier | - |
| JAX GPU (`accelerator`) | imports, lock versions (`uv.lock`, `cuda13-py311.txt`), the pinned XLA flags accepted by the image's jaxlib | GPU devices, the flags active on a device, a GPU rebuild (validator accelerator dispatch is disabled in the repository) |
| PyTorch CPU (`torch`) | imports, CPU devices, lock versions (`uv.lock`, the science-torch export), deterministic algorithms and thread count in force, one recipe rebuilt through the validator carrier | - |
| PyTorch GPU (`torch-gpu`) | imports (a CUDA torch build), lock versions (`uv.lock`, `torch-cu130-py311.txt`) | GPU devices, the GPU determinism profile in force on a device; a CUDA rebuild stays UNVERIFIED even on a GPU while accelerator dispatch is disabled |

On a GPU host, `--gpus` (and optionally `--expect-device-kind`) runs the GPU
device checks. The release workflow never passes them.

## Testnet adoption (Ryan; nothing here has been run)

Old images and old manifest files stay. **Nothing on the host is deleted or
pruned** until the owner signs off the release.

1. Download the release records for tag `worker-images-vN`:

   ```bash
   gh release download worker-images-vN --repo carbonphysicsai/Carbon \
     --pattern '*-worker-image.release.json' --dir ~/released/worker-images-vN
   ```

2. Pull and verify, from a checkout at main:

   ```bash
   python scripts/dev/worker_image_release.py pull \
     --record ~/released/worker-images-vN/c03-worker-image.release.json \
     --out ~/.local/share/carbon-testnet/images/worker-images-vN/c03-worker-image.json
   ```

   Do the same for `accelerator` and `torch` where a deployment serves them.

3. Point the v1 and v2 deployments at the released manifest. In
   `~/.local/share/carbon-testnet/battery-validator/deployment.json` and
   `~/.local/share/carbon-testnet/battery-validator-v2/deployment.json`, set
   `image_manifest` to the new path. The old
   `~/.local/share/carbon-testnet/images/c03-worker-image.json` stays as
   history. Point the service configuration's `practice_images.image_manifest`
   at the same released manifest, so parity holds.

4. Carry each deployment over, then check it:

   ```bash
   python -m carbon.battery.operate upgrade --config <deployment.json>
   python -m carbon.battery.operate status --config <deployment.json>
   ```

   The image identity is a carry-over key, so `upgrade` records the old
   binding in the deployment's identity history. The service's
   `parity --config <service.json>` then confirms that practice and the
   validator name the same released digest.
