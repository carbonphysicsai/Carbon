# VALIDATOR-27: battery validator scoring on a GPU (valV3, `gpu:NVIDIA A40`)

**Status:** slice 1 (JAX) implemented. The Test Lead approved the plan on
2026-10-08 ("Proceed with VALIDATOR-27"). It goes live only after the A40
acceptance passes and its record enters the hardware acceptance registry.

**Authority:** OWNER-VALV3-GPU-VALIDATOR-01 (2026-10-08). Under C-CORE-19
(GPU `VALIDATOR_RECONSTRUCTION` admission through the host record and
`doctor`) and C-CORE-20 (`reconstruction/validator_launch.py`).

**Executor:** the Carbon Validator session.

## The gap

At main `edf6f1fab`, a battery validator cannot score on a GPU:
- **The deployment** (`carbon/battery/deployment.py`) admits only the
  `carrier` and `direct` backends, and no device key.
- **`CarrierBackend`** (`carbon/battery/worker.py`) launches CPU containers
  only. Its identity has no `device_kind`, so every validator score is device
  class `cpu` (`rebuild_identity.py`).
- **`accelerators.require_accelerator_admission()`** always raises
  `accelerator.dispatch_disabled`.
- **The GPU determinism pins** (`GPU_DETERMINISM_XLA_FLAGS`,
  `GPU_DETERMINISM_ENVIRONMENT`, `GPU_DETERMINISM_TORCH`) are declared. Nothing
  applies them to a validator run or refuses one without them.

## Plan (vertical slices; no second orchestration system)

1. **The deployment selects the device.** An optional deployment key,
   `"device": "gpu"`, is valid only with `carrier`. It requires the
   accelerator `image_manifest` (and `torch_image_manifest` for PyTorch).
   CPU stays the default, and existing deployments are unchanged.
2. **The GPU carrier.** On a `gpu` deployment, `CarrierBackend` launches
   through C-CORE-20's `validator_launch`: the same controller, durable queue
   and launch store, with the device bound from the host record
   (`device_request`).
   - **Its identity carries `device_kind` from the host record,** so scores
     are labelled `gpu:NVIDIA A40`, and `require_one_class` keeps them apart
     from CPU scores.
3. **The pins are enforced, not declared.** A GPU validator run always
   carries the pinned XLA flags, environment and PyTorch settings. A run that
   cannot apply them, or a host whose observed driver or device differs from
   its record, is refused as typed infrastructure (`FAILED_INFRA`), never
   scored.
4. **Admission.** `require_accelerator_admission` admits
   `VALIDATOR_RECONSTRUCTION` only when all of these hold:
   - the host record and `doctor`'s four GPU checks pass;
   - the image is the released accelerator image, pinned;
   - a hardware acceptance record names the device class.

   That record is the A40 acceptance's PASS. Until it exists, admission stays
   disabled for that class: fail closed.
5. **Parity.** CPU deployments rebuild byte-identically to today. GPU tests
   run against a fake device runtime in CI, and against the real A40 only on
   the owner's rental.

## Out of scope

- mainnet hosting;
- other GPU classes;
- any change to the determinism values;
- a GPU producer or bank.

## Maturity ceiling

IMPLEMENTED and TESTED (DEVELOPMENT). Not SCIENTIFICALLY_QUALIFIED or
SECURITY_QUALIFIED. GPU scores are UNVERIFIED until the A40 acceptance.

## Slice 1, as built (JAX GPU)

**A design revision, recorded under delegated engineering authority:**
- C-CORE-20's `validator_launch` runs whole admitted construction-plan
  replicas, not the carrier's source-and-files runs. It is the wrong
  granularity for battery's scored rebuild.
- So the GPU runs through the carrier's existing GPU branch
  (`research_carrier._run_locked(accelerator=…)`). That branch already holds
  everything the lane needs, as the miner lane uses it: the host device
  record, `_check_gpu_host` (the pinned GPU worker's lock and labels, the
  NVIDIA runtime, the doctor's blockers, the device record rechecked before
  dispatch), the device lease, and `create_arguments`.

**What it adds:**
- **`hardware_acceptance.ACCEPTED_DEVICE_CLASSES`:** the device classes a
  validator may score on. It is **empty** until the A40 acceptance passes and
  a reviewed commit enters its class with the owner's record and the
  evidence. `require_accepted` refuses any other class
  (`DeviceClassNotAccepted`).
- **The carrier lane:** `research_carrier.VALIDATOR_GPU` is accepted only for
  the validator's scored rebuild (`BATTERY_VALIDATOR`) on an accepted class.
  - The validator's rebuild never takes the miner lane's GPU.
  - Its worker profile has role `VALIDATOR_RECONSTRUCTION`, which C-CORE-19
    admits on a self-service host.
  - Its request binds the device record's digest.
- **The pins are enforced by construction:** the NVIDIA profile's worker
  environment always carries the pinned XLA flags, `CUBLAS_WORKSPACE_CONFIG`
  and `NVIDIA_TF32_OVERRIDE` (`create_arguments` → `worker_environment`).
  Nothing a caller passes can drop them.
- **`CarrierBackend(device="gpu")`:** its identity carries `device_kind` and
  `device_record`, so every score is `gpu:<kind>` and never ranked with CPU
  scores. A CPU deployment's identity and calls are unchanged.
- **The deployment's `device` key** is `cpu` (default) or `gpu`. A GPU
  deployment is a JAX carrier: no PyTorch image yet, because the
  PyTorch GPU image has its own lock and needs its own pinned-worker check.
  Typed refusals:
  - `evaluation_config_device`;
  - `evaluation_device_class_not_accepted`;
  - `evaluation_device_unavailable`.

**Slice 2 (later):** PyTorch on the validator's GPU, with its own pinned
GPU-worker check.
