"""BUILD LANES (Lead 17 Nov 2026): a door's build rounds take its LOCAL lanes only, so its remote grade lanes always grade.

`direct_intake._WorkLock.local_builds`: one build round per local lane plus one per remote GPU build slot (those wait on
the remote box with their lane given back, `grade_lanes.released`); at most one build round per local lane holds a round
slot (`_build_slots`), so a grade round always finds a lane; grade rounds try the remote lanes first; a build round
waiting for a local lane never sleeps holding the door's ``_lock``. A door with fewer than two local lanes is unchanged.
"""

from __future__ import annotations

import threading

import pytest

from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.direct_intake import _WorkLock
from carbon.reconstruction import grade_lanes, remote_gpu_build, remote_lane

pytest.importorskip("fcntl")

POLL = 0.02
LOCAL = ("0-3", "4-7")
REMOTE = tuple(
    remote_lane.RemoteSpec(f"ssh://carbon-grade@box{n}.example", "0-3", "/srv/gb")
    for n in range(2)
)


@pytest.fixture
def host(tmp_path):
    path = tmp_path / "host"
    path.mkdir(mode=0o700)
    return path


def _door(host, lanes=(*LOCAL, *REMOTE), extra=0):
    work = _WorkLock(host, poll_s=POLL, lanes=lanes)
    work.overlap_kinds = True
    rounds = work.local_builds(extra)
    return work, rounds


class _Round:
    def __init__(self, work, kind):
        self.work, self.kind = work, kind
        self.entered, self.leave = threading.Event(), threading.Event()
        self.lane = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        with self.work.taking(self.kind, has_work=lambda: True):
            self.lane = grade_lanes.current()
            self.entered.set()
            assert self.leave.wait(10)

    def end(self):
        self.leave.set()
        self.thread.join(5)


def test_build_rounds_are_one_per_local_lane_plus_the_remote_build_slots(host):
    work, rounds = _door(host, extra=4)
    assert rounds == 6 and work.builds_local
    # local lanes only: the same count; a remote-only door or a one-lane door keeps one build round per usable lane
    plain = _WorkLock(host, poll_s=POLL, lanes=LOCAL)
    assert plain.local_builds(4) == 6 and plain.builds_local
    remote_only = _WorkLock(
        host, poll_s=POLL, lanes=(*LOCAL, *REMOTE), remote_only=True
    )
    assert remote_only.local_builds(4) == 2 and not remote_only.builds_local
    one = _WorkLock(host, poll_s=POLL)
    assert one.local_builds(4) == 1 and not one.builds_local


def test_builds_take_local_lanes_only_and_grades_the_remote_lanes_first(host):
    work, _ = _door(host)
    grades = [_Round(work, "grade") for _ in range(2)]
    for grade in grades:
        assert grade.entered.wait(5)
    assert sorted(grade.lane.index for grade in grades) == [2, 3]
    builds = [_Round(work, "advance") for _ in range(2)]
    for build in builds:
        assert build.entered.wait(5)
    assert sorted(build.lane.index for build in builds) == [0, 1]
    assert all(build.lane.docker_host is None for build in builds)
    for round_ in (*grades, *builds):
        round_.end()


def test_a_third_build_waits_for_a_local_lane_while_grades_keep_the_remote_lanes(host):
    work, _ = _door(host)
    builds = [_Round(work, "advance") for _ in range(2)]
    for build in builds:
        assert build.entered.wait(5)
    third = _Round(work, "advance")
    assert not third.entered.wait(
        0.3
    )  # no third build slot: it never holds a round slot meanwhile
    grades = [_Round(work, "grade") for _ in range(2)]
    for grade in grades:
        assert grade.entered.wait(5)  # both remote lanes grade
    builds[0].end()
    assert third.entered.wait(5) and third.lane.docker_host is None
    for round_ in (builds[1], third, *grades):
        round_.end()


def test_a_build_waiting_for_a_busy_local_lane_never_stops_grades_starting(host):
    """All four lanes grading; one remote grade ends; a build then holds a round slot but finds no local lane free, and
    waits WITHOUT the door's lock: a new grade round still starts on the free remote lane.
    """
    work, _ = _door(host)
    grades = [_Round(work, "grade") for _ in range(4)]
    for grade in grades:
        assert grade.entered.wait(5)
    remote = [g for g in grades if g.lane.docker_host is not None]
    local = [g for g in grades if g.lane.docker_host is None]
    assert len(remote) == 2 and len(local) == 2
    remote[0].end()
    build = _Round(work, "advance")
    assert not build.entered.wait(0.3)
    # the build's slot is the only free one: give a grade a slot by ending a remote grade too
    remote[1].end()
    late = _Round(work, "grade")
    assert late.entered.wait(5) and late.lane.docker_host is not None
    assert not build.entered.wait(0.2)
    local[0].end()
    assert build.entered.wait(5) and build.lane.index == local[0].lane.index
    for round_ in (build, late, local[1]):
        round_.end()


def test_the_build_round_count_reads_the_box_pool_s_most_slots(monkeypatch):
    class _Intake:
        class challenge:
            challenge_id, version = "electric-motor-magnetics", "1.8"

    seen = []

    def slots(challenge_id, version, **kwargs):
        seen.append((challenge_id, version))
        return 12

    monkeypatch.setattr(remote_gpu_build, "door_build_slots", slots)
    assert direct_intake._remote_build_slots(_Intake) == 12
    assert seen == [("electric-motor-magnetics", "1.8")]

    def broken(*a, **k):
        raise ValueError("remote_gpu_build_device_kind")

    monkeypatch.setattr(remote_gpu_build, "door_build_slots", broken)
    assert direct_intake._remote_build_slots(_Intake) == 0


