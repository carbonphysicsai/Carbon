"""Durable validator state for the battery exam (M3).

One owner-only SQLite file holds everything the screening pool and the
finalist comparisons must remember across a restart:
- private batch plaintexts, their journal commitments and reference records;
- which batches are prepared, active, retired, released or used as a finalist
  set;
- the pool version and the admitted-submission count;
- every admission, with its bound identities and lifecycle state;
- retained models and their stored predictions;
- screening scores, the incumbent, finalist comparisons;
- pending operations and an append-only event log.

The rules it applies are the approved ones, unchanged (`exam.DEVELOPMENT_RULE`,
OD-2):
- three active batches of 100 cases, screened as one 300-case pool;
- rotation after three admitted submissions, retiring the oldest batch;
- rotation only into a prepared batch whose references are complete.

When a rotation is due and no complete batch is prepared, the pool is
`ROTATION_PENDING`. Nothing is scored until it is resolved: an exhausted or
incomplete pool is never used silently.

Every multi-row change is one `BEGIN IMMEDIATE` transaction. A replay of a
completed step finds its row and returns it, so a restart can never count a
submission twice, rotate twice or repeat a completed solve.
"""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import time
from contextlib import contextmanager
from pathlib import Path

from . import exam

SCHEMA = "carbon.battery.validator-state.v1"
RULE = exam.DEVELOPMENT_RULE

BATCH_STATES = ("PREPARED", "ACTIVE", "RETIRED", "RELEASED", "FINALIST", "CONSUMED")
REFERENCE_STATES = ("PENDING", "COMPLETE")
SUBMISSION_STATES = (
    "ADMITTED",  # accepted, bound and queued; nothing run yet
    "RECONSTRUCTED",  # a model state is retained
    "SCORED",  # screened on a pool version (terminal for screening)
    "INVALID_CONSTRUCTION",  # refused by the contract or compiler (terminal)
    "RECONSTRUCTION_FAILED",  # the candidate's own build or prediction failed
    "FAILED_INFRA",  # infrastructure; retryable, never a score
)
DDL = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS batches(
  fingerprint TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('screening','finalist')),
  role TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  document TEXT NOT NULL,
  state TEXT NOT NULL,
  references_state TEXT NOT NULL,
  references_digest TEXT,
  activated_version INTEGER,
  retired_version INTEGER
);
CREATE TABLE IF NOT EXISTS reference_records(
  fingerprint TEXT NOT NULL, case_id TEXT NOT NULL, body TEXT NOT NULL,
  PRIMARY KEY(fingerprint, case_id));
