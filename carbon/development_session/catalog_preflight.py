"""Check a catalog recipe against the door's catalog before it is frozen or signed.

The door's public intake info names the digest of the catalog it serves
(`catalog_digest`). A catalog recipe whose id, settings or digest the door would
refuse is refused here instead, with the fix named, for every route that reaches
the door (app, hand-written or agent-written). Nothing here is a scientific or
security decision: the door still checks every recipe itself.
"""

from __future__ import annotations

from carbon.backbone_catalog import listing, served
from carbon.backbone_catalog.entries import CatalogRefused

CATALOG_CHANGED = "construction_catalog_changed"
ENTRY_UNKNOWN = "catalog_entry_unknown"
SETTING_UNKNOWN = "catalog_setting_unknown"


class CatalogPreflightRefused(ValueError):
    """A catalog recipe the door would refuse; `fix` says what to change."""

    def __init__(self, code: str, fix: str):
        super().__init__(f"{code}: {fix}")
        self.code, self.fix = code, fix


def check(recipe: dict, facts: dict | None = None) -> None:
    """Raise `CatalogPreflightRefused` for a catalog recipe the door would refuse.

    `recipe` is the recipe dict; `facts` the door's intake info (None: only the
    local catalog is checked). A recipe of another source kind passes untouched.
    """
    source = recipe.get("source") or {}
    if source.get("kind") != "catalog":
        return
    challenge = recipe["challenge"]
    key = (challenge["id"], challenge["version"])
    door = (facts or {}).get("catalog_digest")
    mine = source.get("catalog_digest")
    if door is not None and mine != door:
        raise CatalogPreflightRefused(
            CATALOG_CHANGED,
            "catalog changed: this recipe was made against a different catalog than the "
            "door serves; update the app (or re-read the catalog) and rebuild the recipe",
        )
    if listing.entry(source.get("catalog_id"), *key) is None:
        offered = ", ".join(e["catalog_id"] for e in listing.entries(*key)) or "none"
        raise CatalogPreflightRefused(
            ENTRY_UNKNOWN,
            f"entry {source.get('catalog_id')!r} is not in this Challenge version's "
            f"catalog; choose one of: {offered}",
        )
    if mine != served.digest(*key):
        raise CatalogPreflightRefused(
            CATALOG_CHANGED,
            "catalog changed: this app's catalog is not the one the recipe names; "
            "update the app and rebuild the recipe",
        )
    try:
        served.expand(recipe)
    except CatalogRefused as refused:
        if refused.code == SETTING_UNKNOWN:
            raise CatalogPreflightRefused(
                SETTING_UNKNOWN,
                f"setting not accepted by entry {source['catalog_id']!r}: {refused.detail}",
            ) from None
        raise CatalogPreflightRefused(refused.code, refused.detail) from None
    except (KeyError, TypeError, ValueError) as bad:
        raise CatalogPreflightRefused(
            "catalog_setting_invalid", f"recipe settings unreadable: {bad}"
        ) from None
