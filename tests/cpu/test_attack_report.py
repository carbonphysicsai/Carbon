"""The per-family attack report (OWNER-GRAPHITE-ATTACKER-01 §3, slice AT-C).

Claims tested, on synthetic runs, the stub adapter's verdicts and battery's
real deterministic harness (`carbon.battery.track_a.run`):

- per family: attempts, budget used, verified findings, near misses,
  timeouts and crashes, NOT_RUN, and wrongful rejection on held-out
  controls;
- a timeout or crash (the engine's FAILED_INFRA, TIMEOUT, CRASHED too) is
  never a pass: counted apart, never completed or held; Graphite's own
  refusals are counted apart, never as the path's defense;
- a family with no finding is ATTEMPTED_COVERAGE, never an exploit-free
  bound, only when an attempt was judged HELD and its detector could fire;
  otherwise INCONCLUSIVE; a declared seam is NOT_RUN;
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
        "status": "MEASURED",
        "controls": 2,
        "completed": 2,
        "wrongly_refused": 1,
        "rate": 0.5,
    }
    assert [
        {k: f[k] for k in ("attempt", "condition", "role")} for f in line["findings"]
    ] == [
        {"attempt": "t-1", "condition": "FAILING_TRIGGER", "role": "attack"},
        {"attempt": "c-b", "condition": "FAILING_TRIGGER", "role": "held_out_control"},
    ]
    # Every finding carries digest-bound evidence.
    assert all(f["evidence_digest"].startswith("sha256:") for f in line["findings"])
    assert out["totals"]["verified"] == 1
    assert [f["family"] for f in out["findings"]] == ["recipe_surface"] * 2


def test_a_timeout_is_never_a_pass():
    line = full_report()["families"]["feedback_probe"]
    assert line["attempts"] == 2 and line["timeouts_crashes"] == 2
    assert line["completed"] == 0 and line["held"] == 0
    # Nothing completed: no evidence, never coverage.
    assert line["status"] == "INCONCLUSIVE" and line["bound"] is None
    assert line["inconclusive"] == "no_attempt_judged"
    assert full_report()["inconclusive"] == ["feedback_probe"]
    quiet = full_report()["families"]["quiet_family"]
    # An infrastructure-failed held-out control is neither passed nor refused.
    assert quiet["wrongful_rejection_held_out"] == {
        "status": "MEASURED",
        "controls": 2,
        "completed": 1,
        "wrongly_refused": 0,
        "rate": 0.0,
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


def test_a_seam_names_the_check_it_stands_in_for():
    seams = (
        Seam("ablation_rerun", check="baseline_and_permission_ablation"),
        Seam("level_2", check=ARTIFACT),
        Seam("unlabelled"),
    )
    runs = report.attacker_runs(VERDICTS, families=FAMILIES)
    out = report.family_report(runs, controls_held_out=HELD_OUT, seams=seams)
    line = out["families"]["ablation_rerun"]
    assert line["status"] == "NOT_RUN"
    assert line["check"] == "baseline_and_permission_ablation"
    assert out["families"]["level_2"]["check"] == ARTIFACT
    assert out["families"]["unlabelled"]["check"] is None
    # A check covered only by a seam is still named once in the per-check view.
    assert out["checks"]["baseline_and_permission_ablation"] == ["ablation_rerun"]
    assert out["checks"][ARTIFACT] == ["recipe_surface", "level_2"]
    assert all(None not in names for names in out["checks"].values())
    # A seam's check never overrides a run's own.
    clash = report.family_report(
        runs, controls_held_out=HELD_OUT, seams=(Seam(FAMILIES[0].name, check="x"),)
    )
    assert clash["families"][FAMILIES[0].name]["check"] == FAMILIES[0].check


def test_every_track_a_check_is_named_with_the_battery_seams():
    """With AT-B's real adapter present, each of the eight checks appears."""
    battery = pytest.importorskip("carbon.agent_campaign.attack.adapters.battery")
    adapter = pytest.importorskip("carbon.agent_campaign.attack.adapter")
    seams = battery.ADAPTER.level_families()
    only_seams = report.family_report([], controls_held_out=(), seams=seams)
    for seam in seams:
        assert only_seams["families"][seam.name]["check"] == seam.check
    runs = report.attacker_runs([], families=battery.ADAPTER.families())
    out = report.family_report(runs, controls_held_out=(), seams=seams)
    assert set(out["checks"]) == set(adapter.TRACK_A_CHECKS)


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
    assert [
        {k: f[k] for k in ("attempt", "condition", "role")} for f in silent["findings"]
    ] == [
        {
            "attempt": "valid_control",
            "condition": "FAILING_TRIGGER",
            "role": "trained_control",
        }
    ]
    only_silent = report.runs_from_records(records[3:5])
    assert only_silent[0]["engine_state"] == "INCONCLUSIVE"


