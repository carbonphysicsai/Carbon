"""Owner-only, inert cache record for a verified local library worker image.

The record preserves identities from a trusted provisioning result. Reading it
does not establish that an image is still installed or eligible for execution;
the runtime must call ``verify_library_worker_image`` before use.
"""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from dataclasses import asdict
from pathlib import Path

from carbon.development_session.library_bundles import (
    LibraryBundleRef,
    ProvisionedLibraryEnvironment,
    _context_digest,
    _private_cache_directory,
    bundle_ref,
    load_pinned_bundle_directory,
    prepare_offline_context,
    provision_offline_bundle,
)
from carbon.development_session.research_image import (
    LibraryWorkerImage,
    verify_library_worker_image,
)
from carbon.reconstruction.worker.model import WorkerFailure, WorkerImageIdentity

SCHEMA = "carbon.library-worker-image-cache.v1"
MAX_RECORD_BYTES = 64 * 1024
_PARENT_FIELDS = frozenset(
    {
        "image_id",
        "config_digest",
        "source_tree_digest",
        "wheel_digest",
        "lock_digest",
        "base_image_digest",
        "build_recipe_digest",
        "entrypoint_digest",
    }
)
_PROVISIONED_FIELDS = frozenset(
    {"parent_image", "context", "context_digest", "image_id"}
)
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _digest(value: object) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError("closed image digest required")
    return value


def library_image_cache_paths(
    cache_root: Path,
    expected_bundle: LibraryBundleRef,
    trusted_parent: WorkerImageIdentity,
) -> tuple[Path, Path]:
    """Return (private receipt, sealed context) for one exact bundle/parent."""
    if (
        type(expected_bundle) is not LibraryBundleRef
        or type(trusted_parent) is not WorkerImageIdentity
    ):
        raise ValueError("trusted bundle and parent identities are required")
    root = _private_cache_directory(
        cache_root, "private operator-owned bundle cache required"
    )
    context = root / expected_bundle.bundle_digest[7:] / trusted_parent.image_id[7:]
    return context.with_name(context.name + ".image.json"), context


def _controlled_path(path: Path, *, existing: bool) -> Path:
    if not isinstance(path, Path) or not path.is_absolute() or ".." in path.parts:
        raise ValueError("cache path must be absolute and normalized")
    if path.is_symlink() or not path.parent.is_dir():
        raise ValueError("cache path is not owner controlled")
    if path.parent.resolve(strict=True) != path.parent:
        raise ValueError("cache parent contains a link")
    if existing and not path.is_file():
        raise ValueError("cache record is missing")
    if os.name == "posix":
        directory = path.parent.stat()
        if directory.st_uid != os.getuid() or stat.S_IMODE(directory.st_mode) & 0o077:
            raise ValueError("cache parent is not owner-only")
        if existing:
            record = path.stat()
            if record.st_uid != os.getuid() or stat.S_IMODE(record.st_mode) & 0o077:
                raise ValueError("cache record is not owner-only")
    return path


def _context_path(value: Path, root: Path) -> Path:
    if (
        not isinstance(value, Path)
        or not isinstance(root, Path)
        or not value.is_absolute()
        or not root.is_absolute()
        or ".." in value.parts
        or ".." in root.parts
        or not root.is_dir()
        or root.is_symlink()
        or root.resolve(strict=True) != root
        or not value.is_dir()
        or value.is_symlink()
        or value.resolve(strict=True) != value
        or not value.is_relative_to(root)
    ):
        raise ValueError("cached context is outside the installed context root")
    return value


