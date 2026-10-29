"""Whether the backbone catalog is installed for this install's current
construction parents (M1 E2E R7-1, E2).

`scripts.dev.catalog_install` builds each catalog entry's child image over
its construction parent and stages the entry's material
(`library_bundle.install_bundle`). Practice resolves the child for the
parent this install runs with now, so after an update that rebuilt the
parent (the PyTorch CPU worker, or the C-03 worker it is built from) every
entry was refused `catalog_not_installed`, while setup read done and the
staged material still counted as installed.

Readiness validates the staged material and bound child/context receipts, then
observes distinct immutable child-image IDs with bounded Docker metadata calls.
It builds or downloads nothing; practice still performs its runtime verification.
"""

from __future__ import annotations

from pathlib import Path

#: Each GPU parent's backend and the bundle runtime it serves
#: (`library_bundle.install_bundle`).
GPU_RUNTIMES = {"jax": "jax-cuda13-py311", "pytorch": "torch-cu130-py311"}
#: The explicit manual retry for the owner-run background installer.
INSTALL_COMMAND = "python -m scripts.dev.catalog_install --state-dir {state_dir}"


def cache_root(cfg) -> Path | None:
    root = cfg.get("campaigns_root") if type(cfg) is dict else None
    if type(root) is not str:
        return None
    return Path(root) / ".direct-development" / "library-cache"


def parents(cfg) -> dict:
    """{bundle runtime: immutable identity} of the construction parents the runner
    profile `cfg` names, by `library_bundle.install_bundle`'s own rule."""
    from carbon.development_session.gpu_practice import (
        derived_cpu_parent,
        direct_parent_backend,
    )
    from carbon.reconstruction.worker.docker_runtime import load_image_identity
    from carbon.reconstruction.worker.model import WorkerFailure

    def identity(path):
        if path is None:
            return None
        if type(path) is not str:
            raise ValueError("configured catalog parent path is invalid")
        try:
            return load_image_identity(Path(path))
        except (OSError, ValueError, TypeError, WorkerFailure) as error:
            raise ValueError("configured catalog parent cannot be read") from error

    found = {}
    paths = cfg.get("paths") if type(cfg.get("paths")) is dict else {}
    primary = identity(paths.get("image_manifest"))
    if primary is not None:
        runtime = cfg.get("runtime")
        images = runtime.get("images") if type(runtime) is dict else None
        if type(images) is not list or not images or images[0] != primary.image_id:
            raise ValueError("configured catalog parent differs from runner profile")
        if direct_parent_backend(primary) == "torch_cpu":
            found["torch-cpu-py311"] = primary
            try:
                cpu = derived_cpu_parent(primary)
            except Exception:  # noqa: BLE001 - its CPU parent is then not served
                cpu = None
            if cpu is not None:
                found["python-cpu-py311"] = cpu
        else:
            from carbon.development_session.library_bundles import SHA256
            from carbon.development_session.research_campaign import (
                digest,
                verify_direct_v13_worker,
            )

            repository = Path(__file__).resolve().parents[3]
            if primary.lock_digest != digest((repository / "uv.lock").read_bytes()):
                raise ValueError("configured catalog CPU parent is unknown")
            implementation = cfg["runtime"]["implementation"]
            source = implementation["source_tree_digest"]
            if type(source) is not str or SHA256.fullmatch(source) is None:
                raise ValueError("configured catalog source identity is invalid")
            verify_direct_v13_worker(primary, implementation, role="cpu")
            found["python-cpu-py311"] = primary
    for field in ("gpu_image", "extra_gpu_image"):
        gpu = identity(cfg.get(field))
        if gpu is not None:
            runtime = GPU_RUNTIMES.get(direct_parent_backend(gpu))
            if runtime is None:
                raise ValueError("configured catalog GPU parent is unknown")
            found[runtime] = gpu
    return found


#: The GPU build runtimes (`gpu_practice.GPU_RUNTIMES`), whose twins'
#: material practice prepares a GPU overlay from.
GPU_BUILD_RUNTIMES = frozenset(GPU_RUNTIMES.values())


