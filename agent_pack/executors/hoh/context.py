"""Allow-listed progressive disclosure and isolated read-role projections."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .identity import digest_file, normalized_repo_path, tracked_paths
from .models import PacketValidationError, Role, ScopeViolation

DEFAULT_PROTECTED_PATTERNS = (
    ".env",
    ".env.*",
    ".carbon-hidden/**",
    "**/*credential*",
    "**/*private_key*",
    "**/*secret*",
    "**/hidden_evaluation/**",
    "**/official_cases/**",
    "**/private_validator/**",
    "**/protected_exam/**",
    "**/reconstruction_private/**",
)

SECRET_VALUE_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
    "CODEX_API_KEY=",
    "OPENAI_API_KEY=",
    "PRODUCTION_CREDENTIAL=",
)

PATH_TOKEN = re.compile(r"(?<![A-Za-z0-9._-])(?:[A-Za-z0-9._-]+/)+[A-Za-z0-9._-]+")


def path_matches(path: str, patterns: Iterable[str]) -> bool:
    """Match repository policy globs, where a leading ``**/`` may match zero dirs."""

    for pattern in patterns:
        if fnmatch.fnmatchcase(path, pattern):
            return True
        # Python's fnmatch treats a leading **/ as requiring at least one
        # directory, while repository policy uses it to mean zero or more.
        while pattern.startswith("**/"):
            pattern = pattern[3:]
            if fnmatch.fnmatchcase(path, pattern):
                return True
    return False


def assert_payload_safe(value: Any, protected_patterns: Iterable[str]) -> None:
    """Reject obvious credential material and protected path references."""

    patterns = tuple(protected_patterns)

    def visit(item: Any, label: str) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                lowered = str(key).lower()
                if any(
                    word in lowered for word in ("api_key", "password", "private_key")
                ):
                    raise PacketValidationError(f"protected value key at {label}.{key}")
                visit(nested, f"{label}.{key}")
        elif isinstance(item, list):
            for index, nested in enumerate(item):
                visit(nested, f"{label}[{index}]")
        elif isinstance(item, str):
            if any(marker in item for marker in SECRET_VALUE_MARKERS):
                raise PacketValidationError(f"protected credential material at {label}")
            candidates = [item] if item and "/" in item else []
            candidates.extend(match.group(0) for match in PATH_TOKEN.finditer(item))
            for candidate in candidates:
                try:
                    path = normalized_repo_path(candidate)
                except ScopeViolation:
                    continue
                if path_matches(path, patterns):
                    raise PacketValidationError(f"protected path at {label}: {path}")

    visit(value, "packet")


class ContextBroker:
    """Grant exact tracked paths and build disposable role repositories."""

    def __init__(
        self,
        repository: Path,
        state_root: Path,
        run_manifest: dict[str, Any],
    ) -> None:
        self.repository = repository.resolve()
        self.state_root = state_root.resolve()
        self.manifest = run_manifest
        self.protected_patterns = tuple(
            dict.fromkeys(
                (*DEFAULT_PROTECTED_PATTERNS, *run_manifest["protected_patterns"])
            )
        )
        self._tracked = frozenset(tracked_paths(self.repository))

    @staticmethod
    def _make_directory_removable(path: Path) -> bool:
        """Open and chmod one directory without ever following a symlink."""

        try:
            identity = os.lstat(path)
        except FileNotFoundError:
            return False
        if stat.S_ISLNK(identity.st_mode):
            path.unlink()
            return False
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (identity.st_dev, identity.st_ino):
                raise ScopeViolation(
                    f"projection cleanup identity changed while opening {path}"
                )
            os.fchmod(descriptor, 0o700)
        finally:
            os.close(descriptor)
        return True

    @staticmethod
    def _remove_projection(target: Path) -> None:
        """Remove a prior projection without following role-created symlinks."""

        try:
            target_identity = os.lstat(target)
        except FileNotFoundError:
            return
        if stat.S_ISLNK(target_identity.st_mode):
            target.unlink()
            return
        try:
            for root, directories, files in os.walk(
                target, topdown=True, followlinks=False
            ):
                root_path = Path(root)
                if not ContextBroker._make_directory_removable(root_path):
                    directories.clear()
                    continue
                for name in tuple(directories):
                    entry = root_path / name
                    if not ContextBroker._make_directory_removable(entry):
                        directories.remove(name)
                for name in files:
                    entry = root_path / name
                    try:
                        identity = os.lstat(entry)
                    except FileNotFoundError:
                        continue
                    if stat.S_ISLNK(identity.st_mode):
                        entry.unlink()
            shutil.rmtree(target)
        except OSError as error:
            raise ScopeViolation(
                f"could not safely remove prior role projection: {error}"
            ) from error

    def _expand(self, raw_path: str) -> tuple[str, ...]:
        path = normalized_repo_path(raw_path)
        if path in self._tracked:
            return (path,)
        prefix = f"{path.rstrip('/')}/"
        children = tuple(item for item in self._tracked if item.startswith(prefix))
        if not children:
            raise ScopeViolation(f"context path is not tracked: {path}")
        return children

    def matching_tracked(self, patterns: Iterable[str]) -> tuple[str, ...]:
        """Return existing tracked files selected by exact, prefix, or glob paths."""

        self._tracked = frozenset(tracked_paths(self.repository))
        selected: set[str] = set()
        for raw_pattern in patterns:
            pattern = normalized_repo_path(raw_pattern)
            prefix = f"{pattern.rstrip('/')}/"
            selected.update(
                path
                for path in self._tracked
                if path == pattern
                or path.startswith(prefix)
                or path_matches(path, (pattern,))
            )
        return tuple(sorted(selected))

    def grant(
        self,
        role: Role,
        requested: Iterable[str],
        *,
        iteration: int,
    ) -> tuple[tuple[str, ...], tuple[dict[str, Any], ...]]:
        self._tracked = frozenset(tracked_paths(self.repository))
        allowed = tuple(self.manifest["context_allow_paths"][role.value.lower()])
        granted: set[str] = set()
        disclosures: list[dict[str, Any]] = []
        for raw in requested:
            normalized = normalized_repo_path(raw)
            if path_matches(normalized, self.protected_patterns):
                raise ScopeViolation(
                    f"protected context request rejected: {normalized}"
                )
            if not path_matches(normalized, allowed):
                raise ScopeViolation(
                    f"out-of-authority context request rejected: {normalized}"
                )
            for path in self._expand(normalized):
                if path_matches(path, self.protected_patterns):
                    raise ScopeViolation(f"protected context path rejected: {path}")
                if not path_matches(path, allowed):
                    raise ScopeViolation(
                        f"expanded context path is out of authority: {path}"
                    )
                source = self.repository / path
                if source.is_symlink() or not source.is_file():
                    raise ScopeViolation(f"context path is not a regular file: {path}")
                granted.add(path)
                disclosures.append(
                    {
                        "role": role.value,
                        "iteration": iteration,
                        "path": path,
                        "sha256": digest_file(source),
                    }
                )
        return tuple(sorted(granted)), tuple(
            sorted(disclosures, key=lambda item: item["path"])
        )

    def projection(
        self,
        role: Role,
        iteration: int,
        paths: Iterable[str],
        candidate: dict[str, str],
    ) -> Path:
        target = self.state_root / "projections" / str(iteration) / role.value.lower()
        self._remove_projection(target)
        target.mkdir(parents=True, mode=0o700)
        for path in sorted(set(paths)):
            source = self.repository / normalized_repo_path(path)
            destination = target / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination, follow_symlinks=False)
        metadata = {
            "candidate": candidate,
            "role": role.value,
            "disclosed_paths": sorted(set(paths)),
        }
        (target / ".carbon-hoh-context.json").write_text(
            json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        self._initialize_projection_repository(target, role.value)
        if role is Role.DEVELOPER:
            shadow = self.developer_shadow(iteration)
            self._remove_projection(shadow)
            shutil.copytree(target, shadow, symlinks=True)
        if role is not Role.DEVELOPER:
            for root, directories, files in os.walk(target):
                if Path(root).name == ".git" or ".git" in Path(root).parts:
                    continue
                for name in directories:
                    os.chmod(Path(root) / name, 0o500)
                for name in files:
                    os.chmod(Path(root) / name, 0o400)
            os.chmod(target, 0o500)
        return target

    def developer_shadow(self, iteration: int) -> Path:
        """Return controller-owned Git metadata never exposed to Developer."""

        return self.state_root / "developer-shadows" / str(iteration)

    def seal_developer_projection(self, workspace: Path, iteration: int) -> Path:
        """Copy only Developer worktree files into trusted controller Git metadata.

        The writable role repository's entire ``.git`` directory is deliberately
        discarded.  No host-side Git command may consume metadata controlled by
        the role process.
        """

        shadow = self.developer_shadow(iteration)
        if not shadow.is_dir() or not (shadow / ".git").is_dir():
            raise ScopeViolation("trusted Developer shadow repository is missing")

        for entry in tuple(shadow.iterdir()):
            if entry.name == ".git":
                continue
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()

        def traversal_error(error: OSError) -> None:
            raise ScopeViolation(
                f"could not safely read Developer worktree: {error}"
            ) from error

        for root, directories, files in os.walk(
            workspace,
            topdown=True,
            onerror=traversal_error,
            followlinks=False,
        ):
            root_path = Path(root)
            relative_root = root_path.relative_to(workspace)
            if ".git" in relative_root.parts:
                raise ScopeViolation("Developer worktree contains nested Git metadata")
            for name in tuple(directories):
                source = root_path / name
                relative = relative_root / name
                identity = os.lstat(source)
                if name == ".git":
                    directories.remove(name)
                    if relative_root != Path("."):
                        raise ScopeViolation(
                            "Developer worktree contains nested Git metadata"
                        )
                    continue
                if not stat.S_ISDIR(identity.st_mode):
                    raise ScopeViolation(
                        f"Developer worktree entry is not a regular directory: {relative}"
                    )
                (shadow / relative).mkdir(parents=True, exist_ok=True)
            for name in files:
                source = root_path / name
                relative = relative_root / name
                if ".git" in relative.parts:
                    raise ScopeViolation("Developer worktree contains Git metadata")
                identity = os.lstat(source)
                if not stat.S_ISREG(identity.st_mode):
                    raise ScopeViolation(
                        f"Developer result has unsupported Git mode: {relative}"
                    )
                destination = shadow / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination, follow_symlinks=False)
                os.chmod(destination, stat.S_IMODE(identity.st_mode))

        self._commit_projection(
            shadow,
            "sealed Developer worktree",
            allow_empty=True,
        )
        return shadow

    def _initialize_projection_repository(self, target: Path, label: str) -> None:
        commands = (
            ("init", "--quiet"),
            ("config", "user.name", "Carbon HoH Projection"),
            ("config", "user.email", "carbon-hoh@example.invalid"),
            ("config", "commit.gpgsign", "false"),
            ("add", "--all"),
            ("commit", "--quiet", "--message", "isolated role projection"),
        )
        with tempfile.TemporaryDirectory(
            prefix="empty-hooks-", dir=self.state_root
        ) as hooks_directory:
            for command in commands:
                process = subprocess.run(
                    ["git", "-c", f"core.hooksPath={hooks_directory}", *command],
                    cwd=target,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if process.returncode:
                    raise ScopeViolation(
                        f"could not build {label} projection: "
                        f"{(process.stderr or process.stdout).strip()}"
                    )

    def _commit_projection(
        self,
        target: Path,
        message: str,
        *,
        allow_empty: bool = False,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="empty-hooks-", dir=self.state_root
        ) as hooks_directory:
            added = subprocess.run(
                ["git", "-c", f"core.hooksPath={hooks_directory}", "add", "--all"],
                cwd=target,
                check=False,
                capture_output=True,
                text=True,
            )
            command = [
                "git",
                "-c",
                f"core.hooksPath={hooks_directory}",
                "commit",
                "--quiet",
                "--message",
                message,
            ]
            if allow_empty:
                command.append("--allow-empty")
            committed = subprocess.run(
                command,
                cwd=target,
                check=False,
                capture_output=True,
                text=True,
            )
        if added.returncode or committed.returncode:
            detail = (
                added.stderr or added.stdout or committed.stderr or committed.stdout
            )
            raise ScopeViolation(
                f"could not seal Developer projection: {detail.strip()}"
            )
