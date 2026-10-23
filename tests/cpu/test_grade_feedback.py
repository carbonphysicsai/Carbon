"""Private-exam Ladder feedback (OWNER-GRADE-FEEDBACK-LADDER-01).

Claims: the miner's document holds exactly the allow-listed fields; values are
rounded down to the step (max(0.02, registered rebuild noise)); submissions
that improve by less than a step give byte-identical documents; a gate
failure shows registry gate names only; a new exam version resets the ladder;
nothing private (case values, ids, picks, unrounded legs) can pass through.
"""

from __future__ import annotations

import json

import pytest

from carbon.scoring import grade_feedback as ladder

GATES = ("native_motor_valid", "complete_fixed_coverage")


def _scored(total, a, d, **extra):
    return {
        "artifact_digest": "sha256:" + "a" * 64,
        "status": "SCORED_DEVELOPMENT_CANDIDATE",
        "score": total,
        "legs": {"A": a, "D": d},
        "gates": {g: "PASS" for g in GATES},
        "components": {"robust_fidelity_benefit": a},
        "decision_outcome": "VERIFIED_FEASIBLE",
        **extra,
    }


def _feedback(graded, best=None, exam_version="exam-1", rebuild_noise=None):
    return ladder.ladder_feedback(
        graded,
        best=best,
        exam_version=exam_version,
        gate_registry=GATES,
        rebuild_noise=rebuild_noise,
    )


def test_the_document_is_exactly_the_allow_list_and_rounds_down_to_the_step():
    doc = _feedback(_scored(0.6239, 0.2811, 0.9667, per_case=[0.1, 0.2], pick="d03"))
    assert set(doc) == ladder.FIELDS
    assert doc == {
        "schema": ladder.SCHEMA,
        "exam_version": "exam-1",
        "status": "IMPROVED",
        "total": 0.62,
        "gate_names": [],
    }
    text = json.dumps(doc)
    for private in (
        "per_case",
        "d03",
        "artifact_digest",
        "components",
        "0.2811",
        "0.9667",
    ):
        assert private not in text
    # Exact on the grid boundary (no float jitter): 0.6 / 0.02 is 30, not 29.
    assert _feedback(_scored(0.6, 0.6, 0.6))["total"] == 0.6


def test_the_step_is_the_larger_of_eta_and_registered_rebuild_noise():
    assert ladder.step(None) == 0.02
    assert ladder.step(0.005) == 0.02
    assert ladder.step(0.05) == 0.05
    assert (
        _feedback(_scored(0.6239, 0.2811, 0.9667), rebuild_noise=0.05)["total"] == 0.6
    )
    with pytest.raises(ladder.LadderFeedbackRefused):
        ladder.step(float("nan"))


def test_rebuild_noise_must_be_passed_explicitly():
    with pytest.raises(TypeError, match="rebuild_noise"):
        ladder.ladder_feedback(
            _scored(0.6, 0.6, 0.6),
            best=None,
            exam_version="exam-1",
            gate_registry=(),
        )


def test_improvements_under_the_step_give_byte_identical_documents():
    first = _feedback(_scored(0.61, 0.3, 0.9))
    second = _feedback(_scored(0.615, 0.31, 0.95), best=first)
    third = _feedback(_scored(0.6199, 0.32, 0.99), best=ladder.next_best(first, second))
    assert second["status"] == third["status"] == "NO_IMPROVEMENT"
    assert json.dumps(second, sort_keys=True) == json.dumps(third, sort_keys=True)
    assert second["total"] == first["total"] == 0.6
    # One full step above the best shown total moves the ladder.
    moved = _feedback(_scored(0.62, 0.3, 0.95), best=ladder.next_best(first, third))
    assert moved["status"] == "IMPROVED" and moved["total"] == 0.62


def test_a_gate_failure_shows_registry_gate_names_only():
    failed = {
        "status": "MANDATORY_GATE_FAILED",
        "score": None,
        "legs": {"A": 0.9, "D": 0.9},
        "gates": {"native_motor_valid": "FAIL", "complete_fixed_coverage": "PASS"},
    }
    best = _feedback(_scored(0.61, 0.3, 0.9))
    doc = _feedback(failed, best=best)
    assert doc["status"] == "GATE_FAILED"
    assert doc["gate_names"] == ["native_motor_valid"]
    assert doc["total"] == 0.6
    assert "A" not in doc and "D" not in doc
    with pytest.raises(ladder.LadderFeedbackRefused, match="gate_registry"):
        _feedback({**failed, "gates": {"case_17_peak": "FAIL"}})


