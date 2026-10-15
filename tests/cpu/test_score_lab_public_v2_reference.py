"""Discriminating reference-only v2 joins/admission on synthetic public shapes."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from carbon.battery.value import contract as ct
from scripts.dev.score_lab import bank
from scripts.dev.score_lab import public_v2_reference as v2
from scripts.dev.score_lab.core import LabRefused

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def fixture():
    contract = json.loads(
        (ROOT / "carbon/battery/value/contracts/ev4-dev-proof-v1.json").read_bytes()
    )
    contract["scenarios"]["development"] = [
        {"id": "D-toy", "conditions": [[24.0, 0.12]]}
    ]
    contract["scenarios"]["verification"] = [
        {"id": "V-toy", "conditions": [[29.0, 0.22]]}
    ]
    refs = {
        job["case_id"]: {
            "status": "OK",
            "outputs": {
                "voltage_v": [4.0] * 10 + [4.2] * 111,
                "temperature_c": [25.0] * 121,
                "plating_margin_v": 0.005,
            },
        }
        for job in ct.decision_cases(contract)
    }
    return contract, refs


def _document(rows):
    return {
        "schema": "carbon.battery.plating-v2-labels.v1",
        "version": v2.VERSION,
        "decision": "VALIDATOR-PLATING-REF-V2-02",
        "rows": rows,
    }


def _near_row(cid, *, margin=0.002, solved=None, source="ev4"):
    outcome = v2.v2_label(margin, solved)
    return {
        "case_id": cid,
        "source": source,
        "m20_mv": margin * 1000,
        "m160_mv": None if solved is None else solved * 1000,
        **outcome,
    }


def test_full_grammar_common_admission_is_reference_only(fixture):
    contract, refs = fixture
    questions, receipt = v2.admission(contract, refs, {}, label_counts={})
    assert receipt["common_mask_by_split"] == {
        "development": ["D-toy"],
        "verification": ["V-toy"],
    }
    assert receipt["full_grammar_actions"] == 35 and receipt["pruned_actions"] == 0
    assert all(len(q["actions"]) == 35 for q in questions.values())
    assert receipt == v2.admission(contract, refs, {}, label_counts={})[1]


def test_pending_candidate_that_can_change_pick_excludes_question(fixture):
    contract, refs = fixture
    cid = next(iter(refs))
    refs[cid]["outputs"]["plating_margin_v"] = 0.002
    refs[cid]["outputs"]["voltage_v"] = [4.0] * 8 + [4.2] * 113
    rows, counts = v2.label_index(_document([_near_row(cid)]), set(refs))
    questions, receipt = v2.admission(contract, refs, rows, label_counts=counts)
    assert questions["D-toy"]["class"] == "INCOMPLETE"
    assert receipt["common_mask_by_split"]["development"] == []
    assert receipt["public_missing_case_handoff"]["PENDING_MESH160"] == [cid]


def test_solved_in_band_candidate_equal_to_best_is_decision_determined(fixture):
    contract, refs = fixture
    cid = next(iter(refs))  # not the registered fallback
    refs[cid]["outputs"]["plating_margin_v"] = 0.002
    rows, counts = v2.label_index(_document([_near_row(cid, solved=0.0005)]), set(refs))
    _, receipt = v2.admission(contract, refs, rows, label_counts=counts)
    assert receipt["questions"][0]["class"] == "SCORED"
    assert receipt["questions"][0]["decision_determined"] is True
    assert "SOLVED_IN_BAND" not in receipt["public_missing_case_handoff"]


def test_outside_v2_claim_does_not_inherit_historical_safe_label(fixture):
    contract, refs = fixture
    cid = next(iter(refs))
    refs[cid]["outputs"]["plating_margin_v"] = 0.020
    questions, receipt = v2.admission(contract, refs, {}, label_counts={})
    assert questions["D-toy"]["class"] == "INCOMPLETE"
    assert receipt["public_missing_case_handoff"]["PLATING_V2_OUTSIDE_CLAIM"] == [cid]


def test_known_thermal_failure_resolves_design_without_claiming_plating(fixture):
    contract, refs = fixture
    cid = next(iter(refs))
    refs[cid]["outputs"]["plating_margin_v"] = 0.020
    refs[cid]["outputs"]["temperature_c"] = [60.0] * 121
    condition = v2.assess_condition(contract, cid, refs[cid], {})
    assert condition["status"] == "INFEASIBLE"
    assert condition["plating_reference"]["label"] == "FAILED_REFERENCE"
    assert condition["checks"]["peak_temperature"] == "FAIL"
    _, receipt = v2.admission(contract, refs, {}, label_counts={})
    assert receipt["questions"][0]["class"] == "SCORED"
    assert "PLATING_V2_OUTSIDE_CLAIM" not in receipt["public_missing_case_handoff"]


def test_owner_covered_admission_preserves_full_menu_and_legacy_reader(fixture):
    contract, refs = fixture
    original = v2.admission(contract, refs, {}, label_counts={})
    questions, receipt = v2.covered_admission(contract, refs, {}, label_counts={})
    assert receipt["common_mask_by_split"] == original[1]["common_mask_by_split"]
    assert receipt["first_line"] == "value conditional on the covered region"
    assert receipt["pruned_actions"] == 0
    assert all(len(q["actions"]) == 35 for q in questions.values())
    assert v2.admission(contract, refs, {}, label_counts={}) == original


def test_owner_excludes_dominated_uncovered_action_even_when_thermal_fails(fixture):
    contract, refs = fixture
    cid = next(iter(refs))
    refs[cid]["outputs"]["plating_margin_v"] = 0.020
    refs[cid]["outputs"]["temperature_c"] = [60.0] * 121
    _, legacy = v2.admission(contract, refs, {}, label_counts={})
    questions, receipt = v2.covered_admission(contract, refs, {}, label_counts={})
    assert "D-toy" in legacy["common_mask_by_split"]["development"]
    assert receipt["common_mask_by_split"]["development"] == []
    assert receipt["common_mask_by_split"]["verification"] == ["V-toy"]
    assert questions["D-toy"]["class"] == "INCOMPLETE"
    assert receipt["reference_coverage"]["plating_status_by_case"][cid] == "UNRESOLVED"
    assert len(questions["D-toy"]["actions"]) == 35


def test_prefix_does_not_override_pdd_source_and_wrong_join_refuses(fixture):
    _, refs = fixture
    index, counts = v2.label_index(
        _document([_near_row("ev4:D-0000", source="pdd")]), set(refs)
    )
    assert index == {} and counts == {"pdd:UNRESOLVED": 1}
    with pytest.raises(LabRefused, match="public_v2_wrong_source_join"):
        v2.label_index(
            _document([_near_row(next(iter(refs)), source="pdd")]), set(refs)
        )


def test_stale_rule_and_changed_margin_join_refuse(fixture):
    contract, refs = fixture
    cid = next(iter(refs))
    row = _near_row(cid)
    bad = {**row, "rule": "m160-d3"}
    with pytest.raises(LabRefused, match="public_v2_source_or_rule"):
        v2.label_index(_document([bad]), set(refs))
    index, counts = v2.label_index(_document([row]), set(refs))
    with pytest.raises(LabRefused, match="public_v2_mesh20_join_mismatch"):
        v2.admission(contract, refs, index, label_counts=counts)


def test_label_file_without_exact_registered_digest_refuses(tmp_path):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(_document([])), encoding="utf-8")
    with pytest.raises(LabRefused, match="public_v2_label_digest"):
        v2.load_labels(path, set())


def test_grammar_pruning_and_missing_reference_refuse(fixture):
    contract, refs = fixture
    pruned = copy.deepcopy(contract)
    pruned["design_variables"]["c1"]["allowed"].pop()
    with pytest.raises(LabRefused, match="public_v2_full_35_action_grammar"):
        v2.admission(pruned, refs, {}, label_counts={})
    refs.pop(next(iter(refs)))
    with pytest.raises(LabRefused, match="public_v2_reference_coverage"):
        v2.admission(contract, refs, {}, label_counts={})


def test_non_reaching_prediction_is_abstention_not_a_fabricated_objective():
    q = {
        "fallback_action": "f",
        "actions": {
            "f": [{"status": "FEASIBLE", "objective": 10.0}],
            "a": [{"status": "FEASIBLE", "objective": 2.0}],
        },
    }
    predicted = {aid: {"feasible": False, "objective": None} for aid in q["actions"]}
    assert bank._v2_question(q, predicted, cap=1, kappa=0.1, unit=1) == {
        "U": 0.0,
        "G": 0.0,
        "n": 0,
    }
    for invalid in (
        {"feasible": True, "objective": None},
        {"feasible": False},
        {"feasible": False, "objective": float("nan")},
    ):
        bad = {**predicted, "a": invalid}
        with pytest.raises(LabRefused, match="bank_predictor_nonfinite"):
            bank._v2_question(q, bad, cap=1, kappa=0.1, unit=1)
