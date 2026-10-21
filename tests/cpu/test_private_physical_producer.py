"""Inert numerical fixtures; no solver, model, actual reference or adopted rule."""

from copy import deepcopy

import pytest

from carbon.scoring import private_evaluation_source as source


def fixture():
    ids = sorted(source._F02_ACTIONS)
    policy = {
        "id": "INERT_F02_SHAPED_SOFTWARE_FIXTURE",
        "case_ids": ids,
        "action_ids": ids,
        "quantities": {
            "peak_top_c": {"unit": "C", "learned": True},
            "thermal_margin_c": {"unit": "C", "learned": True},
            "extra_energy_j": {"unit": "J", "learned": False},
        },
        "objective": {
            "quantity": "extra_energy_j",
            "unit": "J",
            "direction": "MAXIMIZE",
            "scale": {"value": 1.0, "unit": "J"},
            "learned": False,
            "equivalence": {"value": 0.0, "unit": "J"},
        },
        "components": [
            {
                "id": "margin",
                "kind": "margin",
                "quantity": "thermal_margin_c",
                "unit": "C",
                "scale": {"value": 1.0, "unit": "C"},
                "cases": ids,
                "pairs": [],
            },
            {
                "id": "response",
                "kind": "response",
                "quantity": "peak_top_c",
                "unit": "C",
                "scale": {"value": 1.0, "unit": "C"},
                "cases": [],
                "pairs": [
                    [f"cool-rect-near-{p}w", f"cool-rect-near-{p+1}w"]
                    for p in (84, 85, 86)
                ],
            },
        ],
        "coverage_slots": [],
    }
    peaks = {key: 90.0 + i for i, key in enumerate(ids)}
    peaks["cool-rect-low"] = 80.0
    peaks["cool-rect-middle"] = 90.0
    peaks["cool-rect-long-high"] = 98.0
    peaks["cool-rect-short-high"] = 96.0

    def atom(value, unit):
        return {"status": "RESOLVED", "value": value, "unit": unit, "interval": None}

    ref = {"cases": {}, "actions": {}}
    for key in ids:
        peak = peaks[key]
        power, duration = source._F02_ACTIONS[key]
        ref["cases"][key] = {
            "peak_top_c": atom(peak, "C"),
            "thermal_margin_c": atom(95.0 - peak, "C"),
        }
        ref["actions"][key] = {
            "feasibility": "FEASIBLE" if peak <= 95.0 else "INFEASIBLE",
            "objective": atom((power - 20) * duration, "J"),
        }
    return [peaks[k] for k in ids], ref, policy


def reduce(args, *, std=1.0):
    predictions, reference, policy = args
    return source._f02_point_measurements(predictions, reference, policy, std, 95.0)


def test_exact_native_math_and_derived_pick_no_analytic_accuracy_credit():
    result = reduce(fixture())
    assert result["A"] == 1.0
    assert result["model"]["selected_action"] == "cool-rect-middle"
    assert result["reduction"]["V"]["V"] == 1.0
    assert result["reduction"]["point_estimate_D"] == 1.0
    assert result["reduction"]["registered_D"] is None
    assert result["selection_basis"] == "DERIVED_FROZEN_PREDICTION_SELECTION"
    assert set(result["model"]["cases"]["cool-rect-low"]) == {
        "peak_top_c",
        "thermal_margin_c",
    }


def test_correct_pick_wrong_unselected_prediction_loses_both_fidelities():
    args = fixture()
    args[0][args[2]["case_ids"].index("cool-rect-low")] += 2.0
    result = reduce(args)
    assert result["A"] == pytest.approx(1.0 / 3.0)
    assert result["model"]["selected_action"] == "cool-rect-middle"
    assert result["reduction"]["V"]["V"] == 1.0
    assert result["reduction"]["C"] < 1.0
    assert result["reduction"]["point_estimate_D"] < 1.0


def test_optimistic_unsafe_pick_retains_native_adverse_outcome():
    args = fixture()
    args[0][args[2]["case_ids"].index("cool-rect-long-high")] = 94.0
    result = reduce(args)
    assert result["model"]["selected_action"] == "cool-rect-long-high"
    assert (
        result["reduction"]["candidate_selection_outcome"]
        == "SELECTED_PROVEN_INFEASIBLE"
    )


