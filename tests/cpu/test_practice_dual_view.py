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
        "note",
    }


def test_the_block_is_read_from_the_practice_evaluators_outcome():
    # The producer's key (Test Engineer): outcome["practice_dual"].
    assert dual_feedback({"outcome": {"practice_dual": _block()}})["total"] == 0.61
