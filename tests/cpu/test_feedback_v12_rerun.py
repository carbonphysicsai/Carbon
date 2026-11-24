"""Feedback v12 (miner-ux 6054, v2 6039 (3)): the caller's own submission that the DOOR re-ran as a new task reads RERUN
with the new id (`AttemptLedger.requeued_as`), never QUEUED; a miner's own resubmission and another hotkey's task never
name an id."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_build_requeue import CONTRACT, HOTKEYS, A, C, N, _outcome, _queue

from carbon.challenge_validator import direct_intake
from carbon.challenge_validator.ledger import AttemptLedger


@pytest.fixture
def book(tmp_path):
    clock = iter(range(1000, 100_000, 10))
    return AttemptLedger(tmp_path / "attempts.sqlite3", clock=lambda: next(clock))


def test_the_door_requeue_names_its_new_task_for_the_same_hotkey_only(book):
    _queue(book)
    assert book.requeued_as(CONTRACT, A, HOTKEYS[0]) is None  # nothing re-run yet
    requeued = book.requeue_failed_build(
        CONTRACT, from_task=A, new_task=N, hotkey=HOTKEYS[0]
    )
    assert requeued == "requeued"
    assert book.requeued_as(CONTRACT, A, HOTKEYS[0]) == N
    assert book.requeued_as(CONTRACT, A, HOTKEYS[1]) is None  # never another hotkey's
    assert book.requeued_as(CONTRACT, N, HOTKEYS[0]) is None  # N itself not re-run
    assert book.requeued_as("sha256:" + "0" * 64, A, HOTKEYS[0]) is None
    for bad in (None, "", 7):
        assert book.requeued_as(CONTRACT, bad, HOTKEYS[0]) is None


def test_a_miners_own_resubmission_after_a_stop_is_not_a_rerun(book):
    _queue(book)
    resubmitted = "rtsk_" + "e" * 64
    _outcome(book, resubmitted)
    granted = book.grant_queue_place(
        CONTRACT, from_task=A, new_task=resubmitted, hotkey=HOTKEYS[0]
    )
    assert granted == "granted"
    assert book.requeued_as(CONTRACT, A, HOTKEYS[0]) is None
    assert book.requeued_as(CONTRACT, C, HOTKEYS[0]) is None


def test_v12_is_opt_in_advertised_and_names_the_state():
    reply = direct_intake.feedback_reply({"reply": "v12", "submission_id": "t"})
    assert reply == "v12"
    assert direct_intake.FEEDBACK_REPLY_SCHEMA_V12.endswith(".v12")
    assert direct_intake.RERUN_STATE == "RERUN"
    text = Path(direct_intake.__file__).read_text(encoding="utf-8")
    assert '"exam_feedback_v12"' in text
    assert '**({"rerun_task_id": rerun_task_id} if v12 else {})' in text
