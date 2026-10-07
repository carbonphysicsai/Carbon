"""Challenge-neutral owner-only custody of hidden producer batches
(VALIDATOR-21).

The producer keeps its drawn batches and their reference records here, and a
validator keeps the batches it imported through the answer key here, with
their activation windows and the submissions scored on them. One shared
class, for the reason MOTOR-VAL-D5 gives: two security-sensitive stores
would drift.

The store knows no Challenge rule. The adapter validates every document and
record before they reach it, and names which reference statuses are
terminal. The store keeps:

- **batches**, by role and fingerprint, written once. A role is never
  re-drawn differently.
- **reference records**, written once per case. A batch is COMPLETE when
  every case holds a terminal record. Its references digest is
  `sha256` of the canonical `[[case_id, record], ...]` in case-id order,
  recomputed on every read and refused (`references_changed`) if a stored
  record no longer matches it.
- **windows** from the producer's commitment, written once, and the batches
  active at a block (`active`), as battery's `windowed_active`.
- **submissions**, with a per-hotkey cap counted and inserted in one
  transaction, as battery's rule v2 does.

DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import stat

from .interface import digest
from .public_practice_store import _private_directory

BATCH_STATES = ("PENDING", "COMPLETE")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def references_digest(references):
    """The digest over `{case_id: record}`, in case-id order."""
    rows = [[case_id, references[case_id]] for case_id in sorted(references)]
    return "sha256:" + hashlib.sha256(_canonical(rows).encode()).hexdigest()


class HotkeyWindowUsed(Exception):
    """The hotkey's scored submissions in this window reached the cap."""

    def __init__(self, next_block):
        super().__init__("hotkey_window_used")
        self.next_block = next_block


