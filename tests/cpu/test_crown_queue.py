"""Fix 1b (V2's verdict of 18 Nov 2026, GRADE_SPEED_20261118.md; Lead 19 Nov 2026): every grade's own writes land at
once, and only the crown decision is applied in claim order.

Live 116 (19 Nov 2026, 0ebba5e3): 11 grades claimed 11:31-11:35Z; the light ones finished their work in 100-200 s, yet
all landed together at 11:42-11:44Z behind the door-wide commit turn while lanes sat idle with 73 tasks waiting. Now
the commit turn orders a grade's own writes (marker, exam-cap settle, keep, Ladder) only behind EARLIER grades of its
own allowance group, and its crown decision goes to the crown queue (`grade_sequencer.crown_decision`), applied by one
short-lock applier strictly in claim order. V2's three tests, as written in the verdict:

1. the A/B margin example gives A as king whatever order the grades finish in;
2. a light grade's marker and settle land while an earlier heavy grade is still running;
3. the queue never deadlocks when a grade fails or is abandoned.

Threads, a real `ExamCap` over a real `AttemptLedger`, real grade markers, and a stand-in crown store with the margin
rule. Fixture values only.
"""

from __future__ import annotations

import threading
import time

import pytest
from test_exam_cap import EXAM, MOTOR, Clock, make_cap

from carbon.challenge_validator import auto_grade, exam_cap, grade_sequencer
from carbon.development_session import research_carrier

HEAVY_KEY = "5" + "H" * 47
LIGHT_KEY = "5" + "L" * 47
#: A fixture crown margin (V2's example: A beats K = 1.00 by it, B = 1.06 does not beat A = 1.05).
MARGIN = 0.03


@pytest.fixture(autouse=True)
def _no_session(monkeypatch):
    monkeypatch.setattr(research_carrier, "yield_grade_session", lambda: False)


class _Crown:
    """A stand-in crown store: a challenger is crowned only when it beats the king by more than `MARGIN`."""

    def __init__(self):
        self.king, self.score = "K", 1.00
        self.decided = []

    def decide(self, name, score):
        def apply():
            # applied under the crown lock
            assert grade_sequencer.CROWN_LOCK._is_owned()
            self.decided.append(name)
            if score > self.score + MARGIN:
                self.king, self.score = name, score
            return {"outcome": "decided", "reason": name}

        return apply


def _two_grades(crown, b_first):
    """Grade A (claimed first, 1.05) and grade B (claimed second, 1.06), B's work finishing first when ``b_first``."""
    sequencer = grade_sequencer.Sequencer()
    a_claimed, b_claimed = threading.Event(), threading.Event()
    a_go, b_go, b_done = threading.Event(), threading.Event(), threading.Event()
    out = {}

    def grade(name, score, claimed, go, done):
        with sequencer.task() as task:
            task.bind("rtsk_" + name, "h:" + name)
            task.release_claim()
            claimed.set()
            go.wait(10)  # the grade's own work
            out[name] = grade_sequencer.crown_decision(crown.decide(name, score))
        done.set()

    a_done = threading.Event()
    a = threading.Thread(target=grade, args=("A", 1.05, a_claimed, a_go, a_done))
    b = threading.Thread(target=grade, args=("B", 1.06, b_claimed, b_go, b_done))
    a.start()
    assert a_claimed.wait(10)  # A holds the earlier ticket
    b.start()
    assert b_claimed.wait(10)
    if b_first:
        b_go.set()
        # B's grade ENDS (its lane and round are freed) with its decision queued behind A's
        assert b_done.wait(10)
        assert crown.decided == []
        a_go.set()
    else:
        a_go.set()
        b_go.set()
    a.join(10)
    b.join(10)
    return out


