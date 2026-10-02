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
    from carbon.reconstruction.accelerators import GPU_PROFILE
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    return (
        type(image) is WorkerImageIdentity
        and image.lock_digest == GPU_PROFILE.environment_lock_digest
    )
