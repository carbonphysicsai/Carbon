"""A Ladder read that fails for any reason but missing tables is never an empty Ladder (CAPS.md section 3).

`board_rows` and `latest_exam_key` used to return an empty ladder on ANY `sqlite3.OperationalError`, so a locked or
busy ledger could have signed and uploaded an EMPTY board over the real one. Now only "no such table" (the receiver
has not created the Ladder yet) reads as empty. Any other failure raises `LadderUnavailable`, a ValueError, which the
board operator turns into a REFUSED row for that board: its last good board stays served, and the other boards go on.
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest

from carbon.challenge_validator import ladder_store

CHALLENGE = SimpleNamespace(challenge_id="electric-motor-magnetics", version="1.8")
EXAM = "sha256:" + "ab" * 32


class _Failing:
    def __init__(self, message):
        self.message = message

    def execute(self, *_args, **_kwargs):
        raise sqlite3.OperationalError(self.message)

    def close(self):
        pass


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "attempts.sqlite3"
    path.write_bytes(b"")

    def failing(message):
        monkeypatch.setattr(ladder_store, "_readonly", lambda _path: _Failing(message))

    return path, failing


def test_missing_ladder_tables_still_read_as_an_empty_ladder(ledger):
    path, failing = ledger
    failing("no such table: ladder_feedback_v2")
    assert ladder_store.board_rows(path, CHALLENGE, EXAM) == []
    assert ladder_store.latest_exam_key(path, CHALLENGE) is None


@pytest.mark.parametrize(
    "message",
    ["database is locked", "disk I/O error", "database disk image is malformed"],
)
def test_any_other_read_failure_refuses_never_an_empty_ladder(ledger, message):
    path, failing = ledger
    failing(message)
    with pytest.raises(
        ladder_store.LadderUnavailable, match="ladder_ledger_unreadable"
    ):
        ladder_store.board_rows(path, CHALLENGE, EXAM)
    with pytest.raises(
        ladder_store.LadderUnavailable, match="ladder_ledger_unreadable"
    ):
        ladder_store.latest_exam_key(path, CHALLENGE)
    # the operator's refusal list catches it (a ValueError): that board is REFUSED, the run goes on
    assert issubclass(ladder_store.LadderUnavailable, ValueError)
