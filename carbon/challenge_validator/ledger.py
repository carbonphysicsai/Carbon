"""The operator-side attempt ledger: every submission attempt, refusals included.

Track A needs a full attempt ledger, unsuccessful attacks included
(Challenge_Admission §3), so a submission the validator refuses before any
adapter sees it is still recorded. Track A family 8 (adaptive exposure) needs
per-hotkey attempt counts.

The ledger is operator-only. It is never scored, never miner-visible and never
touches adapter state. It keeps the submission's hash, never its strategy, so
hostile content is not stored. Over-long identity strings are kept by digest
only.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import stat
import time
from pathlib import Path

SCHEMA = "carbon.challenge-validator.ledger.v1"
#: Every attempt ends as one of these. `RECEIVED` is a submission a queueing
#: transport (battery's intake) screened and queued for the adapter's own
#: worker; its later outcome is the adapter's, joined by submission id.
KINDS = ("OUTCOME", "RECEIVED", "REFUSED", "UNAVAILABLE", "FAILED_INFRA")
#: Identity strings longer than this are kept by digest only.
MAX_KEPT = 128
DDL = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS attempts(
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    at_ns INTEGER NOT NULL,
    kind TEXT NOT NULL,
    code TEXT,
    hotkey TEXT,
    contract_digest TEXT,
    receipt TEXT,
    submission_sha256 TEXT NOT NULL,
    submission_id TEXT,
    state TEXT
);
CREATE INDEX IF NOT EXISTS attempts_hotkey ON attempts(hotkey);
CREATE TABLE IF NOT EXISTS operator_refusals(
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    at_ns INTEGER NOT NULL,
    action TEXT NOT NULL,
    code TEXT NOT NULL,
    contract_digest TEXT
);
"""


