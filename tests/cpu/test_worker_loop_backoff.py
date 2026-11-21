"""A failing receiver background loop backs off and keeps its traceback private.

valV3, 2026-10-27: a ValueError in the advance step was logged (type only) every
second for two minutes, 129 times, with no traceback anywhere. A loop that keeps
failing now waits longer after each consecutive failure (bounded), logs the
exception type with the failure count and a short site id, and writes the full
traceback once per distinct failure site to the receiver's private evidence
directory. A success resets the wait.
"""

import threading
from types import SimpleNamespace

from carbon.challenge_validator import direct_intake


class FakeStop:
    """A stop event that records each wait and ends the loop after `rounds`."""

    def __init__(self, rounds):
        self.waits = []
        self.rounds = rounds

    def is_set(self):
        return len(self.waits) >= self.rounds

    def wait(self, seconds):
        self.waits.append(seconds)


def _intake(tmp_path, behaviours):
    steps = iter(behaviours)

    def advance():
        behaviour = next(steps)
        if behaviour == "ok":
            return 0
        raise behaviour

    return SimpleNamespace(
        advance=advance,
        adapter=SimpleNamespace(ledger=SimpleNamespace(path=tmp_path / "ledger.db")),
    )


def test_a_failing_advance_backs_off_with_a_bound_and_resets_on_success(
    tmp_path, monkeypatch
):
    lines = []
    monkeypatch.setattr(
        direct_intake, "log", lambda event, **fields: lines.append((event, fields))
    )
    failure = ValueError("retained direct result custody differs: /private/path")
    count = len(direct_intake.FAILURE_BACKOFF_S) + 3
    behaviours = [failure] * count + ["ok", failure]
    stop = FakeStop(len(behaviours))
    direct_intake._advance_loop(_intake(tmp_path, behaviours), stop, threading.Lock())
    expected = list(direct_intake.FAILURE_BACKOFF_S)
    expected += [expected[-1]] * 3  # bounded: never longer than the last step
    assert stop.waits == expected + [
        1,
        1,
    ]  # success: back to the normal 1 s; then step 1
    assert max(stop.waits) == 15  # S7 I3 row 126: capped at 15 s, not 300 s
    events = [
        (event, fields) for event, fields in lines if event == "direct_worker_failure"
    ]
    assert [fields["consecutive"] for _, fields in events] == (
        list(range(1, count + 1)) + [1]
    )
    for _, fields in events:
        assert fields["type"] == "ValueError" and fields["retry_s"] in stop.waits
        # The log carries the type, counts and a hashed site: never the message.
        assert "private" not in repr(fields)


def test_the_full_traceback_is_kept_once_per_site_in_a_private_directory(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(direct_intake, "log", lambda *a, **k: None)

    def raise_here():
        raise ValueError("retained direct result custody differs")

    def advance():
        raise_here()

    intake = SimpleNamespace(
        advance=advance,
        adapter=SimpleNamespace(ledger=SimpleNamespace(path=tmp_path / "ledger.db")),
    )
    direct_intake._advance_loop(intake, FakeStop(5), threading.Lock())
    directory = tmp_path / "worker-failures"
    files = list(directory.iterdir())
    assert len(files) == 1 and files[0].name.startswith("advance-")
    text = files[0].read_text(encoding="utf-8")
    assert "Traceback" in text and "raise_here" in text and "custody differs" in text
    assert oct(directory.stat().st_mode & 0o777) == "0o700"
    assert oct(files[0].stat().st_mode & 0o777) == "0o600"


def test_a_subject_without_a_ledger_still_backs_off(tmp_path, monkeypatch):
    lines = []
    monkeypatch.setattr(
        direct_intake, "log", lambda event, **fields: lines.append(fields)
    )

    def advance():
        raise ValueError("x")

    stop = FakeStop(4)
    direct_intake._advance_loop(
        SimpleNamespace(advance=advance), stop, threading.Lock()
    )
    assert stop.waits == [1, 2, 4, 8]
    assert all("site" in fields for fields in lines)


def test_a_failing_grade_loop_backs_off_from_its_idle_wait(tmp_path, monkeypatch):
    lines = []
    monkeypatch.setattr(
        direct_intake, "log", lambda event, **fields: lines.append((event, fields))
    )

    class Grader:
        ledger = SimpleNamespace(path=tmp_path / "ledger.db")

        def run_once(self):
            raise ValueError("pool grade")

    stop = FakeStop(6)
    direct_intake._grade_loop(Grader(), stop, threading.Lock())
    assert stop.waits == [
        5,
        5,
        5,
        8,
        15,
        15,
    ]  # never under the 5 s idle wait; capped at 15 s
    assert {event for event, _ in lines} == {"direct_grade_failure"}
    assert any((tmp_path / "worker-failures").glob("grade-*.txt"))


def test_a_grade_round_without_a_free_remote_lane_looks_again_after_one_second(
    monkeypatch,
):
    """S7 I3 (audit row 125): `no_grade_lane` (a remote-lane-only door with no remote lane free) re-checks after 1 s,
    not the 5 s idle wait; any other decline keeps 5 s."""
    monkeypatch.setattr(direct_intake, "log", lambda *a, **k: None)
    reasons = iter(["no_grade_lane", "idle", "no_grade_lane"])

    def taking(kind, has_work=None, since=None):
        raise direct_intake.WorkDeclined(next(reasons))

    stop = FakeStop(3)
    direct_intake._grade_loop(
        SimpleNamespace(run_once=lambda: None), stop, SimpleNamespace(taking=taking)
    )
    assert stop.waits == [direct_intake.NO_GRADE_LANE_RECHECK_S, 5, 1]
    assert direct_intake.NO_GRADE_LANE_RECHECK_S == 1


class _Door:
    """A door whose rounds always run (no lanes), sharing ``loop_successes`` like a `_WorkLock`."""

    def __init__(self):
        self.loop_successes = {}
        self.lock = threading.Lock()

    def taking(self, kind, has_work=None, since=None):
        return self.lock


def test_another_loop_s_success_starts_the_failure_count_again(tmp_path, monkeypatch):
    """S7 I3 (audit row 126): a success of ANOTHER round of the same kind on the same door ends the blip for every
    loop: the next failure waits the first step again, not the next one up."""
    monkeypatch.setattr(direct_intake, "log", lambda *a, **k: None)
    door = _Door()
    outcomes = iter(["fail", "fail", "other", "fail", "fail"])

    def advance():
        outcome = next(outcomes)
        if outcome == "other":
            # another build round of this door finished meanwhile; this loop's round fails again
            direct_intake._loop_success(door, "advance")
        raise ValueError("docker blip")

    stop = FakeStop(5)
    direct_intake._advance_loop(
        SimpleNamespace(
            advance=advance,
            adapter=SimpleNamespace(ledger=SimpleNamespace(path=tmp_path / "l.db")),
        ),
        stop,
        door,
    )
    assert stop.waits == [1, 2, 1, 2, 4]
    # a grade success never resets the build loops (and the other way round)
    direct_intake._loop_success(door, "grade")
    assert direct_intake._loop_successes(door, "advance") == 1
    assert direct_intake._loop_successes(threading.Lock(), "advance") == 0
