"""Closed DEVELOPMENT-only C-03/analysis image artifact handoff.

This packages images already built by the normal source-pinned builders. It
does not publish an image, select a host, or grant scientific/security status.
The receiving host verifies the archive and exact clean candidate before any
Docker load; actual load remains subject to the operator's resource admission.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Callable

from carbon.development_session.profile import canonical, digest
from carbon.development_session.research_campaign import (
    development_candidate_implementation,
    verify_current_worker,
)
from carbon.development_session.research_image import (
    load_analysis_image,
    runtime_document,
    verify_image,
)
from carbon.reconstruction.worker.docker_runtime import (
    DockerCLI,
    doctor,
    load_image_identity,
)
from carbon.reconstruction.worker.model import WorkerFailure


SCHEMA = "carbon.development-image-artifact.v1"
SCOPE = "UNQUALIFIED_PUBLIC_DEVELOPMENT"
FILES = frozenset(
    {"bundle.json", "images.tar.gz", "c03-worker-image.json", "analysis-image.json"}
)
MAX_MANIFEST_BYTES = 8192
MAX_ARCHIVE_BYTES = 24 * 1024**3
SHA = "sha256:"


class Refused(ValueError):
    """A named, non-scientific handoff refusal."""


def _sha_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return SHA + value.hexdigest()


def _sha(value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith(SHA)
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise Refused("digest_malformed")
    return value


def _regular(path: Path, *, limit: int) -> Path:
    if (
        path.is_symlink()
        or path.resolve() != path
        or not path.is_file()
        or path.stat().st_size > limit
    ):
        raise Refused(f"file_not_regular_or_bounded:{path.name}")
    return path


def _directory(path: Path) -> Path:
    if not path.is_absolute() or path.is_symlink() or path.resolve() != path:
        raise Refused("directory_not_exact_absolute")
    return path


def _source(revision: str, tree: str, source_digest: str, repository: Path) -> dict:
    try:
        return development_candidate_implementation(
            revision,
            expected_tree=tree,
            expected_source_tree_digest=source_digest,
            repository=repository,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise Refused("exact_clean_development_source_required") from error


def _manifests(c03_path: Path, analysis_path: Path, implementation: dict):
    c03 = load_image_identity(_regular(c03_path, limit=MAX_MANIFEST_BYTES))
    analysis = load_analysis_image(_regular(analysis_path, limit=MAX_MANIFEST_BYTES))
    verify_current_worker(c03, implementation)
    if analysis.parent_image != c03.image_id:
        raise Refused("analysis_parent_mismatch")
    if analysis.runtime_digest != digest(canonical(runtime_document(c03.image_id))):
        raise Refused("analysis_runtime_source_mismatch")
    return c03, analysis


def _containerd(cli: DockerCLI) -> None:
    info = cli.json(["info", "--format", "{{json .}}"])
    status = info.get("DriverStatus") if type(info) is dict else None
    if (
        not isinstance(status, list)
        or ["driver-type", "io.containerd.snapshotter.v1"] not in status
    ):
        raise Refused("containerd_image_store_required")


def _docker_pair(c03, analysis, cli: DockerCLI) -> None:
    _containerd(cli)
    if not doctor(image_id=c03.image_id, image_identity=c03, cli=cli).eligible:
        raise Refused("c03_doctor_ineligible")
    try:
        verify_image(analysis, cli)
    except (OSError, ValueError, WorkerFailure) as error:
        raise Refused("analysis_image_ineligible") from error


def _write_new(path: Path, body: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise Refused(f"output_exists:{path.name}")
    with path.open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())


def _save_compressed(path: Path, c03_id: str, analysis_id: str) -> tuple[str, int, int]:
    with tempfile.TemporaryFile() as errors:
        with path.open("xb") as destination:
            process = subprocess.Popen(
                ["docker", "image", "save", c03_id, analysis_id],
                stdout=subprocess.PIPE,
                stderr=errors,
            )
            raw_bytes = 0
            assert process.stdout is not None
            try:
                with gzip.GzipFile(
                    filename="", mode="wb", fileobj=destination, mtime=0
                ) as compressed:
                    for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
                        raw_bytes += len(chunk)
                        if raw_bytes > MAX_ARCHIVE_BYTES:
                            raise Refused("uncompressed_archive_too_large")
                        compressed.write(chunk)
            except BaseException:
                if process.poll() is None:
                    process.kill()
                process.wait()
                raise
            finally:
                process.stdout.close()
            if process.wait() != 0:
                errors.seek(0)
                raise Refused(
                    "docker_save_failed:" + errors.read(4096).decode("utf-8", "replace")
                )
            destination.flush()
            os.fsync(destination.fileno())
    size = path.stat().st_size
    if size == 0 or size > MAX_ARCHIVE_BYTES:
        raise Refused("compressed_archive_size_invalid")
    return _sha_file(path), size, raw_bytes


def export_bundle(
    *,
    bundle_dir: Path,
    c03_manifest: Path,
    analysis_manifest: Path,
    revision: str,
    tree: str,
    source_tree_digest: str,
    repository: Path,
    cli: DockerCLI | None = None,
) -> dict:
    """Export one compressed archive and closed receipt from existing images."""
    implementation = _source(revision, tree, source_tree_digest, repository)
    c03, analysis = _manifests(c03_manifest, analysis_manifest, implementation)
    _docker_pair(c03, analysis, cli or DockerCLI())
    _directory(bundle_dir)
    if bundle_dir.exists():
        if not bundle_dir.is_dir() or any(bundle_dir.iterdir()):
            raise Refused("bundle_output_not_empty")
    else:
        bundle_dir.mkdir(mode=0o700, parents=True)
    c03_bytes = c03_manifest.read_bytes()
    analysis_bytes = analysis_manifest.read_bytes()
    _write_new(bundle_dir / "c03-worker-image.json", c03_bytes)
    _write_new(bundle_dir / "analysis-image.json", analysis_bytes)
    archive_sha, archive_bytes, raw_bytes = _save_compressed(
        bundle_dir / "images.tar.gz", c03.image_id, analysis.image_id
    )
    receipt = {
        "schema": SCHEMA,
        "scope": SCOPE,
        "security_acceptance": "HUMAN_INPUT",
        "source_authority": "DEVELOPMENT_CANDIDATE",
        "source_commit": implementation["revision"],
        "source_tree": implementation["tree"],
        "source_tree_digest": implementation["source_tree_digest"],
        "image_store": "containerd",
        "c03_image_id": c03.image_id,
        "analysis_image_id": analysis.image_id,
        "analysis_parent_image": analysis.parent_image,
        "c03_manifest_sha256": SHA + hashlib.sha256(c03_bytes).hexdigest(),
        "analysis_manifest_sha256": SHA + hashlib.sha256(analysis_bytes).hexdigest(),
        "archive_sha256": archive_sha,
        "archive_bytes": archive_bytes,
        "uncompressed_bytes": raw_bytes,
    }
    _write_new(bundle_dir / "bundle.json", canonical(receipt))
    return {
        "receipt": str(bundle_dir / "bundle.json"),
        "receipt_sha256": _sha_file(bundle_dir / "bundle.json"),
        **receipt,
    }


def verify_bundle(
    *,
    bundle_dir: Path,
    receipt_sha256: str,
    revision: str,
    tree: str,
    source_tree_digest: str,
    repository: Path,
) -> dict:
    """Verify exact source, complete file set and bytes before Docker load."""
    implementation = _source(revision, tree, source_tree_digest, repository)
    _directory(bundle_dir)
    if not bundle_dir.is_dir() or {p.name for p in bundle_dir.iterdir()} != FILES:
        raise Refused("bundle_file_set_invalid")
    receipt_path = _regular(bundle_dir / "bundle.json", limit=MAX_MANIFEST_BYTES)
    if _sha_file(receipt_path) != _sha(receipt_sha256):
        raise Refused("receipt_digest_mismatch")
    try:
        receipt = json.loads(receipt_path.read_bytes())
    except (UnicodeError, ValueError) as error:
        raise Refused("receipt_invalid_json") from error
    fields = {
        "schema",
        "scope",
        "security_acceptance",
        "source_authority",
        "source_commit",
        "source_tree",
        "source_tree_digest",
        "image_store",
        "c03_image_id",
        "analysis_image_id",
        "analysis_parent_image",
        "c03_manifest_sha256",
        "analysis_manifest_sha256",
        "archive_sha256",
        "archive_bytes",
        "uncompressed_bytes",
    }
    if (
        type(receipt) is not dict
        or set(receipt) != fields
        or any(
            receipt.get(key) != value
            for key, value in {
                "schema": SCHEMA,
                "scope": SCOPE,
                "security_acceptance": "HUMAN_INPUT",
                "source_authority": "DEVELOPMENT_CANDIDATE",
                "source_commit": implementation["revision"],
                "source_tree": implementation["tree"],
                "source_tree_digest": implementation["source_tree_digest"],
                "image_store": "containerd",
            }.items()
        )
    ):
        raise Refused("receipt_identity_invalid")
    c03_path = bundle_dir / "c03-worker-image.json"
    analysis_path = bundle_dir / "analysis-image.json"
    c03, analysis = _manifests(c03_path, analysis_path, implementation)
    if (
        receipt["c03_image_id"] != c03.image_id
        or receipt["analysis_image_id"] != analysis.image_id
        or receipt["analysis_parent_image"] != c03.image_id
        or _sha_file(c03_path) != _sha(receipt["c03_manifest_sha256"])
        or _sha_file(analysis_path) != _sha(receipt["analysis_manifest_sha256"])
    ):
        raise Refused("manifest_receipt_mismatch")
    archive = _regular(bundle_dir / "images.tar.gz", limit=MAX_ARCHIVE_BYTES)
    if (
        type(receipt["archive_bytes"]) is not int
        or receipt["archive_bytes"] != archive.stat().st_size
        or type(receipt["uncompressed_bytes"]) is not int
        or not 0 < receipt["uncompressed_bytes"] <= MAX_ARCHIVE_BYTES
        or _sha_file(archive) != _sha(receipt["archive_sha256"])
    ):
        raise Refused("archive_receipt_mismatch")
    return receipt


def _docker_load(archive: Path, expected_raw_bytes: int) -> None:
    """Stream one verified gzip archive to Docker without an extracted copy."""
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(
            ["docker", "image", "load"],
            stdin=subprocess.PIPE,
            stdout=output,
            stderr=errors,
        )
        raw_bytes = 0
        assert process.stdin is not None
        try:
            with gzip.open(archive, "rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    raw_bytes += len(chunk)
                    if raw_bytes > expected_raw_bytes:
                        raise Refused("archive_expanded_beyond_receipt")
                    process.stdin.write(chunk)
            process.stdin.close()
            if raw_bytes != expected_raw_bytes:
                raise Refused("archive_expanded_size_mismatch")
            if process.wait() != 0:
                errors.seek(0)
                raise Refused(
                    "docker_load_failed:" + errors.read(4096).decode("utf-8", "replace")
                )
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            raise


def _open_directory(parent_fd: int, name: str) -> int:
    """Anchor a cache child below an already opened directory, without links."""
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    try:
        return os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except OSError as error:
        raise Refused(f"installed_cache_directory_invalid:{name}") from error


def _write_under(directory_fd: int, name: str, expected: bytes) -> None:
    """Compare or create an exact manifest relative to a no-follow dir fd."""
    try:
        existing_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    except FileNotFoundError:
        existing_fd = None
    except OSError as error:
        raise Refused(f"installed_manifest_conflict:{name}") from error
    if existing_fd is not None:
        with os.fdopen(existing_fd, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise Refused(f"installed_manifest_conflict:{name}")
            if source.read(MAX_MANIFEST_BYTES + 1) != expected:
                raise Refused(f"installed_manifest_conflict:{name}")
        return
    try:
        new_fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
    except OSError as error:
        raise Refused(f"installed_manifest_conflict:{name}") from error
    with os.fdopen(new_fd, "wb") as destination:
        destination.write(expected)
        destination.flush()
        os.fsync(destination.fileno())


def _install_pair_nofollow(
    artifacts_root: Path, c03_bytes: bytes, analysis_bytes: bytes, runtime_digest: str
) -> None:
    """Post-load manifest install with anchored, no-follow parent traversal."""
    _require_posix_nofollow()
    # Open each component from / so a changed ancestor cannot redirect the
    # final open into an unrelated cache between the precheck and Docker load.
    root_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in artifacts_root.absolute().parts[1:]:
            try:
                next_fd = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=root_fd,
                )
            except OSError as error:
                raise Refused("artifacts_root_changed") from error
            os.close(root_fd)
            root_fd = next_fd
    except BaseException:
        os.close(root_fd)
        raise
    try:
        research_fd = _open_directory(root_fd, "research-images")
        try:
            runtime_fd = _open_directory(research_fd, runtime_digest[7:])
            try:
                _write_under(runtime_fd, "analysis-image.json", analysis_bytes)
            finally:
                os.close(runtime_fd)
        finally:
            os.close(research_fd)
        _write_under(root_fd, "c03-worker-image.json", c03_bytes)
    finally:
        os.close(root_fd)


def _require_posix_nofollow() -> None:
    """Reject a host that cannot use the only supported safe cache installer."""
    if os.name != "posix" or not all(
        hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW")
    ):
        raise Refused("posix_nofollow_install_required")


def import_bundle(
    *,
    bundle_dir: Path,
    receipt_sha256: str,
    artifacts_root: Path,
    revision: str,
    tree: str,
    source_tree_digest: str,
    repository: Path,
    before_load: Callable[[int], None],
    cli: DockerCLI | None = None,
) -> dict:
    """Load only after a mandatory external, at-use physical-capacity gate.

    This is a library operation until the normal host admission adapter is
    connected. The callback receives a conservative additional disk claim;
    it must fail closed when the host cannot reserve that claim and preserve
    the live floor. No bare Boolean can grant capacity.
    """
    receipt = verify_bundle(
        bundle_dir=bundle_dir,
        receipt_sha256=receipt_sha256,
        revision=revision,
        tree=tree,
        source_tree_digest=source_tree_digest,
        repository=repository,
    )
    _directory(artifacts_root)
    if not artifacts_root.is_dir():
        raise Refused("artifacts_root_missing")
    c03_path = artifacts_root / "c03-worker-image.json"
    # The normal analysis cache is keyed by the runtime digest, not image ID.
    analysis_manifest = load_analysis_image(bundle_dir / "analysis-image.json")
    analysis_path = (
        artifacts_root
        / "research-images"
        / analysis_manifest.runtime_digest[7:]
        / "analysis-image.json"
    )
    c03_bytes = (bundle_dir / "c03-worker-image.json").read_bytes()
    analysis_bytes = (bundle_dir / "analysis-image.json").read_bytes()
    for path, body in ((c03_path, c03_bytes), (analysis_path, analysis_bytes)):
        if (
            path.is_symlink()
            or path.resolve() != path
            or (path.exists() and path.read_bytes() != body)
        ):
            raise Refused(f"installed_manifest_conflict:{path.name}")
    if not callable(before_load):
        raise Refused("physical_capacity_admission_required")
    _require_posix_nofollow()
    # The archive is already staged and gzip is streamed without an extracted
    # host copy. Reserve three raw-tar equivalents for daemon import staging,
    # retained image content and unpacked snapshots, plus 1 GiB for metadata.
    # This is a conservative prospective claim, not a measured peak; the host
    # callback can require more and must keep monitoring physical free space.
    required = 3 * receipt["uncompressed_bytes"] + 1024**3
    before_load(required)
    _docker_load(bundle_dir / "images.tar.gz", receipt["uncompressed_bytes"])
    implementation = _source(revision, tree, source_tree_digest, repository)
    c03, analysis = _manifests(
        bundle_dir / "c03-worker-image.json",
        bundle_dir / "analysis-image.json",
        implementation,
    )
    _docker_pair(c03, analysis, cli or DockerCLI())
    _install_pair_nofollow(
        artifacts_root, c03_bytes, analysis_bytes, analysis_manifest.runtime_digest
    )
    if (
        installed_pair_status(
            artifacts_root=artifacts_root,
            revision=revision,
            tree=tree,
            source_tree_digest=source_tree_digest,
            repository=repository,
            cli=cli or DockerCLI(),
        )
        != "VERIFIED"
    ):
        raise Refused("post_import_pair_not_verified")
    return {
        "status": "VERIFIED_IMPORT",
        "c03_manifest": str(c03_path),
        "analysis_manifest": str(analysis_path),
        "c03_image_id": c03.image_id,
        "analysis_image_id": analysis.image_id,
        "receipt_sha256": _sha(receipt_sha256),
    }


def _installed_pair(
    *,
    artifacts_root: Path,
    revision: str,
    tree: str,
    source_tree_digest: str,
    repository: Path,
    cli: DockerCLI | None = None,
) -> tuple[str, Path | None]:
    """Pure read of the two normal cache paths: VERIFIED, ABSENT or refusal.

    A missing member is a cache miss and retains the installer's full build
    reserve. A present but malformed or mismatched member is a hard refusal.
    This never invokes either image builder or writes to Docker/filesystem.
    """
    implementation = _source(revision, tree, source_tree_digest, repository)
    _directory(artifacts_root)
    c03_path = artifacts_root / "c03-worker-image.json"
    if not c03_path.exists() and not c03_path.is_symlink():
        return "ABSENT", None
    c03 = load_image_identity(_regular(c03_path, limit=MAX_MANIFEST_BYTES))
    verify_current_worker(c03, implementation)
    runtime_digest = digest(canonical(runtime_document(c03.image_id)))
    analysis_path = (
        artifacts_root
        / "research-images"
        / runtime_digest.removeprefix(SHA)
        / "analysis-image.json"
    )
    if not analysis_path.exists() and not analysis_path.is_symlink():
        return "ABSENT", None
    _manifests(c03_path, analysis_path, implementation)
    analysis = load_analysis_image(analysis_path)
    _docker_pair(c03, analysis, cli or DockerCLI())
    return "VERIFIED", analysis_path


def installed_pair_status(
    *,
    artifacts_root: Path,
    revision: str,
    tree: str,
    source_tree_digest: str,
    repository: Path,
    cli: DockerCLI | None = None,
) -> str:
    """Pure read status for the exact normal C-03/analysis pair."""
    status, _ = _installed_pair(
        artifacts_root=artifacts_root,
        revision=revision,
        tree=tree,
        source_tree_digest=source_tree_digest,
        repository=repository,
        cli=cli,
    )
    return status


def verified_analysis_manifest(
    *,
    artifacts_root: Path,
    revision: str,
    tree: str,
    source_tree_digest: str,
    repository: Path,
    cli: DockerCLI | None = None,
) -> Path:
    """Return the existing analysis path only after re-verifying both images."""
    status, path = _installed_pair(
        artifacts_root=artifacts_root,
        revision=revision,
        tree=tree,
        source_tree_digest=source_tree_digest,
        repository=repository,
        cli=cli,
    )
    if status != "VERIFIED" or path is None:
        raise Refused("installed_pair_absent")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("export", "verify", "verify-installed"):
        sub = commands.add_parser(command)
        if command != "verify-installed":
            sub.add_argument("--bundle-dir", type=Path, required=True)
        sub.add_argument("--revision", required=True)
        sub.add_argument("--tree", required=True)
        sub.add_argument("--source-tree-digest", required=True)
    export = commands.choices["export"]
    export.add_argument("--c03-manifest", type=Path, required=True)
    export.add_argument("--analysis-manifest", type=Path, required=True)
    verify = commands.choices["verify"]
    verify.add_argument("--receipt-sha256", required=True)
    installed = commands.choices["verify-installed"]
    installed.add_argument("--artifacts-root", type=Path, required=True)
    installed.add_argument("--print-analysis-manifest", action="store_true")
    args = parser.parse_args(argv)
    repository = Path(__file__).resolve().parents[2]
    try:
        if args.command == "export":
            result = export_bundle(
                bundle_dir=args.bundle_dir,
                c03_manifest=args.c03_manifest,
                analysis_manifest=args.analysis_manifest,
                revision=args.revision,
                tree=args.tree,
                source_tree_digest=args.source_tree_digest,
                repository=repository,
            )
        elif args.command == "verify":
            result = verify_bundle(
                bundle_dir=args.bundle_dir,
                receipt_sha256=args.receipt_sha256,
                revision=args.revision,
                tree=args.tree,
                source_tree_digest=args.source_tree_digest,
                repository=repository,
            )
        else:
            options = {
                "artifacts_root": args.artifacts_root,
                "revision": args.revision,
                "tree": args.tree,
                "source_tree_digest": args.source_tree_digest,
                "repository": repository,
            }
            if args.print_analysis_manifest:
                status, path = _installed_pair(**options)
                if status == "ABSENT":
                    print("ABSENT")
                    return 2
                assert path is not None
                result = str(path)
            else:
                result = installed_pair_status(**options)
    except (OSError, ValueError, WorkerFailure, subprocess.SubprocessError) as error:
        print(f"development image artifact refused: {error}", file=sys.stderr)
        if args.command == "verify-installed":
            print("INVALID")
        return 2
    print(
        result
        if args.command == "verify-installed"
        else json.dumps(result, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