CREATE TABLE IF NOT EXISTS pool(
  id INTEGER PRIMARY KEY CHECK(id = 1),
  version INTEGER NOT NULL,
  admitted INTEGER NOT NULL,
  active TEXT NOT NULL,
  status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS submissions(
  submission_id TEXT PRIMARY KEY,
  request_digest TEXT NOT NULL,
  hotkey TEXT NOT NULL,
  challenge TEXT NOT NULL,
  strategy TEXT NOT NULL,
  binding TEXT NOT NULL,
  state TEXT NOT NULL,
  failure TEXT,
  created REAL NOT NULL,
  updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS models(
  model_id TEXT PRIMARY KEY,
  recipe_digest TEXT NOT NULL,
  seed INTEGER NOT NULL,
  state_digest TEXT NOT NULL,
  state BLOB NOT NULL,
  reconstruction TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS predictions(
  model_id TEXT NOT NULL, case_id TEXT NOT NULL, body TEXT NOT NULL,
  PRIMARY KEY(model_id, case_id));
CREATE TABLE IF NOT EXISTS scores(
  submission_id TEXT PRIMARY KEY,
  pool_version INTEGER NOT NULL,
  record TEXT NOT NULL,
  public TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS incumbent(
  id INTEGER PRIMARY KEY CHECK(id = 1), model_id TEXT NOT NULL, reason TEXT NOT NULL,
  since REAL NOT NULL);
CREATE TABLE IF NOT EXISTS finals(
  final_id TEXT PRIMARY KEY,
  challenger TEXT NOT NULL,
  incumbent TEXT NOT NULL,
  finalist TEXT,
  frozen TEXT NOT NULL,
  state TEXT NOT NULL,
  outcome TEXT);
CREATE TABLE IF NOT EXISTS operations(
  op_id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(
  sequence INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, kind TEXT NOT NULL,
  body TEXT NOT NULL);
"""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _json(value):
    import numpy as np

    def default(item):
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(type(item).__name__)

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=default)


class StateError(RuntimeError):
    """A state transition the durable record does not allow."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class PoolStore:
    """Transactional access to the validator's durable battery state."""

    def __init__(self, path, *, clock=time.time):
        self.path = Path(path)
        self.clock = clock
        new = not self.path.exists()
        if not new:
            info = os.lstat(self.path)
            if stat.S_ISLNK(info.st_mode) or info.st_mode & 0o077:
                raise StateError("state_not_owner_only")
        with self.db() as db:
            db.executescript(DDL)
        if new:
            self.path.chmod(0o600)

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
            except BaseException:
                db.execute("ROLLBACK")
                raise
            db.execute("COMMIT")

    # --- identities ---------------------------------------------------------

    def bind(self, identities):
        """Bind the rule, contract and public-material identities once.

        A later start with different identities is refused, so a pool is
        never silently scored under another rule or other material.
        """
        with self.transaction() as db:
            row = db.execute("SELECT value FROM meta WHERE key='identities'").fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO meta VALUES('identities', ?)", (canonical(identities),)
                )
                self._event(db, "bound", identities)
            elif json.loads(row[0]) != identities:
                raise StateError("identities_changed")

    def identities(self):
        with self.db() as db:
            row = db.execute("SELECT value FROM meta WHERE key='identities'").fetchone()
        return json.loads(row[0]) if row else None

    # --- batches and references ---------------------------------------------

    def add_batch(self, committed, *, kind):
        """Record a journal-committed batch as PREPARED (idempotent)."""
        document = committed.batch.document()
        with self.transaction() as db:
            row = db.execute(
                "SELECT kind FROM batches WHERE fingerprint=?", (committed.fingerprint,)
            ).fetchone()
            if row is not None:
                if row[0] != kind:
                    raise StateError("batch_kind_conflict")
                return
            db.execute(
                "INSERT INTO batches VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    committed.fingerprint,
                    kind,
                    committed.batch.role,
                    committed.sequence,
                    canonical(document),
                    "PREPARED",
                    "PENDING",
                    None,
                    None,
                    None,
                ),
            )
            self._event(
                db,
                "batch_prepared",
                {"fingerprint": committed.fingerprint, "kind": kind},
            )

    def batch(self, fingerprint):
        with self.db() as db:
            row = db.execute(
                "SELECT fingerprint,kind,role,sequence,document,state,references_state,"
                "references_digest,activated_version,retired_version FROM batches "
                "WHERE fingerprint=?",
                (fingerprint,),
            ).fetchone()
        if row is None:
            raise StateError("unknown_batch")
        keys = (
            "fingerprint",
            "kind",
            "role",
            "sequence",
            "document",
            "state",
            "references_state",
            "references_digest",
            "activated_version",
            "retired_version",
        )
        value = dict(zip(keys, row, strict=True))
        value["document"] = json.loads(value["document"])
        return value

    def batches(self, *, kind=None, state=None):
        query, args = "SELECT fingerprint FROM batches WHERE 1=1", []
        if kind is not None:
            query, args = query + " AND kind=?", [*args, kind]
        if state is not None:
            query, args = query + " AND state=?", [*args, state]
        with self.db() as db:
            rows = db.execute(query + " ORDER BY sequence", args).fetchall()
        return [self.batch(r[0]) for r in rows]

    def needed_cases(self, fingerprint):
        """Case ids whose reference must be solved: duplicates reuse their
        original's solve, so each distinct input is solved once."""
        document = self.batch(fingerprint)["document"]
        duplicates = set(document["duplicates"])
        return [
            c["case_id"] for c in document["cases"] if c["case_id"] not in duplicates
        ]

    def record_references(self, fingerprint, records):
        """Store terminal reference records for a batch (idempotent per case).

        Only terminal truth statuses are stored. `FAILED_INFRA` is never a
        reference: it is left pending so the truth service retries it.
        """
        terminal = {"OK", "REFERENCE_SOLVER_FAILED", "REFERENCE_TIMEOUT"}
        with self.transaction() as db:
            for record in records:
                if record.get("status") not in terminal or record.get("refined"):
                    continue
                db.execute(
                    "INSERT OR IGNORE INTO reference_records VALUES(?,?,?)",
                    (fingerprint, record["case_id"], _json(record)),
                )

    def complete_references(self, fingerprint):
        """Mark a batch's references COMPLETE once every needed case has a
        terminal record; returns whether it is complete. The digest binds the
        exact records every later score will use."""
        import hashlib

        needed = self.needed_cases(fingerprint)
        with self.transaction() as db:
            rows = dict(
                db.execute(
                    "SELECT case_id, body FROM reference_records WHERE fingerprint=?",
                    (fingerprint,),
                ).fetchall()
            )
            if any(c not in rows for c in needed):
                return False
            digest = (
                "sha256:"
                + hashlib.sha256(
                    canonical(
                        [[c, json.loads(rows[c])] for c in sorted(needed)]
                    ).encode()
                ).hexdigest()
            )
            state = db.execute(
                "SELECT references_state, references_digest FROM batches "
                "WHERE fingerprint=?",
                (fingerprint,),
            ).fetchone()
            if state[0] == "COMPLETE":
                if state[1] != digest:
                    raise StateError("reference_records_changed")
                return True
            db.execute(
                "UPDATE batches SET references_state='COMPLETE', references_digest=? "
                "WHERE fingerprint=?",
                (digest, fingerprint),
            )
            self._event(
                db,
                "references_complete",
                {"fingerprint": fingerprint, "digest": digest},
            )
        return True

    def references(self, fingerprints):
        """Reference records for batches, keyed by case id, with each hidden
        duplicate given its original's record."""
        out = {}
        with self.db() as db:
            for fingerprint in fingerprints:
                for case_id, body in db.execute(
                    "SELECT case_id, body FROM reference_records WHERE fingerprint=?",
                    (fingerprint,),
                ):
                    out[case_id] = json.loads(body)
        for fingerprint in fingerprints:
            for dup, orig in self.batch(fingerprint)["document"]["duplicates"].items():
                if orig in out:
                    out[dup] = dict(out[orig], case_id=dup, duplicate_of=orig)
        return out

    # --- the screening pool --------------------------------------------------

    def pool(self):
        with self.db() as db:
            row = db.execute(
                "SELECT version, admitted, active, status FROM pool WHERE id=1"
            ).fetchone()
        if row is None:
            return None
        return {
            "version": row[0],
            "admitted": row[1],
            "active": json.loads(row[2]),
            "status": row[3],
        }

    def open_pool(self):
        """Activate the first three complete screening batches (once).

        Refused with `pool_incomplete` until three screening batches have
        complete references: the pool never starts short.
        """
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM pool WHERE id=1").fetchone():
                return self._pool_row(db)
            ready = [
                r[0]
                for r in db.execute(
                    "SELECT fingerprint FROM batches WHERE kind='screening' AND "
                    "state='PREPARED' AND references_state='COMPLETE' ORDER BY sequence"
                )
            ]
            if len(ready) < RULE["active_batches"]:
                raise StateError("pool_incomplete", f"{len(ready)} complete batches")
            active = ready[: RULE["active_batches"]]
            for fingerprint in active:
                db.execute(
                    "UPDATE batches SET state='ACTIVE', activated_version=0 "
                    "WHERE fingerprint=?",
                    (fingerprint,),
                )
            db.execute(
                "INSERT INTO pool VALUES(1, 0, 0, ?, 'OPEN')", (canonical(active),)
            )
            self._event(db, "pool_opened", {"version": 0, "active": active})
            return self._pool_row(db)

    def _pool_row(self, db):
        row = db.execute(
            "SELECT version, admitted, active, status FROM pool WHERE id=1"
        ).fetchone()
        return {
            "version": row[0],
            "admitted": row[1],
            "active": json.loads(row[2]),
            "status": row[3],
        }

    def active_case_ids(self, pool=None):
        pool = pool or self.pool()
        ids = []
        for fingerprint in pool["active"]:
            ids.extend(
                c["case_id"] for c in self.batch(fingerprint)["document"]["cases"]
            )
        return ids

    def case_inputs(self, fingerprints):
        inputs = {}
        for fingerprint in fingerprints:
            for case in self.batch(fingerprint)["document"]["cases"]:
                inputs[case["case_id"]] = dict(case["inputs"])
        return inputs

    def _try_rotate(self, db):
        """Rotate if due and possible; else mark ROTATION_PENDING. Returns the
        retired fingerprint when a rotation happened."""
        pool = self._pool_row(db)
        if pool["admitted"] < RULE["rotate_after_admitted"]:
            return None
        nxt = db.execute(
            "SELECT fingerprint FROM batches WHERE kind='screening' AND state='PREPARED' "
            "AND references_state='COMPLETE' ORDER BY sequence LIMIT 1"
        ).fetchone()
        if nxt is None:
            if pool["status"] != "ROTATION_PENDING":
                db.execute("UPDATE pool SET status='ROTATION_PENDING' WHERE id=1")
                self._event(db, "rotation_pending", {"version": pool["version"]})
            return None
        active = pool["active"]
        retired, active = active[0], [*active[1:], nxt[0]]
        version = pool["version"] + 1
        db.execute(
            "UPDATE batches SET state='RETIRED', retired_version=? WHERE fingerprint=?",
            (version, retired),
        )
        db.execute(
            "UPDATE batches SET state='ACTIVE', activated_version=? WHERE fingerprint=?",
            (version, nxt[0]),
        )
        db.execute(
            "UPDATE pool SET version=?, admitted=0, active=?, status='OPEN' WHERE id=1",
            (version, canonical(active)),
        )
        # The journal retirement is a separate file; it is recorded here as a
        # pending operation and completed idempotently (`settle_retirements`).
        db.execute(
            "INSERT OR IGNORE INTO operations VALUES(?, 'journal_retire', 'PENDING', ?)",
            ("retire:" + retired, canonical({"fingerprint": retired})),
        )
        self._event(
            db,
            "rotated",
            {"version": version, "retired": retired, "activated": nxt[0]},
        )
        return retired

    def rotate_if_ready(self):
        """Resolve a pending rotation once a complete batch is prepared."""
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM pool WHERE id=1").fetchone() is None:
                return None
            return self._try_rotate(db)

    def settle_retirements(self, journal, committed_for):
        """Complete pending journal retirements, idempotently."""
        with self.db() as db:
            pending = db.execute(
                "SELECT op_id, body FROM operations WHERE kind='journal_retire' "
                "AND state='PENDING'"
            ).fetchall()
        for op_id, body in pending:
            fingerprint = json.loads(body)["fingerprint"]
            if fingerprint not in journal.retired():
                journal.retire(committed_for(fingerprint))
            with self.transaction() as db:
                db.execute("UPDATE operations SET state='DONE' WHERE op_id=?", (op_id,))

    # --- admissions ------------------------------------------------------------

    def admit(
        self, submission_id, *, request_digest, hotkey, challenge, strategy, binding
    ):
        """Record an admission once. A replay with the same request returns
        the existing row; a different request under the same id is refused."""
        now = self.clock()
        with self.transaction() as db:
            row = db.execute(
                "SELECT request_digest FROM submissions WHERE submission_id=?",
                (submission_id,),
            ).fetchone()
            if row is not None:
                if row[0] != request_digest:
                    raise StateError("submission_replay_conflict")
                return self._submission(db, submission_id), False
            db.execute(
                "INSERT INTO submissions VALUES(?,?,?,?,?,?,'ADMITTED',NULL,?,?)",
                (
                    submission_id,
                    request_digest,
                    hotkey,
                    challenge,
                    canonical(strategy),
                    canonical(binding),
                    now,
                    now,
                ),
            )
            self._event(db, "admitted", {"submission_id": submission_id})
            return self._submission(db, submission_id), True

    def refuse(
        self, submission_id, *, request_digest, hotkey, challenge, strategy, failure
    ):
        """Record an invalid construction (terminal, never a score)."""
        now = self.clock()
        with self.transaction() as db:
            row = db.execute(
                "SELECT request_digest FROM submissions WHERE submission_id=?",
                (submission_id,),
            ).fetchone()
            if row is not None:
                if row[0] != request_digest:
                    raise StateError("submission_replay_conflict")
                return self._submission(db, submission_id)
            db.execute(
                "INSERT INTO submissions VALUES(?,?,?,?,?,?,'INVALID_CONSTRUCTION',?,?,?)",
                (
                    submission_id,
                    request_digest,
                    hotkey,
                    challenge,
                    canonical(strategy) if _jsonable(strategy) else "null",
                    "{}",
                    canonical(failure),
                    now,
                    now,
                ),
            )
            self._event(db, "refused", {"submission_id": submission_id, **failure})
            return self._submission(db, submission_id)

    def _submission(self, db, submission_id):
        row = db.execute(
            "SELECT submission_id, hotkey, challenge, strategy, binding, state, failure, "
            "request_digest FROM submissions WHERE submission_id=?",
            (submission_id,),
        ).fetchone()
        if row is None:
            raise StateError("unknown_submission")
        return {
            "submission_id": row[0],
            "hotkey": row[1],
            "challenge": row[2],
            "strategy": json.loads(row[3]),
            "binding": json.loads(row[4]),
            "state": row[5],
            "failure": json.loads(row[6]) if row[6] else None,
            "request_digest": row[7],
        }

    def submission(self, submission_id):
        with self.db() as db:
            return self._submission(db, submission_id)

    def pending_submissions(self):
        with self.db() as db:
            rows = db.execute(
                "SELECT submission_id FROM submissions WHERE state IN "
                "('ADMITTED','RECONSTRUCTED','FAILED_INFRA') ORDER BY created, "
                "submission_id"
            ).fetchall()
        return [r[0] for r in rows]

    def mark(self, submission_id, state, failure=None):
        if state not in SUBMISSION_STATES:
            raise StateError("unknown_state", state)
        with self.transaction() as db:
            db.execute(
                "UPDATE submissions SET state=?, failure=?, updated=? "
                "WHERE submission_id=?",
                (
                    state,
                    canonical(failure) if failure else None,
                    self.clock(),
                    submission_id,
                ),
            )
            self._event(
                db,
                "state",
                {
                    "submission_id": submission_id,
                    "state": state,
                    **({"failure": failure} if failure else {}),
                },
            )

    # --- models and predictions -------------------------------------------------

    def retain_model(self, model_id, *, recipe_digest, seed, state, reconstruction):
        import hashlib

        digest = "sha256:" + hashlib.sha256(state).hexdigest()
        with self.transaction() as db:
            row = db.execute(
                "SELECT state_digest FROM models WHERE model_id=?", (model_id,)
            ).fetchone()
            if row is not None:
                # A replayed reconstruction keeps the first retained state.
                return row[0]
            db.execute(
                "INSERT INTO models VALUES(?,?,?,?,?,?)",
                (
                    model_id,
                    recipe_digest,
                    seed,
                    digest,
                    state,
                    canonical(reconstruction),
                ),
            )
        return digest

    def model_state(self, model_id):
        with self.db() as db:
            row = db.execute(
                "SELECT state, state_digest, reconstruction, recipe_digest, seed "
                "FROM models WHERE model_id=?",
                (model_id,),
            ).fetchone()
        if row is None:
            return None
        import hashlib

        if "sha256:" + hashlib.sha256(row[0]).hexdigest() != row[1]:
            raise StateError("model_state_changed")
        return {
            "state": row[0],
            "digest": row[1],
            "reconstruction": json.loads(row[2]),
            "recipe_digest": row[3],
            "seed": row[4],
        }

    def store_predictions(self, model_id, predictions):
        with self.transaction() as db:
            for case_id, body in predictions.items():
                db.execute(
                    "INSERT OR IGNORE INTO predictions VALUES(?,?,?)",
                    (model_id, case_id, json.dumps(body)),
                )

    def predictions(self, model_id, case_ids):
        with self.db() as db:
            rows = dict(
                db.execute(
                    "SELECT case_id, body FROM predictions WHERE model_id=?",
                    (model_id,),
                ).fetchall()
            )
        return {c: json.loads(rows[c]) for c in case_ids if c in rows}

    # --- screening scores ---------------------------------------------------------

    def record_score(self, submission_id, record, public, *, expected_version):
        """Record one screening score, count it, and rotate if due - atomically.

        Idempotent: a replay returns the stored score and counts nothing.
        Refused if the pool moved since the score was computed, so a score is
        never recorded against a pool it was not computed on.
        """
        with self.transaction() as db:
            row = db.execute(
                "SELECT pool_version, record, public FROM scores WHERE submission_id=?",
                (submission_id,),
            ).fetchone()
            if row is not None:
                return {
                    "pool_version": row[0],
                    "record": json.loads(row[1]),
                    "public": json.loads(row[2]),
                    "replayed": True,
                }
            pool = self._pool_row(db)
            if pool["status"] != "OPEN" or pool["version"] != expected_version:
                raise StateError("pool_moved")
            db.execute(
                "INSERT INTO scores VALUES(?,?,?,?)",
                (submission_id, pool["version"], _json(record), _json(public)),
            )
            db.execute(
                "UPDATE submissions SET state='SCORED', updated=? WHERE submission_id=?",
                (self.clock(), submission_id),
            )
            db.execute("UPDATE pool SET admitted=admitted+1 WHERE id=1")
            self._event(
                db,
                "scored",
                {"submission_id": submission_id, "pool_version": pool["version"]},
            )
            retired = self._try_rotate(db)
            return {
                "pool_version": pool["version"],
                "record": record,
                "public": public,
                "replayed": False,
                "retired": retired,
            }

    def score(self, submission_id):
        with self.db() as db:
            row = db.execute(
                "SELECT pool_version, record, public FROM scores WHERE submission_id=?",
                (submission_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "pool_version": row[0],
            "record": json.loads(row[1]),
            "public": json.loads(row[2]),
        }

    # --- incumbent and finals ---------------------------------------------------------

    def incumbent(self):
        with self.db() as db:
            row = db.execute(
                "SELECT model_id, reason FROM incumbent WHERE id=1"
            ).fetchone()
        return None if row is None else {"model_id": row[0], "reason": row[1]}

    def set_incumbent(self, model_id, reason, *, expected=None):
        with self.transaction() as db:
            row = db.execute("SELECT model_id FROM incumbent WHERE id=1").fetchone()
            current = row[0] if row else None
            if current == model_id:
                return
            if current != expected:
                raise StateError("incumbent_moved")
            db.execute(
                "INSERT OR REPLACE INTO incumbent VALUES(1, ?, ?, ?)",
                (model_id, reason, self.clock()),
            )
            self._event(
                db,
                "incumbent",
                {"model_id": model_id, "reason": reason, "previous": current},
            )

    def freeze_final(self, final_id, *, challenger, incumbent, frozen):
        """Freeze a finalist comparison before any finalist input is used."""
        with self.transaction() as db:
            row = db.execute(
                "SELECT frozen FROM finals WHERE final_id=?", (final_id,)
            ).fetchone()
            if row is not None:
                if json.loads(row[0]) != frozen:
                    raise StateError("final_replay_conflict")
                return False
            db.execute(
                "INSERT INTO finals VALUES(?,?,?,NULL,?,'FROZEN',NULL)",
                (final_id, challenger, incumbent, canonical(frozen)),
            )
            self._event(db, "final_frozen", {"final_id": final_id})
            return True

    def claim_finalist_set(self, final_id):
        """Assign one prepared, complete finalist batch to a frozen final."""
        with self.transaction() as db:
            row = db.execute(
                "SELECT finalist FROM finals WHERE final_id=?", (final_id,)
            ).fetchone()
            if row is None:
                raise StateError("unknown_final")
            if row[0]:
                return row[0]
            nxt = db.execute(
                "SELECT fingerprint FROM batches WHERE kind='finalist' AND "
                "state='PREPARED' AND references_state='COMPLETE' ORDER BY sequence LIMIT 1"
            ).fetchone()
            if nxt is None:
                return None
            db.execute(
                "UPDATE batches SET state='FINALIST' WHERE fingerprint=?", (nxt[0],)
            )
            db.execute(
                "UPDATE finals SET finalist=? WHERE final_id=?", (nxt[0], final_id)
            )
            self._event(
                db, "finalist_assigned", {"final_id": final_id, "fingerprint": nxt[0]}
            )
            return nxt[0]

    def complete_final(self, final_id, outcome):
        with self.transaction() as db:
            row = db.execute(
                "SELECT state, finalist, outcome FROM finals WHERE final_id=?",
                (final_id,),
            ).fetchone()
            if row[0] == "DECIDED":
                return json.loads(row[2])
            db.execute(
                "UPDATE finals SET state='DECIDED', outcome=? WHERE final_id=?",
                (_json(outcome), final_id),
            )
            db.execute(
                "UPDATE batches SET state='CONSUMED' WHERE fingerprint=?", (row[1],)
            )
            db.execute(
                "INSERT OR IGNORE INTO operations VALUES(?, 'journal_retire', "
                "'PENDING', ?)",
                ("retire:" + row[1], canonical({"fingerprint": row[1]})),
            )
            self._event(
                db,
                "final_decided",
                {"final_id": final_id, "outcome": outcome.get("outcome")},
            )
            return outcome

    def final_attempt(self, final_id):
        """The attempt a finalist comparison's worker runs are named with."""
        with self.db() as db:
            row = db.execute(
                "SELECT body FROM operations WHERE op_id=?",
                ("final-attempt:" + final_id,),
            ).fetchone()
        return 0 if row is None else json.loads(row[0])["attempt"]

    def bump_final_attempt(self, final_id, attempt):
        """After an infrastructure failure: the retry uses a new identity."""
        with self.transaction() as db:
            db.execute(
                "INSERT OR REPLACE INTO operations VALUES(?, 'final_attempt', "
                "'RECORDED', ?)",
                ("final-attempt:" + final_id, canonical({"attempt": attempt})),
            )
            self._event(db, "final_failed_infra", {"final": final_id, "next": attempt})

    def final(self, final_id):
        with self.db() as db:
            row = db.execute(
                "SELECT final_id, challenger, incumbent, finalist, frozen, state, outcome "
                "FROM finals WHERE final_id=?",
                (final_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "final_id": row[0],
            "challenger": row[1],
            "incumbent": row[2],
            "finalist": row[3],
            "frozen": json.loads(row[4]),
            "state": row[5],
            "outcome": json.loads(row[6]) if row[6] else None,
        }

    def open_finals(self):
        with self.db() as db:
            rows = db.execute(
                "SELECT final_id FROM finals WHERE state='FROZEN' ORDER BY rowid"
            ).fetchall()
        return [r[0] for r in rows]

    # --- release -----------------------------------------------------------------------

    def releasable(self):
        """Retired or consumed batches that no still-private evaluation needs.

        A retired screening batch is still needed while any stored score or
        open final references its cases through a pool version it belonged
        to and the incumbent comparison could be asked again; under this
        rule a batch is releasable once retired or consumed and no open final
        holds it. Release publishes nothing by itself: `mark_released` only
        records that the journal reveal was made.
        """
        with self.db() as db:
            rows = db.execute(
                "SELECT fingerprint FROM batches WHERE state IN ('RETIRED','CONSUMED') "
                "ORDER BY sequence"
            ).fetchall()
            held = {
                r[0]
                for r in db.execute("SELECT finalist FROM finals WHERE state='FROZEN'")
            }
        return [r[0] for r in rows if r[0] not in held]

    def mark_released(self, fingerprint):
        with self.transaction() as db:
            state = db.execute(
                "SELECT state FROM batches WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            if state is None or state[0] not in ("RETIRED", "CONSUMED", "RELEASED"):
                raise StateError("release_before_retirement")
            db.execute(
                "UPDATE batches SET state='RELEASED' WHERE fingerprint=?",
                (fingerprint,),
            )
            self._event(db, "released", {"fingerprint": fingerprint})

    # --- events --------------------------------------------------------------------------

    def _event(self, db, kind, body):
        db.execute(
            "INSERT INTO events(at, kind, body) VALUES(?,?,?)",
            (self.clock(), kind, _json(body)),
        )

    def events(self, kind=None):
        with self.db() as db:
            rows = db.execute(
                "SELECT sequence, kind, body FROM events ORDER BY sequence"
            ).fetchall()
        return [
            {"sequence": s, "kind": k, "body": json.loads(b)}
            for s, k, b in rows
            if kind is None or k == kind
        ]


def _jsonable(value):
    try:
        canonical(value)
    except (TypeError, ValueError):
        return False
    return True
