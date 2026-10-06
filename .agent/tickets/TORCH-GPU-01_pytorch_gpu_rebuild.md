# TORCH-GPU-01: PyTorch GPU rebuilds, battery implementation 2.0

**Status:** implemented on branch `claude/torch-gpu-expansion`, which is
stacked on #684 (`claude/released-worker-images`). Built:
- the PyTorch GPU worker image and its lock;
- battery implementation 2.0 (the CUDA rebuild device) beside the read-only
  1.0 snapshot;
- the device class on every score record, never mixed in a comparison;
- the release tooling and the capability cell.

Nothing is LIVE.

**Primary Hub map_ref:** `SYSTEM/AGENT-EXECUTION`. No Hub source change.

**Authority:**
- OWNER-SHARED-ANSWER-KEY-01: "Pytorch should be able to GPU rebuild too".
- The owner, 2026-10-06, relayed by the Test Engineer:
  - "Commit but it is built to be the version that is ready for main and can
    determine reward. We will work tolerance during testing."
  - Ryan chose option A, a new versioned battery implementation. Every recipe
    identity moves forward, and the 1.0 bytes are kept read-only so run 5 and
    every 1.0 record still verify from main.
  - Ryan approved the constrained cu130 lock.
- OWNER-PYTORCH-BACKEND-01: the PyTorch tolerance is human-reserved.

**Executor:** a Test Engineer sub-session. PR Head merges.

## Built

1. **Lock.** `.devcontainer/torch/torch-cu130-py311.{in,txt}`, with
   `torch-cu130-py311.constraints.txt` (the CPU PyTorch export without torch).
   - It has 71 packages, all hashed. torch is 2.13.0+cu130 and cuDNN is
     9.20.0.48.
   - Every package shared with the CPU PyTorch export is at the identical
     version (tested).
   - The header names repository paths. The resolved content is the Test
     Engineer's resolution, unedited.
2. **Separate image on C-03** (`.devcontainer/torch/Dockerfile.gpu`,
   `scripts/dev/torch_gpu_worker_image.sh`).
   - Why separate: torch cu130 needs cuDNN 9.20 and the JAX CUDA 13 lock pins
     9.12, so the two do not resolve together. JAX's lock and accelerator
     image are untouched.
   - The image is labelled as the JAX accelerator worker is
     (`carbon.accelerator.profile`, `.environment`). Like JAX's, it sets
     nothing the overlay sets (see "One mechanism with JAX").
   - The build refuses on any of these:
     - a changed C-03 distribution;
     - a pin that is off the lock;
     - a label, workspace or device that is not the source's.
3. **Battery implementation 2.0** (`carbon/battery/implementation_versions.py`).
   - `CURRENT = "2.0"`. 1.0's module bytes are a read-only snapshot under
     `carbon/battery/implementation_snapshots/v1/`.
   - A snapshot is refused unless its bytes, its manifest and the digest
     pinned in code all agree, so there is no silent re-pin.
   - `contracts.battery_contracts(implementation)`,
     `compile.compile_recipe(..., implementation=)`,
     `practice.staged_files(..., implementation=)`,
     `worker.reconstruct_files(..., implementation=)` and
     `BatteryScoring.built_record(..., implementation=)` each take a version.
   - **1.0 verifies from main:** its implementation, scaffold recipe, scaffold
     built record and program digests (`LEVEL0_PINS`), and run 5's nine
     recipe digests, all under `implementation="1.0"`.
   - **2.0 moves forward:** `LEVEL0_PINS_V2` sit beside the 1.0 set. Strategy
     hashes are unchanged, and only the two PyTorch modules changed.
4. **The CUDA rebuild path** (`torch_training.py`, `torch_families.py`, 2.0).
   - The device comes from the accelerator overlay's `JAX_PLATFORMS`, as
     JAX's does, never from the recipe.
   - Initialization, minibatch order and the stored state stay on the CPU.
   - CUDA rebuilds run in `torch_gpu.deterministic_cuda`.
   - A missing or unknown device, or an unpinned cuBLAS workspace, raises
     `DeviceUnavailable`. It is an ImportError, which the fixed program
     reports as `stage: environment`: Carbon's failure, never the
     candidate's.
   - On the CPU every change is the identity. A torch-required test rebuilds
     each PyTorch family through the fixed worker program under 1.0 and 2.0
     and requires identical `params_sha256`. It runs in CI only, because this
     host has no torch.
