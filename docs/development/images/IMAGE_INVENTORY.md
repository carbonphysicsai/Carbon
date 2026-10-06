# Carbon image inventory (operator host, 2026-10-06)

IMAGE-RELEASE-01. Every Docker image on the operator host (WSL), what uses
it, which script builds it, and whether the released worker images cover it.
It was read with `docker images` and
`docker image inspect --format '{{json .Config.Labels}}'` only. Nothing was
pulled, run, built, tagged, removed or pruned.

**Nothing is deleted.** Every image below stays on the host until the owner
signs off the release. "Obsolete" means only that the release supersedes it;
removing it is the owner's decision, after sign-off.

Status values:
- **COVERED**: the release builds and pushes this image's successor from the
  release tag (`c03`, `accelerator`, `torch`).
- **SEPARATELY PINNED**: outside this release. It keeps its own pin (truth
  image, Challenge reference, Julia lanes, study evidence).
- **OBSOLETE**: superseded. It is kept until owner sign-off.
- **NOT A WORKER**: a development container or a third-party base or tool.

IDs are the host's short image IDs. This host uses the containerd image
store, so an ID is also the registry digest of a pushed image.

## Worker images the release covers

| Image (tag) | ID | Used by | Built by | Status |
|---|---|---|---|---|
| `carbon-c03-worker:211788bc66135406` | 427997a044bc | validator `image_manifest`, miner practice, C-03 service acceptance | `scripts/dev/c03_worker_image.sh` | COVERED (`c03`) |
| `carbon-c03-worker:e85f9b4b6090db6b`, `carbon-cw1d4-parent:944bab…` | 944bab7070a7 | as above; parent of CW1 D4 research images | `c03_worker_image.sh`; parent tag by `carbon/development_session/research_image.py` | COVERED (`c03`) |
| `carbon-c03-worker:2c43e924c54320ca`, `carbon-cw1d4-parent:04f0b7…` | 04f0b73062b5 | as above | as above | COVERED (`c03`) |
| `carbon-c03-worker:b4342b2315626601`, `carbon-cw1d4-parent:499bf7…` | 499bf71a44f1 | as above | as above | COVERED (`c03`) |
| `carbon-c03-worker:37fbd8cb12018543`, `carbon-cw1d4-parent:03000f…` | 03000f3d1698 | as above | as above | COVERED (`c03`) |
| `carbon-c03-worker:5dd297148a3e9016`, `carbon-cw1d4-parent:e45fc2…` | e45fc2c1a81e | as above | as above | COVERED (`c03`) |
| `carbon-c03-worker:d80d11dc494feb69`, `carbon-cw1d4-parent:96a6ba…` | 96a6ba914a87 | as above | as above | COVERED (`c03`) |
| `carbon-cw1d4-parent:c13f12…` | c13f12c58899 | CW1 D4 research parent | as above | COVERED (`c03`) |
| `carbon-c03-worker:764405a92de58c7f`, `carbon-cw1d4-parent:aaa339…` | aaa33950a5b2 | as above | as above | COVERED (`c03`) |
| `carbon-c03-worker:1301819bda4e6a3c`, `carbon-cw1d4-parent:e70de3…` | e70de367f245 | as above | as above | COVERED (`c03`) |
| `carbon-c03-worker:ccd71132a252433e`, `carbon-cw1d4-parent:fd8aca…` | fd8acac99b78 | as above | as above | COVERED (`c03`) |
| `carbon-c03-worker:fd3a1f0fa6a8d4ef`, `carbon-cw1d4-parent:1e1c51…` | 1e1c51cf387a | as above | as above | COVERED (`c03`) |
| `carbon-accelerator-worker:de7fa60b`, `ghcr.io/carbonphysicsai/carbon-accelerator-worker:de7fa60b` | e4a2014daa9a | validator GPU path (`docs/development/VALIDATOR_DEPLOYMENT_PATH.md` pins this digest), miner GPU practice | `scripts/dev/accelerator_worker_image.sh` | COVERED (`accelerator`); its GHCR digest stays pullable |
| `carbon-gpu-worker-local:df26e757-728a6bf37906` | 728a6bf37906 | local GPU practice build; its accelerator-profile label is not the current `GPU_PROFILE` digest | `accelerator_worker_image.sh` (local tag; no script names it) | OBSOLETE (superseded by `accelerator`) |
| (none on host) PyTorch CPU worker | - | validator `torch_image_manifest`, PyTorch practice | `scripts/dev/torch_worker_image.sh` | COVERED (`torch`); first build |
| (none on host) PyTorch GPU worker | - | PyTorch GPU rebuilds (battery implementation 2.0, TORCH-GPU-01) | `scripts/dev/torch_gpu_worker_image.sh` | COVERED (`torch-gpu`); first build |
| (deleted) testnet v1/v2 C-03 worker `sha256:f33ce005…` | - | testnet v1 and v2 `image_manifest` | `c03_worker_image.sh` | COVERED (`c03`): re-pulled from the release, never rebuilt |

