"""Public fixture identity and toy relation; no physical or official verdict."""

import hashlib
import io
import json
from copy import deepcopy
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.challenge_kit import synthetic_linear_field_2d as fixture
from carbon.development_session import research_carrier
from carbon.development_session.bundle_construction_worker import (
    verify_direct_resource_policy,
)
from carbon.development_session.construction_recipe import RecipeRefused
from carbon.level4.allowlist import Allowlist
from scripts.dev.score_lab.solver_benchmark import physics_contract_identity


def test_public_train_archive_is_pinned_and_only_two_numeric_members():
    raw = fixture.train_bytes()
    assert hashlib.sha256(raw).hexdigest() == fixture.TRAIN_SHA256
    with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
        assert set(archive.files) == {"inputs", "targets"}
        inputs, targets = archive["inputs"], archive["targets"]
    assert inputs.shape == targets.shape == (8, 8, 8, 1)
    assert inputs.dtype == targets.dtype == np.float32
    np.testing.assert_array_equal(targets, fixture.public_reference(inputs))
    assert np.count_nonzero(inputs) > 0


def test_public_practice_and_bundle_material_bind_existing_worker_abi():
    material = fixture.bundle_material()
    kit = material["construction_kit"]
    assert set(kit) == {
        "id",
        "version",
        "train_digest",
        "interface_digest",
        "construction_limits_digest",
    }
    assert kit["id"] == material["challenge_key"].challenge_id
    assert kit["version"] == material["challenge_key"].version
    assert kit["train_digest"] == "sha256:" + fixture.TRAIN_SHA256
    assert material["train"] == fixture.train_bytes()
    assert material["train_case_ids"] == tuple(
        f"synthetic-train-{index:02d}" for index in range(8)
    )
    assert material["example"].shape == (2, 8, 8, 1)
    assert material["practice_inputs"].shape == (2, 8, 8, 1)
    assert material["practice_case_ids"] == (
        "synthetic-practice-00",
        "synthetic-practice-01",
    )
    assert material["expected_output_shape"] == (2, 8, 8, 1)
    np.testing.assert_array_equal(
        material["practice_reference"],
        fixture.public_reference(material["practice_inputs"]),
    )
    assert material["allowlist_digest"] == Allowlist(material["allowlist_bytes"]).digest
    assert (
        material["physics_digest"]
        == physics_contract_identity(material["physics_contract"])["definition_digest"]
    )
    assert material["physics_contract"]["definition"]["hidden_evaluation"] is False
    assert material["construction_limits_document"]["live_eligible"] is False
    assert material["construction_limits_document"]["accuracy_gate"] is None
    assert material["resource_facts"]["train_archive_bytes"] == len(material["train"])
    assert (
        material["resource_facts"]["practice_input_bytes"]
        == material["practice_inputs"].nbytes
    )
    assert material["disclosure"]["hidden_evaluation"] is False
    assert material["disclosure"]["official_reference"] is False


def test_v3_material_is_prospective_and_reuses_exact_public_train():
    historical = fixture.bundle_material()
    prospective = fixture.bundle_material_v3()
    assert historical["challenge_key"].version == "1.0"
    assert prospective["challenge_key"].version == "1.1"
    assert historical["construction_kit"]["version"] == "1.0"
    assert prospective["construction_kit"]["version"] == "1.1"
    assert historical["allowlist_bytes"] == fixture.allowlist_v2_bytes()
    assert prospective["allowlist_bytes"] == fixture.allowlist_v3_bytes()
    assert historical["allowlist_digest"] != prospective["allowlist_digest"]
    assert historical["train"] == prospective["train"] == fixture.train_bytes()
    assert (
        historical["construction_kit"]["train_digest"]
        == prospective["construction_kit"]["train_digest"]
    )


