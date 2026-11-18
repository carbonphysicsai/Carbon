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


def test_grades_never_take_a_local_lane_while_the_door_has_remote_grade_lanes(host):
    """Live 116 (7aeaa273, 17 Nov 22:2xZ): with every remote lane grading, grades fell back to the local lanes and held
    them for minutes, so the A100's builds found no local lane to start or re-take (A100 idle, 69 builds queued). Now a
    grade never takes a local lane: it waits for a REMOTE lane without a round slot, or gives its round up (never
    holding the door's lock or a slot), and builds take the local lanes at once.
    """
    work, _ = _door(host)
    grades = [_Round(work, "grade") for _ in range(2)]
    for grade in grades:
        assert grade.entered.wait(5) and grade.lane.docker_host is not None
    outcome = []

    def third():
        try:
            with work.taking("grade", has_work=lambda: True):
                outcome.append(grade_lanes.current())
        except direct_intake.WorkDeclined as declined:
            outcome.append(declined.reason)

    thread = threading.Thread(target=third, daemon=True)
    thread.start()
    builds = [_Round(work, "advance") for _ in range(2)]
    for build in builds:
        assert build.entered.wait(5) and build.lane.docker_host is None
    grades[0].end()
    thread.join(5)
    # it got the freed REMOTE lane, or gave its round up: never a local lane
    assert outcome and (
        outcome[0] == "no_grade_lane"
        or (outcome[0] is not None and outcome[0].docker_host is not None)
    )
    for round_ in (grades[1], *builds):
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


def test_with_remote_build_slots_a_build_starts_with_no_lane(host):
    """Owner, 17 Nov 2026 ("make them independent of each other"): with remote GPU build slots and remote grade lanes,
    a build round STARTS holding no lane and no slot, whatever the grades hold: every lane it could take is busy here
    (two remote grades, a grade on the unreserved local lane, a build's local part on the reserved one).
    """
    work, _ = _door(host, extra=4)
    assert work.builds_laneless and work._reserved_local == (0,)
    first = _Build(work)
    assert first.remote.wait(5)
    first.finish.set()
    assert (
        first.local.wait(5) and first.lane.index == 0
    )  # its local part: the reserved lane
    grades = [_Round(work, "grade") for _ in range(3)]
    for grade in grades:
        assert grade.entered.wait(5)
    assert sorted(g.lane.index for g in grades) == [1, 2, 3]  # never the reserved lane
    late = _Build(work)
    assert late.remote.wait(5)  # started: no lane needed
    for round_ in (*grades, first, late):
        round_.end()


def test_a_draining_door_gives_up_a_grade_waiting_for_a_remote_lane(host, tmp_path):
    """A grade waiting for a remote lane (`_grades_remote_only`) holds no slot and gives up on a drain."""
    state = tmp_path / "state"
    state.mkdir()
    work = _WorkLock(host, state_dir=state, poll_s=POLL, lanes=(*LOCAL, *REMOTE))
    work.overlap_kinds = True
    work.local_builds(0)
    grades = [_Round(work, "grade") for _ in range(2)]
    for grade in grades:
        assert grade.entered.wait(5)
    declined = []

    def grade():
        try:
            with work.taking("grade", has_work=lambda: True):
                pass
        except direct_intake.WorkDeclined as refused:
            declined.append(refused.reason)

    thread = threading.Thread(target=grade, daemon=True)
    thread.start()
    thread.join(0.3)
    builds = [_Round(work, "advance") for _ in range(2)]
    for build in builds:
        assert build.entered.wait(5)  # its wait never held the slots the builds need
    (state / direct_intake.DRAIN_NAME).touch()
    thread.join(5)
    # it waited for a remote lane without a slot and the drain ended it, or it gave its round up at once
    assert declined in (["draining"], ["no_grade_lane"])
    (state / direct_intake.DRAIN_NAME).unlink()
    for round_ in (*grades, *builds):
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


def test_a_build_back_from_the_remote_box_takes_the_reserved_lane_while_grades_wait(
    host,
):
    """Grades fill the remote lanes and the unreserved local lane, never the builds' reserved one: the A100's build
    holds a local lane for its local part at once, and a fourth grade waits for a lane of its own.
    """
    work, _ = _door(host, extra=4)
    away = _Build(work)
    assert away.remote.wait(5)
    grades = [_Round(work, "grade") for _ in range(4)]
    entered = [g for g in grades if g.entered.wait(1)]
    assert sorted(g.lane.index for g in entered) == [1, 2, 3]
    away.finish.set()
    assert away.local.wait(5) and away.lane.index == 0  # the reserved lane, at once
    for round_ in (*grades, away):
        round_.end()


