"""Whether the backbone catalog is installed for this install's current
construction parents (M1 E2E R7-1, E2).

`scripts.dev.catalog_install` builds each catalog entry's child image over
its construction parent and stages the entry's material
(`library_bundle.install_bundle`). Practice resolves the child for the
parent this install runs with now, so after an update that rebuilt the
parent (the PyTorch CPU worker, or the C-03 worker it is built from) every
entry was refused `catalog_not_installed`, while setup read done and the
staged material still counted as installed.

This reads only files: the staged material (which entries this install had)
and each child's receipt, kept per bundle and per parent
(`library_environment_cache.library_image_cache_paths`). It builds nothing
and reaches no Docker; practice still verifies the image itself.
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


def parents(cfg) -> dict[str, str]:
    """{bundle runtime: image ID} of the construction parents the runner
    profile `cfg` names, by `library_bundle.install_bundle`'s own rule."""
    from carbon.development_session.gpu_practice import (
        derived_cpu_parent,
        direct_parent_backend,
    )
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    def identity(path):
        try:
            return load_image_identity(Path(path)) if type(path) is str else None
        except Exception:  # noqa: BLE001 - a record that cannot be read names none
            return None

    found = {}
    paths = cfg.get("paths") if type(cfg.get("paths")) is dict else {}
    primary = identity(paths.get("image_manifest"))
    if primary is not None:
        if direct_parent_backend(primary) == "torch_cpu":
            found["torch-cpu-py311"] = primary.image_id
            try:
                cpu = derived_cpu_parent(primary)
            except Exception:  # noqa: BLE001 - its CPU parent is then not served
                cpu = None
            if cpu is not None:
                found["python-cpu-py311"] = cpu.image_id
        else:
            found["python-cpu-py311"] = primary.image_id
    for field in ("gpu_image", "extra_gpu_image"):
        gpu = identity(cfg.get(field))
        if gpu is not None:
            runtime = GPU_RUNTIMES.get(direct_parent_backend(gpu))
            if runtime is not None:
                found[runtime] = gpu.image_id
    return found


#: The GPU build runtimes (`gpu_practice.GPU_RUNTIMES`), whose twins'
#: material practice prepares a GPU overlay from.
GPU_BUILD_RUNTIMES = frozenset(GPU_RUNTIMES.values())


def _ready(root, item, served) -> bool:
    """Whether `item` is installed for this install: its child built over the
    current parent, and, for each GPU worker this install has, its GPU twin's
    material staged where practice prepares the GPU overlay (M1 E2E S4: only
    the CPU build was staged, so every GPU practice fell back to CPU)."""
    ref = item.get("bundle_ref") or {}
    digest, parent = ref.get("bundle_digest"), served[ref.get("runtime_profile_id")]
    if not (root / digest[7:] / (parent[7:] + ".image.json")).is_file():
        return False
    for runtime, twin in (item.get("bundle_refs") or {}).items():
        if runtime not in GPU_BUILD_RUNTIMES or runtime not in served:
            continue
        staged = (twin or {}).get("bundle_digest")
        if type(staged) is not str or not (root / "materials" / staged[7:]).is_dir():
            return False
    return True


def state(cfg) -> dict | None:
    """None without a runner profile's cache, else {"entries": n,
    "missing": [catalog ids]}: of the n entries whose runtime this install
    serves, those with no child for the current parent (an install that
    never had the catalog, or one whose parent an update rebuilt)."""
    from carbon.backbone_catalog import listing

    root = cache_root(cfg)
    if root is None:
        return None
    served = parents(cfg)
    entries, missing = 0, []
    for item in listing.load()["entries"]:
        ref = item.get("bundle_ref") or {}
        digest = ref.get("bundle_digest")
        parent = served.get(ref.get("runtime_profile_id"))
        if type(digest) is not str or parent is None:
            continue
        entries += 1
        if not _ready(root, item, served):
            missing.append(item["catalog_id"])
    return {"entries": entries, "missing": missing}


def progress(cfg) -> dict | None:
    """How far the catalog is installed for this install's current parents
    (M1 E2E E2): {"total", "installed", "challenges": [{id, version, ready,
    total}]}, over every entry whose runtime this install serves; None
    without a runner profile's cache. A Challenge version can practise a
    catalog backbone as soon as that entry is installed."""
    from carbon.backbone_catalog import listing

    root = cache_root(cfg)
    if root is None:
        return None
    served = parents(cfg)
    total = installed = 0
    by_challenge = {}
    for item in listing.load()["entries"]:
        ref = item.get("bundle_ref") or {}
        digest, parent = ref.get("bundle_digest"), served.get(
            ref.get("runtime_profile_id")
        )
        if type(digest) is not str or parent is None:
            continue
        ready = _ready(root, item, served)
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