def test_v4_layer_norm_policy_is_prospective_and_keeps_prior_material():
    v2 = fixture.bundle_material()
    v3 = fixture.bundle_material_v3()
    v4 = fixture.bundle_material_v4()
    assert [m["challenge_key"].version for m in (v2, v3, v4)] == ["1.0", "1.1", "1.2"]
    assert [m["allowlist_bytes"] for m in (v2, v3, v4)] == [
        fixture.allowlist_v2_bytes(),
        fixture.allowlist_v3_bytes(),
        fixture.allowlist_v4_bytes(),
    ]
    assert len({m["allowlist_digest"] for m in (v2, v3, v4)}) == 3
    assert v2["train"] == v3["train"] == v4["train"] == fixture.train_bytes()
    assert {m["construction_kit"]["train_digest"] for m in (v2, v3, v4)} == {
        v2["construction_kit"]["train_digest"]
    }


def test_v5_observed_math_and_graph_adapter_keep_prior_material():
    materials = [
        fixture.bundle_material(),
        fixture.bundle_material_v3(),
        fixture.bundle_material_v4(),
        fixture.bundle_material_v5(),
    ]
    assert [m["challenge_key"].version for m in materials] == [
        "1.0",
        "1.1",
        "1.2",
        "1.3",
    ]
    assert [m["allowlist_bytes"] for m in materials] == [
        fixture.allowlist_v2_bytes(),
        fixture.allowlist_v3_bytes(),
        fixture.allowlist_v4_bytes(),
        fixture.allowlist_v5_bytes(),
    ]
    assert len({m["allowlist_digest"] for m in materials}) == 4
    for field in (
        "train",
        "train_case_ids",
        "practice_case_ids",
        "interface_document",
        "physics_contract",
        "physics_digest",
    ):
        assert all(m[field] == materials[0][field] for m in materials)
    for field in ("practice_inputs", "practice_reference"):
        assert all(np.array_equal(m[field], materials[0][field]) for m in materials)
    assert {m["construction_kit"]["train_digest"] for m in materials} == {
        materials[0]["construction_kit"]["train_digest"]
    }
    assert all(
        m["construction_limits_document"]
        == materials[0]["construction_limits_document"]
        for m in materials[:3]
    )
    v5_limits = materials[3]["construction_limits_document"]
    assert (
        v5_limits["schema"] == "carbon.synthetic-linear-field-2d.construction-limits.v3"
    )
    assert (
        v5_limits["reconstruction_resource_policy"]
        == materials[2]["construction_limits_document"][
            "reconstruction_resource_policy"
        ]
    )
    assert v5_limits["accuracy_gate"] is None
    assert v5_limits["live_eligible"] is False
    assert materials[3]["construction_kit"][
        "construction_limits_digest"
    ] == fixture._digest(v5_limits)
    adapter = v5_limits["graph_training_adapter"]
    assert (
        adapter == fixture.construction_limits_document_v3()["graph_training_adapter"]
    )
    assert adapter["source_kind"] == "graph"
    assert adapter["train_use_dataset"] == "synthetic-linear-field-2d-public-train"
    assert adapter["id"] == "synthetic-linear-field-2d-public-jax-graph-v1"
    assert adapter["procedure_schema"] == "carbon.construction-recipe.v1"
    assert adapter["output_format"] == "carbon.numeric-graph.v1"
    assert adapter["state_schema"] == "carbon.development.graph-source-state.v1"
    assert "training" not in adapter

    old = json.loads(fixture.allowlist_v4_bytes())
    new = json.loads(fixture.allowlist_v5_bytes())
    assert "aten._softmax.default" not in old["aten_core"]
    assert "aten.sum.dim_IntList" not in old["aten_core"]
    assert new["aten_core"].pop("aten._softmax.default") == {
        "category": "reduction",
        "default": "allow",
        "lowering": "emitted",
        "note": "Stable reduction lowering for float32/float64 tensors; half_to_float is refused.",
    }
    assert new["aten_core"].pop("aten.sum.dim_IntList") == {
        "category": "reduction",
        "default": "allow",
        "lowering": "emitted",
        "note": "Static dimension-list reduction for float32/float64 tensors; unsupported arguments and dtypes are refused.",
    }
    for field in ("schema", "status", "version"):
        old.pop(field)
        new.pop(field)
    assert new == old


