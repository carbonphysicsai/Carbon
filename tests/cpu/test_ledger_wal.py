"""V2 (18 Nov 2026): the attempt ledger runs in WAL mode, so a reader never holds a writer back. A copy taken with the
backup API while a writer commits keeps every row committed before the copy began."""

from __future__ import annotations

import sqlite3
import threading

from carbon.challenge_validator.ledger import AttemptLedger


def _ledger(tmp_path):
    directory = tmp_path / "ledger"
    directory.mkdir(mode=0o700)
    return AttemptLedger(directory / "attempts.sqlite3")


def test_the_ledger_is_in_wal_mode(tmp_path):
    ledger = _ledger(tmp_path)
    db = sqlite3.connect(ledger.path)
    try:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        db.close()


def test_a_reader_never_holds_the_writer_back(tmp_path):
    ledger = _ledger(tmp_path)
    with ledger._read() as reader:
        reader.execute("SELECT COUNT(*) FROM meta").fetchone()
        # a write commits while the read snapshot is open (the rollback journal made it wait)
        with ledger._db() as db:
            db.execute("INSERT INTO meta(key, value) VALUES('w', '1')")


def test_a_copy_taken_mid_write_keeps_every_committed_row(tmp_path):
    ledger = _ledger(tmp_path)
    committed, stop = [], threading.Event()

    def writer():
        n = 0
        while not stop.is_set() and n < 2000:
            with ledger._db() as db:
                db.execute("INSERT INTO meta(key, value) VALUES(?, '1')", (f"k{n}",))
            committed.append(n)
            n += 1

    thread = threading.Thread(target=writer, daemon=True)
    thread.start()
    while len(committed) < 200:
        pass
    before = len(committed)
    source = sqlite3.connect(ledger.path)
    target = sqlite3.connect(tmp_path / "copy.sqlite3")
    try:
        source.backup(target)
    finally:
        source.close()
    stop.set()
    thread.join(10)
    keys = {row[0] for row in target.execute("SELECT key FROM meta WHERE key LIKE 'k%'")}
    target.close()
    assert {f"k{n}" for n in range(before)} <= keys