5. **Release:** a `torch-gpu` kind pushed to `carbon-torch-gpu-worker`. The
   runner-disk estimate is a 30-40 GB peak. This is an estimate: use a larger
   runner, or build this image in its own job.
6. **Capability cell.**
   - Imports and lock versions are verifiable on a standard runner.
   - Devices and the GPU profile need a GPU.
   - The rebuild stays UNVERIFIED while the validator's accelerator dispatch
     is disabled (`require_accelerator_admission`, the owner's, as for JAX
     GPU).

## No expansion record 0002 (the Test Lead's ruling (a))

The ruling: skip 0002. Implementation 2.0 is recorded by its implementation
pin (`ImplementationPin("carbon_battery_recipes", "2.0", <digest>)`) and by
this ticket. The registry contract and the battery Level-1 development
policies are untouched. No 0002 record, draft or registry change is on the
branch.

The owner, on what 2.0 is for: "built to be the version that is ready for
main and can determine reward. We will work tolerance during testing."

Why 0002 would have mattered:

A construction expansion record logs a change to the registry contract
document. Recording one with no change is refused. The natural change for
0002 is a `pytorch_cuda` lane (mlp, deeponet, fno), and any registry change
moves the battery contract digest.

`development_variants.check_base` then refuses every registered battery
development variant as `development_variant_base_stale`: Graphite's Level-1
loss-expression policies, signed and unsigned. Those are registered
development policies that the Test Lead reviewed, so rebasing them is not
this ticket's to do.

Implementation 2.0 alone does not stale them: it changes no registry
document.

## Device class: never compared across (the ruling's condition)

CPU and GPU rebuilds of one recipe produce different numbers.
`carbon/battery/rebuild_identity.py` makes this enforceable, which keeps
OWNER-SHARED-ANSWER-KEY-01's "a CPU rebuild is not a scored result" true:
- **Every score record** carries `rebuild`
  (`carbon.battery.rebuild-identity.v1`):
  - the worker image that rebuilt the model;
  - the device class, `cpu` or `gpu:<device name>`.

  It is taken from what the rebuild recorded: the carrier's image and, on a
  GPU, `fit.device_class`.
- **Versioned.** A record made before the field existed keeps its meaning:
  the legacy CPU class with its image unrecorded. Every validator rebuild
  before 2.0 ran on the CPU. Nothing is rewritten.
  - The operator score record is now `carbon.battery.operator-score-record.v2`.
  - The hidden-score operator record and the hidden-pool report are now v2.
- **Never mixed:**
  - nomination refuses an incumbent of another device class (`exam.nominate`);
  - a final whose two rebuilds differ in class is decided INSUFFICIENT and
    promotes nothing;
  - the hidden-pool report ranks per pool version and device class.
- **Tests** (`tests/cpu/test_battery_rebuild_device_class.py`):
  - mixing device classes in a ranking is refused;
  - the mutation that drops the device class reads as CPU, so it is refused
    against a GPU incumbent and never silently compared.

## One mechanism with JAX (the owner, 2026-10-06)

The owner: "I want it to work the same way JAX does. Consistency is key. Other
than that, test and make best decision."

What JAX GPU does today, and what PyTorch GPU now does:

| | JAX GPU (existing) | PyTorch GPU (now) |
|---|---|---|
| Device selection | `accelerators.worker_environment` sets `JAX_PLATFORMS=cuda` | Same overlay, same variable (`torch_gpu.platform`); `CARBON_TORCH_DEVICE` removed |
| Bound device kind | `CARBON_ACCELERATOR_DEVICE_KIND` from the host record; the worker refuses another kind | Same variable; `deterministic_cuda` refuses none or another kind |
| CUDA library controls | `GPU_DETERMINISM_ENVIRONMENT` via the overlay | The same pin via the same overlay; the image no longer sets it |
| Framework controls | `GPU_DETERMINISM_XLA_FLAGS` (env flags) | `GPU_DETERMINISM_TORCH`, beside the XLA flags, applied in process |
| Image identity | labels `carbon.accelerator.profile` + `.environment` | the same two labels; the profile is `torch_profile.GPU_PROFILE_DIGEST` (its document pins the determinism settings) |
| Missing device | `environment_ineligible`, never the candidate's | `DeviceUnavailable` (ImportError: `stage: environment`), never the candidate's |
| Score | GPU practice is speed only; validator dispatch disabled | the same; the validator GPU rebuild stays UNVERIFIED |
| Device class | `device_kind` in backend records | the same field; one rule (`rebuild_identity`) for both |

