#!/usr/bin/env python3
"""Whether a release changes a door's exam, BEFORE the switch (MAINNET_UPDATE_ARCHITECTURE s1.3 (b), head H2).

    python3 -I -B scripts/dev/release/exam_identity.py digest --repo REPO --rev REV
    python3 -I -B scripts/dev/release/exam_identity.py check  --repo REPO --old OLD --new NEW \\
        --old-pack DIGEST --new-pack DIGEST [--declared-exam-change TEXT]

The exam a door grades with is its evaluation pack plus its grading code. The grading code is every M2 grading path
plus the worker build inputs. The M2 rule (``GRADING_PATHS`` and ``_GRADING_MODULE`` in
``carbon/challenge_validator/direct_receiver.py``) is read FROM EACH REVISION ITSELF (by ``ast``, never imported), so
a release that edits the rule is seen. ``digest`` prints a revision's grading-path digest: sha256 of the git tree
listing (mode, blob id, path) of every file its own rule names, then its build-inputs listing. Blob ids are file
contents, so the digest moves only when a grading file does, never with the commit id.

``check`` answers one question for Deploy, from git alone (no host state is read). Revisions are resolved to commit
ids first; the output carries the full ids.

- ``SAME_EXAM`` (exit 0): the M2 rule is identical at OLD and NEW (a revision older than the rule is judged by the
  other side's, listed in ``grading_rule_absent_at``), OLD..NEW changes no file either rule names, the
  build inputs are identical and the two pack digests are equal. The switch cannot change any evaluation.
- ``EXAM_CHANGE`` (exit 3, REFUSED): something above differs and nobody said so; the fields say what.
- ``EXAM_CHANGE_DECLARED`` (exit 0): the same, with ``--declared-exam-change`` naming the reason (a new exam version,
  or a reviewer's ruling that a listed change grades nothing on this door). The switch's receipt names it.
- ``UNKNOWN`` (exit 4, REFUSED): git could not tell (a revision missing, a rule unreadable, a symlink under a
  grading path, any failure). Never an exit of 0 on doubt. (Exit 2 is argparse's usage error: also a refusal.)

A deploy therefore never changes the exam silently. What happens to kings after a declared change is the receiver's
(the regrade on the new exam), not this tool's.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SAME, CHANGE, DECLARED, UNKNOWN = (
    "SAME_EXAM",
    "EXAM_CHANGE",
    "EXAM_CHANGE_DECLARED",
    "UNKNOWN",
)
EXIT = {SAME: 0, DECLARED: 0, CHANGE: 3, UNKNOWN: 4}
SCHEMA = "carbon.release.exam-identity.v2"
RULE_FILE = "carbon/challenge_validator/direct_receiver.py"
BUILD_INPUTS_FILE = "carbon/reconstruction/worker/build_inputs.txt"
_HEX = re.compile(r"(?:sha256:)?([0-9a-f]{64})")


class Unknown(Exception):
    """Git could not tell; the answer is UNKNOWN."""


def _git(repo, *args, timeout=60) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            timeout=timeout,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as failed:
        raise Unknown(f"git {args[0]} failed") from failed


def resolve(repo, rev) -> str:
    """The full commit id of ``rev`` (a name starting with ``-`` is never an option)."""
    out = _git(repo, "rev-parse", "--verify", "--end-of-options", f"{rev}^{{commit}}")
    full = out.decode("ascii", "replace").strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", full):
        raise Unknown("revision_unresolved")
    return full


def rule(repo, commit):
    """``(GRADING_PATHS, _GRADING_MODULE pattern)`` as written at ``commit``, read by ``ast``; None when that
    revision predates the rule (neither name is assigned: revisions before M2, e.g. 517b5b6b).
    """
    return parse_rule(_git(repo, "show", f"{commit}:{RULE_FILE}"))


def parse_rule(source: bytes):
    """`rule` on the bytes of one ``direct_receiver.py``."""
    try:
        tree = ast.parse(source.decode("utf-8"))
    except (SyntaxError, ValueError) as failed:
        raise Unknown("grading_rule_unreadable") from failed
    paths = pattern = None
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        name = getattr(node.targets[0], "id", None)
        if name == "GRADING_PATHS":
            paths = ast.literal_eval(node.value)
        elif name == "_GRADING_MODULE":
            call = node.value
            if (
                not isinstance(call, ast.Call)
                or len(call.args) != 1
                or not isinstance(call.args[0], ast.Constant)
                or type(call.args[0].value) is not str
            ):
                raise Unknown("grading_rule_unreadable")
            pattern = call.args[0].value
    if paths is None and pattern is None:
        return None
    if (
        type(paths) is not tuple
        or not paths
        or any(type(p) is not str or not p for p in paths)
        or pattern is None
    ):
        raise Unknown("grading_rule_unreadable")
    return paths, pattern


def excluded(repo, commit):
    """``GRADING_EXCLUDED`` as written at ``commit`` (read by ``ast``), or None when it is not assigned."""
    try:
        tree = ast.parse(_git(repo, "show", f"{commit}:{RULE_FILE}").decode("utf-8"))
    except (SyntaxError, ValueError) as failed:
        raise Unknown("grading_rule_unreadable") from failed
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and getattr(node.targets[0], "id", None) == "GRADING_EXCLUDED"
        ):
            try:
                return ast.literal_eval(node.value)
            except ValueError as failed:
                raise Unknown("grading_rule_unreadable") from failed
    return None


def _predicate(*rules):
    """True for a path ANY of ``rules`` names (prefixes end in ``/``; the rest exact; the module pattern full-match)."""
    compiled = [(paths, re.compile(pattern)) for paths, pattern in rules]

    def named(path):
        return any(
            module.fullmatch(path) is not None
            or any(path.startswith(p) if p.endswith("/") else path == p for p in paths)
            for paths, module in compiled
        )

    return named


def _entries(repo, commit):
    """``[(path, entry bytes)]`` of every file at ``commit`` (ls-tree -r -z)."""
    found = []
    for entry in _git(repo, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.partition(b"\t")
        try:
            found.append((path.decode("utf-8"), meta, entry))
        except UnicodeDecodeError as failed:
            raise Unknown("path_not_utf8") from failed
    return found


def grading_listing(repo, commit, named) -> bytes:
    kept = []
    for path, meta, entry in _entries(repo, commit):
        if named(path):
            if meta.startswith(b"120000"):
                # A link's blob is its target's NAME: a change to the target would go unseen.
                raise Unknown("symlink_under_grading_path")
            kept.append((path, entry))
    if not kept:
        raise Unknown("no_grading_path")
    return b"\n".join(entry for _, entry in sorted(kept)) + b"\n"


def build_listing(repo, commit) -> bytes:
    """The tree listing of the worker build inputs, the set read from ``commit`` itself."""
    listed = _git(repo, "show", f"{commit}:{BUILD_INPUTS_FILE}").decode(
        "utf-8", "replace"
    )
    inputs = [
        line.strip()
        for line in listed.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not inputs:
        raise Unknown("build_inputs_empty")
    return _git(repo, "ls-tree", "-r", "--full-tree", commit, "--", *inputs)


def grading_digest(repo, commit, named=None) -> str:
    """sha256 over the grading listing (by ``named``, default the revision's own rule), then the build-inputs
    listing, each length-prefixed."""
    if named is None:
        own = rule(repo, commit)
        if own is None:
            raise Unknown("grading_rule_absent")
        named = _predicate(own)
    h = hashlib.sha256()
    for part in (grading_listing(repo, commit, named), build_listing(repo, commit)):
        h.update(len(part).to_bytes(8, "big"))
        h.update(part)
    return "sha256:" + h.hexdigest()


def pack(value) -> str:
    match = _HEX.fullmatch(value or "")
    if match is None:
        raise ValueError("a pack digest is 64 hex digits (optionally sha256:)")
    return match.group(1)


def check(repo, old, new, *, old_pack, new_pack, declared=None) -> dict:
    """The answer for OLD -> NEW with both packs (both required: a pack not compared is never the same exam)."""
    old_pack, new_pack = pack(old_pack), pack(new_pack)
    out = {"schema": SCHEMA, "old_ref": old, "new_ref": new}
    try:
        old, new = resolve(repo, old), resolve(repo, new)
        out.update(old=old, new=new)
        rules = rule(repo, old), rule(repo, new)
        if rules == (None, None):
            raise Unknown("grading_rule_absent")
        # A revision before M2 has no rule of its own: the other side's rule judges both (as M2's own migration
        # check does); said in the output. Present on both and different = an exam change.
        absent = [side for side, r in zip(("old", "new"), rules) if r is None]
        named = _predicate(*(r for r in rules if r is not None))
        names = _git(repo, "diff", "--name-only", "-z", "--no-renames", old, new, "--")
        changed = sorted(
            {p for p in names.decode("utf-8").split("\0") if p and named(p)}
        )
        moved = build_listing(repo, old) != build_listing(repo, new)
        digests = grading_digest(repo, old, named), grading_digest(repo, new, named)
    except (Unknown, UnicodeDecodeError) as failed:
        return {**out, "state": UNKNOWN, "reason": str(failed) or type(failed).__name__}
    rule_changed = not absent and rules[0] != rules[1]
    additions_only = None
    if rule_changed:
        # (Validator-2 6 Nov 13:21) a rule change that only ADDS grading paths makes M2 stricter; anything else (a
        # path removed, the module pattern or GRADING_EXCLUDED changed) can weaken it
        try:
            same_excluded = excluded(repo, old) == excluded(repo, new)
        except Unknown as failed:
            return {**out, "state": UNKNOWN, "reason": str(failed)}
        (old_paths, old_pattern), (new_paths, new_pattern) = rules
        additions_only = (
            set(old_paths) <= set(new_paths)
            and old_pattern == new_pattern
            and same_excluded
        )
        out.update(
            grading_rule_added=sorted(set(new_paths) - set(old_paths)),
            grading_rule_removed=sorted(set(old_paths) - set(new_paths)),
        )
    pack_changed = old_pack != new_pack
    out.update(
        old_grading_digest=digests[0],
        new_grading_digest=digests[1],
        grading_rule_changed=rule_changed,
        grading_rule_additions_only=additions_only,
        grading_rule_absent_at=absent,
        grading_paths_changed=changed,
        build_inputs_moved=moved,
        old_pack=old_pack,
        new_pack=new_pack,
        pack_changed=pack_changed,
    )
    if not (rule_changed or changed or moved or pack_changed):
        # Nothing named changed: the digests must agree too, or the diff and the listing disagree.
        if digests[0] != digests[1]:
            return {**out, "state": UNKNOWN, "reason": "digest_disagrees_with_diff"}
        return {**out, "state": SAME}
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
    c.add_argument("--old-pack", required=True)
    c.add_argument("--new-pack", required=True)
    c.add_argument("--declared-exam-change")
    args = parser.parse_args(argv)
    if args.command == "check":
        if (
            args.declared_exam_change is not None
            and not args.declared_exam_change.strip()
        ):
            parser.error("--declared-exam-change needs a reason")
        for name in ("old_pack", "new_pack"):
            try:
                pack(getattr(args, name))
            except ValueError as bad:
                parser.error(f"--{name.replace('_', '-')}: {bad}")
    try:
        if args.command == "digest":
            commit = resolve(args.repo, args.rev)
            result = {
                "schema": SCHEMA,
                "rev": commit,
                "grading_digest": grading_digest(args.repo, commit),
            }
            state = SAME
        else:
            result = check(
                args.repo,
                args.old,
                args.new,
                old_pack=args.old_pack,
                new_pack=args.new_pack,
                declared=args.declared_exam_change,
            )
            state = result["state"]
    except Exception as failed:  # noqa: BLE001
        # Every failure is a refusal (UNKNOWN), never a traceback with exit 1.
        result = {"schema": SCHEMA, "state": UNKNOWN, "reason": type(failed).__name__}
        state = UNKNOWN
    print(json.dumps(result, sort_keys=True))
    return EXIT[state]


if __name__ == "__main__":
    sys.exit(main())
