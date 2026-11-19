"""King statistics from the official grade (owner via Lead, 19 Nov 2026: "why can we not just use the actual results
from the exam"): the receiver stages a keep around its producer call (`grade_breakdown.staged`), the pool grade offers
the values it already computed, and the private breakdown is written from them with no remeasuring.

Claims:
- the kept sets' A and D, the menu tasks' D, the accuracy aggregates and the speed seconds ARE the grade's own numbers;
- a staged grade returns exactly what an unstaged one does (the grade, its record and its score never move);
- nothing staged keeps nothing; two measures in one stage keep nothing (ambiguous); an offer never raises into a grade;
- the receiver's writer takes A, D and the gates from the official benchmark, and a failure there never stops a grade.

Every set, case and row is the pool fixtures' SYNTHETIC material.
"""

from __future__ import annotations

import json
import os
import statistics
from types import SimpleNamespace

import pytest
from test_pool_accuracy_only import _accuracy_sets, _grade
from test_pool_exam import FAST
from test_pool_multiclass_regions import (  # noqa: F401  (geometric_v1_stand_in is a fixture)
    geometric_v1_stand_in,
)

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.scoring import grade_breakdown as gb
from carbon.scoring import pool_menu
from carbon.scoring.physical_dual_pack import METRICS

TASK = "rtsk_" + "b" * 64
EXAM = "sha256:" + "3" * 64


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_the_kept_values_are_the_grades_own_numbers():
    the_sets = _accuracy_sets()
    with gb.staged() as keep:
        result, _capture = _grade(the_sets)
    values = gb.kept(keep)
    sets = values["sets"]
    assert len(sets) == result["pool"]["sets"]
    assert statistics.fmean(s["A"] for s in sets.values()) == result["A"]
    assert statistics.fmean(s["D"] for s in sets.values()) == result["D"]
    assert [0.5 * s["A"] + 0.5 * s["D"] for s in sets.values()] == result["pool"][
        "set_totals"
    ]
    assert [s["rows"] for s in sets.values()] == [len(group) for group in the_sets]
    # the menu tasks: the custody record's d per task, with the zero and oracle score_task computed
    record = {t["task_id"]: t["d"] for t in result["pool"]["menu"]["tasks"]}
    assert {t["task"]: t["D"] for t in values["tasks"]} == record
    assert all(t["Z"] < t["oracle"] for t in values["tasks"])
    # the accuracy record's per class x output aggregates, no per-case value
    rows = result["pool"]["accuracy"]["rows"]
    assert values["outputs"] == [
        {k: r[k] for k in ("class", "output", "range", "n", "median", "p90")}
        for r in rows
    ]
    speed = result["pool"]["speed"]
    assert values["speed"] == {
        "call_seconds": list(FAST),
        "median_seconds": speed["median_seconds"],
        "ceiling_seconds": speed["ceiling_seconds_per_design"],
        "passed": speed["passed"],
    }
    # and the document checks
    document = gb.breakdown(
        challenge_id="electric-motor-magnetics",
        challenge_version="1.8",
        submission_id=TASK,
        exam_key=EXAM,
        contract_ids={},
        rule_flags={k: bool(v) for k, v in result["gates"].items()},
        halves={"A": result["A"], "D": result["D"]},
        clock=1_800_000_000.0,
        sets=values["sets"],
        tasks=values["tasks"],
        outputs=values["outputs"],
        speed={**values["speed"], "lane": None},
    )
    assert document["outputs"] == values["outputs"]


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_a_staged_grade_returns_exactly_what_an_unstaged_one_does():
    the_sets = _accuracy_sets()
    plain, plain_capture = _grade(the_sets)
    with gb.staged():
        staged, staged_capture = _grade(the_sets)
    assert json.dumps(staged, sort_keys=True, default=repr) == json.dumps(
        plain, sort_keys=True, default=repr
    )
    assert staged_capture.keys() == plain_capture.keys()


@pytest.mark.usefixtures("geometric_v1_stand_in")
def test_nothing_staged_keeps_nothing_and_two_measures_are_ambiguous():
    the_sets = _accuracy_sets()
    gb.offer("sets", lambda: 1 / 0)  # nothing staged: a no-op, nothing built
    with gb.staged() as keep:
        pass
    assert gb.kept(keep) is None
    with gb.staged() as keep:
        _grade(the_sets)
        _grade(the_sets)
    with pytest.raises(gb.GradeBreakdownRefused) as refused:
        gb.kept(keep)
    assert refused.value.code == "grade_breakdown_more_than_one_measure"


