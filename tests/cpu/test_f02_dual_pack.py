"""F02's dual-pack adapter on pack 2.0: the Validator's registered packet over
the existing native cold-eight reduction, with rung-envelope references."""

import copy
import functools
import json
import math

import pytest

from carbon.challenge_kit import f02_train, physical_pack
from carbon.scoring import design_fidelity, physical_adapters
from carbon.scoring import f02_dual_pack as adapter
from carbon.scoring import physical_dual_pack as physical

PLATFORM = {"inference_image_id": "sha256:" + "a" * 64, "device_class": "cpu"}


@functools.cache
def _bank():
    return physical_pack.development_bank(adapter.CHALLENGE, adapter.VERSION)


def _rows():
    return physical.bank_rows(_bank(), adapter.input_names())


def _definition():
    return adapter.definition(bank=_bank(), train_raw=b"")


def _primary():
    return [[row["record"]["rung_peaks_c"]["primary"]] for row in _rows()]


def _measure(outputs, repeats=None):
    return adapter.measure(
        bank_rows=_rows(),
        outputs=outputs,
        repeats=[outputs, outputs] if repeats is None else repeats,
        definition=_definition(),
        limits={},
        objective={},
        train_raw=b"",
        names=adapter.input_names(),
    )


def test_the_definition_is_the_registered_packet():
    definition = _definition()
    adapter.validate_definition(definition)
    # The exact computed spread (Validator ruling), not the rounded 6.701.
    assert definition["train_peak_std_c"] == 6.701245845436587
    assert (
        definition["train_peak_std_c"]
        == f02_train.load_public_train("2.0")["train_peak_std_c"]
    )
    assert definition["maximum_c"] == 95
    design_fidelity.validate_policy(definition["policy"])
    policy = definition["policy"]
    assert policy["objective"]["scale"] == {"value": 100.0, "unit": "J"}
    assert policy["objective"]["equivalence"] == {"value": 0.0, "unit": "J"}
    assert {c["id"]: c["scale"]["value"] for c in policy["components"]} == {
        "margin": 1.0,
        "response": 1.0,
    }
    # dev1 §2.3 from references alone: the closest margin on each side.
    assert {s["side"]: s["case_id"] for s in policy["coverage_slots"]} == {
        "nonnegative": "cool-rect-near-85w",
        "negative": "cool-rect-near-86w",
    }
    assert definition["paired_repeat"]["tolerance_ulp"] == 0


def test_each_reference_is_its_rung_envelope_bound_to_the_judgement():
    truth = adapter.reference(_rows())
    receipt = "sha256:" + physical_pack._F02_JUDGEMENT[1]
    for row in _rows():
        rungs = row["record"]["rung_peaks_c"]
        peak = truth["cases"][row["case_id"]]["peak_top_c"]
        margin = truth["cases"][row["case_id"]]["thermal_margin_c"]
        assert peak["value"] == rungs["primary"]
        assert (peak["interval"]["lower"], peak["interval"]["upper"]) == (
            min(rungs.values()),
            max(rungs.values()),
        )
        assert peak["interval"]["receipt"] == receipt
        assert margin["value"] == 95 - rungs["primary"]
        assert margin["interval"]["lower"] == 95 - peak["interval"]["upper"]
    feasible = sorted(
        k for k, a in truth["actions"].items() if a["feasibility"] == "FEASIBLE"
    )
    assert feasible == ["cool-rect-low", "cool-rect-near-84w", "cool-rect-near-85w"]


def test_a_model_equal_to_the_reference_earns_full_a_and_d():
    measured = _measure(_primary())
    assert measured["A"] == 1.0
    assert measured["D"] == 1.0
    assert measured["gates"] == {
        "finite_peak": True,
        "paired_repeat": True,
        "reference_acceptance": True,
        "verified_pick": True,
    }
    assert measured["decision_outcome"] == "VERIFIED_FEASIBLE"
    # The best feasible energy: 85 W for 5 s.
    assert measured["selected_action"] == "cool-rect-near-85w"
    assert measured["reduction"]["full_credit_eligible"] is True


