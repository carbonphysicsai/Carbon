"""Owner-only, inert cache record for a verified local library worker image.

The record preserves identities from a trusted provisioning result. Reading it
does not establish that an image is still installed or eligible for execution;
the runtime must call ``verify_library_worker_image`` before use.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from carbon.development_session.library_bundles import (
    UV_IMAGE,
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
from carbon.reconstruction.worker.docker_runtime import DockerCLI
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
OVERLAY_SCHEMA = "carbon.development.library-overlay.v1"
MAX_OVERLAY_BYTES = 128 * 1024**2 - 64 * 1024
MAX_OVERLAY_FILES = 8192


@dataclass(frozen=True)
class VerifiedLibraryOverlay:
    path: Path
    tree_digest: str
    bundle_ref: LibraryBundleRef
    parent_image_id: str
    archive_digest: str
    file_count: int
    total_bytes: int


def pinned_uv_bytes(cli: DockerCLI) -> bytes:
    """Copy /uv from the exact locally pinned image without starting it."""
    if not all(hasattr(cli, name) for name in ("json", "run", "stream_to_file")):
        raise ValueError("trusted Docker adapter required")
    image = cli.json(["image", "inspect", UV_IMAGE, "--format", "{{json .}}"])
    uv_name, _, uv_digest = UV_IMAGE.partition("@")
    repository_digest = uv_name.rsplit(":", 1)[0] + "@" + uv_digest
    if (
        type(image) is not dict
        or _DIGEST.fullmatch(str(image.get("Id"))) is None
        or type(image.get("RepoDigests")) is not list
        or repository_digest not in image.get("RepoDigests", ())
    ):
        raise ValueError("pinned local uv image differs")
    intent = secrets.token_hex(16)
    name = "carbon-overlay-uv-" + intent
    label = "org.carbonphysicsai.overlay-uv-intent"
    created = False

    def owned(held):
        return (
            type(held) is dict
            and held.get("Name") == "/" + name
            and held.get("Image") == image["Id"]
            and re.fullmatch(r"[0-9a-f]{64}", str(held.get("Id"))) is not None
            and type(held.get("Config")) is dict
            and type(held["Config"].get("Labels")) is dict
            and held["Config"]["Labels"].get(label) == intent
        )

    try:
        container = (
            cli.run(
                [
                    "create",
                    "--name",
                    name,
                    "--label",
                    f"{label}={intent}",
                    "--network",
                    "none",
                    "--entrypoint",
                    "/bin/true",
                    image["Id"],
                ]
            )
            .stdout.decode("ascii")
            .strip()
        )
        created = True
        if re.fullmatch(r"[0-9a-f]{64}", container) is None:
            raise ValueError("pinned uv container identity invalid")
        held = cli.json(["container", "inspect", name, "--format", "{{json .}}"])
        if not owned(held) or held["Id"] != container:
            raise ValueError("pinned uv container identity differs")
        with tempfile.TemporaryDirectory(prefix="carbon-uv-copy-") as temporary:
            archive_path = Path(temporary) / "uv.tar"
            cli.stream_to_file(
                ["cp", f"{container}:/uv", "-"],
                archive_path,
                maximum=64 * 1024**2 + 1024**2,
                timeout=120,
            )
            with tarfile.open(archive_path, mode="r:") as archive:
                members = archive.getmembers()
                if (
                    len(members) != 1
                    or members[0].name not in {"uv", "./uv"}
                    or not members[0].isfile()
                    or not 0 < members[0].size <= 64 * 1024**2
                ):
                    raise ValueError("pinned uv archive differs")
                stream = archive.extractfile(members[0])
                if stream is None:
                    raise ValueError("pinned uv bytes unavailable")
                body = stream.read(64 * 1024**2 + 1)
                if len(body) != members[0].size:
                    raise ValueError("pinned uv bytes changed")
                return body
    finally:
        try:
            held = cli.json(["container", "inspect", name, "--format", "{{json .}}"])
        except WorkerFailure:
            if created:
                raise ValueError("owned uv cleanup identity unavailable") from None
        else:
            if not owned(held):
                raise ValueError("owned uv cleanup identity differs")
            cli.run(["rm", "--force", held["Id"]])


def staged_bundle_material_directory(
    cache_root: Path, expected_bundle: LibraryBundleRef
) -> Path:
    """Locate owner-staged source bytes by recipe digest, never by a miner path."""
    if type(expected_bundle) is not LibraryBundleRef:
        raise ValueError("closed recipe bundle reference required")
    root = Path(cache_root) / "materials"
    if not root.is_dir():
        raise FileNotFoundError("pinned bundle material is not staged")
    root = _private_cache_directory(root, "private staged bundle root required")
    return root / expected_bundle.bundle_digest[7:]


def inspect_staged_bundle_material(
    cache_root: Path, expected_bundle: LibraryBundleRef
) -> Path:
    """Check the complete declared closure without creating an image or receipt."""
    directory = staged_bundle_material_directory(cache_root, expected_bundle)
    if not directory.exists() and not directory.is_symlink():
        raise FileNotFoundError("pinned bundle material is not staged")
    material = load_pinned_bundle_directory(directory)
    if bundle_ref(*material) != expected_bundle:
        raise ValueError("staged bundle differs from recipe reference")
    return directory


def _overlay_digest(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _overlay_rows(root: Path) -> list[list[object]]:
    rows: list[list[object]] = []
    total = 0
    for entry in root.rglob("*"):
        if entry == root / ".overlay.json":
            continue
        if entry.is_symlink():
            raise ValueError("overlay link refused")
        if entry.is_dir():
            continue
        relative = entry.relative_to(root).as_posix()
        parts = PurePosixPath(relative).parts
        if (
            not entry.is_file()
            or len(parts) < 2
            or parts[0] not in {"site-packages", "source"}
            or any(part in {"", ".", ".."} for part in parts)
            or "\\" in relative
            or ":" in relative
        ):
            raise ValueError("overlay file role differs")
        size = entry.stat().st_size
        if size > MAX_OVERLAY_BYTES:
            raise ValueError("overlay file exceeds bound")
        hasher = hashlib.sha256()
        with entry.open("rb") as stream:
            for block in iter(lambda: stream.read(1024**2), b""):
                hasher.update(block)
        total += size
        rows.append([relative, size, "sha256:" + hasher.hexdigest()])
        if total > MAX_OVERLAY_BYTES or len(rows) > MAX_OVERLAY_FILES:
            raise ValueError("overlay content exceeds bound")
    rows.sort(key=lambda row: row[0])
    if len({row[0].casefold() for row in rows}) != len(rows):
        raise ValueError("overlay file names collide")
    return rows


def _verified_overlay_tree(root: Path, receipt: dict) -> None:
    stored = root / ".overlay.json"
    if stored.is_symlink() or not stored.is_file() or stored.stat().st_size > 65536:
        raise ValueError("cached overlay receipt differs")
    if json.loads(stored.read_bytes()) != receipt:
        raise ValueError("cached overlay receipt changed")
    rows = _overlay_rows(root)
    if (
        _overlay_digest(json.dumps(rows, separators=(",", ":")).encode())
        != receipt["tree_digest"]
        or len(rows) != receipt["file_count"]
        or sum(row[1] for row in rows) != receipt["total_file_bytes"]
    ):
        raise ValueError("cached overlay content differs")


def _cache_verified_overlay_locked(
    snapshot: Path,
    cache_root: Path,
    *,
    expected_bundle: LibraryBundleRef,
    expected_parent: WorkerImageIdentity,
    expected_receipt: dict,
    material_cache_bytes: int,
) -> VerifiedLibraryOverlay:
    """Verify bounded C03 output and atomically seal an inert private overlay."""
    if (
        not isinstance(snapshot, Path)
        or not snapshot.is_absolute()
        or snapshot.is_symlink()
        or not snapshot.is_dir()
        or type(expected_bundle) is not LibraryBundleRef
        or type(expected_parent) is not WorkerImageIdentity
        or type(expected_receipt) is not dict
    ):
        raise ValueError("trusted completed preparation required")
    entries = {entry.name: entry for entry in snapshot.iterdir()}
    if set(entries) != {"overlay.json", "overlay.tar"} or any(
        entry.is_symlink() or not entry.is_file() for entry in entries.values()
    ):
        raise ValueError("closed preparation snapshot required")
    manifest_path = entries["overlay.json"]
    archive_path = entries["overlay.tar"]
    if (
        not 0 < manifest_path.stat().st_size <= 65536
        or not 0 < archive_path.stat().st_size <= MAX_OVERLAY_BYTES
    ):
        raise ValueError("bounded preparation output required")
    try:
        receipt = json.loads(manifest_path.read_bytes())
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid preparation receipt") from error
    if (
        type(receipt) is not dict
        or receipt != expected_receipt
        or set(receipt)
        != {
            "schema",
            "bundle_ref",
            "parent_image_id",
            "archive_sha256",
            "archive_bytes",
            "tree_digest",
            "file_count",
            "total_file_bytes",
        }
        or receipt["schema"] != OVERLAY_SCHEMA
        or receipt["bundle_ref"] != expected_bundle.to_dict()
        or receipt["parent_image_id"] != expected_parent.image_id
        or _DIGEST.fullmatch(str(receipt["archive_sha256"])) is None
        or _DIGEST.fullmatch(str(receipt["tree_digest"])) is None
        or type(receipt["archive_bytes"]) is not int
        or receipt["archive_bytes"] != archive_path.stat().st_size
        or type(receipt["file_count"]) is not int
        or not 1 <= receipt["file_count"] <= MAX_OVERLAY_FILES
        or type(receipt["total_file_bytes"]) is not int
        or not 1 <= receipt["total_file_bytes"] <= MAX_OVERLAY_BYTES
    ):
        raise ValueError("preparation receipt binding differs")
    hasher = hashlib.sha256()
    with archive_path.open("rb") as archive_bytes:
        for block in iter(lambda: archive_bytes.read(1024**2), b""):
            hasher.update(block)
    if "sha256:" + hasher.hexdigest() != receipt["archive_sha256"]:
        raise ValueError("preparation archive digest differs")
    root = _private_cache_directory(cache_root, "private overlay cache required")
    overlays = root / "overlays"
    overlays.mkdir(mode=0o700, exist_ok=True)
    overlays = _private_cache_directory(overlays, "private overlay root required")
    # The same extracted tree may belong to different pinned bundles or
    # parents. Keep the immutable preparation receipt in the CAS identity.
    bucket = overlays
    for identity in (
        expected_bundle.bundle_digest,
        expected_parent.image_id,
        receipt["archive_sha256"],
    ):
        child = bucket / identity[7:]
        child.mkdir(mode=0o700, exist_ok=True)
        bucket = _private_cache_directory(child, "private overlay binding required")
    target = bucket / receipt["tree_digest"][7:]
    from .direct_material_staging import _cache_bytes

    retained = _cache_bytes(root)
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_dir():
            raise ValueError("cached overlay path differs")
        if retained > material_cache_bytes:
            raise ValueError("operator material and overlay cache capacity exceeded")
        _verified_overlay_tree(target, receipt)
        return VerifiedLibraryOverlay(
            target,
            receipt["tree_digest"],
            expected_bundle,
            expected_parent.image_id,
            receipt["archive_sha256"],
            receipt["file_count"],
            receipt["total_file_bytes"],
        )
    receipt_bytes = len(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    )
    additional = receipt["total_file_bytes"] + receipt_bytes
    if retained + additional > material_cache_bytes:
        raise ValueError("operator material and overlay cache capacity exceeded")
    if shutil.disk_usage(root).free < additional + 16 * 1024**2:
        raise ValueError("overlay cache physical capacity unavailable")
    temporary = Path(tempfile.mkdtemp(prefix=".pending-", dir=bucket))
    try:
        with tarfile.open(archive_path, mode="r:") as archive:
            names: set[str] = set()
            total = 0
            for member in archive:
                relative = PurePosixPath(member.name)
                parts = relative.parts
                if (
                    not member.isfile()
                    or member.pax_headers
                    or len(parts) < 2
                    or parts[0] not in {"site-packages", "source"}
                    or any(part in {"", ".", ".."} for part in parts)
                    or "\\" in member.name
                    or ":" in member.name
                    or relative.as_posix() != member.name
                    or member.name in names
                    or member.mode != 0o444
                    or member.uid != 0
                    or member.gid != 0
                    or member.mtime != 0
                    or not 0 <= member.size <= MAX_OVERLAY_BYTES
                ):
                    raise ValueError("overlay archive member differs")
                names.add(member.name)
                total += member.size
                if (
                    total > receipt["total_file_bytes"]
                    or len(names) > receipt["file_count"]
                ):
                    raise ValueError("overlay archive exceeds bound")
                destination = temporary.joinpath(*parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise ValueError("overlay archive member unavailable")
                with destination.open("xb") as output:
                    remaining = member.size
                    while remaining:
                        block = source.read(min(remaining, 1024**2))
                        if not block:
                            raise ValueError("overlay archive member truncated")
                        output.write(block)
                        remaining -= len(block)
        rows = _overlay_rows(temporary)
        if (
            len(rows) != receipt["file_count"]
            or sum(row[1] for row in rows) != receipt["total_file_bytes"]
            or _overlay_digest(json.dumps(rows, separators=(",", ":")).encode())
            != receipt["tree_digest"]
        ):
            raise ValueError("overlay tree digest differs")
        (temporary / ".overlay.json").write_bytes(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        )
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_dir():
                raise ValueError("cached overlay path differs")
            _verified_overlay_tree(target, receipt)
        else:
            try:
                temporary.rename(target)
            except OSError as error:
                if error.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                    raise
                if target.is_symlink() or not target.is_dir():
                    raise ValueError("cached overlay path differs") from error
                _verified_overlay_tree(target, receipt)
            else:
                for path in target.rglob("*"):
                    path.chmod(0o500 if path.is_dir() else 0o400)
                target.chmod(0o500)
        return VerifiedLibraryOverlay(
            target,
            receipt["tree_digest"],
            expected_bundle,
            expected_parent.image_id,
            receipt["archive_sha256"],
            receipt["file_count"],
            receipt["total_file_bytes"],
        )
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def cache_verified_overlay(
    snapshot: Path,
    cache_root: Path,
    *,
    expected_bundle: LibraryBundleRef,
    expected_parent: WorkerImageIdentity,
    expected_receipt: dict,
    material_cache_bytes: int,
    deadline: float | None = None,
    cancel: Callable[[], None] | None = None,
) -> VerifiedLibraryOverlay:
    """Share the operator's material/overlay reservation with signed intake."""
    if type(material_cache_bytes) is not int or material_cache_bytes <= 0:
        raise ValueError("trusted material and overlay cache capacity required")
    from .direct_material_staging import _cache_lock

    with _cache_lock(cache_root, deadline=deadline, cancel=cancel) as root:
        return _cache_verified_overlay_locked(
            snapshot,
            root,
            expected_bundle=expected_bundle,
            expected_parent=expected_parent,
            expected_receipt=expected_receipt,
            material_cache_bytes=material_cache_bytes,
        )