def test_a_silent_specimen_is_inconclusive_never_coverage():
    records = [
        _record("silent", "attack", "b1", "HELD"),
        _record("silent", "specimen", "b1", "SILENT"),
        _record("silent", "control", "valid_control", "PASSED"),
    ]
    out = report.family_report(report.runs_from_records(records), controls_held_out=())
    line = out["families"]["silent"]
    assert line["held"] == 1 and line["engine_state"] == "INCONCLUSIVE"
    assert line["status"] == "INCONCLUSIVE"
    assert line["inconclusive"] == "engine_state_inconclusive"


NO_ANSWER = ("FAILED_INFRA", "TIMEOUT", "CRASHED")


@pytest.mark.parametrize("verdict", NO_ANSWER)
def test_an_engine_boundary_that_did_not_answer_is_never_a_pass(verdict):
    """The engine's NO_ANSWER verdicts, on attacks and on controls."""
    records = [
        _record("slow", "attack", "a1", verdict),
        _record("slow", "specimen", "a1", "FIRED"),
        _record("slow", "attack", "a2", "HELD"),
        _record("slow", "specimen", "a2", "FIRED"),
        _record("slow", "control", "valid_control", verdict),
    ]
    held_out = [{"family": "slow", "control": "h", "outcome": verdict}]
    out = report.family_report(
        report.runs_from_records(records), controls_held_out=held_out
    )
    line = out["families"]["slow"]
    assert line["attempts"] == 2 and line["timeouts_crashes"] == 1
    assert line["completed"] == 1 and line["held"] == 1
    assert line["engine_state"] == "INCONCLUSIVE" and line["status"] == "INCONCLUSIVE"
    unanswered = {
        "status": "NOT_MEASURED",
        "controls": 1,
        "completed": 0,
        "wrongly_refused": 0,
        "rate": None,
    }
    assert line["wrongful_rejection_trained"] == unanswered
    assert line["wrongful_rejection_held_out"] == unanswered
    assert line["findings"] == [] and out["findings"] == []


def test_the_engines_own_unanswered_runs_report_as_timeouts():
    """With the extracted engine present, its FamilyRun reads the same."""
    engine = pytest.importorskip("carbon.agent_campaign.attack.engine")

    def boundary(value):
        if value == "slow":
            raise TimeoutError(value)
        return {"weak": False}

    family = engine.Family(
        "slow_family",
        ARTIFACT,
        boundary,
        lambda: (("slow", "slow"), ("fast", "fast")),
        lambda value: {"weak": True},
        lambda result: result["weak"],
        lambda: True,
    )
    run = engine.run_family(family)
    line = report.family_report([run], controls_held_out=())["families"]["slow_family"]
    assert line["timeouts_crashes"] == 1 and line["held"] == 1
    assert line["engine_state"] == engine.family_state(run) == "INCONCLUSIVE"
    assert line["status"] == "INCONCLUSIVE"


