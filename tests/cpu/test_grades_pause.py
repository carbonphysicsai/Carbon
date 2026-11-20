"""GRADES-ONLY PAUSE (owner LO-5, 20 Nov 2026: "Whatever stops this"; live-ops 14:43:05Z).

Before a stop the kit sets ``grades-paused``: the door starts no NEW grade round while every started one finishes, the
front and the build rounds go on (DRAINING would refuse every POST), the kit waits (bounded) until no grade round is
live, stops, and clears the flag at UNDRAINED."""

from __future__ import annotations

import json
import os
import threading

import pytest

from carbon.backbone_catalog import receipt_job
from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.direct_intake import (
    DRAIN_NAME,
    GRADES_INFLIGHT_NAME,
    GRADES_PAUSE_NAME,
    INFLIGHT_NAME,
    _WorkLock,
)
from scripts.dev.release import door_drain

POLL = 0.05


@pytest.fixture
def dirs(tmp_path):
    host = tmp_path / "host"
    state = tmp_path / "state"
    for d in (host, state):
        d.mkdir(mode=0o700)
    return host, state


def _alive():
    return {
        "pid": os.getpid(),
        "pid_start": direct_intake._process_start(os.getpid()),
    }


def test_the_kit_names_match_the_receivers():
    assert door_drain.GRADES_PAUSE_NAME == GRADES_PAUSE_NAME
    assert door_drain.GRADES_INFLIGHT_NAME == GRADES_INFLIGHT_NAME
    assert door_drain.INFLIGHT_NAME == INFLIGHT_NAME


def test_a_paused_door_starts_no_grade_round_but_builds_go_on(dirs):
    host, state = dirs
    door_drain.pause(state)
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    with (
        pytest.raises(direct_intake.WorkDeclined, match="grades_paused"),
        work.taking("grade", has_work=lambda: True),
    ):
        pytest.fail("a grade round started while grades are paused")
    assert receipt_job.grading_busy(host) is False
    assert not (state / INFLIGHT_NAME).exists()
    # a build round is never paused
    with work.taking("advance"):
        assert json.loads((state / INFLIGHT_NAME).read_text())["kind"] == "advance"
    # resumed: grades start again
    door_drain.resume(state)
    with work.taking("grade", has_work=lambda: True):
        assert json.loads((state / INFLIGHT_NAME).read_text())["kind"] == "grade"


def test_the_pause_is_not_draining_and_draining_still_wins(dirs):
    host, state = dirs
    door_drain.pause(state)
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    assert work.grades_paused() is True and work.draining() is False
    (state / DRAIN_NAME).write_text("{}")
    with (
        pytest.raises(direct_intake.WorkDeclined, match="draining"),
        work.taking("advance"),
    ):
        pytest.fail("a round started while draining")


def test_a_started_grade_finishes_and_the_kit_waits_for_it(dirs):
    host, state = dirs
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    done = []
    with work.taking("grade", has_work=lambda: True):
        door_drain.pause(state)  # the kit pauses while this grade runs
        read = door_drain.grades_status(state, gap=0)
        assert read["state"] == "GRADES_BUSY" and read["read"]["grades"] == 1
        done.append(True)  # nothing stops it: the round runs to its end
    assert done == [True]
    assert door_drain.grades_status(state, gap=0)["state"] == "GRADES_IDLE"
    # and the next grade round does not start
    with (
        pytest.raises(direct_intake.WorkDeclined, match="grades_paused"),
        work.taking("grade", has_work=lambda: True),
    ):
        pytest.fail("a grade round started after the pause")


def test_a_pause_set_right_after_the_record_declines_the_round(dirs, monkeypatch):
    """The window is closed as for DRAINING: the record goes down first, then the last check reads the pause."""
    host, state = dirs
    real = direct_intake._write_record

    def then_pause(path, body):
        real(path, body)
        if path.name == INFLIGHT_NAME:
            door_drain.pause(state)

    monkeypatch.setattr(direct_intake, "_write_record", then_pause)
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    with (
        pytest.raises(direct_intake.WorkDeclined, match="grades_paused"),
        work.taking("grade"),
    ):
        pytest.fail("a grade round started after the pause")
    assert not (state / INFLIGHT_NAME).exists()
    assert receipt_job.grading_busy(host) is False


def test_the_grade_loop_runs_no_grade_while_paused(dirs):
    host, state = dirs
    door_drain.pause(state)
    stop = threading.Event()
    seen = []

    class Grader:
        def has_work(self):
            return True

        def run_once(self):
            seen.append(1)

    work = _WorkLock(host, state_dir=state, stop=stop, poll_s=POLL)
    thread = threading.Thread(
        target=direct_intake._grade_loop, args=(Grader(), stop, work), daemon=True
    )
    thread.start()
    stop.wait(0.3)
    stop.set()
    thread.join(10)
    assert seen == []


