"""The PyTorch GPU determinism profile, applied (IMAGE-RELEASE-01).

GPU only. It applies `torch_profile.GPU_DETERMINISM` around a PyTorch rebuild
on a CUDA device, and it is the only place the CUDA-only settings (cuDNN
deterministic, no cuDNN benchmark, the fixed cuBLAS workspace) are set. The
CPU rebuild path (`carbon.battery.torch_training`) is untouched, so the battery
contract, its implementation digest and every Level-0 pin stay as they are.

Nothing calls this yet: PyTorch has no CUDA rebuild path. The draft expansion
for one (0002) wires it in. Until then it is the pinned, tested definition the
path will use.

Importing this module never imports torch; `deterministic_cuda` does.
"""

from __future__ import annotations

import contextlib
import os

from carbon.reconstruction.torch_profile import GPU_DETERMINISM

_PINNED = dict(GPU_DETERMINISM)


def worker_environment() -> dict[str, str]:
    """The environment a PyTorch GPU worker must start with. cuBLAS reads its
    workspace setting at initialization, so it is set before the process
    starts, never from inside it."""
    return {"CUBLAS_WORKSPACE_CONFIG": _PINNED["cublas_workspace_config"]}


def state(torch) -> dict[str, object]:
    """The GPU profile's settings as `torch` and the environment report them."""
    return {
        "use_deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "intra_op_threads": torch.get_num_threads(),
        "seed_source": _PINNED["seed_source"],
        "cudnn_deterministic": bool(torch.backends.cudnn.deterministic),
        "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
    }


@contextlib.contextmanager
def deterministic_cuda(torch=None):
    """Every GPU profile setting in force on a CUDA device, restored on exit.

    Refuses rather than skips: no CUDA device, or a cuBLAS workspace that is
    not the pinned one, raises before anything is changed.
    """
    if torch is None:
        import torch
    if not torch.cuda.is_available():
        raise RuntimeError("the PyTorch GPU profile needs a CUDA device")
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != _PINNED["cublas_workspace_config"]:
        raise RuntimeError("the pinned CUBLAS_WORKSPACE_CONFIG is required on CUDA")
    cudnn = torch.backends.cudnn
    saved = (
        torch.are_deterministic_algorithms_enabled(),
        torch.get_num_threads(),
        cudnn.deterministic,
        cudnn.benchmark,
    )
    torch.use_deterministic_algorithms(_PINNED["use_deterministic_algorithms"])
    torch.set_num_threads(_PINNED["intra_op_threads"])
    cudnn.deterministic = _PINNED["cudnn_deterministic"]
    cudnn.benchmark = _PINNED["cudnn_benchmark"]
    try:
        yield state(torch)
    finally:
        torch.use_deterministic_algorithms(saved[0])
        torch.set_num_threads(saved[1])
        cudnn.deterministic, cudnn.benchmark = saved[2], saved[3]