def _ready(root, item, served, images) -> bool:
    """Whether `item` is installed for this install: its child built over the
    current parent, and, for each GPU worker this install has, its GPU twin's
    material staged where practice prepares the GPU overlay (M1 E2E S4: only
    the CPU build was staged, so every GPU practice fell back to CPU)."""
    from carbon.development_session import library_environment_cache as cache
    from carbon.development_session.library_bundles import LibraryBundleRef

    try:
        selected = LibraryBundleRef.from_dict(item["bundle_ref"])
        parent = served[selected.runtime_profile_id]
        receipt, context = cache.library_image_cache_paths(root, selected, parent)
        image = cache.load_cached_library_worker_image(
            receipt,
            expected_bundle=selected,
            expected_parent=parent,
            context_root=context.parent,
        )
        if image.provisioned.context != context:
            return False
        cache.inspect_staged_bundle_material(root, selected)
        for runtime, twin in (item.get("bundle_refs") or {}).items():
            if runtime in GPU_BUILD_RUNTIMES and runtime in served:
                cache.inspect_staged_bundle_material(
                    root, LibraryBundleRef.from_dict(twin)
                )
    except (OSError, ValueError, KeyError, TypeError):
        return False
    images[item["catalog_id"]] = image.image_id
    return True


class ReadinessUnknown(RuntimeError):
    """The daemon or the install's parents could not be read, so nothing is known about the entries."""


def readiness(cfg, items=None, progress=None, strict=False) -> dict | None:
    """One read-only inventory shared by setup and the Challenge picker. `progress(checked, total)`, when given, is
    called as each entry is checked (and once more when the daemon's images are read); it changes no result.
    A daemon or parent that cannot be read gives every entry False (not installed: fail closed); with `strict`
    it raises `ReadinessUnknown` instead, so a display can say "unknown" and never "nothing installed".
    """
    from carbon.backbone_catalog import listing
    from carbon.development_session.library_environment_cache import (
        present_library_worker_images,
    )
    from carbon.reconstruction.worker.docker_runtime import DockerCLI
    from carbon.reconstruction.worker.model import WorkerFailure

    root = cache_root(cfg)
    if root is None:
        return None
    items = list(listing.load()["entries"] if items is None else items)
    try:
        served = parents(cfg)
    except (OSError, ValueError, KeyError, TypeError, WorkerFailure) as failure:
        if strict:
            raise ReadinessUnknown(type(failure).__name__) from None
        return {item["catalog_id"]: False for item in items}
    selected = [
        item
        for item in items
        if (item.get("bundle_ref") or {}).get("runtime_profile_id") in served
    ]
    images = {}
    found = {}
    total = len(selected) + 1
    for number, item in enumerate(selected, 1):
        found[item["catalog_id"]] = _ready(root, item, served, images)
        if progress is not None:
            progress(number, total)
    if not images:
        return found
    try:
        present = present_library_worker_images(images.values(), cli=DockerCLI())
    except (OSError, ValueError, WorkerFailure) as failure:
        if strict:
            raise ReadinessUnknown(type(failure).__name__) from None
        present = frozenset()
    if progress is not None:
        progress(total, total)
    return {
        identity: ready and images[identity] in present
        for identity, ready in found.items()
    }


def state(cfg) -> dict | None:
    """None without a runner profile's cache, else {"entries": n,
    "missing": [catalog ids]}: of the n entries whose runtime this install
    serves, those with no child for the current parent (an install that
    never had the catalog, or one whose parent an update rebuilt)."""
    found = readiness(cfg)
    if found is None:
        return None
    return {
        "entries": len(found),
        "missing": [key for key, ready in found.items() if not ready],
    }


def progress(cfg, found=None) -> dict | None:
    """How far the catalog is installed for this install's current parents
    (M1 E2E E2): {"total", "installed", "challenges": [{id, version, ready,
    total}]}, over every entry whose runtime this install serves; None
    without a runner profile's cache. A Challenge version can practise a
    catalog backbone as soon as that entry is installed."""
    from carbon.backbone_catalog import listing

    items = listing.load()["entries"]
    if found is None:
        found = readiness(cfg, items)
    if found is None:
        return None
    total = installed = 0
    by_challenge = {}
    for item in items:
        if item["catalog_id"] not in found:
            continue
        ready = found[item["catalog_id"]]
        total += 1
        installed += ready
        for challenge in item.get("challenges") or []:
            key = (challenge.get("id"), challenge.get("version"))
            row = by_challenge.setdefault(key, {"ready": 0, "total": 0})
            row["total"] += 1
            row["ready"] += ready
    return {
        "total": total,
        "installed": installed,
        "challenges": [
            {"id": key[0], "version": key[1], **row}
            for key, row in sorted(by_challenge.items(), key=str)
        ],
    }
