"""Option A (Lead 17 Nov 2026): a build round gives its LOCAL grade lane back while its op runs on a remote GPU build box.

Builds and grades share one work lock over the door's local lanes (`direct_intake._WorkLock`). A build round whose GPU
op runs on the A100 used to hold a local lane for that whole op, so every remote build cost grading a lane. Now the
carrier gives the round's lane and round slot back around that op, its slot wait included (`grade_lanes.released`).
The round stays live (a drain still sees it) and keeps its binding meanwhile, so the op's local holds still take the
host timing gate SHARED as before. Once the op has ended it holds a local lane again (`_Taking.retake`), before any
NEW round of the door and before its next op, so its local inference and timing containers stay laned and gated.
`retake` never returns without a lane. A failed remote build keeps its own error (Carbon's, FAILED_INFRA). A second
king's-upkeep prelude never waits behind the first on its lane (`auto_grade`).
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from carbon.challenge_validator import auto_grade, grade_sequencer
from carbon.challenge_validator.direct_intake import INFLIGHT_NAME, _WorkLock
from carbon.reconstruction import grade_lanes
from carbon.reconstruction.remote_lane import RemoteLaneDown

fcntl = pytest.importorskip("fcntl")

POLL = 0.02
LANES = ("0-3", "4-7")


@pytest.fixture
def host(tmp_path):
    path = tmp_path / "host"
    path.mkdir(mode=0o700)
    return path


def _lane_free(host, index):
    import os

    fd = os.open(
        host / grade_lanes.lane_lock_name(index), os.O_RDWR | os.O_CREAT, 0o600
    )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return True
    finally:
        os.close(fd)


def _door(host, state=None):
    work = _WorkLock(host, state_dir=state, poll_s=POLL, lanes=LANES)
    # a door whose rounds take owners (`grade_sequencer.OwnerClaims`)
    work.overlap_kinds = True
    return work


class _Build:
    """One build round on its own thread: takes a lane, runs a 'remote op' inside `grade_lanes.released`, then a
    timing container (its 'local op')."""

    def __init__(self, work, *, fail=None):
        self.work, self.fail = work, fail
        self.remote, self.finish_remote = threading.Event(), threading.Event()
        self.local, self.leave = threading.Event(), threading.Event()
        self.lanes, self.error = {}, None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            with self.work.taking("advance"):
                self.lanes["before"] = grade_lanes.current()
                try:
                    with grade_lanes.released():
                        self.lanes["during"] = grade_lanes.current()
                        self.remote.set()
                        assert self.finish_remote.wait(10)
                        if self.fail is not None:
                            raise self.fail
                finally:
                    self.lanes["after"] = grade_lanes.current()
                with grade_lanes.container_hold(
                    identity="single-call-x", poll_s=POLL
                ) as held:
                    self.lanes["timing"] = held
                self.local.set()
                assert self.leave.wait(10)
        except BaseException as error:  # noqa: BLE001
            self.error = error

    def end(self):
        self.finish_remote.set()
        self.leave.set()
        self.thread.join(5)


class _Grade:
    def __init__(self, work):
        self.work = work
        self.entered, self.leave = threading.Event(), threading.Event()
        self.lane = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        with self.work.taking("grade", has_work=lambda: True):
            self.lane = grade_lanes.current()
            self.entered.set()
            assert self.leave.wait(10)

    def end(self):
        self.leave.set()
        self.thread.join(5)


def test_a_build_on_the_remote_box_holds_no_local_lane_during_its_op(host, tmp_path):
    """V2 T1 too: the released round's in-flight record stays (a drain or an in-place idle check reads busy) through
    the op, the re-take and the rest of the round, and goes only when the round ends."""
    state = tmp_path / "state"
    state.mkdir()
    work = _door(host, state)
    build = _Build(work)
    assert build.remote.wait(5)
    assert _lane_free(host, 0) and _lane_free(host, 1)
    # the binding is kept for the op's own local holds (the timing gate, SHARED), never for cores
    assert build.lanes["during"] == build.lanes["before"] is not None
    record = json.loads((state / INFLIGHT_NAME).read_text())
    assert record["kind"] == "advance"
    assert "lane" not in record and "cpuset" not in record
    build.finish_remote.set()
    assert build.local.wait(5)
    after = build.lanes["after"]
    assert after is not None and after.cpuset in LANES
    assert not _lane_free(host, after.index)
    record = json.loads((state / INFLIGHT_NAME).read_text())
    assert record["lane"] == after.index and record["cpuset"] == after.cpuset
    build.end()
    assert build.error is None
    assert not (state / INFLIGHT_NAME).exists()
    assert _lane_free(host, 0) and _lane_free(host, 1)


def test_both_local_lanes_grade_while_builds_run_on_the_remote_box(host):
    work = _door(host)
    builds = [_Build(work) for _ in range(2)]
    for build in builds:
        assert build.remote.wait(5)
    grades = [_Grade(work) for _ in range(2)]
    for grade in grades:
        assert grade.entered.wait(5)
    assert sorted(grade.lane.index for grade in grades) == [0, 1]
    # a finished remote op waits for a lane; it gets the next free one before any NEW round of the door
    builds[0].finish_remote.set()
    assert not builds[0].local.wait(0.3)
    grades[0].end()
    late = _Grade(work)
    assert builds[0].local.wait(5)
    assert builds[0].lanes["after"].index == grades[0].lane.index
    assert not late.entered.wait(0.3)
    for round_ in (*grades, *builds, late):
        round_.end()
    assert late.entered.is_set()
    assert all(build.error is None for build in builds)


def test_the_remote_ops_local_holds_still_take_the_timing_gate(host):
    """A remote op's local holds (its stage upload, `container_hold`) keep the host timing gate SHARED while its lane is
    out: a timing stage of the round now grading on that lane waits for them, as before.
    """
    work = _door(host)
    build = _Build(work)
    assert build.remote.wait(5)
    grade = _Grade(work)
    assert grade.entered.wait(5)
    upload, upload_done, timing_done = (threading.Event() for _ in range(3))

    def remote_upload():
        # the build's kept binding, as its op's own context has it
        with (
            grade_lanes.bound(build.lanes["during"]),
            grade_lanes.container_hold(identity="upload", poll_s=POLL),
        ):
            upload.set()
            assert upload_done.wait(5)

    def timing():
        with (
            grade_lanes.bound(grade.lane),
            grade_lanes.container_hold(identity="single-call-y", poll_s=POLL),
        ):
            timing_done.set()

    threading.Thread(target=remote_upload, daemon=True).start()
    assert upload.wait(5)
    threading.Thread(target=timing, daemon=True).start()
    assert not timing_done.wait(0.3)
    upload_done.set()
    assert timing_done.wait(5)
    grade.end()
    build.end()


def test_local_inference_after_the_remote_op_runs_under_a_lane_and_the_timing_gate(
    host,
):
    work = _door(host)
    build = _Build(work)
    build.finish_remote.set()
    assert build.local.wait(5)
    # the timing container was laned: `container_hold` took the host timing gate on the re-taken lane
    assert build.lanes["timing"] is not None
    assert build.lanes["timing"] == build.lanes["after"]
    build.end()


def test_a_failed_remote_build_keeps_its_carbon_error_and_retakes_a_lane_first(host):
    work = _door(host)
    failure = RemoteLaneDown(b"remote_gpu_build_lost")
    build = _Build(work, fail=failure)
    assert build.remote.wait(5)
    build.end()
    # unchanged: the carrier's FAILED_INFRA (Carbon's, never charged)
    assert build.error is failure
    assert build.lanes["after"] is not None  # the round's exit path ran with a lane
    assert _lane_free(host, 0) and _lane_free(host, 1)


def test_a_retake_that_fails_never_goes_on_without_a_lane(host, monkeypatch):
    """V2 B1: a failure taking a lane again is logged and tried again; the round never runs its next op bound to the
    lane it gave back, and nothing leaks the lane lock."""
    work = _door(host)
    real, failures = work._take_local_lane, []

    def flaky():
        if len(failures) < 3:
            failures.append(1)
            raise RuntimeError("holder record unwritable")
        return real()

    monkeypatch.setattr(work, "_take_local_lane", flaky)
    build = _Build(work)
    assert build.remote.wait(5)
    build.finish_remote.set()
    assert build.local.wait(5)
    assert len(failures) == 3
    after = build.lanes["after"]
    assert after is not None and not _lane_free(host, after.index)
    build.end()
    assert build.error is None
    assert _lane_free(host, 0) and _lane_free(host, 1)


def test_a_holder_record_failure_lets_the_lane_lock_go(host, monkeypatch):
    work = _door(host)

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(grade_lanes, "write_holder", broken)
    with pytest.raises(OSError):
        work._take_local_lane()
    assert _lane_free(host, 0) and _lane_free(host, 1)


def test_a_grade_round_a_one_lane_door_or_a_door_without_overlap_keeps_its_lane(
    host,
):
    def lane_inside(work, kind):
        with work.taking(kind, has_work=lambda: True):
            before = grade_lanes.current()
            with grade_lanes.released():
                return before, _lane_free(host, before.index)

    before, free = lane_inside(_door(host), "grade")
    assert before is not None and not free
    plain = _WorkLock(host, poll_s=POLL, lanes=LANES)  # overlap_kinds False
    before, free = lane_inside(plain, "advance")
    assert before is not None and not free
    one = _WorkLock(host, poll_s=POLL)
    with one.taking("advance"), grade_lanes.released():
        assert not _lane_free(host, 0)  # one-lane mode holds every lane, as before
    with grade_lanes.released():  # outside any round: nothing
        assert grade_lanes.current() is None


def _prelude_grader(claims, ran):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.sequencer = grade_sequencer.Sequencer()
    grader.owner_claims = claims
    grader.chain_degraded = lambda: False
    grader._prelude_due = lambda pending: True
    grader.pending = list
    grader._settle_queue_places = lambda: ran.append("places")
    grader._upkeep_deferred = lambda: False
    grader._king_upkeep = lambda: ran.append("king")
    grader._resume_paused_crowns = lambda: None
    grader._apply_due_retries = lambda idle: None
    return grader


def test_a_second_prelude_never_waits_behind_the_first_on_its_lane():
    """Two grade rounds find the king's upkeep due while a build round (its lane given back) holds an owner: the first
    waits for that owner; the second goes on at once (it would otherwise hold the other lane the build needs back).
    """
    claims = grade_sequencer.OwnerClaims()
    assert claims.try_claim("builder")
    ran = []
    grader = _prelude_grader(claims, ran)
    first = threading.Thread(target=grader._run_once, daemon=True)
    first.start()
    deadline = time.monotonic() + 5
    while not claims._exclusive and time.monotonic() < deadline:
        time.sleep(0.01)
    assert claims._exclusive  # the first now waits for the build's owner
    second_done = threading.Event()
    second = threading.Thread(
        target=lambda: (grader._run_once(), second_done.set()), daemon=True
    )
    second.start()
    assert second_done.wait(2) and ran == []
    claims.release("builder")
    first.join(5)
    assert ran == ["places", "king"]
