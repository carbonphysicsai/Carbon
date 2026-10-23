"""M1 E2E round 11 fixes in Launchpad's own campaign view."""

from __future__ import annotations

from scripts.dev.miner_launchpad import campaign_view


def _run(summary, eligible):
    return {
        "id": "trial-1",
        "summary": summary,
        "practice_dual": {
            "schema": campaign_view.DUAL_FEEDBACK_SCHEMA,
            "available": True,
            "gates": {"finite_peak": True, "verified_pick": eligible},
            "eligible": eligible,
            "total": None if not eligible else 0.7,
        },
    }


def test_a_direct_run_s_eligibility_is_its_dual_block_s_when_the_summary_has_none():
    # R11: an untouched F02 2.3 catalog default failed verified_pick in
    # practice (and graded CANDIDATE_INVALID), but the run read "eligible: null"
    # because a direct practice's summary carries no gate verdict.
    (row,) = campaign_view.experiment_rows(
        {"experiments": [_run({"score": 0.4}, False)]}, None
    )
    assert row["eligible"] is False
    assert row["dual"]["gates"]["verified_pick"] is False
    (row,) = campaign_view.experiment_rows(
        {"experiments": [_run({"score": 0.4}, True)]}, None
    )
    assert row["eligible"] is True


def test_a_summary_verdict_still_wins_and_no_verdict_stays_unknown():
    (row,) = campaign_view.experiment_rows(
        {"experiments": [_run({"eligible": True}, False)]}, None
    )
    assert row["eligible"] is True
    (row,) = campaign_view.experiment_rows(
        {"experiments": [{"id": "trial-2", "summary": {"score": 0.4}}]}, None
    )
    assert row["eligible"] is None
