"""(a) (Lead 17 Nov 2026): a grade gives its lane back while it waits for its commit turn, then holds one again.

Switch-2 copy, 18:3xZ: grades that had finished their run sat on their lanes (no containers) behind earlier grades'
long HEL1 repeats, so 9 of 10 lanes were held while 2 ran. Now `grade_sequencer._Task.turn` waits inside
`grade_lanes.given_back`: the grade's session container is removed (confirmed) first, its sampler reads its stop sample
and lane first (`grade_lanes.before_give_back`), then the lane (local OR remote) and round slot go back to the door, and
`_Taking.retake` holds ANY lane again before the wait returns (never on without one), ahead of new grade rounds.
Also here: a build round's wall guard counts its own lane cores (Lead), and the per-grade ``grade_lane`` log line (V2).
"""

from __future__ import annotations

import json
import threading
from contextlib import nullcontext

import pytest

from carbon.challenge_validator import auto_grade, grade_sequencer
from carbon.reconstruction import grade_lanes, remote_lane

LANE = grade_lanes.Lane(0, "0-3", "/locks")
OTHER = grade_lanes.Lane(1, "4-7", "/locks")


class _Releaser:
    any_lane = True

    def __init__(self, retaken=OTHER):
        self.events, self.retaken = [], retaken

    def release(self):
        self.events.append("release")

    def retake(self):
        self.events.append("retake")
        return self.retaken


def test_a_grade_gives_its_lane_back_and_holds_one_again():
    releaser, seen = _Releaser(), []
    token = grade_lanes.offer_releaser(releaser)
    try:
        with (
            grade_lanes.bound(LANE),
            grade_lanes.before_give_back(lambda: seen.append(grade_lanes.current())),
        ):
            with grade_lanes.given_back():
                assert releaser.events == ["release"]
            assert releaser.events == ["release", "retake"]
            assert (
                grade_lanes.current() == OTHER
            )  # never on bound to the lane it gave back
    finally:
        grade_lanes.withdraw_releaser(token)
    assert seen == [LANE]  # the hook ran on the lane, before it went back


def test_nothing_goes_back_without_an_any_lane_releaser_or_when_a_hook_fails():
    build = _Releaser()
    build.any_lane = False  # Option A's build releaser: local lanes only, never here

    def fail():
        raise RuntimeError("boom")

    for releaser, hook in ((None, None), (build, None), (_Releaser(), "boom")):
        token = grade_lanes.offer_releaser(releaser)
        try:

            with (
                grade_lanes.bound(LANE),
                grade_lanes.before_give_back(fail) if hook else nullcontext(),
                grade_lanes.given_back(),
            ):
                assert grade_lanes.current() == LANE
            if releaser is not None:
                assert releaser.events == []
        finally:
            grade_lanes.withdraw_releaser(token)


def _two_tickets(monkeypatch, gone=True):
    from carbon.development_session import research_carrier

    monkeypatch.setattr(research_carrier, "yield_grade_session", lambda: gone)
    sequencer = grade_sequencer.Sequencer()
    first_in, first_go = threading.Event(), threading.Event()

    def first():
        with sequencer.task() as task:
            task.bind("rtsk_first")
            task.release_claim()
            first_in.set()
            assert first_go.wait(5)

    thread = threading.Thread(target=first, daemon=True)
    thread.start()
    assert first_in.wait(5)
    return sequencer, first_go, thread


@pytest.mark.parametrize("gone", [True, False])
def test_the_commit_turn_wait_gives_the_lane_back_only_once_the_session_is_gone(
    monkeypatch, gone
):
    sequencer, first_go, thread = _two_tickets(monkeypatch, gone)
    releaser = _Releaser()
    during = []

    def later():
        token = grade_lanes.offer_releaser(releaser)
        try:
            with grade_lanes.bound(LANE), sequencer.task() as task:
                task.bind("rtsk_later")
                task.turn()
                during.append(grade_lanes.current())
        finally:
            grade_lanes.withdraw_releaser(token)

    waiter = threading.Thread(target=later, daemon=True)
    waiter.start()
    for _ in range(200):
        if releaser.events or not gone:
            break
        first_go.wait(0.01)
    assert releaser.events == (["release"] if gone else [])
    first_go.set()
    thread.join(5)
    waiter.join(5)
    assert releaser.events == (["release", "retake"] if gone else [])
    assert during == [OTHER if gone else LANE]


def test_a_first_ticket_never_waits_and_keeps_its_lane(monkeypatch):
    releaser = _Releaser()
    token = grade_lanes.offer_releaser(releaser)
    try:
        with grade_lanes.bound(LANE), grade_sequencer.Sequencer().task() as task:
            task.bind("rtsk_only")
            task.turn()
    finally:
        grade_lanes.withdraw_releaser(token)
    assert releaser.events == []


# -- the door's lanes ----------------------------------------------------------------------------------------------------


def _door(tmp_path, lanes):
    from carbon.challenge_validator.direct_intake import _WorkLock

    pytest.importorskip("fcntl")
    host = tmp_path / "host"
    host.mkdir(mode=0o700)
    work = _WorkLock(host, poll_s=0.02, lanes=lanes)
    work.overlap_kinds = True
    return work


