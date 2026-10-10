"""Synthetic contract tests; no Challenge references or hidden material."""

import copy
import json

import pytest

from carbon.development_comparison import value_bar as vb


def sha(character):
    return "sha256:" + character * 64


def fixture():
    questions = ["q1", "q2", "q3", "q4"]
    export = sha("a")
    baseline = {
        "schema": vb.BASELINE_SCHEMA,
        "family": "f02",
        "material": "DEVELOPMENT",
        "export_digest": export,
        "equal_budget_screening": {
            "schema": vb.SCREEN_SCHEMA,
            "export_digest": export,
            "materials_digest": sha("b"),
            "candidate_rankings": [
                {"case": q, "objective": {"unit": "s"}} for q in questions
            ],
        },
        "held_out": {
            "decision": {
                "decisions": [
                    {
                        "question": q,
                        "kind": "SELECTED_FEASIBLE",
                        "reference_state": "FEASIBLE_EXISTS",
                        "reference_resolved": True,
                        "regret": 2.0,
                    }
                    for q in questions
                ]
            }
        },
    }
    carbon = {
        "schema": vb.CARBON_SCHEMA,
        "challenge": "f02",
        "export_digest": export,
        "model_id": "chosen-before-holdout",
        "decisions": [
            {
                "question": q,
                "kind": "SELECTED_FEASIBLE",
                "reference_state": "FEASIBLE_EXISTS",
                "reference_resolved": True,
                "regret": 0.5,
            }
            for q in questions
        ],
    }
    budget = {"wall_s": 12.0, "core_s": 12.0}
    body = {
        "schema": vb.EVIDENCE_SCHEMA,
        "scope": "DEVELOPMENT",
        "challenge": "f02",
        "export_digest": export,
        "selection": {
            "carbon_model_id": "chosen-before-holdout",
            "baseline_id": "f02",
            "selection_role": "TUNING",
            "selection_receipt_digest": sha("c"),
        },
        "baseline_report": baseline,
        "carbon_report": carbon,
        "folds": {
            "schema": vb.FOLDS_SCHEMA,
            "export_digest": export,
            "folds": [
                {"fold_id": "A", "source_digest": sha("d"), "questions": questions[:2]},
                {"fold_id": "B", "source_digest": sha("e"), "questions": questions[2:]},
            ],
        },
        "speed": {
            "schema": vb.SPEED_SCHEMA,
            "export_digest": export,
            "status": "MEASURED",
            "query_unit": "full_registered_decision_query",
            "route": "same-cpu-route",
            "pairs": [
                {"query": q, "reference_wall_s": 10.0, "carbon_wall_s": 1.0}
                for q in questions
            ],
        },
        "equal_budget": {
            "schema": vb.EQUAL_BUDGET_SCHEMA,
            "status": "OK",
            "challenge": "f02",
            "source_digest": export,
            "objective": {"direction": "min", "unit": "s"},
            "cost_basis": "MEASURED",
            "confidence": 0.95,
            "independent_clusters": 2,
            "curves": [
                {
                    "budget": budget,
                    "bootstrap_ci": {"p_model_beats_solver": [0.8, 0.95]},
                    "estimates": {
                        "model_then_solver": {
                            "mean_regret_conditional": 0.5,
                            "feasible_pick_fraction": 1.0,
                        },
                        "baseline_then_solver": {"mean_regret_conditional": 2.0},
                    },
                }
            ],
        },
        "item_1": {
            "status": "PASS",
            "source_digest": sha("1"),
            "rule_id": "owner-1",
            "challenge": "f02",
            "export_digest": export,
        },
        "item_4": {
            "status": "PASS",
            "source_digest": sha("4"),
            "rule_id": "owner-4",
            "challenge": "f02",
            "export_digest": export,
        },
    }
    rule = {
        "schema": vb.RULE_SCHEMA,
        "rule_id": "synthetic-rule-only",
        "owner_record": "synthetic fixture, no live authority",
        "item_2": {"max_mean_regret_delta": 0.0},
        "item_3": {"min_median_wall_speedup": 5.0},
        "item_5": {
            "budget": budget,
            "min_p_lower": 0.7,
            "max_regret_excess": 0.0,
            "min_feasible_pick_fraction": 0.9,
        },
    }
    return vb.seal(body), rule


def evaluate(evidence, rule):
    return vb.evaluate(evidence, rule, bootstrap_replicates=1000, seed=7)


def reseal(evidence):
    body = {key: value for key, value in evidence.items() if key != "evidence_digest"}
    return vb.seal(body)