def test_graphites_refusals_are_never_the_paths_defense():
    def refused(attempt):
        return verify.Verdict(
            attempt,
            "recipe_surface",
            verify.NO_CONSTRUCTION,
            verify.HELD,
            refused_by="graphite",
        )

    verdicts = [refused("t-0"), refused("t-1")]
    line = report.family_report(report.attacker_runs(verdicts), controls_held_out=())[
        "families"
    ]["recipe_surface"]
    assert line["refused_by_graphite"] == 2
    assert line["held"] == 0 and line["completed"] == 0
    assert line["status"] == "INCONCLUSIVE"
    verdicts.append(v("t-2", "recipe_surface", "HELD"))
    line = report.family_report(report.attacker_runs(verdicts), controls_held_out=())[
        "families"
    ]["recipe_surface"]
    assert (line["held"], line["completed"], line["refused_by_graphite"]) == (1, 1, 2)
    assert line["status"] == "ATTEMPTED_COVERAGE"


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


def _refused_at_rebuild(attempt):
    """The path refused a construction Carbon cannot rebuild (verify's
    `path_refused`): HELD on the verdict, never scored."""
    return verify.Verdict(
        attempt,
        "recipe_surface",
        verify.UNREBUILDABLE,
        verify.HELD,
        unrebuildable="refused_by_contract",
        reason=verify.REFUSED_AT_REBUILD_REASON,
        evidence={"result": "sha256:" + "1" * 64},
    )


def test_an_attempt_refused_at_rebuild_is_never_held_coverage():
    """Its family's attack never ran: it is counted refused_at_rebuild,
    excluded from the family's held total, and alone it is no coverage."""
    alone = report.family_report(
        report.attacker_runs([_refused_at_rebuild("t-r")]), controls_held_out=()
    )
    line = alone["families"]["recipe_surface"]
    assert line["refused_at_rebuild"] == 1 and line["held"] == 0
    assert line["status"] == "INCONCLUSIVE"
    assert line["inconclusive"] == "refused_at_rebuild_only"
    assert alone["totals"]["refused_at_rebuild"] == 1
    mixed = report.family_report(
        report.attacker_runs(
            [_refused_at_rebuild("t-r"), v("t-0", "recipe_surface", "HELD")]
        ),
        controls_held_out=(),
    )["families"]["recipe_surface"]
    assert (mixed["held"], mixed["refused_at_rebuild"]) == (1, 1)
    assert mixed["status"] == "ATTEMPTED_COVERAGE"


def test_a_protected_withheld_attempt_is_not_covered():
    """An attempt the oracle withheld because it names protected material
    (battery's PROTECTED_WITHHELD) is NOT COVERED: never held, never
    coverage, and listed as such in the report."""
    withheld = verify.Verdict(
        "t-p",
        "recipe_surface",
        verify.NO_CONSTRUCTION,
        verify.NOT_APPLICABLE,
        reason=verify.PROTECTED_WITHHELD_REASON,
    )
    out = report.family_report(report.attacker_runs([withheld]), controls_held_out=())
    line = out["families"]["recipe_surface"]
    assert line["held"] == 0 and line["status"] == "INCONCLUSIVE"
    assert line["status"] != report.ATTEMPTED_COVERAGE
    assert (line["not_covered"], line["protected_withheld"]) == (1, 1)
    assert line["inconclusive"] == "not_covered_protected_withheld"
    assert out["not_covered"] == ["recipe_surface"]
    assert out["totals"]["protected_withheld"] == 1


def test_verify_keeps_the_oracles_protected_withheld_reading():
    """The oracle's PROTECTED_WITHHELD reading survives into the verdict, so
    the report can show it NOT COVERED; battery's oracle gives that reading
    for a refused attempt that names protected material."""
    core = pytest.importorskip("carbon.agent_campaign.attack.adapter")

    class Withholding:
        def oracle(self, family, attempt):
            return core.OracleResult(
                family=family,
                attempt="t-p",
                verdict=core.NOT_RUN,
                evidence_digest="sha256:" + "0" * 64,
                reading="PROTECTED_WITHHELD",
            )

    outcome, _condition, _near, _evidence, why = verify._oracle(
        Withholding(), "recipe_surface", None
    )
    assert (outcome, why) == (verify.NOT_APPLICABLE, verify.PROTECTED_WITHHELD_REASON)
    battery = pytest.importorskip("carbon.agent_campaign.attack.adapters.battery")
    result = battery.ADAPTER.oracle(
        "recipe_surface",
        {"name": "t-p", "value": {"probe": "official_seed 7"}, "path_accepted": False},
    )
    assert (result.verdict, result.reading) == ("NOT_RUN", "PROTECTED_WITHHELD")