def test_v5_declared_graph_state_schema_matches_graph_source_header():
    from carbon.development_session import bundle_graph_state

    if not hasattr(bundle_graph_state, "_source_header"):
        pytest.skip("graph-source state is not yet integrated on the material branch")
    submission_digest = "sha256:" + "a" * 64
    recipe = SimpleNamespace(
        to_dict=lambda: {
            "source": {"kind": "graph", "submission_digest": submission_digest}
        }
    )
    header = bundle_graph_state._source_header(recipe)
    assert (
        header["schema"]
        == fixture.bundle_material_v5()["construction_limits_document"][
            "graph_training_adapter"
        ]["state_schema"]
    )
    assert header["submission_digest"] == submission_digest
    assert "bundle_digest" not in header


@pytest.mark.parametrize(
    "field,value",
    [
        ("cpu_count_max", 1),
        ("memory_bytes_max", 2 * 1024**3),
        ("total_reconstruction_wall_seconds_max", 1799),
    ],
)
def test_direct_resource_policy_refuses_changed_limits_even_with_matching_digest(
    field, value
):
    material = fixture.bundle_material()
    binding = material["construction_kit"]
    limits = material["construction_limits_document"]
    assert (
        verify_direct_resource_policy(binding, limits)
        == binding["construction_limits_digest"]
    )

    changed = deepcopy(limits)
    changed["reconstruction_resource_policy"][field] = value
    forged_binding = {
        **binding,
        "construction_limits_digest": fixture._digest(changed),
    }
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy(forged_binding, changed)


def test_direct_resource_policy_refuses_wrong_digest_or_unserved_worker(monkeypatch):
    material = fixture.bundle_material()
    binding = material["construction_kit"]
    limits = material["construction_limits_document"]
    with pytest.raises(
        RecipeRefused, match="construction_resource_policy_binding_invalid"
    ):
        verify_direct_resource_policy(
            {**binding, "construction_limits_digest": "sha256:" + "0" * 64},
            limits,
        )

    actual = deepcopy(
        research_carrier._worker_profile(
            None, "DIRECT_BUNDLE_PUBLIC_RECONSTRUCTION"
        ).body
    )
    actual["cpu"]["count"] = 1
    monkeypatch.setattr(
        research_carrier,
        "_worker_profile",
        lambda device, provenance: SimpleNamespace(body=actual),
    )
    with pytest.raises(RecipeRefused, match="construction_resource_policy_unserved"):
        verify_direct_resource_policy(binding, limits)


@pytest.mark.parametrize("defect", ["dtype", "shape", "nonfinite"])
def test_public_reference_refuses_invalid_input(defect):
    inputs = fixture.practice_inputs()
    if defect == "dtype":
        inputs = inputs.astype(np.float64)
    elif defect == "shape":
        inputs = inputs[:, :7]
    else:
        inputs[0, 0, 0, 0] = np.nan
    with pytest.raises(ValueError):
        fixture.public_reference(inputs)


def test_train_archive_rejects_changed_bytes_and_changed_relation(
    tmp_path, monkeypatch
):
    tampered = tmp_path / "train.npz"
    tampered.write_bytes(fixture.train_bytes() + b"x")
    monkeypatch.setattr(fixture, "TRAIN_PATH", tampered)
    with pytest.raises(ValueError, match="bytes differ"):
        fixture.train_bytes()

    inputs = fixture._public_train_inputs()
    np.savez(tampered, inputs=inputs, targets=inputs)
    monkeypatch.setattr(
        fixture, "TRAIN_SHA256", hashlib.sha256(tampered.read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError, match="tensor relation differs"):
        fixture.train_bytes()
