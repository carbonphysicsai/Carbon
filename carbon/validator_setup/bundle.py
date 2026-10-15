"""Bind and materialize public runtime source without operator state or keys."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SCHEMA = "carbon.validator-operator-bundle.v1"
MANIFEST = "validator-bundle.json"
ROOTS = (
    "carbon/",
    "scripts/dev/battery_validator_service/",
    ".agent/decisions/",
    "Design_Specs/",
    "schemas/",
)
# Exact published data consumed by the existing battery runtime. Broader
# evidence/script directories are deliberately not exported.
PUBLIC_RUNTIME_MATERIALS = frozenset(
    {
        "docs/development/evidence/exam-design-2026-09-24/ocv_table.json",
        "docs/development/evidence/exam-design-2026-09-24/datasets/train-v1.jsonl.gz",
        "docs/development/evidence/exam-design-2026-09-24/prepare.json",
        "scripts/dev/exam_design/locks/battery-overlay.lock.json",
        "docs/development/evidence/exam-design-2026-09-24/datasets/inputs.json",
        "docs/development/evidence/exam-design-2026-09-24/refs-b/out/battery_refs/records.jsonl",
    }
)
FILES = (
    frozenset(
        {
            "pyproject.toml",
            "uv.lock",
            "README.md",
            "CONSTITUTION.md",
            "SPEC.md",
            "scripts/__init__.py",
            "scripts/dev/__init__.py",
            ".agent/DECISIONS.md",
            ".agent/INVARIANTS.md",
        }
    )
    | PUBLIC_RUNTIME_MATERIALS
)


class SetupRefused(ValueError):
    """Closed setup reason; never includes source input, secrets or private state."""


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def safe_path(value):
    if type(value) is not str or "\\" in value or ":" in value or "\0" in value:
        raise SetupRefused("BUNDLE_PATH_REFUSED")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("", ".", "..") for p in value.split("/")):
        raise SetupRefused("BUNDLE_PATH_REFUSED")
    if value not in FILES and not value.startswith(ROOTS):
        raise SetupRefused("BUNDLE_PATH_OUTSIDE_PUBLIC_RUNTIME")
    return path


def git(repository, *args):
    result = subprocess.run(
        ["git", *args], cwd=repository, capture_output=True, check=False
    )
    if result.returncode:
        raise SetupRefused("SOURCE_REVISION_UNAVAILABLE")
    return result.stdout


@contextmanager
def held_lock(path, *, exclusive):
    import fcntl

    path = Path(path)
    if path.is_symlink() or not path.parent.is_dir():
        raise SetupRefused("REGULAR_OPERATOR_LOCK_REQUIRED")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode) or os.fstat(fd).st_mode & 0o077:
            raise SetupRefused("OWNER_ONLY_OPERATOR_LOCK_REQUIRED")
        try:
            fcntl.flock(
                fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
            )
        except BlockingIOError:
            raise SetupRefused("OPERATOR_RUNTIME_OR_RELEASE_SWITCH_ACTIVE") from None
        yield
    finally:
        os.close(fd)


@contextmanager
def runtime_lease(service_config):
    from scripts.dev.battery_validator_service.service import load_service

    service = load_service(service_config)
    with held_lock(service.state_dir / "operator-runtime.lock", exclusive=False):
        yield


@dataclass(frozen=True)
class VerifiedBundle:
    root: Path
    digest: str
    manifest: dict


def materialize(repository, revision, destination):
    """Create a new release from exact tracked public blobs, never working files."""
    if type(revision) is not str or re.fullmatch("[0-9a-f]{40}", revision) is None:
        raise SetupRefused("EXACT_SOURCE_REVISION_REQUIRED")
    repository, destination = Path(repository), Path(destination)
    if (
        not destination.is_absolute()
        or destination.exists()
        or destination.is_symlink()
    ):
        raise SetupRefused("NEW_ABSOLUTE_RELEASE_DIRECTORY_REQUIRED")
    if any(p.is_symlink() for p in destination.parents):
        raise SetupRefused("RELEASE_PARENT_SYMLINK_REFUSED")
    resolved = git(repository, "rev-parse", revision + "^{commit}").decode().strip()
    if resolved != revision:
        raise SetupRefused("EXACT_SOURCE_REVISION_REQUIRED")
    rows, contents = [], {}
    for raw in git(repository, "ls-tree", "-rz", revision).split(b"\0"):
        if not raw:
            continue
        header, path_raw = raw.split(b"\t", 1)
        path = path_raw.decode("utf-8")
        if path not in FILES and not path.startswith(ROOTS):
            continue
        safe_path(path)
        mode, kind, blob = header.decode().split()
        if mode not in ("100644", "100755") or kind != "blob":
            raise SetupRefused("SOURCE_SYMLINK_OR_NONFILE_REFUSED")
        data = git(repository, "cat-file", "blob", blob)
        contents[path] = data
        rows.append(
            {
                "path": path,
                "digest": sha(data),
                "bytes": len(data),
                "executable": mode == "100755",
            }
        )
    required = {
        "pyproject.toml",
        "uv.lock",
        ".agent/DECISIONS.md",
        "carbon/validator_setup/__main__.py",
        "scripts/dev/battery_validator_service/__main__.py",
    }
    if not required <= contents.keys():
        raise SetupRefused("COMPLETE_OPERATOR_SOURCE_REQUIRED")
    if not PUBLIC_RUNTIME_MATERIALS <= contents.keys():
        raise SetupRefused("COMPLETE_PUBLIC_RUNTIME_MATERIAL_REQUIRED")
    sdk = sorted(
        set(re.findall(r"bittensor==([0-9.]+)", contents["pyproject.toml"].decode()))
    )
    if sdk != ["11.1.0"]:
        raise SetupRefused("SDK_PIN_REQUIRES_EXPLICIT_MIGRATION")
    manifest = {
        "schema": SCHEMA,
        "source_revision": revision,
        "source_git_tree": git(repository, "rev-parse", revision + "^{tree}")
        .decode()
        .strip(),
        "sdk": sdk[0],
        "lock_digest": sha(contents["uv.lock"]),
        "files": sorted(rows, key=lambda r: r["path"]),
        "scope": "DEVELOPMENT_OPERATOR_SOURCE_NOT_QUALIFICATION",
        "credentials_and_state": "EXTERNAL_ONLY",
    }
    raw_manifest = encoded(manifest)
    # All validation precedes writes. Refuse concurrent/nonempty destinations.
    destination.mkdir(mode=0o755)
    public_directories = {destination}
    for row in rows:
        target = destination / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        public_directories.update(
            destination / parent for parent in Path(row["path"]).parents
        )
        with target.open("xb") as stream:
            stream.write(contents[row["path"]])
        target.chmod(0o555 if row["executable"] else 0o444)
    (destination / MANIFEST).write_bytes(raw_manifest)
    (destination / MANIFEST).chmod(0o444)
    for directory in public_directories:
        directory.chmod(0o755)
    return verify(destination, sha(raw_manifest))


def verify(root, expected_digest):
    """Verify actual files against an externally pinned manifest digest."""
    root = Path(root)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise SetupRefused("REGULAR_RELEASE_DIRECTORY_REQUIRED")
    if any(p.is_symlink() for p in root.parents):
        raise SetupRefused("RELEASE_PARENT_SYMLINK_REFUSED")
    if (
        type(expected_digest) is not str
        or re.fullmatch("sha256:[0-9a-f]{64}", expected_digest) is None
    ):
        raise SetupRefused("EXTERNAL_BUNDLE_DIGEST_REQUIRED")
    manifest_path = root / MANIFEST
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise SetupRefused("REGULAR_MANIFEST_REQUIRED")
    raw = manifest_path.read_bytes()
    if sha(raw) != expected_digest:
        raise SetupRefused("BUNDLE_MANIFEST_DRIFT")
    try:
        manifest = json.loads(raw)
        if (
            set(manifest)
            != {
                "schema",
                "source_revision",
                "source_git_tree",
                "sdk",
                "lock_digest",
                "files",
                "scope",
                "credentials_and_state",
            }
            or manifest["schema"] != SCHEMA
            or manifest["sdk"] != "11.1.0"
            or manifest["credentials_and_state"] != "EXTERNAL_ONLY"
            or manifest["scope"] != "DEVELOPMENT_OPERATOR_SOURCE_NOT_QUALIFICATION"
        ):
            raise ValueError
        if (
            re.fullmatch("[0-9a-f]{40}", manifest["source_revision"]) is None
            or re.fullmatch("[0-9a-f]{40}", manifest["source_git_tree"]) is None
        ):
            raise ValueError
        if type(manifest["files"]) is not list or not manifest["files"]:
            raise ValueError
        expected = {MANIFEST}
        for row in manifest["files"]:
            if (
                type(row) is not dict
                or set(row) != {"path", "digest", "bytes", "executable"}
                or type(row["bytes"]) is not int
                or row["bytes"] < 0
                or type(row["executable"]) is not bool
            ):
                raise ValueError
            path = str(safe_path(row["path"]))
            if path in expected:
                raise ValueError
            expected.add(path)
            target = root / path
            for parent in target.parents:
                if parent == root:
                    break
                if parent.is_symlink():
                    raise SetupRefused("BUNDLE_SYMLINK_REFUSED")
            info = target.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o222:
                raise SetupRefused("BUNDLE_FILE_NOT_IMMUTABLE")
            data = target.read_bytes()
            if len(data) != row["bytes"] or sha(data) != row["digest"]:
                raise SetupRefused("BUNDLE_SOURCE_DRIFT")
        walked = list(root.rglob("*"))
        if any(p.is_symlink() for p in walked):
            raise SetupRefused("BUNDLE_SYMLINK_REFUSED")
        actual = {p.relative_to(root).as_posix() for p in walked if not p.is_dir()}
        if (
            actual != expected
            or sha((root / "uv.lock").read_bytes()) != manifest["lock_digest"]
        ):
            raise SetupRefused("BUNDLE_FILE_SET_DRIFT")
    except (KeyError, TypeError, ValueError, OSError) as error:
        if isinstance(error, SetupRefused):
            raise
        raise SetupRefused("BUNDLE_SCHEMA_OR_FILE_REFUSED") from None
    return VerifiedBundle(root, expected_digest, manifest)


def select_release(bundle, pointer, service_config, *, expected_current):
    """Switch inactive code only; neither restores state nor starts a process."""
    from carbon.battery.intake import serve_lock_path
    from scripts.dev.battery_validator_service.service import (
        _intake,
        daemon_lock_path,
        load_service,
    )

    bundle = verify(bundle.root, bundle.digest)
    service = load_service(service_config)
    intake = _intake(service, bundle.root)
    pointer = Path(pointer)
    if not pointer.is_absolute() or pointer.is_symlink():
        raise SetupRefused("REGULAR_RELEASE_POINTER_REQUIRED")
    selected = {
        "schema": "carbon.validator-release-selection.v1",
        "release": str(bundle.root),
        "digest": bundle.digest,
        "source_revision": bundle.manifest["source_revision"],
    }
    with ExitStack() as stack:
        for path in (
            pointer.with_name(pointer.name + ".lock"),
            service.state_dir / "operator-runtime.lock",
            service.state_dir / "supervisor.lock",
            daemon_lock_path(service),
            serve_lock_path(intake),
        ):
            stack.enter_context(held_lock(path, exclusive=True))
        current = json.loads(pointer.read_bytes()) if pointer.exists() else None
        if current != expected_current:
            raise SetupRefused("RELEASE_POINTER_CHANGED")
        temporary = pointer.with_name(pointer.name + ".new")
        with temporary.open("xb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(encoded(selected))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, pointer)
    return selected