def test_a_laneless_builds_local_op_holds_a_local_lane_first(host):
    """An op on this host (`grade_lanes.laned`): the laneless build round holds a LOCAL lane first, the reserved one,
    keeps it for the rest of the round, and the binding ends with the round (never a container unpinned).
    """
    work, _ = _door(host, extra=4)
    with work.taking("advance"):
        assert grade_lanes.current() is None
        with grade_lanes.laned():
            lane = grade_lanes.current()
        assert lane is not None and lane.docker_host is None and lane.index == 0
        assert grade_lanes.current() == lane
    assert grade_lanes.current() is None


def test_a_laneless_build_container_chosen_outside_the_carrier_gets_a_local_lane(host):
    """V2's challenge (17 Nov 2026): a container a laneless build round starts outside the carrier's op path (the
    library/overlay environment build, an image check) has its cores chosen by `host_execution.resolve_cpuset`, which
    first holds the round a LOCAL lane (the builds' reserved lane): never the host record's or derived cores, which may
    be a grade lane's."""
    from carbon.reconstruction import host_execution

    work, _ = _door(host, extra=4)
    with work.taking("advance"):
        assert grade_lanes.current() is None
        cpuset = host_execution.resolve_cpuset(logical_cpus=16, count=4)
        assert cpuset == "0-3"  # the reserved local lane's own cores
        assert grade_lanes.current().index == 0
    assert grade_lanes.current() is None


def test_outside_a_laneless_build_round_the_cores_are_chosen_as_before(host):
    from carbon.reconstruction import host_execution

    work, _ = _door(host, extra=4)
    with work.taking("grade", has_work=lambda: True):
        lane = grade_lanes.current()
        assert host_execution.resolve_cpuset(logical_cpus=16, count=4) == lane.cpuset


def test_a_laneless_builds_unsized_doctor_gets_the_reserved_lane_never_policy(host):
    """V2's blocker (17 Nov 2026): an UNSIZED caller (today's CPU count: a doctor in the library-environment or image
    verify path of a build) in a laneless build round binds the 4-core reserved lane and is served its cores, never a
    WorkerCode.POLICY refusal (the bug class that failed 14 of 14 migrated grades in switch 2).
    """
    from carbon.reconstruction import host_execution
    from carbon.reconstruction.worker.model import CPU_COUNT

    work, _ = _door(host, extra=4)
    with work.taking("advance"):
        assert host_execution.resolve_cpuset(logical_cpus=16, count=CPU_COUNT) == "0-3"
        assert grade_lanes.current().index == 0


def test_with_no_box_up_a_new_build_round_starts_on_a_local_lane(host):
    """Lead, 18 Nov 2026: with the remote GPU box down, every laneless build round queued on the one reserved lane and
    the board showed them building. While no box is up, a NEW build round starts on a local lane with a build slot
    (at most one build per local lane is started); once a box is up again, builds start laneless as before.
    """
    work, _ = _door(host, extra=4)
    work.box_up = lambda: False
    with work.taking("advance"):
        lane = grade_lanes.current()
        assert lane is not None and lane.docker_host is None
    work.box_up = lambda: True
    with work.taking("advance"):
        assert grade_lanes.current() is None


def test_only_a_box_slot_wait_marks_an_op_waiting_a_lane_retake_does_not():
    """V2 (18 Nov 2026): a box-slot wait (`waiting_for`) shows the op as waiting to build; a lane re-take does not
    (it only stops the construction's deadline clock, `timed_wait`)."""

    class Releaser:
        _released = True
        any_lane = False

        def __init__(self):
            self.seen = None

        def retake(self):
            self.seen = grade_lanes.waiting_ops()

    releaser = Releaser()
    with grade_lanes.running_op("rtsk_x-build"):
        grade_lanes._retake(releaser)
    assert releaser.seen == frozenset()
    with grade_lanes.waiting_for("a"), grade_lanes.waiting_for("a"):
        assert grade_lanes.waiting_ops() == frozenset({"a"})
    assert grade_lanes.waiting_ops() == frozenset()
