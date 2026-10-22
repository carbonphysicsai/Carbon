"""Allowlist v7 on each Challenge's catalog version (Validator, 2026-10-20):
Cooling 1.2, Battery 2.1, F08 1.3, F02 2.2 and Motor 1.3 (Motor 1.2 plus v7)
serve v7 with step-2 serving (no fixed training-step caps). Motor 1.3, whose
entries are tested, and Cooling 1.2 (owner priority via the Test Lead; its
catalog is empty until a Cooling entry is tested) also serve the backbone
catalog. F08 1.4 and F02 2.3 (the Validator, 2026-10-20) serve v7, the catalog
binding (no entries yet) and Carbon's graph training adapter
(tests/cpu/test_f08_f02_graph_adapters.py). Every earlier version keeps its
bytes and its allowlist.

Exam banks and pack labels are Data Collection's and grading versions the
Test Engineer's; a stand-in Battery bank here checks only this lane's wiring.
"""

from __future__ import annotations

import numpy as np
import pytest

from carbon.backbone_catalog import pipeline, served
from carbon.battery import construction_bundle_material as cbm
from carbon.battery import construction_kit, direct_graph
from carbon.challenge_kit import (
    f02_public,
    f02_train,
    f08_public,
    f08_train,
    physical_material,
    physical_public,
)
from carbon.challenge_kit import served_versions as sv
from carbon.level4 import allowlist as allowlist_module

MOTOR, COOLING, F08, F02, BATTERY = sv.MOTOR, sv.COOLING, sv.F08, sv.F02, sv.BATTERY
#: Each catalog version and the step-2 version it carries forward.
PREDECESSOR = {
    (MOTOR, "1.3"): "1.2",
    (COOLING, "1.2"): "1.1",
    (F08, "1.3"): "1.2",
    (F02, "2.2"): "2.1",
    (BATTERY, "2.1"): "2.0",
}
#: The graph versions (the Validator, 2026-10-20), each 1.3 / 2.2 plus the
#: catalog binding and the graph adapter.
GRAPH = {(F08, "1.4"): "1.3", (F02, "2.3"): "2.2", (COOLING, "1.3"): "1.2"}
#: Battery 2.2 (the Validator, 2026-10-22): 2.1 plus the catalog binding only
#: (tests/cpu/test_battery_catalog_version.py).
CATALOG_ONLY = {(BATTERY, "2.2"): "2.1"}


def _digest(raw):
    return allowlist_module.Allowlist(raw).digest


def test_exactly_the_catalog_versions_serve_v7_and_nothing_else_moves():
    v7 = allowlist_module.v7_bytes()
    assert sv.V7 == frozenset(PREDECESSOR) | frozenset(GRAPH) | frozenset(CATALOG_ONLY)
    for key, before in (GRAPH | CATALOG_ONLY).items():
        assert sv.material_allowlist_bytes(*key) == v7
        assert sv.material_allowlist_bytes(key[0], before) == v7
    for key, before in PREDECESSOR.items():
        assert sv.material_allowlist_bytes(*key) == v7
        assert sv.is_step2(*key) and not sv.step_caps(*key)
        # The version each carries forward keeps v6.
        assert sv.material_allowlist_bytes(key[0], before) == (
            allowlist_module.served_bytes()
        )
    for key in sv.STEP2 | sv.EXISTING | {(MOTOR, "1.2")}:
        assert sv.material_allowlist_bytes(*key) != v7
        assert not sv.serves_v7(*key)