def test_the_grade_record_counts_live_grade_rounds_only(dirs):
    """Parallel mode: ``grades-inflight.json`` names the oldest live GRADE round and how many there are; builds never
    count, and it goes when the last grade round ends."""
    host, state = dirs
    work = _WorkLock(host, state_dir=state, poll_s=POLL)
    record = {**_alive(), "kind": "grade"}
    work._live = {
        1: ("grade", {**record, "since_ns": 30}),
        2: ("advance", {**record, "kind": "advance", "since_ns": 10}),
        3: ("grade", {**record, "since_ns": 20}),
        4: (
            "grade",
            None,
        ),  # entered, no record yet: its last check still reads the pause
    }
    work._write_oldest()
    grades = json.loads((state / GRADES_INFLIGHT_NAME).read_text())
    assert grades["grades"] == 2 and grades["since_ns"] == 20
    assert json.loads((state / INFLIGHT_NAME).read_text())["since_ns"] == 10
    door_drain.pause(state)
    read = door_drain.grades_status(state, gap=0)
    assert read["state"] == "GRADES_BUSY" and read["read"]["grades"] == 2
    work._live = {2: ("advance", {**record, "kind": "advance", "since_ns": 10})}
    work._write_oldest()
    assert not (state / GRADES_INFLIGHT_NAME).exists()
    # a live BUILD round never keeps the kit waiting
    assert door_drain.grades_status(state, gap=0)["state"] == "GRADES_IDLE"


def test_a_grade_record_left_by_a_crash_is_set_aside_at_start(dirs):
    host, state = dirs
    (state / GRADES_INFLIGHT_NAME).write_text(json.dumps({**_alive(), "grades": 1}))
    _WorkLock(host, state_dir=state, poll_s=POLL)
    assert not (state / GRADES_INFLIGHT_NAME).exists()
    assert list(state.glob(GRADES_INFLIGHT_NAME + ".stale-*"))


def test_kit_reads_dead_and_unreadable_grade_records(dirs):
    _, state = dirs
    door_drain.pause(state)
    (state / GRADES_INFLIGHT_NAME).write_text(
        json.dumps({"pid": 2**22 + 7, "pid_start": 5, "grades": 3})
    )
    read = door_drain.grades_status(state, gap=0)
    assert read["state"] == "GRADES_IDLE" and read["read"]["stale_record"] is True
    (state / GRADES_INFLIGHT_NAME).write_text("{not json")
    assert door_drain.grades_status(state, gap=0)["state"] == "GRADES_BUSY"
    (state / GRADES_INFLIGHT_NAME).unlink()
    # a one-lane door's grade round is its work-inflight record of kind grade; a build there is not a grade
    (state / INFLIGHT_NAME).write_text(json.dumps({**_alive(), "kind": "advance"}))
    assert door_drain.grades_status(state, gap=0)["state"] == "GRADES_IDLE"
    (state / INFLIGHT_NAME).write_text(json.dumps({**_alive(), "kind": "grade"}))
    assert door_drain.grades_status(state, gap=0)["state"] == "GRADES_BUSY"


def test_wait_grades_is_bounded_and_clear_removes_both_flags(dirs):
    _, state = dirs
    assert door_drain.wait_grades(state, 3)["state"] == "GRADES_NOT_PAUSED"
    door_drain.pause(state)
    (state / GRADES_INFLIGHT_NAME).write_text(json.dumps({**_alive(), "grades": 1}))
    ticks = iter(range(100))
    timed = door_drain.wait_grades(
        state, 3, gap=0, poll=0, sleep=lambda s: None, clock=lambda: next(ticks)
    )
    assert timed["state"] == "TIMED_OUT" and (state / GRADES_PAUSE_NAME).exists()
    (state / GRADES_INFLIGHT_NAME).unlink()
    assert (
        door_drain.wait_grades(state, 3, gap=0, poll=0, sleep=lambda s: None)["state"]
        == "GRADES_IDLE"
    )
    door_drain.start(state)
    assert door_drain.resume(state) == {"state": "GRADES_NOT_PAUSED"}
    assert (state / DRAIN_NAME).exists() and not (state / GRADES_PAUSE_NAME).exists()
    door_drain.pause(state)
    assert door_drain.clear(state) == {"state": "NOT_DRAINING", "grades_paused": False}
    assert not (state / DRAIN_NAME).exists()
    assert not (state / GRADES_PAUSE_NAME).exists()


def test_kit_exit_codes(dirs, capsys):
    _, state = dirs
    assert door_drain.main(["pause", str(state)]) == 0
    assert door_drain.main(["wait-grades", str(state), "--timeout", "0"]) == 0
    assert (
        json.loads(capsys.readouterr().out.splitlines()[-1])["state"] == "GRADES_IDLE"
    )
    (state / GRADES_INFLIGHT_NAME).write_text(json.dumps({**_alive(), "grades": 1}))
    assert door_drain.main(["wait-grades", str(state), "--timeout", "0"]) == 3
    assert door_drain.main(["resume", str(state)]) == 0
    assert door_drain.main(["wait-grades", str(state), "--timeout", "0"]) == 4