def stage_pinned_bundle_material(directory: Path, cache_root: Path) -> LibraryBundleRef:
    """Trusted owner staging of exact material; no image build or execution."""
    material = load_pinned_bundle_directory(directory)
    selected = bundle_ref(*material)
    root = _private_cache_directory(
        cache_root, "private operator bundle cache required"
    )
    material_root = root / "materials"
    material_root.mkdir(mode=0o700, exist_ok=True)
    material_root = _private_cache_directory(
        material_root, "private staged bundle root required"
    )
    destination = material_root / selected.bundle_digest[7:]
    if destination.exists() or destination.is_symlink():
        inspect_staged_bundle_material(cache_root, selected)
        return selected
    manifest, source, wheels, lock, license_text = material
    temporary = Path(tempfile.mkdtemp(prefix=".pending-", dir=material_root))
    try:
        temporary.chmod(0o700)
        wheel_root = temporary / "wheels"
        wheel_root.mkdir(mode=0o700)
        for path, body in (
            (temporary / "bundle.json", json.dumps(manifest, sort_keys=True).encode()),
            (temporary / "source.tar.gz", source),
            (temporary / "requirements.txt", lock),
            (temporary / "LICENSE", license_text),
            *((wheel_root / name, body) for name, body in wheels.items()),
        ):
            path.write_bytes(body)
            path.chmod(0o600)
        if bundle_ref(*load_pinned_bundle_directory(temporary)) != selected:
            raise ValueError("staged bundle changed while copying")
        try:
            temporary.rename(destination)
        except FileExistsError:
            inspect_staged_bundle_material(cache_root, selected)
    finally:
        if temporary.exists():
            if temporary.is_symlink() or not temporary.resolve().is_relative_to(
                material_root.resolve()
            ):
                raise ValueError("temporary bundle path escaped owner cache")
            shutil.rmtree(temporary)
    return selected


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
