"""PLT-16: content derivation, closed openings, commitment and shadow evidence."""

import copy
import json
from types import SimpleNamespace

import pytest

from carbon.battery.unified_contract import contract
from carbon.development_ladder import operate
from carbon.development_ladder.unified_shadow import Observer, compare
from carbon.development_session import unified_construction as u


@pytest.fixture
def unified():
    return contract()


def strategy(unified, **parameters):
    return {
        "schema_version": "1.0",
        "challenge_id": unified.document["challenge"],
        "backbone": "mlp",
        "parameters": {"steps": 48, "width": 16, "depth": 1, **parameters},
    }


def selection(unified):
    field = unified.document["types"][1]["fields"]["pool_selection"]
    return {
        "pool_version": next(iter(field["low"]["versions"])),
        "strata": {"train": 1.0},
        "cases": 120,
    }


CASES = [
    ({}, 0, None),
    ({"loss_expressions": {"term": "sq_error"}}, 1, None),
    ({"loss_expressions": {"op": "neg", "arg": {"term": "sq_error"}}}, 1, "signed"),
    ({"muon_spectral": True, "optimizer_family": "muon"}, 2, None),
    ({"quasi_newton_family": "ssbfgs", "polish_steps": 2}, 3, None),
    ({"line_search": "none", "polish_steps": 2}, 3, None),
    ({"composition_graphs": "sha256:" + "a" * 64}, 4, None),
]


@pytest.mark.parametrize("parameters,label,arm", CASES)
def test_derived_labels_and_canonical_arm(unified, parameters, label, arm):
    value = strategy(unified, **parameters)
    original = copy.deepcopy(value)
    bound = u.derive(value, unified)
    assert bound["derived_label"] == label
    if label:
        assert next(iter(bound["arms"].values()))["arm"] == arm
        preview = u.classify(value, unified)
        assert preview["refusal"] == "construction_beyond_ceiling"
        assert preview["binding"] == bound
    else:
        assert bound["change_set"] == []
        assert u.classify(value, unified)["refusal"] is None
    assert value == original
    assert u.derive(json.dumps(value), unified) == bound


def test_pool_selection_cannot_be_mislabeled_as_base(unified):
    value = strategy(unified, pool_selection=selection(unified))
    assert u.derive(value, unified)["derived_label"] == 2
    bad = selection(unified)
    bad["strata"] = {"practice": 1.0}
    assert (
        u.classify(strategy(unified, pool_selection=bad), unified)["refusal"]
        == "construction_unclassified"
    )


@pytest.mark.parametrize(
    "parameters",
    [
        {"muon_spectral": False},
        {"quasi_newton_family": "lbfgs", "line_search": "strong_wolfe"},
    ],
)
def test_explicit_defaults_are_level_zero(unified, parameters):
    assert u.derive(strategy(unified, **parameters), unified)["change_set"] == []
    value = strategy(unified, **parameters)
    value.update(backbone="fno", parameters=parameters)
    assert u.derive(value, unified)["change_set"] == []


@pytest.mark.parametrize(
    "parameters",
    [
        {"loss_expressions": None},
        {"muon_spectral": 1},
        {"muon_spectral": True},
        {"muon_spectral": True, "optimizer_family": "muon", "backend": "pytorch"},
        {
            "muon_spectral": True,
            "optimizer_family": "muon",
            "learning_rate_curve": "train_loss_plateau",
        },
        {"line_search": "none"},
        {"loss_expressions": {"term": "err_sq_t"}},
        {"loss_expressions": {"term": "sq_error"}, "h1_weight": 0.0},
        {
            "loss_expressions": {
                "op": "pow",
                "exponent": 10,
                "arg": {"term": "sq_error"},
            }
        },
        {"composition_graphs": "some/file"},
    ],
)
def test_malformed_or_inapplicable_widenings_refuse(unified, parameters):
    assert (
        u.classify(strategy(unified, **parameters), unified)["refusal"]
        == "construction_unclassified"
    )


