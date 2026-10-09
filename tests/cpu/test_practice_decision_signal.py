"""Synthetic public-practice decision diagnostics; no model or solver runs."""

from __future__ import annotations

import json

import pytest

from carbon.battery import practice_safety as safety
from carbon.battery.compile import compile_recipe
from carbon.battery.value import contract as ev_contract
from carbon.battery.value import panel
from scripts.dev.battery import practice_decision_signal as signal


def _outputs(rate=1.0, *, temperature=40.0, plating=0.01):
    points = safety.GRID_POINTS
    return {
        "voltage_v": [3.5 + rate * i / (points - 1) for i in range(points)],
        "temperature_c": [temperature] * points,
        "plating_margin_v": plating,
    }


def _public_panel(*, fastest_temperature=46.0, fastest_plating=0.01):
    grid = {}
    references = {}
    predictions = {}
    fastest = safety.CANDIDATES[-1]["id"]
    for i, candidate in enumerate(safety.CANDIDATES):
        case_id = f"public-toy-{i}"
        grid[candidate["id"]] = case_id
        rate = 0.95 + i / 100
        truth = _outputs(
            rate,
            temperature=fastest_temperature if candidate["id"] == fastest else 40.0,
            plating=fastest_plating if candidate["id"] == fastest else 0.01,
        )
        references[case_id] = {"status": "OK", "outputs": truth}
        predictions[case_id] = dict(truth)
    decision_set = safety.DecisionSet(
        conditions=((20.0, 0.2),), grid=(grid,), references=references
    )
    return decision_set, predictions, fastest


def test_public_q3_style_regret_and_feasibility_follow_the_frozen_selector():
    decision_set, predictions, fastest = _public_panel()
    accurate = signal.evaluate(predictions, decision_set)
    assert accurate["status"] == "MEASURED_PUBLIC_PRACTICE"
    assert accurate["measures"]["regret"] == 0.0
    assert accurate["measures"]["false_feasible"] == 0.0
    case_id = decision_set.grid[0][fastest]
    predictions[case_id] = {
        **predictions[case_id],
        "temperature_c": [40.0] * safety.GRID_POINTS,
    }
    optimistic = signal.evaluate(predictions, decision_set)
    assert optimistic["outcome_counts"] == {"SELECTED_INFEASIBLE": 1}
    assert optimistic["measures"]["regret"] == 10.0
    assert optimistic["measures"]["false_feasible"] == 1.0
    assert optimistic["chosen"] == 1
    assert "selected" not in str(optimistic)
    assert case_id not in str(optimistic)


def test_missing_prediction_and_reference_fault_never_become_clean():
    decision_set, predictions, fastest = _public_panel()
    case_id = decision_set.grid[0][fastest]
    missing = dict(predictions)
    del missing[case_id]
    assert signal.evaluate(missing, decision_set) == {
        "status": "UNMEASURED_PREDICTIONS",
        "missing": 1,
        "extra": 0,
    }
    decision_set.references[case_id] = {"status": "FAILED_INFRA"}
    failed = signal.evaluate(predictions, decision_set)
    assert failed["status"] == "UNMEASURED_REFERENCES"
    assert failed["reference_unresolved"] == 1
    assert "measures" not in failed


def test_unresolved_choice_is_diagnostic_and_all_infeasible_is_excluded():
    decision_set, predictions, _fastest = _public_panel(
        fastest_temperature=40.0, fastest_plating=0.0
    )
    selected_unresolved = signal.evaluate(predictions, decision_set)
    assert selected_unresolved["outcome_counts"] == {"SELECTED_UNRESOLVED": 1}
    assert selected_unresolved["measures"]["unresolved"] == 1.0
    assert selected_unresolved["measures"]["regret"] == 10.0
    for reference in decision_set.references.values():
        reference["outputs"]["temperature_c"] = [46.0] * safety.GRID_POINTS
    all_infeasible = signal.evaluate(predictions, decision_set)
    assert all_infeasible["status"] == "UNMEASURED_REFERENCES"
    assert all_infeasible["excluded_all_infeasible"] == 1


