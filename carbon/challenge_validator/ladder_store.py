"""Each miner's private-exam Ladder documents, stored and served
(OWNER-GRADE-FEEDBACK-LADDER-01, the serving lane of
`carbon.scoring.grade_feedback`).

One row per (hotkey, Challenge, exam) holding two documents, each exactly as
the builder emits it: ``best``, the ladder state (`grade_feedback.next_best`,
the last IMPROVED document, or none yet), and ``latest``, what the most recent
graded result showed (`ladder_feedback`, any of the builder's statuses, so a
GATE_FAILED result reaches the miner with its registered gate names). Nothing
else is stored, and nothing else is served: a document leaves this module only
after the builder's own allow-list (`FIELDS`, `SCHEMA`, and IMPROVED for the
best or any of `STATUSES` for the latest) is checked again.

The exam is keyed by the sealed evaluation pack digest, as the exam cap keys
its counts, so a rotated bank starts a fresh ladder even under an unchanged
evaluation version. The document's own ``exam_version`` is the registered
evaluation version.

The step is the builder's, max(eta, the Challenge's registered rebuild
noise): ``record`` takes that registration in the KOTH comparator's own shape
(``{"value", "measurement_digest"}``, KOTH-TAKEOVER-RULE-01 §1) or None when
none is registered, and has no default, so it cannot be left out.

The table sits beside the exam cap's in the receiver's owner-only
`AttemptLedger` file.
"""

from __future__ import annotations

import json
import sqlite3

from carbon.scoring import grade_feedback as gf

DDL = """
CREATE TABLE IF NOT EXISTS ladder_feedback(
    hotkey TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    challenge_version TEXT NOT NULL,
    exam_key TEXT NOT NULL,
    best TEXT,
    latest TEXT NOT NULL,
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


def _is_v1(raw):
    try:
        return json.loads(raw).get("schema") == gf.SCHEMA_V1
    except (ValueError, AttributeError, TypeError):
        return False


def checked(document, *, latest=False):
    """``document`` when it is exactly as the builder emits it (its
    allow-listed fields and schema, and status IMPROVED for a best document
    or any of the builder's statuses for a ``latest`` one); else refused."""
    statuses = gf.STATUSES if latest else ("IMPROVED",)
    if (
        type(document) is not dict
        or set(document) != gf.FIELDS
        or document["schema"] != gf.SCHEMA
        or document["status"] not in statuses
        or type(document["exam_version"]) is not str
        or type(document["gate_names"]) is not list
    ):
        raise LadderStoreRefused("ladder_document")
    return {name: document[name] for name in sorted(gf.FIELDS)}


def _noise_value(rebuild_noise):
    """The registered rebuild noise's value, or None when none is registered."""
    if rebuild_noise is None:
        return None
    if (
        type(rebuild_noise) is not dict
        or set(rebuild_noise) != {"value", "measurement_digest"}
        or type(rebuild_noise["measurement_digest"]) is not str
        or not rebuild_noise["measurement_digest"].startswith("sha256:")
    ):
        raise LadderStoreRefused("ladder_rebuild_noise")
    return rebuild_noise["value"]


def _raw(document, *, latest=False):
    if document is None:
        return None
    return json.dumps(
        checked(document, latest=latest), sort_keys=True, separators=(",", ":")
    )


class LadderStore:
    """Best and latest Ladder documents in the receiver's attempt ledger."""

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

    def _documents(self, key):
        with self.ledger._db() as db:
            row = db.execute(
                "SELECT best, latest FROM ladder_feedback WHERE hotkey=?"
                " AND challenge_id=? AND challenge_version=? AND exam_key=?",
                key,
            ).fetchone()
        if row is None:
            return None, None
        best, latest = row
        if _is_v1(latest):
            # A v1 document (it showed A and D) is not served; the next grade
            # starts this miner's ladder afresh under v2.
            return None, None
        return (
            None if best is None else checked(json.loads(best)),
            checked(json.loads(latest), latest=True),
        )

    def record(
        self, hotkey, challenge, exam_key, graded, *, exam_version, gates, rebuild_noise
    ):
        """Apply one graded private-exam result (the score row) and return the
        document it shows: stored as the latest, and as the best only when it
        improved. ``rebuild_noise`` is the Challenge's registration or None."""
        key = self._key(hotkey, challenge, exam_key)
        noise = _noise_value(rebuild_noise)
        best, _ = self._documents(key)
        shown = gf.ladder_feedback(
            graded,
            best=best,
            exam_version=exam_version,
            gate_registry=gates,
            rebuild_noise=noise,
        )
        kept = gf.next_best(best, shown)
        with self.ledger._db() as db:
            db.execute(
                "INSERT INTO ladder_feedback(hotkey, challenge_id, challenge_version,"
                " exam_key, best, latest, updated_ns) VALUES(?,?,?,?,?,?,?)"
                " ON CONFLICT(hotkey, challenge_id, challenge_version, exam_key)"
                " DO UPDATE SET best=excluded.best, latest=excluded.latest,"
                " updated_ns=excluded.updated_ns",
                (
                    *key,
                    _raw(kept),
                    _raw(shown, latest=True),
                    int(self.ledger.clock()),
                ),
            )
        return shown

    def served(self, hotkey, challenge, exam_key):
        """What the miner may read for this exam: ``{"best", "latest"}``, each
        a builder document or None."""
        best, latest = self._documents(self._key(hotkey, challenge, exam_key))
        return {"best": best, "latest": latest}