def test_combinations_are_closed(unified):
    value = strategy(
        unified,
        muon_spectral=True,
        optimizer_family="muon",
        line_search="none",
        polish_steps=2,
    )
    assert (
        u.classify(value, unified)["refusal"] == "construction_combination_unregistered"
    )


@pytest.mark.parametrize("raw", [b'{"x":0,"x":1}', b'{"x":NaN}', b"\xff", b"[]", b"{}"])
def test_strict_inputs_refuse_without_echo(unified, raw):
    preview = u.classify(raw, unified)
    assert preview["binding"] is None and preview["refusal"]
    assert "x" not in preview["reason"]


def test_type_specific_health_opening_and_ceiling_refusals(unified):
    doc = unified.document
    doc["ceiling"] = 4
    row = doc["types"][2]
    row["within_ceiling"] = True
    internal = u.UnifiedContract(doc)
    value = strategy(unified, line_search="none", polish_steps=2)
    assert (
        u.classify(value, internal)["refusal"] == "construction_type_not_open:numerics"
    )
    # Synthetic contract facts only; shipped contract remains INTERNAL.
    row.update(open="EXTERNAL", owner_acceptance="OWNER-FIXTURE-ONLY")
    assert (
        u.classify(value, u.UnifiedContract(doc))["refusal"]
        == "construction_type_closed:numerics"
    )
    row["checks"][0]["status"] = "PASS"
    assert u.classify(value, u.UnifiedContract(doc))["refusal"] is None
    assert contract().document["ceiling"] is None


def test_unregistered_type_and_immutable_contract(unified):
    doc = unified.document
    row = doc["types"][2]
    row["arms"] = []
    row["registration_digest"] = u.digest(
        {k: row[k] for k in ("type", "label", "fields", "arms")}
    )
    missing = u.UnifiedContract(doc)
    assert (
        u.classify(strategy(unified, line_search="none", polish_steps=2), missing)[
            "refusal"
        ]
        == "construction_type_unregistered"
    )
    with pytest.raises(AttributeError):
        unified._raw = b"{}"
    doc["ceiling"] = 4
    assert unified.document["ceiling"] is None


def test_signed_attack_arm_remains_closed_under_type_opening(unified):
    doc = unified.document
    doc["ceiling"] = 4
    row = doc["types"][0]
    row.update(
        open="EXTERNAL", owner_acceptance="OWNER-FIXTURE-ONLY", within_ceiling=True
    )
    row["checks"][0]["status"] = "PASS"
    value = strategy(
        unified, loss_expressions={"op": "neg", "arg": {"term": "sq_error"}}
    )
    assert (
        u.classify(value, u.UnifiedContract(doc))["refusal"]
        == "construction_type_not_open:loss_expressions"
    )


@pytest.mark.parametrize("mutation", ["extra", "bounds", "profile", "pin"])
def test_bad_contract_fails_closed(unified, mutation):
    doc = unified.document
    if mutation == "extra":
        doc["unknown"] = True
    elif mutation == "bounds":
        doc["base_fields"]["steps"]["low"] = "unsafe"
    elif mutation == "profile":
        doc["types"][0]["arms"][0]["expression"]["max_nodes"] = False
    else:
        doc["types"][0]["registration_digest"] = "sha256:" + "0" * 64
    with pytest.raises(u.UnifiedRefused):
        u.UnifiedContract(doc)


def test_commitment_and_binding_pin_content_without_level(unified):
    value = strategy(unified)
    expected = u.digest(
        {
            "challenge": value["challenge_id"],
            "unified_digest": unified.digest,
            "canonical_strategy_digest": u.digest(value),
        }
    )
    assert u.commitment(value, unified) == expected
    assert u.commitment(json.dumps(value, indent=2), unified) == expected
    assert u.commitment(strategy(unified, steps=49), unified) != expected
    bound = u.derive(value, unified)
    assert u.verify_binding(value, unified, bound) == bound
    bound["derived_label"] = 4
    with pytest.raises(u.UnifiedRefused, match="construction_binding_mismatch"):
        u.verify_binding(value, unified, bound)
    bound["derived_label"] = False
    with pytest.raises(u.UnifiedRefused, match="construction_binding_mismatch"):
        u.verify_binding(value, unified, bound)
    doc = unified.document
    doc["version"] += ".next"
    assert u.commitment(value, u.UnifiedContract(doc)) != expected


