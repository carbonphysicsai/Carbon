# TORCH-POD-01: battery's PyTorch builds on Carbon's Graphite pods

**Assigned:** the Test Lead, 2026-10-10, under OWNER-DEV-AUTONOMY-01, from
stage A's D3: level-0.json declares fno and PyTorch, but battery's scoring
record served JAX only, so a valid L0 recipe was refused
`REFUSED_BACKEND_NOT_SERVED`. The owner's backend-parity rule (2026-10-06):
PyTorch GPU works exactly like JAX GPU, through one shared mechanism with
parity tests.

**Status:** DEVELOPMENT. IMPLEMENTED and TESTED on CPU; the GPU check below
has not run yet.

## What already existed

- **Validator side:** RECON-TORCH-01 (`test_battery_torch_validator`) and
  TORCH-GPU-01's GPU parity (`test_battery_torch_gpu_parity`, mlp, deeponet
  and fno in the released torch-gpu image) cover the validator rebuilding
  PyTorch.
- **Practice program:** `carbon.battery.practice.PROGRAM` already stages
  battery's PyTorch trainer and families, and `recipes.build` builds the
  recipe's own backend.
- **Graphite pods:** they ran JAX only: the EV4 study image, a JAX runtime
  record, a JAX probe and `JAX_PLATFORMS=cuda,cpu`.

## One mechanism, chosen by the job's backend

| Piece | JAX (unchanged, byte for byte) | PyTorch |
|---|---|---|
| Pod program (`battery_gpu.pod_program`) | v1, or v2 for KNN | v3: the same practice program plus PyTorch's runtime record, under the keys `rebuild_identity.from_runtime` reads |
| Staging (`BatteryScoring.built_from`) | as before | the same staged files, program by backend |
| Image (`pods.pod_image`) | `pod_control.IMAGE` | the released torch-gpu worker image (`a40_acceptance.IMAGES`, worker-images-v3) |
| Host CUDA (`pods.allowed_cuda_versions`) | from the accelerator lock | from the torch lock's CUDA runtime |
| Platform | `JAX_PLATFORMS=cuda,cpu` | `JAX_PLATFORMS=cuda`, the platform `torch_training.rebuild_device` reads |
| Probe (`pod_phase.probe_for`) | JAX's | PyTorch's, the same shape |
| Job config | no `backend` key | `"backend": "pytorch"` |

- **The served record is versioned:** `battery_scoring.SERVED_BACKENDS`.
  `battery-scoring-v1` is `("jax",)`; the current `battery-scoring-v2-pytorch`
  is `("jax", "pytorch")`.
- **Development levels 1–3** keep `development_backends = ("jax",)`, because
  they train with their own JAX programs.
- **No pinned battery module is edited.**

## Tests

- `tests/cpu/test_battery_torch_pods.py`, CPU:
  - JAX programs are unchanged and PyTorch's is v3;
  - the record is versioned;
  - identity parity: a pod's PyTorch build is Carbon's rebuild record, with
    no `rebuild_differences` and the same pinned files and program;
  - the job config;
  - the pod spec's image and platform by backend;
  - the CUDA versions;
  - the probe by backend.
- `test_challenge_validator_scoring` and `test_graphite_phase3`: v1 still
  refuses PyTorch with its code, and a PyTorch proposal launches a PyTorch job.
- **The GPU check:**
  `test_the_pytorch_pod_phase_repeats_on_the_gpu` runs the pod phase twice in
  the released torch-gpu image with CUDA. It checks that predictions and fit
  are bit-identical and that the runtime record reads as a `gpu:` device
  class. Run it on a GPU host with:

      CARBON_REQUIRE_CUDA=1 python -m pytest -q tests/cpu/test_battery_torch_pods.py

## Open

- **The GPU check has not run.** A first real PyTorch pod in the torch-gpu
  image also confirms the code ship's imports there.
- **GPU identity is not measured.** Like the JAX pods, a development rebuild
  is labelled CPU-verified until it is (Test Lead Q6).
