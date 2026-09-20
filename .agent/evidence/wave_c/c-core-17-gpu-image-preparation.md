# GPU worker image preparation: build and inspection under an image-only exception

Recorded 2026-09-20 under programme #209, following C-CORE-17 (PR #238).
Preparation evidence only. **No GPU was attached, no accelerator was
initialized, no host grant exists, and no observation contract is registered.**
Image construction and package inspection are not accelerator execution,
isolation evidence, or hardware acceptance.

## 1. Authority actually used

The recorded GPU pause reads
`PAUSED BEFORE GPU ACQUISITION, NEW IMAGE BUILD, OR INTEGRATED ACCEPTANCE`.

The owner issued a prospective, **image-only** exception lifting the "new image
build" clause alone, for a bounded local preparation task: build Carbon's pinned
NVIDIA DEVELOPMENT worker image, inspect it without accelerator initialization,
retain it locally, and record reproducible evidence. Downloading the
repository-pinned public build dependencies was permitted.

Everything else in the pause remains in force and was not exercised: no GPU
attachment or computation, no installed host grant, no campaign, no resumption of
the paused C-CORE-15 work, no rental, no paid API calls, no image publication,
and no change to the host's security or runtime configuration. The separate GPU
spending allowance was untouched.

This exception does not qualify the image scientifically or for security, and
does not authorize a later GPU run.

## 2. Source and tool identities

| Identity | Value |
| --- | --- |
| Source revision built | `df26e757ba6400757629388811c1f76b916d25f9` (main at build time) |
| Checkout state | fresh detached checkout in the Linux filesystem; `git status --untracked-files=all` empty, as the builder requires |
| Source tree digest | `sha256:802de52232202d9618cd98691ebf0c63c403275f6c53ac0ad97f8dc3fdb83137` |
| Builder | `scripts/dev/accelerator_worker_image.sh` (accepted path, unmodified) |
| Parent builder | `scripts/dev/c03_worker_image.sh` (accepted path, unmodified) |
| Recipe digest | `sha256:9303bb497d53de7af2737a97c5c358c2ab3de0b1db0ff6a580a0eaaa2f5433ad` |
| Lock digest | `sha256:a197af534a061636ba77e4f97f7e9be508b795d58883b6774fde74a5135ad434` |
| Profile digest | `sha256:8408adc8c7a3650bbbfb8d188be7dadae2df1e3c851f5b72a0e086bdcc012e79` |
| Docker Engine | 29.8.0, buildx v0.37.1, BuildKit v0.33.0 |
| Daemon default runtime | `runc` (verified unchanged; `nvidia` registered but not default) |

All values were derived from the checked-out source and the observed image. None
was copied from an earlier handoff.

## 3. Build outcome

| | |
| --- | --- |
| Exit status | **0** (captured from the builder process, not from a log writer) |
| Started / ended | 2026-09-20T04:17:24Z / 2026-09-20T04:20:01Z |
| Parent image | `sha256:f77312b991867089fd96c7089a3f081ba7af7f55157a15301e0bde5cf6d046d7`, tagged `carbon-c03-worker:802de52232202d96` |
| Parent base | `sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517` (pinned) |
| **Accelerator image** | **`sha256:728a6bf37906a2614b6fb3a29c01ee0cfafd4422daaa9b27bdf2c8ca4ef873cd`** |
| Image size | 6,037,086,413 bytes (~5.62 GB) |
| Wheel digest | `sha256:77ccc6f217d06a5e2e1097a056d15404b5bbd72dd697437a155a232bfb4e7f1e` |

Build logs, timings, manifests and inspection outputs are retained locally
outside the repository; they contain host paths and are not committed. Binaries,
virtual environments and caches were not committed.

A fresh output-manifest path outside the paused workspace was used. The builder's
parent-manifest path is fixed inside the repository root, so a fresh checkout was
used to avoid overwriting any pre-existing manifest; none existed there.

## 4. Inspection performed, and its limits

Inspection used the immutable image ID, not a mutable tag.

