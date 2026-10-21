"""No model-size caps on the Challenge versions serving allowlist v7, in the
version binding and the served limits documents (owner, 2026-10-21; Validator,
VALIDATOR_NO_MODEL_SIZE_CAP_SPEC_20261021; survey rows 1-4, 10 and 13).

Claims tested:
- A v7 version's construction contract (`capability_registry.contract_for`)
  has no pure model-size maximum; its structural maxima stay. Every other
  version gets its Challenge's published contract, byte for byte.
- Battery's graph kit publishes `allowlist.caps_for` and `intake.bounds_for`
  of the version's graph allowlist: containment only on 2.1 (v7), the owner's
  CAPS and BOUNDS on 1.0 and 2.0, whose limits digests do not move.
- Battery 2.1's graph route validates under v7 and reads v7's intake bound;
  1.0 and 2.0 keep the owner's.
"""

from __future__ import annotations

import pytest

from carbon.battery import construction_kit, direct_graph, direct_graph_worker
from carbon.challenge_kit import served_versions as sv
from carbon.development_session.construction_recipe import (
    ConstructionRecipe,
    RecipeRefused,
)
from carbon.level4 import allowlist as allowlist_module
from carbon.level4 import intake
from carbon.reconstruction import capability_registry as cr

#: The published Battery contract's digest, pinned by the development
#: variants and compositions; it must not move.
BATTERY_CONTRACT_DIGEST = (
    "sha256:eb0241b5ab35d522b48ed0c9c13564ae826fe32616f3b620528e5e22eaef238e"
)
#: Battery's graph-kit limits digests before this change (1.0 and 2.0 keep them).
LIMITS_DIGESTS = {
    "1.0": "sha256:914a6ef3df99b0931f8127e81144077a51af6274671a2099b1bd95c025b1fe15",
    "2.0": "sha256:7a70b9c6c9467e17cdd8c8e6e18ab638f0f93f85e489479077a190383bb0b00b",
}
CONTRACT_CHALLENGES = (
    cr.BATTERY_CHALLENGE,
    cr.MOTOR_CHALLENGE,
    cr.COLD_PLATE_CHALLENGE,
)


def _versions(challenge, table):
    return sorted(v for c, v in table if c == challenge)


def test_the_capability_tokens_are_the_served_version_ids():
    assert (cr.BATTERY_CHALLENGE, cr.MOTOR_CHALLENGE, cr.COLD_PLATE_CHALLENGE) == (
        sv.BATTERY,
        sv.MOTOR,
        sv.COOLING,
    )


@pytest.mark.parametrize("challenge", CONTRACT_CHALLENGES)
def test_every_version_not_serving_v7_keeps_the_published_contract(challenge):
    others = sv.STEP2 | sv.EXISTING | sv.CATALOG
    for version in [None, "9.9", *_versions(challenge, others - sv.V7)]:
        item = cr.contract_for(challenge, version)
        assert item is cr.contract(challenge)
        assert cr.catalog_surfaces(challenge, version) == cr.catalog_surfaces(challenge)
    assert cr.contract(cr.BATTERY_CHALLENGE).digest == BATTERY_CONTRACT_DIGEST


def test_burgers_has_no_v7_version_and_keeps_its_contract():
    assert cr.contract_for(cr.BURGERS_CHALLENGE, "1.0") is cr.BURGERS_CONTRACT
    assert not any(c == cr.BURGERS_CHALLENGE for c, _ in sv.V7)


def test_size_and_structural_maxima_are_real_disjoint_bounded_fields():
    for challenge, names in cr.SIZE_MAXIMA.items():
        fields = cr.catalog_surfaces(challenge)
        structural = set(cr.STRUCTURAL_MAXIMA.get(challenge, {}))
        rows = cr.ROW_MAXIMA.get(challenge, frozenset())
        assert names and not names & structural and not (names | structural) & rows
        for name in names | structural | rows:
            group, kind, _low, high, _default, _ = fields[name]
            assert group == "model" and kind in ("uint", "float") and high is not None


def test_battery_2_1_has_no_model_size_maximum_and_keeps_the_structural_ones():
    published = cr.catalog_surfaces(cr.BATTERY_CHALLENGE)
    served = cr.catalog_surfaces(cr.BATTERY_CHALLENGE, "2.1")
    size = cr.SIZE_MAXIMA[cr.BATTERY_CHALLENGE]
    assert size == {
        "width",
        "depth",
        "deeponet_depth",
        "basis_functions",
        "trajectory_components",
    }
    assert set(served) == set(published)
    rows = cr.ROW_MAXIMA[cr.BATTERY_CHALLENGE]
    assert rows == {"neighbours"}
    train_cases = dict(cr.BATTERY_CONTRACT.envelope)["train_cases"]
    for name, row in served.items():
        if name in size | rows:
            assert row[3] == (None if name in size else train_cases)
            assert published[name][3] is not None
            assert row[:3] + row[4:] == published[name][:3] + published[name][4:]
        else:
            assert row == published[name], name
    # Structural: the 121-point grid's 61 Fourier modes, and KNN neighbours at
    # most the TRAIN rows a recipe can select (400), replacing <= 64.
    assert served["n_modes"][3] == 61
    assert published["neighbours"][3] == 64 and served["neighbours"][3] == 400
    item = cr.contract_for(cr.BATTERY_CHALLENGE, "2.1")
    assert item.version == "2.1" and item.document()["challenge"]["version"] == "2.1"
    assert item.digest != BATTERY_CONTRACT_DIGEST
    assert cr.contract(cr.BATTERY_CHALLENGE).digest == BATTERY_CONTRACT_DIGEST


