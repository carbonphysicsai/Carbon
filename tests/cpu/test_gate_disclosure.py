"""Owner G14 (18 Nov 2026; V2's spec GATE_DISCLOSURE_20261118): the miner's own grade shows, per registered gate, its
published rule, its result, a closed reason code and the plain-language reason (Ladder feedback v5), and nothing else
from the exam: no case, count, value, margin, unpublished threshold, timing, partial score, digest or other hotkey."""

from __future__ import annotations

import json

import pytest

from carbon.challenge_registry import published_exam
from carbon.challenge_validator import ladder_store
from carbon.scoring import grade_feedback as gf

GATES = ["complete_fixed_coverage", "native_motor_valid", "physics_pool", "speed"]
RULES = {
    "native_motor_valid": "every cell is scorable",
    "complete_fixed_coverage": "all 30 cells are scored",
    "physics_pool": "the physics gates hold on every design",
}
DIGEST = "sha256:" + "a" * 64
#: values planted in the graded row that the document must never carry (each refused class)
SENTINELS = {
    "case": "case-7f3e-hidden",
    "count": 4711,
    "value": 0.123456789,
    "margin": -0.0098765,
    "threshold": 0.4321987,
    "timing": 13.579246,
    "partial": 0.8642097,
    "digest": "sha256:" + "d" * 64,
    "hotkey": "5OtherHotkeyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
}


def _graded(status="MANDATORY_GATE_FAILED", gates=None):
    return {
        "status": status,
        "score": SENTINELS["partial"],
        "legs": {"A": SENTINELS["value"], "D": SENTINELS["partial"]},
        "gates": (
            {"native_motor_valid": "PASS", "complete_fixed_coverage": "PASS", "physics_pool": "FAIL"}
            if gates is None
            else gates
        ),
        # what a grade knows and must never show
        "failed_cases": [SENTINELS["case"]],
        "failed_count": SENTINELS["count"],
        "margin": SENTINELS["margin"],
        "threshold": SENTINELS["threshold"],
        "speed_median_seconds": SENTINELS["timing"],
        "pool_digest": SENTINELS["digest"],
        "other_hotkey": SENTINELS["hotkey"],
    }


def _document(graded, rules=RULES):
    return gf.ladder_feedback(
        graded,
        best=None,
        exam_version="electric-motor-magnetics 1.8",
        gate_registry=GATES,
        rebuild_noise=None,
        recipe_digest=DIGEST,
        epoch=26431,
        published_rules=rules,
    )


def test_a_failed_gate_shows_its_published_rule_result_and_plain_reason():
    document = _document(_graded())
    assert document["schema"] == gf.SCHEMA_V5 and document["stage"] == "grading"
    assert document["status"] == "GATE_FAILED" and document["gate_names"] == ["physics_pool"]
    report = {entry["name"]: entry for entry in document["gate_report"]}
    assert set(report) == set(GATES)
    assert report["physics_pool"] == {
        "name": "physics_pool",
        "rule": RULES["physics_pool"],
        "result": "fail",
        "reason_code": "pool_design_violates_published_constraint",
        "reason": "physics pool: a predicted design violates a published physics constraint.",
    }
    assert report["native_motor_valid"]["result"] == "pass"
    assert report["native_motor_valid"]["reason"] is None
    # a gate the grade did not reach; a gate with no published rule says so, never an invented one
    assert report["speed"]["result"] == "not_evaluated"
    assert report["speed"]["rule"] == gf.NOT_PUBLISHED


def test_carbons_own_failure_shows_carbon_failure_on_every_gate():
    document = _document(_graded(status="FAILED_INFRA", gates={}))
    assert document["status"] == "NOT_SCORED"
    assert {entry["result"] for entry in document["gate_report"]} == {"carbon_failure"}
    assert all("not charged" in entry["reason"] for entry in document["gate_report"])


def test_the_key_sets_are_pinned():
    document = _document(_graded())
    assert set(document) == gf.FIELDS_V3 | gf.V5_ADDED
    assert all(set(entry) == gf.GATE_REPORT_FIELDS for entry in document["gate_report"])


@pytest.mark.parametrize("refused", sorted(SENTINELS))
def test_no_refused_class_ever_appears(refused):
    for status in ("MANDATORY_GATE_FAILED", "FAILED_INFRA"):
        text = json.dumps(_document(_graded(status=status)))
        assert str(SENTINELS[refused]) not in text


def test_shape_refuses_anything_outside_the_closed_report():
    document = _document(_graded())
    assert gf.shape(document) == gf.SCHEMA_V5
    for change in (
        lambda d: d["gate_report"][0].update(case="x"),
        lambda d: d["gate_report"][0].update(result="partial"),
        lambda d: d["gate_report"][2].update(reason_code="made_up"),
        lambda d: d["gate_report"][2].update(reason="a value of 0.31 was below 0.4"),
        lambda d: d.update(margin=0.1),
    ):
        broken = json.loads(json.dumps(document))
        change(broken)
        assert gf.shape(broken) is None


def test_the_store_keeps_a_v5_document_whole():
    document = _document(_graded())
    assert ladder_store.checked(document, latest=True) == document


def test_motor_18_rules_are_the_published_registration_text():
    block = published_exam.for_version("electric-motor-magnetics", "1.8")
    published = {gate["id"]: gate["passes_when"] for gate in block["gates"]}
    assert "physics_pool" in published
    document = _document(_graded(), rules=published)
    report = {entry["name"]: entry for entry in document["gate_report"]}
    assert report["physics_pool"]["rule"] == published["physics_pool"]