@pytest.mark.parametrize("b_first", [True, False])
def test_the_margin_example_crowns_a_whatever_order_the_grades_finish_in(b_first):
    crown = _Crown()
    out = _two_grades(crown, b_first)
    assert crown.decided == ["A", "B"]  # claim order, always
    assert crown.king == "A"
    if b_first:
        # B's decision was handed over (not applied by its own thread): queued, applied after A's
        assert out["B"] == grade_sequencer.CROWN_QUEUED
        assert out["A"] == {"outcome": "decided", "reason": "A"}


def _grader(tmp_path):
    grader = auto_grade.AutoGrader.__new__(auto_grade.AutoGrader)
    grader.markers = tmp_path / "markers"
    grader.markers.mkdir()
    return grader


def _task_id(char):
    return "rtsk_" + char * 64


def _reserve(cap, hotkey, sid, block):
    return cap.reserve(
        hotkey=hotkey,
        challenge_id=MOTOR[0],
        challenge_version=MOTOR[1],
        exam_key=EXAM,
        submission_id=sid,
        block=block,
    )


def _state(cap, sid):
    with cap.ledger._db() as db:
        (state,) = db.execute(
            "SELECT state FROM exam_graded WHERE submission_id=? AND kind='GRADED'",
            (sid,),
        ).fetchone()
    return state


@pytest.mark.parametrize("same_group", [False, True])
def test_a_light_grades_marker_and_settle_land_while_an_earlier_heavy_grade_runs(
    tmp_path, same_group
):
    cap = make_cap(tmp_path, Clock())
    grader = _grader(tmp_path)
    sequencer = grade_sequencer.Sequencer()
    heavy_id, light_id = _task_id("a"), _task_id("b")
    light_key = HEAVY_KEY if same_group else LIGHT_KEY
    heavy_reserved, heavy_release = threading.Event(), threading.Event()
    light_landed, light_ended = threading.Event(), threading.Event()

    def heavy():
        with sequencer.task() as task:
            task.bind(heavy_id, exam_cap.group_of(HEAVY_KEY))
            task.release_claim()
            grade_sequencer.reserve_turn()
            slot = _reserve(cap, HEAVY_KEY, heavy_id, 360)
            grade_sequencer.claimed()
            heavy_reserved.set()
            heavy_release.wait(10)  # the heavy graded pass, still running
            cap.settle(slot, "SCORED_DEVELOPMENT_CANDIDATE")
            grader._write(heavy_id, "GRADED")

    def light():
        heavy_reserved.wait(10)
        with sequencer.task() as task:
            task.bind(light_id, exam_cap.group_of(light_key))
            task.release_claim()
            grade_sequencer.reserve_turn()
            slot = _reserve(cap, light_key, light_id, 720)
            grade_sequencer.claimed()
            cap.settle(slot, "SCORED_DEVELOPMENT_CANDIDATE")  # its commit turn
            grader._write(light_id, "GRADED")
            light_landed.set()
        light_ended.set()

    threads = [threading.Thread(target=heavy), threading.Thread(target=light)]
    for thread in threads:
        thread.start()
    if same_group:
        # one allowance group: its allowance is read in its own order, so the later settle waits for the earlier
        assert not light_landed.wait(1.0)
        assert _state(cap, light_id) == "RESERVED"
        heavy_release.set()
        assert light_landed.wait(10)
    else:
        # another miner's group: the marker, the settle and the grade's end come at once, the heavy grade still running
        assert light_ended.wait(10)
        assert not heavy_release.is_set()
        assert grader.marker(light_id)["state"] == "GRADED"
        assert _state(cap, light_id) == "COUNTED"
        assert grader.marker(heavy_id) is None
        heavy_release.set()
    for thread in threads:
        thread.join(10)
    assert _state(cap, heavy_id) == "COUNTED" and _state(cap, light_id) == "COUNTED"


