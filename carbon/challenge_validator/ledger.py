"""The operator-side attempt ledger: every submission attempt, refusals included.

Track A needs a full attempt ledger, unsuccessful attacks included
(Challenge_Admission §3), so a submission the validator refuses before any
adapter sees it is still recorded. Track A family 8 (adaptive exposure) needs
per-hotkey attempt counts.

The ledger is operator-only. It is never scored and never touches adapter state.
PLT-08 publishes only a closed, count-only projection through public_status_counts.
It keeps the submission's hash, never its strategy, so
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
#: How long a ledger connection waits for another's write lock before "database is locked" (sqlite's default is 5 s).
#: One attempts.sqlite3 serves the door's build rounds and its grade rounds at once (switch 3, 18 Nov 2026: builds
#: failed it 20 times in 10 min; a grade's exam-cap reserve or settle failing it ends the grade as Carbon's, burning
#: its one retry, or settles it UNAVAILABLE). Every block is short SQL or a requeue decision: a wait, never a refusal.
LEDGER_BUSY_SECONDS = 60.0
#: Every attempt ends as one of these. `RECEIVED` is a submission a queueing
#: transport (battery's intake) screened and queued for the adapter's own
#: worker; its later outcome is the adapter's, joined by submission id.
KINDS = ("OUTCOME", "RECEIVED", "REFUSED", "UNAVAILABLE", "FAILED_INFRA")
#: Identity strings longer than this are kept by digest only.
MAX_KEPT = 128
#: An engineering limit, not a policy value: at most this many REFUSED rows per
#: hotkey in any rolling hour. Beyond it each refusal is still counted, in the
#: `overflow` tally, so attempt counts stay exact while the table stays bounded
#: (VALIDATOR-01 security review, finding 7). How long rows are kept is the
#: owner's retention decision; nothing here deletes.
MAX_REFUSED_ROWS_PER_HOUR = 120
HOUR_NS = 3600 * 10**9
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
CREATE INDEX IF NOT EXISTS attempts_recent ON attempts(hotkey, kind, at_ns);
CREATE INDEX IF NOT EXISTS attempts_submission_owner
    ON attempts(contract_digest, submission_id, kind);
CREATE TABLE IF NOT EXISTS recipe_task_intents(
    contract_digest TEXT NOT NULL,
    submission_id TEXT NOT NULL,
    hotkey TEXT NOT NULL,
    request_sha256 TEXT NOT NULL,
    PRIMARY KEY(contract_digest, submission_id)
);
CREATE TABLE IF NOT EXISTS queue_place_grants(
    contract_digest TEXT NOT NULL,
    new_task TEXT NOT NULL,
    from_task TEXT NOT NULL,
    hotkey TEXT NOT NULL,
    place_seq INTEGER NOT NULL,
    granted_ns INTEGER NOT NULL,
    PRIMARY KEY(contract_digest, new_task),
    UNIQUE(contract_digest, from_task)
);
CREATE TABLE IF NOT EXISTS miner_withdrawals(
    contract_digest TEXT NOT NULL,
    submission_id TEXT PRIMARY KEY,
    hotkey TEXT NOT NULL,
    at_ns INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS catalog_submissions(
    contract_digest TEXT NOT NULL,
    submission_id TEXT NOT NULL,
    document BLOB NOT NULL,
    PRIMARY KEY(contract_digest, submission_id)
);
CREATE TABLE IF NOT EXISTS overflow(
    hotkey TEXT NOT NULL,
    hour INTEGER NOT NULL,
    kind TEXT NOT NULL,
    code TEXT NOT NULL,
    contract_digest TEXT NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY(hotkey, hour, kind, code, contract_digest)
);
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


def _place(db, contract_digest, task, own_seq):
    """The queue place ``task`` gives (`grant_queue_place`, `requeue_failed_build`): the place it holds itself when it
    took another task's (a chain: a requeue of a stop-cancel resubmission keeps the original's), else its own first
    accepted-submission sequence."""
    held = db.execute(
        "SELECT place_seq FROM queue_place_grants WHERE contract_digest=? AND new_task=?",
        (contract_digest, task),
    ).fetchone()
    return int(own_seq if held is None else held[0])


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
        db = sqlite3.connect(
            self.path, isolation_level=None, timeout=LEDGER_BUSY_SECONDS
        )
        try:
            # `executescript` commits on its own, so it runs outside `_db`.
            db.executescript(DDL)
            # V2 (18 Nov 2026): WAL, so readers (`_read`: the advance passes) never hold a writer back and a writer never
            # holds a reader (live 116: the rollback journal let 6 readers starve the grade claim's write). Persistent in
            # the file; every copier takes the backup API or a checkpoint + db/wal/shm (Deploy's audit). A filesystem
            # that refuses WAL keeps the default journal, unchanged.
            db.execute("PRAGMA journal_mode=WAL")
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
        db = sqlite3.connect(
            self.path, isolation_level=None, timeout=LEDGER_BUSY_SECONDS
        )
        try:
            # A BEGIN that fails (e.g. 'database is locked') is raised as itself: there is no transaction to roll back,
            # and a ROLLBACK here would replace the real cause with 'cannot rollback' (RB door, 4affa5b9, 9 Nov).
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        finally:
            db.close()

    @contextlib.contextmanager
    def _read(self):
        """A read-only connection: one DEFERRED transaction (a consistent snapshot), never the write lock, so readers
        never queue behind each other or hold a writer back while they read. Live 116, 18 Nov 2026: the advance pass's
        per-task owner reads (`BEGIN IMMEDIATE` each) queued 17 threads on the write lock, the grade claimer's write
        among them."""
        db = sqlite3.connect(
            self.path, isolation_level=None, timeout=LEDGER_BUSY_SECONDS
        )
        try:
            db.execute("BEGIN")
            try:
                yield db
            finally:
                db.execute("ROLLBACK")
        finally:
            db.close()

    def record(self, submission, *, kind, code=None, submission_id=None, state=None):
        if kind not in KINDS:
            raise ValueError("unknown attempt kind")
        now = int(self.clock())
        hotkey = _kept(getattr(submission, "hotkey", None))
        digest_kept = _kept(getattr(submission, "contract_digest", None))
        with self._db() as db:
            if kind == "REFUSED" and hotkey is not None:
                recent = db.execute(
                    "SELECT COUNT(*) FROM attempts WHERE hotkey=? AND kind='REFUSED'"
                    " AND at_ns>?",
                    (hotkey, now - HOUR_NS),
                ).fetchone()[0]
                if recent >= MAX_REFUSED_ROWS_PER_HOUR:
                    db.execute(
                        "INSERT INTO overflow VALUES(?,?,?,?,?,1) ON CONFLICT("
                        "hotkey, hour, kind, code, contract_digest) DO UPDATE SET"
                        " count=count+1",
                        (hotkey, now // HOUR_NS, kind, code or "", digest_kept or ""),
                    )
                    return
            db.execute(
                "INSERT INTO attempts(at_ns, kind, code, hotkey, contract_digest,"
                " receipt, submission_sha256, submission_id, state)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    now,
                    kind,
                    code,
                    hotkey,
                    digest_kept,
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

    def owned_outcome(self, contract_digest, submission_id):
        """One authenticated owner of a submitted task, or no usable owner.

        A recipe intent is committed before the direct task, closing the
        cross-ledger crash gap. Ambiguous ownership fails closed.
        """
        with self._read() as db:
            rows = db.execute(
                "SELECT DISTINCT hotkey FROM ("
                "SELECT hotkey FROM attempts WHERE kind='OUTCOME' "
                "AND contract_digest=? AND submission_id=? AND hotkey IS NOT NULL "
                "UNION ALL SELECT hotkey FROM recipe_task_intents "
                "WHERE contract_digest=? AND submission_id=? )",
                (contract_digest, submission_id, contract_digest, submission_id),
            ).fetchall()
        return rows[0][0] if len(rows) == 1 else None

    def admitted_owner(self, submission_id):
        """``(contract_digest, hotkey)`` of the one contract a task was admitted under and its one owner, or None.

        For a task admitted under an EARLIER contract of this receiver (its pack has since changed): the owner
        `owned_outcome` gives under that contract. Two contracts, or two owners, fail closed (None).
        """
        with self._db() as db:
            rows = db.execute(
                "SELECT DISTINCT contract_digest, hotkey FROM ("
                "SELECT contract_digest, hotkey FROM attempts WHERE kind='OUTCOME' "
                "AND submission_id=? AND hotkey IS NOT NULL "
                "UNION ALL SELECT contract_digest, hotkey FROM recipe_task_intents "
                "WHERE submission_id=? )",
                (submission_id, submission_id),
            ).fetchall()
        if len(rows) != 1:
            return None
        contract, hotkey = rows[0]
        if self.owned_outcome(contract, submission_id) != hotkey:
            return None
        return contract, hotkey

    def record_recipe_task_intent(
        self, contract_digest, submission_id, hotkey, request_sha256
    ):
        """Durably bind an authenticated owner before direct-task persistence.

        Repeating the same intent is safe. A conflicting owner or request is
        refused before it can be interpreted as an admitted task.
        """
        values = (contract_digest, submission_id, _kept(hotkey), request_sha256)
        if not all(type(value) is str and value for value in values):
            raise ValueError("recipe task intent incomplete")
        with self._db() as db:
            prior_owners = db.execute(
                "SELECT DISTINCT hotkey FROM attempts WHERE kind='OUTCOME' "
                "AND contract_digest=? AND submission_id=? AND hotkey IS NOT NULL",
                values[:2],
            ).fetchall()
            if any(owner != (values[2],) for owner in prior_owners):
                raise ValueError("recipe task intent owner conflict")
            db.execute(
                "INSERT OR IGNORE INTO recipe_task_intents VALUES(?,?,?,?)", values
            )
            row = db.execute(
                "SELECT contract_digest,submission_id,hotkey,request_sha256 "
                "FROM recipe_task_intents WHERE contract_digest=? AND submission_id=?",
                values[:2],
            ).fetchone()
            if row != values:
                raise ValueError("recipe task intent conflict")

    def record_catalog_submission(self, contract_digest, submission_id, document):
        """Keep the miner's own catalog recipe behind a direct task, create-only
        (OWNER-BACKBONE-CATALOG-01, Validator: the catalog recipe is the
        submission identity; the task runs the bundle it expands to). The
        same bytes again are accepted; different bytes are refused."""
        if (
            type(contract_digest) is not str
            or type(submission_id) is not str
            or type(document) is not bytes
            or not contract_digest
            or not submission_id
            or not document
        ):
            raise ValueError("catalog submission incomplete")
        with self._db() as db:
            db.execute(
                "INSERT OR IGNORE INTO catalog_submissions VALUES(?,?,?)",
                (contract_digest, submission_id, document),
            )
            row = db.execute(
                "SELECT document FROM catalog_submissions "
                "WHERE contract_digest=? AND submission_id=?",
                (contract_digest, submission_id),
            ).fetchone()
            if row is None or bytes(row[0]) != document:
                raise ValueError("catalog submission conflict")

    def catalog_submission(self, contract_digest, submission_id):
        """The catalog submission document behind a task, or None."""
        with self._db() as db:
            row = db.execute(
                "SELECT document FROM catalog_submissions "
                "WHERE contract_digest=? AND submission_id=?",
                (contract_digest, submission_id),
            ).fetchone()
        return None if row is None else bytes(row[0])

    def submitted_outcomes(self, contract_digest):
        """Authenticated task IDs for one adapter's restart-safe advance pass, OLDEST SUBMISSION FIRST (slow-tail F0,
        Lead / TE-B 8 Nov): by each task's first OUTCOME row (its accepted submission), then any intent-only task
        (an interrupted start, no OUTCOME yet) by id. The rebuild pass (`LeanRecipeAdapter.advance`) and the grader
        (`AutoGrader.pending`) both walk this order, so no newer submission is rebuilt or graded before an older one
        of the same door. (It was by id, random hex, so an older task could be jumped again and again.)
        """
        with self._read() as db:
            rows = db.execute(
                "SELECT t.submission_id FROM ("
                "SELECT submission_id, MIN(seq) AS first FROM attempts WHERE kind='OUTCOME' "
                "AND contract_digest=? AND submission_id IS NOT NULL GROUP BY submission_id "
                "UNION ALL SELECT submission_id, NULL FROM recipe_task_intents "
                "WHERE contract_digest=? ) AS t "
                "LEFT JOIN queue_place_grants AS g ON g.contract_digest=? AND g.new_task=t.submission_id "
                "GROUP BY t.submission_id "
                "ORDER BY MIN(COALESCE(g.place_seq, t.first)) IS NULL, MIN(COALESCE(g.place_seq, t.first)), "
                "t.submission_id",
                (contract_digest, contract_digest, contract_digest),
            ).fetchall()
        return tuple(row[0] for row in rows)

    def submitted_since(self, contract_digest, hotkey, since_ns, *, exclude=()):
        """Whether ``hotkey`` had a submission accepted on ``contract_digest`` after ``since_ns``: its own, never a door
        re-run's copied row (code `BUILD_REQUEUED`) nor a task in ``exclude`` (the failed task's own chain). Owner
        G-LEAD-10: Carbon's one rebuild is skipped when it did."""
        read = getattr(self, "_read", None)
        with read() if callable(read) else self._db() as db:
            rows = db.execute(
                "SELECT submission_id FROM attempts WHERE kind='OUTCOME' AND contract_digest=? AND hotkey=? "
                "AND at_ns>? AND COALESCE(code, '')<>?",
                (contract_digest, _kept(hotkey), int(since_ns), self.BUILD_REQUEUED),
            ).fetchall()
        excluded = set(exclude)
        return any(row[0] not in excluded for row in rows)

    def grant_queue_place(self, contract_digest, *, from_task, new_task, hotkey):
        """Give ``new_task`` (the resubmission of the recipe of ``from_task``, a task a receiver stop cancelled) the ORIGINAL
        arrival place of ``from_task`` in `submitted_outcomes`, ONCE per ``from_task`` and only to the SAME hotkey.

        The place is ``from_task``'s first OUTCOME row (its accepted submission); it is a pure ordering fact, written to its
        own table: no attempt row, no slot, no score. Returns ``"granted"``, ``"already_granted"`` (the same pair again),
        or a refusal code: ``"no_original"`` (``from_task`` has no accepted submission here), ``"hotkey_mismatch"``,
        ``"from_task_used"`` (it already gave its place to another task), ``"same_task"`` or ``"incomplete"``.
        """
        values = (contract_digest, from_task, new_task, hotkey)
        if not all(type(value) is str and value for value in values):
            return "incomplete"
        if from_task == new_task:
            return "same_task"
        with self._db() as db:
            original = db.execute(
                "SELECT MIN(seq), MIN(hotkey), MAX(hotkey) FROM attempts WHERE kind='OUTCOME' "
                "AND contract_digest=? AND submission_id=? AND hotkey IS NOT NULL",
                (contract_digest, from_task),
            ).fetchone()
            if original is None or original[0] is None:
                return "no_original"
            if original[1] != _kept(hotkey) or original[2] != _kept(hotkey):
                return "hotkey_mismatch"
            prior = db.execute(
                "SELECT new_task FROM queue_place_grants WHERE contract_digest=? AND from_task=?",
                (contract_digest, from_task),
            ).fetchone()
            if prior is not None:
                return "already_granted" if prior[0] == new_task else "from_task_used"
            if db.execute(
                "SELECT 1 FROM queue_place_grants WHERE contract_digest=? AND new_task=?",
                (contract_digest, new_task),
            ).fetchone():
                return "from_task_used"  # this task already holds another task's place
            db.execute(
                "INSERT INTO queue_place_grants VALUES(?,?,?,?,?,?)",
                (
                    contract_digest,
                    new_task,
                    from_task,
                    _kept(hotkey),
                    _place(db, contract_digest, from_task, original[0]),
                    int(self.clock()),
                ),
            )
        return "granted"

    #: The code of the accepted-submission row a build requeue copies (`requeue_failed_build`): the door's, not a miner's.
    BUILD_REQUEUED = "build_requeued"

    def requeue_failed_build(
        self,
        contract_digest,
        *,
        from_task,
        new_task,
        hotkey,
        apply=True,
        operator=False,
    ):
        """Order 3 (Lead 17 Nov 2026, handoff s3 item 5): ``new_task`` (the next generation of ``from_task``'s recipe, a
        build that ended on Carbon's infrastructure) is queued ONCE at ``from_task``'s ORIGINAL place, as if its miner had
        resubmitted then: in one transaction it takes ``from_task``'s place (`queue_place_grants`, the stop-cancel
        mechanism) and an accepted-submission row copied from ``from_task``'s first one (its signed receipt, so the grade
        keeps the original epoch; code `BUILD_REQUEUED`). Returns ``"requeued"`` or a refusal, nothing written:
        ``"no_original"``, ``"hotkey_mismatch"``, ``"same_task"``, ``"incomplete"``, ``"from_task_is_a_requeue"`` (a task
        the door itself requeued is never requeued again: once), ``"from_task_used"`` / ``"already_requeued"`` (its place
        was already given), ``"new_task_holds_a_place"`` or ``"new_task_known"`` (the miner already resubmitted it).
        The place is ``from_task``'s own, or the one IT holds (a stop-cancel resubmission's): never a later one.
        ``apply=False``: the same answer, ``"requeuable"`` instead of ``"requeued"``, nothing written.
        ``operator`` (the operator's build re-arm on Validator-2's receipt, 17 Nov): the one refusal it lifts is
        ``"from_task_is_a_requeue"``; every other check stands (a place is still given once per task).
        """
        values = (contract_digest, from_task, new_task, hotkey)
        if not all(type(value) is str and value for value in values):
            return "incomplete"
        if from_task == new_task:
            return "same_task"
        with self._db() as db:
            original = db.execute(
                "SELECT seq, hotkey, receipt, submission_sha256, state FROM attempts WHERE kind='OUTCOME' "
                "AND contract_digest=? AND submission_id=? ORDER BY seq LIMIT 1",
                (contract_digest, from_task),
            ).fetchone()
            if original is None:
                return "no_original"
            if original[1] != _kept(hotkey):
                return "hotkey_mismatch"
            first_code = db.execute(
                "SELECT code FROM attempts WHERE kind='OUTCOME' AND contract_digest=? AND submission_id=? "
                "ORDER BY seq LIMIT 1",
                (contract_digest, from_task),
            ).fetchone()[0]
            if first_code == self.BUILD_REQUEUED and not operator:
                return "from_task_is_a_requeue"
            prior = db.execute(
                "SELECT new_task FROM queue_place_grants WHERE contract_digest=? AND from_task=?",
                (contract_digest, from_task),
            ).fetchone()
            if prior is not None:
                return "already_requeued" if prior[0] == new_task else "from_task_used"
            if db.execute(
                "SELECT 1 FROM queue_place_grants WHERE contract_digest=? AND new_task=?",
                (contract_digest, new_task),
            ).fetchone():
                return "new_task_holds_a_place"
            if db.execute(
                "SELECT 1 FROM attempts WHERE kind='OUTCOME' AND contract_digest=? AND submission_id=?",
                (contract_digest, new_task),
            ).fetchone():
                return "new_task_known"
            if not apply:
                return "requeuable"
            now = int(self.clock())
            db.execute(
                "INSERT INTO queue_place_grants VALUES(?,?,?,?,?,?)",
                (
                    contract_digest,
                    new_task,
                    from_task,
                    _kept(hotkey),
                    _place(db, contract_digest, from_task, original[0]),
                    now,
                ),
            )
            db.execute(
                "INSERT INTO attempts(at_ns, kind, code, hotkey, contract_digest,"
                " receipt, submission_sha256, submission_id, state)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    now,
                    "OUTCOME",
                    self.BUILD_REQUEUED,
                    original[1],
                    contract_digest,
                    original[2],
                    original[3],
                    new_task,
                    original[4],
                ),
            )
        return "requeued"

    def record_miner_withdrawal(self, contract_digest, submission_id, hotkey):
        """Record that ``hotkey`` withdrew its own queued submission ``submission_id`` (`LeanRecipeAdapter.withdraw`), ONCE:
        the first row stands (its time is the first record's) and the same withdrawal again changes nothing. The task's
        intent and OUTCOME rows are kept, so its owner still resolves. A pure record: no attempt row, no slot, no score.
        Returns the stored ``(hotkey, at_ns)``; a row of another hotkey or contract for the same id refuses (ValueError).
        """
        values = (contract_digest, submission_id, hotkey)
        if not all(type(value) is str and value for value in values):
            raise ValueError("miner withdrawal incomplete")
        with self._db() as db:
            db.execute(
                "INSERT OR IGNORE INTO miner_withdrawals VALUES(?,?,?,?)",
                (contract_digest, submission_id, _kept(hotkey), int(self.clock())),
            )
            row = db.execute(
                "SELECT contract_digest, hotkey, at_ns FROM miner_withdrawals WHERE submission_id=?",
                (submission_id,),
            ).fetchone()
        if row is None or row[0] != contract_digest or row[1] != _kept(hotkey):
            raise ValueError("miner withdrawal conflict")
        return row[1], int(row[2])

    def miner_withdrawal(self, contract_digest, submission_id):
        """``(hotkey, at_ns)`` of ``submission_id``'s withdrawal by its owner under ``contract_digest``, or None."""
        with self._db() as db:
            row = db.execute(
                "SELECT hotkey, at_ns FROM miner_withdrawals WHERE contract_digest=? AND submission_id=?",
                (contract_digest, submission_id),
            ).fetchone()
        return None if row is None else (row[0], int(row[1]))

    def queue_place_from_tasks(self, contract_digest):
        """The tasks that already GAVE their queue place (`grant_queue_place`: once per task), read only."""
        with self._read() as db:
            rows = db.execute(
                "SELECT from_task FROM queue_place_grants WHERE contract_digest=?",
                (contract_digest,),
            ).fetchall()
        return {row[0] for row in rows}

    def queue_place_origins(self, contract_digest):
        """``{new task id: the ORIGINAL task's accepted time (ns)}`` for every task that holds a queue place (`grant_queue_place`): the time of
        the granted-from task's first OUTCOME row, the arrival whose place the new task took. A read only: the public queue rows count a
        granted task's wait from it, so the clock agrees with the rank. A grant whose original has no OUTCOME row is not listed.
        """
        with self._db() as db:
            rows = db.execute(
                "SELECT g.new_task, MIN(a.at_ns) FROM queue_place_grants AS g "
                "JOIN attempts AS a ON a.contract_digest=g.contract_digest AND a.submission_id=g.from_task "
                "AND a.kind='OUTCOME' WHERE g.contract_digest=? GROUP BY g.new_task",
                (contract_digest,),
            ).fetchall()
        return {task: int(ns) for task, ns in rows if ns is not None}

    def first_outcome_ns(self, contract_digest, submission_id):
        """When the task's submission was accepted (its first OUTCOME row's ``at_ns``), or None."""
        with self._read() as db:
            row = db.execute(
                "SELECT at_ns FROM attempts WHERE kind='OUTCOME' AND contract_digest=? AND submission_id=? "
                "ORDER BY seq LIMIT 1",
                (contract_digest, submission_id),
            ).fetchone()
        return None if row is None else int(row[0])

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
            spilled = db.execute(
                "SELECT kind, SUM(count) FROM overflow GROUP BY kind"
            ).fetchall()
        totals = dict.fromkeys(KINDS, 0)
        for kind, count in [*rows, *spilled]:
            totals[kind] += count
        return totals

    def attempt_counts(self, hotkey):
        """Attempts by this hotkey: in total, by kind and by contract digest."""
        with self._db() as db:
            rows = db.execute(
                "SELECT kind, contract_digest, COUNT(*) FROM attempts"
                " WHERE hotkey=? GROUP BY kind, contract_digest",
                (_kept(hotkey),),
            ).fetchall()
            spilled = db.execute(
                "SELECT kind, NULLIF(contract_digest, ''), SUM(count) FROM overflow"
                " WHERE hotkey=? GROUP BY kind, contract_digest",
                (_kept(hotkey),),
            ).fetchall()
        rows = [*rows, *spilled]
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


