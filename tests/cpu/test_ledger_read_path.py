"""LOCK + CACHE AUDIT #6 (door-code, 19 Nov 2026): the shared attempt ledger's WRITE lock is taken only to write.

`ExamCap()` prepared its tables on the write lock at every construct (three times per submit, every v4 feedback, the
grader), `LadderStore()` and the gate-failure table ran their DDL per request, and pure reads (`holds_slot`, `count`,
`released_on_infra`, `submission_block`, `later_own_holds_the_round`, `allowance`, `admission_refusal`, the Ladder rows,
`gate_failure_feedback.read`) queued on the write lock behind every grade settle. Now a preparation runs once per process
per ledger FILE (path and inode) and the reads use a DEFERRED snapshot.
"""

from __future__ import annotations

import os

import pytest

from carbon.challenge_validator import exam_cap
from carbon.challenge_validator import gate_failure_feedback as gff
from carbon.challenge_validator import ladder_store
from carbon.challenge_validator import ledger as ledger_module
from carbon.challenge_validator.ledger import AttemptLedger

SID = "rtsk_" + "1" * 64
EXAM = "sha256:" + "e" * 64
HOTKEY = "5" + "H" * 47


@pytest.fixture
def ledger(tmp_path):
    directory = tmp_path / "state"
    directory.mkdir(mode=0o700)
    return AttemptLedger(directory / "attempts.sqlite3")


@pytest.fixture
def writes(monkeypatch):
    """How many times the ledger's write lock (`AttemptLedger._db`) is entered."""
    seen = {"n": 0}
    original = AttemptLedger._db

    def counted(self):
        seen["n"] += 1
        return original(self)

    monkeypatch.setattr(AttemptLedger, "_db", counted)
    return seen


def test_exam_cap_prepares_once_per_ledger_file_and_reads_take_no_write_lock(
    ledger, writes
):
    first = exam_cap.ExamCap(ledger)
    assert writes["n"] == 1
    exam_cap.ExamCap(ledger)
    exam_cap.ExamCap(ledger)
    assert writes["n"] == 1  # one preparation per process for this file
    identity = dict(
        hotkey=HOTKEY,
        challenge_id="toy",
        challenge_version="1",
        exam_key=EXAM,
        submission_id=SID,
    )
    assert first.holds_slot(**identity) is False
    assert first.released_on_infra(**identity) is False
    assert first.count(hotkey=HOTKEY, challenge_id="toy") == 0
    assert exam_cap.submission_block(ledger, "sha256:" + "c" * 64, SID) is None
    assert (
        exam_cap.later_own_holds_the_round(
            ledger,
            "sha256:" + "c" * 64,
            hotkey=HOTKEY,
            challenge_id="toy",
            submission_id=SID,
        )
        is False
    )
    assert writes["n"] == 1  # every read above on a snapshot


def test_a_file_replaced_at_the_same_path_is_prepared_again(tmp_path):
    path = tmp_path / "x.sqlite3"
    path.write_bytes(b"")
    target = type("L", (), {"path": path})()
    runs = []
    ledger_module.prepared_once(target, "t", lambda: runs.append(1))
    ledger_module.prepared_once(target, "t", lambda: runs.append(1))
    assert runs == [1]
    other = tmp_path / "y.sqlite3"
    other.write_bytes(b"")  # both exist at once: a different inode
    os.replace(other, path)
    ledger_module.prepared_once(target, "t", lambda: runs.append(1))
    assert runs == [1, 1]
    # no path, or a file that cannot be stat'ed: prepared every time, as before
    for missing in (type("L", (), {})(), type("L", (), {"path": tmp_path / "no"})()):
        ledger_module.prepared_once(missing, "t", lambda: runs.append(1))
        ledger_module.prepared_once(missing, "t", lambda: runs.append(1))
    assert len(runs) == 6


def test_the_ladder_and_gate_failure_tables_are_prepared_once_and_read_on_a_snapshot(
    ledger, writes
):
    ladder_store.LadderStore(ledger)
    gff.ensure(ledger)
    connects = []
    original = ladder_store.sqlite3.connect

    def counted(*args, **kwargs):
        connects.append(args)
        return original(*args, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(ladder_store.sqlite3, "connect", counted)
        ladder_store.LadderStore(ledger)
        gff.ensure(ledger)
    assert connects == []  # no DDL connection the second time
    before = writes["n"]
    assert gff.read(ledger, SID, EXAM) is None
    failures = [{"output": "a", "reason": "over_limit"}]
    gff.record(ledger, SID, EXAM, failures)  # a write takes the write lock
    assert gff.read(ledger, SID, EXAM) == failures
    store = ladder_store.LadderStore(ledger)
    assert store._row((HOTKEY, "toy", "1", EXAM)) is None
    assert writes["n"] == before + 1  # only the record wrote


def test_a_read_snapshot_of_a_test_double_is_its_ordinary_transaction():
    class Double:
        def _db(self):
            return "write"

    assert ledger_module.read_snapshot(Double()) == "write"
