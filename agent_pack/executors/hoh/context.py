"""Allow-listed progressive disclosure and isolated read-role projections."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
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


def _matches(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


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
                if _matches(path, patterns):
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
        self.protected_patterns = tuple(run_manifest["protected_patterns"])
        self._tracked = frozenset(tracked_paths(self.repository))

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
                or fnmatch.fnmatchcase(path, pattern)
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
            if _matches(normalized, self.protected_patterns):
                raise ScopeViolation(
                    f"protected context request rejected: {normalized}"
                )
            if not _matches(normalized, allowed):
                raise ScopeViolation(
                    f"out-of-authority context request rejected: {normalized}"
                )
            for path in self._expand(normalized):
                if _matches(path, self.protected_patterns):
                    raise ScopeViolation(f"protected context path rejected: {path}")
                if not _matches(path, allowed):
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
        if target.exists():
            for root, directories, files in os.walk(target):
                os.chmod(root, 0o700)
                for name in directories:
                    os.chmod(Path(root) / name, 0o700)
                for name in files:
                    os.chmod(Path(root) / name, 0o600)
            shutil.rmtree(target)
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
        commands = (
            ("init", "--quiet"),
            ("config", "user.name", "Carbon HoH Projection"),
            ("config", "user.email", "carbon-hoh@example.invalid"),
            ("config", "commit.gpgsign", "false"),
            ("add", "--all"),
            ("commit", "--quiet", "--message", "isolated role projection"),
        )
        for command in commands:
            process = subprocess.run(
                ["git", *command],
                cwd=target,
                check=False,
                capture_output=True,
                text=True,
            )
            if process.returncode:
                raise ScopeViolation(
                    f"could not build {role.value} projection: "
                    f"{(process.stderr or process.stdout).strip()}"
                )
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