@pytest.mark.parametrize(
    "challenge, version",
    [(cr.MOTOR_CHALLENGE, "1.3"), (cr.COLD_PLATE_CHALLENGE, "1.2")],
)
def test_motor_and_cooling_v7_have_no_uint_size_maximum_to_remove(challenge, version):
    # Motor's size bounds are a finite Level-0 menu (choices, kept); Cooling's
    # fields are the kernel ridge's calibration grid. Neither serves the Level-0
    # compiler on its v7 version; its catalog settings have no size cap.
    assert sv.serves_v7(challenge, version)
    assert cr.contract_for(challenge, version) is cr.contract(challenge)


def test_battery_kits_publish_their_versions_caps_and_intake_bounds():
    v7 = allowlist_module.Allowlist(allowlist_module.v7_bytes())
    new = construction_kit.construction_limits_document_for("2.1")
    assert new["graph_caps"] == allowlist_module.caps_for(v7)
    assert new["graph_caps"] == allowlist_module.UNCAPPED_CAPS
    assert "nodes_executed" not in new["graph_caps"]
    assert new["graph_intake"] == intake.bounds_for(v7) == intake.CONTAINMENT_BOUNDS
    old = construction_kit.construction_limits_document_for("2.0")
    assert old["train_surfaces"] == new["train_surfaces"]
    for document in (old, construction_kit.construction_limits_document()):
        assert document["graph_caps"] == allowlist_module.CAPS
        assert document["graph_intake"] == intake.BOUNDS
    for version, pinned in LIMITS_DIGESTS.items():
        assert (
            construction_kit.construction_kit_for(version)["construction_limits_digest"]
            == pinned
        )
    assert (
        construction_kit.construction_kit_for("2.1")["construction_limits_digest"]
        != construction_kit.construction_kit_for("2.0")["construction_limits_digest"]
    )


def test_battery_2_1_graphs_validate_and_take_intake_under_v7():
    v7 = allowlist_module.Allowlist(allowlist_module.v7_bytes())
    assert sv.serves_v7(sv.BATTERY, "2.1")
    assert direct_graph.GRAPH_ALLOWLISTS["2.1"] == "allowlist_v7.json"
    assert direct_graph.graph_allowlist("2.1").digest == v7.digest
    assert (
        allowlist_module.caps_for(direct_graph.graph_allowlist("2.1"))
        == allowlist_module.UNCAPPED_CAPS
    )
    assert (
        direct_graph.submission_bytes("2.1")
        == intake.CONTAINMENT_BOUNDS["submission_bytes"]
    )
    for version in ("1.0", "2.0"):
        assert (
            allowlist_module.caps_for(direct_graph.graph_allowlist(version))
            == allowlist_module.CAPS
        )
        assert (
            direct_graph.submission_bytes(version) == intake.BOUNDS["submission_bytes"]
        )
    with pytest.raises(
        RecipeRefused, match="battery_graph_challenge_version_unregistered"
    ):
        direct_graph.submission_bytes("1.1")


def _graph_recipe(version, steps=600):
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


def test_battery_2_1_training_settings_read_its_own_surfaces():
    assert direct_graph.training_settings(_graph_recipe("2.1", 30_000))["steps"] == (
        30_000
    )
    with pytest.raises(RecipeRefused, match="battery_graph_training_value_invalid"):
        direct_graph.training_settings(_graph_recipe("1.0", 30_000))


def test_the_1_0_worker_keeps_the_owner_envelope_bound(tmp_path):
    bound = intake.BOUNDS["submission_bytes"]
    with pytest.raises(RecipeRefused, match="battery_direct_envelope_invalid"):
        direct_graph_worker.staged_files(
            tmp_path,
            _graph_recipe("1.0"),
            b" " * (2 * bound + 1),
            seed=0,
            test_inputs={"cases": []},
        )
    # The fixed worker program reads the version's bound, not BOUNDS.
    assert 'intake.BOUNDS["submission_bytes"]' not in direct_graph_worker.PROGRAM
    assert "direct_graph.submission_bytes(" in direct_graph_worker.PROGRAM
