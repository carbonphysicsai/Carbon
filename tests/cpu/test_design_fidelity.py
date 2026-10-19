"""Product-run toy tests only; no Challenge physics, model or reference solver."""

import json
from copy import deepcopy

import pytest

from carbon.scoring import design_fidelity as REDUCER


def atom(value, unit="W", interval=True):
    return {
        "status": "RESOLVED",
        "value": value,
        "unit": unit,
        "interval": (
            {
                "lower": value,
                "upper": value,
                "unit": unit,
                "receipt": "TOY_ONLY_SOURCE_ACCEPTANCE",
            }
            if interval
            else None
        ),
    }


def pred(value, unit="W"):
    return {"value": value, "unit": unit}


def fixture():
    policy = {
        "id": "TOY_ONLY_NOT_A_CHALLENGE_RULE",
        "case_ids": ["c0", "c1"],
        "action_ids": ["a", "b"],
        "quantities": {
            "margin": {"unit": "W", "learned": True},
            "objective": {"unit": "W", "learned": True},
        },
        "objective": {
            "quantity": "objective",
            "unit": "W",
            "direction": "MINIMIZE",
            "scale": {"value": 1.0, "unit": "W"},
            "learned": True,
            "equivalence": {"value": 0.0, "unit": "W"},
        },
        "components": [
            {
                "id": "margin",
                "kind": "margin",
                "quantity": "margin",
                "unit": "W",
                "scale": {"value": 1.0, "unit": "W"},
                "cases": ["c0", "c1"],
                "pairs": [],
            },
            {
                "id": "response",
                "kind": "response",
                "quantity": "margin",
                "unit": "W",
                "scale": {"value": 1.0, "unit": "W"},
                "cases": [],
                "pairs": [["c0", "c1"]],
            },
            {
                "id": "gap",
                "kind": "gap",
                "quantity": "objective",
                "unit": "W",
                "scale": {"value": 1.0, "unit": "W"},
                "cases": [],
                "pairs": [["a", "b"]],
            },
        ],
        "coverage_slots": [
            {
                "id": "context:positive",
                "component": "margin",
                "case_id": "c0",
                "side": "nonnegative",
                "max_distance": {"value": 1.0, "unit": "W"},
                "structural_na_receipt": None,
            },
            {
                "id": "context:negative",
                "component": "margin",
                "case_id": "c1",
                "side": "negative",
                "max_distance": {"value": 1.0, "unit": "W"},
                "structural_na_receipt": None,
            },
        ],
    }
    reference = {
        "cases": {"c0": {"margin": atom(0.1)}, "c1": {"margin": atom(-0.1)}},
        "actions": {
            "a": {"feasibility": "FEASIBLE", "objective": atom(1.0)},
            "b": {"feasibility": "FEASIBLE", "objective": atom(2.0)},
        },
    }
    model = {
        "artifact_digest": "toy-model",
        "selected_action": "a",
        "cases": {"c0": {"margin": pred(0.1)}, "c1": {"margin": pred(-0.1)}},
        "actions": {"a": {"objective": pred(1.0)}, "b": {"objective": pred(2.0)}},
    }
    return policy, reference, model


def result(policy, reference, model):
    return REDUCER.reduce_design(policy, reference, [model])["models"][0]


def test_correct_pick_wrong_margin_loses_credit():
    policy, reference, model = fixture()
    model["cases"]["c0"]["margin"] = pred(1.1)
    row = result(policy, reference, model)
    assert row["V"]["V"] == 1.0
    assert row["C"] < 1.0 and row["registered_D"] < 1.0
    assert row["candidate_issues"] == []


@pytest.mark.parametrize("error,expected", [(0.0, 1.0), (1.0, 0.5)])
def test_zero_and_scale_errors(error, expected):
    policy, reference, model = fixture()
    for key in model["cases"]:
        model["cases"][key]["margin"]["value"] += error
    row = result(policy, reference, model)
    assert row["critical_components"]["margin"]["benefit"] == pytest.approx(expected)
    assert row["critical_components"]["response"]["benefit"] == pytest.approx(1.0)


