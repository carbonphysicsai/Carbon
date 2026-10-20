"""Battery 2.0's construction side, the step-2 version (Validator,
STEP2_BATCH_VERSIONS_20261020): served material from Data Collection's bank
with the reference_present mask (Test Engineer's mask interface §3), served
v6, and no fixed training-step cap (OWNER-REBUILD-TIME-LIMIT-01). Battery 1.0
is unchanged.

The bank itself is Data Collection's; a stand-in here (1.0's 200 practice
rows, then three absent probe rows) checks only this lane's wiring.
"""

from __future__ import annotations

import numpy as np
import pytest

from carbon.battery import challenge as battery_challenge
from carbon.battery import construction_bundle_material as cbm
from carbon.battery import construction_kit, direct_graph
from carbon.challenge_kit.synthetic_linear_field_2d import allowlist_v5_bytes
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.level4 import allowlist as allowlist_module

BATTERY = battery_challenge.CHALLENGE.challenge_id
PROBES = 3


@pytest.fixture
def bank(monkeypatch):
    from carbon.challenge_kit import physical_pack

    v1 = cbm.bundle_material()
    width = v1["practice_reference"].shape[1]
    inputs = np.vstack([v1["practice_inputs"], v1["practice_inputs"][:PROBES]])
    references = np.vstack([v1["practice_reference"], np.full((PROBES, width), np.nan)])
    n = inputs.shape[0]
    stand_in = {
        "case_ids": tuple(v1["practice_case_ids"])
        + tuple(f"p{i}-base" for i in range(PROBES)),
        "cohorts": ("practice",) * (n - PROBES) + ("probe",) * PROBES,
        "inputs": inputs,
        "references": references,
        "reference_present": (True,) * (n - PROBES) + (False,) * PROBES,
    }

    def development_bank(challenge_id, version):
        assert (challenge_id, version) == (BATTERY, "2.0")
        return stand_in

    monkeypatch.setattr(
        physical_pack, "development_bank", development_bank, raising=False
    )
    return stand_in


def test_battery_1_0_material_is_unchanged():
    assert cbm.VERSIONS == ("1.0", "2.0")
    old, new = cbm.bundle_material(), cbm.versioned_material("1.0")
    assert new["construction_kit"] == old["construction_kit"]
    assert new["allowlist_bytes"] == old["allowlist_bytes"] == allowlist_v5_bytes()
    assert (
        cbm.construction_limits_document_for("1.0")
        == cbm.construction_limits_document()
    )


@pytest.mark.parametrize("version", ["1.1", "3.0", ""])
def test_an_unregistered_battery_version_is_refused(version):
    for read in (cbm.versioned_material, construction_kit.construction_kit_for):
        with pytest.raises(battery_challenge.MaterialMismatch):
            read(version)


def test_battery_2_0_serves_the_bank_with_its_mask_v6_and_no_step_cap(bank):
    material = cbm.versioned_material("2.0")
    n = len(bank["case_ids"])
    assert material["challenge_key"].version == "2.0"
    assert material["construction_kit"]["version"] == "2.0"
    assert material["practice_inputs"].shape == (n, 4)
    assert material["expected_output_shape"] == (n, 247)
    assert material["reference_present"] == bank["reference_present"]
    assert np.isnan(material["practice_reference"][-PROBES:]).all()
    assert material["practice_case_ids"] == bank["case_ids"]
    # Public practice feedback reads only practice rows with a reference.
    assert material["public_practice_rows"] == tuple(range(n - PROBES))
    assert material["allowlist_bytes"] == allowlist_module.served_bytes()
    assert material["physics_contract"]["version"] == "battery-physics-v2"
    assert set(material["physics_contract"]) == {"version", "definition"}
    limits = material["construction_limits_document"]
    assert limits["schema"] == cbm.LIMITS_SCHEMA_V2
    assert limits["training_step_cap"] is None and limits["practice_cases"] == n
    assert material["construction_kit"]["construction_limits_digest"] != (
        cbm.bundle_material()["construction_kit"]["construction_limits_digest"]
    )


def test_a_present_nan_or_an_absent_value_is_refused(bank, monkeypatch):
    broken = dict(bank, references=bank["references"].copy())
    broken["references"][0, 0] = np.nan
    from carbon.challenge_kit import physical_pack

    monkeypatch.setattr(physical_pack, "development_bank", lambda *_: broken)
    with pytest.raises(battery_challenge.MaterialMismatch, match="reference_invalid"):
        cbm.versioned_material("2.0")


def test_the_bundle_worker_checks_2_0_limits_against_its_own_material(bank):
    from carbon.development_session.bundle_construction_worker import (
        verify_direct_resource_policy,
    )

    material = cbm.versioned_material("2.0")
    kit = material["construction_kit"]
    binding = {"challenge_id": BATTERY, "challenge_version": "2.0", **kit}
    assert (
        verify_direct_resource_policy(binding, material["construction_limits_document"])
        == kit["construction_limits_digest"]
    )
    with pytest.raises(RecipeRefused, match="construction_resource_policy"):
        verify_direct_resource_policy(binding, cbm.construction_limits_document())


def test_the_served_contract_registers_battery_2_0(bank):
    from carbon.reconstruction.served_recipe_contract import registered

    contract = registered(BATTERY, "2.0")
    assert contract.version == "2.0"
    assert contract.allowlist_digest == allowlist_module.load_served().digest


def _graph_recipe(version, steps):
    kit = construction_kit.construction_kit_for(version)
    return ConstructionRecipe.from_dict(
        {
            "schema": "carbon.construction-recipe.v1",
            "challenge": kit,
            "source": {"kind": "graph", "submission_digest": "sha256:" + "a" * 64},
            "procedure": {
                "entrypoint": None,
                "configuration": {"training": {"steps": steps, "batch_size": 8}},
                "train_use": {
                    "dataset": direct_graph.TRAIN_USE,
                    "train_fraction": 1.0,
                    "curriculum": "none",
                },
                "initial_state": None,
            },
            "output": {
                "format": direct_graph.OUTPUT_FORMAT,
                "interface_digest": kit["interface_digest"],
            },
        }
    )


def test_a_2_0_graph_recipe_may_declare_more_steps_than_the_old_cap():
    assert (
        direct_graph.training_settings(_graph_recipe("2.0", 30_000))["steps"] == 30_000
    )
    with pytest.raises(RecipeRefused, match="battery_graph_training_value_invalid"):
        direct_graph.training_settings(_graph_recipe("1.0", 30_000))
    with pytest.raises(RecipeRefused, match="battery_graph_training_value_invalid"):
        direct_graph.training_settings(_graph_recipe("2.0", 2))  # the low bound stays


def test_the_2_0_graph_limits_uncap_exactly_the_step_surfaces():
    old = construction_kit.construction_limits_document()
    new = construction_kit.construction_limits_document_for("2.0")
    assert (
        set(construction_kit.STEP_SURFACES)
        == direct_graph.UNCAPPED_STEP_SURFACES["2.0"]
    )
    for name, surface in new["train_surfaces"].items():
        if name in construction_kit.STEP_SURFACES:
            assert surface["high"] is None and old["train_surfaces"][name]["high"]
        else:
            assert surface == old["train_surfaces"][name]
    assert new["training_step_cap"] is None
    assert (
        construction_kit.construction_kit_for("1.0")
        == construction_kit.construction_kit()
    )