class HiddenBatchStore:
    """Owner-only SQLite custody of hidden batches, references, windows and
    submissions for one Challenge."""

    DDL = """
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS batches(
        fingerprint TEXT PRIMARY KEY,
        role TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL,
        document TEXT NOT NULL,
        sequence INTEGER,
        state TEXT NOT NULL,
        references_digest TEXT
    );
    CREATE TABLE IF NOT EXISTS refs(
        fingerprint TEXT NOT NULL,
        case_id TEXT NOT NULL,
        record TEXT NOT NULL,
        PRIMARY KEY(fingerprint, case_id),
        FOREIGN KEY(fingerprint) REFERENCES batches(fingerprint)
    );
    CREATE TABLE IF NOT EXISTS windows(
        fingerprint TEXT PRIMARY KEY,
        slot INTEGER NOT NULL,
        activate_block INTEGER NOT NULL,
        retire_block INTEGER NOT NULL,
        FOREIGN KEY(fingerprint) REFERENCES batches(fingerprint)
    );
    CREATE TABLE IF NOT EXISTS submissions(
        submission_id TEXT PRIMARY KEY,
        hotkey TEXT NOT NULL,
        block INTEGER,
        scored INTEGER NOT NULL,
        strategy TEXT NOT NULL,
        outcome TEXT NOT NULL,
        score_record TEXT
    );
    """

    def _fail(self, suffix):
        return self.error_type(f"{self.name}_{suffix}")

    def __init__(self, root, *, name, schema, error_type):
        self.name = name
        self.schema = schema
        self.error_type = error_type
        self.root = _private_directory(root, self._fail)
        self.path = self.root / f"{name}-hidden.sqlite3"
        if self.path.exists():
            info = os.lstat(self.path)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise self._fail("store_not_owner_only")
        else:
            os.close(os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600))
        database = sqlite3.connect(self.path, isolation_level=None)
        try:
            database.execute("PRAGMA foreign_keys = ON")
            database.executescript(self.DDL)
        finally:
            database.close()
        with self._db() as database:
            database.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('schema', ?)",
                (self.schema,),
            )
            found = database.execute(
                "SELECT value FROM meta WHERE key = 'schema'"
            ).fetchone()[0]
        if found != self.schema:
            raise self._fail("store_schema")

    @contextlib.contextmanager
    def _db(self):
        database = sqlite3.connect(self.path, timeout=30)
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA busy_timeout = 30000")
        database.execute("PRAGMA foreign_keys = ON")
        try:
            yield database
            database.commit()
        except Exception:
            database.rollback()
            raise
        finally:
            database.close()

    # --- batches ------------------------------------------------------------

    def add(self, document, *, role, kind, sequence=None):
        """Store one batch document once; return its fingerprint. The same
        role with a different document or kind is refused."""
        fingerprint = digest(document)
        with self._db() as database:
            database.execute("BEGIN IMMEDIATE")
            same = database.execute(
                "SELECT fingerprint, kind, document, sequence FROM batches "
                "WHERE role = ?",
                (role,),
            ).fetchone()
            if same is not None:
                if (
                    same["kind"] != kind
                    or same["document"] != _canonical(document)
                    or same["sequence"] != sequence
                ):
                    raise self._fail("batch_role_changed")
                return same["fingerprint"]
            if database.execute(
                "SELECT 1 FROM batches WHERE fingerprint = ?", (fingerprint,)
            ).fetchone():
                raise self._fail("batch_role_changed")
            database.execute(
                "INSERT INTO batches VALUES (?, ?, ?, ?, ?, 'PENDING', NULL)",
                (fingerprint, role, kind, _canonical(document), sequence),
            )
        return fingerprint

    def batch(self, fingerprint):
        """`{document, role, kind, sequence, state, references_digest}`."""
        with self._db() as database:
            row = database.execute(
                "SELECT document, role, kind, sequence, state, references_digest "
                "FROM batches WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        if row is None:
            raise self._fail("batch_unknown")
        value = dict(row)
        value["document"] = json.loads(value["document"])
        return value

    def fingerprints(self):
        with self._db() as database:
            rows = database.execute(
                "SELECT fingerprint FROM batches ORDER BY rowid"
            ).fetchall()
        return [row["fingerprint"] for row in rows]

    @staticmethod
    def _cases(document):
        return [case["case_id"] for case in document["cases"]]

    def references(self, fingerprint):
        self.batch(fingerprint)
        with self._db() as database:
            rows = database.execute(
                "SELECT case_id, record FROM refs WHERE fingerprint = ? "
                "ORDER BY case_id",
                (fingerprint,),
            ).fetchall()
        return {row["case_id"]: json.loads(row["record"]) for row in rows}

    def pending(self, fingerprint):
        """The batch's case ids with no terminal record yet."""
        found = self.references(fingerprint)
        return [
            c
            for c in self._cases(self.batch(fingerprint)["document"])
            if c not in found
        ]

    def ingest(self, fingerprint, records, *, terminal):
        """Store each terminal record once (others are skipped: an
        infrastructure failure is retried, never stored). Returns whether
        the batch is complete. A case outside the batch, a duplicate, or a
        stored record that changed is refused."""
        batch = self.batch(fingerprint)
        cases = set(self._cases(batch["document"]))
        seen = set()
        with self._db() as database:
            database.execute("BEGIN IMMEDIATE")
            for record in records:
                if type(record) is not dict or type(record.get("case_id")) is not str:
                    raise self._fail("reference_record_malformed")
                case_id = record["case_id"]
                if case_id not in cases:
                    raise self._fail("reference_case_not_in_batch")
                if case_id in seen:
                    raise self._fail("reference_case_duplicate")
                seen.add(case_id)
                if record.get("status") not in terminal:
                    continue
                stored = database.execute(
                    "SELECT record FROM refs WHERE fingerprint = ? AND case_id = ?",
                    (fingerprint, case_id),
                ).fetchone()
                if stored is not None:
                    if stored["record"] != _canonical(record):
                        raise self._fail("references_changed")
                    continue
                if batch["state"] == "COMPLETE":
                    raise self._fail("references_changed")
                database.execute(
                    "INSERT INTO refs VALUES (?, ?, ?)",
                    (fingerprint, case_id, _canonical(record)),
                )
        return self._complete(fingerprint)

    def _complete(self, fingerprint):
        batch = self.batch(fingerprint)
        references = self.references(fingerprint)
        if set(references) != set(self._cases(batch["document"])):
            return False
        value = references_digest(references)
        if batch["state"] == "COMPLETE":
            if batch["references_digest"] != value:
                raise self._fail("references_changed")
            return True
        with self._db() as database:
            database.execute(
                "UPDATE batches SET state = 'COMPLETE', references_digest = ? "
                "WHERE fingerprint = ? AND state = 'PENDING'",
                (value, fingerprint),
            )
        return True

    def complete_digest(self, fingerprint):
        """The references digest of a complete batch, re-derived; None while
        any case is pending."""
        if not self._complete(fingerprint):
            return None
        return self.batch(fingerprint)["references_digest"]

    # --- windows ------------------------------------------------------------

    def set_window(self, fingerprint, window):
        self.batch(fingerprint)
        values = (window["slot"], window["activate_block"], window["retire_block"])
        with self._db() as database:
            database.execute("BEGIN IMMEDIATE")
            row = database.execute(
                "SELECT slot, activate_block, retire_block FROM windows "
                "WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            if row is not None:
                if tuple(row) != values:
                    raise self._fail("window_changed")
                return
            database.execute(
                "INSERT INTO windows VALUES (?, ?, ?, ?)", (fingerprint, *values)
            )

    def window(self, fingerprint):
        with self._db() as database:
            row = database.execute(
                "SELECT slot, activate_block, retire_block FROM windows "
                "WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        return None if row is None else dict(row)

    def active(self, block, *, kind="screening"):
        """The complete batches of `kind` whose window covers `block`, by
        activation block, then fingerprint."""
        with self._db() as database:
            rows = database.execute(
                "SELECT w.fingerprint FROM windows w JOIN batches b "
                "ON b.fingerprint = w.fingerprint WHERE b.kind = ? "
                "AND b.state = 'COMPLETE' AND w.activate_block <= ? "
                "AND ? < w.retire_block ORDER BY w.activate_block, w.fingerprint",
                (kind, block, block),
            ).fetchall()
        return [row["fingerprint"] for row in rows]

    def latest_active(self, block, *, kind="screening"):
        """`active(block)`, or, when no window covers it, the batches active
        at the latest earlier activation: scoring never stalls."""
        found = self.active(block, kind=kind)
        if found:
            return found
        with self._db() as database:
            row = database.execute(
                "SELECT MAX(w.activate_block) FROM windows w JOIN batches b "
                "ON b.fingerprint = w.fingerprint WHERE b.kind = ? "
                "AND b.state = 'COMPLETE' AND w.activate_block <= ?",
                (kind, block),
            ).fetchone()
        latest = row[0]
        return [] if latest is None else self.active(latest, kind=kind)

    # --- submissions --------------------------------------------------------

    def record_submission(
        self,
        submission_id,
        hotkey,
        strategy,
        outcome,
        score_record,
        *,
        block=None,
        window=None,
    ):
        """Record a submission once. `window` is `(start, end, limit)`: the
        hotkey's scored submissions received in blocks `[start, end)`,
        counted and inserted in one transaction. A full window raises
        `HotkeyWindowUsed` and records nothing."""
        scored = int(score_record is not None)
        values = (
            submission_id,
            hotkey,
            block,
            scored,
            _canonical(strategy),
            _canonical(outcome),
            None if score_record is None else _canonical(score_record),
        )
        with self._db() as database:
            database.execute("BEGIN IMMEDIATE")
            existing = database.execute(
                "SELECT * FROM submissions WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != values:
                    raise self._fail("submission_identity_collision")
                return
            if window is not None and scored:
                start, end, limit = window
                used = database.execute(
                    "SELECT COUNT(*) FROM submissions WHERE hotkey = ? AND scored = 1 "
                    "AND block >= ? AND block < ?",
                    (hotkey, start, end),
                ).fetchone()[0]
                if used >= limit:
                    raise HotkeyWindowUsed(end)
            database.execute(
                "INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?, ?)", values
            )

    def used(self, hotkey, start, end):
        with self._db() as database:
            return database.execute(
                "SELECT COUNT(*) FROM submissions WHERE hotkey = ? AND scored = 1 "
                "AND block >= ? AND block < ?",
                (hotkey, start, end),
            ).fetchone()[0]

    def submission(self, submission_id):
        with self._db() as database:
            row = database.execute(
                "SELECT hotkey, outcome, score_record FROM submissions "
                "WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "hotkey": row["hotkey"],
            "outcome": json.loads(row["outcome"]),
            "score_record": (
                None if row["score_record"] is None else json.loads(row["score_record"])
            ),
        }

    def status(self, block=None):
        """Public counts only."""
        with self._db() as database:
            count = {
                state: database.execute(
                    "SELECT COUNT(*) FROM batches WHERE state = ?", (state,)
                ).fetchone()[0]
                for state in BATCH_STATES
            }
            windows = database.execute("SELECT COUNT(*) FROM windows").fetchone()[0]
            submissions = database.execute(
                "SELECT COUNT(*) FROM submissions"
            ).fetchone()[0]
            scored = database.execute(
                "SELECT COUNT(*) FROM submissions WHERE scored = 1"
            ).fetchone()[0]
        status = {
            "batches": count,
            "windowed": windows,
            "submissions": submissions,
            "scored": scored,
        }
        if block is not None:
            status["active"] = len(self.latest_active(block))
        return status


__all__ = [
    "HiddenBatchStore",
    "HotkeyWindowUsed",
    "references_digest",
]