Engineering decisions (delegated, recorded):
- **J1.** PyTorch reads JAX's `JAX_PLATFORMS`, not a new variable. One
  overlay chooses both, so no setting can make the two backends disagree.
- **J2.** The PyTorch GPU profile is a new document,
  `carbon.accelerator-profile.pytorch.v1`, not JAX's `AcceleratorProfile`.
  That document is JAX's (it names jax and jaxlib), and reusing it would move
  `GPU_PROFILE.digest`. JAX's identities are unchanged; a test holds
  `e1d8aefd…`.
- **J3.** The separate `carbon.torch.gpu-determinism` label is replaced by
  JAX's accelerator label pair. The determinism settings live inside the
  profile, so a changed setting still changes the identity.
- **J4.** Implementation 2.0's pins moved again: the device code changed.
  `LEVEL0_PINS_V2` is updated. 1.0, run 5 and JAX's identities are unchanged.
- **J5.** An EV experiment's retained bundle verifies under any registered
  implementation version. Run-5 bundles made under 1.0 are therefore not
  refused under 2.0.

## Score surfaces (the Test Lead's inventory)

Every surface that ranks, compares or shows battery scores is tabled in
#692's description. Ranking surfaces refuse or split a mixed device-class set,
each with a test and a mutation. Display surfaces are labelled.

Two surfaces are owner-reserved (HUMAN_INPUT) and unchanged:
- **The weights source.** Which device class may earn weight is the owner's.
  The winner is the incumbent, not a ranking.
- **The miner outcome and Launchpad projection.** Adding the class is a
  change to the disclosure allow-list (OWNER-BATTERY-3B-AND-EXPOSURE-01).

A Graphite record made before the field existed reads as `unrecorded`, since
it may have run on a GPU pod, and is compared with nothing.

## Operator note

The implementation digest is a deployment carry-over key. After merge, each
battery deployment needs `python -m carbon.battery.operate upgrade --config
<deployment.json>` before it starts. Admitted submissions are then recompiled
under 2.0, and each recompilation is recorded. Nothing is deleted.

## Owner-reserved (HUMAN_INPUT)

- The PyTorch GPU reproducibility tolerance, to be set during testing.
- Security acceptance of the released digests before mainnet.
- Which device class may earn weight (the weights source), and adding the
  device class to the miner disclosure allow-list.
- Reward and LIVE authority. Agents never flip LIVE. The owner intends this
  path for reward once tolerance and security acceptance are settled.
- Enabling validator accelerator dispatch (JAX and PyTorch).
- GHCR visibility of `carbon-torch-gpu-worker` and package access (Ryan).

The A40 re-run is granted (#681). It should include this image's GPU cell.

## Validation

- Targeted tests:
  - `tests/cpu/test_battery_implementation_versions.py`
  - `tests/cpu/test_battery_level1.py`
  - `tests/cpu/test_battery_graphite_run5_q1.py`
  - `tests/cpu/test_torch_gpu_worker_image.py`
  - `tests/cpu/test_torch_determinism_config.py`
  - `tests/cpu/test_worker_image_capability.py`
  - `tests/cpu/test_release_worker_images_workflow.py`
  - `tests/cpu/test_worker_image_release.py`
  - the battery suites the implementation move could reach
- The three gates.

A probe made one byte change to `torch_training.py` and ran every
battery-related CPU test file. Only the three Level-0/CPU pin tests and run 5
failed, and those are now versioned.

## Maturity

The image tooling and implementation 2.0 are SPECIFIED, IMPLEMENTED and
TESTED. The CUDA numerics have not been run anywhere, because there is no
torch or GPU here. Nothing is qualified.
