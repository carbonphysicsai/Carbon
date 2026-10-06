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

There is no PyTorch GPU image yet. The owner put PyTorch GPU rebuilds in
scope (OWNER-SHARED-ANSWER-KEY-01), but the repository has no CUDA PyTorch
lock and no CUDA rebuild path, and adding them is a contract revision that is
the owner's call. A draft development expansion (0002) designs it.

PyTorch determinism is pinned as two profiles with separate identities
(`carbon/reconstruction/torch_profile.py`):
- `CPU_DETERMINISM`: deterministic algorithms, 2 threads, explicit-generator
  seeds. The PyTorch CPU image carries its digest as the
  `carbon.torch.determinism` label.
- `GPU_DETERMINISM`: the CPU settings plus cuDNN deterministic, no cuDNN
  benchmark and `CUBLAS_WORKSPACE_CONFIG=:4096:8`. It has its own digest and
  `carbon.torch.gpu-determinism` label, and is applied by the GPU-only module
  `carbon/reconstruction/torch_gpu.py`.

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

New GHCR packages start private. Until the owner makes `carbon-c03-worker`
and `carbon-torch-worker` public, a host needs its own `docker login ghcr.io`
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
| PyTorch GPU | nothing | every check: no PyTorch GPU image exists yet (draft expansion 0002) |

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