class LedgerUnavailable(RuntimeError):
    """The ledger cannot be opened safely; the validator refuses to run."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _kept(value):
    """A string as recorded: itself if short, else its digest; never content
    of another type."""
    if type(value) is not str:
        return None if value is None else "<" + type(value).__name__ + ">"
    try:
        body = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        body = value.encode("utf-8", errors="surrogatepass")
        return "sha256:" + hashlib.sha256(body).hexdigest()
    if len(value) <= MAX_KEPT and value.isprintable():
        return value
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _receipt(value):
    """A well-formed receipt (short keys, int or short printable string
    values) as JSON; anything else only by digest."""
    if type(value) is not dict:
        return None
    simple = len(value) <= 16 and all(
        type(k) is str
        and len(k) <= MAX_KEPT
        and k.isprintable()
        and (
            v is None
            or type(v) is int
            or (type(v) is str and len(v) <= MAX_KEPT and v.isprintable())
        )
        for k, v in value.items()
    )
    try:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        return json.dumps({"unencodable": True})
    if not simple:
        body = text.encode("utf-8", errors="surrogatepass")
        return json.dumps({"sha256": hashlib.sha256(body).hexdigest()})
    return text


def submission_sha256(submission):
    """A hash over every field of a submission as received, whatever its types."""
    h = hashlib.sha256()
    for name in (
        "hotkey",
        "receipt",
        "challenge_id",
        "challenge_version",
        "strategy_json",
        "contract_digest",
    ):
        value = getattr(submission, name, None)
        if type(value) is bytes:
            body = b"b" + value
        elif type(value) is str:
            body = b"s" + value.encode("utf-8", errors="surrogatepass")
        else:
            try:
                body = (
                    b"j"
                    + json.dumps(
                        value, sort_keys=True, separators=(",", ":"), allow_nan=False
                    ).encode()
                )
            except (TypeError, ValueError):
                body = b"t" + type(value).__name__.encode()
        h.update(name.encode() + b"\0" + len(body).to_bytes(8, "big") + body)
    return "sha256:" + h.hexdigest()


class AttemptLedger:
    """An owner-only SQLite ledger of submission attempts."""

    def __init__(self, path, *, clock=time.time_ns):
        self.path = Path(path)
        self.clock = clock
        parent = self.path.parent
        try:
            info = os.lstat(parent)
        except OSError:
            raise LedgerUnavailable("ledger_directory_missing") from None
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
            raise LedgerUnavailable("ledger_directory_not_owner_only")
        if self.path.exists():
            info = os.lstat(self.path)
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise LedgerUnavailable("ledger_not_owner_only")
        else:
            os.close(os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600))
        db = sqlite3.connect(self.path, isolation_level=None)
        try:
            # `executescript` commits on its own, so it runs outside `_db`.
            db.executescript(DDL)
        finally:
            db.close()
        with self._db() as db:
            db.execute(
                "INSERT OR IGNORE INTO meta(key, value) VALUES('schema', ?)", (SCHEMA,)
            )
            row = db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
        if row[0] != SCHEMA:
            raise LedgerUnavailable("ledger_schema")

    @contextlib.contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, isolation_level=None)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def record(self, submission, *, kind, code=None, submission_id=None, state=None):
        if kind not in KINDS:
            raise ValueError("unknown attempt kind")
        with self._db() as db:
            db.execute(
                "INSERT INTO attempts(at_ns, kind, code, hotkey, contract_digest,"
                " receipt, submission_sha256, submission_id, state)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    int(self.clock()),
                    kind,
                    code,
                    _kept(getattr(submission, "hotkey", None)),
                    _kept(getattr(submission, "contract_digest", None)),
                    _receipt(getattr(submission, "receipt", None)),
                    submission_sha256(submission),
                    submission_id,
                    state,
                ),
            )

    def record_operator_refusal(self, action, code, contract_digest):
        with self._db() as db:
            db.execute(
                "INSERT INTO operator_refusals(at_ns, action, code, contract_digest)"
                " VALUES(?,?,?,?)",
                (int(self.clock()), action, code, _kept(contract_digest)),
            )

    def attempts(self, *, hotkey=None):
        keys = (
            "seq",
            "at_ns",
            "kind",
            "code",
            "hotkey",
            "contract_digest",
            "receipt",
            "submission_sha256",
            "submission_id",
            "state",
        )
        query, args = "SELECT " + ",".join(keys) + " FROM attempts", ()
        if hotkey is not None:
            query, args = query + " WHERE hotkey=?", (_kept(hotkey),)
        with self._db() as db:
            rows = db.execute(query + " ORDER BY seq", args).fetchall()
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def operator_refusals(self):
        with self._db() as db:
            rows = db.execute(
                "SELECT action, code, contract_digest FROM operator_refusals"
                " ORDER BY seq"
            ).fetchall()
        return [{"action": a, "code": c, "contract_digest": d} for a, c, d in rows]

    def totals(self):
        """Attempts by kind across every hotkey: counts only, for the
        operator's status."""
        with self._db() as db:
            rows = db.execute(
                "SELECT kind, COUNT(*) FROM attempts GROUP BY kind"
            ).fetchall()
        return {**dict.fromkeys(KINDS, 0), **dict(rows)}

    def attempt_counts(self, hotkey):
        """Attempts by this hotkey: in total, by kind and by contract digest."""
        with self._db() as db:
            rows = db.execute(
                "SELECT kind, contract_digest, COUNT(*) FROM attempts"
                " WHERE hotkey=? GROUP BY kind, contract_digest",
                (_kept(hotkey),),
            ).fetchall()
        by_kind, by_contract = dict.fromkeys(KINDS, 0), {}
        for kind, contract, count in rows:
            by_kind[kind] += count
            by_contract[contract] = by_contract.get(contract, 0) + count
        return {
            "total": sum(by_kind.values()),
            "by_kind": by_kind,
            "by_contract": by_contract,
        }


__all__ = ["KINDS", "AttemptLedger", "LedgerUnavailable", "submission_sha256"]
