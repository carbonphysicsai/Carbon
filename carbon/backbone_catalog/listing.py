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
    """Every entry, or those offered on (challenge_id, version): named for it,
    or for each version whose entries it declares it offers
    (`version_registry`'s `catalog_entries_from`: graph route v2's Motor and
    Cooling 1.4 also offer 1.3's). An unregistered version offers its own
    named entries only."""
    if challenge_id is None:
        return list(load()["entries"])
    from carbon.challenge_kit.version_registry import find

    declared = find(challenge_id, version)
    named = declared.catalog_entries_from if declared is not None else ()
    offered = [{"id": challenge_id, "version": each} for each in (version, *named)]
    return [
        e
        for e in load()["entries"]
        if any(challenge in e["challenges"] for challenge in offered)
    ]


def entry(catalog_id, challenge_id=None, version=None):
    for item in entries(challenge_id, version):
        if item["catalog_id"] == catalog_id:
            return item
    return None
