"""The speed stage in the grade's own lane (CV-Motor L12433, Lead's A19): contention can only slow the timed calls, so a
PASS beside other rounds is final; a FAIL while the host was contended runs ONCE more alone (the host's exclusive
timing gate) and that verdict is final; a FAIL on a quiet host is final; a solo rerun that cannot get a quiet host is
Carbon's; an outputs mismatch in either run is the candidate's; every run has a fresh identity and its own write-once
record, so a retry never replays an earlier run under a new quiet verdict; the host probe covers each run's hold window
only. Fakes only: no container runs here."""

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


def _probe(*quiet):
    """One probe per hold window, each with the given quiet verdict."""
    verdicts = iter(quiet)

    def start():
        value = next(verdicts)
        return SimpleNamespace(
            verdict=lambda: SimpleNamespace(
                quiet=value, max_worker_containers=1 if value else 3, samples=4
            )
        )

    return start


def _timed(times, called, *, hold=True):
    seconds = iter(times)

    def timed(identity):
        called.append(identity)
        if not hold:
            return _stage(next(seconds))
        # the carrier's container hold for this op (lane-less here: the watcher is still told)
        with grade_lanes.container_hold(identity=identity):
            return _stage(next(seconds))

    return timed


def _run(tmp_path, times, quiet, *, ceiling=CEILING, matches=None, hold=True):
    called = []
    answers = iter(matches or [True] * len(times))
    stage, match = retention._speed_stage(
        _timed(times, called, hold=hold),
        "n",
        ceiling,
        outputs_match=lambda stage: next(answers),
        runs_dir=tmp_path / "runs",
        probe=_probe(*quiet),
    )
    runs = [
        json.loads(path.read_text()) for path in sorted((tmp_path / "runs").glob("*"))
    ]
    return stage, match, called, runs


def test_the_first_run_is_in_lane_and_shared_and_the_rerun_exclusive():
    assert not grade_lanes.is_timing_identity(retention.SPEED_LANE_PREFIX + "n-r0")
    assert grade_lanes.is_timing_identity("single-call-n-alone0")


def test_a_pass_beside_other_rounds_is_final(tmp_path):
    stage, match, called, runs = _run(tmp_path, [1.0], [False])
    assert called == [retention.SPEED_LANE_PREFIX + "n-r0"] and match is True
    assert stage.receipt["single_call"]["call_s"][0] == 1.0
    assert [run["run"] for run in runs] == ["in_lane"] and runs[0]["passed"]


def test_a_fail_on_a_quiet_host_is_final(tmp_path):
    _, match, called, runs = _run(tmp_path, [9.0], [True])
    assert called == [retention.SPEED_LANE_PREFIX + "n-r0"] and match is True
    assert not runs[0]["passed"] and runs[0]["host_quiet"]


def test_a_fail_under_contention_runs_once_alone_and_that_verdict_is_final(tmp_path):
    for n, (alone_seconds, passed) in enumerate(((1.0, True), (9.0, False))):
        stage, _, called, runs = _run(
            tmp_path / str(n), [9.0, alone_seconds], [False, True]
        )
        assert called == [retention.SPEED_LANE_PREFIX + "n-r0", "single-call-n-alone0"]
        assert stage.receipt["single_call"]["call_s"][0] == alone_seconds
        assert [run["median_seconds"] for run in runs] == [9.0, alone_seconds]
        assert runs[1]["passed"] is passed


def test_a_solo_rerun_without_a_quiet_host_is_carbons_and_the_retry_runs_afresh(
    tmp_path,
):
    with pytest.raises(
        retention.RetentionUnavailable, match=retention.SPEED_ALONE_NOT_QUIET
    ):
        _run(tmp_path, [9.0, 9.0], [False, False])
    assert retention.SPEED_ALONE_NOT_QUIET in retention._propagated_carbon_failures()
    # the grade's retry: new identities, new records beside the old ones (never a replay)
    _, _, called, runs = _run(tmp_path, [1.0], [True])
    assert called == [retention.SPEED_LANE_PREFIX + "n-r2"]
    assert len(runs) == 3 and runs[-1]["passed"]


def test_a_mismatch_in_either_run_is_the_candidates(tmp_path):
    _, match, called, _ = _run(tmp_path / "a", [9.0], [False], matches=[False])
    assert match is False and len(called) == 1  # no rerun for a mismatch
    _, match, called, _ = _run(
        tmp_path / "b", [9.0, 1.0], [False, True], matches=[True, False]
    )
    assert match is False and len(called) == 2


def test_a_run_whose_hold_was_never_seen_is_not_quiet(tmp_path):
    # no container hold observed (a replayed op): the in-lane FAIL is treated as contended and the solo run goes ahead;
    # the solo run has no hold either, so it is not quiet: Carbon's
    with pytest.raises(
        retention.RetentionUnavailable, match=retention.SPEED_ALONE_NOT_QUIET
    ):
        _run(tmp_path, [9.0, 1.0], [], hold=False)
    runs = [
        json.loads(path.read_text()) for path in sorted((tmp_path / "runs").glob("*"))
    ]
    assert [run["host_quiet"] for run in runs] == [False, False]
    assert runs[0]["samples"] == 0


def test_without_a_ceiling_the_stage_runs_alone_as_before(tmp_path):
    _, match, called, runs = _run(tmp_path, [9.0], [], ceiling=None)
    assert called == ["single-call-n"] and match is True and runs == []


def test_motor_1_8_has_a_registered_ceiling():
    assert retention._speed_ceiling(
        SimpleNamespace(challenge_id="electric-motor-magnetics")
    ) == pytest.approx(3.3)
    assert retention._speed_ceiling(SimpleNamespace(challenge_id="no-such")) is None
