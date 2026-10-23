"""Whether the backbone catalog this install had is installed for its current
construction parents (M1 E2E R7-1).

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
#: What the miner runs to install it (owner-run; never from MCP).
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
    gpu = identity(cfg.get("gpu_image"))
    if gpu is not None:
        runtime = GPU_RUNTIMES.get(direct_parent_backend(gpu))
        if runtime is not None:
            found[runtime] = gpu.image_id
    return found


def state(cfg) -> dict | None:
    """None when this install never had the catalog (nothing staged), else
    {"had": n, "missing": [catalog ids]}: of the n entries it had whose
    runtime this install serves, those with no child for the current
    parent."""
    from carbon.backbone_catalog import pipeline

    root = cache_root(cfg)
    if root is None:
        return None
    materials = root / "materials"
    try:
        staged = {p.name for p in materials.iterdir() if p.is_dir()}
    except OSError:
        return None
    if not staged:
        return None
    served = parents(cfg)
    had, missing = 0, []
    for item in pipeline.load()["entries"]:
        ref = item.get("bundle_ref") or {}
        digest = ref.get("bundle_digest")
        if type(digest) is not str or digest[7:] not in staged:
            continue
        parent = served.get(ref.get("runtime_profile_id"))
        if parent is None:
            continue
        had += 1
        receipt = root / digest[7:] / (parent[7:] + ".image.json")
        if not receipt.is_file():
            missing.append(item["catalog_id"])
    return {"had": had, "missing": missing}
