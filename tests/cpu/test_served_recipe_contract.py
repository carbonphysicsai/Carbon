"""The prospective recipe contract is distinct from legacy strategy contracts."""

from pathlib import Path

import pytest

from carbon.challenge_kit.synthetic_linear_field_2d import bundle_material_v5
from carbon.challenge_validator.lean_recipe import _source_identity
from carbon.development_session.construction_recipe import SCHEMA as RECIPE_SCHEMA
from carbon.reconstruction.capability_registry import BATTERY_CHALLENGE, contract_digest
from carbon.reconstruction.served_recipe_contract import registered


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
