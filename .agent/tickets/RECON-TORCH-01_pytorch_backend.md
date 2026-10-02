# RECON-TORCH-01 — PyTorch as a reconstruction backend, miner and validator

**Status:** implemented in bounded DEVELOPMENT scope (slices 1-6); closes on
merge. The human-reserved values below stay open and fail closed.
**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`, `HUB_UPDATE_REQUIRED`.
**Authority:** OWNER-PYTORCH-BACKEND-01 (2026-10-01) and OWNER-DX-03.
**Supersedes, for PyTorch only:** OWNER-BATTERY-TESTNET-02's "Only JAX for
validation" and the battery `pytorch_backend` exclusion.

## Outcome

A battery recipe names its reconstruction backend, `jax` or `pytorch`. The
validator rebuilds it with Carbon's own trainer for that backend, in that
backend's pinned worker image. The prediction format is the same for both
backends. The exam scores both the same way, in one ranking. Miners get the
same PyTorch environment for research and practice.

Miners still submit recipes, never code. A backend choice grants no evaluator
authority (invariant 7.9).

## Seams (from the 2026-10-01 code map)

- **Contract:**
  - `carbon/reconstruction/capability_registry.py`: the battery registry and
    the `pytorch_backend` exclusion.
  - `carbon/battery/contracts.py`: `battery_contracts()`, its environment and
    dependency pins, and the backbone options.
  - `carbon/battery/compile.py`: `compile_recipe`, `BatteryRecipe` and
    `rebuild_issues`.
  - The append-only expansion record
    `carbon/reconstruction/expansions/battery-fastcharge-ageing-development-v1/0001.json`.
- **Training:** `carbon/battery/recipes.py` and `training.py` (JAX). They gain
  a PyTorch sibling with its own model-state kind.
- **Validator:**
  - `carbon/battery/worker.py`: the fixed programs and `CarrierBackend`.
  - `carbon/battery/deployment.py`: today one image per validator; this
    becomes one image per backend.
  - `carbon/battery/daemon.py`: identities and dispatch.
- **Image:** `.devcontainer/Dockerfile.reconstruction-worker` and
  `scripts/dev/c03_worker_image.sh`, plus a PyTorch variant built from the
  exact-pinned `science-torch` group.
- **Miner:**
  - `carbon/development_session/research_image.py`: its parent becomes the
    PyTorch worker image.
  - `carbon/battery/research.py`: practice.
  - `carbon/challenge_kit/standard.py`: the declared provisions.
- **Disclosure:**
  - `carbon/challenge_registry/battery.py` and `registry.py`;
  - `carbon/development_session/exam_environment.py`;
  - `docs/development/DECLARATIVE_CONSTRUCTION_MAP.md` and
    `VALIDATOR_EXAM_ENVIRONMENT.md`.

## Slices (one PR unless a real dependency forces a split)

1. **Decision, ticket and Hub mapping.**
2. **The backend in the contract.**
   - A `reconstruction.backend` surface: `jax` (the default) or `pytorch`.
   - The battery `pytorch_backend` capability moves from excluded to
     supported, with expansion record `0001`.
   - A PyTorch environment pin and dependency pins.
   - Per-backend admission rules. A setting the chosen backend cannot rebuild
     is refused by name.
   - Strategy hashes are unchanged, and JAX recipes rebuild with the same
     numerics. Plan and recipe digests bind the contract document, so a
     recompile under expansion `0001` gets new ones, as on every contract
     revision. Retained evidence keeps the contract digest it recorded.
3. **The PyTorch battery trainer.**
   - Carbon-owned PyTorch training for the battery families: `mlp`,
     `deeponet` and `knn` (which needs no framework).
   - PyTorch-only families from the locked `neuraloperator`, starting with a
     1D Fourier neural operator over the time grid.
   - Optimizers, schedules, losses, stages and averaging mapped wherever
     PyTorch provides them; anything else refused by name.
   - Deterministic CPU settings: `torch.use_deterministic_algorithms`, seeded
     generators and fixed thread counts.
   - The same prediction format.
   - A PyTorch model-state kind (`safetensors`-free: tensors exported to npz
     with a JSON header, no pickle).
4. **The validator image and dispatch.**
   - A PyTorch worker image (Dockerfile variant, build script and manifest).
   - The deployment config names one image per backend.
   - The carrier picks the image by the recipe's backend.
   - The worker environment sets the PyTorch thread variables.
   - Daemon identities record the backend.
5. **The miner side.**
   - The analysis image is built on the PyTorch worker.
   - Practice runs in the recipe's backend.
   - The standard and the research environment provisions say so.
6. **Determinism harness, disclosure, docs, Hub and PR.**
   - A repeat-and-compare harness for the PyTorch backend: same recipe,
     same seed, N rebuilds, and an exact-difference report.
   - The exam environment discloses both backend profiles.

## Owner decisions after delivery (OWNER-BATTERY-CARRYOVER-01, 2026-10-01)

- PyTorch runs with the same standing as JAX. The reproducibility tolerance,
  the training limit and the image's acceptance are analysed in tandem with
  testing; they are no longer holds. Battery stays a DEVELOPMENT, non-paying
  Challenge.
- The determinism harness (`python -m carbon.battery.torch_determinism`) is
  the evidence for that analysis.

## Operational note: contract revisions and admitted submissions

The daemon binds the contract and implementation it started with. Under
OWNER-BATTERY-CARRYOVER-01 an operator carries a deployment over a revision
with `python -m carbon.battery.operate upgrade --config <deployment>`:

- the incumbent, retained models, scores and pool stay; incumbents stay
  winners;
- a recipe admitted under a recorded earlier contract is recompiled under the
  current one, and each recompile is recorded;
- one the current contract refuses is closed as `contract_revised`, never
  scored, and a final whose side the current contract refuses keeps the
  incumbent;
- a changed exam rule, public material or seed pin is still refused.

## Engineering decisions (recorded under OWNER-DX-03)

- The FNO family is PyTorch-only and float32-only. neuraloperator's spectral
  weights are complex64, and a float64 cast would drop the imaginary part.
  Both refusals name the field.
- Carbon holds each complex FNO weight as its real view, a trailing axis of
  (real, imaginary). Every optimizer and the stored state then see real
  tensors only.
- CI installs `science-torch` in the canonical and dev-image jobs, and
  `CARBON_REQUIRE_TORCH=1` turns PyTorch skips into failures there.
- The PyTorch worker image follows the accelerator image's pattern: layered on
  the exact C-03 image, installing the checked-in exact-hashed export
  `.devcontainer/torch/torch-cpu-py311.txt`. A deployment refuses a PyTorch
  manifest whose base is not its JAX image or whose lock digest is not that
  export's.
- A validator without a PyTorch image raises `BackendNotServed` at admission.
  It is answered `backend_not_served` and records nothing, so the miner is
  never charged with it. A worker image that lacks the recipe's backend reports
  the `environment` stage, which is infrastructure.
- Miners use the PyTorch worker image as their worker `image_manifest`. It
  keeps the C-03 source identity, and the analysis image is built on it.
- The public execution-profile id `jax-cpu/isolated-carrier` is unchanged
  (AGENTS section 12); only its description names both backends.

## Known environment limit (2026-10-01)

This cloud session's network policy denies `download.pytorch.org`, the host
the locked CPU wheels come from. Images are built on the owner's host. Local
tests here use the same torch version from PyPI, as a diagnostic only.

## Definition of Done

- A PyTorch recipe is admitted, rebuilt and scored end to end in the battery
  validator path (carrier or direct). It is tested with a fixture worker
  where Docker is unavailable.
- JAX recipes, their digests and retained evidence are unchanged, and a test
  holds that.
- The miner research image and practice support PyTorch recipes.
- No test that blocks eager torch imports is weakened. PyTorch loads only
  inside the PyTorch backend.
- Docs, disclosure and Hub are updated. CI is green.
