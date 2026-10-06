"""PyTorch on the NVIDIA accelerator lane, the way JAX runs there (TORCH-GPU-01).

The owner (2026-10-06): "I want it to work the same way JAX does." So a
PyTorch GPU rebuild uses JAX's accelerator mechanism, generalised, and nothing
parallel:

- **Device selection.** The controller's `accelerators.worker_environment`
  overlay chooses the platform with `JAX_PLATFORMS` (`cuda` on the NVIDIA lane,
  `cpu` otherwise, as the C-03 image's default). PyTorch reads the same
  variable (`platform`).
- **Expected device.** The same overlay names the device kind the run is bound
  to (`CARBON_ACCELERATOR_DEVICE_KIND`, from the installed host record). JAX's
  worker refuses a backend reporting another kind
  (`accelerators.validate_worker_observation`); PyTorch's does the same
  (`expected_device_kind`).
- **Determinism.** The CUDA library controls are JAX's
  (`accelerators.GPU_DETERMINISM_ENVIRONMENT`), delivered by the same overlay
  and checked present. PyTorch's in-process controls
  (`accelerators.GPU_DETERMINISM_TORCH`) sit beside JAX's XLA flags and are
  applied here, because PyTorch takes them in process rather than as flags.
- **A missing device** is the environment's failure, never the candidate's,
  as `reconstruction.runtime.environment_ineligible` is for JAX.

Importing this module never imports torch.
"""

from __future__ import annotations

import contextlib
import os

from carbon.reconstruction.accelerators import (
    GPU_DETERMINISM_ENVIRONMENT,
    GPU_DETERMINISM_TORCH,
)
from carbon.reconstruction.torch_profile import CPU_DETERMINISM

PLATFORM_ENV = "JAX_PLATFORMS"
DEVICE_KIND_ENV = "CARBON_ACCELERATOR_DEVICE_KIND"
PLATFORMS = ("cpu", "cuda")
_IN_PROCESS = dict(GPU_DETERMINISM_TORCH)
_THREADS = dict(CPU_DETERMINISM)["intra_op_threads"]


class EnvironmentIneligible(RuntimeError):
    """The accelerator environment this worker was given is not usable."""


def platform(environ=None) -> str:
    """The platform the overlay chose: `cpu` (the default) or `cuda`."""
    environ = os.environ if environ is None else environ
    name = environ.get(PLATFORM_ENV, "cpu") or "cpu"
    if name not in PLATFORMS:
        raise EnvironmentIneligible("unknown accelerator platform " + name)
    return name


def worker_environment() -> dict[str, str]:
    """The CUDA library controls a GPU worker starts with: JAX's own."""
    return dict(GPU_DETERMINISM_ENVIRONMENT)


def expected_device_kind(environ=None) -> str:
    environ = os.environ if environ is None else environ
    kind = environ.get(DEVICE_KIND_ENV, "")
    if not kind:
        raise EnvironmentIneligible("the run is bound to no device kind")
    return kind


def state(torch) -> dict[str, object]:
    """The PyTorch GPU determinism settings in force, keyed as pinned."""
    return {
        "use_deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "intra_op_threads": torch.get_num_threads(),
        "seed_source": dict(CPU_DETERMINISM)["seed_source"],
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        **{
            "environment:" + key: os.environ.get(key)
            for key in sorted(GPU_DETERMINISM_ENVIRONMENT)
        },
    }


@contextlib.contextmanager
def deterministic_cuda(torch=None):
    """The pinned GPU determinism in force on the bound CUDA device, restored
    on exit. Refuses, before anything changes, a missing device, a device of
    another kind than the run is bound to, or a missing pinned control."""
    if torch is None:
        import torch
    if not torch.cuda.is_available():
        raise EnvironmentIneligible("the run needs a CUDA device")
    if any(os.environ.get(k) != v for k, v in GPU_DETERMINISM_ENVIRONMENT.items()):
        raise EnvironmentIneligible("the pinned CUDA library controls are not set")
    kind = expected_device_kind()
    if torch.cuda.get_device_name(0) != kind:
        raise EnvironmentIneligible("the device is not the kind the run is bound to")
    cudnn = torch.backends.cudnn
    saved = (
        torch.are_deterministic_algorithms_enabled(),
        torch.get_num_threads(),
        cudnn.deterministic,
        cudnn.benchmark,
    )
    torch.use_deterministic_algorithms(_IN_PROCESS["use_deterministic_algorithms"])
    torch.set_num_threads(_THREADS)
    cudnn.deterministic = _IN_PROCESS["cudnn_deterministic"]
    cudnn.benchmark = _IN_PROCESS["cudnn_benchmark"]
    try:
        yield state(torch)
    finally:
        torch.use_deterministic_algorithms(saved[0])
        torch.set_num_threads(saved[1])
        cudnn.deterministic, cudnn.benchmark = saved[2], saved[3]
