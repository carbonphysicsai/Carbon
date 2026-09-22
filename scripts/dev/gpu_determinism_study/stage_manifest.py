"""Pin the Carbon revision across a boundary `git` cannot cross.

The pinned worker image has no `git`, no `curl`, no `wget` and no CA bundle, so
the runner's original `git rev-parse` check cannot run inside it and the
repository cannot be fetched from it either. The checkout therefore arrives on a
mounted volume, staged by a separate pod that does have `git` and never runs any
part of the study.

That splits the revision check in two, and this module is both halves:

``write``   on the staging pod, record the revision and a digest of the tree
``verify``  in the pinned image, recompute the digest and compare

The digest is the point. A recorded revision string is a claim by whoever staged
it; recomputing a content digest checks the bytes that are actually present. So
this is a stronger pin than the `git rev-parse` and `git diff --quiet` it
replaces - those asked git's opinion of the working tree, while this reads the
tree.

Deliberately dependency-free: it runs under the worker image's isolated
interpreter, which has the standard library and nothing else.

    python stage_manifest.py write  <repo> <revision>
    python stage_manifest.py verify <repo> <revision>
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

MANIFEST = "carbon-revision.json"
SCHEMA = "carbon.study.staged-revision.v1"

# Directories that are not the checkout's content. `.git` is excluded because it
# is staging machinery rather than the tree under test, and because its contents
# differ between a full clone and a shallow one while the source does not.
SKIP = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"}


def tree_digest(repo: Path) -> str:
    """A digest of every tracked file's path and contents, order-independent.

    Paths are sorted and hashed with their contents, so a renamed file, an edited
    file and a deleted file all move the digest. Symlinks are recorded as their
    target text rather than followed, so a link that points somewhere new is a
    change even when the destination is unchanged.
    """
    entries = []
    for path in sorted(repo.rglob("*")):
        if any(part in SKIP for part in path.relative_to(repo).parts):
            continue
        relative = str(path.relative_to(repo))
        if path.is_symlink():
            entries.append((relative, "L" + os.readlink(path)))
        elif path.is_file():
            entries.append(
                (relative, "F" + hashlib.sha256(path.read_bytes()).hexdigest())
            )
    digest = hashlib.sha256()
    for relative, mark in entries:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(mark.encode("utf-8"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def write(repo: Path, revision: str) -> dict:
    document = {
        "schema": SCHEMA,
        "revision": revision,
        "tree_digest": tree_digest(repo),
    }
    (repo.parent / MANIFEST).write_text(json.dumps(document, indent=1, sort_keys=True))
    return document


def verify(repo: Path, revision: str) -> list[str]:
    """Problems with the staged checkout. Empty means it is the named revision."""
    path = repo.parent / MANIFEST
    if not path.is_file():
        return [f"no staged revision manifest at {path}"]
    try:
        document = json.loads(path.read_text())
    except ValueError:
        return [f"staged revision manifest at {path} is not readable JSON"]
    problems = []
    if document.get("schema") != SCHEMA:
        problems.append(
            f"manifest schema is {document.get('schema')!r}, expected {SCHEMA!r}"
        )
    if document.get("revision") != revision:
        problems.append(
            f"staged revision is {document.get('revision')!r}, expected {revision!r}"
        )
    found = tree_digest(repo)
    if document.get("tree_digest") != found:
        # The tree does not match what was staged. Either it was modified after
        # staging or the manifest describes a different checkout; both mean the
        # revision no longer describes what is about to run.
        problems.append(
            f"tree digest is {found}, manifest records {document.get('tree_digest')}"
        )
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in ("write", "verify"):
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    action, repo, revision = argv[1], Path(argv[2]).resolve(), argv[3]
    if action == "write":
        print(json.dumps(write(repo, revision), indent=1, sort_keys=True))
        return 0
    problems = verify(repo, revision)
    for problem in problems:
        print(f"staged checkout: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
