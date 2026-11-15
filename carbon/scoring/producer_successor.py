"""A registered producer successor: a live pack's pinned producer digest read as one exact newer producer.

A sealed pack pins its producer (``accuracy_definition.producer_digest``, `physical_dual_pack.producer_digest`): the
bytes of every file the producer executes. Motor 1.8's keyed subset repeat (owner, Sun 15 Nov 2026 08:19 CST: "I also do
not think that needs a new exam version") changes Motor 1.8's own producer files and so its digest, while its live pack,
exam key and public accuracy definition stay exactly as sealed. Validator-2B's R-1 admits that through ONE successor row
per version (``scripts/validator_host_classes/producer_successor.json``):

    "<challenge> <version>": {"pack_producer_digest": <the digest the live pack pins>,
                              "producer_digest": <the exact new code's digest>}

`binds` accepts a pinned digest that is not the running producer's only when the row maps exactly that pinned digest to
exactly the producer's digest recomputed at load (`physical_dual_pack.producer_digest`); any mismatch, a missing or
malformed registry, or a version with no row refuses as before. New grades carry the new digest in their evidence and
measurement basis (R-3); a measurement basis that carries the row's producer digest is that pinned contract read through
the row (`pinned_basis`), never a rescore. The record is docs/records/2026-11-15-motor18-subset-repeat.json.

This module is a producer file of Motor 1.8 only (`motor18_dual_pack.FILES`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SCHEMA = "carbon.exam.producer-successor.v1"
REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "validator_host_classes"
    / "producer_successor.json"
)
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ROW_KEYS = {"pack_producer_digest", "producer_digest"}


def row(challenge, version, *, path=None):
    """The registered ``{"pack_producer_digest", "producer_digest"}`` of ``"<challenge> <version>"``, or None (no
    registry, a malformed one, no row, or a malformed row: every one refuses a successor, fail closed). Never raises.
    """
    try:
        document = json.loads(Path(REGISTRY if path is None else path).read_bytes())
    except (OSError, ValueError):
        return None
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
            type(found[k]) is str and _DIGEST.fullmatch(found[k]) for k in _ROW_KEYS
        )
        or found["pack_producer_digest"] == found["producer_digest"]
    ):
        return None
    return dict(found)


def binds(challenge, version, pinned, identity, *, path=None):
    """Whether a pack pinning ``pinned`` is graded by the running producer ``identity`` (recomputed by the caller):
    exactly equal, or the version's successor row maps exactly ``pinned`` to exactly ``identity``.
    """
    if type(pinned) is not str or type(identity) is not str:
        return False
    if pinned == identity:
        return True
    found = row(challenge, version, path=path)
    return (
        found is not None
        and found["pack_producer_digest"] == pinned
        and found["producer_digest"] == identity
    )


def pinned_basis(challenge, version, basis, *, path=None):
    """A measurement basis read through the version's successor row: ``basis`` with its ``producer_digest`` replaced by
    the pinned one, when it carries exactly the row's producer digest; else None."""
    found = row(challenge, version, path=path)
    if (
        found is None
        or type(basis) is not dict
        or basis.get("producer_digest") != found["producer_digest"]
    ):
        return None
    return {**basis, "producer_digest": found["pack_producer_digest"]}


__all__ = ["REGISTRY", "SCHEMA", "binds", "pinned_basis", "row"]
