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