class _Build:
    """A build round that gives its lane back for a 'remote op' (`grade_lanes.released`) and then holds one again."""

    def __init__(self, work):
        self.work = work
        self.remote, self.finish, self.local, self.leave = (
            threading.Event() for _ in range(4)
        )
        self.lane = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        with self.work.taking("advance"):
            with grade_lanes.released():
                self.remote.set()
                assert self.finish.wait(10)
            self.lane = grade_lanes.current()
            self.local.set()
            assert self.leave.wait(10)

    def end(self):
        self.finish.set()
        self.leave.set()
        self.thread.join(5)


def test_a_waiting_retake_holds_back_new_builds_never_new_grades(host):
    """Both build slots held by builds in a local phase; a third build's remote op ends and it waits to re-take: a new
    grade still starts on a remote lane, a new build waits behind the re-take."""
    work, _ = _door(host, extra=4)
    remote_build = _Build(work)
    assert remote_build.remote.wait(5)  # its lane and both slots are back
    local = [_Round(work, "advance") for _ in range(2)]
    for build in local:
        assert build.entered.wait(5)
    remote_build.finish.set()
    assert not remote_build.local.wait(0.3)  # no build slot free
    grade = _Round(work, "grade")
    assert grade.entered.wait(5) and grade.lane.docker_host is not None
    late = _Round(work, "advance")
    local[0].end()
    assert remote_build.local.wait(5)
    assert not late.entered.wait(0.3)
    for round_ in (remote_build, local[1], grade, late):
        round_.end()
    assert late.entered.is_set()


def test_a_draining_door_gives_up_a_build_waiting_for_a_local_lane(host, tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    work = _WorkLock(host, state_dir=state, poll_s=POLL, lanes=(*LOCAL, *REMOTE))
    work.overlap_kinds = True
    work.local_builds(0)
    grades = [_Round(work, "grade") for _ in range(4)]
    for grade in grades:
        assert grade.entered.wait(5)
    grades[0].end()
    declined = []

    def build():
        try:
            with work.taking("advance"):
                pass
        except direct_intake.WorkDeclined as refused:
            declined.append(refused.reason)

    thread = threading.Thread(target=build, daemon=True)
    thread.start()
    thread.join(0.3)
    assert thread.is_alive()  # holds a slot, waits for a local lane without the lock
    (state / direct_intake.DRAIN_NAME).touch()
    thread.join(5)
    assert declined == ["draining"]
    (state / direct_intake.DRAIN_NAME).unlink()
    late = _Round(work, "grade")  # every slot came back: a grade starts
    assert late.entered.wait(5)
    for round_ in (*grades[1:], late):
        round_.end()


def test_a_build_away_on_the_remote_box_never_lets_grades_starve_a_new_build(tmp_path):
    """Live 116 (3326c78b, 17 Nov): 4 A100 slots, but building_now stayed at 2. A build away on the A100 (its lane given
    back) counted as a LIVE build for the kind fairness, so back-to-back grade rounds never stood back for a build waiting
    to START (it needs a local lane first). A round whose lane is out is no longer live for the fairness: the next free
    lane goes to the waiting build, not to a new grade round. Five rounds: the old race lost to the grade half the time.
    """
    for attempt in range(5):
        host = tmp_path / f"host{attempt}"
        host.mkdir(mode=0o700)
        work = _WorkLock(host, poll_s=POLL, lanes=LOCAL)
        work.overlap_kinds = True
        assert work.local_builds(4) == 6
        away = _Build(work)
        assert away.remote.wait(5)  # on the A100: no lane, no slot
        grades = [_Round(work, "grade") for _ in range(2)]
        for grade in grades:
            assert grade.entered.wait(5)
        waiting_build = _Round(work, "advance")
        waiting_grade = _Round(work, "grade")
        assert not waiting_build.entered.wait(0.2)
        assert not waiting_grade.entered.wait(0.1)
        grades[0].end()
        assert waiting_build.entered.wait(5)  # the freed lane goes to the build
        assert not waiting_grade.entered.wait(0.2)
        for round_ in (grades[1], waiting_build, away, waiting_grade):
            round_.end()
        assert waiting_grade.entered.is_set()


def test_a_grade_never_stands_back_while_a_remote_lane_it_can_grade_on_is_free(host):
    """Review: builds use LOCAL lanes only, so a grade stands back for a waiting build only when it would take a local
    lane itself. A free remote lane is graded on at once; the waiting build gets the next free LOCAL lane.
    """
    work, _ = _door(host, extra=4)
    away = _Build(work)
    assert away.remote.wait(5)
    grades = [_Round(work, "grade") for _ in range(4)]
    for grade in grades:
        assert grade.entered.wait(5)
    remote = [g for g in grades if g.lane.docker_host is not None]
    local = [g for g in grades if g.lane.docker_host is None]
    waiting_build = _Round(work, "advance")
    assert not waiting_build.entered.wait(0.2)
    remote[0].end()
    late = _Round(work, "grade")
    assert late.entered.wait(5) and late.lane.docker_host is not None
    assert not waiting_build.entered.wait(0.2)
    local[0].end()
    assert waiting_build.entered.wait(5) and waiting_build.lane.docker_host is None
    for round_ in (remote[1], local[1], late, waiting_build, away):
        round_.end()