def test_an_offer_that_fails_marks_the_keep_and_never_raises():
    with gb.staged() as keep:
        gb.offer("sets", lambda: 1 / 0)
        gb.offer("measure", None)
    with pytest.raises(gb.GradeBreakdownRefused) as refused:
        gb.kept(keep)
    assert refused.value.code == "grade_breakdown_offer_failed"


def test_a_row_dependent_menu_keeps_its_zero_d_with_no_zero_or_oracle(monkeypatch):
    offered = []
    monkeypatch.setattr(gb, "offer", lambda name, value: offered.append((name, value)))
    pool_menu._offer_tasks([("pool-1/t1", 0.0, None, None)])
    ((name, build),) = offered
    assert name == "tasks"
    assert build() == [{"task": "pool-1/t1", "D": 0.0, "Z": None, "oracle": None}]


def _benchmark(a=0.4, d=0.2, gates=None):
    return {
        "physics_contract_digest": "sha256:" + "4" * 64,
        "measurement_contract_digest": "sha256:" + "5" * 64,
        "models": [
            {
                "gates": gates or {"physics": "PASS", "speed": "PASS"},
                "measurements": {
                    METRICS["A"]: {"value": a},
                    METRICS["D"]: {"value": d},
                },
            }
        ],
    }


def _keep(values):
    with gb.staged() as keep:
        for name, value in values.items():
            gb.offer(name, value)
        gb.offer("measure", None)
    return keep


ADAPTER = SimpleNamespace(
    challenge_id="electric-motor-magnetics", challenge_version="1.8"
)
SNAPSHOT = SimpleNamespace(manifest_digest=EXAM)


def _private(tmp_path):
    directory = tmp_path / (TASK + ".evaluation")
    directory.mkdir(mode=0o700)
    return directory


def test_the_receiver_writes_the_official_halves_and_gates_beside_the_measurement(
    tmp_path,
):
    directory = _private(tmp_path)
    keep = _keep(
        {
            "sets": {"set0": {"A": 0.9, "D": 0.3, "rows": 4}},
            "tasks": [{"task": "pool-1/t1", "D": 0.3, "Z": 0.1, "oracle": 0.8}],
        }
    )
    # a producer gate after the measure (Motor 1.8's subset repeat) is what the halves and flags say
    retention._keep_grade_breakdown(
        keep,
        directory,
        ADAPTER,
        TASK,
        SNAPSHOT,
        _benchmark(a=None, d=0.0, gates={"physics": "PASS", "native_motor_valid": "FAIL"}),
        "sha256:" + "6" * 64,
    )
    document = json.loads((directory / (TASK + gb.SUFFIX)).read_bytes())
    assert document["halves"] == {"A": None, "D": 0.0}
    assert document["rule_flags"] == {"physics": True, "native_motor_valid": False}
    assert document["sets"] == {"set0": {"A": 0.9, "D": 0.3, "rows": 4}}
    assert document["contract_ids"]["dual_measurement"] == "sha256:" + "6" * 64
    assert document["outputs"] is None and document["speed"] is None
    if os.name == "posix":
        assert (directory / (TASK + gb.SUFFIX)).stat().st_mode & 0o077 == 0


def test_a_receiver_breakdown_failure_never_stops_the_grade(tmp_path, monkeypatch):
    lines = []
    import carbon.battery.intake as intake

    monkeypatch.setattr(intake, "log", lambda event, **f: lines.append((event, f)))
    directory = _private(tmp_path)
    bad = _keep({"sets": {"set0": {"A": float("nan"), "D": 0.1, "rows": 1}}})
    retention._keep_grade_breakdown(
        bad, directory, ADAPTER, TASK, SNAPSHOT, _benchmark(), "sha256:" + "6" * 64
    )
    assert lines == [
        ("grade_breakdown_unwritten", {"task": TASK, "code": "grade_breakdown_sets_invalid"})
    ]
    assert not (directory / (TASK + gb.SUFFIX)).exists()
    # no pool grade inside the stage: nothing written, nothing logged
    with gb.staged() as empty:
        pass
    retention._keep_grade_breakdown(
        empty, directory, ADAPTER, TASK, SNAPSHOT, _benchmark(), "sha256:" + "6" * 64
    )
    assert len(lines) == 1
