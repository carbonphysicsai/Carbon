"""Safe SHA-256 verification for challenge-registry artifact bindings."""

from __future__ import annotations

import errno
import hashlib
import hmac
import os
import re
import stat
from pathlib import Path, PurePosixPath, PureWindowsPath

_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)
_MAX_ARTIFACT_PATH_LENGTH = 1024
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
_SUPPORTS_DIR_FD_OPEN = os.open in os.supports_dir_fd


class ArtifactAccessError(Exception):
    """Safe artifact access failure with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def is_sha256_digest(value: object) -> bool:
    """Return whether *value* implements A3's only supported digest contract."""
    return type(value) is str and _SHA256.fullmatch(value) is not None


def _artifact_parts(value: object) -> tuple[str, ...]:
    if type(value) is not str or not value or len(value) > _MAX_ARTIFACT_PATH_LENGTH:
        raise ArtifactAccessError(
            "artifact.path_invalid", "Artifact path is not a safe relative path."
        )
    if "\\" in value or any(
        ord(character) < 0x20
        or ord(character) == 0x7F
        or 0xD800 <= ord(character) <= 0xDFFF
        for character in value
    ):
        raise ArtifactAccessError(
            "artifact.path_invalid", "Artifact path is not a safe relative path."
        )
    try:
        os.fsencode(value)
    except UnicodeError as exc:
        raise ArtifactAccessError(
            "artifact.path_invalid", "Artifact path is not a safe relative path."
        ) from exc

    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    parts = tuple(value.split("/"))
    if (
        posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ArtifactAccessError(
            "artifact.path_invalid", "Artifact path is not a safe relative path."
        )
    return parts


def _secure_open(artifact_root: Path, parts: tuple[str, ...]) -> int:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if no_follow is None or directory is None or not _SUPPORTS_DIR_FD_OPEN:
        raise ArtifactAccessError(
            "artifact.secure_open_unavailable",
            "Artifact root cannot provide secure descriptor-relative access.",
        )

    opened: list[int] = []
    try:
        opened.append(os.open(artifact_root, os.O_RDONLY | directory | no_follow))
        for index, part in enumerate(parts):
            flags = os.O_RDONLY | no_follow
            if index < len(parts) - 1:
                flags |= directory
            else:
                flags |= _NONBLOCK
            opened.append(os.open(part, flags, dir_fd=opened[-1]))
    except OSError as exc:
        for descriptor in reversed(opened):
            os.close(descriptor)
        if exc.errno == errno.ELOOP:
            raise ArtifactAccessError(
                "artifact.path_escape",
                "Artifact path uses a disallowed symbolic link.",
            ) from exc
        if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
            raise ArtifactAccessError(
                "artifact.missing", "Artifact file could not be read."
            ) from exc
        raise ArtifactAccessError(
            "artifact.unreadable", "Artifact file could not be read."
        ) from exc

    final_descriptor = opened.pop()
    for descriptor in reversed(opened):
        os.close(descriptor)
    return final_descriptor


def digest_artifact(artifact_root: Path, relative_path: object) -> str:
    """Hash one securely opened regular file beneath *artifact_root*."""
    parts = _artifact_parts(relative_path)
    descriptor = _secure_open(artifact_root, parts)

    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ArtifactAccessError(
                "artifact.not_regular_file", "Artifact must be a regular file."
            )
        hasher = hashlib.sha256()
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
        return f"sha256:{hasher.hexdigest()}"
    except ArtifactAccessError:
        raise
    except OSError as exc:
        raise ArtifactAccessError(
            "artifact.unreadable", "Artifact file could not be read."
        ) from exc
    finally:
        os.close(descriptor)


def read_verified_artifact_bytes(
    artifact_root: Path,
    relative_path: object,
    expected_digest: object,
    *,
    max_bytes: int,
) -> bytes:
    """Read one bounded regular file and verify its exact bytes before return."""
    if not is_sha256_digest(expected_digest):
        raise ArtifactAccessError(
            "artifact.digest_invalid",
            "Expected artifact digest is not canonical tagged SHA-256.",
        )
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ArtifactAccessError(
            "artifact.limit_invalid",
            "Artifact byte limit must be a positive built-in integer.",
        )

    parts = _artifact_parts(relative_path)
    descriptor = _secure_open(artifact_root, parts)

    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ArtifactAccessError(
                "artifact.not_regular_file", "Artifact must be a regular file."
            )
        if metadata.st_size > max_bytes:
            raise ArtifactAccessError(
                "artifact.too_large", "Artifact exceeds the configured byte limit."
            )
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            payload = stream.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise ArtifactAccessError(
                "artifact.too_large", "Artifact exceeds the configured byte limit."
            )

        actual_digest = f"sha256:{hashlib.sha256(payload).hexdigest()}"
        if not hmac.compare_digest(actual_digest, expected_digest):
            raise ArtifactAccessError(
                "artifact.digest_mismatch",
                "Actual artifact bytes do not match the expected digest.",
            )
        return payload
    except ArtifactAccessError:
        raise
    except OSError as exc:
        raise ArtifactAccessError(
            "artifact.unreadable", "Artifact file could not be read."
        ) from exc
    finally:
        os.close(descriptor)