def test_a_grade_rounds_lane_serves_another_round_while_it_waits(tmp_path):
    work = _door(tmp_path, ("0-3", "4-7"))
    busy_in, busy_go = threading.Event(), threading.Event()
    waiting, done, second_in = threading.Event(), threading.Event(), threading.Event()
    lanes = {}

    def busy():  # holds the other lane all along: only a give-back lets the second round in
        with work.taking("grade", has_work=lambda: True):
            lanes["busy"] = grade_lanes.current()
            busy_in.set()
            assert busy_go.wait(10)

    def first():
        assert busy_in.wait(5)
        with work.taking("grade", has_work=lambda: True):
            lanes["first"] = grade_lanes.current()
            with grade_lanes.given_back():
                waiting.set()
                assert second_in.wait(5)
            lanes["after"] = grade_lanes.current()
        done.set()

    def second():
        assert waiting.wait(5)
        with work.taking("grade", has_work=lambda: True):
            lanes["second"] = grade_lanes.current()
            second_in.set()

    threads = [threading.Thread(target=f, daemon=True) for f in (busy, first, second)]
    for thread in threads:
        thread.start()
    assert done.wait(10)
    busy_go.set()
    assert lanes["first"].index == lanes["second"].index == lanes["after"].index
    assert lanes["busy"].index != lanes["first"].index


def test_a_grade_retakes_any_lane_a_remote_one_first(tmp_path):
    spec = remote_lane.RemoteSpec("ssh://carbon-grade@box.example", "0-3", "/srv/gb")
    work = _door(tmp_path, ("0-3", "4-7", spec))
    fd, _fds, lane = work._take_local_lane(any_lane=True)
    try:
        assert lane.docker_host == spec.docker_host and lane.index == 2
    finally:
        work._unlock(fd)
    fd, _fds, lane = work._take_local_lane()
    try:
        assert (
            lane.docker_host is None
        )  # a build round re-takes a LOCAL lane only, as before
    finally:
        work._unlock(fd)


def test_a_waiting_grade_retaker_goes_before_new_grade_rounds(tmp_path):
    work = _door(tmp_path, ("0-3", "4-7"))
    work._grade_retakers = 1
    assert work._acquire_slot("grade") is False
    work._grade_retakers = 0
    assert work._acquire_slot("grade") is True
    work._release_slot("grade")


# -- the wall rule across a give-back -------------------------------------------------------------------------------------


def test_a_wall_stop_settled_after_a_give_back_is_judged_on_the_lane_it_ran_on(
    tmp_path,
):
    """The settle's commit turn (inside the grade) gave the lane back and a different one was re-taken: the stop sample
    and the lane are read before it went back, so the run is judged on its own lane, as without the give-back.
    """
    from test_lane_wall_attribution import _lane_grader, _logged

    asked = []

    def own(cpuset, lane=None):
        asked.append(cpuset)
        return (
            1 if len(asked) < 3 else 0
        )  # its own container during the run; none at the stop

    grader, _cap, _ident, _ledger = _lane_grader(tmp_path, own=own)
    real = grader.intake.retain_result
    releaser = _Releaser(retaken=OTHER)

    def settled_after_a_wait(submission_id, **kwargs):
        try:
            return real(submission_id, **kwargs)
        finally:
            with grade_lanes.given_back():
                pass

    grader.intake.retain_result = settled_after_a_wait
    token = grade_lanes.offer_releaser(releaser)
    try:
        with grade_lanes.bound(LANE):
            outcome = grader.run_once()
    finally:
        grade_lanes.withdraw_releaser(token)
    assert releaser.events == ["release", "retake"]
    assert set(asked) == {"0-3"}  # never the re-taken lane's cores
    assert outcome == (auto_grade_task(), "CANDIDATE_FAILED")
    assert _logged(tmp_path)["counted"] is True


def auto_grade_task():
    from test_auto_grade import A

    return A


# -- the build wall guard on its own cores ------------------------------------------------------------------------------


def test_a_build_rounds_wall_guard_counts_its_own_lane_cores(monkeypatch):
    from carbon.challenge_validator import host_quiet, lean_recipe
    from carbon.development_session import research_carrier

    monkeypatch.setattr(lean_recipe, "BUILD_PROBE_SECONDS", 0.01)
    monkeypatch.setattr(
        host_quiet, "worker_containers", lambda: pytest.fail("never the whole host")
    )
    monkeypatch.setattr(host_quiet, "foreign_gpu_compute", lambda: 0)
    asked = []
    monkeypatch.setattr(
        host_quiet,
        "count_lane_containers",
        lambda cpuset, lane=None: asked.append(cpuset) or 1,
    )
    with grade_lanes.bound(LANE), lean_recipe._build_wall_guard(object()):
        quiet = research_carrier.BUILD_WALL_GUARD.get()
        for _ in range(500):
            if asked:
                break
            threading.Event().wait(0.01)
        assert quiet()  # its own container only, on its own cores
        with grade_lanes.bound(OTHER):
            assert not quiet()  # moved to other cores: the samples read the wrong ones
    assert set(asked) == {"0-3"}


# -- the per-grade lane line (V2) ---------------------------------------------------------------------------------------


def test_one_lane_line_per_grade_and_none_for_a_task_not_ready(monkeypatch, capsys):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    outcomes = iter([auto_grade._NEXT, ("rtsk_a", "COUNTED")])
    grader._grade_on_lane = lambda sid, turn: next(outcomes)
    with grade_lanes.bound(LANE):
        assert grader._grade_one("rtsk_b") is auto_grade._NEXT
        assert grader._grade_one("rtsk_a") == ("rtsk_a", "COUNTED")
    lines = [
        json.loads(line)
        for line in capsys.readouterr().err.splitlines()
        if '"grade_lane"' in line
    ]
    assert len(lines) == 1
    line = lines[0]
    assert line["task"] == "rtsk_a" and line["lane"] == 0 and line["cpuset"] == "0-3"
    assert line["docker_host"] == "local" and line["end_lane"] == 0
    assert isinstance(line["started_ns"], int)


def test_no_lane_line_on_a_one_lane_door(capsys):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader._grade_on_lane = lambda sid, turn: ("rtsk_a", "COUNTED")
    grader._grade_one("rtsk_a")
    assert '"grade_lane"' not in capsys.readouterr().err
