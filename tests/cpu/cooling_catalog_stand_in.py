"""A stand-in Cooling 1.2 catalog entry for wiring tests only.

Cooling 1.2's real entries (the five `cooling.*` Torch builds, each with its
Cooling pair-identity receipt) are in the manifest. These wiring tests patch
the read-only manifest (`carbon.backbone_catalog.listing.load`) instead, so
each states its catalog exactly: `inject` offers only a stand-in on Cooling
1.2 (a copy of a Motor-tested Torch entry, renamed; it claims nothing about
Cooling), and `empty` offers nothing there, for the empty-catalog refusals.
"""

from __future__ import annotations

import copy

COOLING = "chip-cold-plate"
STAND_IN = "standin.cooling_fno"


def _without_cooling(manifest):
    return [
        e
        for e in manifest["entries"]
        if not any(c["id"] == COOLING for c in e["challenges"])
    ]


def inject(monkeypatch):
    """Offer only the stand-in on Cooling 1.2; returns the entry."""
    from carbon.backbone_catalog import listing

    manifest = listing.load()
    item = copy.deepcopy(
        next(e for e in manifest["entries"] if e["catalog_id"] == "neuralop.FNO")
    )
    item["catalog_id"] = STAND_IN
    item["challenges"] = [{"id": COOLING, "version": "1.2"}]
    patched = {**manifest, "entries": [*_without_cooling(manifest), item]}
    monkeypatch.setattr(listing, "load", lambda: patched)
    return item


def empty(monkeypatch):
    """Offer nothing on Cooling 1.2 (the empty-catalog refusals)."""
    from carbon.backbone_catalog import listing

    manifest = listing.load()
    patched = {**manifest, "entries": _without_cooling(manifest)}
    monkeypatch.setattr(listing, "load", lambda: patched)
