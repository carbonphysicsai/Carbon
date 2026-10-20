"""Each miner's best private-exam Ladder document, stored and served
(OWNER-GRADE-FEEDBACK-LADDER-01, the serving lane of
`carbon.scoring.grade_feedback`).

One row per (hotkey, Challenge, exam): the miner's best document, exactly as
the builder emits it (`grade_feedback.next_best` over `ladder_feedback`).
Nothing else is stored, and nothing else is served: a document leaves this
module only after the builder's own allow-list (`FIELDS`, `SCHEMA`, status
IMPROVED) is checked again.

The exam is keyed by the sealed evaluation pack digest, as the exam cap keys
its counts, so a rotated bank starts a fresh ladder even under an unchanged
evaluation version. The document's own ``exam_version`` is the registered
evaluation version.

The table sits beside the exam cap's in the receiver's owner-only
`AttemptLedger` file.
"""

from __future__ import annotations

import json
import sqlite3

from carbon.scoring import grade_feedback as gf

DDL = """
CREATE TABLE IF NOT EXISTS ladder_best(
    hotkey TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    challenge_version TEXT NOT NULL,
    exam_key TEXT NOT NULL,
    document TEXT NOT NULL,
    updated_ns INTEGER NOT NULL,
    PRIMARY KEY(hotkey, challenge_id, challenge_version, exam_key)
);
"""


class LadderStoreRefused(ValueError):
    """A key or document the store refuses; ``code`` is the closed reason."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _text(value, code):
    if type(value) is not str or not value or len(value) > 512:
        raise LadderStoreRefused(code)
    return value


def checked(document):
    """``document`` when it is a best document exactly as the builder emits
    it (its allow-listed fields, schema and IMPROVED status); else refused."""
    if (
        type(document) is not dict
        or set(document) != gf.FIELDS
        or document["schema"] != gf.SCHEMA
        or document["status"] != "IMPROVED"
        or type(document["exam_version"]) is not str
        or type(document["gate_names"]) is not list
    ):
        raise LadderStoreRefused("ladder_document")
    return {name: document[name] for name in sorted(gf.FIELDS)}


class LadderStore:
    """Best Ladder documents in the receiver's attempt ledger."""

    def __init__(self, ledger):
        self.ledger = ledger
        db = sqlite3.connect(ledger.path, isolation_level=None)
        try:
            db.executescript(DDL)
        finally:
            db.close()

    @staticmethod
    def _key(hotkey, challenge, exam_key):
        return (
            _text(hotkey, "ladder_hotkey"),
            _text(getattr(challenge, "challenge_id", None), "ladder_challenge"),
            _text(getattr(challenge, "version", None), "ladder_challenge"),
            _text(exam_key, "ladder_exam_key"),
        )

    def best(self, hotkey, challenge, exam_key):
        """The miner's best document for this exam, or None."""
        key = self._key(hotkey, challenge, exam_key)
        with self.ledger._db() as db:
            row = db.execute(
                "SELECT document FROM ladder_best WHERE hotkey=? AND challenge_id=?"
                " AND challenge_version=? AND exam_key=?",
                key,
            ).fetchone()
        return None if row is None else checked(json.loads(row[0]))

    def record(self, hotkey, challenge, exam_key, graded, *, exam_version, gates):
        """Apply one graded private-exam result (the score row) and return the
        document it shows; the stored best changes only when it improved."""
        key = self._key(hotkey, challenge, exam_key)
        best = self.best(hotkey, challenge, exam_key)
        shown = gf.ladder_feedback(
            graded, best=best, exam_version=exam_version, gate_registry=gates
        )
        kept = gf.next_best(best, shown)
        if kept is not None and kept is not best:
            raw = json.dumps(checked(kept), sort_keys=True, separators=(",", ":"))
            with self.ledger._db() as db:
                db.execute(
                    "INSERT INTO ladder_best(hotkey, challenge_id, challenge_version,"
                    " exam_key, document, updated_ns) VALUES(?,?,?,?,?,?)"
                    " ON CONFLICT(hotkey, challenge_id, challenge_version, exam_key)"
                    " DO UPDATE SET document=excluded.document,"
                    " updated_ns=excluded.updated_ns",
                    (*key, raw, int(self.ledger.clock())),
                )
        return shown

    def served(self, hotkey, challenge, exam_key):
        """What the miner may read: its best document for this exam, or None."""
        return self.best(hotkey, challenge, exam_key)
