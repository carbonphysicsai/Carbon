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


def _git(repository: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", *arguments],
        cwd=repository,
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
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repository,
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
        "--no-renames",
        "--name-only",
        "--diff-filter=ACDMRTUXB",
        f"{base}...{candidate}",
        "--",
    )
    return tuple(
        normalized_repo_path(line) for line in output.splitlines() if line.strip()
    )


def tracked_paths(repository: Path) -> tuple[str, ...]:
    output = _git(repository, "ls-files")
    return tuple(normalized_repo_path(line) for line in output.splitlines() if line)


def git_blob(repository: Path, reference: str, path: str) -> str:
    normalized = normalized_repo_path(path)
    value = _git(repository, "rev-parse", f"{reference}:{normalized}")
    if not GIT_OID_RE.fullmatch(value):
        raise IdentityMismatch(f"invalid Git blob for {reference}:{normalized}")
    return value
