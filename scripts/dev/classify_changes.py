#!/usr/bin/env python3
"""Classify a strict changed-path manifest into Carbon CI acceptance scope."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath


class ChangeScope(StrEnum):
    """Ordered acceptance scopes; unknown paths deliberately use the full lane."""

    DERIVED_DOCUMENTATION = "DERIVED_DOCUMENTATION"
    CONTRACT_AUTHORITY = "CONTRACT_AUTHORITY"
    RUNTIME_FULL = "RUNTIME_FULL"


@dataclass(frozen=True)
class PathClassification:
    path: str
    scope: ChangeScope
    rule: str
    unknown: bool = False


@dataclass(frozen=True)
class Classification:
    scope: ChangeScope
    paths: tuple[PathClassification, ...]

    @property
    def unknown_paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.paths if item.unknown)


_RUNTIME_PREFIXES = (
    "carbon/",
    "tests/",
    "scripts/",
    ".github/workflows/",
    ".devcontainer/",
    "tools/",
    "bin/",
    "docs/development/carbon_hub/tools/",
)
_RUNTIME_EXACT = frozenset(
    {
        ".agent/CODE_AUTHORITY.toml",
        ".dockerignore",
        ".python-version",
        "docs/development/ENVIRONMENT.md",
        "MANIFEST.in",
        "Pipfile",
        "Pipfile.lock",
        "noxfile.py",
        "poetry.lock",
        "pyproject.toml",
        "setup.cfg",
        "setup.py",
        "tox.ini",
        "uv.lock",
    }
)
_CONTRACT_PREFIXES = (
    ".agent/",
    ".github/rulesets/",
    "agent_pack/",
    "Business/",
    "Design_Specs/",
    "docs/context/",
    "docs/development/carbon_hub/data/",
    "docs/development/carbon_hub/orientation/",
)
_CONTRACT_EXACT = frozenset(
    {
        ".github/pull_request_template.md",
        "AGENTS.md",
        "CONSTITUTION.md",
        "README.md",
        "docs/development/carbon_hub/AGENTS.md",
    }
)
_DERIVED_EXACT = frozenset(
    {
        "docs/development/carbon_hub/Carbon_Development_Hub_v2.md",
        "docs/development/carbon_hub/README.md",
        "docs/development/carbon_hub/data/hub_index_v2.yaml",
        "docs/development/carbon_hub/index.html",
        "docs/development/carbon_hub/interactive.html",
        "docs/development/carbon_hub/orientation/CHANGE_ROUTING.md",
        "docs/development/carbon_hub/orientation/GLOSSARY.md",
        "docs/development/carbon_hub/orientation/START_HERE.md",
    }
)
_DERIVED_PAGE_RE = re.compile(
    r"docs/development/carbon_hub/explainers/(?:tickets|waves)/[^/]+\.md"
)


class ChangeClassificationError(RuntimeError):
    """A manifest or Git comparison could not be established."""


def normalize_path(raw_path: str) -> str:
    """Return one safe repository-relative Git path or fail closed."""

    if "\\" in raw_path:
        raise ChangeClassificationError(
            f"Changed path uses a non-Git separator: {raw_path!r}"
        )
    pure = PurePosixPath(raw_path)
    normalized = pure.as_posix()
    if (
        not raw_path
        or raw_path != normalized
        or pure.is_absolute()
        or ".." in pure.parts
        or normalized == "."
    ):
        raise ChangeClassificationError(
            f"Changed path is not normalized and repository-relative: {raw_path!r}"
        )
    return normalized


def classify_path(raw_path: str) -> PathClassification:
    path = normalize_path(raw_path)
    if path in _RUNTIME_EXACT:
        return PathClassification(path, ChangeScope.RUNTIME_FULL, "runtime exact path")
    if path.startswith(_RUNTIME_PREFIXES):
        return PathClassification(path, ChangeScope.RUNTIME_FULL, "runtime prefix")
    if re.fullmatch(r"requirements(?:[-_.][^/]*)?\.txt", path, re.IGNORECASE):
        return PathClassification(path, ChangeScope.RUNTIME_FULL, "dependency manifest")
    if path in _DERIVED_EXACT:
        return PathClassification(
            path, ChangeScope.DERIVED_DOCUMENTATION, "derived exact allow-list"
        )
    if _DERIVED_PAGE_RE.fullmatch(path):
        return PathClassification(
            path, ChangeScope.DERIVED_DOCUMENTATION, "derived page allow-list"
        )
    if path in _CONTRACT_EXACT:
        return PathClassification(
            path, ChangeScope.CONTRACT_AUTHORITY, "contract exact path"
        )
    if path.startswith(_CONTRACT_PREFIXES):
        return PathClassification(
            path, ChangeScope.CONTRACT_AUTHORITY, "contract authority prefix"
        )
    return PathClassification(
        path,
        ChangeScope.RUNTIME_FULL,
        "unknown path fails closed",
        unknown=True,
    )


def classify_paths(paths: list[str] | tuple[str, ...]) -> Classification:
    """Classify the complete manifest, choosing the strongest required lane."""

    unique = tuple(sorted({normalize_path(path) for path in paths}))
    if not unique:
        fallback = PathClassification(
            "<empty-manifest>",
            ChangeScope.RUNTIME_FULL,
            "empty manifest fails closed",
            unknown=True,
        )
        return Classification(ChangeScope.RUNTIME_FULL, (fallback,))
    classified = tuple(classify_path(path) for path in unique)
    if any(item.scope is ChangeScope.RUNTIME_FULL for item in classified):
        scope = ChangeScope.RUNTIME_FULL
    elif any(item.scope is ChangeScope.CONTRACT_AUTHORITY for item in classified):
        scope = ChangeScope.CONTRACT_AUTHORITY
    else:
        scope = ChangeScope.DERIVED_DOCUMENTATION
    return Classification(scope, classified)


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
    )


def _resolve_commit(repository: Path, reference: str, *, label: str) -> str:
    stripped = reference.strip()
    if not stripped or set(stripped) == {"0"}:
        raise ChangeClassificationError(
            f"{label} is empty or all-zero; a real comparison commit is required."
        )
    process = _git(
        repository,
        "rev-parse",
        "--verify",
        "--quiet",
        "--end-of-options",
        f"{stripped}^{{commit}}",
    )
    resolved = process.stdout.decode("ascii", "replace").strip()
    if process.returncode or not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise ChangeClassificationError(
            f"Could not resolve {label} {stripped!r}; fetch the comparison history."
        )
    return resolved


def changed_paths(repository: Path, base_reference: str) -> tuple[str, ...]:
    """Return committed, staged, and unstaged tracked paths for the comparison."""

    base = _resolve_commit(repository, base_reference, label="comparison base")
    head = _resolve_commit(repository, "HEAD", label="HEAD")
    merge_process = _git(repository, "merge-base", base, head)
    merge_base = merge_process.stdout.decode("ascii", "replace").strip()
    if merge_process.returncode or not re.fullmatch(r"[0-9a-f]{40}", merge_base):
        raise ChangeClassificationError(
            "Could not compute a merge base; fetch complete shared history."
        )
    commands = (
        (
            "diff",
            "--no-renames",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            "-z",
            merge_base,
            head,
            "--",
        ),
        (
            "diff",
            "--cached",
            "--no-renames",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            "-z",
            "--",
        ),
        (
            "diff",
            "--no-renames",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            "-z",
            "--",
        ),
    )
    paths: set[str] = set()
    for command in commands:
        process = _git(repository, *command)
        if process.returncode:
            detail = (process.stderr or process.stdout).decode("utf-8", "replace")
            raise ChangeClassificationError(
                f"Git could not build the changed-path manifest: {detail.strip()}"
            )
        paths.update(
            item.decode("utf-8", "surrogateescape")
            for item in process.stdout.split(b"\0")
            if item
        )
    return tuple(sorted(paths))


def _manifest_paths(path: Path) -> tuple[str, ...]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ChangeClassificationError(
            f"Cannot read manifest {path}: {error}"
        ) from error
    stripped = text.lstrip()
    if stripped.startswith("["):
        try:
            value = json.loads(text)
        except json.JSONDecodeError as error:
            raise ChangeClassificationError(
                f"Manifest {path} is invalid JSON: {error}"
            ) from error
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ChangeClassificationError(
                f"JSON manifest {path} must be an array of path strings"
            )
        return tuple(value)
    return tuple(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def _payload(classification: Classification) -> dict[str, object]:
    return {
        "scope": classification.scope.value,
        "path_count": len(classification.paths),
        "unknown_paths": list(classification.unknown_paths),
        "paths": [
            {
                "path": item.path,
                "scope": item.scope.value,
                "rule": item.rule,
                "unknown": item.unknown,
            }
            for item in classification.paths
        ],
    }


def _write_github_output(path: Path, classification: Classification) -> None:
    values = {
        "change_scope": classification.scope.value,
        "runtime_full": str(classification.scope is ChangeScope.RUNTIME_FULL).lower(),
        "contract_authority": str(
            classification.scope is ChangeScope.CONTRACT_AUTHORITY
        ).lower(),
        "derived_documentation": str(
            classification.scope is ChangeScope.DERIVED_DOCUMENTATION
        ).lower(),
        "unknown_path_count": str(len(classification.unknown_paths)),
        "changed_path_count": str(len(classification.paths)),
    }
    try:
        with path.open("a", encoding="utf-8") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")
    except OSError as error:
        raise ChangeClassificationError(
            f"Cannot append classifier outputs to {path}: {error}"
        ) from error


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base", help="Git comparison base/ref.")
    source.add_argument("--manifest", type=Path, help="Newline or JSON path manifest.")
    parser.add_argument(
        "--github-output",
        type=Path,
        help="Append stable scalar outputs to a GitHub Actions output file.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        paths = (
            changed_paths(args.repository.resolve(), args.base)
            if args.base is not None
            else _manifest_paths(args.manifest)
        )
        classification = classify_paths(paths)
        if args.github_output is not None:
            _write_github_output(args.github_output, classification)
    except (ChangeClassificationError, OSError) as error:
        print(f"Change classification error: {error}", file=sys.stderr)
        return 2
    payload = _payload(classification)
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"Carbon change scope: {classification.scope.value}")
        for item in classification.paths:
            unknown = " [UNKNOWN -> FAIL CLOSED]" if item.unknown else ""
            print(f"  {item.scope.value}: {item.path} ({item.rule}){unknown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
