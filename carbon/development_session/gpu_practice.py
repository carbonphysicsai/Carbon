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
#: The PyTorch CUDA runtime is a catalog entry's GPU build (one shared GPU
#: practice path for every Challenge, Lead/owner 2026-10-22): its parent is
#: the pinned PyTorch GPU worker. A runtime listed here is only admissible;
#: a host serves it only when it holds that parent (`DirectParents`).
DIRECT_RUNTIMES = {
    "torch-cpu-py311": "torch_cpu",
    "python-cpu-py311": None,
    "torch-cu130-py311": "pytorch",
    "jax-cuda13-py311": "jax",
}
#: The GPU build a catalog entry may carry (`bundle_refs`), by the GPU
#: backend of the host's declared GPU worker: a PyTorch entry's CUDA build on
#: the PyTorch GPU worker, a JAX entry's on the JAX one (Graphite Test: pick
#: by framework, never assume torch). An entry with no build for the host's
#: GPU runtime practises on CPU.
GPU_RUNTIMES = {"pytorch": "torch-cu130-py311", "jax": "jax-cuda13-py311"}


def gpu_runtime(gpu_image):
    """The catalog GPU build runtime a host's declared GPU worker builds (by
    its backend), or None: the one device choice every Challenge's catalog
    practice makes."""
    return GPU_RUNTIMES.get(gpu_image_backend(gpu_image))


def gpu_images(declared):
    """The host's declared GPU workers as a tuple: one per installed backend
    (Validator ruling: a profile carries one GPU worker per backend). A
    single worker - every profile before that ruling - is a one-element
    tuple; none is empty. Two workers of one backend are refused."""
    if declared is None:
        return ()
    images = tuple(declared) if type(declared) in (tuple, list) else (declared,)
    runtimes = [gpu_runtime(image) for image in images]
    if len(images) > 1 and (None in runtimes or len(set(runtimes)) != len(images)):
        raise ValueError("one registered GPU worker per backend")
    return images


def gpu_runtimes(declared):
    """The catalog GPU build runtime of each declared GPU worker, in order;
    a worker with none (not a registered GPU worker) adds nothing."""
    found = (gpu_runtime(image) for image in gpu_images(declared))
    return tuple(runtime for runtime in found if runtime is not None)


def with_gpu_parent(parents, gpu_image):
    """`parents` plus each declared GPU worker (`gpu_images`) as the parent of
    its GPU build runtime; `parents` unchanged when the host declares none."""
    images = [image for image in gpu_images(gpu_image) if gpu_runtime(image)]
    if not images:
        return parents
    served = {name: parents.for_runtime(name) for name in parents.runtimes()}
    return DirectParents({**served, **{gpu_runtime(image): image for image in images}})


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


#: The miner host's overlay cache bound for GPU builds: the receiver's own
#: (`challenge_validator.receiver_setup.MATERIAL_CACHE_BYTES`), so a GPU
#: practice prepares exactly what a receiver would (one shared path).
MINER_OVERLAY_CACHE_BYTES = 192 * 1024 * 1024


