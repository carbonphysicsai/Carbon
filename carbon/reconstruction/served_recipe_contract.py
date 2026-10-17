"""Prospective served ConstructionRecipe identity, separate from Strategy 1.0.

The registered synthetic material is public DEVELOPMENT fixture material. This
contract identifies what a validator adapter may parse and build; it carries
no Score Pack, exam qualification, promotion or network authority. Historical
family/backbone contracts remain in ``capability_registry.CONTRACTS``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from carbon.development_session.construction_recipe import SCHEMA as RECIPE_SCHEMA

SCHEMA = "carbon.served-construction-recipe-contract.v1"


@dataclass(frozen=True)
class ServedRecipeContract:
    challenge_id: str
    version: str
    construction_kit: dict
    allowlist_digest: str

    @property
    def document(self) -> dict:
        return {
            "schema": SCHEMA,
            "challenge": {"id": self.challenge_id, "version": self.version},
            "recipe_schema": RECIPE_SCHEMA,
            "construction_kit": dict(self.construction_kit),
            "allowlist_digest": self.allowlist_digest,
            "scope": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
            "score_pack": None,
        }

    @property
    def digest(self) -> str:
        body = json.dumps(
            self.document, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(body).hexdigest()


def registered(challenge_id: str, version: str) -> ServedRecipeContract:
    """Return only the built-in verified 1.3 material; no caller-made contract."""
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5

    if (challenge_id, version) != ("synthetic-linear-field-2d", "1.3"):
        raise LookupError("served_recipe_contract_not_registered")
    material = bundle_material_v5()
    kit = material["construction_kit"]
    if (kit["id"], kit["version"]) != (challenge_id, version):
        raise RuntimeError("registered recipe material identity changed")
    return ServedRecipeContract(
        challenge_id, version, dict(kit), material["allowlist_digest"]
    )
