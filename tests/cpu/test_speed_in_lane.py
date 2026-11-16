"""The speed stage in the grade's own lane (CV-Motor L12433, Lead's A19): contention can only slow the timed calls, so a
PASS beside other rounds is final; a FAIL while the host was contended runs ONCE more alone (the host's exclusive
timing gate) and that verdict is final; a FAIL on a quiet host is final; a solo rerun that cannot get a quiet host is
Carbon's. Fakes only: no container runs here."""

from __future__ import annotations

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
    verdicts = iter(quiet)

    def start():
        value = next(verdicts)
        return SimpleNamespace(
            verdict=lambda: SimpleNamespace(
                quiet=value, max_worker_containers=1 if value else 3, samples=4
            )
        )

    return start


def _run(times, quiet, ceiling=CEILING):
    called, kept = [], []
    seconds = iter(times)

    def timed(identity):
        called.append(identity)
        return _stage(next(seconds))

    stage = retention._speed_stage(
        timed, "n", ceiling, record=kept.append, probe=_probe(*quiet)
    )
    return stage, called, kept


def test_the_first_run_is_in_lane_and_shared():
    assert not grade_lanes.is_timing_identity(retention.SPEED_LANE_PREFIX + "n")
    assert grade_lanes.is_timing_identity("single-call-n-alone")


def test_a_pass_beside_other_rounds_is_final():
    stage, called, kept = _run([1.0], [False])
    assert called == [retention.SPEED_LANE_PREFIX + "n"]
    assert stage.receipt["single_call"]["call_s"][0] == 1.0
    assert [run["run"] for run in kept[0]] == ["in_lane"] and kept[0][0]["passed"]


def test_a_fail_on_a_quiet_host_is_final():
    _, called, kept = _run([9.0], [True])
    assert called == [retention.SPEED_LANE_PREFIX + "n"]
    assert not kept[0][0]["passed"] and kept[0][0]["host_quiet"]


def test_a_fail_under_contention_runs_once_alone_and_that_verdict_is_final():
    for alone_seconds, passed in ((1.0, True), (9.0, False)):
        stage, called, kept = _run([9.0, alone_seconds], [False, True])
        assert called == [retention.SPEED_LANE_PREFIX + "n", "single-call-n-alone"]
        assert stage.receipt["single_call"]["call_s"][0] == alone_seconds
        # both medians kept
        assert [run["median_seconds"] for run in kept[0]] == [9.0, alone_seconds]
        assert kept[0][1]["passed"] is passed


def test_a_solo_rerun_without_a_quiet_host_is_carbons():
    called, kept = [], []
    seconds = iter([9.0, 9.0])

    def timed(identity):
        called.append(identity)
        return _stage(next(seconds))

    with pytest.raises(
        retention.RetentionUnavailable, match=retention.SPEED_ALONE_NOT_QUIET
    ):
        retention._speed_stage(
            timed, "n", CEILING, record=kept.append, probe=_probe(False, False)
        )
    assert len(called) == 2 and [run["run"] for run in kept[0]] == [
        "in_lane",
        "alone",
    ]


def test_without_a_ceiling_the_stage_runs_alone_as_before():
    _, called, kept = _run([9.0], [], ceiling=None)
    assert called == ["single-call-n"] and kept == []


def test_motor_1_8_has_a_registered_ceiling():
    assert retention._speed_ceiling(
        SimpleNamespace(challenge_id="electric-motor-magnetics")
    ) == pytest.approx(3.3)
    assert retention._speed_ceiling(SimpleNamespace(challenge_id="no-such")) is None
