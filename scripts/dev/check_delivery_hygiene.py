#!/usr/bin/env python3
"""Reject workstation-specific text and non-substantive introduced commits.

The checker uses only the Python standard library.  By default it scans every
tracked path changed between the comparison merge base and ``HEAD``, plus
staged and unstaged versions of those paths.  ``--all-tree`` expands the text
scan to the complete tracked tree.  In both modes, every introduced commit is
checked for author/committer identity, forbidden completion-only intent, empty
trees, and evidence-only changes.

The optional allow-list is deliberately exact and line oriented.  Non-comment
lines have four tab-separated fields:

``text<TAB>repo/path<TAB>exact matched value<TAB>reason``
``commit<TAB>40-character SHA<TAB>message|empty|evidence-only<TAB>reason``

Reasons must be meaningful.  Globs, regular expressions, directory-wide text
exceptions, and abbreviated commit IDs are not supported.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

DEFAULT_ALLOWLIST = Path("scripts/dev/delivery_hygiene_allowlist.txt")
FORBIDDEN_COMMIT_INTENT = (
    "record successful ci",
    "record final review evidence",
    "evidence seal",
    "record merge evidence",
    "retrigger validation",
)
_FORBIDDEN_COMMIT_SUBJECT_RE = re.compile(
    r"^(?:(?:[a-z0-9]+(?:-[a-z0-9]+)*):\s*)?"
    r"(?P<intent>"
    + "|".join(re.escape(value) for value in FORBIDDEN_COMMIT_INTENT)
    + r")"
    r"[.!]?$",
    re.IGNORECASE,
)
COMMIT_RULES = frozenset({"message", "empty", "evidence-only"})
PLACEHOLDER_USERNAMES = frozenset({"user", "username"})

_PATH_USER = r"(?:<(?P<placeholder>[^<>\r\n/\\]+)>|(?P<username>[\w](?:[\w.-]*[\w])?))"
_HOST_PATH_RE = re.compile(
    rf"(?P<value>"
    rf"(?:"
    rf"(?<![A-Za-z0-9_.-])/(?:Users|home)"
    rf"|(?<![A-Za-z0-9_.-])[A-Za-z]:[\\/]+Users"
    rf")[\\/]+{_PATH_USER}"
    rf")"
)
_LOCAL_EMAIL_RE = re.compile(
    r"(?P<value>(?<![\w.+-])[\w.+-]+@[A-Za-z0-9.-]+\.local\b)",
    re.IGNORECASE,
)
_OBVIOUS_HOST_RE = re.compile(
    r"(?P<value>\b(?:"
    r"(?:[A-Za-z0-9]+-)+macbook(?:-pro|-air)?(?:-[0-9]+)?"
    r"|macbook(?:-pro|-air)(?:-[0-9]+)?"
    r"|(?:desktop|laptop|workstation)-(?=[A-Za-z0-9.-]*[0-9])[A-Za-z0-9][A-Za-z0-9.-]*"
    r"|[A-Za-z][A-Za-z0-9-]*-[A-Za-z0-9-]+\.local"
    r")\b)",
    re.IGNORECASE,
)
_LOCAL_HOST_RE = re.compile(
    r"(?P<value>(?<![@\w.-])(?:"
    r"[A-Za-z0-9-]*(?:host|machine|desktop|laptop|macbook)[A-Za-z0-9-]*"
    r"|[A-Za-z][A-Za-z0-9-]*[0-9][A-Za-z0-9-]*"
    r"|[A-Za-z0-9]+-[A-Za-z0-9-]+"
    r")\.local\b)",
    re.IGNORECASE,
)
_LABELED_HOST_RE = re.compile(
    r"\b(?:host(?:name)?|machine)\s*(?:=|:)\s*"
    r"(?P<value>[A-Za-z0-9][A-Za-z0-9.-]*\.local)\b",
    re.IGNORECASE,
)


class DeliveryHygieneConfigurationError(RuntimeError):
    """The requested repository comparison or allow-list is invalid."""


@dataclass(frozen=True, order=True)
class Finding:
    """One rejected value, tied to an exact source and line."""

    path: str
    source: str
    line: int
    kind: str
    value: str


@dataclass(frozen=True)
class Allowlist:
    """Exact exceptions reviewed with a durable reason."""

    text: frozenset[tuple[str, str]] = frozenset()
    commits: frozenset[tuple[str, str]] = frozenset()

    def allows_text(self, path: str, value: str) -> bool:
        return (path, value) in self.text

    def allows_commit(self, commit: str, rule: str) -> bool:
        return (commit, rule) in self.commits


def _git(
    repository: Path,
    *arguments: str,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        input=input_bytes,
    )


def _git_output(repository: Path, *arguments: str) -> bytes:
    process = _git(repository, *arguments)
    if process.returncode != 0:
        detail = (process.stderr or process.stdout).decode("utf-8", "replace").strip()
        raise DeliveryHygieneConfigurationError(
            f"Git {' '.join(arguments)!r} failed: {detail or 'no diagnostic'}"
        )
    return process.stdout


def _resolve_commit(repository: Path, reference: str, *, label: str) -> str:
    candidate = reference.strip()
    if not candidate or set(candidate) == {"0"}:
        raise DeliveryHygieneConfigurationError(
            f"{label} is empty or all-zero; provide a real comparison commit."
        )
    process = _git(
        repository,
        "rev-parse",
        "--verify",
        "--quiet",
        "--end-of-options",
        f"{candidate}^{{commit}}",
    )
    resolved = process.stdout.decode("ascii", "replace").strip()
    if process.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise DeliveryHygieneConfigurationError(
            f"Could not resolve {label} {candidate!r} to a commit. Fetch the "
            "comparison history or provide an available commit/ref."
        )
    return resolved


def _merge_base(repository: Path, base: str, head: str) -> str:
    process = _git(repository, "merge-base", base, head)
    resolved = process.stdout.decode("ascii", "replace").strip()
    if process.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise DeliveryHygieneConfigurationError(
            "Could not compute the comparison merge base. Fetch full history and "
            "ensure the comparison base and HEAD share ancestry."
        )
    return resolved


def _validate_repo_path(raw_path: str, *, label: str) -> str:
    normalized = raw_path.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if (
        not normalized
        or pure.is_absolute()
        or ".." in pure.parts
        or normalized.startswith("./")
    ):
        raise DeliveryHygieneConfigurationError(
            f"{label} must be a normalized repository-relative path: {raw_path!r}"
        )
    return pure.as_posix()


def load_allowlist(path: Path | None) -> Allowlist:
    """Load exact, reason-bearing exceptions from ``path`` when it exists."""

    if path is None or not path.exists():
        return Allowlist()
    if not path.is_file():
        raise DeliveryHygieneConfigurationError(
            f"Delivery hygiene allow-list is not a file: {path}"
        )
    text_entries: set[tuple[str, str]] = set()
    commit_entries: set[tuple[str, str]] = set()
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line or raw_line.lstrip().startswith("#"):
            continue
        fields = raw_line.split("\t")
        if len(fields) != 4:
            raise DeliveryHygieneConfigurationError(
                f"{path}:{line_number}: expected four tab-separated fields"
            )
        entry_kind, target, rule_or_value, reason = fields
        if len(reason.strip()) < 12:
            raise DeliveryHygieneConfigurationError(
                f"{path}:{line_number}: exception reason is too short"
            )
        if entry_kind == "text":
            normalized = _validate_repo_path(target, label=f"{path}:{line_number}")
            if not rule_or_value:
                raise DeliveryHygieneConfigurationError(
                    f"{path}:{line_number}: exact text value is empty"
                )
            key = (normalized, rule_or_value)
            if key in text_entries:
                raise DeliveryHygieneConfigurationError(
                    f"{path}:{line_number}: duplicate text exception {key!r}"
                )
            text_entries.add(key)
        elif entry_kind == "commit":
            commit = target.casefold()
            if not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise DeliveryHygieneConfigurationError(
                    f"{path}:{line_number}: commit exception requires a full SHA"
                )
            if rule_or_value not in COMMIT_RULES:
                raise DeliveryHygieneConfigurationError(
                    f"{path}:{line_number}: unknown commit rule {rule_or_value!r}"
                )
            key = (commit, rule_or_value)
            if key in commit_entries:
                raise DeliveryHygieneConfigurationError(
                    f"{path}:{line_number}: duplicate commit exception {key!r}"
                )
            commit_entries.add(key)
        else:
            raise DeliveryHygieneConfigurationError(
                f"{path}:{line_number}: entry kind must be 'text' or 'commit'"
            )
    return Allowlist(frozenset(text_entries), frozenset(commit_entries))


def _nul_paths(output: bytes) -> set[str]:
    paths: set[str] = set()
    for item in output.split(b"\0"):
        if not item:
            continue
        decoded = item.decode("utf-8", "surrogateescape")
        paths.add(PurePosixPath(decoded).as_posix())
    return paths


def _tracked_paths(repository: Path) -> set[str]:
    return _nul_paths(_git_output(repository, "ls-files", "-z"))


def _changed_paths(repository: Path, merge_base: str, head: str) -> set[str]:
    paths = _nul_paths(
        _git_output(
            repository,
            "diff",
            "--name-only",
            "--diff-filter=ACMRTUXB",
            "-z",
            merge_base,
            head,
            "--",
        )
    )
    paths.update(
        _nul_paths(
            _git_output(
                repository,
                "diff",
                "--cached",
                "--name-only",
                "--diff-filter=ACMRTUXB",
                "-z",
                "--",
            )
        )
    )
    paths.update(
        _nul_paths(
            _git_output(
                repository,
                "diff",
                "--name-only",
                "--diff-filter=ACMRTUXB",
                "-z",
                "--",
            )
        )
    )
    return paths & _tracked_paths(repository)


def _blob(repository: Path, object_name: str) -> bytes | None:
    process = _git(repository, "show", object_name)
    if process.returncode == 0:
        return process.stdout
    return None


def _worktree_bytes(repository: Path, relative: str) -> bytes | None:
    path = repository / relative
    try:
        if path.is_symlink():
            return os.readlink(path).encode("utf-8", "surrogateescape")
        if path.is_file():
            return path.read_bytes()
    except OSError as error:
        raise DeliveryHygieneConfigurationError(
            f"Could not read tracked worktree path {relative!r}: {error}"
        ) from error
    return None


def _text_versions(
    repository: Path,
    relative: str,
    *,
    head: str,
) -> tuple[tuple[str, str], ...]:
    candidates = (
        ("HEAD", _blob(repository, f"{head}:{relative}")),
        ("index", _blob(repository, f":{relative}")),
        ("worktree", _worktree_bytes(repository, relative)),
    )
    versions: list[tuple[str, str]] = []
    observed: set[bytes] = set()
    for source, payload in candidates:
        if payload is None or payload in observed:
            continue
        observed.add(payload)
        if b"\0" in payload:
            continue
        versions.append((source, payload.decode("utf-8", "replace")))
    return tuple(versions)


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def scan_text(
    text: str,
    *,
    path: str,
    source: str,
    allowlist: Allowlist,
) -> tuple[Finding, ...]:
    """Return actual workstation-value findings from one text payload."""

    findings: set[Finding] = set()
    for match in _HOST_PATH_RE.finditer(text):
        placeholder = match.groupdict().get("placeholder")
        if placeholder is not None and placeholder.casefold() in PLACEHOLDER_USERNAMES:
            continue
        value = match.group("value")
        if not allowlist.allows_text(path, value):
            findings.add(
                Finding(
                    path,
                    source,
                    _line_number(text, match.start("value")),
                    "host path",
                    value,
                )
            )
    detectors = (
        (".local email", _LOCAL_EMAIL_RE),
        ("workstation hostname", _LOCAL_HOST_RE),
        ("workstation hostname", _OBVIOUS_HOST_RE),
        ("workstation hostname", _LABELED_HOST_RE),
    )
    for kind, detector in detectors:
        for match in detector.finditer(text):
            if detector is _OBVIOUS_HOST_RE and text[
                match.end() :
            ].casefold().startswith(".local"):
                continue
            value = match.group("value")
            if allowlist.allows_text(path, value):
                continue
            findings.add(
                Finding(
                    path,
                    source,
                    _line_number(text, match.start("value")),
                    kind,
                    value,
                )
            )
    return tuple(sorted(findings))


def _introduced_commits(
    repository: Path, merge_base: str, head: str
) -> tuple[str, ...]:
    output = _git_output(
        repository,
        "rev-list",
        "--reverse",
        f"{merge_base}..{head}",
    ).decode("ascii", "replace")
    commits = tuple(line.strip() for line in output.splitlines() if line.strip())
    if not all(re.fullmatch(r"[0-9a-f]{40}", commit) for commit in commits):
        raise DeliveryHygieneConfigurationError(
            "Git returned an invalid commit identity"
        )
    return commits


def _commit_record(repository: Path, commit: str) -> tuple[str, str, str, str, str]:
    output = _git_output(
        repository,
        "show",
        "--no-patch",
        "--format=%an%x00%ae%x00%cn%x00%ce%x00%B",
        commit,
    ).decode("utf-8", "replace")
    fields = output.split("\0", 4)
    if len(fields) != 5:
        raise DeliveryHygieneConfigurationError(
            f"Could not parse author/committer metadata for {commit}"
        )
    return tuple(fields)  # type: ignore[return-value]


def _commit_paths(repository: Path, commit: str) -> tuple[str, ...]:
    parent_line = (
        _git_output(repository, "rev-list", "--parents", "-n", "1", commit)
        .decode("ascii", "replace")
        .strip()
    )
    parts = parent_line.split()
    arguments = (
        ("diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "-z", commit)
        if len(parts) == 1
        else (
            "diff",
            "--name-only",
            "--diff-filter=ACDMRTUXB",
            "-z",
            parts[1],
            commit,
            "--",
        )
    )
    return tuple(sorted(_nul_paths(_git_output(repository, *arguments))))


def _commit_tree_is_empty(repository: Path, commit: str) -> bool:
    line = (
        _git_output(repository, "rev-list", "--parents", "-n", "1", commit)
        .decode("ascii", "replace")
        .strip()
    )
    parts = line.split()
    if len(parts) == 1:
        return not _commit_paths(repository, commit)
    commit_tree = _git_output(repository, "rev-parse", f"{commit}^{{tree}}").strip()
    first_parent_tree = _git_output(
        repository, "rev-parse", f"{parts[1]}^{{tree}}"
    ).strip()
    return commit_tree == first_parent_tree


def _commit_findings(
    repository: Path,
    commit: str,
    allowlist: Allowlist,
) -> tuple[Finding, ...]:
    author_name, author_email, committer_name, committer_email, message = (
        _commit_record(repository, commit)
    )
    findings: set[Finding] = set()
    for label, value in (
        ("author", f"{author_name} <{author_email}>"),
        ("committer", f"{committer_name} <{committer_email}>"),
    ):
        findings.update(
            scan_text(
                value,
                path=f"commit:{commit}",
                source=label,
                allowlist=allowlist,
            )
        )
    subject = next((line.strip() for line in message.splitlines() if line.strip()), "")
    intent_match = _FORBIDDEN_COMMIT_SUBJECT_RE.fullmatch(subject)
    if intent_match and not allowlist.allows_commit(commit, "message"):
        findings.add(
            Finding(
                f"commit:{commit}",
                "message",
                1,
                "forbidden completion-only commit intent",
                intent_match.group("intent").casefold(),
            )
        )
    if _commit_tree_is_empty(repository, commit) and not allowlist.allows_commit(
        commit, "empty"
    ):
        findings.add(
            Finding(
                f"commit:{commit}",
                "tree",
                1,
                "empty introduced commit",
                commit,
            )
        )
    paths = _commit_paths(repository, commit)
    if (
        paths
        and all(path.startswith(".agent/evidence/") for path in paths)
        and not allowlist.allows_commit(commit, "evidence-only")
    ):
        findings.add(
            Finding(
                f"commit:{commit}",
                "tree",
                1,
                "evidence-only introduced commit",
                ", ".join(paths),
            )
        )
    return tuple(sorted(findings))


def check_delivery_hygiene(
    repository: Path,
    base_reference: str,
    *,
    all_tree: bool = False,
    allowlist_path: Path | None = None,
) -> tuple[Finding, ...]:
    """Inspect changed/all tracked text and introduced commit metadata."""

    repository = repository.resolve()
    base = _resolve_commit(repository, base_reference, label="comparison base")
    head = _resolve_commit(repository, "HEAD", label="HEAD")
    merge_base = _merge_base(repository, base, head)
    selected_allowlist = allowlist_path
    if selected_allowlist is None:
        candidate = repository / DEFAULT_ALLOWLIST
        selected_allowlist = candidate if candidate.exists() else None
    allowlist = load_allowlist(selected_allowlist)

    paths = (
        _tracked_paths(repository)
        if all_tree
        else _changed_paths(repository, merge_base, head)
    )
    if selected_allowlist is not None:
        try:
            allowlist_relative = selected_allowlist.resolve().relative_to(repository)
        except ValueError:
            allowlist_relative = None
        if allowlist_relative is not None:
            paths.discard(allowlist_relative.as_posix())

    findings: set[Finding] = set()
    for relative in sorted(paths):
        for source, text in _text_versions(repository, relative, head=head):
            findings.update(
                scan_text(
                    text,
                    path=relative,
                    source=source,
                    allowlist=allowlist,
                )
            )
    for commit in _introduced_commits(repository, merge_base, head):
        findings.update(_commit_findings(repository, commit, allowlist))

    print("Delivery hygiene comparison:")
    print(f"  requested base: {base_reference}")
    print(f"  resolved base:  {base}")
    print(f"  merge base:     {merge_base}")
    print(f"  HEAD:           {head}")
    print(
        f"  text scope:     {'complete tracked tree' if all_tree else 'changed tracked text'}"
    )
    print(f"  tracked paths:  {len(paths)}")
    print(f"  commits:        {len(_introduced_commits(repository, merge_base, head))}")
    return tuple(sorted(findings))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path.cwd(),
        help="Git repository to inspect (default: current directory).",
    )
    parser.add_argument(
        "--base",
        required=True,
        help="Commit/ref defining the introduced commit and text comparison.",
    )
    parser.add_argument(
        "--all-tree",
        action="store_true",
        help="Scan the complete tracked textual tree instead of changed paths only.",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        help="Exact reason-bearing allow-list (default: repository policy file).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        findings = check_delivery_hygiene(
            args.repository,
            args.base,
            all_tree=args.all_tree,
            allowlist_path=args.allowlist,
        )
    except (DeliveryHygieneConfigurationError, OSError, UnicodeError) as error:
        print(f"Delivery hygiene configuration error: {error}", file=sys.stderr)
        return 2
    if findings:
        print(
            "Delivery hygiene rejected workstation or delivery artifacts:",
            file=sys.stderr,
        )
        for finding in findings:
            print(
                f"  {finding.path}:{finding.line} [{finding.source}] "
                f"{finding.kind}: {finding.value!r}",
                file=sys.stderr,
            )
        return 1
    print("Carbon delivery hygiene passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
