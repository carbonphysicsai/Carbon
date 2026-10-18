"""Fixed, offline dependency preparation inside a bounded C03 worker.

The controller stages exact bundle bytes and a pinned uv binary into the
worker's read-only input. This module never runs source code or imports an
installed wheel. It exports only a bounded regular-file overlay for a later,
separately isolated construction operation.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

from .library_bundles import LibraryBundleRef, bundle_ref, validate_bundle

OVERLAY_SCHEMA = "carbon.development.library-overlay.v1"
# The C03 export counts both overlay.tar and overlay.json against 128 MiB.
# Reserve a fixed 64 KiB for the receipt and stream framing.
MAX_OVERLAY_BYTES = 128 * 1024**2 - 64 * 1024
MAX_OVERLAY_FILES = 8192


def _digest(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _regular_file(path: Path, maximum: int, *, allow_empty: bool = False) -> bytes:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or not (
        (0 if allow_empty else 1) <= metadata.st_size <= maximum
    ):
        raise ValueError("bounded regular preparation input required")
    body = path.read_bytes()
    if len(body) != metadata.st_size:
        raise ValueError("preparation input changed")
    return body


def _source_into(source: bytes, root: Path) -> None:
    source_root = None
    with tarfile.open(fileobj=io.BytesIO(source), mode="r:gz") as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if (
                not name.parts
                or name.is_absolute()
                or any(part in {"", ".", ".."} for part in name.parts)
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("source overlay member differs")
            if source_root is None:
                source_root = name.parts[0]
            if name.parts[0] != source_root:
                raise ValueError("source overlay root differs")
            if len(name.parts) == 1:
                if not member.isdir():
                    raise ValueError("source overlay root differs")
                continue
            target = root.joinpath("source", *name.parts[1:])
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            content = archive.extractfile(member)
            if content is None:
                raise ValueError("source overlay member unavailable")
            with target.open("xb") as stream:
                remaining = member.size
                while remaining:
                    chunk = content.read(min(remaining, 1024**2))
                    if not chunk:
                        raise ValueError("source overlay member truncated")
                    stream.write(chunk)
                    remaining -= len(chunk)


def _overlay_rows(root: Path) -> list[list[object]]:
    rows: list[list[object]] = []
    total = 0
    for base, directories, filenames in os.walk(root, followlinks=False):
        for name in directories:
            if not stat.S_ISDIR((Path(base) / name).lstat().st_mode):
                raise ValueError("overlay directory is not regular")
        for name in filenames:
            path = Path(base) / name
            relative = path.relative_to(root).as_posix()
            if (
                not relative.startswith(("site-packages/", "source/"))
                or any(
                    part in {"", ".", ".."} for part in PurePosixPath(relative).parts
                )
                or not stat.S_ISREG(path.lstat().st_mode)
            ):
                raise ValueError("overlay file role differs")
            body = path.read_bytes()
            total += len(body)
            rows.append([relative, len(body), _digest(body)])
            if total > MAX_OVERLAY_BYTES or len(rows) > MAX_OVERLAY_FILES:
                raise ValueError("overlay output exceeds fixed bound")
    rows.sort(key=lambda row: row[0])
    if len({row[0].casefold() for row in rows}) != len(rows):
        raise ValueError("overlay file names collide")
    return rows


def prepare(
    input_dir: Path,
    output_dir: Path,
    *,
    python_path: str = "/opt/carbon-worker/bin/python",
) -> dict:
    """Validate exact material, install wheels offline, and export inert bytes."""
    if not input_dir.is_dir() or not output_dir.is_dir():
        raise ValueError("bounded preparation directories required")
    control = json.loads(_regular_file(input_dir / "control.json", 65536))
    if type(control) is not dict or set(control) != {
        "bundle_ref",
        "parent_image_id",
        "uv_sha256",
    }:
        raise ValueError("closed preparation control required")
    bundle = LibraryBundleRef.from_dict(control["bundle_ref"])
    parent = control["parent_image_id"]
    if type(parent) is not str or not parent.startswith("sha256:") or len(parent) != 71:
        raise ValueError("exact preparation parent required")
    manifest = json.loads(_regular_file(input_dir / "bundle.json", 65536))
    source = _regular_file(input_dir / "source.tar.gz", 32 * 1024**2)
    lock = _regular_file(input_dir / "requirements.txt", 512 * 1024, allow_empty=True)
    license_text = _regular_file(input_dir / "LICENSE", 256 * 1024, allow_empty=True)
    wheels = {
        name: _regular_file(input_dir / name, 128 * 1024**2)
        for name in manifest.get("wheels", {})
    }
    validate_bundle(manifest, source, wheels, lock, license_text)
    if bundle_ref(manifest, source, wheels, lock, license_text) != bundle:
        raise ValueError("prepared bundle reference differs")
    uv = input_dir / "uv-bin"
    if _digest(_regular_file(uv, 64 * 1024**2)) != control["uv_sha256"]:
        raise ValueError("pinned uv preparation bytes differ")
    overlay = output_dir.parent / "workspace" / "overlay"
    overlay.mkdir(parents=True, exist_ok=False)
    site = overlay / "site-packages"
    site.mkdir()
    environment = {
        **os.environ,
        "UV_NO_CONFIG": "1",
        "UV_NO_PROGRESS": "1",
        "UV_LINK_MODE": "copy",
        "UV_CACHE_DIR": str(output_dir.parent / "cache"),
        "PYTHONNOUSERSITE": "1",
    }
    subprocess.run(
        [
            str(uv),
            "--no-cache",
            "pip",
            "install",
            "--target",
            str(site),
            "--python",
            python_path,
            "--no-index",
            "--find-links",
            str(input_dir),
            "--require-hashes",
            "--no-deps",
            "--only-binary=:all:",
            "-r",
            str(input_dir / "requirements.txt"),
        ],
        cwd=output_dir.parent / "workspace",
        env=environment,
        check=True,
        timeout=540,
        capture_output=True,
    )
    _source_into(source, overlay)
    rows = _overlay_rows(overlay)
    archive_path = output_dir / "overlay.tar"
    with tarfile.open(archive_path, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for relative, size, _ in rows:
            item = tarfile.TarInfo(relative)
            item.size = size
            item.mode = 0o444
            item.mtime = 0
            item.uid = item.gid = 0
            with (overlay / relative).open("rb") as stream:
                archive.addfile(item, stream)
            if archive_path.stat().st_size > MAX_OVERLAY_BYTES:
                raise ValueError("overlay archive exceeds fixed output bound")
    archive_bytes = _regular_file(archive_path, MAX_OVERLAY_BYTES)
    receipt = {
        "schema": OVERLAY_SCHEMA,
        "bundle_ref": bundle.to_dict(),
        "parent_image_id": parent,
        "archive_sha256": _digest(archive_bytes),
        "archive_bytes": len(archive_bytes),
        "tree_digest": _digest(json.dumps(rows, separators=(",", ":")).encode()),
        "file_count": len(rows),
        "total_file_bytes": sum(row[1] for row in rows),
    }
    (output_dir / "overlay.json").write_bytes(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    )
    return receipt