def test_the_crown_queue_never_deadlocks_on_a_failed_or_abandoned_grade():
    """Three grades in claim order: the first FAILS (ends with no decision), the second is ended as hung with its
    decision queued (dropped: its slot was given back), the third's decision is applied once the first has ended.
    """
    crown = _Crown()
    sequencer = grade_sequencer.Sequencer()
    claimed = [threading.Event() for _ in range(3)]
    queued = [threading.Event() for _ in range(3)]
    fail_now, tickets, out = threading.Event(), {}, {}

    def first():
        try:
            with sequencer.task() as task:
                task.bind("rtsk_1", "h:1")
                task.release_claim()
                claimed[0].set()
                fail_now.wait(10)
                raise RuntimeError("worker failure")  # FAILED: no crown decision
        except RuntimeError:
            out["first"] = "failed"

    def later(index, name, score):
        claimed[index - 1].wait(10)
        with sequencer.task() as task:
            task.bind("rtsk_" + name, "h:" + name)
            tickets[name] = task.ticket
            task.release_claim()
            claimed[index].set()
            out[name] = grade_sequencer.crown_decision(crown.decide(name, score))
            queued[index].set()
            if name == "2":
                time.sleep(0.5)  # still in flight when it is ended as hung

    threads = [
        threading.Thread(target=first),
        threading.Thread(target=later, args=(1, "2", 2.0)),
        threading.Thread(target=later, args=(2, "3", 1.5)),
    ]
    for thread in threads:
        thread.start()
    assert queued[1].wait(10) and queued[2].wait(10)
    # both wait for the first grade, never in their own threads
    assert crown.decided == []
    # the hung second grade: its queued decision is dropped
    sequencer.abandon(tickets["2"])
    fail_now.set()
    for thread in threads:
        thread.join(10)
        assert not thread.is_alive()
    assert out["first"] == "failed"
    # the failed grade held nothing; the abandoned one's decision never applied
    assert crown.decided == ["3"]
    assert crown.king == "3"
    assert out["2"] == out["3"] == grade_sequencer.CROWN_QUEUED
    # the queue is empty and at its end: a new grade's decision is applied at once, in its own thread
    with sequencer.task() as task:
        task.bind("rtsk_4", "h:4")
        assert grade_sequencer.crown_decision(crown.decide("4", 9.0)) == {
            "outcome": "decided",
            "reason": "4",
        }


def test_an_unsequenced_crown_decision_is_applied_at_once_under_the_crown_lock():
    crown = _Crown()
    assert grade_sequencer.crown_decision(crown.decide("A", 1.05)) == {
        "outcome": "decided",
        "reason": "A",
    }
    assert crown.king == "A"


# --- V2 C5 (19 Nov 2026): a decision queued at a stop is never lost ---------------------------------------------------

KEY, PACK = "sha256:" + "k" * 64, "sha256:" + "e" * 64
ENTRY, PIN = "sha256:" + "1" * 64, "sha256:" + "2" * 64


class _Store:
    """A stand-in pool store: the crown pause sweep's filings, in order."""

    def __init__(self):
        self.filed = []

    def record_crown_paused(self, submission_id, key, **fields):
        self.filed.append((submission_id, key, fields))


def _journal(root, name):
    from carbon.challenge_validator.lean_recipe_retention import CrownJournal

    return CrownJournal(
        root / "auto-grade" / "artifacts",
        submission_id="rtsk_" + name * 64,
        evaluation_key=KEY,
        kind="pack",
        exam=PACK,
        entry_id=ENTRY,
        pin=PIN,
    )


