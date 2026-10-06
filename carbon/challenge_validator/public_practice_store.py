"""Challenge-parameterized owner-only public-practice custody.

Only an adapter may validate and ingest its exact pinned public references.
This store holds the checked records and outcomes; it grants no reference
or scientific authority by itself.
"""

from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import stat
from pathlib import Path

from .interface import digest


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _copy(value):
    return json.loads(_canonical(value))


def _private_directory(path, fail):
    path = Path(path)
    if not path.exists():
        path.mkdir(parents=True, mode=0o700)
    try:
        info = os.lstat(path)
    except OSError:
        raise fail("store_directory_unavailable") from None
    if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise fail("store_directory_not_owner_only")
    return path


class PublicPracticeStore:
    """Owner-only SQLite custody for batches, outcomes and score records."""

    DDL = """
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS batches(
        fingerprint TEXT PRIMARY KEY,
        role TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL,
        document TEXT NOT NULL,
        state TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS refs(
        fingerprint TEXT NOT NULL,
        case_id TEXT NOT NULL,
        record TEXT NOT NULL,
        PRIMARY KEY(fingerprint, case_id),
        FOREIGN KEY(fingerprint) REFERENCES batches(fingerprint)
    );
    CREATE TABLE IF NOT EXISTS pool(
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        fingerprint TEXT NOT NULL,
        FOREIGN KEY(fingerprint) REFERENCES batches(fingerprint)
    );
    CREATE TABLE IF NOT EXISTS submissions(
        submission_id TEXT PRIMARY KEY,
        hotkey TEXT NOT NULL,
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
        self.path = self.root / f"{name}-validator.sqlite3"
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

    def prepare(self, role, kind, document):
        fingerprint = digest(document)
        with self._db() as database:
            same = database.execute(
                "SELECT fingerprint, kind, document FROM batches WHERE role = ?",
                (role,),
            ).fetchone()
            if same is not None:
                if same["kind"] != kind or same["document"] != _canonical(document):
                    raise self._fail("batch_role_changed")
                return same["fingerprint"]
            if database.execute("SELECT 1 FROM batches LIMIT 1").fetchone() is not None:
                raise self._fail("public_batch_already_prepared")
            database.execute(
                "INSERT INTO batches VALUES (?, ?, ?, ?, 'PREPARED')",
                (fingerprint, role, kind, _canonical(document)),
            )
        return fingerprint

    def batch(self, fingerprint):
        with self._db() as database:
            row = database.execute(
                "SELECT document, state FROM batches WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        if row is None:
            raise self._fail("batch_unknown")
        return _copy(json.loads(row["document"])), row["state"]

    def references(self, fingerprint):
        self.batch(fingerprint)
        with self._db() as database:
            rows = database.execute(
                "SELECT case_id, record FROM refs WHERE fingerprint = ? ORDER BY case_id",
                (fingerprint,),
            ).fetchall()
        return {row["case_id"]: json.loads(row["record"]) for row in rows}

    def ingest(self, fingerprint, records):
        self.batch(fingerprint)
        with self._db() as database:
            for case_id, record in records.items():
                encoded = _canonical(record)
                existing = database.execute(
                    "SELECT record FROM refs WHERE fingerprint = ? AND case_id = ?",
                    (fingerprint, case_id),
                ).fetchone()
                if existing is not None and existing["record"] != encoded:
                    raise self._fail("reference_changed")
                database.execute(
                    "INSERT OR IGNORE INTO refs VALUES (?, ?, ?)",
                    (fingerprint, case_id, encoded),
                )

    def open_pool(self, case_count):
        with self._db() as database:
            batches = database.execute(
                "SELECT fingerprint FROM batches ORDER BY fingerprint"
            ).fetchall()
            complete = []
            for row in batches:
                count = database.execute(
                    "SELECT COUNT(*) FROM refs WHERE fingerprint = ?",
                    (row["fingerprint"],),
                ).fetchone()[0]
                if count == case_count:
                    complete.append(row["fingerprint"])
            if len(complete) != 1:
                raise self._fail("public_references_incomplete")
            fingerprint = complete[0]
            current = database.execute(
                "SELECT fingerprint FROM pool WHERE singleton = 1"
            ).fetchone()
            if current is not None and current["fingerprint"] != fingerprint:
                raise self._fail("pool_identity_changed")
            database.execute("INSERT OR IGNORE INTO pool VALUES (1, ?)", (fingerprint,))
            database.execute(
                "UPDATE batches SET state = 'OPEN' WHERE fingerprint = ?",
                (fingerprint,),
            )
        return fingerprint

    def active_pool(self):
        with self._db() as database:
            row = database.execute(
                "SELECT fingerprint FROM pool WHERE singleton = 1"
            ).fetchone()
        return None if row is None else row["fingerprint"]

    def record_submission(self, submission_id, hotkey, strategy, outcome, score_record):
        values = (
            submission_id,
            hotkey,
            _canonical(strategy),
            _canonical(outcome),
            None if score_record is None else _canonical(score_record),
        )
        with self._db() as database:
            existing = database.execute(
                "SELECT hotkey, strategy, outcome, score_record FROM submissions "
                "WHERE submission_id = ?",
                (submission_id,),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != values[1:]:
                    raise self._fail("submission_identity_collision")
                return
            database.execute("INSERT INTO submissions VALUES (?, ?, ?, ?, ?)", values)

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

    def status(self):
        with self._db() as database:
            batches = database.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
            references = database.execute("SELECT COUNT(*) FROM refs").fetchone()[0]
            submissions = database.execute(
                "SELECT COUNT(*) FROM submissions"
            ).fetchone()[0]
            scored = database.execute(
                "SELECT COUNT(*) FROM submissions WHERE score_record IS NOT NULL"
            ).fetchone()[0]
            pool = database.execute(
                "SELECT fingerprint FROM pool WHERE singleton = 1"
            ).fetchone()
        return {
            "batches": batches,
            "references": references,
            "pool_open": pool is not None,
            "submissions": submissions,
            "scored": scored,
        }


