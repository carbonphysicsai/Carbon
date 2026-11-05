#!/usr/bin/env python3
"""Whether a release changes a door's exam, BEFORE the switch (MAINNET_UPDATE_ARCHITECTURE s1.3 (b), head H2).

    python3 -I -B scripts/dev/release/exam_identity.py digest --repo REPO --rev REV
    python3 -I -B scripts/dev/release/exam_identity.py check  --repo REPO --old OLD --new NEW \\
        [--old-pack DIGEST --new-pack DIGEST] [--declared-exam-change TEXT]

The exam a door grades with is its evaluation pack plus its grading code. The grading code is every M2 grading path
(`direct_receiver.GRADING_PATHS` and its module patterns: the ONE list, read from this checkout) plus the worker build
inputs. ``digest`` prints the grading-path digest of a revision: sha256 of the git tree listing (mode, blob id, path)
of every grading file at that revision, then the build-inputs listing. Blob ids are file contents, so the digest moves
only when a grading file does, never with the commit id.

``check`` answers one question for Deploy, from git alone (no host state is read):

- ``SAME_EXAM`` (exit 0): OLD..NEW changes no grading path, the build inputs are identical and the pack is equal.
  The switch cannot change any evaluation; a king's grade stays comparable.
- ``EXAM_CHANGE`` (exit 2, REFUSED): something above differs and nobody said so. The listed paths say what.
- ``EXAM_CHANGE_DECLARED`` (exit 0): the same, with ``--declared-exam-change`` naming the reason (a new exam version,
  or a reviewer's ruling that a listed change grades nothing on this door). The receipt for the switch names it.
- ``UNKNOWN`` (exit 3, REFUSED): git could not tell (a revision missing, a listing failed).

A deploy therefore never changes the exam silently. What happens to kings after a declared change is the receiver's
(the regrade on the new exam), not this tool's.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

SAME, CHANGE, DECLARED, UNKNOWN = (
    "SAME_EXAM",
    "EXAM_CHANGE",
    "EXAM_CHANGE_DECLARED",
    "UNKNOWN",
)
EXIT = {SAME: 0, DECLARED: 0, CHANGE: 2, UNKNOWN: 3}
SCHEMA = "carbon.release.exam-identity.v1"


def _checkout_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _receiver():
    root = str(_checkout_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from carbon.challenge_validator import direct_receiver

    return direct_receiver


def _build_inputs():
    root = str(_checkout_root())
    if root not in sys.path:
        sys.path.insert(0, root)
    from carbon.reconstruction.worker import build_inputs

    return build_inputs


def grading_listing(repo, revision) -> bytes:
    """The git tree listing of every grading path at ``revision``, sorted by path (the bytes the digest covers)."""
    receiver = _receiver()
    found = subprocess.check_output(
        ["git", "-C", str(repo), "ls-tree", "-r", "-z", "--full-tree", revision],
        timeout=60,
    )
    kept = [
        entry
        for entry in found.split(b"\0")
        if entry and receiver.grading_path(entry.split(b"\t", 1)[1].decode("utf-8"))
    ]
    if not kept:
        raise ValueError("no grading path at this revision")
    return b"\n".join(sorted(kept, key=lambda e: e.split(b"\t", 1)[1])) + b"\n"


def grading_digest(repo, revision) -> str:
    """sha256 over the grading listing, then the build-inputs listing, each length-prefixed."""
    h = hashlib.sha256()
    for part in (
        grading_listing(repo, revision),
        _build_inputs().listing(repo, revision=revision),
    ):
        h.update(len(part).to_bytes(8, "big"))
        h.update(part)
    return "sha256:" + h.hexdigest()


def check(repo, old, new, *, old_pack=None, new_pack=None, declared=None) -> dict:
    out = {"schema": SCHEMA, "old": old, "new": new}
    if (old_pack is None) != (new_pack is None):
        raise ValueError("give both --old-pack and --new-pack, or neither")
    try:
        changed = _receiver()._grading_change(old, new, repo)
        digests = (grading_digest(repo, old), grading_digest(repo, new))
    except (OSError, ValueError, subprocess.SubprocessError):
        changed, digests = None, None
    if changed is None or digests is None:
        return {**out, "state": UNKNOWN}
    receiver = _receiver()
    pack_changed = old_pack is not None and old_pack != new_pack
    out.update(
        old_grading_digest=digests[0],
        new_grading_digest=digests[1],
        build_inputs_moved=receiver.BUILD_INPUTS_CHANGED in changed,
        grading_paths_changed=[
            p for p in changed if p != receiver.BUILD_INPUTS_CHANGED
        ],
        pack_compared=old_pack is not None,
        pack_changed=pack_changed,
    )
    if not changed and not pack_changed:
        # Equal listings with no changed path: the digests must agree too, or the predicate and the diff disagree.
        return {**out, "state": SAME if digests[0] == digests[1] else UNKNOWN}
    if declared:
        return {**out, "state": DECLARED, "declared": declared}
    return {**out, "state": CHANGE}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="exam_identity.py")
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("digest")
    d.add_argument("--repo", type=Path, required=True)
    d.add_argument("--rev", required=True)
    c = sub.add_parser("check")
    c.add_argument("--repo", type=Path, required=True)
    c.add_argument("--old", required=True)
    c.add_argument("--new", required=True)
    c.add_argument("--old-pack")
    c.add_argument("--new-pack")
    c.add_argument("--declared-exam-change")
    args = parser.parse_args(argv)
    if args.command == "digest":
        try:
            print(
                json.dumps(
                    {
                        "schema": SCHEMA,
                        "rev": args.rev,
                        "grading_digest": grading_digest(args.repo, args.rev),
                    }
                )
            )
        except (OSError, ValueError, subprocess.SubprocessError) as failed:
            print(
                json.dumps(
                    {
                        "schema": SCHEMA,
                        "rev": args.rev,
                        "state": UNKNOWN,
                        "error": type(failed).__name__,
                    }
                )
            )
            return EXIT[UNKNOWN]
        return 0
    if args.declared_exam_change is not None and not args.declared_exam_change.strip():
        parser.error("--declared-exam-change needs a reason")
    result = check(
        args.repo,
        args.old,
        args.new,
        old_pack=args.old_pack,
        new_pack=args.new_pack,
        declared=args.declared_exam_change,
    )
    print(json.dumps(result, sort_keys=True))
    return EXIT[result["state"]]


if __name__ == "__main__":
    sys.exit(main())