| Check | Result |
| --- | --- |
| Lock bytes inside image vs repo lock vs `GPU_PROFILE.environment_lock_digest` | all three identical |
| Label `…accelerator.profile` vs `GPU_PROFILE.digest` | identical |
| Label `…c03.base-image` vs parent manifest `image_id` | identical |
| Label `…c03.source-tree` vs source tree digest | identical |
| Internal `/opt/carbon/worker-image-build.json` vs manifest and source | agrees on base, recipe, lock, entrypoint, source tree, wheel |
| Pinned distributions installed | 34 / 34, zero missing, zero version mismatches |
| CUDA plugin packages | `jax-cuda13-plugin` and `jax-cuda13-pjrt` 0.10.2, plus 15 pinned `nvidia-*` packages at their locked versions |
| Distribution beyond the lock | exactly one: `carbon` itself |
| Default user | `65532:65532`, non-root |
| Entrypoint | fixed: `/opt/carbon-worker/bin/python -I -m carbon.reconstruction.worker.entrypoint` |
| Worker file modes | `/opt/carbon` and `/opt/carbon-worker` `dr-xr-xr-x`; build metadata and lock `-r--r--r--` |
| Write probes as the image user | both denied (`PermissionError`) |
| Host grant paths present in image | none (`/var/lib/carbon*` absent) |
| Paused C-CORE-15 artifacts in image | none, over 6,399 scanned files |
| Credential-shaped files in image | none found, same scan |

Package metadata was read with `importlib.metadata`. **No numerical backend was
imported**, `jax.devices()` was not called, and no matmul, training or GPU
diagnostic was executed.

**Coverage limits, stated rather than implied.** The filename scan covered
`/opt/carbon` and `/opt/carbon-worker` only; it did not inspect file contents or
other layers, and is not an exhaustive secret or security audit. Image metadata
is not a runtime control: a non-root user and the presence of CUDA libraries do
not establish isolation, GPU memory enforcement, device visibility, or any
ability to reconstruct a scientific workload.

## 5. Evidence that no GPU was attached

- Neither builder script nor the accelerator recipe contains `--gpus`, a device
  request, `/dev/dxg`, an NVIDIA device mapping, `--privileged`, or a GPU
  BuildKit entitlement. Verified by search over all three files.
- The build logs contain zero occurrences of `--gpus`, `/dev/dxg` or `nvidia-smi`.
- The daemon default runtime remained `runc`; no global default was changed to
  satisfy this task.
- Inspection containers ran with `--network none` and `--security-opt
  no-new-privileges`, with no device request.
- The image's own default environment is `JAX_PLATFORMS=cpu`.

This establishes that this task issued no device request. It is not a claim
about other processes on the host, and no live GPU telemetry probe was run.
`verify_device_release()` was deliberately not called, since it can create
quarantine state.

## 6. Cleanup and preservation

The builder's temporary manifest containers were removed by its own trap, and
the inspection container created for file extraction was removed explicitly.
`docker ps -a` reports **0 containers**. No `docker system prune`, image prune,
global cache removal or deletion of other executors' assets was performed.

The built parent and accelerator images and their manifests are deliberately
retained. That is an intended local change, not a claim that the host is
byte-for-byte unchanged. Docker image storage grew from 54.54 GB to 60.46 GB.

Host authority state is untouched: `/var/lib/carbon/accelerators` still does not
exist, and `/etc/docker/daemon.json` retains digest
`6376ec5a8dea443f35d6937aaf017a5c93f3d98f859774443d9a51e796102758`.

The paused C-CORE-15 workspace was rechecked, not assumed: HEAD
`3f3eec3b882090ea3ca87951a93eac52db4954d9`, the same three modified and eight
untracked files, with per-file content digests matching the previously recorded
inventory. Nothing was staged, stashed, reset, renamed, cleaned or overwritten,
and no C-CORE-15 file entered the build context.

## 7. Observation for the integration owner

The accelerator overlay image is left **untagged** (`RepoTags: []`) while the
C-03 parent is tagged by source digest. The manifest references the overlay by
immutable ID, which is what the controller checks, so this is not a correctness
defect. It does mean a routine `docker image prune` would discard a 5.62 GB
build. Recorded as an observation; the accepted builder was not modified, since
changing it would require a fresh build to re-verify.

## 8. Status after this task

- Accelerator worker image: **built and inspected locally**; not published.
- `ESTABLISHED_OBSERVATION_CONTRACTS`: still **empty**. Strict accelerator
  admission and verified whole-device release remain **unavailable on every
  host**. The build did not populate the registry or certify any host.
- Host grant: **absent**. No lease, journal or admission state was created.
- C-CORE-15: **still paused and preserved**.
- GPU execution, campaign and acceptance: **not authorized and not performed**.

### Remaining prerequisites, kept separate

**Trusted local diagnostics** would need a development-only contract defining
what may run, on which inputs, with what finite bounds and retained evidence —
explicitly not masquerading as strict admission. The image now exists; the
contract does not.

**Strict GPU acceptance** additionally needs an established observation source
for compute-process enumeration with its own evidence, a registered observation
contract bound to that source, and an operator-installed host grant. No grant
field is proposed here, and a device-free build establishes none of this.
