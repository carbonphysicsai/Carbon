"""Toy public-practice counts shown to both Launchpad doors."""

from scripts.dev.battery.gate_pass_diagnosis import (
    PUBLIC_BATTERY_GATES,
    diagnose,
    shareable_counts,
)
from scripts.dev.miner_launchpad.gate_breakdown import summarize


def _trial(eligible, failures, scored=200):
    return {
        "id": "private-trial-id",
        "recipe": {"secret": "do-not-show"},
        "summary": {
            "eligible": eligible,
            "gate_failures": failures,
            "n_scored": scored,
            "score": 0.123456,
        },
    }


def test_battery_counts_match_918_and_strip_recipe_score_and_unknown_names():
    trials = [
        _trial(True, {}),
        _trial(False, {"voltage_ceiling": 2, "capacity_bound": 1}),
        _trial(False, {"voltage_ceiling": 3, "private-gate-name": 2}),
        _trial(True, {"voltage_floor": 1}),  # contradictory, not a pass
        {"summary": {"eligible": True}},  # incomplete, not a pass
    ]
    expected = shareable_counts(diagnose({"experiments": trials}))
    value = summarize(trials, list(PUBLIC_BATTERY_GATES))
    for key in (
        "exported_trials",
        "checked_trials",
        "unverified_trial_summaries",
        "gate_failures",
        "unrecognized_gate_names",
    ):
        assert value[key] == expected[key]
    assert value["trials_passing_all_gates"] == 1
    assert value["gate_failures"]["voltage_ceiling"] == {"trials": 2, "cases": 5}
    assert "private-trial-id" not in str(value)
    assert "do-not-show" not in str(value)
    assert "private-gate-name" not in str(value)
    assert "0.123456" not in str(value)


def test_counts_every_trial_beyond_the_50_row_campaign_feed():
    trials = [_trial(False, {"gate_a": 1}) for _ in range(60)]
    value = summarize(trials, ["gate_a"])
    assert value["exported_trials"] == 60
    assert value["gate_failures"]["gate_a"] == {"trials": 60, "cases": 60}


def test_missing_gate_registry_and_unverified_coverage_fail_closed():
    trial = _trial(True, {}, scored=0)
    unavailable = summarize([trial], None)
    assert unavailable["status"] == "UNAVAILABLE_PUBLIC_GATE_LIST"
    assert unavailable["gate_failures"] == {}
    incomplete = summarize([trial], ["gate_a"])
    assert incomplete["status"] == "INSUFFICIENT_VERIFIED_SUMMARIES"
    assert incomplete["checked_trials"] == 0
    assert incomplete["trials_passing_all_gates"] == 0
    empty = summarize([], ["gate_a"])
    assert empty["status"] == "NO_TRIALS"
    assert empty["gate_failures"]["gate_a"] == {"trials": 0, "cases": 0}