def test_only_motor_1_3_cooling_1_2_and_the_graph_versions_serve_the_catalog():
    assert {key for key in sv.V7 if sv.serves_catalog(*key)} == {
        (MOTOR, "1.3"),
        (COOLING, "1.2"),
        *GRAPH,
        *CATALOG_ONLY,
    }
    assert cbm.versioned_material("2.2")["construction_limits_document"][
        "backbone_catalog"
    ]["digest"] == served.digest(BATTERY, "2.2")
    for key in ((MOTOR, "1.3"), (COOLING, "1.2")):
        limits = physical_public.construction_limits_document(*key)
        assert limits["backbone_catalog"]["digest"] == served.digest(*key)
    # Cooling 1.1 keeps its bytes: no catalog.
    assert "backbone_catalog" not in physical_public.construction_limits_document(
        COOLING, "1.1"
    )
    # 1.3 offers every 1.2 entry, plus the jNO entries (python-cpu-py311) and
    # the six cleaned DeepXDE/THUML coverage entries (torch-cpu-py311).
    on_1_2 = {e["catalog_id"] for e in pipeline.entries(MOTOR, "1.2")}
    on_1_3 = {e["catalog_id"]: e for e in pipeline.entries(MOTOR, "1.3")}
    assert on_1_2 < set(on_1_3)
    assert {
        e["bundle_ref"]["runtime_profile_id"]
        for name, e in on_1_3.items()
        if name not in on_1_2
    } == {"python-cpu-py311", "torch-cpu-py311"}
    # Cooling 1.2 offers its own Cooling-tested entries; every other v7
    # version offers none yet.
    assert {e["catalog_id"] for e in pipeline.entries(COOLING, "1.2")} == {
        "cooling.neuralop.FNO",
        "cooling.neuralop.TFNO",
        "cooling.neuralop.UQNO",
        "cooling.physicsnemo.FullyConnected",
        "cooling.transolver",
    }
    # F08 1.4 and F02 2.3 offer their float32 builds: the first five from the PX14 pair batch, and the
    # ports added since (each with its own pair receipt), all under their own f08./f02. ids.
    f08 = {e["catalog_id"] for e in pipeline.entries("f08-ribbed-bracket", "1.4")}
    assert {
        "f08.neuralop.FNO",
        "f08.neuralop.TFNO",
        "f08.neuralop.UQNO",
        "f08.physicsnemo.FullyConnected",
        "f08.transolver",
    } <= f08
    assert all(name.startswith("f08.") for name in f08)
    f02 = {e["catalog_id"] for e in pipeline.entries("f02", "2.3")}
    assert "f02.physicsnemo.FullyConnected" in f02
    assert all(name.startswith("f02.") for name in f02)
    # Cooling 1.3 (encoded outputs) offers the five baselines re-tested on it (pair-identity C13).
    assert {e["catalog_id"] for e in pipeline.entries(COOLING, "1.3")} == {
        "cooling13.neuralop.FNO",
        "cooling13.neuralop.TFNO",
        "cooling13.neuralop.UQNO",
        "cooling13.physicsnemo.FullyConnected",
        "cooling13.transolver",
    }
    for challenge_id, version in sv.V7 - {
        (MOTOR, "1.3"),
        (COOLING, "1.2"),
        (COOLING, "1.3"),
        ("f08-ribbed-bracket", "1.4"),
        ("f02", "2.3"),
    }:
        assert pipeline.entries(challenge_id, version) == []


@pytest.mark.parametrize("key", [(MOTOR, "1.3"), (COOLING, "1.2")])
def test_motor_and_cooling_catalog_kits_differ_only_in_their_version(key):
    before = PREDECESSOR[key]
    new = physical_public.construction_limits_document(*key)
    old = physical_public.construction_limits_document(key[0], before)
    assert new["challenge"]["version"] == key[1]
    new.pop("backbone_catalog", None)
    old.pop("backbone_catalog", None)
    new["challenge"]["version"] = before
    assert new == old
    assert physical_material.is_registered(*key)
    material = physical_material.bundle_material(*key)
    assert material["allowlist_bytes"] == allowlist_module.v7_bytes()
    assert material["allowlist_digest"] == _digest(allowlist_module.v7_bytes())
    assert material["construction_kit"] == physical_public.construction_kit(*key)
    assert material["construction_kit"]["train_digest"] == (
        physical_public.construction_kit(key[0], before)["train_digest"]
    )


@pytest.mark.parametrize(
    "public, train, key",
    [(f08_public, f08_train, (F08, "1.3")), (f02_public, f02_train, (F02, "2.2"))],
)
def test_f08_and_f02_catalog_kits_serve_their_predecessors_train(public, train, key):
    before = PREDECESSOR[key]
    assert train.load_public_train(key[1])["train"] == (
        train.load_public_train(before)["train"]
    )
    new = public.construction_limits_document(*key)
    old = public.construction_limits_document(key[0], before)
    assert new["training_step_cap"] is None
    new["challenge"]["version"] = before
    assert new == old
    kit = public.construction_kit(*key)
    assert kit["version"] == key[1]
    assert (
        kit["train_digest"] == public.construction_kit(key[0], before)["train_digest"]
    )


