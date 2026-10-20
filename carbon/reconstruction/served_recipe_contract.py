"""Prospective served ConstructionRecipe identity, separate from Strategy 1.0.

Only registered public DEVELOPMENT material can reach this contract. It
identifies what a validator adapter may parse and build; it carries no Score
Pack, exam qualification, promotion or network authority. Historical
family/backbone contracts remain in ``capability_registry.CONTRACTS``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from carbon.development_session.construction_recipe import SCHEMA as RECIPE_SCHEMA

SCHEMA = "carbon.served-construction-recipe-contract.v1"


@dataclass(frozen=True)
class RemoteStageAttachment:
    """Trusted local attachment routing; absent from the public contract."""

    state_name: str
    connection_route: Literal["DIRECT_DEVELOPMENT", "SIGNED_RESEARCH"]


@dataclass(frozen=True)
class ServedRecipeContract:
    challenge_id: str
    version: str
    construction_kit: dict
    allowlist_digest: str
    scope: str = "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY"
    remote_stage_attachment: RemoteStageAttachment | None = None

    @property
    def evidence_label(self) -> str:
        labels = {
            "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY": "DEVELOPMENT_PUBLIC_SYNTHETIC",
            "PUBLIC_BATTERY_DEVELOPMENT_ONLY": "DEVELOPMENT_PUBLIC_BATTERY",
            "PUBLIC_PHYSICAL_DEVELOPMENT_ONLY": "DEVELOPMENT_PUBLIC_PHYSICAL",
            "PUBLIC_F08_DEVELOPMENT_ONLY": "DEVELOPMENT_PUBLIC_PHYSICAL",
        }
        try:
            return labels[self.scope]
        except KeyError:
            raise ValueError("served recipe scope is unregistered") from None

    @property
    def document(self) -> dict:
        return {
            "schema": SCHEMA,
            "challenge": {"id": self.challenge_id, "version": self.version},
            "recipe_schema": RECIPE_SCHEMA,
            "construction_kit": dict(self.construction_kit),
            "allowlist_digest": self.allowlist_digest,
            "scope": self.scope,
            "score_pack": None,
        }

    @property
    def digest(self) -> str:
        body = json.dumps(
            self.document, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(body).hexdigest()


def registered(challenge_id: str, version: str) -> ServedRecipeContract:
    """Select only exact public material for the two registered Challenges."""
    from carbon.battery import challenge as battery_challenge
    from carbon.battery.construction_bundle_material import (
        bundle_material as battery_bundle_material,
    )
    from carbon.challenge_kit import physical_material
    from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5

    if (challenge_id, version) == ("synthetic-linear-field-2d", "1.3"):
        material = bundle_material_v5()
        attachment = RemoteStageAttachment("remote-stage-v1.3", "DIRECT_DEVELOPMENT")
    elif (challenge_id, version) == (
        battery_challenge.CHALLENGE.challenge_id,
        battery_challenge.CHALLENGE.version,
    ):
        material = battery_bundle_material()
        attachment = RemoteStageAttachment(
            "remote-stage-battery-v1.0", "SIGNED_RESEARCH"
        )
    elif physical_material.is_registered(challenge_id, version):
        material = physical_material.bundle_material(challenge_id, version)
        attachment = RemoteStageAttachment(
            "remote-stage-" + challenge_id + "-v" + version, "SIGNED_RESEARCH"
        )
    else:
        raise LookupError("served_recipe_contract_not_registered")
    kit = material["construction_kit"]
    if (kit["id"], kit["version"]) != (challenge_id, version):
        raise RuntimeError("registered recipe material identity changed")
    return ServedRecipeContract(
        challenge_id,
        version,
        dict(kit),
        material["allowlist_digest"],
        material["disclosure"]["scope"],
        remote_stage_attachment=attachment,
    )
