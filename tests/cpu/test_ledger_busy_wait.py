"""One attempts.sqlite3 serves a door's build rounds and grade rounds at once (switch-3 copy, 18 Nov 2026: builds hit
"database is locked" 20 times in 10 min at sqlite's 5 s default). Every connection to it waits `LEDGER_BUSY_SECONDS`
for another's write lock: a grade's exam-cap reserve or settle never fails on a brief queue of other blocks.
"""

from __future__ import annotations

import sqlite3
import threading
import time

from carbon.challenge_validator import gate_failure_feedback, ladder_store, ledger


def test_every_connection_to_the_ledger_waits_the_busy_seconds(tmp_path, monkeypatch):
    seen = []
    real = sqlite3.connect

    def connect(*args, **kwargs):
        seen.append(kwargs.get("timeout"))
        return real(*args, **kwargs)

    path = tmp_path / "ledger"
    path.mkdir(mode=0o700)
    monkeypatch.setattr(sqlite3, "connect", connect)
    attempts = ledger.AttemptLedger(path / "attempts.sqlite3")
    ladder_store.LadderStore(attempts)
    gate_failure_feedback.ensure(attempts)
    assert seen and set(seen) == {ledger.LEDGER_BUSY_SECONDS}
    assert ledger.LEDGER_BUSY_SECONDS >= 60


def test_a_ledger_block_waits_out_another_writer_instead_of_failing(tmp_path):
    """The write lock held 1 s by another connection: the block waits for it (bounded by
    `LEDGER_BUSY_SECONDS`)."""
    path = tmp_path / "ledger"
    path.mkdir(mode=0o700)
    attempts = ledger.AttemptLedger(path / "attempts.sqlite3")
    holder = sqlite3.connect(
        attempts.path, isolation_level=None, check_same_thread=False
    )
    holder.execute("BEGIN IMMEDIATE")
    threading.Timer(1.0, lambda: holder.execute("COMMIT")).start()
    began = time.monotonic()
    with attempts._db() as db:
        db.execute("SELECT 1").fetchone()
    assert time.monotonic() - began >= 0.9
    holder.close()