def test_classifier_is_challenge_neutral(unified):
    from carbon.reconstruction import capability_registry as cr

    doc = unified.document
    doc.update(
        challenge=cr.BURGERS_CHALLENGE,
        base_contract_digest=cr.contract_digest(cr.BURGERS_CHALLENGE),
        families=["fno"],
        types=[],
    )
    other = u.UnifiedContract(doc)
    value = strategy(unified)
    assert u.classify(value, other)["refusal"] == "challenge_mismatch"
    value.update(
        challenge_id=cr.BURGERS_CHALLENGE, backbone="fno", parameters={"steps": 48}
    )
    assert u.classify(value, other)["label"] == 0


def test_shadow_requires_separate_artifact_receipts(unified):
    value = strategy(unified, line_search="none", polish_steps=2)
    arm = unified.document["types"][2]["arms"][0]
    receipt = compare(value, unified, arm["digest"])
    assert (
        receipt["status"] == "INCOMPLETE"
        and receipt["derivation_match"]
        and receipt["route_match"]
    )
    assert receipt["artifact_match"] is None
    # Synthetic opaque digests exercise receipt comparison, not physical validity.
    artifact = "sha256:" + "b" * 64
    assert (
        compare(
            value,
            unified,
            arm["digest"],
            legacy_artifact=artifact,
            unified_artifact=artifact,
        )["status"]
        == "MATCH"
    )
    assert (
        compare(
            value,
            unified,
            arm["digest"],
            legacy_artifact=artifact,
            unified_artifact="sha256:" + "c" * 64,
        )["status"]
        == "MISMATCH"
    )
    assert (
        compare(value, unified, arm["digest"], legacy_artifact=artifact)["status"]
        == "INCOMPLETE"
    )
    assert (
        compare(value, unified, unified.document["types"][1]["arms"][0]["digest"])[
            "status"
        ]
        == "MISMATCH"
    )


def test_observer_cannot_mutate_or_fail_legacy_compilation(unified, monkeypatch):
    sentinel = object()
    monkeypatch.setattr(operate, "compile_variant", lambda *a: sentinel)
    target = SimpleNamespace(ladder={"levels": [0, 1, 2, 3]})

    def bad_observer(value, pinned):
        value["parameters"]["steps"] = 99
        raise RuntimeError("fixture diagnostic sink unavailable")

    operate.setup(target, shadow=bad_observer)
    value = strategy(unified)
    assert target.development_compiler(value, "fixture") is sentinel
    assert value["parameters"]["steps"] == 48
    assert target.development_compiler.shadow_failures == 1
    records = []
    operate.setup(target, shadow=Observer(unified, records.append))
    assert (
        target.development_compiler(value, unified.document["base_contract_digest"])
        is sentinel
    )
    assert records[0]["status"] == "INCOMPLETE"
    assert "parameters" not in records[0]
    operate.setup(target)
    assert target.development_compiler(value, "fixture") is sentinel


@pytest.mark.parametrize("parameters,label,arm", CASES[1:-1])
def test_shadow_agrees_with_existing_child_compiler(
    unified, parameters, label, arm, monkeypatch
):
    pytest.importorskip("jax")
    from carbon.development_session import construction_level as cl

    found = cl.with_target(
        cl.resolve(unified.document["challenge"], label, arm),
        "http://127.0.0.1:9/fixture",
    )
    monkeypatch.setattr(
        cl,
        "READ_TARGET",
        lambda *a: {
            "served_contracts": [
                {"level": label, "variant": found["variant"], "digest": found["digest"]}
            ]
        },
    )
    cl._compiled.cache_clear()
    value = strategy(unified, **parameters)
    compiled = cl.compile_strategy(found, value)
    assert compiled["variant_digest"] == found["digest"]
    receipt = compare(value, unified, compiled["variant_digest"])
    assert receipt["derivation_match"] and receipt["route_match"]
    assert receipt["status"] == "INCOMPLETE"