def test_calling_86w_safe_picks_an_unsafe_action_and_fails_verified_pick():
    ids = [row["case_id"] for row in _rows()]
    optimistic = copy.deepcopy(_primary())
    optimistic[ids.index("cool-rect-near-86w")] = [94.9]
    measured = _measure(optimistic)
    assert measured["selected_action"] == "cool-rect-near-86w"
    assert measured["gates"]["verified_pick"] is False
    assert measured["D"] is None
    assert measured["A"] < 1.0


def test_a_nonfinite_peak_fails_its_gate_not_the_run():
    bad = copy.deepcopy(_primary())
    bad[0] = [math.inf]
    measured = _measure(bad)
    assert measured["gates"]["finite_peak"] is False
    assert (measured["A"], measured["D"]) == (None, None)


def test_a_repeat_that_differs_at_all_fails_the_paired_repeat():
    outputs = _primary()
    moved = copy.deepcopy(outputs)
    moved[2][0] = math.nextafter(moved[2][0], math.inf)
    measured = _measure(outputs, repeats=[outputs, moved])
    assert measured["gates"]["paired_repeat"] is False


def test_f02_dispatches_by_version_outside_every_producer_digest():
    assert physical_adapters.adapter("f02", "2.0") is adapter
    assert physical_adapters.adapter("f02", "1.0") is None
    assert "physical_adapters.py" not in adapter.FILES


def test_the_pack_physics_role_is_the_adapters_and_adopts_no_law():
    physics = physical_pack.physics_contract("f02", "2.0")
    assert physics == adapter.physics_contract()
    assert physics["definition"]["adopted_laws"] == []
    public = physical_pack.public_roles("f02", "2.0")
    assert json.loads(public["physics_contract"]) == physics


def test_each_reference_wall_time_is_its_measured_completed_primary_solve():
    # RR-04's own ledger (Data Collection, d81f8afa1); the shared core sums
    # these for the solver-speed benchmark. No stand-in is used anywhere.
    raw = (physical_pack._REPOSITORY / physical_pack._F02_LEDGER[0]).read_bytes()
    finished = {
        event["case"]: event
        for event in map(json.loads, raw.decode("utf-8").splitlines())
        if event.get("event") == "FINISHED"
    }
    image = json.loads(
        (physical_pack._REPOSITORY / physical_pack._F02_JUDGEMENT[0]).read_bytes()
    )["image"]
    for record in _bank()["reference_records"]:
        solve = finished[record["case_id"] + "-primary"]
        assert (solve["outcome"], solve["exit"], solve["reservation"]) == (
            "COMPLETED",
            0,
            "primary",
        )
        assert solve["image_pin"] == image == record["image"]
        assert record["wall_s"] == solve["wall_s"] > 0


def _documents(bank):
    public = physical_pack.public_roles("f02", "2.0")
    return adapter.pack_documents(
        bank=bank,
        physics=adapter.physics_contract(),
        interface_raw=public["interface"],
        train_raw=public["train"],
        limits_raw=public["important_limit_definition"],
        objective_raw=public["design_objective"],
        platform=PLATFORM,
        minimums="calibration",
    )


def test_a_reference_without_a_measured_wall_time_cannot_build_a_pack():
    planted = copy.deepcopy(_bank())
    del planted["reference_records"][3]["wall_s"]
    with pytest.raises(KeyError, match="wall_s"):
        _documents(planted)


def test_the_real_calibration_pack_builds_with_no_minimums():
    documents = _documents(_bank())
    pack = json.loads(documents["score_pack"])
    assert pack["hard_gates"] == list(adapter.GATES)
    assert pack["combination"] == "weighted_arithmetic_mean"
    assert all(leg["minimum"] is None for leg in pack["legs"].values())
    definition = json.loads(documents["accuracy_definition"])
    assert definition["leg_minimum_mode"] == "calibration"
    (row,) = json.loads(documents["reference_rows"])
    assert row["elapsed_s"] == sum(r["wall_s"] for r in _bank()["reference_records"])
    with pytest.raises(adapter.Refused) as refused:
        adapter.baseline_outputs([])
    assert refused.value.code == "f02_baseline_unregistered"
