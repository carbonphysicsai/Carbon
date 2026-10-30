"""The backbone catalog's manifest, read-only: what every miner-reachable
reader (`served`, Motor's registry and practice) needs.

Kept apart from `pipeline`, the owner's command (add, verify, install): its
install reaches the owner installers and the receiver, which no miner surface
may import (`tests/invariants/test_attack_store_unreachable.py`).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
SCHEMA = "carbon.backbone-catalog-manifest.v1"


class CatalogBroken(ValueError):
    """The catalog's own files disagree: Carbon's problem, never a miner's."""


def _json(path):
    return json.loads(Path(path).read_bytes())


_LOADED = {"seal": None, "manifest": None}
_LOADED_LOCK = threading.Lock()


def _seal(path):
    """The file's stat seal and its newest timestamp: a rewrite changes the seal (ctime moves even when a writer
    restores the mtime), and a file that changed within `file_seal.RACY_NS` is not kept at all.
    """
    from carbon import file_seal

    stat = Path(path).stat()
    return file_seal.stat_seal(path, stat), max(stat.st_mtime_ns, stat.st_ctime_ns)


def clear_cache():
    """Forget the kept parse (tests and operator tools: the next `load` reads the file)."""
    with _LOADED_LOCK:
        _LOADED["seal"] = _LOADED["manifest"] = None


def load_fresh():
    """A new parse of the manifest that no one else holds: for the owner commands that edit it and write it
    back (`pipeline.add`, `add_twin`). `load` serves one shared object and must never be edited.
    """
    if not MANIFEST.exists():
        return {"schema": SCHEMA, "entries": []}
    manifest = _json(MANIFEST)
    if type(manifest) is not dict or manifest.get("schema") != SCHEMA:
        raise CatalogBroken("catalog manifest schema differs")
    return manifest


def load():
    """The manifest: {"schema", "entries": [...]}, ordered by catalog id.

    Parsed once per process and served again until the file changes (a full catalog is hundreds of entries and
    this is read for every entry of every Challenge). The returned object is shared: callers read it and never
    change it; copy before editing."""
    if not MANIFEST.exists():
        return {"schema": SCHEMA, "entries": []}
    from carbon import file_seal

    seal, newest = _seal(MANIFEST)
    with _LOADED_LOCK:
        if _LOADED["seal"] == seal:
            return _LOADED["manifest"]
    manifest = _json(MANIFEST)
    if type(manifest) is not dict or manifest.get("schema") != SCHEMA:
        raise CatalogBroken("catalog manifest schema differs")
    # Kept only if unchanged while it was read and settled (not rewritten inside one timestamp tick).
    if _seal(MANIFEST)[0] == seal and file_seal.settled(newest):
        with _LOADED_LOCK:
            _LOADED["seal"], _LOADED["manifest"] = seal, manifest
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
#: Shown on every entry whose GPU build is smoke-only (CNO1d, under each id): the official rebuild is the CPU one.
CPU_REBUILD_NOTE = " (CPU rebuild on this validator class)"
#: The legacy F08 CNO1d has the same GPU build but no smoke receipt (no valid GPU receipt: the official route
#: refuses it), so it is CPU-rebuilt too and is labelled alike.
LEGACY_CPU_REBUILD = frozenset({"f08.cno.CNO1d"})
LEGACY_NOTE = (
    " (legacy entry: some settings stay Carbon-limited here; the v2.* entries take "
    "every setting, so start from one of those)"
)


#: Versions whose served example is a named entry rather than the first v2.* one. Motor 1.4 and Cooling 1.4
#: serve the jNO bcat entry (Lead, 2026-10-26): it is the tested v2.* entry whose GPU rebuild is bit-identical
#: across runs (13/13 on the dev 4090, official determinism environment), where the CNO1d entries differ
#: (`upsample_bicubic2d_aa` backward has no deterministic CUDA kernel) and so rebuild on the CPU on a GPU host.
#: The CNO entries stay in the catalog.
SERVED_EXAMPLE = {
    ("electric-motor-magnetics", "1.4"): "v2.motor.jno.bcat",
    ("chip-cold-plate", "1.4"): "v2.cooling.jno.bcat",
}


def preferred(challenge_id, version):
    """The catalog id a ready example should use on (challenge_id, version): the named
    served example where one is registered (`SERVED_EXAMPLE`), else its first v2.* entry
    when it offers any, else None (the caller's own default stands)."""
    named = SERVED_EXAMPLE.get((challenge_id, version))
    if named is not None and any(
        item["catalog_id"] == named for item in entries(challenge_id, version)
    ):
        return named
    for item in entries(challenge_id, version):
        if item["catalog_id"].startswith(V2_PREFIX):
            return item["catalog_id"]
    return None


def install_order(items):
    """`items` (manifest entries) with the entries a first practice starts on first, the rest in their own order.

    A miner's first practice runs on the entry the picker starts on: each Challenge's newest catalog version's
    `preferred` entry. Installing all of a full catalog takes about 15 minutes, so those come first and a first
    practice can run a minute or two after the install starts, not after the last entry. A permutation: nothing is
    dropped, added or changed."""
    items = list(items)
    newest = {}
    for item in items:
        for each in item.get("challenges") or []:
            key = each["id"]
            if key not in newest or _version_key(each["version"]) > _version_key(
                newest[key]
            ):
                newest[key] = each["version"]
    first = []
    for challenge_id in sorted(newest):
        wanted = preferred(challenge_id, newest[challenge_id])
        if wanted is not None and wanted not in first:
            first.append(wanted)
    rank = {catalog_id: index for index, catalog_id in enumerate(first)}
    return sorted(items, key=lambda item: rank.get(item["catalog_id"], len(first)))


def _version_key(version):
    return tuple(int(part) if part.isdigit() else 0 for part in str(version).split("."))


def is_legacy(catalog_id, challenge_id, version):
    """Whether ``catalog_id`` is a pre-v2 entry on a version that also offers v2.* ones."""
    return (
        not catalog_id.startswith(V2_PREFIX)
        and preferred(challenge_id, version) is not None
    )


def summary(catalog_id, backbone, challenge_id, version):
    """The miner-facing line for a catalog entry, labelled when it is a legacy one."""
    from . import gpu_receipt

    text = "Carbon's tested " + backbone + " bundle"
    if catalog_id in gpu_receipt.SMOKE_ONLY or catalog_id in LEGACY_CPU_REBUILD:
        # Its GPU build is not bit-reproducible, so grading rebuilds it on the CPU.
        text += CPU_REBUILD_NOTE
    return text + (LEGACY_NOTE if is_legacy(catalog_id, challenge_id, version) else "")


def entry(catalog_id, challenge_id=None, version=None):
    for item in entries(challenge_id, version):
        if item["catalog_id"] == catalog_id:
            return item
    return None
