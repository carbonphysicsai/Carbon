"""The prospective recipe contract is distinct from legacy strategy contracts."""

from pathlib import Path

import pytest

from carbon.battery import challenge as battery_challenge
from carbon.battery.construction_bundle_material import (
    bundle_material as battery_bundle_material,
)
from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator.lean_recipe import _source_identity
from carbon.development_session.construction_recipe import SCHEMA as RECIPE_SCHEMA
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE, contract_digest
from carbon.reconstruction.served_recipe_contract import (
    RemoteStageAttachment,
    ServedRecipeContract,
    registered,
)


def test_synthetic_v13_registered_recipe_contract_binds_existing_material():
    material = bundle_material_v5()
    contract = registered("synthetic-linear-field-2d", "1.3")
    assert contract.construction_kit == material["construction_kit"]
    assert contract.allowlist_digest == material["allowlist_digest"]
    assert contract.document["recipe_schema"] == RECIPE_SCHEMA
    assert contract.document["score_pack"] is None
    assert contract.document["scope"] == "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY"
    assert contract.digest.startswith("sha256:")
    assert contract.digest != contract_digest(BATTERY_CHALLENGE)


def test_battery_v10_served_contract_binds_original_public_bundle_material():
    material = battery_bundle_material()
    contract = registered(
        battery_challenge.CHALLENGE.challenge_id,
        battery_challenge.CHALLENGE.version,
    )
    assert contract.construction_kit == material["construction_kit"]
    assert contract.allowlist_digest == material["allowlist_digest"]
    assert contract.document["scope"] == "PUBLIC_BATTERY_DEVELOPMENT_ONLY"
    assert contract.evidence_label == "DEVELOPMENT_PUBLIC_BATTERY"
    assert contract.document["score_pack"] is None


@pytest.mark.parametrize(
    "challenge,version",
    [
        ("synthetic-linear-field-2d", "1.2"),
        ("battery-fastcharge-ageing-development-v1", "1.3"),
        ("unknown", "1.3"),
    ],
)
def test_no_other_recipe_contract_is_registered(challenge, version):
    with pytest.raises(LookupError, match="served_recipe_contract_not_registered"):
        registered(challenge, version)


@pytest.mark.parametrize("lowerer", ["lower_jax.py", "lower_torch.py"])
def test_served_implementation_identity_binds_staged_lowerers(monkeypatch, lowerer):
    baseline = _source_identity()
    original = Path.read_bytes

    def changed(path):
        body = original(path)
        if path.as_posix().endswith("/carbon/level4/tooling/" + lowerer):
            return body + b"\n# test-only source drift\n"
        return body

    monkeypatch.setattr(Path, "read_bytes", changed)
    assert _source_identity() != baseline


@pytest.mark.parametrize(
    "challenge_id,version,state_name,route",
    [
        ("synthetic-linear-field-2d", "1.3", "remote-stage-v1.3", "DIRECT_DEVELOPMENT"),
        (
            "battery-fastcharge-ageing-development-v1",
            "1.0",
            "remote-stage-battery-v1.0",
            "SIGNED_RESEARCH",
        ),
    ],
)
def test_registered_attachment_routing_preserves_public_contract_identity(
    challenge_id, version, state_name, route
):
    contract = registered(challenge_id, version)
    assert contract.remote_stage_attachment == RemoteStageAttachment(state_name, route)
    # The historical constructor and serialized contract do not acquire local
    # attachment metadata or change the immutable public contract identity.
    historical = ServedRecipeContract(
        contract.challenge_id,
        contract.version,
        contract.construction_kit,
        contract.allowlist_digest,
        contract.scope,
    )
    assert historical.remote_stage_attachment is None
    assert historical.document == contract.document
    assert historical.digest == contract.digest
    assert set(contract.document) == {
        "schema",
        "challenge",
        "recipe_schema",
        "construction_kit",
        "allowlist_digest",
        "scope",
        "score_pack",
    }
