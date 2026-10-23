"""Launchpad fixes from the round-8 M1 E2E (reports/E2E_RESULTS_20261022.md)."""

from scripts.dev.miner_launchpad import projection


def test_a_grade_says_in_words_whether_it_is_this_submission_s_and_its_direction():
    # R8-1: an agent read the key's latest grade (then `exam_latest`) as its
    # own; R8-3: an agent assumed lower is better.
    other = {
        "schema": "carbon.private-exam.ladder-feedback.v1",
        "exam_version": "motor-1.3-dev",
        "status": "IMPROVED",
        "total": 0.54,
        "A": 0.3,
        "D": 0.8,
        "gate_names": [],
    }
    grade = projection._grade({"best": other, "latest": other}, "sha256:" + "a" * 64)
    assert grade["this_submission"] == "not_graded_yet" and grade["latest"] is None
    assert grade["other_submission_latest"]["total"] == 0.54
    assert "exam_latest" not in grade
    assert grade["score_direction"] == "higher_is_better"
    mine = {**other, "recipe_digest": "sha256:" + "a" * 64, "epoch": 1}
    grade = projection._grade({"best": mine, "latest": mine}, "sha256:" + "a" * 64, 1)
    assert grade["this_submission"] == "graded"


def test_the_practice_total_says_which_way_it_points():
    from scripts.dev.miner_launchpad.campaign_view import (
        DUAL_FEEDBACK_SCHEMA,
        dual_feedback,
    )

    shown = dual_feedback(
        {
            "practice_dual": {
                "schema": DUAL_FEEDBACK_SCHEMA,
                "available": True,
                "gates": {},
                "eligible": True,
                "total": 0.5,
            }
        }
    )
    assert shown["total_direction"] == "higher_is_better"


def test_the_backend_qualification_says_it_does_not_stop_a_submission():
    # R8-4: agents read BACKEND_UNSUPPORTED as "cannot be rebuilt".
    from carbon.challenge_registry.campaigns import challenge_ref
    from scripts.dev.miner_launchpad import toolbox

    built = toolbox.build(challenge_ref("electric-motor-magnetics"), lanes={})
    text = repr(built)
    assert "does not stop a submission" in text
    # Validator: grading happens on its own registered machines, and no
    # cross-backend parity is promised.
    assert "on its own registered machines" in text
    assert "grades your recipe on this environment" not in text
    assert "not done yet" not in text
