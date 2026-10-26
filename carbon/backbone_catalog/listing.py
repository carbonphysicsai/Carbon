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
    if named:
        # Entries named for another version carry only under the cross-version pair rule.
        from . import carries

        carries.require_identity_only(challenge_id, version)
    offered = [{"id": challenge_id, "version": each} for each in (version, *named)]
    return [
        e
        for e in load()["entries"]
        if any(challenge in e["challenges"] for challenge in offered)
    ]


#: The prefix of the v2 entries (graph route v2's catalog: every setting a miner may set).
V2_PREFIX = "v2."
LEGACY_NOTE = (
    " (legacy entry: some settings stay Carbon-limited here; the v2.* entries take "
    "every setting, so start from one of those)"
)


def preferred(challenge_id, version):
    """The catalog id a ready example should use on (challenge_id, version): its first
    v2.* entry when it offers any, else None (the caller's own default stands)."""
    for item in entries(challenge_id, version):
        if item["catalog_id"].startswith(V2_PREFIX):
            return item["catalog_id"]
    return None


def is_legacy(catalog_id, challenge_id, version):
    """Whether ``catalog_id`` is a pre-v2 entry on a version that also offers v2.* ones."""
    return (
        not catalog_id.startswith(V2_PREFIX)
        and preferred(challenge_id, version) is not None
    )


def summary(catalog_id, backbone, challenge_id, version):
    """The miner-facing line for a catalog entry, labelled when it is a legacy one."""
    text = "Carbon's tested " + backbone + " bundle"
    return text + (LEGACY_NOTE if is_legacy(catalog_id, challenge_id, version) else "")


def entry(catalog_id, challenge_id=None, version=None):
    for item in entries(challenge_id, version):
        if item["catalog_id"] == catalog_id:
            return item
    return None