def test_a_decision_queued_at_a_stop_is_refiled_once_at_the_next_start(tmp_path):
    from carbon.battery.pool_store import CROWN_PAUSED
    from carbon.challenge_validator.lean_recipe_retention import refile_queued_crowns

    root = tmp_path / "receiver"
    (root / "auto-grade" / "artifacts").mkdir(parents=True)
    crown = _Crown()
    sequencer = grade_sequencer.Sequencer()
    head_claimed, stop = threading.Event(), threading.Event()

    def head():
        # still running at the stop: no decision of its own yet
        with sequencer.task() as task:
            task.bind("rtsk_" + "a" * 64, "h:a")
            task.release_claim()
            head_claimed.set()
            stop.wait(10)

    thread = threading.Thread(target=head)
    thread.start()
    assert head_claimed.wait(10)
    with sequencer.task() as task:
        task.bind("rtsk_" + "b" * 64, "h:b")
        out = grade_sequencer.crown_decision(
            crown.decide("B", 2.0), _journal(root, "b")
        )
    assert out == grade_sequencer.CROWN_QUEUED and crown.decided == []
    # the receiver stops here: the in-memory queue is gone; the next start files B for the crown pause sweep
    store = _Store()
    assert refile_queued_crowns(root, store) == (1, 0)
    assert store.filed == [
        (
            "rtsk_" + "b" * 64,
            KEY,
            {
                "kind": "pack",
                "exam": PACK,
                "entry_id": ENTRY,
                "pin": PIN,
                "state": CROWN_PAUSED,
            },
        )
    ]
    assert refile_queued_crowns(root, store) == (0, 0)  # once
    stop.set()
    thread.join(10)


def test_an_applied_or_dropped_decision_is_never_refiled(tmp_path):
    from carbon.challenge_validator.lean_recipe_retention import refile_queued_crowns

    root = tmp_path / "receiver"
    (root / "auto-grade" / "artifacts").mkdir(parents=True)
    crown = _Crown()
    sequencer = grade_sequencer.Sequencer()
    # applied at once (nothing earlier): queued, then applied
    with sequencer.task() as task:
        task.bind("rtsk_" + "c" * 64, "h:c")
        grade_sequencer.crown_decision(crown.decide("C", 2.0), _journal(root, "c"))
    # queued behind an earlier grade, then that grade is ended as hung: dropped
    head_claimed, release = threading.Event(), threading.Event()

    def head():
        with sequencer.task() as task:
            task.bind("rtsk_" + "a" * 64, "h:a")
            task.release_claim()
            head_claimed.set()
            release.wait(10)

    thread = threading.Thread(target=head)
    thread.start()
    assert head_claimed.wait(10)
    hung = {}

    def queued_then_hung():
        with sequencer.task() as task:
            task.bind("rtsk_" + "d" * 64, "h:d")
            hung["ticket"] = task.ticket
            grade_sequencer.crown_decision(crown.decide("D", 3.0), _journal(root, "d"))
            hung["queued"] = True
            release.wait(10)

    other = threading.Thread(target=queued_then_hung)
    other.start()
    for _ in range(500):
        if hung.get("queued"):
            break
        time.sleep(0.01)
    sequencer.abandon(hung["ticket"])
    release.set()
    thread.join(10)
    other.join(10)
    assert crown.decided == ["C"]
    store = _Store()
    assert refile_queued_crowns(root, store) == (0, 0) and store.filed == []


def test_the_start_filing_refiles_queued_crowns_before_recontend(monkeypatch):
    from carbon.challenge_validator import king_upkeep
    from carbon.challenge_validator import lean_recipe_retention as retention
    from carbon.challenge_validator import recontend

    order = []
    monkeypatch.setattr(
        retention, "refile_queued_crowns", lambda root, pool: order.append("refile")
    )

    def file(root, pool, exam, apply):
        order.append("recontend")
        return {"king": "k", "filed": [], "skipped": {}}

    monkeypatch.setattr(recontend, "file", file)
    discovery = type("D", (), {"evaluation_pack_digest": PACK})()
    state, _count = king_upkeep.file_stranded("/root", "/pool", discovery)
    assert state == king_upkeep.STRANDED_DONE and order == ["refile", "recontend"]

    def broken(root, pool):
        raise OSError("unreadable")

    monkeypatch.setattr(retention, "refile_queued_crowns", broken)
    order.clear()
    state, _count = king_upkeep.file_stranded("/root", "/pool", discovery)
    # tried again with the filing (the stranded hold keeps grades back meanwhile), never skipped
    assert state == king_upkeep.STRANDED_RETRY and order == []
