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


def direct_parent_backend(image):
    """Recognize the separate pinned Torch CPU construction parent."""
    backend = gpu_image_backend(image)
    if backend is not None:
        return backend
    from pathlib import Path

    from carbon.reconstruction import torch_profile
    from carbon.reconstruction.worker.model import WorkerImageIdentity

    if type(image) is not WorkerImageIdentity:
        return None
    root = Path(__file__).resolve().parents[2]
    if image.lock_digest == torch_profile.requirements_digest(root):
        return "torch_cpu"
    return None


def direct_bundle_accelerators(construction_parent, inference_image):
    """Select independent controls for the verified build and inference images.

    The fixed inference program uses JAX, including for a graph built with
    PyTorch. The separate PyTorch CUDA image does not carry the JAX runtime.
    Image admission and Docker doctor remain the private receiver's duty.
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
    if infer_backend == "pytorch":
        raise ValueError("fixed direct inference requires JAX worker")
    return (
        MINER_GPU if build_backend is not None else None,
        MINER_GPU if infer_backend == "jax" else None,
    )


#: The pinned base of the C-03 CPU worker (`scripts/dev/c03_worker_image.sh`).
C03_BASE_IMAGE_DIGEST = (
    "sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517"
)
#: The construction runtimes a direct bundle may name, each with the parent
#: backend that builds it (OWNER-BACKBONE-CATALOG-01, Validator 2026-10-20).
DIRECT_RUNTIMES = {"torch-cpu-py311": "torch_cpu", "python-cpu-py311": None}


class DirectParentRefused(ValueError):
    """A bundle runtime with no parent here: REFUSED when no such runtime is
    registered, GAP `backend_not_served` when its parent is not installed."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def derived_cpu_parent(torch_identity):
    """The C-03 CPU worker the pinned PyTorch CPU worker was built FROM.

    `scripts/dev/torch_worker_image.sh` builds the Torch image on the CPU
    worker and `.devcontainer/torch/cpu_image_identity.record` keeps the
    parent's build record, overwriting only its base (the parent's id), recipe
    and lock. The parent is those three restored: never a separate profile
    field. Docker `doctor` then checks every label against the real image, so
    a wrong derivation fails closed.
    """
    import hashlib
    from pathlib import Path

    from carbon.reconstruction.worker.model import WorkerImageIdentity

    if direct_parent_backend(torch_identity) != "torch_cpu":
        raise DirectParentRefused("backend_not_served")
    root = Path(__file__).resolve().parents[2]

    def digest(path):
        return "sha256:" + hashlib.sha256((root / path).read_bytes()).hexdigest()

    return WorkerImageIdentity(
        image_id=torch_identity.base_image_digest,
        config_digest=torch_identity.base_image_digest,
        source_tree_digest=torch_identity.source_tree_digest,
        wheel_digest=torch_identity.wheel_digest,
        lock_digest=digest("uv.lock"),
        base_image_digest=C03_BASE_IMAGE_DIGEST,
        build_recipe_digest=digest(".devcontainer/Dockerfile.reconstruction-worker"),
        entrypoint_digest=torch_identity.entrypoint_digest,
    )


class DirectParents:
    """The construction parent for each bundle runtime, chosen only from the
    bundle's pinned runtime (never from a recipe field or miner input)."""

    def __init__(self, parents):
        if type(parents) is not dict or set(parents) - set(DIRECT_RUNTIMES):
            raise ValueError("direct parents name registered runtimes only")
        for runtime, image in parents.items():
            if direct_parent_backend(image) != DIRECT_RUNTIMES[runtime]:
                raise ValueError("direct parent differs from its runtime")
        self._parents = dict(parents)

    @classmethod
    def from_torch(cls, torch_identity):
        """Both CPU parents from the pinned PyTorch CPU worker."""
        return cls(
            {
                "torch-cpu-py311": torch_identity,
                "python-cpu-py311": derived_cpu_parent(torch_identity),
            }
        )

    def runtimes(self):
        return tuple(sorted(self._parents))

    def for_runtime(self, runtime):
        if runtime not in DIRECT_RUNTIMES:
            raise DirectParentRefused("construction_runtime_unknown")
        if runtime not in self._parents:
            raise DirectParentRefused("backend_not_served")
        return self._parents[runtime]

    def for_bundle(self, bundle_ref):
        return self.for_runtime(getattr(bundle_ref, "runtime_profile_id", None))

    def identities(self):
        """Each runtime's parent, as the receiver's binding records it."""
        from dataclasses import asdict

        return {
            runtime: asdict(image) for runtime, image in sorted(self._parents.items())
        }
