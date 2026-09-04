"""Descriptor-safe external run-state persistence under the Git common directory."""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .identity import canonical_json_bytes, resolve_git_common_dir
from .models import IdentityMismatch


class StateStore:
    """Own one private run directory without following filesystem links."""

    def __init__(self, root: Path) -> None:
        self.root = Path(os.path.abspath(root))
        descriptor = self._open_root(create=True)
        os.close(descriptor)

    @classmethod
    def for_repository(cls, repository: Path, run_id: str) -> StateStore:
        common = resolve_git_common_dir(repository)
        return cls(common / ".carbon-hoh" / "runs" / run_id)

    @property
    def manifest_path(self) -> Path:
        return self.root / "run_manifest.json"

    @property
    def state_path(self) -> Path:
        return self.root / "controller_state.json"

    @property
    def pending_install_path(self) -> Path:
        return self.root / "pending_install.json"

    @property
    def lock_path(self) -> Path:
        return self.root / "controller.lock"

    def _open_root(self, *, create: bool) -> int:
        """Traverse every absolute component with ``O_NOFOLLOW``."""

        descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        final_created = False
        try:
            components = self.root.parts[1:]
            for index, component in enumerate(components):
                created = False
                if create:
                    try:
                        os.mkdir(component, 0o700, dir_fd=descriptor)
                        created = True
                    except FileExistsError:
                        pass
                if index == len(components) - 1:
                    final_created = created
                child = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                os.close(descriptor)
                descriptor = child
            identity = os.fstat(descriptor)
            if identity.st_uid != os.getuid() or not stat.S_ISDIR(identity.st_mode):
                raise IdentityMismatch(
                    f"external state root is not an owned directory: {self.root}"
                )
            if stat.S_IMODE(identity.st_mode) & 0o077:
                raise IdentityMismatch(
                    f"external state root is not private mode-0700: {self.root}"
                )
            if final_created:
                os.fchmod(descriptor, 0o700)
            return descriptor
        except (OSError, IdentityMismatch) as error:
            os.close(descriptor)
            if isinstance(error, IdentityMismatch):
                raise
            raise IdentityMismatch(
                f"external state root is unsafe: {self.root}: {error}"
            ) from error

    @staticmethod
    def _require_owned_regular(descriptor: int, label: str) -> os.stat_result:
        identity = os.fstat(descriptor)
        if (
            identity.st_uid != os.getuid()
            or not stat.S_ISREG(identity.st_mode)
            or identity.st_nlink != 1
        ):
            raise IdentityMismatch(f"{label} is not one owned regular file")
        return identity

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Serialize every state/ref transaction with a no-follow lock file."""

        root_descriptor = self._open_root(create=False)
        descriptor = -1
        try:
            try:
                descriptor = os.open(
                    "controller.lock",
                    os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=root_descriptor,
                )
                self._require_owned_regular(descriptor, "controller lock")
                os.fchmod(descriptor, 0o600)
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            except OSError as error:
                raise IdentityMismatch(f"controller lock is unsafe: {error}") from error
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(root_descriptor)

    def _exists(self, name: str) -> bool:
        root_descriptor = self._open_root(create=False)
        try:
            try:
                os.stat(name, dir_fd=root_descriptor, follow_symlinks=False)
            except FileNotFoundError:
                return False
            return True
        finally:
            os.close(root_descriptor)

    def _atomic_write(self, name: str, value: Any) -> None:
        payload = canonical_json_bytes(value)
        root_descriptor = self._open_root(create=False)
        temporary_name = f".{name}.{secrets.token_hex(16)}"
        descriptor = -1
        try:
            try:
                existing = os.stat(name, dir_fd=root_descriptor, follow_symlinks=False)
            except FileNotFoundError:
                existing = None
            if existing is not None and (
                existing.st_uid != os.getuid()
                or not stat.S_ISREG(existing.st_mode)
                or existing.st_nlink != 1
            ):
                raise IdentityMismatch(f"external state target is unsafe: {name}")
            descriptor = os.open(
                temporary_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=root_descriptor,
            )
            identity = self._require_owned_regular(descriptor, "temporary state file")
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fchmod(descriptor, 0o600)
            os.fsync(descriptor)
            named = os.stat(
                temporary_name, dir_fd=root_descriptor, follow_symlinks=False
            )
            if (named.st_dev, named.st_ino) != (identity.st_dev, identity.st_ino):
                raise IdentityMismatch("temporary state file was replaced")
            os.replace(
                temporary_name,
                name,
                src_dir_fd=root_descriptor,
                dst_dir_fd=root_descriptor,
            )
            installed = os.stat(name, dir_fd=root_descriptor, follow_symlinks=False)
            if (installed.st_dev, installed.st_ino) != (
                identity.st_dev,
                identity.st_ino,
            ):
                raise IdentityMismatch("installed state file identity changed")
            os.fsync(root_descriptor)
        except OSError as error:
            raise IdentityMismatch(
                f"cannot atomically write {name}: {error}"
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                os.unlink(temporary_name, dir_fd=root_descriptor)
            except FileNotFoundError:
                pass
            os.close(root_descriptor)

    def initialize(self, run_manifest: dict[str, Any], state: dict[str, Any]) -> None:
        if self._exists("run_manifest.json") or self._exists("controller_state.json"):
            raise IdentityMismatch(f"run state already exists at {self.root}")
        self._atomic_write("run_manifest.json", run_manifest)
        self._atomic_write("controller_state.json", state)

    def save_state(self, state: dict[str, Any]) -> None:
        if not self._exists("run_manifest.json"):
            raise IdentityMismatch("run manifest is missing from external state")
        self._atomic_write("controller_state.json", state)

    def save_pending_install(self, pending: dict[str, Any]) -> None:
        self._atomic_write("pending_install.json", pending)

    def load_pending_install(self) -> dict[str, Any] | None:
        if not self._exists("pending_install.json"):
            return None
        return self._load("pending_install.json", "pending candidate install")

    def clear_pending_install(self) -> None:
        root_descriptor = self._open_root(create=False)
        try:
            try:
                identity = os.stat(
                    "pending_install.json",
                    dir_fd=root_descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                return
            if (
                identity.st_uid != os.getuid()
                or not stat.S_ISREG(identity.st_mode)
                or identity.st_nlink != 1
            ):
                raise IdentityMismatch("pending candidate install path is unsafe")
            os.unlink("pending_install.json", dir_fd=root_descriptor)
            os.fsync(root_descriptor)
        finally:
            os.close(root_descriptor)

    def load_manifest(self) -> dict[str, Any]:
        return self._load("run_manifest.json", "run manifest")

    def load_state(self) -> dict[str, Any]:
        return self._load("controller_state.json", "controller state")

    def _load(self, name: str, label: str) -> dict[str, Any]:
        root_descriptor = self._open_root(create=False)
        descriptor = -1
        try:
            descriptor = os.open(
                name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=root_descriptor
            )
            self._require_owned_regular(descriptor, label)
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
            value = json.loads(b"".join(chunks).decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise IdentityMismatch(
                f"cannot load {label} {self.root / name}: {error}"
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(root_descriptor)
        if not isinstance(value, dict):
            raise IdentityMismatch(f"{label} must be a JSON object")
        return value
