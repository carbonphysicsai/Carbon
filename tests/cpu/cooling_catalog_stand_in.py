"""A stand-in Cooling 1.2 catalog entry for wiring tests only.

No Cooling entry is tested yet: each needs its own Cooling pair-identity
receipt from the Test Lead. These tests inject one by patching the read-only
manifest (`carbon.backbone_catalog.listing.load`): a copy of a Motor-tested
Torch entry, renamed and offered on Cooling 1.2. It exercises Carbon's wiring
(catalog digest, recipe binding, expansion, practice and submit plumbing); it
is not a Cooling-tested backbone and claims nothing about Cooling.
"""

from __future__ import annotations

import copy

COOLING = "chip-cold-plate"
STAND_IN = "standin.cooling_fno"


def inject(monkeypatch):
    """Offer the stand-in on Cooling 1.2; returns the entry."""
    from carbon.backbone_catalog import listing

    manifest = listing.load()
    item = copy.deepcopy(
        next(e for e in manifest["entries"] if e["catalog_id"] == "neuralop.FNO")
    )
    item["catalog_id"] = STAND_IN
    item["challenges"] = [{"id": COOLING, "version": "1.2"}]
    patched = {**manifest, "entries": [*manifest["entries"], item]}
    monkeypatch.setattr(listing, "load", lambda: patched)
    return item
