"""The per-family attack report (OWNER-GRAPHITE-ATTACKER-01 §3, slice AT-C).

Claims tested, on synthetic runs, the stub adapter's verdicts and battery's
real deterministic harness (`carbon.battery.track_a.run`):

- per family: attempts, budget used, verified findings, near misses,
  timeouts and crashes, NOT_RUN, and wrongful rejection on held-out
  controls;
- a timeout or crash is never a pass: counted apart, never completed or held;
- a family with no finding is ATTEMPTED_COVERAGE, never an exploit-free
  bound; a declared seam is NOT_RUN;
- a breach or a wrongly refused control is a FAILING_TRIGGER; any condition
  outside the admission CONDITIONS is refused;
- engine records keep the engine's own state (a silent specimen is
  INCONCLUSIVE);
- mutations: counting a timeout as completed, or admitting a finding outside
  CONDITIONS, turns its guarding test red.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_attack_analysis import Seam, StubFamily

from carbon.agent_campaign.attack import report, verify

ARTIFACT = "artifact_and_dependency_attacks"
FEEDBACK = "adaptive_feedback_and_state_attacks"


def v(attempt, family, outcome, conditions=(), near_miss=False):
    return verify.Verdict(
        attempt,
        family,
        verify.REBUILT if outcome != verify.INFRA else verify.NO_CONSTRUCTION,
        outcome,
        tuple(conditions),
        scored=outcome in (verify.HELD, verify.BREACHED),
        near_miss=near_miss,
        evidence={"result": "sha256:" + "1" * 64},
    )


VERDICTS = [
    v("t-0", "recipe_surface", "HELD"),
    v("t-1", "recipe_surface", "BREACHED", ["FAILING_TRIGGER"]),
    v("t-2", "recipe_surface", "HELD", near_miss=True),
    v("t-3", "recipe_surface", "INFRA"),
    v("t-4", "feedback_probe", "INFRA"),
    v("t-5", "feedback_probe", "INFRA"),
    v("t-6", "quiet_family", "HELD"),
    v("t-7", "quiet_family", "UNDETERMINED"),
]
FAMILIES = (
    StubFamily("recipe_surface", ARTIFACT),
    StubFamily("feedback_probe", FEEDBACK),
    StubFamily("quiet_family", "resource_and_failure_accounting"),
    StubFamily("never_tried", "fresh_attack_confirmation"),
)
HELD_OUT = (
    {"family": "recipe_surface", "control": "c-a", "passed": True},
    {"family": "recipe_surface", "control": "c-b", "outcome": "WRONGLY_REFUSED"},
    ("quiet_family", "c-c", True),
    {"family": "quiet_family", "control": "c-d", "outcome": "INFRA"},
)


def full_report():
    runs = report.attacker_runs(VERDICTS, families=FAMILIES)
    return report.family_report(
        runs, controls_held_out=HELD_OUT, seams=(Seam("participant_code"),)
    )


def test_every_family_reports_the_registered_fields():
    out = full_report()
    assert list(out["families"]) == [
        "recipe_surface",
        "feedback_probe",
        "quiet_family",
        "never_tried",
        "participant_code",
    ]
    line = out["families"]["recipe_surface"]
    assert {
        k: line[k]
        for k in (
            "check",
            "status",
            "attempts",
            "budget_used",
            "completed",
            "held",
            "verified",
            "near_misses",
            "timeouts_crashes",
            "not_run",
        )
    } == {
        "check": ARTIFACT,
        "status": "FINDING",
        "attempts": 4,
        "budget_used": 4,
        "completed": 3,
        "held": 2,
        "verified": 1,
        "near_misses": 1,
        "timeouts_crashes": 1,
        "not_run": None,
    }
    assert line["wrongful_rejection_held_out"] == {
        "controls": 2,
        "completed": 2,
        "wrongly_refused": 1,
    }
    assert line["findings"] == [
        {"attempt": "t-1", "condition": "FAILING_TRIGGER", "role": "attack"},
        {"attempt": "c-b", "condition": "FAILING_TRIGGER", "role": "held_out_control"},
    ]
    assert out["totals"]["verified"] == 1
    assert [f["family"] for f in out["findings"]] == ["recipe_surface"] * 2


def test_a_timeout_is_never_a_pass():
    line = full_report()["families"]["feedback_probe"]
    assert line["attempts"] == 2 and line["timeouts_crashes"] == 2
    assert line["completed"] == 0 and line["held"] == 0
    assert line["status"] == "ATTEMPTED_COVERAGE" and line["bound"] is None
    quiet = full_report()["families"]["quiet_family"]
    # An infrastructure-failed held-out control is neither passed nor refused.
    assert quiet["wrongful_rejection_held_out"] == {
        "controls": 2,
        "completed": 1,
        "wrongly_refused": 0,
    }


def test_zero_findings_is_attempted_coverage_never_a_bound():
    out = full_report()
    quiet = out["families"]["quiet_family"]
    assert quiet["status"] == "ATTEMPTED_COVERAGE" and quiet["verified"] == 0
    assert quiet["bound"] is None
    assert out["zero_findings_reads_as"] == "ATTEMPTED_COVERAGE"
    assert out["claims"] == {
        "exploit_free_bound": False,
        "security_acceptance": False,
        "graded": False,
        "timeouts_counted_as_pass": False,
    }
    assert "PASS" not in {line["status"] for line in out["families"].values()}


def test_seams_and_untried_families_are_not_run():
    out = full_report()
    assert out["families"]["participant_code"]["status"] == "NOT_RUN"
    assert out["families"]["participant_code"]["not_run"].endswith("NOT_RUN")
    assert out["families"]["never_tried"]["status"] == "NOT_RUN"
    assert out["families"]["never_tried"]["not_run"] == "no_attempts_recorded"
    assert out["not_run"] == ["never_tried", "participant_code"]


def test_held_out_controls_are_required():
    with pytest.raises(TypeError):
        report.family_report([])


def test_a_finding_outside_conditions_is_refused():
    run = {
        "family": "recipe_surface",
        "attempts": [
            {"attempt": "x", "outcome": "BREACHED", "conditions": ["EXPLOIT"]}
        ],
    }
    with pytest.raises(ValueError, match="finding_condition_outside_conditions"):
        report.family_report([run], controls_held_out=())
    with pytest.raises(ValueError, match="attempt_outcome_unknown"):
        report.family_report(
            [{"family": "f", "attempts": [{"attempt": "x", "outcome": "PASS"}]}],
            controls_held_out=(),
        )


def test_one_run_per_family():
    run = {"family": "f", "attempts": [{"attempt": "x", "outcome": "HELD"}]}
    with pytest.raises(ValueError, match="two_runs_for_one_family"):
        report.family_report([run, run], controls_held_out=())


def _record(family, role, attempt, verdict, check=ARTIFACT):
    return {
        "family": family,
        "check": check,
        "role": role,
        "attempt": attempt,
        "verdict": verdict,
        "result_digest": "sha256:" + "2" * 64,
    }


def test_engine_records_keep_the_engines_own_state():
    records = [
        _record("loud", "attack", "a1", "HELD"),
        _record("loud", "specimen", "a1", "FIRED"),
        _record("loud", "control", "valid_control", "PASSED"),
        _record("silent", "attack", "b1", "HELD"),
        _record("silent", "specimen", "b1", "SILENT"),
        _record("silent", "control", "valid_control", "WRONGLY_REFUSED"),
    ]
    runs = report.runs_from_records(records)
    out = report.family_report(runs, controls_held_out=())
    assert out["families"]["loud"]["engine_state"] == "IN_PROGRESS"
    assert out["families"]["loud"]["status"] == "ATTEMPTED_COVERAGE"
    silent = out["families"]["silent"]
    assert silent["engine_state"] == "FINDING"
    assert silent["wrongful_rejection_trained"]["wrongly_refused"] == 1
    assert silent["findings"] == [
        {
            "attempt": "valid_control",
            "condition": "FAILING_TRIGGER",
            "role": "trained_control",
        }
    ]
    only_silent = report.runs_from_records(records[3:5])
    assert only_silent[0]["engine_state"] == "INCONCLUSIVE"


def test_an_engine_family_run_object_reads_like_its_records():
    class FamilyRun:
        family = StubFamily("loud", ARTIFACT)
        records = (_record("loud", "attack", "a1", "BREACHED"),)

    (run,) = [report.normalize(FamilyRun())]
    assert run["family"] == "loud" and run["check"] == ARTIFACT
    assert run["attempts"][0]["conditions"] == ["FAILING_TRIGGER"]


def test_the_battery_harness_reports_per_family_like_track_a():
    from carbon.battery import track_a

    records, coverage, _ = track_a.run(str(Path(__file__).resolve().parents[2]))
    out = report.family_report(report.runs_from_records(records), controls_held_out=())
    assert list(out["families"]) == [f.family_id for f in track_a.FAMILIES]
    for family in track_a.FAMILIES:
        line = out["families"][family.family_id]
        assert line["engine_state"] == coverage["families"][family.family_id]
        assert line["check"] == family.check
        assert line["attempts"] == sum(
            r["family"] == family.family_id and r["role"] == "attack" for r in records
        )
    assert len(out["findings"]) == len(coverage["findings"])


# -- mutations --------------------------------------------------------------------------------
MUTATIONS = {
    "timeouts_never_complete": (
        lambda m: m.setattr(report, "NOT_COMPLETED", frozenset()),
        test_a_timeout_is_never_a_pass,
    ),
    "findings_only_in_conditions": (
        lambda m: m.setattr(
            verify, "check_conditions", lambda conditions: tuple(conditions)
        ),
        test_a_finding_outside_conditions_is_refused,
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_disabling_the_protection_fails_its_test(name, monkeypatch):
    disable, guard = MUTATIONS[name]
    guard()  # passes with the protection in place
    disable(monkeypatch)
    with pytest.raises((AssertionError, pytest.fail.Exception)):
        guard()