def test_accepted_intervals_allow_resolution_without_demanding_exact_point():
    policy, reference, model = fixture()
    reference["cases"]["c0"]["margin"]["interval"].update(lower=0.0, upper=0.2)
    model["cases"]["c0"]["margin"]["value"] = 0.15
    row = result(policy, reference, model)
    error = row["critical_components"]["margin"]["rows"][0]
    assert error["absolute_point_error"] > 0
    assert error["effective_error"] == 0
    assert row["registered_D"] == 1.0
    assert row["D_bounds"][0] < row["D_bounds"][1]


def test_point_only_reference_retains_numeric_partial_d_without_candidate_penalty():
    policy, reference, model = fixture()
    reference["cases"]["c0"]["margin"]["interval"] = None
    row = result(policy, reference, model)
    assert row["point_estimate_D"] == 1.0
    assert row["registered_D"] is None
    assert row["status"] == "PARTIAL_DIAGNOSTIC"
    assert not row["full_credit_eligible"] and row["candidate_issues"] == []


def test_reference_missing_and_candidate_missing_are_separate():
    policy, reference, model = fixture()
    missing_reference = deepcopy(reference)
    del missing_reference["cases"]["c1"]
    row = result(policy, missing_reference, model)
    assert row["registered_D"] is None and row["candidate_issues"] == []
    del model["cases"]["c1"]
    row = result(policy, reference, model)
    assert row["status"] == "CANDIDATE_INVALID"
    assert row["registered_D"] is None
    assert "CANDIDATE_COMMON_CASE_MASK_MISMATCH" in row["candidate_issues"]


@pytest.mark.parametrize("where", ["candidate", "reference"])
def test_nonfinite_is_typed_and_result_remains_json(where):
    policy, reference, model = fixture()
    target = model["cases"] if where == "candidate" else reference["cases"]
    target["c0"]["margin"]["value"] = float("nan")
    row = result(policy, reference, model)
    assert row["registered_D"] is None
    assert bool(row["candidate_issues"]) == (where == "candidate")
    json.dumps(row, allow_nan=False)


def test_wrong_gap_and_response_receive_continuous_loss():
    policy, reference, model = fixture()
    model["actions"]["b"]["objective"]["value"] = 3.0
    model["cases"]["c1"]["margin"]["value"] = -1.1
    row = result(policy, reference, model)
    assert row["critical_components"]["gap"]["benefit"] == pytest.approx(0.5)
    assert row["critical_components"]["response"]["benefit"] == pytest.approx(0.5)
    assert row["registered_D"] == pytest.approx(0.5)


def test_analytic_mass_or_energy_does_not_increase_c():
    policy, reference, model = fixture()
    baseline = result(policy, reference, model)
    policy["quantities"]["analytic_mass"] = {"unit": "kg", "learned": False}
    policy["components"].append(
        {
            "id": "mass",
            "kind": "resonance",
            "quantity": "analytic_mass",
            "unit": "kg",
            "scale": {"value": 1.0, "unit": "kg"},
            "cases": ["c0", "c1"],
            "pairs": [],
        }
    )
    row = result(policy, reference, model)
    assert row["C"] == baseline["C"]
    assert (
        row["critical_components"]["mass"]["status"]
        == "STRUCTURAL_NA_ANALYTIC_NO_CREDIT"
    )


@pytest.mark.parametrize("count", [0, 1])
def test_settled_zero_or_one_feasible_makes_gap_structural_na(count):
    policy, reference, model = fixture()
    for i, key in enumerate(("a", "b")):
        if i >= count:
            reference["actions"][key] = {"feasibility": "INFEASIBLE", "objective": None}
    policy["components"][2]["pairs"] = []
    row = result(policy, reference, model)
    assert (
        row["critical_components"]["gap"]["status"]
        == "STRUCTURAL_NA_FEWER_THAN_TWO_SETTLED_FEASIBLE"
    )
    if count == 0:
        assert row["V"]["status"] == "NONE_FEASIBLE_VALUE_NOT_MEASURED"
        assert row["registered_D"] is None


def test_unresolved_competitive_action_is_not_gap_na():
    policy, reference, model = fixture()
    reference["actions"]["b"] = {"feasibility": "UNRESOLVED", "objective": None}
    policy["components"][2]["pairs"] = []
    row = result(policy, reference, model)
    assert (
        row["critical_components"]["gap"]["status"]
        == "REFERENCE_UNRESOLVED_COMPETITIVE_ACTION"
    )
    assert row["registered_D"] is None and row["candidate_issues"] == []


