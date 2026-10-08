# VALIDATOR-27: battery validator scoring on a GPU (valV3, `gpu:NVIDIA A40`)

**Status:** planned. The plan awaits the Test Lead's approval. It goes live
only after the A40 acceptance passes.

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
