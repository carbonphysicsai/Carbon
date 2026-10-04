"""Benchmark B2 (OWNER-GRAPHITE-ATTACKER-01 §4, slice AT-C).

Claims tested, on synthetic Attacker verdicts and battery's real
deterministic harness (`carbon.battery.track_a.run`):

- each family compares both sides at an equal attempt budget: the first
  `budget` attempts of each, in run order, and nothing after;
- each side reports attempts, budget used, verified findings, near misses,
  timeouts and crashes, NOT_RUN and held-out wrongful rejection; a timeout is
  never a pass and no finding reads as attempted coverage;
- B2 is recorded per attack-knowledge store snapshot;
- mutation: comparing past the budget turns its guarding test red.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_attack_analysis import Seam, StubFamily

from carbon.agent_campaign.attack import benchmark, report, verify

REPOSITORY = Path(__file__).resolve().parents[2]
SNAPSHOT = "sha256:" + "3" * 64


def v(attempt, family, outcome, conditions=(), near_miss=False):
    return verify.Verdict(
        attempt,
        family,
        verify.NO_CONSTRUCTION,
        outcome,
        tuple(conditions),
        near_miss=near_miss,
    )


def attacker():
    return report.attacker_runs(
        [
            v("t-0", "recipe_surface", "HELD"),
            v("t-1", "recipe_surface", "INFRA"),
            v("t-2", "recipe_surface", "BREACHED", ["FAILING_TRIGGER"]),
            v("t-3", "recipe_surface", "BREACHED", ["GATE_ANOMALY"]),
            v("t-4", "mandatory_failure", "HELD", near_miss=True),
        ],
        families=(StubFamily("recipe_surface", "artifact_and_dependency_attacks"),),
    )


def baseline():
    return [
        {
            "family": "recipe_surface",
            "check": "artifact_and_dependency_attacks",
            "attempts": [
                {"attempt": f"b-{n}", "outcome": "HELD", "conditions": []}
                for n in range(5)
            ],
        },
        {
            "family": "staged_bytes",
            "check": "construction_evaluation_isolation",
            "attempts": [{"attempt": "s-0", "outcome": "HELD", "conditions": []}],
        },
    ]


def test_both_sides_are_compared_at_an_equal_attempt_budget():
    out = benchmark.b2(attacker(), baseline(), budget=3, store_snapshot=SNAPSHOT)
    line = out["families"]["recipe_surface"]
    assert line["budget"] == 3
    mine, theirs = line["attacker"], line["baseline"]
    assert (mine["attempts"], mine["budget_used"]) == (3, 3)
    assert (theirs["attempts"], theirs["budget_used"]) == (3, 3)
    # t-3 lies past the budget: not counted.
    assert mine["verified"] == 1 and mine["findings"][0]["attempt"] == "t-2"
    assert mine["timeouts_crashes"] == 1 and mine["completed"] == 2
    assert theirs["verified"] == 0 and theirs["status"] == "ATTEMPTED_COVERAGE"
    assert line["verified_difference"] == 1
    assert out["store_snapshot"] == SNAPSHOT
    assert out["store_snapshot_status"] == "PINNED"
    assert out["claims"]["comparison_is_descriptive"] is True
    assert out["claims"]["exploit_free_bound"] is False


def test_a_side_without_the_family_is_not_run_never_a_pass():
    out = benchmark.b2(attacker(), baseline(), budget=2, seams=(Seam("child_process"),))
    assert out["families"]["staged_bytes"]["attacker"]["status"] == "NOT_RUN"
    assert out["families"]["mandatory_failure"]["baseline"]["status"] == "NOT_RUN"
    assert out["families"]["mandatory_failure"]["attacker"]["near_misses"] == 1
    seam = out["families"]["child_process"]
    assert seam["attacker"]["status"] == seam["baseline"]["status"] == "NOT_RUN"


def test_a_budget_per_family_covers_every_family():
    budget = {"recipe_surface": 1, "staged_bytes": 1, "mandatory_failure": 0}
    out = benchmark.b2(attacker(), baseline(), budget=budget)
    assert out["families"]["recipe_surface"]["attacker"]["attempts"] == 1
    assert out["families"]["mandatory_failure"]["attacker"]["attempts"] == 0
    assert out["budget"] == budget and out["store_snapshot"] is None
    # Recorded per store snapshot: one made without it says so plainly.
    assert out["store_snapshot_status"] == "store_snapshot_missing"
    for bad in ({"recipe_surface": 1}, -1, True, 1.5):
        with pytest.raises(ValueError, match="b2_budget"):
            benchmark.b2(attacker(), baseline(), budget=bad)
    with pytest.raises(ValueError, match="b2_store_snapshot"):
        benchmark.b2(attacker(), baseline(), budget=1, store_snapshot="latest")


def test_held_out_wrongful_rejection_is_reported_on_both_sides():
    held_out = [{"family": "recipe_surface", "control": "c", "passed": False}]
    out = benchmark.b2(attacker(), baseline(), budget=1, controls_held_out=held_out)
    line = out["families"]["recipe_surface"]
    for side in ("attacker", "baseline"):
        assert line[side]["wrongful_rejection_held_out"]["wrongly_refused"] == 1


def test_b2_against_the_battery_harness_at_equal_budget():
    """The deterministic side is `track_a.run()` itself."""
    from carbon.battery import track_a

    base = benchmark.track_a_baseline(REPOSITORY)
    assert [r["family"] for r in base] == [f.family_id for f in track_a.FAMILIES]
    records, coverage, _ = track_a.run(REPOSITORY)
    attacks = [r for r in records if r["role"] == "attack"]
    budget = 2
    out = benchmark.b2(attacker(), base, budget=budget, store_snapshot=SNAPSHOT)
    for family in track_a.FAMILIES:
        theirs = out["families"][family.family_id]["baseline"]
        mine = [r for r in attacks if r["family"] == family.family_id][:budget]
        assert theirs["attempts"] == len(mine)
        assert theirs["verified"] == sum(r["verdict"] == "BREACHED" for r in mine)
    assert out["families"]["recipe_surface"]["attacker"]["verified"] == 0
    # At a budget covering every attack, the engine state is track_a's own.
    whole = benchmark.b2(attacker(), base, budget=len(attacks), store_snapshot=SNAPSHOT)
    for family in track_a.FAMILIES:
        theirs = whole["families"][family.family_id]["baseline"]
        assert theirs["engine_state"] == coverage["families"][family.family_id]


def _record(role, attempt, verdict):
    return {
        "family": "late",
        "check": "artifact_and_dependency_attacks",
        "role": role,
        "attempt": attempt,
        "verdict": verdict,
        "result_digest": "sha256:" + "2" * 64,
    }


def test_the_engine_state_is_recomputed_within_the_budget():
    """A breach past the budget is neither counted nor the cut side's state;
    controls are engine diagnostics, never budgeted."""
    late = report.runs_from_records(
        [
            _record("attack", "a1", "HELD"),
            _record("specimen", "a1", "FIRED"),
            _record("attack", "a2", "BREACHED"),
            _record("specimen", "a2", "FIRED"),
            _record("control", "valid_control", "PASSED"),
        ]
    )
    cut = benchmark.b2([], late, budget=1)["families"]["late"]["baseline"]
    assert (cut["verified"], cut["engine_state"], cut["status"]) == (
        0,
        "IN_PROGRESS",
        "ATTEMPTED_COVERAGE",
    )
    whole = benchmark.b2([], late, budget=2)["families"]["late"]["baseline"]
    assert (whole["verified"], whole["engine_state"]) == (1, "FINDING")
    refused = report.runs_from_records(
        [
            _record("attack", "a1", "HELD"),
            _record("specimen", "a1", "FIRED"),
            _record("control", "valid_control", "WRONGLY_REFUSED"),
        ]
    )
    none = benchmark.b2([], refused, budget=0)["families"]["late"]["baseline"]
    assert none["attempts"] == 0 and none["status"] == "FINDING"
    assert none["findings"][0]["role"] == "trained_control"


# -- mutation ---------------------------------------------------------------------------------
def test_comparing_past_the_budget_fails_its_test(monkeypatch):
    test_both_sides_are_compared_at_an_equal_attempt_budget()
    monkeypatch.setattr(benchmark, "_within", lambda run, budget: run)
    with pytest.raises(AssertionError):
        test_both_sides_are_compared_at_an_equal_attempt_budget()