@pytest.mark.parametrize(
    "gap",
    [
        "reference_infra",
        "reference_unresolved",
        "malformed_cases",
        "margin",
        "interval",
        "verdict",
        "objective",
        "drop_component",
        "analytic_credit",
    ],
)
def test_reference_and_definition_faults_are_typed_not_candidate_failures(gap):
    args = fixture()
    _pred, ref, policy = args
    key = policy["case_ids"][0]
    expected = {
        "reference_infra": "dual_native_reference_infra",
        "reference_unresolved": "dual_native_reference_unresolved",
        "malformed_cases": "dual_f02_reference_roster",
        "margin": "dual_f02_reference_margin_binding",
        "interval": "dual_f02_reference_interval_binding",
        "verdict": "dual_f02_reference_verdict_binding",
        "objective": "dual_f02_analytic_objective_binding",
        "drop_component": "dual_f02_critical_components",
        "analytic_credit": "dual_f02_quantity_credit",
    }[gap]
    if gap == "reference_infra":
        ref["cases"][key]["peak_top_c"]["status"] = "FAILED_INFRA"
    elif gap == "reference_unresolved":
        ref["cases"][key]["peak_top_c"]["status"] = "UNRESOLVED"
    elif gap == "malformed_cases":
        ref["cases"] = []
    elif gap == "margin":
        ref["cases"][key]["thermal_margin_c"]["value"] += 1.0
    elif gap == "interval":
        peak = ref["cases"][key]["peak_top_c"]
        peak["interval"] = {
            "lower": peak["value"] - 1.0,
            "upper": peak["value"] + 1.0,
            "unit": "C",
            "receipt": "TOY_ONLY",
        }
    elif gap == "verdict":
        ref["actions"][key]["feasibility"] = (
            "FEASIBLE"
            if ref["actions"][key]["feasibility"] == "INFEASIBLE"
            else "INFEASIBLE"
        )
    elif gap == "objective":
        ref["actions"][key]["objective"]["value"] += 1.0
    elif gap == "drop_component":
        policy["components"].pop()
    else:
        policy["quantities"]["extra_energy_j"]["learned"] = True
    with pytest.raises(source.PrivateEvaluationSourceRefused) as raised:
        reduce(args)
    assert raised.value.code == expected


def test_large_finite_predictions_do_not_overflow_the_mean():
    args = fixture()
    args[0][:] = [1e308] * 8
    # Source aggregate/reducer overflow must be typed, not an uncaught exception.
    with pytest.raises(
        source.PrivateEvaluationSourceRefused, match="candidate_numeric_overflow"
    ):
        reduce(args)
    with pytest.raises(
        source.PrivateEvaluationSourceRefused, match="candidate_numeric_overflow"
    ):
        reduce(args, std=1e-308)


@pytest.mark.parametrize(
    "role",
    [
        "accuracy_definition",
        "important_limit_definition",
        "design_objective",
        "case_bank",
        "reference_rows",
        "solver_evidence",
        "score_pack",
    ],
)
def test_actual_missing_selected_roles_refuse_before_prediction_math(monkeypatch, role):
    class Selected:
        def read_json_role(self, root, audience, name, **kwargs):
            if name == role:
                raise ValueError("missing actual role")
            return {}

    monkeypatch.setattr(source, "EvaluationPackSnapshot", Selected)
    with pytest.raises(source.PrivateEvaluationSourceRefused) as raised:
        source._produce_f02_cold(Selected(), None, None, {}, {}, {}, [], {}, b"")
    assert raised.value.code == "dual_native_role_unavailable:" + role


def test_unknown_challenge_has_no_implicit_producer():
    with pytest.raises(source.PrivateEvaluationSourceRefused) as raised:
        source.produce_dual_benchmark_input(
            selected_pack=None,
            public_root=None,
            private_root=None,
            entry={"challenge": "inert-non-physical-fixture"},
            trusted_job={},
            registration={},
            references=[],
            graph_originals={},
            evaluation_source_receipt_raw=b"",
            timing_step=0.02,
        )
    assert raised.value.code == "dual_measurement_producer_unavailable"


def test_reduction_preserves_inputs():
    args = fixture()
    before = deepcopy(args)
    reduce(args)
    assert args == before
