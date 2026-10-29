"""The worker image's real build inputs, and the one digest every image identity is scoped to.

``source_tree_digest`` in a ``carbon.c03.worker-image-build.v2`` record is NOT the digest of the whole repository: it is
the digest of the git tree listing (modes and blob ids) of the build inputs, the paths the worker Dockerfiles actually COPY (plus the
Dockerfile itself and the derived images' input directories). A change anywhere else (``scripts/``, ``docs/``,
``tests/``, ``codex-queue/`` ...) no longer moves any image id. The checkout must still be clean as a whole, and the
exact commit is recorded beside the digest, so provenance is unchanged. Records of ``...build.v1`` kept the old
meaning (the whole tree) and are never reinterpreted: the schema is the difference.

The set lives in ONE data file, ``build_inputs.txt`` beside this module (itself inside ``carbon/``, so a change to the
set moves the digest). Python reads it here; shell scripts run this file as a program::

    python carbon/reconstruction/worker/build_inputs.py digest [REPO]   # sha256:<hex>
    python carbon/reconstruction/worker/build_inputs.py paths           # one repo-relative path per line

Standard library only, so any script can run it before the package is importable.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

#: The record schema whose ``source_tree_digest`` means "the worker build inputs" (v1 meant the whole tree).
BUILD_SCHEMA = "carbon.c03.worker-image-build.v2"
INPUTS_FILE = Path(__file__).with_name("build_inputs.txt")
#: The checkout path of the set file (relative to a repository root).
INPUTS_FILE_IN_REPO = "carbon/reconstruction/worker/build_inputs.txt"


def paths(inputs_file=None) -> tuple:
    """The repo-relative build inputs, in file order (comments and blank lines skipped)."""
    lines = Path(INPUTS_FILE if inputs_file is None else inputs_file).read_text(
        encoding="utf-8"
    )
    found = tuple(
        line.strip()
        for line in lines.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not found or len(set(found)) != len(found):
        raise ValueError("the worker build inputs file is empty or repeats a path")
    for path in found:
        if path.startswith(("/", "..")) or ".." in Path(path).parts:
            raise ValueError("a build input must be a path inside the repository")
    return found


def listing(repo, *, revision="HEAD") -> bytes:
    """The git tree listing of the build inputs at ``revision``: mode, type, blob id and path of every file.

    This, not ``git archive``: a tar made from a commit embeds the commit id and its timestamp, so it would change
    with every commit. The blob ids are the files' contents, so the listing changes only when a build input does.
    The set is read from the same commit."""
    repo = Path(repo)
    listed = subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{revision}:{INPUTS_FILE_IN_REPO}"],
        timeout=30,
    ).decode("utf-8")
    inputs = tuple(
        line.strip()
        for line in listed.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not inputs:
        raise ValueError("the worker build inputs file is empty")
    found = subprocess.check_output(
        [
            "git",
            "-C",
            str(repo),
            "ls-tree",
            "-r",
            "--full-tree",
            revision,
            "--",
            *inputs,
        ],
        timeout=60,
    )
    if not found:
        raise ValueError("none of the worker build inputs exists at this revision")
    return found


def digest(repo, *, revision="HEAD") -> str:
    """``sha256:<hex>`` of the build-input tree listing at ``revision`` of ``repo``."""
    return "sha256:" + hashlib.sha256(listing(repo, revision=revision)).hexdigest()


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["digest"] and len(args) in (1, 2):
        repo = args[1] if len(args) == 2 else Path(__file__).resolve().parents[3]
        print(digest(repo))
        return 0
    if args == ["paths"]:
        print("\n".join(paths()))
        return 0
    print("usage: build_inputs.py digest [REPO] | paths", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
