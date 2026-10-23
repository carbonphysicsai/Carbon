"""R5-3: after a submit, "Practice runs" does not flip back to Now; nothing is Now until something is pending."""

from scripts.dev.miner_launchpad import campaign_view


def _stages(state, **own):
    return {s["id"]: s["state"] for s in campaign_view.stages({"state": state, **own})}


EXPERIMENTS = [{"id": "e1"}]
FREEZES = [{"epoch": 1}]
RESULTS = [{"epoch": 1}]


def test_practice_is_not_now_again_once_a_submit_is_recorded_and_nothing_is_pending():
    states = _stages(
        "ACTIVE",
        experiments=EXPERIMENTS,
        candidate_freezes=FREEZES,
        final_results=RESULTS,
        started_unix=1,
    )
    assert states == {
        "research": "done",
        "practice": "done",
        "candidate": "done",
        "submit": "done",
    }


def test_practising_again_after_a_submit_says_so_and_a_pending_submit_is_still_now():
    own = dict(
        experiments=EXPERIMENTS,
        candidate_freezes=FREEZES,
        final_results=RESULTS,
        started_unix=1,
    )
    assert _stages("PRACTICING", **own)["practice"] == "current"
    assert _stages("SUBMITTING", **own)["submit"] == "current"
    assert _stages("PAUSED", **own)["practice"] == "halted"


def test_before_any_submit_practice_is_still_now():
    states = _stages("ACTIVE", experiments=EXPERIMENTS, started_unix=1)
    assert states["practice"] == "current" and states["submit"] == "waiting"
