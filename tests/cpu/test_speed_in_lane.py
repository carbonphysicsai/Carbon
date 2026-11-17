"""The speed stage in the grade's own lane (owner, 17 Nov 2026: lane core pinning is the timing protection). The timed
calls run ONCE, in the grade's own lane on its pinned cores, beside the other lanes; that verdict is final, pass or fail.
No timing gate and no solo rerun. An outputs mismatch is the candidate's; every run has a fresh identity and its own
write-once record, so a retry never replays an earlier run. Fakes only: no container runs here.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import lean_recipe_retention as retention
from carbon.reconstruction import grade_lanes

CEILING = 3.3


def _stage(seconds):
    return SimpleNamespace(
        receipt={"single_call": {"call_s": [seconds] * 20}},
        worker_operation="op-" + str(seconds),
    )


def _run(tmp_path, times, *, ceiling=CEILING, matches=None):
    called = []
    seconds = iter(times)
    answers = iter(matches or [True] * len(times))

    def timed(identity):
        called.append(identity)
        return _stage(next(seconds))

    stage, match = retention._speed_stage(
        timed,
        "n",
        ceiling,
        outputs_match=lambda stage: next(answers),
        runs_dir=tmp_path / "runs",
    )
    runs = [
        json.loads(path.read_text()) for path in sorted((tmp_path / "runs").glob("*"))
    ]
    return stage, match, called, runs


def test_the_run_is_in_lane_never_a_timing_identity():
    assert not grade_lanes.is_timing_identity(retention.SPEED_LANE_PREFIX + "n-r0")


@pytest.mark.parametrize(("seconds", "passed"), [(1.0, True), (9.0, False)])
def test_one_run_in_the_lane_and_its_verdict_is_final(tmp_path, seconds, passed):
    stage, match, called, runs = _run(tmp_path, [seconds])
    assert called == [retention.SPEED_LANE_PREFIX + "n-r0"] and match is True
    assert stage.receipt["single_call"]["call_s"][0] == seconds
    assert [run["run"] for run in runs] == ["in_lane"]
    assert runs[0]["passed"] is passed and runs[0]["median_seconds"] == seconds
    assert runs[0]["schema"] == "carbon.lean-recipe.speed-run.v2"
    assert "host_quiet" not in runs[0]  # no contention probe decides anything


def test_a_mismatch_is_the_candidates_and_never_rerun(tmp_path):
    _, match, called, _ = _run(tmp_path, [9.0], matches=[False])
    assert match is False and len(called) == 1


def test_a_retry_runs_afresh_beside_the_earlier_record(tmp_path):
    _run(tmp_path, [9.0])
    _, _, called, runs = _run(tmp_path, [1.0])
    assert called == [retention.SPEED_LANE_PREFIX + "n-r1"]
    assert [run["median_seconds"] for run in runs] == [9.0, 1.0]


def test_without_a_ceiling_the_stage_runs_once_as_before(tmp_path):
    _, match, called, runs = _run(tmp_path, [9.0], ceiling=None)
    assert called == ["single-call-n"] and match is True and runs == []


def test_the_historical_solo_code_still_reads_as_carbons():
    assert retention.SPEED_ALONE_NOT_QUIET in retention._propagated_carbon_failures()


def test_motor_1_8_has_a_registered_ceiling():
    assert retention._speed_ceiling(
        SimpleNamespace(challenge_id="electric-motor-magnetics")
    ) == pytest.approx(3.3)
    assert retention._speed_ceiling(SimpleNamespace(challenge_id="no-such")) is None