def store_verified_library_worker_image(
    path: Path,
    image: LibraryWorkerImage,
    *,
    context_root: Path,
    cli: object,
) -> None:
    """Persist only a trusted provisioned image after runtime verification.

    ``cli`` is the verifier's Docker adapter; the caller supplies it from the
    trusted owner setup, never from a miner or a cached record.
    """
    path = _controlled_path(path, existing=False)
    if type(image) is not LibraryWorkerImage:
        raise ValueError("expected a provisioned library worker image")
    _digest(image.provisioned.image_id)
    _digest(image.provisioned.context_digest)
    context = _context_path(image.provisioned.context, context_root)
    if _context_digest(context) != image.provisioned.context_digest:
        raise ValueError("provisioned context changed")
    verify_library_worker_image(image, cli)
    record = {
        "schema": SCHEMA,
        "bundle": image.provisioned.bundle.to_dict(),
        "parent": asdict(image.parent),
        "provisioned": {
            "parent_image": image.provisioned.parent_image,
            "context": str(image.provisioned.context),
            "context_digest": image.provisioned.context_digest,
            "image_id": image.provisioned.image_id,
        },
    }
    encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    if len(encoded) > MAX_RECORD_BYTES:
        raise ValueError("cache record exceeds size limit")
    descriptor, temporary = tempfile.mkstemp(prefix=".library-image-", dir=path.parent)
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_cached_library_worker_image(
    path: Path,
    *,
    expected_bundle: LibraryBundleRef,
    expected_parent: WorkerImageIdentity,
    context_root: Path,
) -> LibraryWorkerImage:
    """Rehydrate inert identities bound to independently selected owner state.

    This loader intentionally does not inspect Docker. Its result must be
    checked by ``verify_library_worker_image`` at runtime before execution.
    """
    path = _controlled_path(path, existing=True)
    if (
        type(expected_bundle) is not LibraryBundleRef
        or type(expected_parent) is not WorkerImageIdentity
    ):
        raise ValueError("trusted bundle and parent identities are required")
    if path.stat().st_size > MAX_RECORD_BYTES:
        raise ValueError("cache record exceeds size limit")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid library image cache record") from error
    if type(record) is not dict or frozenset(record) != {
        "schema",
        "bundle",
        "parent",
        "provisioned",
    }:
        raise ValueError("invalid library image cache shape")
    if record["schema"] != SCHEMA:
        raise ValueError("unsupported library image cache version")
    parent = record["parent"]
    provisioned = record["provisioned"]
    if (
        type(parent) is not dict
        or frozenset(parent) != _PARENT_FIELDS
        or type(provisioned) is not dict
        or frozenset(provisioned) != _PROVISIONED_FIELDS
    ):
        raise ValueError("invalid cached image identity")
    try:
        bundle = LibraryBundleRef.from_dict(record["bundle"])
        parent_image = WorkerImageIdentity(**parent)
        context = _context_path(Path(provisioned["context"]), context_root)
        environment = ProvisionedLibraryEnvironment(
            bundle=bundle,
            parent_image=_digest(provisioned["parent_image"]),
            context=context,
            context_digest=_digest(provisioned["context_digest"]),
            image_id=_digest(provisioned["image_id"]),
        )
        if _context_digest(context) != environment.context_digest:
            raise ValueError("cached context changed")
    except (KeyError, TypeError, ValueError, WorkerFailure) as error:
        raise ValueError("invalid cached library worker image") from error
    if (
        bundle != expected_bundle
        or parent_image != expected_parent
        or environment.parent_image != expected_parent.image_id
    ):
        raise ValueError("cached library worker image binding changed")
    return LibraryWorkerImage(environment, parent_image, bundle.to_dict())


def install_pinned_library_worker_image(
    directory: Path,
    cache_root: Path,
    trusted_parent: WorkerImageIdentity,
    *,
    expected_bundle: LibraryBundleRef,
    cli: object,
) -> LibraryWorkerImage:
    """Install or reuse one verified child during an admitted owner setup step.

    This operation can build an image and must not be called from MCP preflight
    or miner-controlled recipe handling. The caller selects the trusted parent
    from maintained installed state and performs host admission first.
    """
    if type(trusted_parent) is not WorkerImageIdentity:
        raise ValueError("trusted installed parent identity required")
    if type(expected_bundle) is not LibraryBundleRef:
        raise ValueError("trusted recipe bundle reference required")
    material = load_pinned_bundle_directory(directory)
    selected = bundle_ref(*material)
    if selected != expected_bundle:
        raise ValueError("recipe bundle reference differs from pinned closure")
    receipt, selected_context = library_image_cache_paths(
        cache_root, selected, trusted_parent
    )
    context, bundle_digest, context_digest = prepare_offline_context(
        cache_root, *material, trusted_parent.image_id
    )
    if bundle_digest != selected.bundle_digest or context != selected_context:
        raise ValueError("prepared bundle identity changed")
    # The receipt is a sibling of the sealed context, never an extra file in it.
    if receipt.exists() or receipt.is_symlink():
        image = load_cached_library_worker_image(
            receipt,
            expected_bundle=selected,
            expected_parent=trusted_parent,
            context_root=context.parent,
        )
        if (
            image.provisioned.context != context
            or image.provisioned.context_digest != context_digest
        ):
            raise ValueError("cached library context differs from selected closure")
        return verify_library_worker_image(image, cli)
    provisioned = provision_offline_bundle(
        cache_root,
        selected.to_dict(),
        *material,
        trusted_parent.image_id,
        cli=cli,
    )
    if (
        type(provisioned) is not ProvisionedLibraryEnvironment
        or provisioned.bundle != selected
        or provisioned.parent_image != trusted_parent.image_id
        or provisioned.context != context
        or provisioned.context_digest != context_digest
    ):
        raise ValueError("provisioned library identity differs")
    image = LibraryWorkerImage(provisioned, trusted_parent, selected.to_dict())
    store_verified_library_worker_image(
        receipt, image, context_root=context.parent, cli=cli
    )
    return image
