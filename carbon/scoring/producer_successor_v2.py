"""A registered producer successor for ANY registered version (new-exam prep #2; v2 ruling 22 Nov 2026 00:12:09Z).

`producer_successor` (v1) admits a successor row only for a subset-repeat version (its rule L2: ANY other row makes
its whole registry refuse), and it is a Motor 1.8 producer file, so it is never edited (fix forward, no live version's
bytes move). Versions registered from now on name THIS module in their producer FILES instead
(`NEW_VERSION_PRODUCER_FILES`); Motor 1.8 keeps v1, its registry and its L2 unchanged.

This module reads its OWN registry, ``scripts/validator_host_classes/producer_successor_v2.json`` (own `SCHEMA`), and
never v1's file: a v2 row in v1's registry would make v1 refuse Motor 1.8's live successor binding. One row per
``"<challenge> <version>"`` (a duplicate key refuses the whole registry):

    {"pack_producer_digest": <the digest the live pack pins>,
     "producer_digest": <the exact new code's digest (differs from the pinned one)>,
     "v2_receipt": "<RECEIPTS col-1 UTC time> <seat>",
     "kept_grade_proof": {"path": <repo-relative file>, "sha256": "sha256:<hex>"}}

The kept-grade proof is the bit-for-bit evidence that the new producer grades kept grades exactly as the pinned one (the
LO-3 pattern; owner line 5 of NEW_EXAM_BLOCKERS_20261121.md): its file's sha256 is checked before the row is honoured.
A missing, mismatched or malformed proof, a missing or malformed registry, or no row is NO row: today's refusal, fail
closed. Nothing here raises.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

SCHEMA = "carbon.exam.producer-successor.v2"
_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = _ROOT / "scripts" / "validator_host_classes" / "producer_successor_v2.json"
#: The producer files a version registered from now on lists for its successor binding (in place of v1's module).
NEW_VERSION_PRODUCER_FILES = ("producer_successor_v2.py",)
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RECEIPT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z [a-z][a-z0-9-]{0,31}\Z")
_ROW_KEYS = {
    "pack_producer_digest",
    "producer_digest",
    "v2_receipt",
    "kept_grade_proof",
}
_PROOF_KEYS = {"path", "sha256"}
_PROOF_PATH = re.compile(r"[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*\Z")


class _Duplicate(ValueError):
    pass


def _no_duplicates(pairs):
    keys = [k for k, _v in pairs]
    if len(keys) != len(set(keys)):
        raise _Duplicate("duplicate key")
    return dict(pairs)


def _proof_holds(proof, root):
    """The kept-grade proof file exists inside the repository (no link, no ``..``) and has the recorded sha256."""
    if type(proof) is not dict or set(proof) != _PROOF_KEYS:
        return False
    rel, want = proof["path"], proof["sha256"]
    if (
        type(rel) is not str
        or type(want) is not str
        or not _DIGEST.fullmatch(want)
        or not _PROOF_PATH.fullmatch(rel)
        or any(part in ("", ".", "..") for part in rel.split("/"))
    ):
        return False
    base = Path(root).resolve()
    path = base / rel
    if path.is_symlink() or not path.is_file():
        return False
    if base not in path.resolve().parents:
        return False
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() == want


def row(challenge, version, *, path=None, root=None):
    """The registered row of ``"<challenge> <version>"`` (any registered version), or None. Never raises."""
    try:
        document = json.loads(
            Path(REGISTRY if path is None else path).read_bytes(),
            object_pairs_hook=_no_duplicates,
        )
        if (
            type(document) is not dict
            or document.get("schema") != SCHEMA
            or set(document) != {"schema", "rows"}
            or type(document["rows"]) is not dict
        ):
            return None
        found = document["rows"].get(f"{challenge} {version}")
        if (
            type(found) is not dict
            or set(found) != _ROW_KEYS
            or not all(
                type(found[k]) is str and _DIGEST.fullmatch(found[k])
                for k in ("pack_producer_digest", "producer_digest")
            )
            or found["pack_producer_digest"] == found["producer_digest"]
            or type(found["v2_receipt"]) is not str
            or not _RECEIPT.fullmatch(found["v2_receipt"])
            or not _proof_holds(
                found["kept_grade_proof"], _ROOT if root is None else root
            )
        ):
            return None
        return {k: found[k] for k in ("pack_producer_digest", "producer_digest")}
    except (OSError, ValueError, TypeError):
        return None


def binds(challenge, version, pinned, identity, *, path=None, root=None):
    """Whether a pack pinning ``pinned`` is graded by the running producer ``identity``: exactly equal, or the version's
    v2 successor row maps exactly ``pinned`` to exactly ``identity``."""
    if type(pinned) is not str or type(identity) is not str:
        return False
    if pinned == identity:
        return True
    found = row(challenge, version, path=path, root=root)
    return (
        found is not None
        and found["pack_producer_digest"] == pinned
        and found["producer_digest"] == identity
    )


def pinned_basis(challenge, version, basis, *, path=None, root=None):
    """A measurement basis read through the version's v2 successor row (as v1's `pinned_basis`), else None."""
    found = row(challenge, version, path=path, root=root)
    if (
        found is None
        or type(basis) is not dict
        or basis.get("producer_digest") != found["producer_digest"]
    ):
        return None
    return {**basis, "producer_digest": found["pack_producer_digest"]}


__all__ = [
    "NEW_VERSION_PRODUCER_FILES",
    "REGISTRY",
    "SCHEMA",
    "binds",
    "pinned_basis",
    "row",
]
