"""OWNER-COOLING-HOTSPOT-GATE-DROP-01, prospective Cooling 1.6 only.

The grading fixtures are synthetic, not solver qualification or an exam pack.
"""

from __future__ import annotations

import copy
import json

import pytest
from test_cooling_sealed_grading import (
    NAMES,
    PUBLIC,
    _full,
    _model,
    _sealed_bank,
    _truth,
    sealed_cells,
)

from carbon.backbone_catalog import carries
from carbon.challenge_kit import physical_material, version_registry
from carbon.challenge_registry import published_exam, registry
from carbon.cold_plate import domain, output_encoding
from carbon.development_session import graph_adapters
from carbon.scoring import (
    cooling_dual_pack,
    cooling_encoded_dual_pack,
    dev_grid,
    physical_dual_pack,
    pool_version,
    practice_grid,
)
from carbon.scoring import cooling_hotspot_dual_pack as corrected


@pytest.fixture(scope="module")
def probed():
    bank = _sealed_bank(probes=True)
    return {"bank": bank, "cells": _truth(sealed_cells(bank))}


def _definition(chosen, bank):
    return chosen.definition(bank=bank, train_raw=PUBLIC["train"])


def _measure(version, probed, predictor):
    chosen = practice_grid.adapter("cooling", version)
    values = _full(probed["bank"], probed["cells"], probe=predictor)
    outputs = output_encoding.encode_targets(values).tolist()
    return chosen.measure(
        bank_rows=physical_dual_pack.bank_rows(probed["bank"], NAMES),
        outputs=outputs,
        repeats=[outputs, outputs],
        definition=_definition(chosen, probed["bank"]),
        limits=json.loads(PUBLIC["important_limit_definition"]),
        objective=json.loads(PUBLIC["design_objective"]),
        train_raw=PUBLIC["train"],
        names=NAMES,
    )


def test_only_the_approved_response_pair_changes_and_old_definitions_stay_equal(probed):
    original = _definition(cooling_encoded_dual_pack, probed["bank"])
    expected = copy.deepcopy(original)
    response = expected["physics"]["response"]
    j = response["outputs"].index("rise_c")
    d = response["inputs"].index("hotspot_ratio")
    response["exponent"][j][d] = None
    response["sign_gates"] = [
        gate
        for gate in response["sign_gates"]
        if (gate["output"], gate["input"]) != ("rise_c", "hotspot_ratio")
    ]
    found = _definition(corrected, probed["bank"])
    corrected.validate_definition(found)
    assert found == expected
    assert _definition(cooling_encoded_dual_pack, probed["bank"]) == original
    assert original["physics"]["response"]["exponent"][j][d] is not None


def test_a_negative_hotspot_sensitivity_passes_the_remaining_law_gates(probed):
    registered = _model()
    index = domain.INPUTS.index("hotspot_ratio")
    low, high = domain.INPUT_BOUNDS["hotspot_ratio"]

    def reversed_hotspot(point):
        changed = list(point)
        changed[index] = low + high - point[index]
        return registered(changed)

    older = _measure("1.5", probed, reversed_hotspot)
    newer = _measure("1.6", probed, reversed_hotspot)
    assert older["gates"]["physics_laws"] is False
    assert older["physics_half"]["sign_gate_failed"] == ["rise_c~hotspot_ratio"]
    assert newer["gates"]["physics_laws"] is True
    assert newer["physics_half"]["sign_gate_failed"] == []
    assert newer["A_legs"]["A_acc"] == older["A_legs"]["A_acc"] == 1.0
    assert newer["A_legs"]["A_response"] > older["A_legs"]["A_response"]


def test_the_other_sign_gates_still_fail_a_wrong_flow_trend(probed):
    registered = _model()
    index = domain.INPUTS.index("flow_lpm_per_kw")
    low, high = domain.INPUT_BOUNDS["flow_lpm_per_kw"]

    def reversed_flow(point):
        changed = list(point)
        changed[index] = low + high - point[index]
        return registered(changed)

    newer = _measure("1.6", probed, reversed_flow)
    assert newer["gates"]["physics_laws"] is False
    assert "rise_c~flow_lpm_per_kw" in newer["physics_half"]["sign_gate_failed"]


