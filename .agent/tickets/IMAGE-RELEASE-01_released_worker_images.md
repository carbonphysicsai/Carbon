# IMAGE-RELEASE-01: released worker images, pulled by digest

**Status:** implemented in bounded DEVELOPMENT scope on branch
`claude/released-worker-images`. Not yet run: no tag, release, workflow run
or image exists. The owner-reserved items below stay HUMAN_INPUT.
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`. No Hub source change: the
system's placement, dependencies and maturity stay as recorded. This adds
release tooling around images that already exist.
**Authority:**
- the owner's direction, relayed by the Test Lead on 2026-10-06: build an
  image that main can use too, and do not rebuild locally;
- the owner's addition the same day: full JAX and PyTorch CPU and GPU
  capability, with nothing lost;
- the Test Lead's addition: a pinned PyTorch determinism configuration;
- OWNER-SHARED-ANSWER-KEY-01 (the validator-GPU addendum names the A40);
- OWNER-PYTORCH-BACKEND-01 (the PyTorch tolerance is human-reserved);
- OWNER-LAUNCHPAD-PROD-02 answer 10 (practice runs on the validator's own
  images).

**Consulted:** the Carbon Validator, on the deployment fields
(`image_manifest`, `torch_image_manifest`, `practice_images`) and the adoption
steps.
**Executor:** a Test Engineer sub-session. PR Head merges.

## Why

The testnet v1 and v2 C-03 worker image (`sha256:f33ce005…`) was deleted
from the laptop's Docker. A local rebuild gives a new identity, so it is not
that image. The fix is a released image that every host pulls by digest. A
deleted image is then re-pulled, never rebuilt.

## Scope

1. **Release workflow** (`.github/workflows/release-worker-images.yml`).
   - Trigger: manual dispatch only, with a `worker-images-vN` tag input. It
     never runs on a pull request or a push.
   - Before building, it checks out the exact tag and requires that the tag
     is on main.
   - It builds with the existing scripts through
     `scripts/dev/release_worker_images.sh`:
     - `c03_worker_image.sh`: JAX CPU;
     - `accelerator_worker_image.sh`: JAX GPU, CUDA 13, on `c03`;
     - `torch_worker_image.sh`: PyTorch CPU, on `c03`.
   - It requires that each child image is built on the released `c03` image.
   - It pushes to `ghcr.io/carbonphysicsai/{carbon-c03-worker,carbon-accelerator-worker,carbon-torch-worker}`
     and records each image by its registry digest.
   - It attaches the manifests, the release records and the capability
     report to the existing release, and never overwrites an asset.
   - Permissions are least privilege:
     - no default permissions;
     - build: `packages: write` and `contents: read`;
     - capability: `packages: read` and `contents: read`;
     - publish: `contents: write`.
   - Every action is pinned by commit SHA. The token reaches `docker login`
     on stdin only.
2. **Runner disk.** Toolchains are removed (dotnet, Android, GHC, CodeQL,
   Swift, PowerShell). This is an estimate, not a measurement:
   - the NVIDIA worker is about 6 GB unpacked, based on the operator host's
     build;
   - the C-03 worker is about 1 GB;
   - the PyTorch worker is an estimated 2-3 GB;
   - the containerd store keeps the compressed layers too, so the peak with
     build cache is an estimated 15-20 GB;
   - removing the toolchains frees an estimated 25-30 GB.

   If it does not fit, run the `build` job on a larger runner. That is a
   one-line `runs-on` change.
3. **Host pull** (`scripts/dev/worker_image_release.py pull`). It pulls by
   digest. It refuses on any mismatch of:
   - the image ID;
   - the registry digest;
   - the platform;
   - the user and entrypoint;
   - any identity label.

   It refuses a record that is missing a field before it calls Docker. It
   writes the build's exact manifest where the validator, the service and
   the Launchpad read it, and never overwrites a different file.
4. **Parity.** A manifest pulled from a release record satisfies the battery
   service's image parity. Two pulls from one record match; a release of
   another build differs. This is tested.
5. **Capability matrix** (`scripts/dev/worker_image_capability.py`, the
   `capability` job). It runs after the push, on the pulled digests. It
   covers:
   - JAX CPU, JAX GPU, PyTorch CPU and PyTorch GPU;
   - imports, devices, lock versions read from `uv.lock` and the exports,
     the determinism config, and one battery recipe rebuilt through the
     validator carrier.

   Each check is VERIFIED, UNVERIFIED or FAILED. A GPU check on a GPU-less
   runner is UNVERIFIED, never passed. The report is a job artifact and a
   release asset.
6. **PyTorch determinism configuration** (`torch_profile.DETERMINISM`). It
   pins:
   - deterministic algorithms;
   - cuDNN deterministic, no benchmark;
   - `CUBLAS_WORKSPACE_CONFIG=:4096:8`, the NVIDIA overlay's own value;
   - 2 intra-op threads;
   - the explicit-generator seed source.

   `DETERMINISM_DIGEST` is its identity, and any changed setting changes it.
   The PyTorch image recipe checks the digest at build time and carries it as
   the `carbon.torch.determinism` label. The release record and the pull
   require that label. No tolerance is set.
7. **Inventory** (`docs/development/images/IMAGE_INVENTORY.md`). It lists all
   50 images on the operator host, from read-only `docker images` and label
   inspection only, and says what uses each one, which script built it, and
   its status.
8. **Adoption steps** (`docs/development/images/RELEASED_WORKER_IMAGES.md`
   and below).

## Engineering decisions (delegated, recorded here)

- **D1: containerd image store.** On the operator host, every GHCR image's
  ID equals its registry digest, so the host is on the containerd image
  store. A manifest's `image_id` is `docker image inspect .Id`, which depends
  on the store. Released images are therefore built, pushed and pulled on the
  containerd store, where `image_id` is the registry digest and the same on
  every such host.
  - `record` refuses a push whose digest is not the image ID.
  - `pull` refuses a host whose `Id` differs.
  - The workflow switches its ephemeral runners to the containerd store.
- **D2: the release record is a new file.** It is
  `carbon.worker-image-release.v1`, beside the manifest. The
  `carbon.c03.worker-image.v1` manifest schema is unchanged, because the
  validator loads an exact key set. The record carries the registry reference
  and the labels the manifest has no place for.
- **D3: the cuDNN settings are not applied in the rebuild path in this PR.**
  `carbon/battery/torch_training.py` is a battery implementation module.
  Editing it moves `contracts.implementation_digest()`, and with it the
  battery contract digest and the frozen `LEVEL0_PINS`, which is a contract
  migration. The CPU path already applies deterministic algorithms, the
  thread count and an explicit generator, and a test holds them equal to the
  pin. The cuDNN settings act only on CUDA, and PyTorch has no CUDA path. They
  are applied when that path is added, as its own contract revision (see
  Blocked).
- **D4: no PyTorch GPU image.** Building one needs a CUDA PyTorch lock with
  hashes, which needs network resolution, and a CUDA rebuild path. Neither
  exists. The matrix reports the cell as UNVERIFIED throughout and does not
  pretend otherwise.
- **D5: the GPU rebuild check stays UNVERIFIED even on a GPU host.** The
  validator path's accelerator dispatch is disabled
  (`require_accelerator_admission`). The GPU device checks run with `--gpus`.

## VERIFIED vs UNVERIFIED (what CI can show)

- **VERIFIED on CI, once a release runs** (nothing has run yet):
  - JAX CPU: imports, devices, locks, carrier rebuild.
  - PyTorch CPU: the same, plus deterministic algorithms and threads in
    force.
  - JAX GPU: imports, locks, and the pinned XLA flags accepted.
- **UNVERIFIED until an A40 run:**
  - JAX GPU: devices, the flags active on a device, a GPU rebuild.
  - Every PyTorch GPU check.
  - Any reproducibility claim.

## Owner-reserved (HUMAN_INPUT)

- **Security acceptance of the released digests** before mainnet (the OD-3
  successor).
- **The A40 determinism re-run.** It needs a grant.
- **The PyTorch reproducibility tolerance** (OWNER-PYTORCH-BACKEND-01). Only
  the configuration is pinned.
- **Removing old images** from the host, after the release is signed off.

## Blocked / follow-up

- **PyTorch GPU worker.** It needs a CUDA PyTorch lock with hashes, a CUDA
  rebuild path in `torch_training.py`, and the cuDNN settings applied there.
  That is a battery contract revision. The smallest decision needed is for
  the owner or the Carbon Validator to authorize that revision.
- **Package visibility.** New GHCR packages start private. The owner makes
  `carbon-c03-worker` and `carbon-torch-worker` public, or each host logs in.
- **Pushing to the existing `carbon-accelerator-worker` package** needs that
  package to grant this repository's Actions write access.

## Testnet adoption (Ryan; not run by this ticket)

Nothing on the host is deleted or pruned. Old images and the old manifest
file stay until the owner signs off.

1. `gh release download worker-images-vN --pattern '*-worker-image.release.json'`
2. `python scripts/dev/worker_image_release.py pull --record c03-worker-image.release.json --out ~/.local/share/carbon-testnet/images/worker-images-vN/c03-worker-image.json`
3. Set `image_manifest` in `battery-validator/deployment.json` and
   `battery-validator-v2/deployment.json` to that path. Point the service's
   `practice_images.image_manifest` at the same released manifest.
   `images/c03-worker-image.json` stays as history.
4. Run `python -m carbon.battery.operate upgrade --config <deployment.json>`,
   then `status`, for each deployment. Then run the service `parity` check.

## Expected manifest

- `.github/workflows/release-worker-images.yml` (new)
- `scripts/dev/release_worker_images.sh` (new, 100755)
- `scripts/dev/worker_image_release.py` (new, 100755)
- `scripts/dev/worker_image_capability.py` (new, 100755)
- `scripts/dev/torch_worker_image.sh`: the determinism build argument
- `.devcontainer/torch/Dockerfile`: the determinism label and build-time
  check
- `carbon/reconstruction/torch_profile.py`: `DETERMINISM` and its digest
- `tests/cpu/test_worker_image_release.py`,
  `tests/cpu/test_worker_image_capability.py`,
  `tests/cpu/test_torch_determinism_config.py`,
  `tests/cpu/test_release_worker_images_workflow.py` (new)
- `docs/development/images/IMAGE_INVENTORY.md`,
  `docs/development/images/RELEASED_WORKER_IMAGES.md` (new)
- this ticket

## Validation

- Targeted tests:
  `pytest tests/cpu/test_worker_image_release.py tests/cpu/test_worker_image_capability.py tests/cpu/test_torch_determinism_config.py tests/cpu/test_release_worker_images_workflow.py tests/cpu/test_battery_level1.py tests/cpu/test_battery_torch_validator.py`
- Static validation of the workflow: a YAML parse, the triggers and
  permissions, SHA pins, and `bash -n` on every run block. actionlint is not
  installed.
- The gates `ci_preflight.sh`, `check_quality.py --base origin/main` and
  `python -m carbon.challenge_pipeline validate`.
- No Docker, image build, `canonical.sh`, tag or workflow run was used.

## Invariants

- Pinned official evaluation: images are named by digest only. A mismatch
  refuses.
- Infrastructure failure is not scientific failure: a pull or registry
  failure is a named refusal, never a score.
- No placeholder becomes LIVE: the scope label stays
  `UNQUALIFIED_PUBLIC_DEVELOPMENT`.
- Historical evidence is versioned: the battery contract and implementation
  digests are unchanged (D3). Old manifests and images are kept.

## Maturity

The work is SPECIFIED, IMPLEMENTED and TESTED, with unit tests and fake
Docker. It is not run, and not SECURITY_QUALIFIED, SCIENTIFICALLY_QUALIFIED
or PRODUCTION_QUALIFIED.

## Completion predicate

The ticket closes when its PR merges through PR Head, under the delivery
protocol. A first release run and its capability report are owner actions
after merge.
