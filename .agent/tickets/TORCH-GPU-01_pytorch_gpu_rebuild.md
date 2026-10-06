# TORCH-GPU-01: PyTorch GPU rebuilds (worker image now; rebuild path blocked)

**Status:** partly implemented on branch `claude/torch-gpu-expansion`, which
is stacked on #684 (`claude/released-worker-images`). The worker image, its
lock, the release and the capability cell are built. The CUDA rebuild path,
the contract revision and expansion record 0002 are **blocked** on one owner
decision (below). Nothing is LIVE.
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`. No Hub source change.
**Authority:**
- OWNER-SHARED-ANSWER-KEY-01: "Pytorch should be able to GPU rebuild too".
- The owner on 2026-10-06, relayed by the Test Engineer: "Commit but it is
  built to be the version that is ready for main and can determine reward. We
  will work tolerance during testing."
- OWNER-PYTORCH-BACKEND-01: the PyTorch tolerance is human-reserved.
- IMAGE-RELEASE-01 / #684: the GPU determinism profile.

**Executor:** a Test Engineer sub-session. PR Head merges.

## Built

1. **Lock.** `.devcontainer/torch/torch-cu130-py311.{in,txt}` holds the
   exact-hashed `uv pip compile` against PyPI and the PyTorch cu130 index. It
   pins torch 2.13.0+cu130, nvidia-cublas 13.1.1.3, cuDNN 9.20.0.48 and
   triton 3.7.1. The Test Engineer ran the resolution with Ryan's approval.
   Only the header's command line was changed, to repository paths.
2. **Separate image, decided by the Test Engineer.**
   - Why: torch 2.13.0+cu130 requires `nvidia-cudnn-cu13==9.20.0.48`, and
     the JAX CUDA 13 lock pins 9.12.0.46, so resolving the two together
     fails.
   - The PyTorch GPU worker (`.devcontainer/torch/Dockerfile.gpu`,
     `scripts/dev/torch_gpu_worker_image.sh`) is layered on C-03, in its own
     environment. The JAX accelerator image and its lock are untouched.
   - The build refuses if:
     - the cu130 install changes the version of any C-03 distribution. The
       overlap today is numpy, opt-einsum, pyyaml, scipy and
       typing-extensions, all at identical versions;
     - a pin is not the lock's;
     - the `carbon.torch.gpu-determinism` label is not the source's
       `GPU_DETERMINISM_DIGEST`;
     - `CUBLAS_WORKSPACE_CONFIG` is not the profile's.
3. **Environment identity** (`torch_profile`): `GPU_PINS`,
   `GPU_ENVIRONMENT_DIGEST` and `gpu_requirements_digest`. The CPU
   `ENVIRONMENT_DIGEST`, `DEPENDENCY_SPECS` and every Level-0 pin are
   byte-identical, and a test holds them.
4. **Release.** A `torch-gpu` kind in `worker_image_release.py`, the release
   script and the workflow, pushed to
   `ghcr.io/carbonphysicsai/carbon-torch-gpu-worker`. The runner-disk
   estimate is now 30-40 GB peak, which is likely over a standard runner. This
   is an estimate: use a larger runner, or build this image in its own job.
5. **Capability cell** (PyTorch GPU, on the `torch-gpu` image):
   - VERIFIED on a standard runner: imports (a CUDA torch build) and lock
     versions;
   - VERIFIED only on a GPU host: devices and the GPU determinism profile in
     force;
   - UNVERIFIED even on a GPU: the rebuild, because no CUDA rebuild path
     exists yet.
6. **Inventory and docs** updated.

## Blocked: the CUDA rebuild path (owner decision)

A real CUDA rebuild has to put the PyTorch backend's tensors and generator on
the device. Today that code is `carbon/battery/torch_training.py` (CPU-only),
which is a battery implementation module.

Measured on this branch with a scratch byte change, reverted afterwards:
editing it moves `contracts.implementation_digest()`. That moves the plan
digest and so **every battery recipe digest, JAX included**:
- the scaffold recipe and all nine run-5 recipes;
- the PyTorch recipe digests.

Strategy hashes, the registry contract digest and the Level-0 program digest
do not move.

The run-5 recipe digests are frozen evidence
(`docs/development/evidence/graphite-run5-q1/`,
`tests/cpu/test_battery_graphite_run5_q1.py`). Admitted submissions carry
over by recorded recompilation. Run-5, however, would no longer recompile to
its frozen digests from main, so "run-5 still verifies under v1" cannot hold
with a single implementation.

**Smallest decision needed:**
- **(A) Implementation v2.** Accept that every battery recipe digest moves
  to a new implementation version. The v1 module bytes are retained
  read-only, so v1 records (run-5, freeze manifests) still recompile and
  verify under v1, and the Level-0 v2 pins sit alongside v1. This is new
  machinery: versioned implementation snapshots.
- **(B) A GPU-only placement layer outside the implementation modules.** It
  is pinned by the GPU image and the GPU profile, and no recipe digest
  moves. The GPU numerics then depend on code the recipe digest does not
  bind. It would place tensors through a device mode around unchanged code,
  which is fragile, and it cannot be exercised here because there is no
  torch and no GPU.

Recommendation: (A). It keeps one contract-bound implementation for
scoring, and it is the "ready for main and can determine reward" version.
Until the owner chooses, the rebuild path, the contract revision and
expansion record 0002 stay unbuilt. Nothing advertises a capability the code
cannot execute.

## Owner-reserved (HUMAN_INPUT)

- The choice above, (A) or (B).
- The PyTorch GPU reproducibility tolerance. The owner sets it during
  testing.
- Security acceptance of the released digests before mainnet.
- Reward and LIVE authority. Agents never flip LIVE. The owner intends this
  path for reward once the tolerance and security acceptance are settled.
- GHCR visibility of `carbon-torch-gpu-worker` and package access (Ryan).

The A40 re-run is granted (#681). It should include this image's GPU cell.

## Risks

- The cu130 resolution took `requests 2.28.1`, `urllib3 1.26.13`,
  `certifi 2022.12.7` and `packaging 24.1` from the PyTorch index, which are
  older than the CPU export's. The worker runs with no network, so the risk is
  limited. A later recompile could restrict the extra index to torch, triton
  and the nvidia packages. The lock was not edited here.
- The image has not been built, because no Docker was used. The build-time
  guards are its first check.

## Validation

- Targeted tests:
  - `tests/cpu/test_torch_gpu_worker_image.py`
  - `tests/cpu/test_worker_image_capability.py`
  - `tests/cpu/test_release_worker_images_workflow.py`
  - `tests/cpu/test_worker_image_release.py`
  - `tests/cpu/test_torch_determinism_config.py`
  - `tests/cpu/test_battery_level1.py`
  - `tests/cpu/test_battery_graphite_run5_q1.py`
- The three gates: `ci_preflight.sh`, `check_quality.py --base origin/main`
  and `python -m carbon.challenge_pipeline validate`.

## Maturity

The worker image tooling is SPECIFIED, IMPLEMENTED and TESTED, with no build.
The CUDA rebuild path is SPECIFIED only (blocked). None of it is qualified.
