"""A stand-in catalog entry on F08 1.4 or F02 2.3, for wiring tests only.

No F08 or F02 entry is tested yet: each needs its own pair-identity receipt.
These tests inject one by patching the read-only manifest
(`carbon.backbone_catalog.listing.load`): a copy of a Motor-tested Torch
entry, renamed and offered on the named version. It exercises Carbon's wiring
(catalog digest, recipe binding, expansion, practice and submit plumbing); it
is not an F08- or F02-tested backbone and claims nothing about either.
"""

from __future__ import annotations

import copy

STAND_IN = "standin.direct_fno"


def inject(monkeypatch, challenge_id, version):
    """Offer the stand-in on (challenge_id, version); returns the entry."""
    from carbon.backbone_catalog import listing

    manifest = listing.load()
    item = copy.deepcopy(
        next(e for e in manifest["entries"] if e["catalog_id"] == "neuralop.FNO")
    )
    item["catalog_id"] = STAND_IN
    item["challenges"] = [{"id": challenge_id, "version": version}]
    patched = {**manifest, "entries": [*manifest["entries"], item]}
    monkeypatch.setattr(listing, "load", lambda: patched)
    return item


def empty(monkeypatch, challenge_id, version):
    """Offer nothing on (challenge_id, version): the empty-catalog paths, now
    that F08 1.4 / F02 2.3 serve tested entries (B3, 2026-10-22)."""
    from carbon.backbone_catalog import listing

    manifest = listing.load()
    key = {"id": challenge_id, "version": version}
    entries = [
        {**e, "challenges": [c for c in e["challenges"] if c != key]}
        for e in manifest["entries"]
    ]
    patched = {**manifest, "entries": [e for e in entries if e["challenges"]]}
    monkeypatch.setattr(listing, "load", lambda: patched)
