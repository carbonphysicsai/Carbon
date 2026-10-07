"""Merkle roots and proofs for bank tranches (VALIDATOR-23).

Kept apart from the producer's `bank` module, so a validator surface can
verify a drawn case's membership without importing the producer.

A tranche's leaves are its cases in case-id order. Each leaf is
`sha256(0x00 || canonical {case_id, inputs, reference})`; an inner node is
`sha256(0x01 || left || right)`; an odd node is carried up unchanged. A proof
is the list of `[side, hash]` siblings from the leaf to the root, where side
says on which side the sibling lies.
"""

from __future__ import annotations

import hashlib
import json


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def leaf(case_id, inputs, reference):
    body = _canonical({"case_id": case_id, "inputs": inputs, "reference": reference})
    return hashlib.sha256(b"\x00" + body).hexdigest()


def _node(left, right):
    return hashlib.sha256(
        b"\x01" + bytes.fromhex(left) + bytes.fromhex(right)
    ).hexdigest()


def tree(leaves):
    """Every level, leaves first."""
    if not leaves:
        raise ValueError("a tranche has at least one case")
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        level, up = levels[-1], []
        for i in range(0, len(level), 2):
            up.append(_node(level[i], level[i + 1]) if i + 1 < len(level) else level[i])
        levels.append(up)
    return levels


def root(leaves):
    return "sha256:" + tree(leaves)[-1][0]


def proof(leaves, index):
    """The sibling path of `leaves[index]`."""
    path = []
    for level in tree(leaves)[:-1]:
        sibling = index ^ 1
        if sibling < len(level):
            path.append(["L" if sibling < index else "R", level[sibling]])
        index //= 2
    return path


def verify(case_id, inputs, reference, path, expected_root):
    """Whether `(case_id, inputs, reference)` proves into `expected_root`."""
    try:
        value = leaf(case_id, inputs, reference)
        for side, sibling in path:
            if side == "L":
                value = _node(sibling, value)
            elif side == "R":
                value = _node(value, sibling)
            else:
                return False
    except (TypeError, ValueError):
        return False
    return "sha256:" + value == expected_root


__all__ = ["leaf", "proof", "root", "verify"]