def test_missing_side_or_far_side_is_partial_not_an_artificial_gate():
    policy, reference, model = fixture()
    policy["coverage_slots"][1]["case_id"] = None
    row = result(policy, reference, model)
    assert row["point_estimate_D"] == 1
    assert row["registered_D"] is None and row["candidate_issues"] == []
    policy["coverage_slots"][1]["case_id"] = "c1"
    policy["coverage_slots"][1]["max_distance"]["value"] = 0.01
    row = result(policy, reference, model)
    assert any("OUTSIDE_DECLARED_PROXIMITY" in x for x in row["reference_limitations"])


def test_scale_unit_mismatch_is_refused_without_adopting_a_conversion():
    policy, reference, model = fixture()
    policy["components"][0]["scale"]["unit"] = "V"
    with pytest.raises(REDUCER.ReductionRefused, match="scale_unit_mismatch"):
        result(policy, reference, model)


def test_reference_interval_units_do_not_become_candidate_fault():
    policy, reference, model = fixture()
    reference["cases"]["c0"]["margin"]["interval"]["unit"] = "V"
    row = result(policy, reference, model)
    assert row["registered_D"] is None and row["candidate_issues"] == []


def test_common_reference_mask_and_coverage_identical_across_models():
    policy, reference, first = fixture()
    second = deepcopy(first)
    second["artifact_digest"] = "second-toy"
    del reference["cases"]["c1"]
    report = REDUCER.reduce_design(policy, reference, [first, second])
    assert len(report["models"]) == 2
    assert (
        report["models"][0]["reference_limitations"]
        == report["models"][1]["reference_limitations"]
    )
    assert all(row["registered_D"] is None for row in report["models"])


def test_resonance_is_a_learned_level_component():
    policy, reference, model = fixture()
    policy["quantities"]["frequency"] = {"unit": "Hz", "learned": True}
    policy["components"].append(
        {
            "id": "resonance",
            "kind": "resonance",
            "quantity": "frequency",
            "unit": "Hz",
            "scale": {"value": 10.0, "unit": "Hz"},
            "cases": ["c0", "c1"],
            "pairs": [],
        }
    )
    for key in policy["case_ids"]:
        reference["cases"][key]["frequency"] = atom(100, "Hz")
        model["cases"][key]["frequency"] = pred(110, "Hz")
    row = result(policy, reference, model)
    assert row["critical_components"]["resonance"]["benefit"] == 0.5
    assert row["registered_D"] == 0.5


def test_value_regret_and_critical_min_preserve_original_inputs():
    policy, reference, model = fixture()
    model["selected_action"] = "b"
    original = deepcopy((policy, reference, model))
    row = result(policy, reference, model)
    assert row["V"]["regret"] == 1.0 and row["registered_D"] == 0.5
    assert (policy, reference, model) == original


def test_all_feasible_gap_pairs_are_required():
    policy, reference, model = fixture()
    policy["components"][2]["pairs"] = []
    with pytest.raises(
        REDUCER.ReductionRefused, match="gap_requires_every_settled_feasible_pair"
    ):
        result(policy, reference, model)


def test_candidate_invalid_remains_visible_with_reference_resolution_gap():
    policy, reference, model = fixture()
    reference["cases"]["c0"]["margin"]["interval"] = None
    model["cases"]["c1"]["margin"]["value"] = float("nan")
    row = result(policy, reference, model)
    assert row["status"] == "CANDIDATE_INVALID"
    assert row["candidate_status"] == "INVALID"
    assert row["reference_status"] == "PARTIAL_OR_UNRESOLVED"
    assert row["registered_D"] is None
    assert not any(
        "UNMEASURED_COMPONENT:response" in issue
        for issue in row["reference_limitations"]
    )


def test_candidate_missing_does_not_create_reference_gap():
    policy, reference, model = fixture()
    del model["cases"]["c1"]
    row = result(policy, reference, model)
    assert row["status"] == "CANDIDATE_INVALID"
    assert row["reference_limitations"] == []
    assert row["reference_status"] == "COMPLETE_ACCEPTED_PANEL"


def test_proven_unsafe_selection_visible_despite_other_reference_gap():
    policy, reference, model = fixture()
    reference["cases"]["c0"]["margin"]["interval"] = None
    reference["actions"]["b"] = {"feasibility": "INFEASIBLE", "objective": None}
    policy["components"][2]["pairs"] = []
    model["selected_action"] = "b"
    row = result(policy, reference, model)
    assert row["status"] == "CANDIDATE_UNSAFE_SELECTION"
    assert row["candidate_status"] == "PROVEN_UNSAFE_SELECTION"
    assert row["reference_status"] == "PARTIAL_OR_UNRESOLVED"
    assert row["registered_D"] is None