def test_five_item_pass_and_replay():
    evidence, rule = fixture()
    first = evaluate(evidence, rule)
    assert first == evaluate(evidence, rule)
    assert first["status"] == vb.PASS
    assert all(item["status"] == vb.PASS for item in first["items"].values())
    assert first["items"]["2"]["ci95"] == [-1.5, -1.5]
    page = vb.evidence_page(first)
    assert "q1" not in page
    assert "paired regret" in page


def test_item_2_failure_requires_lower_bound_to_cross_margin():
    evidence, rule = fixture()
    evidence["carbon_report"]["decisions"] = [
        {**row, "regret": 3.0} for row in evidence["carbon_report"]["decisions"]
    ]
    report = evaluate(reseal(evidence), rule)
    assert report["items"]["2"]["status"] == vb.FAIL
    assert report["status"] == vb.FAIL


@pytest.mark.parametrize(
    "change", ["overlap", "same_source", "unresolved", "inadmissible"]
)
def test_item_2_never_passes_incomplete_or_unmatched_evidence(change):
    evidence, rule = fixture()
    if change == "overlap":
        evidence["folds"]["folds"][1]["questions"][0] = "q1"
    elif change == "same_source":
        evidence["folds"]["folds"][1]["source_digest"] = sha("d")
    elif change == "unresolved":
        evidence["carbon_report"]["decisions"][0]["reference_resolved"] = False
    else:
        evidence["carbon_report"]["decisions"][0]["kind"] = "SELECTED_INFEASIBLE"
    report = evaluate(reseal(evidence), rule)
    assert report["items"]["2"]["status"] == vb.INSUFFICIENT
    assert report["status"] == vb.INSUFFICIENT


def test_missing_owner_values_or_measured_costs_are_insufficient():
    evidence, rule = fixture()
    missing_rule = copy.deepcopy(rule)
    missing_rule["item_2"] = None
    assert evaluate(evidence, missing_rule)["items"]["2"]["status"] == vb.INSUFFICIENT
    evidence["speed"]["status"] = "ASSUMPTION"
    evidence["equal_budget"]["cost_basis"] = "ASSUMPTION"
    report = evaluate(reseal(evidence), rule)
    assert report["items"]["3"]["status"] == vb.INSUFFICIENT
    assert report["items"]["5"]["status"] == vb.INSUFFICIENT


def test_speed_and_equal_budget_must_use_same_decisions_and_buyer_unit():
    evidence, rule = fixture()
    evidence["speed"]["pairs"][0]["query"] = "different-question"
    evidence["equal_budget"]["objective"]["unit"] = "J"
    report = evaluate(reseal(evidence), rule)
    assert report["items"]["3"]["status"] == vb.INSUFFICIENT
    assert report["items"]["5"]["status"] == vb.INSUFFICIENT


def test_none_feasible_is_unpriced_without_invented_regret():
    evidence, rule = fixture()
    for arm in (
        evidence["baseline_report"]["held_out"]["decision"],
        evidence["carbon_report"],
    ):
        arm["decisions"][0].update(
            kind="CORRECT_ABSTENTION", reference_state="NONE_FEASIBLE", regret=None
        )
    report = evaluate(reseal(evidence), rule)
    assert report["items"]["2"]["none_feasible_questions"] == 1
    assert report["items"]["2"]["paired_questions"] == 3


def test_mixed_units_and_tampered_digest_refused():
    evidence, rule = fixture()
    evidence["baseline_report"]["equal_budget_screening"]["candidate_rankings"][0][
        "objective"
    ]["unit"] = "J"
    assert evaluate(reseal(evidence), rule)["items"]["2"]["status"] == vb.INSUFFICIENT
    with pytest.raises(vb.ValueBarError, match="digest mismatch"):
        evidence["challenge"] = "motor"
        evaluate(evidence, rule)


def test_other_challenge_owner_receipt_cannot_pass():
    evidence, rule = fixture()
    evidence["item_1"]["challenge"] = "motor"
    with pytest.raises(vb.ValueBarError, match="item 1 receipt invalid"):
        evaluate(reseal(evidence), rule)


def test_cli_writes_page_once(tmp_path):
    evidence, rule = fixture()
    inp = tmp_path / "evidence.json"
    policy = tmp_path / "rule.json"
    out = tmp_path / "report.json"
    page = tmp_path / "page.md"
    inp.write_text(json.dumps(evidence), encoding="utf-8")
    policy.write_text(json.dumps(rule), encoding="utf-8")
    args = [
        "--evidence",
        str(inp),
        "--rule",
        str(policy),
        "--bootstrap-replicates",
        "100",
        "--seed",
        "7",
        "--output-json",
        str(out),
        "--output-page",
        str(page),
    ]
    vb.main(args)
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == vb.PASS
    with pytest.raises(FileExistsError):
        vb.main(args)