def test_a_no_probe_definition_does_not_apply_the_hotspot_gate():
    bank = _sealed_bank()
    old = _definition(cooling_encoded_dual_pack, bank)
    assert "physics" not in old
    assert _definition(corrected, bank) == old


def test_practice_and_pool_share_the_new_module_with_new_evaluation_identities():
    development = dev_grid.adapter(corrected.CHALLENGE, "1.6")
    practice = practice_grid.adapter("cooling", "1.6")
    sealed = cooling_dual_pack.sealed_adapter("1.6")
    assert development._module is practice._module is sealed._module is corrected
    assert development.EVALUATION_VERSION == "cooling-dual-development-grid-v3"
    assert sealed.EVALUATION_VERSION == "cooling-pool-sealed-v2"
    assert sealed.POOL_GRADED is True
    assert getattr(practice, "POOL_GRADED", False) is False
    assert corrected.sealed_adapter("1.5") is None
    assert corrected.producer_digest() == physical_dual_pack.producer_digest(corrected)
    assert corrected.producer_digest() != cooling_encoded_dual_pack.producer_digest()
    entry = version_registry.entry(corrected.CHALLENGE, "1.6")
    assert entry.predecessor == "1.5"
    assert entry.sealed_evaluation == sealed.EVALUATION_VERSION
    assert all(
        not changed
        for changed in carries.require_identity_only(
            corrected.CHALLENGE, "1.6"
        ).values()
    )


def test_the_new_pool_version_stays_reserved_without_owner_constants():
    found = next(
        e
        for e in registry.entries()
        if (e.challenge_id, e.version) == (corrected.CHALLENGE, "1.6")
    )
    assert found.status == registry.RESERVED
    assert published_exam.registered_pool(corrected.CHALLENGE, "1.6") is None
    for call in (
        pool_version.registered_policies,
        pool_version.registered_a_multiplier,
    ):
        with pytest.raises(
            pool_version.PoolConstantsNotRegistered,
            match="pool_constants_not_registered",
        ):
            call(corrected.CHALLENGE, "1.6")


def test_public_kit_and_graph_recipe_keep_the_same_train_interface_and_adapter():
    cid = corrected.CHALLENGE
    old = physical_material.construction_kit(cid, "1.5")
    new = physical_material.construction_kit(cid, "1.6")
    assert new["train_digest"] == old["train_digest"]
    assert new["interface_digest"] == old["interface_digest"]
    module = graph_adapters.for_version(cid, "1.6")
    assert module is graph_adapters.for_version(cid, "1.5")
    before, after = module.spec_for(cid, "1.5"), module.spec_for(cid, "1.6")
    assert after.predecessor == "1.5"
    assert {
        name: getattr(after, name)
        for name in after.__dataclass_fields__
        if name not in {"version", "predecessor"}
    } == {
        name: getattr(before, name)
        for name in before.__dataclass_fields__
        if name not in {"version", "predecessor"}
    }
    recipe = graph_adapters.graph_recipe(cid, "1.6")
    assert recipe["challenge"] == new
    assert recipe["procedure"]["train_use"]["dataset"] == before.train_use


def test_the_published_change_is_versioned_and_exposes_no_new_constant():
    old = published_exam.for_version(corrected.CHALLENGE, "1.5")
    new = published_exam.for_version(corrected.CHALLENGE, "1.6")
    assert "hotspot ratio" in old["physics_laws"]["sign_laws"][0]
    assert "hotspot ratio" not in new["physics_laws"]["sign_laws"][0]
    assert new["scoring_version"] == "cooling-pool-sealed-v2"
    assert new["limits"] == old["limits"]
    assert new["gates"] == old["gates"]
    assert new["score"]["formula"] == old["score"]["formula"]