def test_interval_crossing_limit_does_not_certify_its_point_side():
    policy, reference, model = fixture()
    reference["cases"]["c0"]["margin"]["interval"].update(lower=-0.1, upper=0.2)
    report = REDUCER.reduce_design(policy, reference, [model])
    assert report["coverage"][0]["status"] == "INTERVAL_SIDE_UNRESOLVED"
    row = report["models"][0]
    assert row["point_estimate_D"] == 1.0
    assert row["registered_D"] is None and row["candidate_issues"] == []


def test_interval_outside_proximity_cannot_certify_near_point():
    policy, reference, model = fixture()
    reference["cases"]["c0"]["margin"]["interval"].update(lower=0.05, upper=1.01)
    report = REDUCER.reduce_design(policy, reference, [model])
    assert report["coverage"][0]["status"] == "INTERVAL_PROXIMITY_UNRESOLVED"
    row = report["models"][0]
    assert row["point_estimate_D"] == 1.0
    assert row["registered_D"] is None and row["candidate_issues"] == []


@pytest.mark.parametrize("direction", ["MINIMIZE", "MAXIMIZE"])
def test_single_feasible_action_has_exact_zero_regret_despite_objective_interval(
    direction,
):
    policy, reference, model = fixture()
    policy["objective"]["direction"] = direction
    policy["components"][2]["pairs"] = []
    reference["actions"]["a"]["objective"] = atom(1.5)
    reference["actions"]["a"]["objective"]["interval"].update(lower=1.0, upper=2.0)
    reference["actions"]["b"] = {"feasibility": "INFEASIBLE", "objective": None}
    row = result(policy, reference, model)
    assert row["V"]["regret_bounds"] == [0.0, 0.0]
    assert row["V"]["value_equivalence_status"] == "VERIFIED_EQUIVALENT"
    assert row["registered_D"] == 1.0 and row["earns_full_credit"]


@pytest.mark.parametrize("direction", ["MINIMIZE", "MAXIMIZE"])
def test_selected_interval_dominating_other_action_has_zero_regret(direction):
    policy, reference, model = fixture()
    policy["objective"]["direction"] = direction
    values = (
        {"a": (1.0, 0.8, 1.2), "b": (2.5, 2.0, 3.0)}
        if direction == "MINIMIZE"
        else {"a": (3.5, 3.0, 4.0), "b": (1.5, 1.0, 2.0)}
    )
    for key, (point, lo, hi) in values.items():
        reference["actions"][key]["objective"] = atom(point)
        reference["actions"][key]["objective"]["interval"].update(lower=lo, upper=hi)
        model["actions"][key]["objective"] = pred(point)
    row = result(policy, reference, model)
    assert row["V"]["regret_bounds"] == [0.0, 0.0]
    assert row["V"]["winner_order_is_settled"]
    assert row["registered_D"] == 1.0 and row["earns_full_credit"]


def test_ambiguous_value_equivalence_is_reference_gap_not_registered_full_credit():
    policy, reference, model = fixture()
    for key, (point, lo, hi) in {"a": (1.5, 1.0, 2.0), "b": (1.75, 1.4, 2.1)}.items():
        reference["actions"][key]["objective"] = atom(point)
        reference["actions"][key]["objective"]["interval"].update(lower=lo, upper=hi)
        model["actions"][key]["objective"] = pred(point)
    row = result(policy, reference, model)
    assert row["point_estimate_D"] == 1.0
    assert row["V"]["regret_bounds"] == pytest.approx([0.0, 0.6])
    assert row["V"]["value_equivalence_status"] == "UNRESOLVED"
    assert row["registered_D"] is None and not row["earns_full_credit"]
    assert row["candidate_issues"] == []
    assert "VALUE_EQUIVALENCE_UNRESOLVED" in row["reference_limitations"]
    policy["objective"]["equivalence"]["value"] = 0.7
    resolved = result(policy, reference, model)
    assert resolved["V"]["regret_bounds"] == [0.0, 0.0]
    assert resolved["registered_D"] == 1.0 and resolved["earns_full_credit"]
