"""Signed, owner-bound pinned construction material intake.

The direct service supplies the authenticated provider. Untrusted requests name
only a bundle digest and one flat material filename, never a host path. Partial
bytes stay outside the resolver's material root. A complete, validated closure
is promoted through the ordinary owner cache helper before admission can use it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import time
from pathlib import Path

from carbon.research.errors import ResearchServiceErrorCode
from carbon.research.lifecycle import ResearchTaskProviderError
from carbon.research.model import (
    DirectStageMaterialRequestV1,
    DirectStageMaterialResultV1,
)

from .library_bundles import (
    MAX_LICENSE_BYTES,
    MAX_LOCK_BYTES,
    MAX_SOURCE_BYTES,
    MAX_WHEEL_TOTAL_BYTES,
    bundle_ref,
    load_pinned_bundle_directory,
)
from .library_environment_cache import stage_pinned_bundle_material

_MAX_PENDING = (
    MAX_WHEEL_TOTAL_BYTES
    + MAX_SOURCE_BYTES
    + MAX_LOCK_BYTES
    + MAX_LICENSE_BYTES
    + 1024**2
)
_STALE_SECONDS = 24 * 60 * 60


def _private(path: Path) -> Path:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError("material staging root differs")
    path.mkdir(mode=0o700, exist_ok=True)
    if path.is_symlink() or path.resolve(strict=True) != path:
        raise ValueError("material staging root differs")
    if os.name == "posix":
        record = path.stat()
        if record.st_uid != os.getuid() or stat.S_IMODE(record.st_mode) & 0o077:
            raise ValueError("private material staging root required")
    return path


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as body:
        for block in iter(lambda: body.read(1024 * 1024), b""):
            hasher.update(block)
    return "sha256:" + hasher.hexdigest()


def _item(root: Path, name: str, fingerprint: str) -> Path:
    key = hashlib.sha256((name + "\0" + fingerprint).encode("utf-8")).hexdigest()
    return root / key


def _verified(path: Path, total: int, fingerprint: str) -> bool:
    return (
        not path.is_symlink()
        and path.is_file()
        and path.stat().st_size == total
        and _digest(path) == fingerprint
    )


def _finalized(cache_root: Path, request: DirectStageMaterialRequestV1):
    material_root = cache_root / "materials"
    if material_root.is_symlink() or (
        material_root.exists()
        and (
            not material_root.is_dir()
            or material_root.resolve(strict=True) != material_root
        )
    ):
        raise ValueError("staged material root differs")
    directory = material_root / request.bundle_digest[7:]
    if not directory.exists() and not directory.is_symlink():
        return None
    if (
        directory.is_symlink()
        or not directory.is_dir()
        or directory.resolve(strict=True) != directory
    ):
        raise ValueError("staged bundle path differs")
    manifest_file = directory / "bundle.json"
    if (
        manifest_file.is_symlink()
        or not manifest_file.is_file()
        or manifest_file.stat().st_size > 65536
    ):
        raise ResearchTaskProviderError(ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT)
    try:
        manifest = json.loads(manifest_file.read_bytes())
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except (UnicodeError, json.JSONDecodeError):
        raise ResearchTaskProviderError(
            ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
        ) from None
    if (
        type(manifest) is not dict
        or type(manifest.get("wheels")) is not dict
        or "sha256:" + hashlib.sha256(canonical).hexdigest() != request.bundle_digest
    ):
        raise ResearchTaskProviderError(ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT)
    file = (
        directory / ("wheels" if request.name.endswith(".whl") else "") / request.name
    )
    if request.name == "bundle.json":
        if (
            len(canonical) != request.total_bytes
            or request.content_digest != request.bundle_digest
            or canonical[request.offset : request.offset + len(request.chunk)]
            != request.chunk
        ):
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
            )
    else:
        declared = (
            manifest.get("wheels", {}).get(request.name)
            if request.name.endswith(".whl")
            else manifest.get(
                {
                    "source.tar.gz": "source_sha256",
                    "requirements.txt": "lock_sha256",
                    "LICENSE": "license_sha256",
                }[request.name]
            )
        )
        if (
            declared != request.content_digest
            or file.is_symlink()
            or not file.is_file()
            or file.stat().st_size != request.total_bytes
        ):
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
            )
        with file.open("rb") as body:
            body.seek(request.offset)
            if body.read(len(request.chunk)) != request.chunk:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
                )
    return DirectStageMaterialResultV1(
        request.name, request.total_bytes, request.content_digest, True, True
    )


def _ready_file(db, owner: str, bundle: str, root: Path, name: str, fingerprint: str):
    row = db.execute(
        "SELECT total,received,digest FROM direct_material_uploads "
        "WHERE owner=? AND bundle=? AND name=?",
        (owner, bundle, name),
    ).fetchone()
    if row is None or row[0] != row[1] or row[2] != fingerprint:
        raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_NOT_FOUND)
    path = _item(root, name, fingerprint)
    if not _verified(path, row[0], fingerprint):
        raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
    return path


def _promote(provider, cache_root: Path, root: Path, bundle: str) -> None:
    owner = provider.owner
    manifest_path = _item(root, "bundle.json", bundle)
    if manifest_path.stat().st_size > 65536:
        raise ResearchTaskProviderError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    try:
        manifest = json.loads(manifest_path.read_bytes())
    except (UnicodeError, json.JSONDecodeError):
        raise ResearchTaskProviderError(
            ResearchServiceErrorCode.REFERENCE_MISMATCH
        ) from None
    if type(manifest) is not dict or type(manifest.get("wheels")) is not dict:
        raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
    declared = {
        "bundle.json": bundle,
        "source.tar.gz": manifest.get("source_sha256"),
        "requirements.txt": manifest.get("lock_sha256"),
        "LICENSE": manifest.get("license_sha256"),
        **manifest["wheels"],
    }
    if len(manifest["wheels"]) > 64 or len(declared) != len(manifest["wheels"]) + 4:
        raise ResearchTaskProviderError(ResearchServiceErrorCode.BOUND_EXCEEDED)
    temporary = Path(tempfile.mkdtemp(prefix=".assemble-", dir=root))
    try:
        temporary.chmod(0o700)
        wheelhouse = temporary / "wheels"
        wheelhouse.mkdir(mode=0o700)
        closure_bytes = 0
        with provider.ledger.db() as db:
            for name, fingerprint in declared.items():
                if (
                    type(name) is not str
                    or type(fingerprint) is not str
                    or not fingerprint.startswith("sha256:")
                    or len(fingerprint) != 71
                    or any(c not in "0123456789abcdef" for c in fingerprint[7:])
                    or (
                        name
                        not in {
                            "bundle.json",
                            "source.tar.gz",
                            "requirements.txt",
                            "LICENSE",
                        }
                        and (
                            not name.endswith(".whl")
                            or Path(name).name != name
                            or len(name) > 200
                        )
                    )
                ):
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    )
                staged = _ready_file(db, owner, bundle, root, name, fingerprint)
                closure_bytes += staged.stat().st_size
                destination = (
                    wheelhouse if name.endswith(".whl") else temporary
                ) / name
                os.link(staged, destination)
        selected = bundle_ref(*load_pinned_bundle_directory(temporary))
        if selected.bundle_digest != bundle:
            raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        if shutil.disk_usage(cache_root).free < closure_bytes + 16 * 1024**2:
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.INFRASTRUCTURE_FAILURE
            )
        if stage_pinned_bundle_material(temporary, cache_root) != selected:
            raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
    except (OSError, ValueError) as exc:
        if isinstance(exc, ResearchTaskProviderError):
            raise
        raise ResearchTaskProviderError(
            ResearchServiceErrorCode.REFERENCE_MISMATCH
        ) from None
    finally:
        shutil.rmtree(temporary)


def stage_material(
    provider, request: DirectStageMaterialRequestV1
) -> DirectStageMaterialResultV1:
    """Append/replay one bounded chunk; promote only a full validated closure."""
    if type(request) is not DirectStageMaterialRequestV1:
        raise TypeError("exact material request required")
    resolver = getattr(provider, "image_resolver", None)
    cache_root = getattr(resolver, "cache_root", None)
    if not isinstance(cache_root, Path) or not cache_root.is_absolute():
        raise ResearchTaskProviderError(ResearchServiceErrorCode.CAPABILITY_UNAVAILABLE)
    cache_root = _private(cache_root)
    completed = _finalized(cache_root, request)
    if completed is not None:
        return completed
    owner = provider.owner
    owner_key = hashlib.sha256(owner.encode("utf-8")).hexdigest()
    uploads = _private(cache_root / "material-uploads")
    owner_root = _private(uploads / owner_key)
    bundle_root = _private(owner_root / request.bundle_digest[7:])
    path = _item(bundle_root, request.name, request.content_digest)
    with provider.ledger.db() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS direct_material_uploads "
            "(owner TEXT NOT NULL,bundle TEXT NOT NULL,name TEXT NOT NULL,"
            "total INTEGER NOT NULL,received INTEGER NOT NULL,digest TEXT NOT NULL,"
            "PRIMARY KEY(owner,bundle,name))"
        )
        for stale in owner_root.iterdir():
            if stale == bundle_root:
                continue
            if stale.is_symlink() or not stale.is_dir():
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.REFERENCE_MISMATCH
                )
            if time.time() - stale.stat().st_mtime > _STALE_SECONDS:
                shutil.rmtree(stale)
                db.execute(
                    "DELETE FROM direct_material_uploads WHERE owner=? AND bundle=?",
                    (owner, "sha256:" + stale.name),
                )
        row = db.execute(
            "SELECT total,received,digest FROM direct_material_uploads "
            "WHERE owner=? AND bundle=? AND name=?",
            (owner, request.bundle_digest, request.name),
        ).fetchone()
        if row is not None and (row[0], row[2]) != (
            request.total_bytes,
            request.content_digest,
        ):
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
            )
        if row is None:
            count = db.execute(
                "SELECT COUNT(*) FROM direct_material_uploads WHERE owner=? AND bundle=?",
                (owner, request.bundle_digest),
            ).fetchone()[0]
            if count >= 68:
                raise ResearchTaskProviderError(ResearchServiceErrorCode.BOUND_EXCEEDED)
            # A process can stop after fsync and before the SQLite commit.
            # With no committed offset, restart that exact digest from zero.
            if path.is_symlink():
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.REFERENCE_MISMATCH
                )
            if path.exists():
                if not path.is_file() or request.offset != 0:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    )
                path.unlink()
        received = row[1] if row is not None else 0
        if (path.exists() or path.is_symlink()) and (
            path.is_symlink() or not path.is_file() or path.stat().st_size != received
        ):
            raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
        end = request.offset + len(request.chunk)
        if request.offset > received:
            raise ResearchTaskProviderError(
                ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
            )
        if request.offset < received:
            if end > received:
                raise ResearchTaskProviderError(
                    ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
                )
            with path.open("rb") as body:
                body.seek(request.offset)
                if body.read(len(request.chunk)) != request.chunk:
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.IDEMPOTENCY_CONFLICT
                    )
        else:
            total_pending = 0
            for entry in owner_root.rglob("*"):
                if entry.is_symlink():
                    raise ResearchTaskProviderError(
                        ResearchServiceErrorCode.REFERENCE_MISMATCH
                    )
                if entry.is_file():
                    total_pending += entry.stat().st_size
            retained_rows = db.execute(
                "SELECT COUNT(*) FROM direct_material_uploads WHERE owner=?",
                (owner,),
            ).fetchone()[0]
            if (
                total_pending + len(request.chunk) + (retained_rows + 1) * 4096
                > _MAX_PENDING
            ):
                raise ResearchTaskProviderError(ResearchServiceErrorCode.BOUND_EXCEEDED)
            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "ab") as output:
                output.write(request.chunk)
                output.flush()
                os.fsync(output.fileno())
            bundle_root.touch()
            received = end
            db.execute(
                "INSERT OR REPLACE INTO direct_material_uploads VALUES(?,?,?,?,?,?)",
                (
                    owner,
                    request.bundle_digest,
                    request.name,
                    request.total_bytes,
                    received,
                    request.content_digest,
                ),
            )
        complete = received == request.total_bytes
        if complete and not _verified(path, received, request.content_digest):
            path.unlink(missing_ok=True)
            db.execute(
                "DELETE FROM direct_material_uploads WHERE owner=? AND bundle=? AND name=?",
                (owner, request.bundle_digest, request.name),
            )
            db.commit()
            raise ResearchTaskProviderError(ResearchServiceErrorCode.REFERENCE_MISMATCH)
    bundle_complete = False
    if complete and request.name == "bundle.json":
        _promote(provider, cache_root, bundle_root, request.bundle_digest)
        bundle_complete = True
        # Completed bytes are now in the immutable owner material cache; free
        # partial staging storage. Replays read their exact bytes there.
        shutil.rmtree(bundle_root)
        with provider.ledger.db() as db:
            db.execute(
                "DELETE FROM direct_material_uploads WHERE owner=? AND bundle=?",
                (owner, request.bundle_digest),
            )
    return DirectStageMaterialResultV1(
        request.name, received, request.content_digest, complete, bundle_complete
    )
