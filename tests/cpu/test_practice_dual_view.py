"""C13: every Challenge's practice run shows the same dual-feedback block,
gates first, then the graded total, read by one shared reader."""

from __future__ import annotations

from scripts.dev.miner_launchpad.campaign_view import dual_feedback

SCHEMA = "carbon.practice.dual-feedback.v1"


def _block(**overrides):
    return {
        "schema": SCHEMA,
        "scope": "PUBLIC_PRACTICE_FEEDBACK",
        "challenge": {"id": "electric-motor-magnetics", "version": "1.3"},
        "available": True,
        "gates": {"native_shape": True, "selected_design_verified_feasible": True},
        "eligible": True,
        "total": 0.61,
        "accuracy": 0.42,
        "design_value": 0.8,
        "decision_outcome": "VERIFIED_FEASIBLE",
        "note": "Computed on the public development bank.",
        "n_cases": 48,
        **overrides,
    }


def test_the_block_is_read_beside_or_inside_the_summary():
    assert dual_feedback({"practice_dual": _block()})["total"] == 0.61
    assert dual_feedback({"summary": {"dual": _block()}})["accuracy"] == 0.42
    assert dual_feedback({"summary": {"score": 1.0}}) is None


def test_a_gate_failure_is_not_eligible_and_carries_no_number():
    shown = dual_feedback(
        {
            "x": _block(
                eligible=False,
                total=None,
                accuracy=None,
                design_value=None,
                gates={"native_shape": False},
            )
        }
    )
    assert shown["eligible"] is False and shown["total"] is None
    assert shown["gates"] == {"native_shape": False}


def test_an_unavailable_block_says_why_and_nothing_else():
    shown = dual_feedback(
        {
            "x": {
                "schema": SCHEMA,
                "available": False,
                "reason": "practice_predict_failed",
            }
        }
    )
    assert shown == {"available": False, "reason": "practice_predict_failed"}


def test_only_allow_listed_fields_reach_the_page():
    shown = dual_feedback({"x": _block(hidden="secret")})
    assert set(shown) == {
        "available",
        "gates",
        "eligible",
        "total",
        "total_direction",
        "accuracy",
        "design_value",
        "n_cases",
        "note",
    }


def test_the_block_is_read_from_the_practice_evaluators_outcome():
    # The producer's key (Test Engineer): outcome["practice_dual"].
    assert dual_feedback({"outcome": {"practice_dual": _block()}})["total"] == 0.61


def test_a_validator_outcomes_practice_dual_reaches_the_submission_view(tmp_path):
    # The Test Engineer's wiring (Motor outcome v2): outcome["practice_dual"].
    import json

    from scripts.dev.miner_launchpad import projection

    path = tmp_path / "permitted-final-feedback.json"
    path.write_text(
        json.dumps(
            {
                "schema": "carbon.battery.permitted-feedback.v1",
                "epoch": 1,
                "outcome": {
                    "state": "SCORED",
                    "evidence": "DEVELOPMENT",
                    "practice_dual": _block(hidden="secret"),
                },
            }
        )
    )
    shown = projection._validator_outcome(1, path)["result"]["practice_dual"]
    assert shown["total"] == 0.61 and "hidden" not in shown


def test_the_query_size_is_carried():
    assert dual_feedback({"x": _block()})["n_cases"] == 48
    assert dual_feedback({"x": _block(n_cases="48")})["n_cases"] is None


def test_a_gate_practice_cannot_test_is_kept_as_not_tested():
    # Test Engineer 309f80fcc: paired_repeat is NOT_TESTED_ON_PRACTICE on
    # F08, F02, Battery; never a pass or a fail; other non-booleans dropped.
    gates = {
        "native_shape": True,
        "paired_repeat": "NOT_TESTED_ON_PRACTICE",
        "x": "yes",
    }
    shown = dual_feedback({"x": _block(gates=gates)})
    assert shown["gates"] == {
        "native_shape": True,
        "paired_repeat": "NOT_TESTED_ON_PRACTICE",
    }


# ---- practice shows the exam's minimums (OWNER-PRACTICE-SHOWS-MINIMUMS-01) ----

SCHEMA_V2 = "carbon.practice.dual-feedback.v2"


def _v2(**overrides):
    fields = {
        "schema": SCHEMA_V2,
        "bank": "public",
        "accuracy_legs": {"A_acc": 0.5},
        "design_parts": {"V": 0.6},
        "status": "PRACTICE_SCORED",
        "failed_legs": [],
        "minimums": {
            "source": "published_exam",
            "version": "f08-dual-sealed-grid-8x1-v2",
            "status": "NOT_YET_SET",
            "legs": {},
        },
        **overrides,
    }
    return _block(**fields)


def test_minimums_not_yet_set_reach_the_page_as_the_doc_carries_them():
    shown = dual_feedback({"x": _v2()})
    assert shown["practice_status"] == "PRACTICE_SCORED"
    assert shown["failed_legs"] == []
    assert shown["minimums"]["status"] == "NOT_YET_SET"
    assert shown["minimums"]["legs"] == {}


def test_a_leg_below_its_minimum_is_named_with_its_minimum_and_value():
    shown = dual_feedback(
        {
            "x": _v2(
                status="PRACTICE_BELOW_MINIMUM",
                failed_legs=["D"],
                minimums={
                    "source": "published_exam",
                    "version": "v",
                    "status": "SET",
                    "legs": {
                        "A": {"minimum": 0.3, "value": 0.5, "met": True},
                        "D": {"minimum": 0.4, "value": 0.2, "met": False},
                    },
                },
            )
        }
    )
    assert shown["practice_status"] == "PRACTICE_BELOW_MINIMUM"
    assert shown["failed_legs"] == ["D"]
    assert shown["minimums"]["legs"]["D"] == {
        "minimum": 0.4,
        "value": 0.2,
        "met": False,
    }
    assert shown["minimums"]["legs"]["A"]["met"] is True


def test_an_unknown_status_or_junk_minimums_do_not_reach_the_page():
    shown = dual_feedback(
        {"x": _v2(status="EXAM_PASSED", minimums={"status": "ok", "legs": {"A": 3}})}
    )
    assert shown["practice_status"] is None
    assert shown["minimums"]["status"] is None and shown["minimums"]["legs"] == {}
    assert dual_feedback({"x": _v2(minimums=None)})["minimums"] is None


def test_the_page_words_are_practice_labelled_and_compute_no_minimum():
    from pathlib import Path

    text = (
        Path(__file__).resolve().parents[2] / "scripts/dev/miner_launchpad/app.js"
    ).read_text(encoding="utf-8")
    assert "practice: below the required minimum for " in text
    assert "Practice: minimums not yet set." in text
    start = text.index("function practiceMinimumsText")
    body = text[start : text.index("\n  }\n", start)]
    # It reads the doc's numbers and never derives or compares one.
    assert "row.minimum" in body and "row.value" in body
    assert " < " not in body and " >= " not in body and "Math." not in body


def test_the_practice_gate_status_never_shares_the_ladders_name():
    shown = dual_feedback({"x": _v2(status="PRACTICE_GATE_FAILED")})
    assert shown["practice_status"] == "PRACTICE_GATE_FAILED"
    # The Ladder's official status is not a practice status: refused.
    assert dual_feedback({"x": _v2(status="GATE_FAILED")})["practice_status"] is None
