"""Canonical hashing, repository identity, and normalized path helpers."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from .models import IdentityMismatch, ScopeViolation

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_OID_RE = re.compile(r"^[0-9a-f]{40}$")


def canonical_json_bytes(value: Any) -> bytes:
    """Encode one JSON-compatible value with stable bytes."""

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def normalized_repo_path(raw: str) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise ScopeViolation(f"path is not normalized repository text: {raw!r}")
    path = PurePosixPath(raw)
    normalized = path.as_posix()
    if (
        normalized != raw
        or path.is_absolute()
        or normalized == "."
        or ".." in path.parts
    ):
        raise ScopeViolation(f"path is not normalized and repository-relative: {raw!r}")
    return normalized


def sanitized_git_environment(
    *, home: str = "/nonexistent-carbon-hoh-home"
) -> dict[str, str]:
    """Return the complete environment for controller-authority Git commands."""

    return {
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": home,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }


def git_command(*arguments: str) -> list[str]:
    """Build a Git command with executable local hooks and fsmonitor disabled."""

    return [
        "git",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
        *arguments,
    ]


def _git(repository: Path, *arguments: str) -> str:
    process = subprocess.run(
        git_command(*arguments),
        cwd=repository,
        env=sanitized_git_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode:
        detail = (process.stderr or process.stdout).strip()
        raise IdentityMismatch(
            f"git {' '.join(arguments)!r} failed: {detail or 'no diagnostic'}"
        )
    return process.stdout.strip()


def git_bytes(repository: Path, *arguments: str) -> bytes:
    """Run one read-only controller Git command and return exact stdout bytes."""

    process = subprocess.run(
        git_command(*arguments),
        cwd=repository,
        env=sanitized_git_environment(),
        check=False,
        capture_output=True,
    )
    if process.returncode:
        detail = (
            (process.stderr or process.stdout).decode("utf-8", errors="replace").strip()
        )
        raise IdentityMismatch(
            f"git {' '.join(arguments)!r} failed: {detail or 'no diagnostic'}"
        )
    return process.stdout


def resolve_repository_root(repository: Path) -> Path:
    return Path(_git(repository, "rev-parse", "--show-toplevel")).resolve()


def resolve_git_common_dir(repository: Path) -> Path:
    raw = _git(repository, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(raw).resolve()


def resolve_commit(repository: Path, reference: str = "HEAD") -> str:
    value = _git(repository, "rev-parse", "--verify", f"{reference}^{{commit}}")
    if not GIT_OID_RE.fullmatch(value):
        raise IdentityMismatch(f"invalid commit identity for {reference!r}: {value!r}")
    return value


def resolve_tree(repository: Path, reference: str = "HEAD") -> str:
    value = _git(repository, "rev-parse", "--verify", f"{reference}^{{tree}}")
    if not GIT_OID_RE.fullmatch(value):
        raise IdentityMismatch(f"invalid tree identity for {reference!r}: {value!r}")
    return value


def head_identity(repository: Path) -> dict[str, str]:
    return {
        "head": resolve_commit(repository),
        "tree": resolve_tree(repository),
    }


def require_ancestor(repository: Path, ancestor: str, descendant: str) -> None:
    """Require one exact commit to be an ancestor of another exact commit."""

    process = subprocess.run(
        git_command("merge-base", "--is-ancestor", ancestor, descendant),
        cwd=repository,
        env=sanitized_git_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode:
        detail = (process.stderr or process.stdout).strip()
        raise IdentityMismatch(
            "candidate does not descend from its pinned authority commit"
            + (f": {detail}" if detail else "")
        )


def require_clean_worktree(repository: Path) -> None:
    if _git(repository, "status", "--porcelain=v1", "--untracked-files=all"):
        raise IdentityMismatch("candidate worktree is not clean and cannot be frozen")


def changed_paths(
    repository: Path, base: str, candidate: str = "HEAD"
) -> tuple[str, ...]:
    output = _git(
        repository,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--no-renames",
        "--name-only",
        "--diff-filter=ACDMRTUXB",
        f"{base}...{candidate}",
        "--",
    )
    return tuple(
        normalized_repo_path(line) for line in output.splitlines() if line.strip()
    )


def tracked_paths(repository: Path, reference: str = "HEAD") -> tuple[str, ...]:
    output = _git(repository, "ls-tree", "-r", "--name-only", reference, "--")
    return tuple(normalized_repo_path(line) for line in output.splitlines() if line)


def git_blob(repository: Path, reference: str, path: str) -> str:
    normalized = normalized_repo_path(path)
    value = _git(repository, "rev-parse", f"{reference}:{normalized}")
    if not GIT_OID_RE.fullmatch(value):
        raise IdentityMismatch(f"invalid Git blob for {reference}:{normalized}")
    return value


def git_blob_bytes(repository: Path, reference: str, path: str) -> bytes:
    """Read one regular-file blob from an immutable tree without filters."""

    normalized = normalized_repo_path(path)
    entry = _git(repository, "ls-tree", reference, "--", normalized)
    fields, separator, recorded = entry.partition("\t")
    metadata = fields.split()
    if (
        not separator
        or recorded != normalized
        or len(metadata) != 3
        or metadata[0] not in {"100644", "100755"}
        or metadata[1] != "blob"
        or not GIT_OID_RE.fullmatch(metadata[2])
    ):
        raise ScopeViolation(f"candidate path is not a regular Git blob: {normalized}")
    return git_bytes(repository, "cat-file", "blob", metadata[2])


def git_file_mode(repository: Path, reference: str, path: str) -> int:
    """Return the executable mode of one exact regular-file tree entry."""

    normalized = normalized_repo_path(path)
    entry = _git(repository, "ls-tree", reference, "--", normalized)
    fields, separator, recorded = entry.partition("\t")
    metadata = fields.split()
    if (
        not separator
        or recorded != normalized
        or len(metadata) != 3
        or metadata[0] not in {"100644", "100755"}
        or metadata[1] != "blob"
    ):
        raise ScopeViolation(f"candidate path is not a regular Git blob: {normalized}")
    return 0o755 if metadata[0] == "100755" else 0o644