def public_status_counts(path, contract_digest, hotkeys):
    """PLT-08's count-only exception to operator-only records.

    Read an existing ledger, never initialize one for a display. The query
    selects no receipts, times, hashes, strategies or submission/window ids.
    Only the served contract and supplied public chain identities count.
    """
    from .dispatch import SCREEN_REFUSALS

    codes = {
        *SCREEN_REFUSALS,
        "hotkey_window_used",
        "receipt_block_missing",
        "level4_envelope_incomplete",
        "unclassified_refusal",
    }
    path = Path(path)
    try:
        info, parent = os.lstat(path), os.lstat(path.parent)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_mode & 0o077
            or not stat.S_ISDIR(parent.st_mode)
            or parent.st_mode & 0o077
        ):
            raise LedgerUnavailable("status_ledger_not_owner_only")
        with contextlib.closing(
            sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        ) as db:
            db.execute("BEGIN")
            if db.execute("SELECT value FROM meta WHERE key='schema'").fetchone() != (
                SCHEMA,
            ):
                raise LedgerUnavailable("status_ledger_schema")
            rows = db.execute(
                "SELECT hotkey, kind, code, COUNT(*) FROM attempts "
                "WHERE contract_digest=? AND kind IN ('RECEIVED','REFUSED') "
                "GROUP BY hotkey, kind, code",
                (contract_digest,),
            ).fetchall()
            rows += db.execute(
                "SELECT hotkey, kind, code, SUM(count) FROM overflow "
                "WHERE contract_digest=? AND kind='REFUSED' GROUP BY hotkey, kind, code",
                (contract_digest,),
            ).fetchall()
    except (OSError, sqlite3.Error):
        raise LedgerUnavailable("status_ledger_unavailable") from None
    found = {
        hotkey: {"hotkey": hotkey, "received": 0, "refused": {}} for hotkey in hotkeys
    }
    for hotkey, kind, code, count in rows:
        if hotkey not in hotkeys:
            continue
        row = found.setdefault(hotkey, {"hotkey": hotkey, "received": 0, "refused": {}})
        if kind == "RECEIVED":
            row["received"] += count
        else:
            closed = code if code in codes else "unclassified_refusal"
            row["refused"][closed] = row["refused"].get(closed, 0) + count
    return found
