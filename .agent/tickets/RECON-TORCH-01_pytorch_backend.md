# RECON-TORCH-01 — PyTorch as a reconstruction backend, miner and validator

**Status:** in progress (slice 1).
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
   - Recipes and evidence from before this change keep their digests and
     meaning.
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

## Human-reserved (fail closed until set)

- The PyTorch backend's reproducibility tolerance. The harness produces the
  evidence; the owner sets the value.
- The training limit for PyTorch recipes (OWNER-TRAINING-BUDGET-STUDY-01).
- Security acceptance of the PyTorch worker image.

Until those are set, PyTorch recipes run in DEVELOPMENT only, with no LIVE,
reward or frontier authority.

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