def test_practice_rule_fields_are_copied_from_registered_public_ev4_contract():
    contract, _ = ev_contract.load(
        signal.ROOT
        / "carbon/battery/value/contracts/ev4-charge-protocol-selection.v1.json"
    )
    for name, value in signal.RULES["objective"].items():
        assert value == contract["objective"][name]
    contract_constraints = {row["id"]: row for row in contract["constraints"]}
    for rule in signal.RULES["constraints"]:
        for name, value in rule.items():
            assert value == contract_constraints[rule["id"]][name]
    assert signal.RULES["reference"] == {
        "uncertainty": {"bands": contract["reference"]["uncertainty"]["bands"]}
    }
    assert (
        signal.RULES["minimum_useful_improvement_s"]
        == contract["minimum_useful_improvement_s"]
    )
    for name, value in signal.RULES["mistake_costs"].items():
        assert value == contract["mistake_costs"][name]
    assert signal.BASELINE_ID == ev_contract.candidate_id(
        contract["baseline"]["protocol"]
    )
    assert safety.CANDIDATES == tuple(ev_contract.candidates(contract))


def test_run5_rebuild_uses_historical_recipe_identity_and_unchanged_jax_code():
    signal._verify_historical_jax_rebuild()
    _q1, members = signal._first_seed_panel()
    summaries = json.loads(signal.PRACTICE_SUMMARIES.read_text())
    for member, _recipe, strategy, _seed in members:
        _, compiled = compile_recipe(
            strategy, implementation=signal.RUN5_IMPLEMENTATION
        )
        assert compiled.settings["backend"] == "jax"
        assert compiled.recipe_digest == summaries[member]["recipe_digest"]


def test_report_requires_every_matched_member_and_discloses_only_aggregates(
    tmp_path, monkeypatch
):
    members = list(panel.members("graphite-run5"))[:4:3]
    q1 = {
        "members": {},
        "mask": {"common_resolved": 6},
    }
    summaries = {}
    values = [(0.1, 0.3, 1.0), (0.3, 0.1, 0.0)]
    selected = []
    for (member, recipe, strategy, seed), (accuracy, regret, value) in zip(
        members, values, strict=True
    ):
        _, compiled = compile_recipe(
            strategy, implementation=signal.RUN5_IMPLEMENTATION
        )
        q1["members"][member] = {
            "recipe": recipe,
            "cpu_practice_score": accuracy,
            "development_decision_loss": value,
        }
        summaries[member] = {
            "recipe_digest": compiled.recipe_digest,
            "summary": {"score": accuracy},
        }
        selected.append((member, recipe, strategy, seed))
        receipt = {
            **signal._receipt_context(member, recipe, seed, compiled.recipe_digest),
            "result": {
                "status": "MEASURED_PUBLIC_PRACTICE",
                "conditions": 6,
                "scored_conditions": 5,
                "reference_unresolved": 1,
                "excluded_all_infeasible": 0,
                "chosen": 5,
                "abstained": 0,
                "outcome_counts": {"SELECTED_FEASIBLE": 5},
                "measures": {
                    "regret": regret,
                    "false_feasible": 0.0,
                    "unresolved": 0.0,
                    "over_caution": 0.0,
                },
            },
        }
        (tmp_path / (recipe + ".json")).write_text(json.dumps(receipt))
    summary_path = tmp_path / "summaries.json"
    summary_path.write_text(json.dumps(summaries))
    q1_path = tmp_path / "q1.json"
    q1_path.write_text(json.dumps(q1))
    monkeypatch.setattr(signal, "PRACTICE_SUMMARIES", summary_path)
    monkeypatch.setattr(signal, "Q1", q1_path)
    monkeypatch.setattr(signal, "_first_seed_panel", lambda: (q1, selected))
    result = signal.report(tmp_path)
    assert result["recipes"] == 2
    assert result["accuracy_vs_development_value"]["kendall_tau_b"] == -1.0
    assert result["public_decision_regret_vs_development_value"]["kendall_tau_b"] == 1.0
    assert result["difference_decision_minus_accuracy"]["kendall_tau_b"] == 2.0
    assert '"seed"' not in json.dumps(result)
    assert "receipt_sha256" not in json.dumps(result)
    assert "public-toy" not in json.dumps(result)
    (tmp_path / (selected[0][1] + ".json")).unlink()
    with pytest.raises(ValueError, match="missing public-practice receipt"):
        signal.report(tmp_path)