## Images the release does not cover

| Image (tag) | ID | Used by | Built by | Status |
|---|---|---|---|---|
| `ghcr.io/carbonphysicsai/carbon-determinism-study:d0c19830d095` | 2d19b261e722 | battery truth image (`carbon/battery/truth.py`), exam-design pods (`scripts/dev/exam_design/runpod/pod_control.py`) | GPU determinism study (`scripts/dev/gpu_determinism_study/`) | SEPARATELY PINNED (truth image) |
| `carbon-study:candidate`, `ghcr.io/carbonphysicsai/carbon-determinism-study:77c5206116e0` | 998060acfe8a | GPU determinism study candidate | `scripts/dev/gpu_determinism_study/` | SEPARATELY PINNED (study evidence) |
| `ghcr.io/carbonphysicsai/carbon-determinism-study:74ff35ead1e5` | 3ebfe68571f2 | GPU determinism study candidate | as above | SEPARATELY PINNED (study evidence) |
| `carbon-study:local` | 125eb8c7bfd3 | local study build | as above | OBSOLETE (superseded by the published study images) |
| `carbon-study-runner:local` | 93f34e9515c5 | local study runner build | as above | OBSOLETE (as above) |
| `carbon-motor-reference:main-75330721`, `ghcr.io/carbonphysicsai/carbon-motor-reference:main-75330721` | 599521e79786 | electric-motor Challenge reference | `scripts/dev/motor/reference/` | SEPARATELY PINNED (Challenge reference) |
| `carbon-motor-reference:dev` | 85c337abf8e2 | the image `carbon/challenge_registry/motor.py` names | `scripts/dev/motor/reference/` | SEPARATELY PINNED (Challenge reference) |
| `carbon-cw1d4-parent:de8308…` | de83087a4814 | native Julia reference worker (CW1 D4 research, Workbench) | `scripts/dev/julia_worker_image.sh` | SEPARATELY PINNED (Julia) |
| `carbon-cw1d4-parent:ac873d…` | ac873d7622d9 | native Julia reference worker | `julia_worker_image.sh` | SEPARATELY PINNED (Julia) |
| `carbon-c03-worker:7540003d5ee5337d`, `carbon-julia-parent:0bd385…` | 0bd385eb429d | C-03 parent of the Julia workers | `julia_worker_image.sh` (via `c03_worker_image.sh`) | SEPARATELY PINNED (Julia parent) |
| `carbon-julia-parent:e623ce…` | e623cec461d1 | C-03 parent of an older Julia build | as above | SEPARATELY PINNED (Julia parent) |
| `carbon-julia-parent:eef521…` | eef521815d4b | C-03 parent of the authored-Julia analysis images | as above | SEPARATELY PINNED (Julia parent) |
| `carbon-authored-julia-parent:22750c…` | 22750c4d6c2b | miner analysis image (Launchpad `analysis_image_manifest`) | `carbon/development_session/julia_analysis.py` | SEPARATELY PINNED (Julia) |
| `carbon-authored-julia-parent:4cb885…` | 4cb8855c77c0 | miner analysis image, earlier build | as above | SEPARATELY PINNED (Julia) |
| `carbon-authored-julia-parent:649a5b…` | 649a5b0bf98d | miner analysis image, earlier build | as above | SEPARATELY PINNED (Julia) |
| `carbon-authored-julia-packages:2d885c…` | 2d885cb264dd | authored-Julia package stage | as above | SEPARATELY PINNED (Julia) |
| `carbon-authored-julia-packages:3fd756…` | 3fd7564e0591 | authored-Julia package stage | as above | SEPARATELY PINNED (Julia) |
| `carbon-julia-depot:aa09e0…`, `ghcr.io/carbonphysicsai/carbon-julia-depot:52a6de…` | aa09e0acfdc0 | the published authored-Julia depot (`scripts/dev/julia_depot.lock.json` pins this digest), CI `julia-service` | `carbon/development_session/julia_depot_build.py` | SEPARATELY PINNED (Julia depot) |
| `carbon-julia-depot:f2330a…` | f2330a3ee4bd | an earlier depot build | as above | OBSOLETE (superseded by the pinned depot) |
| `ghcr.io/carbonphysicsai/carbon-julia-depot:32c72b…` | e013596b5496 | an earlier published depot | as above | OBSOLETE (superseded by the pinned depot) |
| `carbon-julia-depot-packages:8e5a00…` | 8e5a006a30fd | depot build stage | as above | SEPARATELY PINNED (depot build stage) |
| `carbon-julia-depot-packages:baeb05…` | baeb05980f76 | depot build stage, earlier | as above | OBSOLETE |
| `carbon-julia-depot-packages:8c1581…` | 8c1581008661 | depot build stage, earlier | as above | OBSOLETE |
| `carbon-julia-depot-base:1d0946…` | 1d0946f51082 | depot base stage | as above | SEPARATELY PINNED (depot build stage) |
| `carbon-julia-depot-base:f2c643…` | f2c64317aee4 | depot base stage, earlier | as above | OBSOLETE |
| `carbon-julia-depot-base:f50481…` | f50481507003 | depot base stage, earlier | as above | OBSOLETE |
| `carbon-julia-science:core-platform-v1` | f20c4cbf9ec2 | native Julia science instrument | `.devcontainer/Dockerfile.julia-science` (`scripts/dev/julia_scope.py`) | SEPARATELY PINNED (Julia) |
| `carbon-canonical:d9bc9b882f702299` | 5fd3fcd4eb2d | canonical validation container | `scripts/dev/canonical.sh` (`.devcontainer/Dockerfile`) | NOT A WORKER |
| `ubuntu:<none>` | 33ceb71981b6 | the C-03 worker's pinned base | upstream | NOT A WORKER (base) |
| `nvidia/cuda:13.0.0-base-ubuntu24.04` | 6e43a6b02e5f | CUDA host checks | upstream | NOT A WORKER (tool) |
| `postgres:<none>` | 051f7b7b3abd | evidence-archive storage (`carbon/evidence_archive/storage.py`) | upstream | NOT A WORKER (tool) |
| `opencfd/openfoam-default:<none>` | 33fb575aa998 | cold-plate reference cases (`scripts/dev/cold_plate/*/run_case.sh`) | upstream | NOT A WORKER (tool) |
| `mcr.microsoft.com/playwright:v1.56.0-noble` | 35246d87a7c8 | browser tooling | upstream | NOT A WORKER (tool) |
| `node:24.19.0-bookworm-slim` | a9f5f7c91a43 | web tooling | upstream | NOT A WORKER (tool) |
| `node:24.19.0-alpine` | d32cdf619f63 | web tooling | upstream | NOT A WORKER (tool) |
| (untagged) | 871366b15ffa | none found: no name, no labels | unknown | NOT A WORKER (dangling) |

## Capabilities

| Capability | Before (host) | After (release) |
|---|---|---|
| JAX CPU | many local C-03 builds; the testnet one deleted | `carbon-c03-worker`, released by digest |
| JAX GPU (CUDA 13) | `carbon-accelerator-worker` e4a2014daa9a | `carbon-accelerator-worker`, released from the tag |
| PyTorch CPU | no image on the host | `carbon-torch-worker`, released |
| PyTorch GPU | never existed | `carbon-torch-gpu-worker`, released (CUDA 13, its own environment); PyTorch CUDA rebuilds are battery implementation 2.0 (TORCH-GPU-01) |
| Julia, truth, motor reference | as above | unchanged and separately pinned |
| TPU (`scripts/dev/tpu_worker_image.sh`) | no image on the host | not released (preparation only) |

No capability the host has today is dropped by the release.