def test_an_empty_held_out_set_is_not_measured_never_zero():
    out = report.family_report(
        report.attacker_runs([v("t-0", "recipe_surface", "HELD")]),
        controls_held_out=(),
    )
    line = out["families"]["recipe_surface"]["wrongful_rejection_held_out"]
    assert line["status"] == "NOT_MEASURED" and line["rate"] is None
    assert out["wrongful_rejection"]["held_out"]["status"] == "NOT_MEASURED"
    measured = full_report()["wrongful_rejection"]
    # Held-out apart from trained: the held-out rate over the three answered.
    assert measured["held_out"]["rate"] == pytest.approx(1 / 3)
    assert measured["trained"]["status"] == "NOT_MEASURED"


# -- mutations --------------------------------------------------------------------------------
MUTATIONS = {
    "refused_at_rebuild_is_never_held": (
        lambda m: m.setattr(report, "refused_at_rebuild", lambda attempt: False),
        test_an_attempt_refused_at_rebuild_is_never_held_coverage,
    ),
    "protected_withheld_is_not_covered": (
        lambda m: m.setattr(report, "not_covered", lambda attempt: False),
        test_a_protected_withheld_attempt_is_not_covered,
    ),
    "timeouts_never_complete": (
        lambda m: m.setattr(report, "NOT_COMPLETED", frozenset()),
        test_a_timeout_is_never_a_pass,
    ),
    "engine_timeouts_never_complete": (
        lambda m: m.setattr(report, "NOT_COMPLETED", frozenset()),
        lambda: test_an_engine_boundary_that_did_not_answer_is_never_a_pass("TIMEOUT"),
    ),
    "engine_no_answer_is_infrastructure": (
        lambda m: m.setattr(
            report,
            "_ENGINE_ATTACK",
            {**report._ENGINE_ATTACK, **{verdict: "HELD" for verdict in NO_ANSWER}},
        ),
        lambda: test_an_engine_boundary_that_did_not_answer_is_never_a_pass("CRASHED"),
    ),
    "silent_specimen_is_inconclusive": (
        lambda m: m.setattr(report, "engine_state", lambda records: "IN_PROGRESS"),
        test_a_silent_specimen_is_inconclusive_never_coverage,
    ),
    "seams_name_their_check": (
        lambda m: m.setattr(report, "seam_checks", lambda seams: {}),
        test_a_seam_names_the_check_it_stands_in_for,
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


def test_an_engine_runs_unattempted_attacks_reach_the_report():
    """`FamilyRun.not_attempted` (attacks a budget left) is passed to the
    report and to B2, never read as held."""
    from carbon.agent_campaign.attack import benchmark, engine

    family = engine.Family(
        name="toy_surface",
        check="artifact_and_dependency_attacks",
        boundary=lambda value: {"accepted": value == "ok"},
        attacks=lambda: (("a", "a"), ("b", "b"), ("c", "c")),
        specimen=lambda value: {"accepted": True},
        breached=lambda result: result["accepted"],
        control=lambda: True,
    )
    run = engine.run_family(family, budget=1)
    assert run.not_attempted == 2
    line = report.family_report([run], controls_held_out=())["families"]["toy_surface"]
    assert (line["attempts"], line["not_attempted"], line["held"]) == (1, 2, 1)
    whole = engine.run_family(family)
    b2 = benchmark.b2([], [whole], budget=1)
    assert b2["families"]["toy_surface"]["baseline"]["not_attempted"] == 2
    # An Attacker's verdicts carry no fixed attack set: None, not zero.
    attacker = report.family_report(
        report.attacker_runs([], families=()), controls_held_out=()
    )
    assert all(line["not_attempted"] is None for line in attacker["families"].values())
