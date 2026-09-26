"""Provider credentials: file-backed, owner-only, never printable.

The key file checks follow ``carbon.development_session.agent`` (not a symlink,
a regular file, bounded size, one line) and add owner-only mode and ownership
by the current user. A loaded key is wrapped in :class:`Secret`, whose ``str``
and ``repr`` are redacted, so an accidental format or log call cannot print it.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

__all__ = [
    "CredentialProvider",
    "CredentialStatus",
    "CredentialUnavailable",
    "FileCredentialProvider",
    "Secret",
]

MAX_CREDENTIAL_BYTES = 1024


class CredentialStatus(StrEnum):
    CONFIGURED = "configured"
    NOT_CONFIGURED = "credential_not_configured"
    UNSAFE = "credential_file_unsafe"
    INVALID = "credential_file_invalid"


class CredentialUnavailable(Exception):
    """A credential could not be loaded; carries only a status, never content."""

    def __init__(self, status: CredentialStatus) -> None:
        self.status = status
        super().__init__(str(status))


class Secret:
    """A credential value that refuses to render itself."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "Secret(<redacted>)"

    __str__ = __repr__

    def __reduce__(self):  # pragma: no cover - defensive
        raise TypeError("Secret is not serialisable")


class CredentialProvider(Protocol):
    def status(self) -> CredentialStatus: ...

    def load(self) -> Secret: ...


@dataclass(frozen=True)
class FileCredentialProvider:
    """Reads one key from an owner-only file. ``path=None`` means not configured."""

    path: Path | None

    def _check(self) -> CredentialStatus:
        if self.path is None:
            return CredentialStatus.NOT_CONFIGURED
        try:
            info = os.lstat(self.path)
        except FileNotFoundError:
            return CredentialStatus.NOT_CONFIGURED
        except OSError:
            return CredentialStatus.UNSAFE
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            return CredentialStatus.UNSAFE
        if stat.S_IMODE(info.st_mode) & 0o077:
            return CredentialStatus.UNSAFE
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            return CredentialStatus.UNSAFE
        if info.st_size == 0 or info.st_size > MAX_CREDENTIAL_BYTES:
            return CredentialStatus.INVALID
        return CredentialStatus.CONFIGURED

    def status(self) -> CredentialStatus:
        status = self._check()
        if status is not CredentialStatus.CONFIGURED:
            return status
        try:
            self.load()
        except CredentialUnavailable as refused:
            return refused.status
        return status

    def load(self) -> Secret:
        status = self._check()
        if status is not CredentialStatus.CONFIGURED:
            raise CredentialUnavailable(status)
        assert self.path is not None
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self.path, flags)
        except OSError:
            raise CredentialUnavailable(CredentialStatus.UNSAFE) from None
        with os.fdopen(fd, "rb") as handle:
            raw = handle.read(MAX_CREDENTIAL_BYTES + 1)
        if len(raw) > MAX_CREDENTIAL_BYTES:
            raise CredentialUnavailable(CredentialStatus.INVALID)
        try:
            value = raw.decode("ascii").strip()
        except UnicodeDecodeError:
            raise CredentialUnavailable(CredentialStatus.INVALID) from None
        if not value or any(ch.isspace() for ch in value):
            raise CredentialUnavailable(CredentialStatus.INVALID)
        return Secret(value)
