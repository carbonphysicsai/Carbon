"""Allowance groups: which funder a coldkey belongs to (OWNER-PROBING-COUNTERS-01 (a); R89).

One function, `FunderMap.group(coldkey)`, keys both the door's verified request bucket (R89: Validator-2
6 Nov 09:16, Release Architect 11:31, Validator-2 11:32) and, later, the exam allowance (a). A group is an
opaque id. The map file is operator-only. It is written by the Chain Auditor's refresh job, and its group ids
are digests: no ss58 and no amounts appear in them, and no group id is ever served.

The map is keyed by COLDKEY, so every hotkey of one coldkey always shares a group, even a hotkey registered
after the last refresh. A coldkey the map does not name is its own group (the per-coldkey fallback). A map
that is missing, unreadable or malformed is no map at all: every coldkey is its own group and `problem`
says why. It never refuses traffic and never widens to per-hotkey.

The funder rule itself (which transfer names a funder; the exchange exclusions) is the Chain Auditor's. This
module only loads its output.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

SCHEMA = "carbon.funder-map.v1"
MAX_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 65536
_HEX = frozenset("0123456789abcdef")


def _coldkey_group(coldkey):
    """The fallback group of an unmapped coldkey: a digest, never the ss58 itself."""
    return (
        "c:"
        + hashlib.sha256(
            ("carbon.funder-group.coldkey.v1\0" + coldkey).encode()
        ).hexdigest()
    )


def _valid_group_id(value):
    return type(value) is str and len(value) == 64 and set(value) <= _HEX


def _valid_coldkey(value):
    return (
        type(value) is str
        and 1 <= len(value) <= 64
        and value.isascii()
        and value.isalnum()
    )


@dataclass(frozen=True)
class FunderMap:
    """An immutable coldkey -> group map. `FunderMap.empty()` means "no map": every coldkey is its own group."""

    groups: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))
    block: int | None = None
    digest: str | None = None
    #: Why no usable map is loaded (a closed code), or None. The operator alerts on it; nothing is refused.
    problem: str | None = None

    @classmethod
    def empty(cls, problem=None):
        return cls(problem=problem)

    def group(self, coldkey):
        """The allowance group of a coldkey. Never raises for a well-formed ss58-like string."""
        mapped = self.groups.get(coldkey)
        return "f:" + mapped if mapped is not None else _coldkey_group(coldkey)


def parse(raw):
    """A `FunderMap` from the file's bytes, or `FunderMap.empty(problem=...)` when they are not a valid map."""
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        return FunderMap.empty("funder_map_size")
    try:
        document = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return FunderMap.empty("funder_map_malformed")
    if type(document) is not dict or set(document) != {"schema", "block", "groups"}:
        return FunderMap.empty("funder_map_malformed")
    if document["schema"] != SCHEMA:
        return FunderMap.empty("funder_map_schema")
    block, groups = document["block"], document["groups"]
    if (
        type(block) is not int
        or block < 0
        or type(groups) is not dict
        or len(groups) > MAX_ENTRIES
    ):
        return FunderMap.empty("funder_map_malformed")
    if not all(_valid_coldkey(k) and _valid_group_id(v) for k, v in groups.items()):
        return FunderMap.empty("funder_map_malformed")
    return FunderMap(
        groups=MappingProxyType(dict(groups)),
        block=block,
        digest=hashlib.sha256(raw).hexdigest(),
    )


def load(path):
    """Read an operator-only map file. A path of None means no map is configured (no problem)."""
    if path is None:
        return FunderMap.empty()
    path = Path(path)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        return FunderMap.empty("funder_map_unreadable")
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            return FunderMap.empty("funder_map_not_owner_only")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = handle.read(MAX_BYTES + 1)
    finally:
        os.close(fd)
    return parse(raw)
