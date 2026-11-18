"""Live 116 stacks (18 Nov 2026): the advance pass's per-task owner reads took `BEGIN IMMEDIATE` each, so 17 threads
queued on the ledger's write lock and the grade claimer's own write waited behind them. The hot reads now take a
DEFERRED transaction (`AttemptLedger._read`): they read while another connection holds the write lock, and never
hold it themselves."""

from __future__ import annotations

import sqlite3

from carbon.challenge_validator import AttemptLedger


def test_the_hot_reads_answer_while_a_writer_holds_the_lock_and_never_take_it(
    tmp_path,
):
    ledger = AttemptLedger(tmp_path / "attempts.sqlite3")
    contract = "sha256:" + "c" * 64
    task = "rtsk_" + "a" * 64
    with ledger._db() as db:
        db.execute(
            "INSERT INTO attempts(at_ns, kind, hotkey, contract_digest, receipt, submission_sha256, "
            "submission_id) VALUES(5, 'OUTCOME', '5Owner', ?, '{}', 'sha256:s', ?)",
            (contract, task),
        )
    writer = sqlite3.connect(ledger.path, isolation_level=None)
    writer.execute("BEGIN IMMEDIATE")  # another round's write in progress
    try:
        assert ledger.owned_outcome(contract, task) == "5Owner"
        assert ledger.submitted_outcomes(contract) == (task,)
        assert ledger.first_outcome_ns(contract, task) == 5
    finally:
        writer.execute("ROLLBACK")
        writer.close()
    # and a reader holds no write lock: a writer starts at once while a read is open
    with ledger._read() as db:
        db.execute("SELECT COUNT(*) FROM attempts").fetchone()
        other = sqlite3.connect(ledger.path, isolation_level=None, timeout=0)
        try:
            other.execute("BEGIN IMMEDIATE")
            other.execute("ROLLBACK")
        finally:
            other.close()
