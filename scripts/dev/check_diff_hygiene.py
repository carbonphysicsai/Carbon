"""Fail closed on committed, staged, or unstaged Git whitespace defects."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


class DiffHygieneConfigurationError(RuntimeError):
    """The requested Git comparison cannot be established."""


def _git(repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )


def _resolve_commit(repository: Path, reference: str, *, label: str) -> str:
    stripped = reference.strip()
    if not stripped or set(stripped) == {"0"}:
        raise DiffHygieneConfigurationError(
            f"{label} is empty or all-zero; provide a real comparison commit."
        )
    process = _git(
        repository,
        "rev-parse",
        "--verify",
        "--quiet",
        "--end-of-options",
        f"{stripped}^{{commit}}",
    )
    commit = process.stdout.strip()
    if process.returncode != 0 or not commit:
        raise DiffHygieneConfigurationError(
            f"Could not resolve {label} '{stripped}' to a commit. "
            "Fetch the comparison history or set QUALITY_BASE_SHA to an "
            "available commit/ref."
        )
    return commit


def _merge_base(repository: Path, base: str, head: str, *, label: str) -> str:
    process = _git(repository, "merge-base", base, head)
    merge_base = process.stdout.strip()
    if process.returncode != 0 or not merge_base:
        raise DiffHygieneConfigurationError(
            "Could not compute a merge base between "
            f"QUALITY_BASE_SHA '{label}' ({base}) and HEAD ({head}). "
            "Fetch full comparison history and ensure the refs share ancestry."
        )
    return merge_base


def _report_failure(
    description: str,
    process: subprocess.CompletedProcess[str],
) -> None:
    print(f"Git diff hygiene failed for {description}:", file=sys.stderr)
    if process.stdout:
        print(process.stdout, end="", file=sys.stderr)
    if process.stderr:
        print(process.stderr, end="", file=sys.stderr)


def check_diff_hygiene(repository: Path, base_reference: str) -> int:
    """Check the committed base-to-HEAD range plus staged/local changes."""

    base = _resolve_commit(
        repository,
        base_reference,
        label="comparison base",
    )
    head = _resolve_commit(repository, "HEAD", label="HEAD")
    merge_base = _merge_base(repository, base, head, label=base_reference)

    print("Git diff hygiene comparison:")
    print(f"  requested base: {base_reference}")
    print(f"  resolved base:  {base}")
    print(f"  merge base:     {merge_base}")
    print(f"  HEAD:           {head}")

    checks = (
        (
            "the committed merge-base-to-HEAD range",
            ("diff", "--no-renames", "--check", merge_base, head, "--"),
        ),
        (
            "staged changes",
            ("diff", "--cached", "--no-renames", "--check", "--"),
        ),
        ("unstaged changes", ("diff", "--no-renames", "--check", "--")),
    )
    failed = False
    for description, arguments in checks:
        process = _git(repository, *arguments)
        if process.returncode in {1, 2}:
            failed = True
            _report_failure(description, process)
        elif process.returncode != 0:
            details = process.stderr.strip() or process.stdout.strip() or "no output"
            raise DiffHygieneConfigurationError(
                f"Git could not inspect {description}: {details}"
            )
    return 1 if failed else 0


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
        help="Commit/ref defining the committed comparison base.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        return check_diff_hygiene(args.repository.resolve(), args.base)
    except DiffHygieneConfigurationError as error:
        print(f"Git diff hygiene configuration error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