def test_unscored_outcomes_reveal_no_grade_and_keep_the_ladder():
    """Validator, 2026-10-20: INDETERMINATE_EVIDENCE and DIAGNOSTIC_Q (and
    every other result that does not count) show NOT_SCORED with no total, A
    or D; the cap releases their slot on that condition."""
    best = _feedback(_scored(0.61, 0.3, 0.9))
    for status in (
        "INDETERMINATE_EVIDENCE",
        "DIAGNOSTIC_Q",
        "CANDIDATE_INVALID",
        "REQUIRED_LEG_MINIMUM_FAILED",
        "DECISION_OUTCOME_INELIGIBLE",
        "FAILED_INFRA",
    ):
        doc = _feedback(
            {"status": status, "score": 0.97, "legs": {"A": 0.99, "D": 0.95}}, best=best
        )
        assert doc["status"] == "NOT_SCORED" and doc["gate_names"] == []
        assert doc["total"] is None
        # The ladder is kept: the best document is unchanged.
        assert ladder.next_best(best, doc) is best
    after = _feedback(_scored(0.615, 0.3, 0.9), best=best)
    assert after["status"] == "NO_IMPROVEMENT" and after["total"] == 0.6


def test_a_new_exam_version_resets_the_ladder():
    old = _feedback(_scored(0.9, 0.9, 0.9), exam_version="exam-1")
    fresh = _feedback(_scored(0.41, 0.4, 0.4), best=old, exam_version="exam-2")
    assert fresh["status"] == "IMPROVED"
    assert fresh["exam_version"] == "exam-2" and fresh["total"] == 0.4


def test_a_malformed_or_unimproved_best_document_is_refused():
    with pytest.raises(ladder.LadderFeedbackRefused, match="best"):
        _feedback(_scored(0.6, 0.6, 0.6), best={"total": 0.1, "case_ids": []})
    shown = _feedback({"status": "CANDIDATE_INVALID"})
    with pytest.raises(ladder.LadderFeedbackRefused, match="best"):
        _feedback(_scored(0.6, 0.6, 0.6), best=shown)


# --- a v3 NOT_SCORED document says why (reason, leg) --------------------------

DIGEST = "sha256:" + "d" * 64


def _v3(graded, **extra):
    return ladder.ladder_feedback(
        graded,
        best=None,
        exam_version="exam-1",
        gate_registry=GATES,
        rebuild_noise=None,
        recipe_digest=DIGEST,
        epoch=3,
        **extra,
    )


@pytest.mark.parametrize(
    "status,reason",
    [
        ("REQUIRED_LEG_MINIMUM_FAILED", "LEG_MINIMUM_FAILED"),
        ("CANDIDATE_INVALID", "CANDIDATE_INVALID"),
        ("DECISION_OUTCOME_INELIGIBLE", "DECISION_INELIGIBLE"),
        ("FAILED_INFRA", "FAILED_INFRA"),
        ("INDETERMINATE_EVIDENCE", "INDETERMINATE"),
        ("DIAGNOSTIC_Q", "INDETERMINATE"),
    ],
)
def test_a_v3_not_scored_document_names_its_reason_and_only_a_minimum_names_a_leg(
    status, reason
):
    graded = {"status": status, "score": None, "legs": {"A": 0.7, "D": 0.2}}
    doc = _v3(graded, leg_minimums={"A": 0.5, "D": 0.4})
    assert doc["status"] == "NOT_SCORED" and doc["total"] is None
    assert doc["reason"] == reason
    assert doc["leg"] == ("D" if reason == "LEG_MINIMUM_FAILED" else None)
    assert ladder.shape(doc) == ladder.SCHEMA_V3
    assert set(doc) == ladder.FIELDS_V3_NOT_SCORED
    assert "0.7" not in json.dumps(doc) and "0.2" not in json.dumps(doc)


def test_the_leg_is_the_first_registered_leg_below_its_minimum_never_a_number():
    graded = {
        "status": "REQUIRED_LEG_MINIMUM_FAILED",
        "score": None,
        "legs": {"A": 0.1, "D": 0.1},
    }
    assert _v3(graded, leg_minimums={"A": 0.5, "D": 0.5})["leg"] == "A"
    assert _v3(graded, leg_minimums=None)["leg"] is None  # unknown stays null


def test_other_documents_and_v2_are_unchanged_by_the_reason_fields():
    scored = _v3(_scored(0.7, 0.5, 0.9))
    assert set(scored) == ladder.FIELDS_V3 and "reason" not in scored
    v2 = _feedback({"status": "FAILED_INFRA", "score": None, "legs": {}})
    assert set(v2) == ladder.FIELDS and v2["status"] == "NOT_SCORED"


def test_a_malformed_reason_or_a_leg_on_another_reason_is_not_a_ladder_document():
    doc = _v3({"status": "CANDIDATE_INVALID", "score": None, "legs": {}})
    for bad in (
        {**doc, "reason": "SOMETHING"},
        {**doc, "leg": "A"},  # a leg only with LEG_MINIMUM_FAILED
        {**doc, "status": "IMPROVED"},
    ):
        assert ladder.shape(bad) is None
