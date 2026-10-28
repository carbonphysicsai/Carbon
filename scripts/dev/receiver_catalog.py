"""The receiver's catalog: install every served entry, and say whether it is all there.

A submission that names a catalog entry is resolved by the receiver from its own
library cache; an entry that is not installed there is refused
(`direct_reference_not_found`). Day-one step 8a: after `prepare`, run

    python -B -m carbon.challenge_validator.receiver_setup install-catalog \\
        --receiver-state DIR [--wheelhouse DIR]
    python -B -m carbon.challenge_validator.receiver_setup catalog-status \\
        --receiver-state DIR

`install` builds each entry of the receiver's Challenge version that its parents
serve (CPU builds, over the receiver's own construction parents) and stages the
material of every official-grade GPU twin whose GPU worker the receiver has.
`verify` is read-only and is what `receiver_setup status` reads: every served
bundle listed, how many are missing, and `ready` only when none is.

An entry the receiver cannot build is named with its reason and counts as
missing: a receiver is not "ready" for a version it cannot fully serve.

This lives under `scripts/dev`, beside the owner installers it calls, and not in
`carbon.backbone_catalog`: miner paths read the catalog, and nothing they import
may reach these installers or the receiver
(`tests/invariants/test_attack_store_unreachable.py`).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

SCHEMA = "carbon.receiver-catalog.v1"
#: The reasons an entry is missing, closed.
NOT_INSTALLED = "not_installed"
RUNTIME_NOT_SERVED = "runtime_not_served"
GPU_MATERIAL_NOT_STAGED = "gpu_material_not_staged"


def _read_profile(config):
    path = Path(config["runner_profile"])
    profile = json.loads(path.read_bytes())
    if type(profile) is not dict:
        raise ValueError("receiver runner profile must be an object")
    return profile


def cache_root(config) -> Path:
    """Where the receiver itself resolves its library bundles
    (`direct_receiver.installed_source`: the campaigns root's library cache)."""
    profile = _read_profile(config)
    return Path(profile["campaigns_root"]) / ".direct-development" / "library-cache"


def _served_parents(config) -> dict:
    """The exact CPU construction identities selected by the receiver's records."""
    from carbon.development_session.gpu_practice import (
        DirectParents,
        derived_cpu_parent,
        direct_parent_backend,
    )
    from carbon.development_session.library_bundles import SHA256
    from carbon.development_session.research_campaign import (
        digest,
        verify_direct_v13_worker,
    )
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    profile = _read_profile(config)
    paths = profile.get("paths") if isinstance(profile.get("paths"), dict) else {}
    found = {}
    primary_path = config.get("construction_image_manifest") or paths.get(
        "image_manifest"
    )
    try:
        primary = load_image_identity(Path(primary_path))
    except Exception:  # noqa: BLE001 - an unreadable record serves nothing
        return found
    if direct_parent_backend(primary) == "torch_cpu":
        found["torch-cpu-py311"] = primary
        if "construction_runtimes" in config:
            try:
                found["python-cpu-py311"] = derived_cpu_parent(primary)
            except Exception:  # noqa: BLE001, S110 - its CPU parent is then not served
                pass
    else:
        # None is also the backend of an unknown record. Only the existing
        # canonical CPU lock/worker rules can identify the C-03 CPU parent.
        try:
            if primary.lock_digest != digest((REPOSITORY / "uv.lock").read_bytes()):
                return {}
            implementation = profile["runtime"]["implementation"]
            source = implementation["source_tree_digest"]
            if type(source) is not str or SHA256.fullmatch(source) is None:
                return {}
            verify_direct_v13_worker(primary, implementation, role="cpu")
        except (OSError, ValueError, KeyError, TypeError):
            return {}
        found["python-cpu-py311"] = primary
    try:
        DirectParents(found)
    except ValueError:
        return {}
    return found


def served_runtimes(config) -> dict:
    """{bundle runtime: construction parent image id}, from records alone.

    The full CPU mode includes the C-03 parent derived from the PyTorch CPU
    worker. Reading these identities neither inspects nor builds Docker images.
    """
    return {
        runtime: parent.image_id for runtime, parent in _served_parents(config).items()
    }


def gpu_runtimes(config) -> list:
    """The GPU build runtimes the receiver's GPU construction workers serve."""
    from carbon.development_session.gpu_practice import gpu_runtime
    from carbon.reconstruction.worker.docker_runtime import load_image_identity

    if "gpu_construction_images" not in config:
        return []
    declared = config["gpu_construction_images"]
    if type(declared) is not list:
        raise ValueError("configured GPU inventory must be a list")
    runtimes = []
    for path in declared:
        try:
            runtime = gpu_runtime(load_image_identity(Path(path)))
        except Exception as error:
            raise ValueError("configured GPU inventory is unreadable") from error
        if runtime is None or runtime in runtimes:
            raise ValueError("configured GPU inventory is unregistered or duplicated")
        runtimes.append(runtime)
    return runtimes


def served_bundles(config) -> list:
    """Every catalog bundle the receiver of ``config["challenge"]`` must hold:
    each served entry's CPU build, and each of its GPU twins that is
    official-grade (a `repeat` receipt on the pinned worker image, the full
    determinism environment and a registered host class) for a GPU runtime the
    receiver has a worker for. ``[{"catalog_id", "runtime", "kind", "digest"}]``."""
    from carbon.backbone_catalog import gpu_receipt, listing

    challenge = config["challenge"]
    gpus = gpu_runtimes(config)
    rows = []
    for item in listing.entries(challenge["id"], challenge["version"]):
        ref = item["bundle_ref"]
        rows.append(
            {
                "catalog_id": item["catalog_id"],
                "runtime": ref["runtime_profile_id"],
                "kind": "cpu",
                "digest": ref["bundle_digest"],
            }
        )
        for runtime, twin in sorted((item.get("bundle_refs") or {}).items()):
            if runtime not in gpus:
                continue
            try:
                receipt = gpu_receipt.load(item["catalog_id"], runtime)
            except gpu_receipt.GpuReceiptBroken:
                continue
            if gpu_receipt.official_grade_problem(receipt, runtime) is None:
                rows.append(
                    {
                        "catalog_id": item["catalog_id"],
                        "runtime": runtime,
                        "kind": "gpu_twin",
                        "digest": twin["bundle_digest"],
                    }
                )
    return rows


def _missing(row, root, parents, items):
    from carbon.development_session import library_environment_cache as cache
    from carbon.development_session.library_bundles import LibraryBundleRef

    if row["kind"] == "cpu":
        parent = parents.get(row["runtime"])
        if parent is None:
            return RUNTIME_NOT_SERVED
    item = items[row["catalog_id"]]
    selected = LibraryBundleRef.from_dict(
        item["bundle_ref"]
        if row["kind"] == "cpu"
        else item["bundle_refs"][row["runtime"]]
    )
    try:
        if row["kind"] == "cpu":
            receipt, context = cache.library_image_cache_paths(root, selected, parent)
            image = cache.load_cached_library_worker_image(
                receipt,
                expected_bundle=selected,
                expected_parent=parent,
                context_root=context.parent,
            )
            if image.provisioned.context != context:
                return NOT_INSTALLED
        cache.inspect_staged_bundle_material(root, selected)
    except (OSError, ValueError):
        return NOT_INSTALLED if row["kind"] == "cpu" else GPU_MATERIAL_NOT_STAGED
    return None


def verify(config) -> dict:
    """Read-only: every served bundle, which are installed, which are missing and
    why. ``ready`` requires bound cache records, sealed contexts and complete
    staged material for every entry. Runtime image verification remains separate;
    this check never calls Docker."""
    from carbon.backbone_catalog import listing

    root = cache_root(config)
    parents = _served_parents(config)
    rows = served_bundles(config)
    items = {
        item["catalog_id"]: item
        for item in listing.entries(
            config["challenge"]["id"], config["challenge"]["version"]
        )
    }
    missing, bundles = [], []
    for row in rows:
        reason = _missing(row, root, parents, items)
        if reason is not None:
            missing.append({**row, "reason": reason})
        bundles.append(
            {
                "catalog_id": row["catalog_id"],
                "runtime": row["runtime"],
                "kind": row["kind"],
                "installed": reason is None,
            }
        )
    return {
        "schema": SCHEMA,
        "challenge": config["challenge"],
        "served": len(rows),
        "installed": len(rows) - len(missing),
        "missing": missing,
        "ready": bool(rows) and not missing,
        "bundles": bundles,
    }


def install(config, config_path, *, wheelhouse=None) -> dict:
    """Install every served entry that is not installed yet (one entry's failure
    never stops the rest), stage the official GPU twins' material, then verify.
    Returns `verify`'s document plus ``skipped``: what could not be installed and
    why. The caller's exit status is `ready`."""
    from carbon.backbone_catalog import listing, pipeline
    from scripts.dev import catalog_install, library_bundle

    root = cache_root(config)
    parents = _served_parents(config)
    skipped = []
    items = {
        item["catalog_id"]: item
        for item in listing.entries(
            config["challenge"]["id"], config["challenge"]["version"]
        )
    }
    for row in served_bundles(config):
        if _missing(row, root, parents, items) is None:
            continue
        if row["kind"] == "cpu":
            if row["runtime"] not in parents:
                skipped.append({**row, "reason": RUNTIME_NOT_SERVED})
                continue
            try:
                catalog_install.install(
                    [row["catalog_id"]],
                    wheelhouse=wheelhouse,
                    receiver_config=Path(config_path),
                    skipped=skipped,
                )
            # One entry's failure never stops the rest.
            except Exception as failure:  # noqa: BLE001
                skipped.append(
                    {
                        **row,
                        "reason": "install_failed",
                        "detail": f"{type(failure).__name__}: {failure}"[:300],
                    }
                )
            continue
        try:
            with tempfile.TemporaryDirectory() as work:
                directory = pipeline.twin_directory(
                    items[row["catalog_id"]],
                    row["runtime"],
                    Path(work) / "twin",
                    wheelhouse=wheelhouse,
                )
                library_bundle.stage_pinned_bundle_material(directory, root)
        except Exception as failure:  # noqa: BLE001 - one twin never stops the rest
            skipped.append(
                {
                    **row,
                    "reason": GPU_MATERIAL_NOT_STAGED,
                    "detail": f"{type(failure).__name__}: {failure}"[:300],
                }
            )
    return {**verify(config), "skipped": skipped}