def gpu_overlay(practice, identity, bundle, parent, expanded, kit, limits_document):
    """Stage S2: an entry's GPU build as a verified overlay on the GPU parent,
    prepared in a controlled C-03 operation on the GPU (offline wheels from
    the installed bundle material only) and sealed in the owner cache, as the
    receiver's direct path prepares one. The same for every Challenge."""
    from .bundle_construction_worker import (
        direct_child_identity,
        prepare_library_overlay,
    )
    from .construction_recipe import ConstructionRecipe
    from .library_bundles import (
        load_pinned_bundle_directory,
        verify_bundle_parent_environment,
    )
    from .library_environment_cache import (
        cache_verified_overlay,
        inspect_staged_bundle_material,
    )
    from .research_carrier import MINER_GPU

    directory = inspect_staged_bundle_material(practice.cache_root, bundle)
    material = load_pinned_bundle_directory(directory)
    verify_bundle_parent_environment(material[0], parent)
    prep = prepare_library_overlay(
        practice.ledger,
        owner=practice.owner,
        identity=direct_child_identity(identity, "prep"),
        parent=parent,
        recipe=ConstructionRecipe.from_dict(expanded),
        challenge_binding={
            "challenge_id": kit["id"],
            "challenge_version": kit["version"],
            "train_digest": kit["train_digest"],
            "interface_digest": kit["interface_digest"],
            "construction_limits_digest": kit["construction_limits_digest"],
        },
        limits_document=limits_document,
        material=material,
        accelerator=MINER_GPU,
        runner=practice.runner,
    )
    from .catalog_gpu import RemotePractice

    # A preparation on the miner's own remote GPU (S4) ran in the route's
    # hardened job container, not a local C-03 operation with a controls
    # record; the overlay itself is checked the same way either way.
    if prep.controls_digest is None and type(practice.runner) is not RemotePractice:
        raise ValueError("completed C03 preparation controls unavailable")
    return cache_verified_overlay(
        prep.snapshot,
        practice.cache_root,
        expected_bundle=bundle,
        expected_parent=parent,
        expected_receipt=prep.receipt,
        material_cache_bytes=MINER_OVERLAY_CACHE_BYTES,
    )


def device_build(practice, expand_for, bundle_of, overlay=None):
    """The build one catalog practice runs, chosen by device, the same for
    every Challenge: the entry's GPU build on the host's GPU worker of the
    entry's backend (one per installed backend) when that build is installed
    as a verified overlay, else its CPU build. Returns (expanded, bundle, image, construction_parent,
    accelerator, gpu_note); gpu_note says why a GPU host ran the CPU build
    (`catalog_gpu_build_missing`, `catalog_gpu_build_not_offered`,
    `gpu_overlay_not_installed`, `gpu_build_failed`), None otherwise. Never a score input.
    """
    from carbon.backbone_catalog.served import GpuBuildMissing

    from .library_environment_cache import VerifiedLibraryOverlay
    from .research_carrier import MINER_GPU

    try:
        runtimes = gpu_runtimes(getattr(practice, "gpu_image", None))
    except ValueError:  # no registered GPU worker: CPU, as before
        runtimes = ()
    note = None
    # The entry's GPU build for the backend it has one for, among the host's
    # GPU workers (one per installed backend): a PyTorch entry's twin on the
    # PyTorch worker, a jno.* entry's on the JAX worker. No build for any
    # of them: the typed note, and the CPU build.
    runtime = None
    for candidate in runtimes:
        try:
            expand_for(candidate)
        except GpuBuildMissing as missing:
            note = missing.code
            continue
        except Exception:  # noqa: BLE001 - attempted below, as one GPU attempt
            runtime = candidate
            break
        runtime, note = candidate, None
        break
    if runtime is not None:
        try:
            expanded = expand_for(runtime)
            bundle = bundle_of(expanded["source"]["bundle_ref"])
            parent = practice.parents().for_bundle(bundle)
            try:
                image = practice._resolve(bundle)
            except FileNotFoundError:
                image = None
            if type(image) is not VerifiedLibraryOverlay and overlay is not None:
                # S2: prepared on the GPU, as the receiver prepares one.
                image = overlay(bundle, parent, expanded)
            if type(image) is VerifiedLibraryOverlay:
                return expanded, bundle, image, parent, MINER_GPU, None
            note = "gpu_overlay_not_installed"
        except GpuBuildMissing as missing:
            note = missing.code
        except Exception:  # a GPU attempt never fails the practice
            # Why, in the controller's own log (M1 E2E: a 5090 fell back with
            # no reason anywhere). The note stays the code; the CPU build runs.
            import logging

            logging.getLogger(__name__).warning(
                "catalog GPU build failed for runtime %s; practising the CPU build",
                runtime,
                exc_info=True,
            )
            note = "gpu_build_failed"
    expanded = expand_for(None)
    bundle = bundle_of(expanded["source"]["bundle_ref"])
    image = practice._resolve(bundle)
    return expanded, bundle, image, practice.parents().for_bundle(bundle), None, note
