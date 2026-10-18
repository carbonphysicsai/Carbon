"""What every Challenge's GPU practice shares (C-MLP-04).

A Challenge's own GPU practice scope (battery's is
`carbon.development_session.battery_gpu`) binds its own program and files.
Two things are the same for all of them, and the Control Center reads them
here so it never imports a Challenge's module:

- the pinned GPU worker image, recognised by its lock digest
  (`scripts/dev/accelerator_worker_image.sh`);
- what GPU practice is for: speed only. The validator rebuilds every
  submitted recipe on its own pinned backend and resources.
"""

from __future__ import annotations

SPEED_ONLY = (
    "GPU practice is for speed only. The validator rebuilds your recipe on its "
    "own pinned backend and resources; nothing measured here is scored."
)


def is_gpu_image(image):
    """Whether `image` is the pinned GPU worker (its lock is the GPU profile's)."""
    return gpu_image_backend(image) == "jax"


def gpu_image_backend(image):
    """The backend of an exact registered GPU worker; unknown images refuse.

    Legacy callers of is_gpu_image remain JAX-only. Challenges explicitly
    choose whether they serve the sibling PyTorch worker.
    """
    from carbon.reconstruction import torch_profile
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    if type(image) is not WorkerImageIdentity:
        return None
    if image.lock_digest == GPU_PROFILE.environment_lock_digest:
        return "jax"
    if image.lock_digest == torch_profile.GPU_LOCK_DIGEST:
        return "pytorch"
    return None


def direct_bundle_accelerator(construction_parent, inference_image):
    """Select one control for the already-verified direct build/infer image pair.

    The normal bundle route sends the same accelerator to both phases. A GPU
    constructor paired with a CPU inference worker cannot make a CUDA predict
    result, so refuse that pair before reserving either phase. Image admission
    and Docker doctor remain the private receiver's responsibility.
    """
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    from .research_carrier import MINER_GPU

    if (
        type(construction_parent) is not WorkerImageIdentity
        or type(inference_image) is not WorkerImageIdentity
    ):
        raise ValueError("exact direct worker image pair required")
    build_backend = gpu_image_backend(construction_parent)
    infer_backend = gpu_image_backend(inference_image)
    if build_backend != infer_backend:
        raise ValueError("direct build and inference accelerator backends differ")
    return MINER_GPU if build_backend is not None else None