def test_every_catalog_version_is_receivable_with_its_pack():
    # Validator, 2026-10-20: F02 2.1/2.2 and Battery 2.x are receivable too.
    for key in (
        (MOTOR, "1.3"),
        (COOLING, "1.2"),
        (F08, "1.3"),
        (F02, "2.1"),
        (F02, "2.2"),
    ):
        assert physical_material.is_registered(*key)


def test_motor_1_2_is_byte_for_byte_unchanged():
    # Offering the entries on 1.3 too leaves 1.2's served catalog alone.
    assert served.document(MOTOR, "1.2")["challenge"]["version"] == "1.2"
    assert sv.material_allowlist_bytes(MOTOR, "1.2") == allowlist_module.served_bytes()
    limits = physical_public.construction_limits_document(MOTOR, "1.2")
    assert limits["backbone_catalog"]["digest"] == served.digest(MOTOR, "1.2")
    assert served.digest(MOTOR, "1.2") != served.digest(MOTOR, "1.3")


# --- Battery 2.1 -------------------------------------------------------------------


@pytest.fixture
def bank(monkeypatch):
    """Battery 2.1's bank is Data Collection's label; a stand-in (1.0's 200
    practice rows, one absent probe row) checks only the wiring."""
    from carbon.challenge_kit import physical_pack

    v1 = cbm.bundle_material()
    width = v1["practice_reference"].shape[1]
    stand_in = {
        "case_ids": tuple(v1["practice_case_ids"]) + ("p0-base",),
        "cohorts": ("practice",) * len(v1["practice_case_ids"]) + ("probe",),
        "inputs": np.vstack([v1["practice_inputs"], v1["practice_inputs"][:1]]),
        "references": np.vstack(
            [v1["practice_reference"], np.full((1, width), np.nan)]
        ),
        "reference_present": (True,) * len(v1["practice_case_ids"]) + (False,),
    }
    asked = []

    def development_bank(challenge_id, version):
        asked.append((challenge_id, version))
        return stand_in

    monkeypatch.setattr(physical_pack, "development_bank", development_bank)
    return asked


def test_battery_2_1_serves_its_own_bank_label_with_v7(bank):
    material = cbm.versioned_material("2.1")
    assert bank == [(BATTERY, "2.1")]
    assert material["challenge_key"].version == "2.1"
    assert material["construction_kit"]["version"] == "2.1"
    assert material["allowlist_bytes"] == allowlist_module.v7_bytes()
    limits = material["construction_limits_document"]
    assert limits["challenge"]["version"] == "2.1"
    assert limits["training_step_cap"] is None
    # 2.0 is served as before: its own label, v6.
    old = cbm.versioned_material("2.0")
    assert bank[-1] == (BATTERY, "2.0")
    assert old["allowlist_bytes"] == allowlist_module.served_bytes()
    assert old["construction_limits_document"]["challenge"]["version"] == "2.0"
    old_limits = dict(old["construction_limits_document"])
    old_limits["challenge"] = {**old_limits["challenge"], "version": "2.1"}
    assert old_limits == limits


def test_battery_2_1_graphs_validate_against_v7_with_2_0s_uncapped_steps():
    assert direct_graph.graph_allowlist("2.1").digest == _digest(
        allowlist_module.v7_bytes()
    )
    assert direct_graph.graph_allowlist("2.0").digest == (
        allowlist_module.load_served().digest
    )
    assert direct_graph.UNCAPPED_STEP_SURFACES["2.1"] == (
        direct_graph.UNCAPPED_STEP_SURFACES["2.0"]
    )
    new = construction_kit.construction_limits_document_for("2.1")
    old = construction_kit.construction_limits_document_for("2.0")
    assert new["challenge"]["version"] == "2.1"
    new["challenge"] = old["challenge"]
    # 2.1 differs from 2.0 only by its v7 caps and intake bounds (no
    # model-size caps; tests/cpu/test_launchpad_v7_version_caps.py).
    for key in ("graph_caps", "graph_intake"):
        new[key] = old[key]
    assert new == old
    assert construction_kit.construction_kit_for("2.1")["version"] == "2.1"


