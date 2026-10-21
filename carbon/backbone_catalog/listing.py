"""The backbone catalog's manifest, read-only: what every miner-reachable
reader (`served`, Motor's registry and practice) needs.

Kept apart from `pipeline`, the owner's command (add, verify, install): its
install reaches the owner installers and the receiver, which no miner surface
may import (`tests/invariants/test_attack_store_unreachable.py`).
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
SCHEMA = "carbon.backbone-catalog-manifest.v1"


class CatalogBroken(ValueError):
    """The catalog's own files disagree: Carbon's problem, never a miner's."""


def _json(path):
    return json.loads(Path(path).read_bytes())


def load():
    """The manifest: {"schema", "entries": [...]}, ordered by catalog id."""
    if not MANIFEST.exists():
        return {"schema": SCHEMA, "entries": []}
    manifest = _json(MANIFEST)
    if type(manifest) is not dict or manifest.get("schema") != SCHEMA:
        raise CatalogBroken("catalog manifest schema differs")
    return manifest


def entries(challenge_id=None, version=None):
    """Every entry, or those offered on (challenge_id, version)."""
    return [
        e
        for e in load()["entries"]
        if challenge_id is None
        or {"id": challenge_id, "version": version} in e["challenges"]
    ]


def entry(catalog_id, challenge_id=None, version=None):
    for item in entries(challenge_id, version):
        if item["catalog_id"] == catalog_id:
            return item
    return None