def test_the_served_contracts_register_each_catalog_version(bank):
    from carbon.reconstruction.served_recipe_contract import registered

    v7 = _digest(allowlist_module.v7_bytes())
    for key in ((MOTOR, "1.3"), (COOLING, "1.2"), (F08, "1.3"), (BATTERY, "2.1")):
        contract = registered(*key)
        assert (contract.challenge_id, contract.version) == key
        assert contract.allowlist_digest == v7


# --- Motor 1.3 on the Launchpad path ------------------------------------------------


def test_motor_1_3_is_its_own_catalog_campaign():
    from carbon.challenge_registry import campaigns, describe
    from carbon.challenge_registry.motor import catalog_recipe
    from carbon.motor import campaign

    assert campaign.CATALOG_VERSIONS == ("1.2", "1.3")
    document = describe(MOTOR, "1.3")
    assert document["identity"] == "carbon.electric-motor-magnetics-catalog.1.3"
    recipe = catalog_recipe(version="1.3")
    assert recipe["challenge"] == physical_public.construction_kit(MOTOR, "1.3")
    assert recipe["source"]["catalog_digest"] == served.digest(MOTOR, "1.3")
    built = campaigns._versioned_campaigns()
    assert {key[1] for key in built if key[0] == MOTOR} == {"1.2", "1.3"}
    assert built[(MOTOR, "1.3")]().key.version == "1.3"
    assert built[(MOTOR, "1.2")]().key.version == "1.2"
    with pytest.raises(ValueError, match="motor catalog version"):
        campaigns._motor_catalog("1.1")


def test_motor_1_3_material_serves_its_own_catalog():
    from carbon.motor.research import MotorCatalogMaterial

    assert MotorCatalogMaterial(".", "1.3").VERSION == "1.3"
    assert MotorCatalogMaterial(".").VERSION == "1.2"
    with pytest.raises(ValueError, match="motor catalog version"):
        MotorCatalogMaterial(".", "1.0")


@pytest.mark.parametrize(
    "challenge, accepted",
    [
        ({"id": BATTERY, "version": "1.0"}, True),
        ({"id": BATTERY, "version": "2.0"}, True),
        ({"id": BATTERY, "version": "2.1"}, True),
        ({"id": BATTERY, "version": "3.0"}, False),
        ({"id": F02, "version": "2.1"}, True),
        ({"id": F02, "version": "2.2"}, True),
        ({"id": F02, "version": "2.9"}, False),
    ],
)
def test_the_receiver_selects_every_served_battery_and_f02_version(
    tmp_path, monkeypatch, challenge, accepted
):
    from test_direct_receiver import _config

    from carbon.challenge_validator import direct_receiver as receiver

    cfg = {**_config(tmp_path), "challenge": challenge}
    monkeypatch.setattr(receiver, "private_json", lambda _: cfg)
    if accepted:
        assert receiver.load_config(tmp_path / "config.json") == cfg
    else:
        with pytest.raises(ValueError, match="registered direct Challenge"):
            receiver.load_config(tmp_path / "config.json")


def test_the_bundle_worker_trusts_each_served_allowlist_and_nothing_else():
    # A v7 version's material carries v7: its bundle builds, inference and paired
    # inference must accept exactly those bytes (bundle_allowlist_unregistered
    # refused every Motor 1.3 / Cooling 1.2 build before).
    from carbon.development_session.bundle_construction_worker import (
        _trusted_allowlist,
    )
    from carbon.development_session.construction_recipe import RecipeRefused

    for key in sv.V7:
        raw = sv.material_allowlist_bytes(*key)
        assert _trusted_allowlist(raw).digest == _digest(raw)
    assert _trusted_allowlist(allowlist_module.served_bytes())
    with pytest.raises(RecipeRefused, match="bundle_allowlist_unregistered"):
        _trusted_allowlist(allowlist_module.v7_bytes() + b" ")
